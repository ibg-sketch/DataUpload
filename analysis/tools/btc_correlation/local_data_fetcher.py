"""
Local Data Fetcher for Correlation Analysis
Uses existing analysis_log.csv data instead of external APIs
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta


def fetch_from_analysis_log(symbol: str, days: int = 7) -> Optional[pd.DataFrame]:
    """
    Extract price data for a symbol from analysis_log.csv
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        days: Number of days to include (default 7)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        (close = price from analysis_log, others are approximations)
    """
    try:
        df = pd.read_csv('analysis_log.csv')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        symbol_data = df[df['symbol'] == symbol].copy()
        
        if len(symbol_data) == 0:
            return None
        
        cutoff_time = datetime.now() - timedelta(days=days)
        symbol_data = symbol_data[symbol_data['timestamp'] >= cutoff_time]
        
        if len(symbol_data) == 0:
            return None
        
        symbol_data = symbol_data.sort_values('timestamp').reset_index(drop=True)
        
        result = pd.DataFrame({
            'timestamp': symbol_data['timestamp'],
            'open': symbol_data['price'],
            'high': symbol_data['price'],
            'low': symbol_data['price'],
            'close': symbol_data['price'],
            'volume': 0.0
        })
        
        # WARNING: analysis_log.csv contains only 'price', not full OHLCV candles
        # All O/H/L/C are set to the same 'price' value from analysis_log
        # This is acceptable for correlation analysis (uses only 'close' for log returns)
        # but NOT suitable for candle pattern analysis or volatility calculations
        # For full OHLCV data, use external API fetchers (bybit_fetcher.py, etc)
        
        return result
        
    except Exception as e:
        print(f"  ❌ Error loading {symbol}: {e}")
        return None


def fetch_all_symbols(symbols: list, days: int = 7) -> Dict[str, pd.DataFrame]:
    """
    Fetch price data for all symbols from analysis_log.csv
    
    Args:
        symbols: List of trading pairs
        days: Number of days to fetch
    
    Returns:
        Dictionary mapping symbol -> DataFrame
    """
    print(f"\n📊 Loading {days} days of price data from analysis_log.csv...")
    print(f"Symbols: {', '.join(symbols)}\n")
    
    data = {}
    
    for symbol in symbols:
        print(f"  Loading {symbol}...", end=' ')
        df = fetch_from_analysis_log(symbol, days=days)
        
        if df is not None and len(df) > 0:
            data[symbol] = df
            print(f"✅ {len(df)} data points ({df['timestamp'].min()} to {df['timestamp'].max()})")
        else:
            print(f"❌ No data")
    
    print(f"\n✅ Successfully loaded {len(data)}/{len(symbols)} symbols")
    
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
    
    if len(common_timestamps) < 50:
        print("  ⚠️ Warning: Very few common timestamps! Data may not be well-synchronized.")
        print("  Trying time-based alignment with 5-minute tolerance...")
        
        return align_timestamps_with_tolerance(data, tolerance_seconds=300)
    
    aligned_data = {}
    for symbol, df in data.items():
        aligned_df = df[df['timestamp'].isin(common_timestamps)].copy()
        aligned_df = aligned_df.sort_values('timestamp').reset_index(drop=True)
        aligned_data[symbol] = aligned_df
        print(f"  {symbol}: {len(aligned_df)} candles")
    
    return aligned_data


def align_timestamps_with_tolerance(data: Dict[str, pd.DataFrame], tolerance_seconds: int = 300) -> Dict[str, pd.DataFrame]:
    """
    Align timestamps with time tolerance using pd.merge_asof for one-to-one mapping
    Ensures all DataFrames share the EXACT same timestamps
    
    Args:
        data: Dictionary of symbol -> DataFrame
        tolerance_seconds: Time tolerance in seconds (default 5 minutes)
    
    Returns:
        Dictionary with aligned DataFrames (identical timestamps, no duplicates)
    """
    if 'BTCUSDT' not in data:
        return {}
    
    btc_df = data['BTCUSDT'].copy()
    btc_df = btc_df.sort_values('timestamp').reset_index(drop=True)
    
    tolerance = pd.Timedelta(seconds=tolerance_seconds)
    temp_aligned = {}
    
    for symbol in data.keys():
        if symbol == 'BTCUSDT':
            temp_aligned['BTCUSDT'] = btc_df
            continue
        
        symbol_df = data[symbol].copy()
        symbol_df = symbol_df.sort_values('timestamp').reset_index(drop=True)
        
        merged = pd.merge_asof(
            btc_df[['timestamp']],
            symbol_df,
            on='timestamp',
            direction='nearest',
            tolerance=tolerance
        )
        
        valid_rows = merged.dropna(subset=['close'])
        
        if len(valid_rows) > 0:
            temp_aligned[symbol] = valid_rows
            print(f"  {symbol}: {len(valid_rows)} matched candles")
        else:
            print(f"  {symbol}: ⚠️ No valid matches within tolerance")
    
    if len(temp_aligned) < 2:
        print("  ❌ Insufficient symbols after alignment")
        return {}
    
    print("\n  🔍 Computing timestamp intersection across all symbols...")
    
    common_timestamps = None
    for symbol, df in temp_aligned.items():
        symbol_timestamps = set(df['timestamp'])
        if common_timestamps is None:
            common_timestamps = symbol_timestamps
        else:
            common_timestamps = common_timestamps.intersection(symbol_timestamps)
        print(f"     {symbol}: {len(symbol_timestamps)} timestamps")
    
    if not common_timestamps:
        print("  ❌ No common timestamps found!")
        return {}
    
    common_timestamps = sorted(common_timestamps)
    print(f"\n  ✅ Common timestamps: {len(common_timestamps)}")
    
    aligned_data = {}
    for symbol, df in temp_aligned.items():
        aligned_df = df[df['timestamp'].isin(common_timestamps)].copy()
        aligned_df = aligned_df.sort_values('timestamp').reset_index(drop=True)
        aligned_data[symbol] = aligned_df
        
        assert len(aligned_df) == len(common_timestamps), f"{symbol}: length mismatch"
        assert aligned_df['timestamp'].is_monotonic_increasing, f"{symbol}: not monotonic"
        
        print(f"     {symbol}: {len(aligned_df)} candles ✓")
    
    reference_timestamps = aligned_data['BTCUSDT']['timestamp'].tolist()
    for symbol, df in aligned_data.items():
        assert df['timestamp'].tolist() == reference_timestamps, f"{symbol}: timestamp mismatch with BTC"
    
    print(f"  ✅ All symbols aligned with identical {len(reference_timestamps)} timestamps")
    
    return aligned_data


def save_aligned_data(data: Dict[str, pd.DataFrame], output_dir: str = 'data/btc_corr'):
    """
    Save aligned price data to CSV files
    
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
