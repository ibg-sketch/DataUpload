"""
Data Feeds Service Runner - Main entry point.

Collects OI, Funding, Basis, Liquidations, Order Book Imbalance for 11 symbols.
Runs in 30-second cycles, writes to append-only CSV with rotation.
"""
import asyncio
import aiohttp
import yaml
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.data_feeds.binance_clients import BinanceRESTClient, BinanceWebSocketClient
from services.data_feeds.coinalyze_client import CoinalyzeRESTClient
from services.data_feeds.spot_clients import BinanceSpotWebSocket, OKXSpotClient, BybitSpotClient, CoinbaseSpotClient
from services.data_feeds.synthetic_basis import SyntheticBasisCalculator
from services.data_feeds.calculators import FeedCalculators
from services.data_feeds.schemas import FeedRow
from services.data_feeds.writer import FeedWriter
from services.data_feeds.health import HealthMonitor
from services.data_feeds.status_server import StatusServer


class DataFeedsService:
    """Main service coordinator"""
    
    def __init__(self, config: dict):
        self.config = config
        self.data_feeds_config = config.get('data_feeds', {})
        self.feature_flags = config.get('feature_flags', {})
        
        # Get symbols from config
        self.symbols = self.data_feeds_config.get('symbols', config.get('symbols', []))
        if not self.symbols:
            raise ValueError("No symbols configured!")
        
        print(f"[INIT] Data Feeds Service starting with {len(self.symbols)} symbols:")
        print(f"[INIT] {', '.join(self.symbols)}")
        
        # Configuration
        self.interval_sec = self.data_feeds_config.get('interval_sec', 30)
        self.depth_levels = self.data_feeds_config.get('depth_levels', 3)
        self.rest_batch_size = self.data_feeds_config.get('concurrency', {}).get('rest_batch_size', 5)
        self.enable_synthetic_basis = self.feature_flags.get('enable_synthetic_basis', False)
        
        print(f"[INIT] Synthetic Basis: {'ENABLED' if self.enable_synthetic_basis else 'DISABLED'}")
        
        # Components
        self.writer = FeedWriter(
            csv_path=self.data_feeds_config.get('sinks', {}).get('csv_path', 'data/feeds_log.csv'),
            rotate_mb=self.data_feeds_config.get('sinks', {}).get('rotate_mb', 200),
            keep_files=self.data_feeds_config.get('sinks', {}).get('keep_files', 14)
        )
        
        self.health = HealthMonitor(self.symbols)
        self.calculator = FeedCalculators()
        
        # State tracking
        self.previous_oi: Dict[str, float] = {}  # For OI% calculation
        self.previous_obi: Dict[str, float] = {}  # For OBI EMA smoothing
        self.liquidations_buffer: Dict[str, Dict[str, float]] = defaultdict(lambda: {'long': 0.0, 'short': 0.0})
        self.obi_cache: Dict[str, Dict[str, float]] = {}  # {symbol: {bid_qty, ask_qty}}
        
        # Clients (initialized in start())
        self.rest_client: Optional[BinanceRESTClient] = None
        self.coinalyze_client: Optional[CoinalyzeRESTClient] = None
        self.ws_client: Optional[BinanceWebSocketClient] = None
        self.spot_ws_client: Optional[BinanceSpotWebSocket] = None
        self.okx_client: Optional[OKXSpotClient] = None
        self.bybit_client: Optional[BybitSpotClient] = None
        self.coinbase_client: Optional[CoinbaseSpotClient] = None
        self.synthetic_basis: Optional[SyntheticBasisCalculator] = None
        self.status_server: Optional[StatusServer] = None
    
    async def start(self):
        """Start the service"""
        print(f"[START] Data Feeds Service initialized")
        print(f"[START] Collection interval: {self.interval_sec}s")
        print(f"[START] Output: {self.data_feeds_config.get('sinks', {}).get('csv_path', 'data/feeds_log.csv')}")
        
        async with aiohttp.ClientSession() as session:
            self.coinalyze_client = CoinalyzeRESTClient(session=session)
            
            # Initialize synthetic basis components (REST-only, no WebSocket due to Binance blocking)
            if self.enable_synthetic_basis:
                self.okx_client = OKXSpotClient(session=session)
                self.bybit_client = BybitSpotClient(session=session)
                self.coinbase_client = CoinbaseSpotClient(session=session)
                self.synthetic_basis = SyntheticBasisCalculator(
                    spot_ws_client=None,  # Disabled - Binance blocked
                    okx_client=self.okx_client,
                    bybit_client=self.bybit_client,
                    coinbase_client=self.coinbase_client
                )
            
            # Start HTTP status server (internal-only port)
            self.status_server = StatusServer(self.health, port=8081)
            await self.status_server.start()
            
            try:
                # Main collection loop
                await self._collection_loop()
            finally:
                # Cleanup status server
                if self.status_server:
                    await self.status_server.stop()
    
    async def _start_websockets(self):
        """Initialize WebSocket subscriptions - DISABLED due to Binance geo-blocking"""
        print("[WS] Binance WebSocket disabled (HTTP 451 geo-blocking)")
        print("[WS] Liquidations: Use dedicated Liquidation Service instead")
        print("[WS] OBI: Disabled (bookTicker unavailable)")
        print("[WS] Synthetic Basis: Using REST-only approach (OKX/Bybit/Coinbase)")
    
    async def _on_liquidation(self, data: dict):
        """Handle liquidation WebSocket message"""
        liq_event = self.ws_client.parse_liquidation(data)
        if not liq_event or liq_event.symbol not in self.symbols:
            return
        
        # Calculate liquidation value in USD
        liq_value_usd = liq_event.original_qty * liq_event.avg_price
        
        # Aggregate liquidations per symbol
        # BUY liquidation = forced buy = long liquidated (bearish)
        # SELL liquidation = forced sell = short liquidated (bullish)
        if liq_event.side == 'BUY':
            self.liquidations_buffer[liq_event.symbol]['long'] += liq_value_usd
        elif liq_event.side == 'SELL':
            self.liquidations_buffer[liq_event.symbol]['short'] += liq_value_usd
    
    async def _on_book_ticker(self, data: dict):
        """Handle bookTicker WebSocket message from combined stream"""
        try:
            # Combined stream format: {"stream": "btcusdt@bookTicker", "data": {...}}
            if 'data' in data:
                ticker_data = data['data']
            else:
                ticker_data = data
            
            # Parse symbol (convert to uppercase)
            symbol = ticker_data.get('s', '').upper()
            if symbol not in self.symbols:
                return
            
            # Extract best bid/ask quantities
            best_bid_qty = float(ticker_data.get('B', 0))
            best_ask_qty = float(ticker_data.get('A', 0))
            
            # Calculate OBI: bid_qty / (bid_qty + ask_qty)
            total = best_bid_qty + best_ask_qty
            if total > 0:
                obi_raw = best_bid_qty / total
                
                # Apply EMA(5) smoothing
                previous_ema = self.previous_obi.get(symbol)
                obi_smoothed = self.calculator.smooth_ema(obi_raw, previous_ema, periods=5)
                self.previous_obi[symbol] = obi_smoothed
        
        except (KeyError, ValueError, TypeError) as e:
            pass  # Silently ignore parsing errors
    
    async def _on_mark_price(self, data: dict):
        """Handle markPrice WebSocket message from aggregated stream"""
        try:
            # markPrice@arr format: [{"s": "BTCUSDT", "p": "43500.00", ...}, ...]
            if isinstance(data, list):
                for ticker in data:
                    symbol = ticker.get('s', '').upper()
                    if symbol in self.symbols:
                        mark_price = float(ticker.get('p', 0))
                        if mark_price > 0 and self.synthetic_basis:
                            self.synthetic_basis.update_mark_price(symbol, mark_price)
        except (KeyError, ValueError, TypeError):
            pass  # Silently ignore parsing errors
    
    async def _collection_loop(self):
        """Main data collection loop"""
        cycle_num = 0
        
        while True:
            cycle_start = time.time()
            cycle_num += 1
            
            try:
                print(f"\n[CYCLE {cycle_num}] Starting data collection...")
                
                # Collect data for all symbols (pass cycle_start for latency calculation)
                rows = await self._collect_all_symbols(cycle_start)
                
                # Write to CSV
                self.writer.append_rows(rows)
                
                # Write snapshot JSON for smart_signal.py integration
                self._write_snapshot(rows)
                
                # Calculate latency
                latency_ms = int((time.time() - cycle_start) * 1000)
                self.health.record_cycle(latency_ms)
                
                print(f"[CYCLE {cycle_num}] ✅ Collected {len(rows)} symbols in {latency_ms}ms")
                
                # Print health summary every 10 cycles
                if cycle_num % 10 == 0:
                    self.health.print_summary()
                    writer_stats = self.writer.get_stats()
                    print(f"[WRITER] CSV: {writer_stats['rows']} rows, {writer_stats['size_mb']:.1f} MB, {writer_stats['rotated_files']} rotated files")
                
                # Clear liquidations buffer after writing
                self.liquidations_buffer.clear()
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.interval_sec - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    print(f"[WARNING] Cycle took {elapsed:.1f}s (>{self.interval_sec}s), skipping sleep")
            
            except Exception as e:
                print(f"[ERROR] Collection cycle failed: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(self.interval_sec)
    
    async def _collect_all_symbols(self, cycle_start: float) -> List[FeedRow]:
        """Collect data for all symbols in batches"""
        rows = []
        timestamp = datetime.now()
        
        # Process symbols in batches for REST API
        for i in range(0, len(self.symbols), self.rest_batch_size):
            batch = self.symbols[i:i + self.rest_batch_size]
            batch_rows = await asyncio.gather(*[
                self._collect_symbol_data(symbol, timestamp, cycle_start) 
                for symbol in batch
            ])
            rows.extend([r for r in batch_rows if r is not None])
        
        return rows
    
    async def _collect_symbol_data(self, symbol: str, timestamp: datetime, cycle_start: float) -> Optional[FeedRow]:
        """Collect all data for a single symbol with provider fallback"""
        errors = 0
        row_data = {
            'timestamp': timestamp,
            'symbol': symbol,
            'source_errors': 0,
            'latency_ms': int((time.time() - cycle_start) * 1000),
            'provider_oi': None,
            'provider_funding': None,
            'provider_basis': None
        }
        
        try:
            # === OI from Coinalyze ONLY (Binance blocked with HTTP 451) ===
            oi_data = await self.coinalyze_client.get_open_interest(symbol)
            if oi_data:
                current_oi = oi_data.sumOpenInterest
                row_data['oi'] = current_oi
                row_data['provider_oi'] = 'coinalyze'
                previous_oi = self.previous_oi.get(symbol)
                row_data['oi_pct'] = self.calculator.calculate_oi_pct(current_oi, previous_oi)
                self.previous_oi[symbol] = current_oi
            else:
                errors += 1
            
            # === Funding from Coinalyze ONLY (Binance blocked with HTTP 451) ===
            funding_data = await self.coinalyze_client.get_funding_rate(symbol)
            if funding_data:
                row_data['funding'] = funding_data.fundingRate
                row_data['provider_funding'] = 'coinalyze'
            else:
                errors += 1
            
            # === Basis removed - Binance API blocked, use Synthetic Basis only ===
            
            # Get liquidations from buffer
            liq = self.liquidations_buffer.get(symbol, {'long': 0.0, 'short': 0.0})
            row_data['liq_long_usd'] = liq['long']
            row_data['liq_short_usd'] = liq['short']
            row_data['liq_ratio'] = self.calculator.calculate_liq_ratio(liq['short'], liq['long'])
            
            # Get OBI from WebSocket state
            row_data['obi_top'] = self.previous_obi.get(symbol)
            
            # === Synthetic Basis (if enabled) ===
            if self.enable_synthetic_basis and self.synthetic_basis:
                basis_pct, basis_provider = await self.synthetic_basis.calculate_basis(symbol)
                row_data['basis_pct'] = basis_pct
                row_data['basis_provider'] = basis_provider
                
                # Track basis health
                if basis_pct is not None and basis_provider:
                    self.health.record_basis_success(basis_provider)
                else:
                    self.health.record_basis_failure()
                    errors += 1
            
            row_data['source_errors'] = errors
            
            # Update health - считать успехом если получены критически важные данные
            # OI или Funding обязательны, Basis опциональный (synthetic basis может не работать)
            has_critical_data = row_data.get('oi') is not None or row_data.get('funding') is not None
            if has_critical_data:
                self.health.record_success(symbol)
            else:
                self.health.record_error(symbol, "No critical data (OI/Funding)")
            
            return FeedRow(**row_data)
        
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
            self.health.record_error(symbol, str(e))
            return None
    
    def _write_snapshot(self, rows: List[FeedRow]):
        """
        Write latest feeds snapshot to JSON file with atomic writes.
        Used by smart_signal.py for basis_pct integration.
        """
        try:
            import json
            import os
            import tempfile
            from pathlib import Path
            
            # Prepare snapshot data
            snapshot = {
                'ts': int(time.time()),  # Unix timestamp of snapshot build
                'symbols': {}
            }
            
            for row in rows:
                if row and row.symbol:
                    snapshot['symbols'][row.symbol] = {
                        'basis_pct': row.basis_pct if row.basis_pct is not None else None,
                        'provider': row.basis_provider if row.basis_provider else None,
                        'funding': row.funding if row.funding is not None else None,
                        'oi_pct': row.oi_pct if row.oi_pct is not None else None,
                        'updated': int(row.timestamp.timestamp()) if row.timestamp else int(time.time())
                    }
            
            # Atomic write: temp file + fsync + rename
            snapshot_path = Path('data/feeds_snapshot.json')
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temp file in same directory for atomic rename
            fd, temp_path = tempfile.mkstemp(
                suffix='.tmp',
                prefix='feeds_snapshot_',
                dir=snapshot_path.parent,
                text=True
            )
            
            try:
                # Write to temp file
                with os.fdopen(fd, 'w') as f:
                    json.dump(snapshot, f, separators=(',', ':'))
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data written to disk
                
                # Atomic rename (POSIX guarantees atomicity)
                os.replace(temp_path, str(snapshot_path))
                
            except Exception as e:
                # Cleanup temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
            
        except Exception as e:
            print(f"[SNAPSHOT ERROR] Failed to write feeds_snapshot.json: {e}")


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent.parent / 'config.yaml'
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def main():
    """Main entry point"""
    print("=" * 60)
    print("DATA FEEDS SERVICE - OI, Funding, Basis, Liquidations, OBI")
    print("=" * 60)
    
    # Load config
    config = load_config()
    
    # Check feature flag
    if not config.get('feature_flags', {}).get('enable_data_feeds', False):
        print("[DISABLED] feature_flags.enable_data_feeds is False")
        print("[DISABLED] Service will not start")
        return
    
    # Start service
    service = DataFeedsService(config)
    await service.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Data Feeds Service stopped by user")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
