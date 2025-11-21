"""
Download Historical Data from Binance for All Symbols
Fetches 1 month of 5-minute candles for backtesting
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import yaml

print("="*80)
print("DOWNLOADING HISTORICAL DATA FOR BACKTESTING")
print("="*80)

# Load symbols from config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

symbols = config['symbols']
print(f"\nSymbols to download: {symbols}")

# Binance API endpoint
BINANCE_API = "https://fapi.binance.com"

def download_klines(symbol, interval='5m', days=30):
    """Download historical klines from Binance Futures"""
    
    # Calculate start and end timestamps
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    print(f"\nDownloading {symbol} ({interval} candles, last {days} days)...")
    
    all_klines = []
    current_start = start_time
    
    while current_start < end_time:
        url = f"{BINANCE_API}/fapi/v1/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_time,
            'limit': 1500  # Max limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            
            if not klines:
                break
            
            all_klines.extend(klines)
            
            # Update start time for next batch
            current_start = klines[-1][0] + 1
            
            print(f"  Downloaded {len(all_klines)} candles so far...", end='\r')
            
            # Rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            print(f"\n  Error downloading {symbol}: {e}")
            break
    
    if not all_klines:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
        df[col] = df[col].astype(float)
    
    # Keep only needed columns
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']]
    
    print(f"\n  ✅ Downloaded {len(df)} candles for {symbol}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

# Download data for all symbols
all_data = {}

for symbol in symbols:
    df = download_klines(symbol, interval='5m', days=30)
    if df is not None:
        all_data[symbol] = df
        
        # Save to CSV
        filename = f"historical_data/{symbol}_5m.csv"
        df.to_csv(filename, index=False)
        print(f"  Saved to {filename}")

print("\n" + "="*80)
print("DOWNLOAD SUMMARY")
print("="*80)

for symbol, df in all_data.items():
    print(f"{symbol:<12} {len(df):>6} candles  {df['timestamp'].min()} to {df['timestamp'].max()}")

print(f"\nTotal symbols: {len(all_data)}")
print(f"✅ All data saved to historical_data/ directory")
