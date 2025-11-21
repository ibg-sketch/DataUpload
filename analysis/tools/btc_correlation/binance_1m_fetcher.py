"""
Coinalyze 1-Minute Data Fetcher
Fetches 1-minute candles from Coinalyze API for lag analysis
Note: Coinalyze retains ~1500-2000 1-minute candles (25-33 hours)
"""

import requests
import pandas as pd
import time
import os
from typing import Dict, List
from datetime import datetime, timedelta


COINALYZE_API = "https://api.coinalyze.net/v1"
COINALYZE_KEY = os.getenv('COINALYZE_API_KEY')


def fetch_1m_candles(symbol: str, hours: int = 24) -> pd.DataFrame:
    """
    Fetch 1-minute candles from Coinalyze API
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        hours: Number of hours to fetch (default 24, max ~30 due to API limits)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    hours = min(hours, 30)
    
    end_ts = int(datetime.now().timestamp())
    start_ts = int((datetime.now() - timedelta(hours=hours)).timestamp())
    
    coinalyze_symbol = f"{symbol}_PERP.A"
    
    print(f"  Fetching {symbol} (1m candles, {hours}h)...", end=" ")
    
    url = f"{COINALYZE_API}/ohlcv-history"
    params = {
        'symbols': coinalyze_symbol,
        'interval': '1min',
        'from': start_ts,
        'to': end_ts
    }
    
    if COINALYZE_KEY:
        params['api_key'] = COINALYZE_KEY
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            print("❌ No data")
            return None
        
        history = data[0].get('history', [])
        
        if not history:
            print("❌ Empty history")
            return None
        
        df = pd.DataFrame(history)
        
        df['timestamp'] = pd.to_datetime(df['t'], unit='s')
        df = df.rename(columns={
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume'
        })
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"✅ {len(df)} candles ({df['timestamp'].min()} to {df['timestamp'].max()})")
        
        return df
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def fetch_all_coins(symbols: List[str], hours: int = 24) -> Dict[str, pd.DataFrame]:
    """
    Fetch 1-minute candles for all symbols
    
    Args:
        symbols: List of trading pairs
        hours: Number of hours to fetch (default 24, max ~30)
    
    Returns:
        Dictionary of DataFrames keyed by symbol
    """
    print(f"\n📥 Fetching 1-minute candles for {len(symbols)} symbols ({hours} hours via Coinalyze)...\n")
    
    data = {}
    
    for symbol in symbols:
        df = fetch_1m_candles(symbol, hours)
        if df is not None and len(df) > 0:
            data[symbol] = df
        time.sleep(1.6)
    
    print(f"\n✅ Successfully fetched {len(data)}/{len(symbols)} symbols")
    
    return data
