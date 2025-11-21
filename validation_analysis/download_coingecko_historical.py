"""
Download Historical Data from CoinGecko (No Geo-Blocking, Free Tier)
Fetches 30 days of OHLC data for backtesting
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta

print("="*80)
print("DOWNLOADING HISTORICAL DATA FROM COINGECKO")
print("="*80)

# CoinGecko API mappings
COINGECKO_IDS = {
    'BTCUSDT': 'bitcoin',
    'ETHUSDT': 'ethereum',
    'BNBUSDT': 'binancecoin',
    'SOLUSDT': 'solana',
    'AVAXUSDT': 'avalanche-2',
    'DOGEUSDT': 'dogecoin',
    'LINKUSDT': 'chainlink',
    'XRPUSDT': 'ripple',
    'TRXUSDT': 'tron',
    'ADAUSDT': 'cardano',
    'HYPEUSDT': 'hyperliquid'  # May not be available
}

COINGECKO_API = "https://api.coingecko.com/api/v3"

def download_coingecko_ohlc(coin_id, days=30):
    """
    Download OHLC data from CoinGecko
    Free tier allows up to 365 days
    """
    
    print(f"\nDownloading {coin_id} ({days} days)...")
    
    url = f"{COINGECKO_API}/coins/{coin_id}/ohlc"
    params = {
        'vs_currency': 'usd',
        'days': days
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"  ❌ No data returned for {coin_id}")
            return None
        
        # CoinGecko OHLC format: [timestamp_ms, open, high, low, close]
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Add volume (not provided in OHLC, need separate endpoint)
        df['volume'] = 0.0  # Placeholder
        
        print(f"  ✅ Downloaded {len(df)} candles")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"  ❌ Error downloading {coin_id}: {e}")
        return None

# Test with Bitcoin first
print(f"\n{'='*80}")
print(f"TESTING WITH BITCOIN")
print(f"{'='*80}")

test_df = download_coingecko_ohlc('bitcoin', days=30)

if test_df is not None:
    print(f"\n✅ SUCCESS! CoinGecko API works from Replit")
    print(f"\nSample data:")
    print(test_df.head())
    print(f"\nData points: {len(test_df)}")
    print(f"Interval: ~{((test_df['timestamp'].max() - test_df['timestamp'].min()).total_seconds() / 3600) / len(test_df):.1f} hours between candles")
    
    print(f"\n{'='*80}")
    print(f"DOWNLOADING ALL COINS")
    print(f"{'='*80}")
    
    all_data = {}
    
    for symbol, coin_id in COINGECKO_IDS.items():
        df = download_coingecko_ohlc(coin_id, days=30)
        
        if df is not None:
            all_data[symbol] = df
            
            # Save to CSV
            filename = f"historical_data/{symbol}_coingecko.csv"
            df.to_csv(filename, index=False)
            print(f"  Saved to {filename}")
        
        # Rate limiting (free tier)
        time.sleep(1.5)
    
    print("\n" + "="*80)
    print("DOWNLOAD SUMMARY")
    print("="*80)
    
    for symbol, df in all_data.items():
        days_covered = (df['timestamp'].max() - df['timestamp'].min()).days
        avg_interval_hours = ((df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 3600) / len(df)
        print(f"{symbol:<12} {len(df):>6} candles  {days_covered:>3} days  ~{avg_interval_hours:.1f}h interval")
    
    print(f"\nTotal coins: {len(all_data)}/{len(COINGECKO_IDS)}")
    print(f"✅ All data saved to historical_data/ directory")
    
    print(f"\n⚠️ NOTE: CoinGecko OHLC gives ~4-6 hour candles, not 5-minute")
    print(f"   This is still useful for backtesting signal logic on longer timeframes")
    
else:
    print(f"\n❌ FAILED: CoinGecko API also blocked")
