#!/usr/bin/env python3
"""
Win/Loss Pattern Analysis
Compare successful vs unsuccessful signals to identify predictive patterns
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

def merge_datasets():
    """Merge effectiveness_log with analysis_log to get raw indicator values"""
    print("=" * 80)
    print("STEP 1: MERGING DATASETS")
    print("=" * 80)
    
    eff = pd.read_csv('effectiveness_log.csv')
    analysis = pd.read_csv('analysis_log.csv')
    
    eff['timestamp_sent'] = pd.to_datetime(eff['timestamp_sent'])
    analysis['timestamp'] = pd.to_datetime(analysis['timestamp'])
    
    print(f"Effectiveness log: {len(eff)} signals")
    print(f"Analysis log: {len(analysis)} records")
    
    merged_records = []
    unmatched = 0
    
    for _, sig in eff.iterrows():
        time_window_start = sig['timestamp_sent'] - timedelta(minutes=2)
        time_window_end = sig['timestamp_sent'] + timedelta(minutes=2)
        
        matches = analysis[
            (analysis['symbol'] == sig['symbol']) &
            (analysis['verdict'] == sig['verdict']) &
            (analysis['timestamp'] >= time_window_start) &
            (analysis['timestamp'] <= time_window_end)
        ]
        
        if len(matches) > 0:
            match = matches.iloc[0]
            merged = {
                'timestamp': sig['timestamp_sent'],
                'symbol': sig['symbol'],
                'verdict': sig['verdict'],
                'result': sig['result'],
                'confidence': sig['confidence'],
                'profit_pct': sig['profit_pct'],
                'entry_price': sig['entry_price'],
                'target_min': sig['target_min'],
                'target_max': sig['target_max'],
                'duration_minutes': sig['duration_minutes'],
                'market_strength': sig['market_strength'],
                'cvd': match['cvd'],
                'oi': match['oi'],
                'oi_change': match['oi_change'],
                'oi_change_pct': match['oi_change_pct'],
                'price_vs_vwap_pct': match['price_vs_vwap_pct'],
                'volume': match['volume'],
                'volume_median': match['volume_median'],
                'volume_spike': match['volume_spike'],
                'liq_ratio': match['liq_ratio'],
                'rsi': match['rsi'],
                'ema_short': match['ema_short'],
                'ema_long': match['ema_long'],
                'atr': match['atr'],
                'score': match['score'],
                'min_score': match['min_score'],
                'max_score': match['max_score']
            }
            merged_records.append(merged)
        else:
            unmatched += 1
    
    merged_df = pd.DataFrame(merged_records)
    print(f"\n✅ Matched: {len(merged_df)} signals")
    print(f"❌ Unmatched: {unmatched} signals")
    
    merged_df.to_csv('win_loss_merged_data.csv', index=False)
    print(f"\n💾 Saved to: win_loss_merged_data.csv")
    
    return merged_df

def cohens_d(group1, group2):
    """Calculate Cohen's d effect size"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    return (np.mean(group1) - np.mean(group2)) / pooled_std if pooled_std > 0 else 0

def global_analysis(df):
    """Global WIN vs LOSS comparison across all signals"""
    print("\n" + "=" * 80)
    print("STEP 2: GLOBAL WIN vs LOSS ANALYSIS")
    print("=" * 80)
    
    wins = df[df['result'] == 'WIN']
    losses = df[df['result'] == 'LOSS']
    
    print(f"\nTotal: {len(df)} signals")
    print(f"  WIN:  {len(wins)} ({len(wins)/len(df)*100:.1f}%)")
    print(f"  LOSS: {len(losses)} ({len(losses)/len(df)*100:.1f}%)")
    
    indicators = [
        ('confidence', 'Confidence'),
        ('cvd', 'CVD'),
        ('oi_change_pct', 'OI Change %'),
        ('price_vs_vwap_pct', 'Price vs VWAP %'),
        ('volume_spike', 'Volume Spike'),
        ('liq_ratio', 'Liquidation Ratio'),
        ('rsi', 'RSI'),
        ('market_strength', 'Market Strength'),
        ('score', 'Signal Score'),
        ('duration_minutes', 'Duration (min)')
    ]
    
    print("\n" + "-" * 80)
    print(f"{'INDICATOR':<25} {'WIN Mean':<12} {'LOSS Mean':<12} {'Diff':<10} {'Cohen d':<10} {'P-value'}")
    print("-" * 80)
    
    results = []
    
    for col, name in indicators:
        if col not in df.columns:
            continue
            
        win_vals = wins[col].dropna()
        loss_vals = losses[col].dropna()
        
        if len(win_vals) == 0 or len(loss_vals) == 0:
            continue
        
        win_mean = win_vals.mean()
        loss_mean = loss_vals.mean()
        diff = win_mean - loss_mean
        effect_size = cohens_d(win_vals, loss_vals)
        
        t_stat, p_val = stats.ttest_ind(win_vals, loss_vals)
        
        sig_marker = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
        
        print(f"{name:<25} {win_mean:>11.3f} {loss_mean:>11.3f} {diff:>9.3f} {effect_size:>9.2f} {p_val:>8.4f} {sig_marker}")
        
        results.append({
            'indicator': name,
            'win_mean': win_mean,
            'loss_mean': loss_mean,
            'difference': diff,
            'cohens_d': effect_size,
            'p_value': p_val
        })
    
    print("-" * 80)
    print("*** p<0.001, ** p<0.01, * p<0.05")
    
    return pd.DataFrame(results)

def per_symbol_analysis(df):
    """Analyze patterns per symbol"""
    print("\n" + "=" * 80)
    print("STEP 3: PER-SYMBOL ANALYSIS")
    print("=" * 80)
    
    symbols = sorted(df['symbol'].unique())
    
    for symbol in symbols:
        sym_df = df[df['symbol'] == symbol]
        wins = sym_df[sym_df['result'] == 'WIN']
        losses = sym_df[sym_df['result'] == 'LOSS']
        
        if len(sym_df) < 3:
            continue
        
        wr = len(wins) / len(sym_df) * 100
        avg_profit = sym_df['profit_pct'].mean()
        
        status = "🟢" if wr >= 50 else "🔴"
        
        print(f"\n{status} {symbol} ({len(sym_df)} signals)")
        print(f"   Win Rate: {wr:.1f}% ({len(wins)}W-{len(losses)}L)")
        print(f"   Avg Profit: {avg_profit:+.2f}%")
        
        if len(wins) >= 2 and len(losses) >= 2:
            key_indicators = ['confidence', 'cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'volume_spike']
            
            print(f"\n   {'Indicator':<20} {'WIN':<12} {'LOSS':<12} {'Diff':<10}")
            print(f"   {'-'*54}")
            
            for ind in key_indicators:
                if ind not in sym_df.columns:
                    continue
                    
                win_vals = wins[ind].dropna()
                loss_vals = losses[ind].dropna()
                
                if len(win_vals) == 0 or len(loss_vals) == 0:
                    continue
                
                win_mean = win_vals.mean()
                loss_mean = loss_vals.mean()
                diff = win_mean - loss_mean
                
                print(f"   {ind:<20} {win_mean:>11.3f} {loss_mean:>11.3f} {diff:>9.3f}")

def verdict_analysis(df):
    """Analyze BUY vs SELL patterns separately"""
    print("\n" + "=" * 80)
    print("STEP 4: BUY vs SELL DIRECTION ANALYSIS")
    print("=" * 80)
    
    for verdict in ['BUY', 'SELL']:
        verdict_df = df[df['verdict'] == verdict]
        wins = verdict_df[verdict_df['result'] == 'WIN']
        losses = verdict_df[verdict_df['result'] == 'LOSS']
        
        if len(verdict_df) == 0:
            continue
        
        wr = len(wins) / len(verdict_df) * 100
        
        print(f"\n{verdict} SIGNALS ({len(verdict_df)} total)")
        print(f"  Win Rate: {wr:.1f}% ({len(wins)}W-{len(losses)}L)")
        print(f"  Avg Profit: {verdict_df['profit_pct'].mean():+.2f}%")
        
        if len(wins) >= 5 and len(losses) >= 5:
            print(f"\n  Key Differences (WIN vs LOSS):")
            
            indicators = ['confidence', 'cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'volume_spike', 'rsi']
            
            for ind in indicators:
                if ind not in verdict_df.columns:
                    continue
                    
                win_vals = wins[ind].dropna()
                loss_vals = losses[ind].dropna()
                
                if len(win_vals) == 0 or len(loss_vals) == 0:
                    continue
                
                diff = win_vals.mean() - loss_vals.mean()
                effect = cohens_d(win_vals, loss_vals)
                
                if abs(effect) > 0.3:
                    direction = "higher" if diff > 0 else "lower"
                    print(f"    • {ind}: WIN is {direction} ({diff:+.3f}, d={effect:.2f})")

def threshold_analysis(df):
    """Find optimal thresholds for key indicators"""
    print("\n" + "=" * 80)
    print("STEP 5: THRESHOLD OPTIMIZATION")
    print("=" * 80)
    
    indicators = [
        ('confidence', 'Confidence', [0.70, 0.75, 0.80, 0.85, 0.90]),
        ('volume_spike', 'Volume Spike', [0.8, 1.0, 1.2, 1.5, 2.0]),
        ('market_strength', 'Market Strength', [1.0, 1.2, 1.4, 1.6, 1.8])
    ]
    
    for col, name, thresholds in indicators:
        if col not in df.columns:
            continue
        
        print(f"\n{name} Thresholds:")
        print(f"  {'Threshold':<12} {'Signals':<10} {'Win Rate':<12} {'Avg PnL':<12}")
        print(f"  {'-'*46}")
        
        for threshold in thresholds:
            filtered = df[df[col] >= threshold]
            
            if len(filtered) < 5:
                continue
            
            wins = len(filtered[filtered['result'] == 'WIN'])
            wr = wins / len(filtered) * 100
            avg_pnl = filtered['profit_pct'].mean()
            
            print(f"  ≥{threshold:<11.2f} {len(filtered):<10} {wr:>10.1f}% {avg_pnl:>10.2f}%")

def main():
    """Run complete analysis"""
    print("\n" + "=" * 80)
    print("WIN/LOSS PATTERN ANALYSIS")
    print("Identifying what differentiates successful from unsuccessful signals")
    print("=" * 80)
    
    df = merge_datasets()
    
    if len(df) == 0:
        print("\n❌ No data to analyze!")
        return
    
    global_results = global_analysis(df)
    per_symbol_analysis(df)
    verdict_analysis(df)
    threshold_analysis(df)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\n📊 Analyzed {len(df)} signals")
    print(f"💾 Merged data saved to: win_loss_merged_data.csv")
    print(f"📈 Global results show which indicators predict success")
    print(f"🎯 Use findings above to redesign algorithm\n")

if __name__ == '__main__':
    main()
