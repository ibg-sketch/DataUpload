#!/usr/bin/env python3
"""
BTC Correlation Analysis
Analyzes correlation between BTC price movements and other cryptocurrencies
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

def load_data(start_time_str):
    """Load analysis log data from specified start time"""
    # Read CSV with explicit engine and error handling
    df = pd.read_csv('analysis_log.csv', engine='python', on_bad_lines='warn')
    
    # Convert timestamp with error handling
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # Remove rows with invalid timestamps
    df = df.dropna(subset=['timestamp'])
    
    print(f"DEBUG: Loaded {len(df)} rows total")
    if len(df) > 0:
        print(f"DEBUG: First timestamp: {df['timestamp'].min()}")
        print(f"DEBUG: Last timestamp: {df['timestamp'].max()}")
        print(f"DEBUG: Sample columns: {list(df.columns[:5])}")
    
    # Filter data from start_time onwards (without timezone)
    start_time = pd.to_datetime(start_time_str).tz_localize(None)
    df = df[df['timestamp'] >= start_time].copy()
    
    return df

def calculate_price_changes(df, symbol):
    """Calculate percentage price changes for a symbol"""
    symbol_data = df[df['symbol'] == symbol].copy()
    symbol_data = symbol_data.sort_values('timestamp')
    
    if len(symbol_data) < 2:
        return None
    
    # Calculate percentage change from first price
    first_price = symbol_data.iloc[0]['price']
    symbol_data['pct_change'] = ((symbol_data['price'] - first_price) / first_price) * 100
    
    return symbol_data[['timestamp', 'price', 'pct_change']]

def calculate_correlation(btc_data, alt_data, symbol):
    """Calculate correlation between BTC and altcoin movements"""
    # Merge on timestamp (using closest match within 1 minute)
    merged = pd.merge_asof(
        btc_data.sort_values('timestamp'),
        alt_data.sort_values('timestamp'),
        on='timestamp',
        suffixes=('_btc', '_alt'),
        direction='nearest',
        tolerance=pd.Timedelta('1min')
    )
    
    if len(merged) < 10:
        return None
    
    # Calculate correlation
    correlation = merged['pct_change_btc'].corr(merged['pct_change_alt'])
    
    # Calculate beta (how much alt moves relative to BTC)
    # Beta = Cov(Alt, BTC) / Var(BTC)
    covariance = merged['pct_change_btc'].cov(merged['pct_change_alt'])
    btc_variance = merged['pct_change_btc'].var()
    beta = covariance / btc_variance if btc_variance > 0 else 0
    
    # Calculate lag (time delay)
    # Find which lag gives highest correlation
    best_lag = 0
    best_corr = correlation
    
    for lag in range(-6, 7):  # Test lags from -30min to +30min (5min intervals)
        if lag == 0:
            continue
            
        alt_shifted = alt_data.copy()
        alt_shifted['timestamp'] = alt_shifted['timestamp'] + pd.Timedelta(minutes=lag*5)
        
        merged_lag = pd.merge_asof(
            btc_data.sort_values('timestamp'),
            alt_shifted.sort_values('timestamp'),
            on='timestamp',
            suffixes=('_btc', '_alt'),
            direction='nearest',
            tolerance=pd.Timedelta('1min')
        )
        
        if len(merged_lag) >= 10:
            corr_lag = merged_lag['pct_change_btc'].corr(merged_lag['pct_change_alt'])
            if abs(corr_lag) > abs(best_corr):
                best_corr = corr_lag
                best_lag = lag
    
    # Get current prices and changes
    btc_first = btc_data.iloc[0]['price']
    btc_last = btc_data.iloc[-1]['price']
    btc_change = ((btc_last - btc_first) / btc_first) * 100
    
    alt_first = alt_data.iloc[0]['price']
    alt_last = alt_data.iloc[-1]['price']
    alt_change = ((alt_last - alt_first) / alt_first) * 100
    
    return {
        'symbol': symbol,
        'correlation': correlation,
        'beta': beta,
        'best_correlation': best_corr,
        'lag_minutes': best_lag * 5,
        'btc_change_pct': btc_change,
        'alt_change_pct': alt_change,
        'price_ratio': alt_change / btc_change if btc_change != 0 else 0,
        'data_points': len(merged)
    }

def main():
    # Use UTC timezone since data is in UTC
    now = datetime.now(pytz.UTC)
    
    # Start from 2025-11-04 00:00 UTC
    start_time = datetime(2025, 11, 4, 0, 0, 0, tzinfo=pytz.UTC)
    
    print(f"Analysis Period: {start_time.strftime('%Y-%m-%d %H:%M UTC')} to {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Duration: {(now - start_time).total_seconds() / 3600:.1f} hours\n")
    
    # Load data
    df = load_data(start_time.strftime('%Y-%m-%d %H:%M:%S'))
    
    print(f"Total data points loaded: {len(df)}")
    print(f"Symbols in data: {df['symbol'].unique()}\n")
    
    # All symbols from config
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 
               'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT']
    
    # Calculate BTC price changes
    btc_data = calculate_price_changes(df, 'BTCUSDT')
    
    if btc_data is None or len(btc_data) < 2:
        print("ERROR: Insufficient BTC data for analysis")
        return
    
    print(f"BTC data points: {len(btc_data)}")
    print(f"BTC price: {btc_data.iloc[0]['price']:.2f} → {btc_data.iloc[-1]['price']:.2f}")
    print(f"BTC change: {btc_data.iloc[-1]['pct_change']:.2f}%\n")
    print("="*80)
    
    # Analyze correlations
    results = []
    for symbol in symbols:
        if symbol == 'BTCUSDT':
            continue
        
        alt_data = calculate_price_changes(df, symbol)
        if alt_data is None or len(alt_data) < 2:
            print(f"⚠️  {symbol}: Insufficient data")
            continue
        
        result = calculate_correlation(btc_data, alt_data, symbol)
        if result:
            results.append(result)
    
    # Sort by correlation strength
    results.sort(key=lambda x: abs(x['correlation']), reverse=True)
    
    # Print results
    print("\n📊 CORRELATION ANALYSIS WITH BTC:\n")
    print(f"{'Symbol':<12} {'Corr':<8} {'Beta':<8} {'BTC Δ%':<10} {'Alt Δ%':<10} {'Ratio':<8} {'Lag':<10} {'Points'}")
    print("-" * 90)
    
    for r in results:
        corr_icon = "🟢" if r['correlation'] > 0.7 else "🟡" if r['correlation'] > 0.4 else "🔴"
        lag_str = f"{r['lag_minutes']:+d}min" if r['lag_minutes'] != 0 else "0min"
        
        print(f"{corr_icon} {r['symbol']:<10} {r['correlation']:>6.2f}  "
              f"{r['beta']:>6.2f}  "
              f"{r['btc_change_pct']:>8.2f}%  "
              f"{r['alt_change_pct']:>8.2f}%  "
              f"{r['price_ratio']:>6.2f}  "
              f"{lag_str:>8}  "
              f"{r['data_points']}")
    
    # Summary statistics
    print("\n" + "="*80)
    print("\n📈 SUMMARY:\n")
    
    avg_corr = np.mean([r['correlation'] for r in results])
    avg_beta = np.mean([r['beta'] for r in results])
    
    print(f"Average Correlation: {avg_corr:.3f}")
    print(f"Average Beta: {avg_beta:.3f}")
    print(f"\nInterpretation:")
    print(f"  • Beta > 1.0: Altcoin moves MORE than BTC (higher volatility)")
    print(f"  • Beta = 1.0: Altcoin moves SAME as BTC")
    print(f"  • Beta < 1.0: Altcoin moves LESS than BTC (lower volatility)")
    print(f"  • Lag > 0: Altcoin follows BTC with delay")
    print(f"  • Lag < 0: Altcoin leads BTC")
    
    # Identify leaders and followers
    leaders = [r for r in results if r['lag_minutes'] < 0]
    followers = [r for r in results if r['lag_minutes'] > 0]
    
    if leaders:
        print(f"\n🏃 LEADING BTC (move before BTC):")
        for r in sorted(leaders, key=lambda x: x['lag_minutes']):
            print(f"  • {r['symbol']}: {r['lag_minutes']} minutes ahead")
    
    if followers:
        print(f"\n🐌 FOLLOWING BTC (move after BTC):")
        for r in sorted(followers, key=lambda x: x['lag_minutes'], reverse=True):
            print(f"  • {r['symbol']}: {r['lag_minutes']} minutes behind")
    
    # High beta coins
    high_beta = [r for r in results if r['beta'] > 1.2]
    if high_beta:
        print(f"\n⚡ HIGH VOLATILITY (Beta > 1.2):")
        for r in sorted(high_beta, key=lambda x: x['beta'], reverse=True):
            print(f"  • {r['symbol']}: {r['beta']:.2f}x (moves {r['beta']*100:.0f}% when BTC moves 100%)")

if __name__ == '__main__':
    main()
