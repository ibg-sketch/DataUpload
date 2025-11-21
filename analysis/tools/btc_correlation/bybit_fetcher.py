"""
Bybit OHLCV Data Fetcher for Correlation Analysis
Fetches synchronized 5-minute candles for all monitored symbols
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

BYBIT_API = "https://api.bybit.com"

def fetch_bybit_klines(symbol: str, interval: str = '5', days: int = 7) -> Optional[pd.DataFrame]:
    """
    Fetch historical klines from Bybit API
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval in minutes ('5' for 5min)
        days: Number of days to fetch (default 7 for correlation analysis)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume, turnover
        None if fetch fails
    """
    end_time = int(datetime.now().timestamp())
    start_time = int((datetime.now() - timedelta(days=days)).timestamp())
    
    all_klines = []
    current_end = end_time
    
    while True:
        url = f"{BYBIT_API}/v5/market/kline"
        params = {
            'category': 'linear',
            'symbol': symbol,
            'interval': interval,
            'start': start_time * 1000,
            'end': current_end * 1000,
            'limit': 200
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['retCode'] != 0:
                print(f"  ❌ Error fetching {symbol}: {data['retMsg']}")
                return None
            
            klines = data['result']['list']
            
            if not klines:
                break
            
            all_klines.extend(klines)
            
            oldest_timestamp = int(klines[-1][0]) // 1000
            
            if oldest_timestamp <= start_time:
                break
            
            current_end = oldest_timestamp - 1
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  ❌ Exception fetching {symbol}: {e}")
            return None
    
    if not all_klines:
        return None
    
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume', 'turnover']:
        df[col] = df[col].astype(float)
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    return df


def fetch_all_symbols(symbols: list, days: int = 7) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all symbols with synchronized timestamps
    
    Args:
        symbols: List of trading pairs
        days: Number of days to fetch
    
    Returns:
        Dictionary mapping symbol -> DataFrame
    """
    print(f"\n📊 Fetching {days} days of 5-minute OHLCV data from Bybit...")
    print(f"Symbols: {', '.join(symbols)}\n")
    
    data = {}
    
    for symbol in symbols:
        print(f"  Fetching {symbol}...", end=' ')
        df = fetch_bybit_klines(symbol, interval='5', days=days)
        
        if df is not None:
            data[symbol] = df
            print(f"✅ {len(df)} candles ({df['timestamp'].min()} to {df['timestamp'].max()})")
        else:
            print(f"❌ Failed")
        
        time.sleep(0.2)
    
    print(f"\n✅ Successfully fetched {len(data)}/{len(symbols)} symbols")
    
    return data


def align_timestamps(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Align all DataFrames to common timestamps for correlation analysis
    
    Args:
        data: Dictionary of symbol -> DataFrame
    
    Returns:
        Dictionary with aligned DataFrames (common timestamps only)
    """
    if not data:
        return {}
    
    print("\n🔄 Aligning timestamps across all symbols...")
    
    common_timestamps = None
    
    for symbol, df in data.items():
        timestamps = set(df['timestamp'])
        if common_timestamps is None:
            common_timestamps = timestamps
        else:
            common_timestamps = common_timestamps.intersection(timestamps)
    
    print(f"  Common timestamps: {len(common_timestamps)}")
    
    aligned_data = {}
    for symbol, df in data.items():
        aligned_df = df[df['timestamp'].isin(common_timestamps)].copy()
        aligned_df = aligned_df.sort_values('timestamp').reset_index(drop=True)
        aligned_data[symbol] = aligned_df
        print(f"  {symbol}: {len(aligned_df)} candles")
    
    return aligned_data


def save_aligned_data(data: Dict[str, pd.DataFrame], output_dir: str = 'data/btc_corr'):
    """
    Save aligned OHLCV data to CSV files
    
    Args:
        data: Dictionary of aligned DataFrames
        output_dir: Directory to save CSV files
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n💾 Saving aligned data to {output_dir}/...")
    
    for symbol, df in data.items():
        filepath = f"{output_dir}/{symbol}_aligned.csv"
        df.to_csv(filepath, index=False)
        print(f"  ✅ {symbol}: {filepath}")
    
    print(f"\n✅ Saved {len(data)} files")
