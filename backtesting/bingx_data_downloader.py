#!/usr/bin/env python3
"""
BingX Data Downloader
Downloads historical OHLCV data from BingX API (no auth required for market data)
"""

import requests
import pandas as pd
import yaml
import time
from datetime import datetime, timedelta
from pathlib import Path

class BingXDataDownloader:
    def __init__(self):
        self.base_url = "https://open-api.bingx.com"
        
        # Load config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = self.config.get('symbols', [])
        
    def _format_symbol_for_api(self, symbol: str) -> str:
        """Convert BTCUSDT to BTC-USDT format"""
        if '-' in symbol:
            return symbol
        return symbol.replace('USDT', '-USDT').replace('USDC', '-USDC')
    
    def download_klines(self, symbol, start_ts, end_ts, interval='5m'):
        """
        Download kline/OHLCV data from BingX
        
        Args:
            symbol: Trading pair (BTCUSDT)
            start_ts: Start timestamp (seconds)
            end_ts: End timestamp (seconds)
            interval: 5m, 15m, 1h, etc.
        
        Returns:
            DataFrame with OHLCV data
        """
        formatted_symbol = self._format_symbol_for_api(symbol)
        
        # Convert to milliseconds
        start_ms = int(start_ts * 1000)
        end_ms = int(end_ts * 1000)
        
        # BingX limit: 1440 candles per request
        # For 5m candles: 1440 * 5min = 7200min = 5 days
        max_candles = 1440
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720,
            '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
        }
        
        interval_min = interval_minutes.get(interval, 5)
        chunk_duration_ms = max_candles * interval_min * 60 * 1000
        
        all_data = []
        current_start = start_ms
        
        while current_start < end_ms:
            current_end = min(current_start + chunk_duration_ms, end_ms)
            
            params = {
                'symbol': formatted_symbol,
                'interval': interval,
                'startTime': current_start,
                'endTime': current_end,
                'limit': max_candles
            }
            
            try:
                # Public endpoint - NO authentication required!
                response = requests.get(
                    f"{self.base_url}/openApi/swap/v2/quote/klines",
                    params=params,
                    timeout=10
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('code') != 0:
                    print(f"❌ API Error: {result.get('msg')}")
                    break
                
                data = result.get('data', [])
                
                if not data:
                    break
                
                all_data.extend(data)
                
                # Move to next chunk
                current_start = current_end + 1
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Error downloading {symbol}: {e}")
                break
        
        if not all_data:
            return None
        
        # BingX returns dict format: {'open': '...', 'close': '...', 'time': ...}
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        
        # Rename 'time' to 'timestamp' for consistency
        if 'time' in df.columns:
            df = df.rename(columns={'time': 'timestamp'})
        
        if 'timestamp' not in df.columns:
            print(f"  ❌ No timestamp column in data")
            return None
        
        # Convert types
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # BingX doesn't provide quote_volume, calculate it
        df['quote_volume'] = df['volume'] * df['close']
        
        # Drop rows with any NaN values
        df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        if df.empty:
            print(f"  ⚠️ No valid data after conversion")
            return None
        
        # Keep only needed columns
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']]
        
        return df
    
    def download_all_symbols(self, start_date=None, end_date=None):
        """
        Download data for all symbols
        """
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = datetime.now() - timedelta(days=30)
        
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_dt = datetime.now()
        
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())
        
        print("="*80)
        print("🔽 BINGX DATA DOWNLOAD")
        print("="*80)
        print(f"Period: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print("="*80)
        print()
        
        # Create data directory
        data_dir = Path('backtesting/data')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        for symbol in self.symbols:
            print(f"Downloading {symbol}...")
            
            df = self.download_klines(symbol, start_ts, end_ts, interval='5m')
            
            if df is not None and not df.empty:
                output_file = data_dir / f"{symbol}_5m.csv"
                df.to_csv(output_file, index=False)
                print(f"  ✅ Saved {len(df)} candles to {output_file}")
            else:
                print(f"  ❌ No data for {symbol}")
            
            print()
        
        print("="*80)
        print("✅ DOWNLOAD COMPLETE")
        print("="*80)

if __name__ == '__main__':
    import sys
    
    downloader = BingXDataDownloader()
    
    # Parse command line args
    start_date = sys.argv[1] if len(sys.argv) > 1 else None
    end_date = sys.argv[2] if len(sys.argv) > 2 else None
    
    downloader.download_all_symbols(start_date, end_date)
