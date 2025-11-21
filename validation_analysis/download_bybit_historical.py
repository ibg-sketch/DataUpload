"""
Download Historical Data from Bybit (No Geo-Blocking!)
Fetches 30 days of 5-minute candles for backtesting
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import yaml

print("="*80)
print("DOWNLOADING HISTORICAL DATA FROM BYBIT")
print("="*80)

# Load symbols from config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

symbols = config['symbols']
print(f"\nSymbols to download: {symbols}")

BYBIT_API = "https://api.bybit.com"

def download_bybit_klines(symbol, interval='5', days=30):
    """
    Download historical klines from Bybit
    interval in minutes: 1,3,5,15,30,60,120,240,360,720,D,W,M
    """
    
    # Calculate timestamps (Bybit uses Unix seconds, not ms)
    end_time = int(datetime.now().timestamp())
    start_time = int((datetime.now() - timedelta(days=days)).timestamp())
    
    print(f"\nDownloading {symbol} (interval={interval}min, last {days} days)...")
    
    all_klines = []
    current_start = start_time
    
    # Bybit returns max 200 bars per request
    interval_seconds = int(interval) * 60
    
    while current_start < end_time:
        url = f"{BYBIT_API}/v5/market/kline"
        params = {
            'category': 'linear',  # USDT perpetual
            'symbol': symbol,
            'interval': interval,
            'start': current_start * 1000,  # Convert to ms
            'end': end_time * 1000,
            'limit': 200
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['retCode'] != 0:
                print(f"\n  Error: {data['retMsg']}")
                break
            
            klines = data['result']['list']
            
            if not klines:
                break
            
            all_klines.extend(klines)
            
            print(f"  Downloaded {len(all_klines)} candles so far...", end='\r')
            
            # Bybit returns newest first, so get oldest timestamp for next batch
            oldest_timestamp = int(klines[-1][0]) // 1000
            
            # If we've reached our start time, stop
            if oldest_timestamp <= start_time:
                break
            
            # Next batch ends where this one started
            end_time = oldest_timestamp - 1
            
            # Rate limiting
            time.sleep(0.2)
            
        except Exception as e:
            print(f"\n  Error downloading {symbol}: {e}")
            break
    
    if not all_klines:
        return None
    
    # Convert to DataFrame
    # Bybit format: [timestamp, open, high, low, close, volume, turnover]
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    
    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    
    # Sort by timestamp (Bybit returns newest first)
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    print(f"\n  ✅ Downloaded {len(df)} candles for {symbol}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

# Test with one symbol first
test_symbol = symbols[0]
print(f"\n{'='*80}")
print(f"TESTING WITH {test_symbol}")
print(f"{'='*80}")

test_df = download_bybit_klines(test_symbol, interval='5', days=30)

if test_df is not None:
    print(f"\n✅ SUCCESS! Bybit API works from Replit")
    print(f"Sample data:")
    print(test_df.head())
    
    print(f"\n{'='*80}")
    print(f"DOWNLOADING ALL SYMBOLS")
    print(f"{'='*80}")
    
    # Download all symbols
    all_data = {}
    
    for symbol in symbols:
        df = download_bybit_klines(symbol, interval='5', days=30)
        if df is not None:
            all_data[symbol] = df
            
            # Save to CSV
            filename = f"historical_data/{symbol}_5m_bybit.csv"
            df.to_csv(filename, index=False)
            print(f"  Saved to {filename}")
        
        # Pause between symbols
        time.sleep(0.5)
    
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)
    
    for symbol, df in all_data.items():
        days_covered = (df['timestamp'].max() - df['timestamp'].min()).days
        print(f"{symbol:<12} {len(df):>6} candles  {days_covered:>3} days  {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    print(f"\nTotal symbols: {len(all_data)}/{len(symbols)}")
    print(f"✅ All data saved to historical_data/ directory")
    
else:
    print(f"\n❌ FAILED: Bybit API blocked or symbol not found")
    print(f"Trying alternative...")
