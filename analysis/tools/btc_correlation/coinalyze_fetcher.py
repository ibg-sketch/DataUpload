"""
Coinalyze OHLCV Data Fetcher for Correlation Analysis
Fetches synchronized 5-minute candles for all monitored symbols
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

COINALYZE_API_BASE = "https://api.coinalyze.net/v1"

def fetch_coinalyze_ohlcv(symbol: str, interval: str = '5m', days: int = 7) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV from Coinalyze API
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Candle interval ('5m' for 5 minutes)
        days: Number of days to fetch (max ~7 for 5m due to retention limits)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        None if fetch fails
    """
    api_key = os.getenv('COINALYZE_API_KEY')
    if not api_key:
        print(f"  ❌ COINALYZE_API_KEY not set")
        return None
    
    coinalyze_symbol = f"{symbol}_PERP.A"
    
    url = f"{COINALYZE_API_BASE}/ohlcv-history"
    params = {
        'symbols': coinalyze_symbol,
        'interval': interval,
        'api_key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            print(f"  ❌ No data returned for {symbol}")
            return None
        
        history = data[0].get('history', [])
        
        if not history:
            print(f"  ❌ Empty history for {symbol}")
            return None
        
        df = pd.DataFrame(history)
        
        df = df.rename(columns={
            't': 'timestamp',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        cutoff_time = datetime.now() - timedelta(days=days)
        df = df[df['timestamp'] >= cutoff_time].reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"  ❌ Exception fetching {symbol}: {e}")
        return None


def fetch_all_symbols(symbols: list, days: int = 7) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all symbols with synchronized timestamps
    
    Args:
        symbols: List of trading pairs
        days: Number of days to fetch
    
    Returns:
        Dictionary mapping symbol -> DataFrame
    """
    print(f"\n📊 Fetching {days} days of 5-minute OHLCV data from Coinalyze...")
    print(f"Symbols: {', '.join(symbols)}\n")
    
    data = {}
    
    for symbol in symbols:
        print(f"  Fetching {symbol}...", end=' ')
        df = fetch_coinalyze_ohlcv(symbol, interval='5m', days=days)
        
        if df is not None:
            data[symbol] = df
            print(f"✅ {len(df)} candles ({df['timestamp'].min()} to {df['timestamp'].max()})")
        else:
            print(f"❌ Failed")
        
        time.sleep(1.6)
    
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
