import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("COMPREHENSIVE CORRELATION ANALYSIS - FULL DATASET")
print("=" * 80)

# Load data
print("\n[1] Loading data files...")
analysis_df = pd.read_csv('analysis_log.csv')
effectiveness_df = pd.read_csv('effectiveness_log.csv')

print(f"  - Analysis log: {len(analysis_df)} records")
print(f"  - Effectiveness log: {len(effectiveness_df)} records")

# Convert timestamps
analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'])
effectiveness_df['timestamp_sent'] = pd.to_datetime(effectiveness_df['timestamp_sent'])

# Filter only actual signals (not NO_TRADE)
signals_analysis = analysis_df[analysis_df['verdict'] != 'NO_TRADE'].copy()
print(f"  - Signals in analysis log: {len(signals_analysis)}")

# Merge on symbol, verdict, and timestamp (within 3 minute window)
print("\n[2] Merging analysis data with effectiveness outcomes...")
merged_data = []
unmatched = []

for idx, eff_row in effectiveness_df.iterrows():
    time_window = timedelta(minutes=3)
    match = signals_analysis[
        (signals_analysis['symbol'] == eff_row['symbol']) &
        (signals_analysis['verdict'] == eff_row['verdict']) &
        (signals_analysis['timestamp'] >= eff_row['timestamp_sent'] - time_window) &
        (signals_analysis['timestamp'] <= eff_row['timestamp_sent'] + time_window)
    ]
    
    if len(match) > 0:
        # Take the closest match by time
        match['time_diff'] = abs(match['timestamp'] - eff_row['timestamp_sent'])
        match = match.loc[match['time_diff'].idxmin()]
        
        merged_row = {
            'timestamp': eff_row['timestamp_sent'],
            'symbol': eff_row['symbol'],
            'verdict': eff_row['verdict'],
            'result': 1 if eff_row['result'] == 'WIN' else 0,
            'profit_pct': eff_row['profit_pct'],
            'confidence': match['confidence'],
            'score': match['score'],
            'price_vs_vwap_pct': match['price_vs_vwap_pct'],
            'cvd': match['cvd'],
            'oi_change_pct': match['oi_change_pct'],
            'volume_spike': 1 if match['volume_spike'] else 0,
            'liq_ratio': match['liq_ratio'],
            'rsi': match['rsi'],
            'atr': match['atr'],
            'market_strength': eff_row['market_strength'],
            'ttl_minutes': match['ttl_minutes'],
            'duration_actual': eff_row['duration_actual'],
        }
        merged_data.append(merged_row)
    else:
        unmatched.append({
            'time': eff_row['timestamp_sent'],
            'symbol': eff_row['symbol'],
            'verdict': eff_row['verdict']
        })

merged_df = pd.DataFrame(merged_data)
print(f"  - Successfully merged: {len(merged_df)} signals")
print(f"  - Unmatched: {len(unmatched)} signals")

if len(merged_df) < 20:
    print(f"\n[WARNING] Only {len(merged_df)} signals matched. Data quality may be limited.")
    print("Unmatched signals (first 10):")
    for i, u in enumerate(unmatched[:10]):
        print(f"  {i+1}. {u['time']} - {u['symbol']} {u['verdict']}")

# Save merged data
merged_df.to_csv('full_merged_analysis.csv', index=False)
print(f"  - Saved to: full_merged_analysis.csv")

# OVERALL STATS
print("\n" + "=" * 80)
print("[OVERALL PERFORMANCE]")
print("=" * 80)
wins = merged_df['result'].sum()
total = len(merged_df)
win_rate = wins / total if total > 0 else 0
avg_profit = merged_df['profit_pct'].mean()
total_profit = merged_df['profit_pct'].sum()
print(f"Win Rate: {int(wins)}W-{total-int(wins)}L ({win_rate*100:.1f}%)")
print(f"Average Profit per Trade: {avg_profit:.3f}%")
print(f"Total Cumulative P/L: {total_profit:.2f}%")

# Winners vs Losers breakdown
winners = merged_df[merged_df['result'] == 1]
losers = merged_df[merged_df['result'] == 0]
print(f"\nWinning Trades: Avg profit = {winners['profit_pct'].mean():.3f}%")
print(f"Losing Trades: Avg loss = {losers['profit_pct'].mean():.3f}%")

if len(merged_df) < 10:
    print("\n[ERROR] Insufficient data for correlation analysis (need at least 10 samples)")
    exit(1)

# CORRELATION ANALYSIS
print("\n" + "=" * 80)
print("[3] CORRELATION ANALYSIS: Which indicators predict SUCCESS?")
print("=" * 80)
print("\nPositive correlation = Higher values increase win probability")
print("Negative correlation = Lower values increase win probability")
print("-" * 80)

indicators = {
    'confidence': 'Confidence Score',
    'score': 'Weighted Score',
    'cvd': 'Cumulative Volume Delta',
    'oi_change_pct': 'Open Interest Change %',
    'price_vs_vwap_pct': 'Price vs VWAP %',
    'volume_spike': 'Volume Spike',
    'liq_ratio': 'Liquidation Ratio',
    'rsi': 'RSI',
    'market_strength': 'Market Strength Multiplier',
    'atr': 'ATR',
    'ttl_minutes': 'Signal Duration (TTL)',
}

correlations = []
for indicator, name in indicators.items():
    clean_data = merged_df[[indicator, 'result']].dropna()
    clean_data = clean_data[np.isfinite(clean_data[indicator])]
    
    if len(clean_data) > 9:
        pearson_corr, pearson_p = stats.pearsonr(clean_data[indicator], clean_data['result'])
        spearman_corr, spearman_p = stats.spearmanr(clean_data[indicator], clean_data['result'])
        
        correlations.append({
            'indicator': indicator,
            'name': name,
            'pearson_corr': pearson_corr,
            'pearson_p_value': pearson_p,
            'spearman_corr': spearman_corr,
            'spearman_p_value': spearman_p,
            'samples': len(clean_data)
        })
        
        sig = "***" if pearson_p < 0.01 else ("**" if pearson_p < 0.05 else ("*" if pearson_p < 0.10 else ""))
        direction = "↑ POSITIVE" if pearson_corr > 0 else "↓ NEGATIVE"
        
        print(f"{name:30s}  {pearson_corr:+7.3f} {sig:3s} {direction:12s}  (p={pearson_p:.4f}, n={len(clean_data)})")

if len(correlations) > 0:
    corr_df = pd.DataFrame(correlations)
    corr_df = corr_df.reindex(corr_df['pearson_corr'].abs().sort_values(ascending=False).index)
    corr_df.to_csv('full_correlation_results.csv', index=False)
    
    print("\n  *** = p<0.01 (highly significant)")
    print("  **  = p<0.05 (significant)")
    print("  *   = p<0.10 (marginally significant)")
    
    print("\n[TOP PREDICTIVE INDICATORS]")
    print("-" * 80)
    for i, row in corr_df.head(5).iterrows():
        print(f"{i+1}. {row['name']:30s}  Correlation: {row['pearson_corr']:+.3f}")

# SYMBOL PERFORMANCE
print("\n" + "=" * 80)
print("[4] PERFORMANCE BY SYMBOL")
print("=" * 80)
symbol_stats = []
for symbol in sorted(merged_df['symbol'].unique()):
    symbol_data = merged_df[merged_df['symbol'] == symbol]
    wins = symbol_data['result'].sum()
    total = len(symbol_data)
    win_rate = wins / total if total > 0 else 0
    avg_profit = symbol_data['profit_pct'].mean()
    total_profit = symbol_data['profit_pct'].sum()
    symbol_stats.append({
        'symbol': symbol,
        'win_rate': win_rate,
        'wins': int(wins),
        'total': total,
        'avg_profit': avg_profit,
        'total_profit': total_profit
    })

symbol_stats_df = pd.DataFrame(symbol_stats).sort_values('win_rate', ascending=False)
for _, row in symbol_stats_df.iterrows():
    emoji = "🟢" if row['win_rate'] >= 0.4 else ("🟡" if row['win_rate'] >= 0.25 else "🔴")
    print(f"{emoji} {row['symbol']:10s}  {row['wins']:2d}W-{row['total']-row['wins']:2d}L  ({row['win_rate']*100:5.1f}%)  Avg: {row['avg_profit']:+6.3f}%  Total: {row['total_profit']:+7.2f}%")

# VERDICT PERFORMANCE
print("\n" + "=" * 80)
print("[5] PERFORMANCE BY VERDICT (BUY vs SELL)")
print("=" * 80)
for verdict in ['BUY', 'SELL']:
    verdict_data = merged_df[merged_df['verdict'] == verdict]
    if len(verdict_data) > 0:
        wins = verdict_data['result'].sum()
        total = len(verdict_data)
        win_rate = wins / total
        avg_profit = verdict_data['profit_pct'].mean()
        total_profit = verdict_data['profit_pct'].sum()
        emoji = "🟢" if win_rate >= 0.4 else ("🟡" if win_rate >= 0.25 else "🔴")
        print(f"{emoji} {verdict:5s}  {int(wins):2d}W-{total-int(wins):2d}L  ({win_rate*100:5.1f}%)  Avg: {avg_profit:+6.3f}%  Total: {total_profit:+7.2f}%")
    else:
        print(f"   {verdict:5s}  No data")

# INDICATOR VALUE COMPARISON
print("\n" + "=" * 80)
print("[6] INDICATOR VALUES: Winners vs Losers")
print("=" * 80)
for indicator in ['confidence', 'score', 'cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'liq_ratio', 'market_strength']:
    if indicator in merged_df.columns:
        win_mean = winners[indicator].mean() if len(winners) > 0 else 0
        lose_mean = losers[indicator].mean() if len(losers) > 0 else 0
        diff = win_mean - lose_mean
        diff_pct = (diff / abs(lose_mean) * 100) if lose_mean != 0 else 0
        
        better = "✓ WINNERS HIGHER" if diff > 0 else "✗ LOSERS HIGHER"
        print(f"\n{indicator.upper().replace('_', ' ')}:")
        print(f"  Winners: {win_mean:10.3f}  |  Losers: {lose_mean:10.3f}  |  Diff: {diff:+10.3f} ({diff_pct:+.1f}%)  {better}")

# TIME-BASED ANALYSIS
print("\n" + "=" * 80)
print("[7] PERFORMANCE BY HOUR OF DAY")
print("=" * 80)
merged_df['hour'] = pd.to_datetime(merged_df['timestamp']).dt.hour

for hour in sorted(merged_df['hour'].unique()):
    hour_data = merged_df[merged_df['hour'] == hour]
    wins = hour_data['result'].sum()
    total = len(hour_data)
    win_rate = wins / total
    avg_profit = hour_data['profit_pct'].mean()
    emoji = "🟢" if win_rate >= 0.4 else ("🟡" if win_rate >= 0.25 else "🔴")
    print(f"{emoji} {hour:02d}:00  {int(wins):2d}W-{total-int(wins):2d}L  ({win_rate*100:5.1f}%)  Avg: {avg_profit:+6.3f}%")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print(f"\nOutput files:")
print(f"  - full_merged_analysis.csv: Complete merged dataset")
print(f"  - full_correlation_results.csv: Statistical correlations")
