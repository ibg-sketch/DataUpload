"""
Threshold Optimizer
Find optimal parameter ranges for each indicator to maximize win rate
"""

import pandas as pd
import numpy as np

def analyze_threshold_ranges():
    """Find optimal ranges for each indicator"""
    
    # Load data
    df_analysis = pd.read_csv('analysis_log.csv')
    df_analysis['timestamp'] = pd.to_datetime(df_analysis['timestamp'])
    
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_eff['timestamp_sent'] = pd.to_datetime(df_eff['timestamp_sent'])
    
    # Merge
    merged = []
    for _, sig in df_eff.iterrows():
        analysis = df_analysis[
            (df_analysis['symbol'] == sig['symbol']) &
            (df_analysis['timestamp'] <= sig['timestamp_sent']) &
            (df_analysis['timestamp'] >= sig['timestamp_sent'] - pd.Timedelta(minutes=2))
        ].tail(1)
        
        if len(analysis) > 0:
            row = analysis.iloc[0]
            merged.append({
                'result': 1 if sig['result'] == 'WIN' else 0,
                'profit_pct': sig['profit_pct'],
                'cvd': row['cvd'],
                'oi_change_pct': row['oi_change_pct'],
                'volume': row['volume'],
                'volume_median': row['volume_median'],
                'rsi': row['rsi'],
                'price_vs_vwap_pct': row['price_vs_vwap_pct'],
                'ema_short': row['ema_short'],
                'ema_long': row['ema_long'],
                'atr': row['atr'],
                'price': row['price'],
            })
    
    df = pd.DataFrame(merged)
    df['volume_ratio'] = df['volume'] / df['volume_median']
    df['cvd_millions'] = abs(df['cvd']) / 1_000_000
    df['vwap_dist_abs'] = abs(df['price_vs_vwap_pct'])
    df['ema_diff_pct'] = ((df['ema_short'] - df['ema_long']) / df['price']) * 100
    df['atr_pct'] = (df['atr'] / df['price']) * 100
    
    print("="*90)
    print("OPTIMAL THRESHOLD RANGES FOR MAXIMUM WIN RATE")
    print("="*90)
    
    # RSI Analysis
    print("\n📊 RSI RANGES:")
    print("-"*90)
    rsi_bins = [(0, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 100)]
    for low, high in rsi_bins:
        subset = df[(df['rsi'] >= low) & (df['rsi'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"  RSI {low:3}-{high:3}: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # Volume Ratio Analysis
    print("\n📊 VOLUME RATIO (vs Median):")
    print("-"*90)
    vol_bins = [(0, 0.4), (0.4, 0.7), (0.7, 1.0), (1.0, 1.5), (1.5, 3.0)]
    for low, high in vol_bins:
        subset = df[(df['volume_ratio'] >= low) & (df['volume_ratio'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"  Volume {low:.1f}x-{high:.1f}x median: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # VWAP Distance Analysis
    print("\n📊 DISTANCE FROM VWAP:")
    print("-"*90)
    vwap_bins = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 1.0), (1.0, 5.0)]
    for low, high in vwap_bins:
        subset = df[(df['vwap_dist_abs'] >= low) & (df['vwap_dist_abs'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"  Distance {low:.1f}%-{high:.1f}%: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # EMA Difference Analysis
    print("\n📊 EMA CROSSOVER (Short - Long):")
    print("-"*90)
    ema_bins = [(-1.0, -0.3), (-0.3, -0.1), (-0.1, 0), (0, 0.1), (0.1, 0.3), (0.3, 1.0)]
    for low, high in ema_bins:
        subset = df[(df['ema_diff_pct'] >= low) & (df['ema_diff_pct'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            direction = "↘️ Bearish" if high <= 0 else "↗️ Bullish"
            print(f"  EMA {low:+.1f}% to {high:+.1f}% {direction}: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # OI Change Analysis
    print("\n📊 OPEN INTEREST CHANGE:")
    print("-"*90)
    oi_bins = [(-5, -1), (-1, -0.3), (-0.3, 0), (0, 0.3), (0.3, 1.0), (1.0, 5.0)]
    for low, high in oi_bins:
        subset = df[(df['oi_change_pct'] >= low) & (df['oi_change_pct'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"  OI Change {low:+.1f}% to {high:+.1f}%: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # CVD Analysis
    print("\n📊 CVD MAGNITUDE (Absolute):")
    print("-"*90)
    cvd_bins = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 100)]
    for low, high in cvd_bins:
        subset = df[(df['cvd_millions'] >= low) & (df['cvd_millions'] < high)]
        if len(subset) > 5:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"  CVD {low:2.0f}M-{high:3.0f}M: {wr:5.1f}% WR | {len(subset):3} signals | Avg P&L: {avg_profit:+.2f}%")
    
    # Combined optimal ranges
    print("\n" + "="*90)
    print("🎯 OPTIMAL PARAMETER RANGES (Highest Win Rates)")
    print("="*90)
    
    # Find best performing subset
    optimal = df[
        (df['rsi'] < 45) &  # Low RSI
        (df['volume_ratio'] < 0.8) &  # Low-moderate volume
        (df['vwap_dist_abs'] < 0.3)  # Close to VWAP
    ]
    
    if len(optimal) > 0:
        print(f"\nCondition: RSI < 45 AND Volume < 0.8x median AND |VWAP distance| < 0.3%")
        print(f"Results: {optimal['result'].mean()*100:.1f}% WR | {len(optimal)} signals | Avg P&L: {optimal['profit_pct'].mean():+.2f}%")
    
    # Test multiple combinations
    print("\n📈 BEST MULTI-CONDITION FILTERS:")
    print("-"*90)
    
    tests = [
        ("RSI < 40 + Vol < 0.7x + VWAP < 0.2%", 
         (df['rsi'] < 40) & (df['volume_ratio'] < 0.7) & (df['vwap_dist_abs'] < 0.2)),
        ("RSI < 45 + Vol < 0.8x + VWAP < 0.3%", 
         (df['rsi'] < 45) & (df['volume_ratio'] < 0.8) & (df['vwap_dist_abs'] < 0.3)),
        ("RSI 30-50 + Vol 0.5-1.0x + VWAP < 0.25%", 
         (df['rsi'] >= 30) & (df['rsi'] < 50) & (df['volume_ratio'] >= 0.5) & (df['volume_ratio'] < 1.0) & (df['vwap_dist_abs'] < 0.25)),
        ("VWAP < 0.1% + Vol < 0.8x", 
         (df['vwap_dist_abs'] < 0.1) & (df['volume_ratio'] < 0.8)),
    ]
    
    for name, condition in tests:
        subset = df[condition]
        if len(subset) > 3:
            wr = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            print(f"{name:45} | {wr:5.1f}% WR | {len(subset):3} signals | {avg_profit:+.2f}%")

if __name__ == "__main__":
    analyze_threshold_ranges()
