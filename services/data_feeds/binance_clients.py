"""
Binance REST and WebSocket clients for data feeds.
"""
import aiohttp
import asyncio
import websockets
import json
import time
from typing import Optional, Dict, List, Callable
from datetime import datetime
from .schemas import OIData, FundingData, BasisData, LiquidationEvent, DepthSnapshot, BookTickerData


class BinanceRESTClient:
    """Async REST client for Binance Futures API"""
    
    BASE_URL = "https://fapi2.binance.com"
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
    
    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    async def get_open_interest_hist(self, symbol: str, period: str = "5m", limit: int = 2) -> List[OIData]:
        """
        Get Open Interest history.
        
        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
            limit: Number of data points (max 500)
        """
        endpoint = f"{self.BASE_URL}/futures/data/openInterestHist"
        params = {"symbol": symbol, "period": period, "limit": limit}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return [OIData(**item) for item in data]
                else:
                    print(f"[REST ERROR] OI {symbol}: HTTP {resp.status}")
                    return []
        except Exception as e:
            print(f"[REST ERROR] OI {symbol}: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str, limit: int = 1) -> Optional[FundingData]:
        """Get current/recent funding rate"""
        endpoint = f"{self.BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": limit}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return FundingData(**data[0])
                else:
                    print(f"[REST ERROR] Funding {symbol}: HTTP {resp.status}")
        except Exception as e:
            print(f"[REST ERROR] Funding {symbol}: {e}")
        return None
    
    async def get_premium_index(self, symbol: str) -> Optional[BasisData]:
        """Get premium index (mark price, index price, funding)"""
        endpoint = f"{self.BASE_URL}/fapi/v1/premiumIndex"
        params = {"symbol": symbol}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return BasisData(**data)
                else:
                    print(f"[REST ERROR] Basis {symbol}: HTTP {resp.status}")
        except Exception as e:
            print(f"[REST ERROR] Basis {symbol}: {e}")
        return None


class BinanceWebSocketClient:
    """WebSocket client for liquidations and order book depth"""
    
    WS_BASE = "wss://fstream2.binance.com"
    
    def __init__(self):
        self.ws = None
        self.running = False
        self.callbacks: Dict[str, Callable] = {}
    
    async def subscribe_liquidations(self, callback: Callable):
        """
        Subscribe to aggregated liquidations stream.
        Stream: !forceOrder@arr (all symbols)
        """
        stream_url = f"{self.WS_BASE}/ws/!forceOrder@arr"
        self.callbacks['liquidations'] = callback
        
        asyncio.create_task(self._ws_loop(stream_url, 'liquidations'))
    
    async def subscribe_book_ticker(self, symbols: List[str], callback: Callable):
        """
        Subscribe to combined bookTicker stream for all symbols.
        Stream: wss://fstream.binance.com/stream?streams=symbol1@bookTicker/symbol2@bookTicker/...
        """
        streams = '/'.join([f"{symbol.lower()}@bookTicker" for symbol in symbols])
        stream_url = f"{self.WS_BASE}/stream?streams={streams}"
        
        self.callbacks['book_ticker'] = callback
        asyncio.create_task(self._ws_loop(stream_url, 'book_ticker'))
    
    async def subscribe_mark_price(self, callback: Callable):
        """
        Subscribe to aggregated markPrice stream for all symbols.
        Stream: !markPrice@arr (all USDⓈ-M symbols, 1s or 3s updates)
        """
        stream_url = f"{self.WS_BASE}/ws/!markPrice@arr"
        
        self.callbacks['mark_price'] = callback
        asyncio.create_task(self._ws_loop(stream_url, 'mark_price'))
    
    async def subscribe_depth(self, symbol: str, callback: Callable, levels: int = 5):
        """
        Subscribe to order book depth.
        Stream: <symbol>@depth<levels>@100ms
        """
        stream_name = f"{symbol.lower()}@depth{levels}@100ms"
        stream_url = f"{self.WS_BASE}/ws/{stream_name}"
        
        callback_key = f"depth_{symbol}"
        self.callbacks[callback_key] = callback
        
        asyncio.create_task(self._ws_loop(stream_url, callback_key))
    
    async def _ws_loop(self, url: str, callback_key: str):
        """WebSocket connection loop with auto-reconnect"""
        retry_delay = 1
        max_retry_delay = 60
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    print(f"[WS] Connected: {callback_key}")
                    retry_delay = 1  # Reset on successful connection
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            
                            if 'depth_' in callback_key:
                                print(f"[WS RAW] {callback_key} - keys: {list(data.keys())[:5]}")
                            
                            if callback_key in self.callbacks:
                                await self.callbacks[callback_key](data)
                            else:
                                print(f"[WS ERROR] No callback registered for {callback_key}")
                        
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"[WS ERROR] {callback_key} processing: {e}")
            
            except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
                print(f"[WS ERROR] {callback_key} connection: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            
            except Exception as e:
                print(f"[WS FATAL] {callback_key}: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
    
    @staticmethod
    def parse_liquidation(data: dict) -> Optional[LiquidationEvent]:
        """Parse liquidation event from WebSocket"""
        try:
            order = data.get('o', {})
            return LiquidationEvent(
                symbol=order['s'],
                side=order['S'],
                order_type=order['o'],
                time_in_force=order['f'],
                original_qty=float(order['q']),
                price=float(order['p']),
                avg_price=float(order['ap']),
                order_status=order['X'],
                order_last_filled_qty=float(order['l']),
                order_filled_accumulated_qty=float(order['z']),
                order_trade_time=order['T']
            )
        except (KeyError, ValueError, TypeError):
            return None
    
    @staticmethod
    def parse_depth(data: dict, symbol: str) -> Optional[DepthSnapshot]:
        """Parse depth snapshot from WebSocket (Partial Book Depth Stream)"""
        try:
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if not bids or not asks:
                return None
            
            return DepthSnapshot(
                symbol=symbol,
                bids=[[float(p), float(q)] for p, q in bids],
                asks=[[float(p), float(q)] for p, q in asks],
                timestamp=data.get('E', int(time.time() * 1000))
            )
        except (KeyError, ValueError, TypeError):
            return None
