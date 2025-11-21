"""
Local 5-Minute Data Fetcher
Fetches 5-minute price data from analysis_log_clean.csv
Avoids API rate limits by using locally collected data
"""

import pandas as pd
from typing import Dict, List


def fetch_5m_candles_from_log(symbol: str, log_path: str = 'analysis_log_clean.csv') -> pd.DataFrame:
    """
    Fetch 5-minute candles from local analysis log
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        log_path: Path to analysis log CSV
    
    Returns:
        DataFrame with columns: timestamp, close (price)
    """
    print(f"  Loading {symbol} from local log...", end=" ")
    
    try:
        df = pd.read_csv(log_path, on_bad_lines='skip', engine='python')
        
        if 'symbol' not in df.columns or 'timestamp' not in df.columns or 'price' not in df.columns:
            print(f"❌ Missing columns")
            return None
        
        df = df[df['timestamp'] != 'timestamp']
        df = df[df['symbol'] != 'symbol']
        
        symbol_df = df[df['symbol'] == symbol].copy()
        
        if len(symbol_df) == 0:
            print(f"❌ No data")
            return None
        
        symbol_df['timestamp'] = pd.to_datetime(symbol_df['timestamp'])
        symbol_df = symbol_df.rename(columns={'price': 'close'})
        symbol_df = symbol_df[['timestamp', 'close']].dropna()
        symbol_df = symbol_df.sort_values('timestamp').reset_index(drop=True)
        
        symbol_df['open'] = symbol_df['close']
        symbol_df['high'] = symbol_df['close']
        symbol_df['low'] = symbol_df['close']
        symbol_df['volume'] = 0.0
        
        print(f"✅ {len(symbol_df)} candles ({symbol_df['timestamp'].min()} to {symbol_df['timestamp'].max()})")
        
        return symbol_df
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def fetch_all_coins_from_log(symbols: List[str], log_path: str = 'analysis_log_clean.csv') -> Dict[str, pd.DataFrame]:
    """
    Fetch 5-minute candles for all symbols from local log
    
    Args:
        symbols: List of trading pairs
        log_path: Path to analysis log CSV
    
    Returns:
        Dictionary of DataFrames keyed by symbol
    """
    print(f"\n📥 Loading 5-minute price data from local log ({log_path})...\n")
    
    data = {}
    
    for symbol in symbols:
        df = fetch_5m_candles_from_log(symbol, log_path)
        if df is not None and len(df) > 0:
            data[symbol] = df
    
    print(f"\n✅ Successfully loaded {len(data)}/{len(symbols)} symbols")
    
    return data
