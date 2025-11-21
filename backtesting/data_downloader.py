#!/usr/bin/env python3
"""
Historical Data Downloader
Downloads 1 month of 5-minute candle data for all coins
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import yaml

class DataDownloader:
    def __init__(self):
        self.coinalyze_key = os.getenv('COINALYZE_API_KEY')
        self.base_url = "https://api.coinalyze.net/v1"
        
        # Load config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = self.config.get('symbols', [])
        
    def download_ohlcv(self, symbol, start_ts, end_ts, interval='5m'):
        """
        Download OHLCV data from Coinalyze
        """
        # Convert BTCUSDT to BTC for Coinalyze
        base_symbol = symbol.replace('USDT', '')
        
        url = f"{self.base_url}/futures/history"
        params = {
            'api_key': self.coinalyze_key,
            'symbols': base_symbol,
            'interval': interval,
            'from': int(start_ts),
            'to': int(end_ts),
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"Error downloading {symbol}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Exception downloading {symbol}: {e}")
            return None
    
    def download_binance_klines(self, symbol, start_time, end_time, interval='5m'):
        """
        Download klines from Binance as backup/supplement
        """
        url = "https://fapi.binance.com/fapi/v1/klines"
        
        all_klines = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': symbol,
                'interval': interval,
                'startTime': int(current_start * 1000),
                'endTime': int(end_time * 1000),
                'limit': 1500
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    klines = response.json()
                    
                    if not klines:
                        break
                    
                    all_klines.extend(klines)
                    
                    # Update start time to last candle
                    current_start = klines[-1][0] / 1000 + 300  # +5 min
                    
                    print(f"  Downloaded {len(klines)} candles, total: {len(all_klines)}")
                    
                    time.sleep(0.5)  # Rate limit
                else:
                    print(f"Error: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"Exception: {e}")
                break
        
        return all_klines
    
    def download_all_data(self, days=None, start_date=None):
        """
        Download data for all symbols
        days: number of days back (default 30)
        start_date: specific start date (overrides days) e.g., '2025-01-01'
        """
        end_time = datetime.now()
        
        if start_date:
            start_time = datetime.strptime(start_date, '%Y-%m-%d')
        elif days:
            start_time = end_time - timedelta(days=days)
        else:
            start_time = end_time - timedelta(days=30)
        
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        print(f"Downloading data from {start_time} to {end_time}")
        print(f"Symbols: {', '.join(self.symbols)}")
        
        os.makedirs('backtesting/data', exist_ok=True)
        
        for symbol in self.symbols:
            print(f"\n{'='*60}")
            print(f"Downloading {symbol}...")
            print(f"{'='*60}")
            
            # Download from Binance
            klines = self.download_binance_klines(symbol, start_ts, end_ts)
            
            if klines:
                # Convert to DataFrame
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                # Convert types
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                    df[col] = df[col].astype(float)
                
                # Save to CSV
                filename = f"backtesting/data/{symbol}_5m.csv"
                df.to_csv(filename, index=False)
                
                print(f"✅ Saved {len(df)} candles to {filename}")
                print(f"   Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
            else:
                print(f"❌ Failed to download {symbol}")
            
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print("✅ Download complete!")
        print(f"{'='*60}")

if __name__ == '__main__':
    import sys
    
    downloader = DataDownloader()
    
    # Check for start_date argument
    if len(sys.argv) > 1 and sys.argv[1].startswith('--start='):
        start_date = sys.argv[1].replace('--start=', '')
        print(f"Using custom start date: {start_date}")
        downloader.download_all_data(start_date=start_date)
    else:
        # Default: from January 1, 2025
        downloader.download_all_data(start_date='2025-01-01')
