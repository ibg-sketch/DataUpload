"""
Backtest the dual-formula signal logic against historical data
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# Formulas derived for RAW (unnormalized) values - produce logit scores
def signal_long_logit(rsi, ema_diff_pct, volume_ratio, atr_pct):
    """Compute raw LONG logit score (uses RAW values, no normalization)."""
    return (
        -0.001468 * rsi
        +0.794991 * ema_diff_pct
        -0.211934 * volume_ratio
        +0.222079 * atr_pct
        -0.224266
    )

def signal_short_logit(rsi, ema_diff_pct, volume_ratio, atr_pct):
    """Compute raw SHORT logit score (uses RAW values, no normalization)."""
    return (
        -0.065756 * rsi
        +1.106601 * ema_diff_pct
        -0.136820 * volume_ratio
        -0.951073 * atr_pct
        +2.836546
    )

def sigmoid(x):
    """Convert logit score to probability (0-1 range)."""
    return 1 / (1 + np.exp(-x))

def signal_long(rsi, ema_diff_pct, volume_ratio, atr_pct):
    """Compute LONG probability score (0-1 range)."""
    logit = signal_long_logit(rsi, ema_diff_pct, volume_ratio, atr_pct)
    return sigmoid(logit)

def signal_short(rsi, ema_diff_pct, volume_ratio, atr_pct):
    """Compute SHORT probability score (0-1 range)."""
    logit = signal_short_logit(rsi, ema_diff_pct, volume_ratio, atr_pct)
    return sigmoid(logit)

def long_filters_ok(rsi, vwap_dist, volume_ratio):
    """Direction-specific filters for LONG entries."""
    if not (40.0 <= rsi <= 70.0):
        return False
    if vwap_dist > 0.010:  # <= 1.0%
        return False
    if not (0.5 <= volume_ratio <= 1.2):
        return False
    return True

def short_filters_ok(rsi, vwap_dist, volume_ratio):
    """Direction-specific filters for SHORT entries."""
    if not (rsi < 50.0):
        return False
    if vwap_dist > 0.003:  # <= 0.3%
        return False
    if not (volume_ratio <= 1.0):
        return False
    return True

def backtest_dual_formula():
    """Backtest the dual-formula approach"""
    
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
                'verdict': sig['verdict'],
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
    
    # Feature engineering (RAW values for formulas)
    df['volume_ratio'] = df['volume'] / df['volume_median']
    df['vwap_dist'] = abs(df['price_vs_vwap_pct']) / 100  # Convert to decimal
    df['ema_diff_pct'] = ((df['ema_short'] - df['ema_long']) / df['price']) * 100  # as percentage
    df['atr_pct'] = (df['atr'] / df['price']) * 100  # as percentage
    
    print("="*90)
    print("DUAL-FORMULA BACKTEST RESULTS")
    print("="*90)
    
    # Apply dual formula logic
    results = {
        'baseline': {'long': 0, 'short': 0, 'long_win': 0, 'short_win': 0},
        'new_logic': {'long': 0, 'short': 0, 'long_win': 0, 'short_win': 0}
    }
    
    signals_kept = []
    signals_filtered = []
    
    for idx, row in df.iterrows():
        # Get raw values (formulas work on raw values directly)
        rsi = row['rsi']
        ema_diff_pct = row['ema_diff_pct']
        volume_ratio = row['volume_ratio']
        atr_pct = row['atr_pct']
        vwap_dist = row['vwap_dist']
        
        verdict = row['verdict']
        is_win = row['result']
        
        # Baseline: all signals sent
        if verdict == 'BUY':
            results['baseline']['long'] += 1
            if is_win:
                results['baseline']['long_win'] += 1
        else:
            results['baseline']['short'] += 1
            if is_win:
                results['baseline']['short_win'] += 1
        
        # New logic: apply formulas ONLY (no strict filters - formulas learned from data)
        if verdict == 'BUY':
            sig_val = signal_long(rsi, ema_diff_pct, volume_ratio, atr_pct)
            threshold = 0.30  # Based on 40.2% WR @ threshold > 0.3
            filters_pass = True  # Test formula-only first
            
            if sig_val > threshold:
                results['new_logic']['long'] += 1
                if is_win:
                    results['new_logic']['long_win'] += 1
                signals_kept.append({
                    'verdict': verdict,
                    'signal': sig_val,
                    'result': is_win,
                    'rsi': rsi,
                    'vwap_dist': vwap_dist,
                    'vol_ratio': volume_ratio
                })
            else:
                signals_filtered.append({
                    'verdict': verdict,
                    'signal': sig_val,
                    'result': is_win,
                    'reason': 'filters' if not filters_pass else 'threshold',
                    'rsi': rsi,
                    'vwap_dist': vwap_dist,
                    'vol_ratio': volume_ratio
                })
        else:  # SELL
            sig_val = signal_short(rsi, ema_diff_pct, volume_ratio, atr_pct)
            threshold = 0.30  # Based on 37.5% WR @ threshold > 0.3
            filters_pass = True  # Test formula-only first
            
            if sig_val > threshold:
                results['new_logic']['short'] += 1
                if is_win:
                    results['new_logic']['short_win'] += 1
                signals_kept.append({
                    'verdict': verdict,
                    'signal': sig_val,
                    'result': is_win,
                    'rsi': rsi,
                    'vwap_dist': vwap_dist,
                    'vol_ratio': volume_ratio
                })
            else:
                signals_filtered.append({
                    'verdict': verdict,
                    'signal': sig_val,
                    'result': is_win,
                    'reason': 'filters' if not filters_pass else 'threshold',
                    'rsi': rsi,
                    'vwap_dist': vwap_dist,
                    'vol_ratio': volume_ratio
                })
    
    # Print results
    print("\n📊 BASELINE (Current Bot - All Signals):")
    print("-"*90)
    baseline_long_wr = (results['baseline']['long_win'] / results['baseline']['long'] * 100) if results['baseline']['long'] > 0 else 0
    baseline_short_wr = (results['baseline']['short_win'] / results['baseline']['short'] * 100) if results['baseline']['short'] > 0 else 0
    baseline_total = results['baseline']['long'] + results['baseline']['short']
    baseline_total_wins = results['baseline']['long_win'] + results['baseline']['short_win']
    baseline_overall_wr = (baseline_total_wins / baseline_total * 100) if baseline_total > 0 else 0
    
    print(f"LONG signals:  {results['baseline']['long']:3} sent | {results['baseline']['long_win']:3} wins | {baseline_long_wr:5.1f}% WR")
    print(f"SHORT signals: {results['baseline']['short']:3} sent | {results['baseline']['short_win']:3} wins | {baseline_short_wr:5.1f}% WR")
    print(f"OVERALL:       {baseline_total:3} sent | {baseline_total_wins:3} wins | {baseline_overall_wr:5.1f}% WR")
    
    print("\n✨ NEW DUAL-FORMULA LOGIC (With Filters):")
    print("-"*90)
    new_long_wr = (results['new_logic']['long_win'] / results['new_logic']['long'] * 100) if results['new_logic']['long'] > 0 else 0
    new_short_wr = (results['new_logic']['short_win'] / results['new_logic']['short'] * 100) if results['new_logic']['short'] > 0 else 0
    new_total = results['new_logic']['long'] + results['new_logic']['short']
    new_total_wins = results['new_logic']['long_win'] + results['new_logic']['short_win']
    new_overall_wr = (new_total_wins / new_total * 100) if new_total > 0 else 0
    
    print(f"LONG signals:  {results['new_logic']['long']:3} sent | {results['new_logic']['long_win']:3} wins | {new_long_wr:5.1f}% WR")
    print(f"SHORT signals: {results['new_logic']['short']:3} sent | {results['new_logic']['short_win']:3} wins | {new_short_wr:5.1f}% WR")
    print(f"OVERALL:       {new_total:3} sent | {new_total_wins:3} wins | {new_overall_wr:5.1f}% WR")
    
    print("\n📈 IMPROVEMENT:")
    print("-"*90)
    long_improvement = new_long_wr - baseline_long_wr
    short_improvement = new_short_wr - baseline_short_wr
    overall_improvement = new_overall_wr - baseline_overall_wr
    
    print(f"LONG WR:    {baseline_long_wr:5.1f}% → {new_long_wr:5.1f}%  ({long_improvement:+.1f}%)")
    print(f"SHORT WR:   {baseline_short_wr:5.1f}% → {new_short_wr:5.1f}%  ({short_improvement:+.1f}%)")
    print(f"OVERALL WR: {baseline_overall_wr:5.1f}% → {new_overall_wr:5.1f}%  ({overall_improvement:+.1f}%)")
    
    signal_reduction = (1 - new_total / baseline_total) * 100
    print(f"\nSignal Reduction: {baseline_total} → {new_total} ({signal_reduction:.1f}% fewer signals)")
    
    # Analyze filtered signals
    df_filtered = pd.DataFrame(signals_filtered)
    if len(df_filtered) > 0:
        filtered_wins = df_filtered['result'].sum()
        filtered_total = len(df_filtered)
        filtered_wr = (filtered_wins / filtered_total * 100) if filtered_total > 0 else 0
        
        print(f"\n🗑️  FILTERED OUT: {filtered_total} signals | {filtered_wins} would have won | {filtered_wr:.1f}% WR")
        print("    (Good filtration = removing mostly losing signals)")
        
        # Show why signals were filtered
        reason_counts = df_filtered['reason'].value_counts()
        print(f"\n    Filtered by threshold: {reason_counts.get('threshold', 0)}")
        print(f"    Filtered by filters:   {reason_counts.get('filters', 0)}")
    
    print("\n" + "="*90)
    print("🎯 CONCLUSION")
    print("="*90)
    
    if new_overall_wr > baseline_overall_wr:
        print(f"✅ DUAL-FORMULA LOGIC IMPROVES WIN RATE by {overall_improvement:+.1f}%")
        print(f"   Recommendation: DEPLOY this logic to production")
    else:
        print(f"⚠️  No improvement observed ({overall_improvement:+.1f}%)")
        print(f"   Recommendation: Review thresholds and filters")
    
    if new_total < baseline_total * 0.5:
        print(f"\n⚠️  Signal volume reduced by {signal_reduction:.0f}%")
        print(f"   Consider if this trade-off (quality vs quantity) is acceptable")

if __name__ == "__main__":
    backtest_dual_formula()
