import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats

print("=" * 80)
print("COMPREHENSIVE CORRELATION ANALYSIS")
print("=" * 80)

# Load data
print("\n[1] Loading data files...")
signals_df = pd.read_csv('signals_log.csv')
effectiveness_df = pd.read_csv('effectiveness_log.csv')

print(f"  - Signals sent: {len(signals_df)} records")
print(f"  - Effectiveness log: {len(effectiveness_df)} records")

# Convert timestamps
signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])
effectiveness_df['timestamp_sent'] = pd.to_datetime(effectiveness_df['timestamp_sent'])

# Merge on symbol, verdict, and timestamp (within 2 minute window)
print("\n[2] Merging signal data with outcomes...")
merged_data = []

for idx, eff_row in effectiveness_df.iterrows():
    # Find matching signal in signals log
    time_window = timedelta(minutes=2)
    match = signals_df[
        (signals_df['symbol'] == eff_row['symbol']) &
        (signals_df['verdict'] == eff_row['verdict']) &
        (signals_df['timestamp'] >= eff_row['timestamp_sent'] - time_window) &
        (signals_df['timestamp'] <= eff_row['timestamp_sent'] + time_window)
    ]
    
    if len(match) > 0:
        # Take the closest match
        match = match.iloc[0]
        
        # Parse components to extract indicator values
        components = match['components'].split('|')
        
        merged_row = {
            'timestamp': eff_row['timestamp_sent'],
            'symbol': eff_row['symbol'],
            'verdict': eff_row['verdict'],
            'result': 1 if eff_row['result'] == 'WIN' else 0,
            'profit_pct': eff_row['profit_pct'],
            'confidence': match['confidence'],
            'score': match['score'],
            'oi_change': match['oi_change'],
            'volume_spike': 1 if match['volume_spike'] else 0,
            'liq_long': match['liq_long'],
            'liq_short': match['liq_short'],
            'liq_ratio': match['liq_short'] / max(match['liq_long'], 1) if match['verdict'] == 'SELL' else match['liq_long'] / max(match['liq_short'], 1),
            'market_strength': eff_row['market_strength'],
            'ttl_minutes': match['ttl_minutes'],
            'components': match['components'],
            'has_cvd': 1 if any('CVD' in c for c in components) else 0,
            'has_oi': 1 if any('OI' in c for c in components) else 0,
            'has_vwap': 1 if any('VWAP' in c for c in components) else 0,
            'has_liq': 1 if any('Liq' in c for c in components) else 0,
            'has_rsi': 1 if any('RSI' in c for c in components) else 0,
        }
        merged_data.append(merged_row)

merged_df = pd.DataFrame(merged_data)
print(f"  - Successfully merged: {len(merged_df)} signals")
print(f"  - Unmatched signals: {len(effectiveness_df) - len(merged_df)}")

if len(merged_df) == 0:
    print("\n[ERROR] No matching signals found! Cannot perform correlation analysis.")
    exit(1)

# Save merged data
merged_df.to_csv('merged_analysis.csv', index=False)
print(f"  - Saved to: merged_analysis.csv")

# Overall stats
print("\n[OVERALL PERFORMANCE]")
print("=" * 80)
wins = merged_df['result'].sum()
total = len(merged_df)
win_rate = wins / total if total > 0 else 0
avg_profit = merged_df['profit_pct'].mean()
print(f"Win Rate: {wins}W-{total-wins}L ({win_rate*100:.1f}%)")
print(f"Average Profit per Trade: {avg_profit:.2f}%")
print(f"Total Cumulative: {merged_df['profit_pct'].sum():.2f}%")

# Calculate correlations
print("\n[3] CORRELATION ANALYSIS: Which indicators predict success?")
print("=" * 80)

numeric_indicators = ['confidence', 'score', 'oi_change', 'volume_spike', 'liq_ratio', 
                      'market_strength', 'ttl_minutes', 'has_cvd', 'has_oi', 'has_vwap', 
                      'has_liq', 'has_rsi']

correlations = []
for indicator in numeric_indicators:
    # Remove NaN and inf values
    clean_data = merged_df[[indicator, 'result']].dropna()
    clean_data = clean_data[np.isfinite(clean_data[indicator])]
    
    if len(clean_data) > 10:
        # Pearson correlation (linear)
        pearson_corr, pearson_p = stats.pearsonr(clean_data[indicator], clean_data['result'])
        
        # Spearman correlation (non-linear)
        spearman_corr, spearman_p = stats.spearmanr(clean_data[indicator], clean_data['result'])
        
        correlations.append({
            'indicator': indicator,
            'pearson_corr': pearson_corr,
            'pearson_p_value': pearson_p,
            'spearman_corr': spearman_corr,
            'spearman_p_value': spearman_p,
            'samples': len(clean_data)
        })
        
        # Statistical significance marker
        sig = "***" if pearson_p < 0.01 else ("**" if pearson_p < 0.05 else ("*" if pearson_p < 0.10 else ""))
        
        print(f"{indicator:20s}  Pearson: {pearson_corr:7.3f} {sig:3s}  Spearman: {spearman_corr:7.3f}  (n={len(clean_data)})")

if len(correlations) > 0:
    corr_df = pd.DataFrame(correlations)
    corr_df = corr_df.reindex(corr_df['pearson_corr'].abs().sort_values(ascending=False).index)
    corr_df.to_csv('correlation_results.csv', index=False)

print("\n  *** = p<0.01 (highly significant)")
print("  **  = p<0.05 (significant)")
print("  *   = p<0.10 (marginally significant)")

# Symbol-specific analysis
print("\n[4] PERFORMANCE BY SYMBOL")
print("=" * 80)
symbol_stats = []
for symbol in sorted(merged_df['symbol'].unique()):
    symbol_data = merged_df[merged_df['symbol'] == symbol]
    wins = symbol_data['result'].sum()
    total = len(symbol_data)
    win_rate = wins / total if total > 0 else 0
    avg_profit = symbol_data['profit_pct'].mean()
    symbol_stats.append({'symbol': symbol, 'win_rate': win_rate, 'wins': wins, 'total': total, 'avg_profit': avg_profit})
    print(f"{symbol:10s}  {wins:2d}W-{total-wins:2d}L  ({win_rate*100:5.1f}%)  Avg: {avg_profit:6.2f}%")

# Verdict-specific analysis
print("\n[5] PERFORMANCE BY VERDICT (BUY vs SELL)")
print("=" * 80)
for verdict in ['BUY', 'SELL']:
    verdict_data = merged_df[merged_df['verdict'] == verdict]
    wins = verdict_data['result'].sum()
    total = len(verdict_data)
    win_rate = wins / total if total > 0 else 0
    avg_profit = verdict_data['profit_pct'].mean()
    print(f"{verdict:5s}  {wins:2d}W-{total-wins:2d}L  ({win_rate*100:5.1f}%)  Avg: {avg_profit:6.2f}%")

# Indicator combination analysis
print("\n[6] COMPONENT ANALYSIS: Which indicators appear in winners?")
print("=" * 80)
winners = merged_df[merged_df['result'] == 1]
losers = merged_df[merged_df['result'] == 0]

components_list = ['has_cvd', 'has_oi', 'has_vwap', 'has_liq', 'has_rsi']
for comp in components_list:
    win_pct = winners[comp].mean() * 100 if len(winners) > 0 else 0
    lose_pct = losers[comp].mean() * 100 if len(losers) > 0 else 0
    diff = win_pct - lose_pct
    print(f"{comp:15s}  Winners: {win_pct:5.1f}%  Losers: {lose_pct:5.1f}%  Diff: {diff:+6.1f}%")

# Numeric indicator ranges
print("\n[7] INDICATOR VALUES: Winners vs Losers")
print("=" * 80)
for indicator in ['confidence', 'score', 'market_strength', 'ttl_minutes', 'liq_ratio']:
    if indicator in merged_df.columns:
        win_mean = winners[indicator].mean() if len(winners) > 0 else 0
        lose_mean = losers[indicator].mean() if len(losers) > 0 else 0
        win_std = winners[indicator].std() if len(winners) > 1 else 0
        lose_std = losers[indicator].std() if len(losers) > 1 else 0
        
        print(f"\n{indicator}:")
        print(f"  WINNERS: {win_mean:8.3f} ± {win_std:6.3f}")
        print(f"  LOSERS:  {lose_mean:8.3f} ± {lose_std:6.3f}")
        print(f"  Difference: {win_mean - lose_mean:+8.3f}")

# Time-based analysis
print("\n[8] PERFORMANCE BY HOUR OF DAY")
print("=" * 80)
merged_df['hour'] = pd.to_datetime(merged_df['timestamp']).dt.hour

for hour in sorted(merged_df['hour'].unique()):
    hour_data = merged_df[merged_df['hour'] == hour]
    wins = hour_data['result'].sum()
    total = len(hour_data)
    win_rate = wins / total if total > 0 else 0
    avg_profit = hour_data['profit_pct'].mean()
    print(f"{hour:02d}:00  {wins:2d}W-{total-wins:2d}L  ({win_rate*100:5.1f}%)  Avg: {avg_profit:6.2f}%")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE - Check merged_analysis.csv and correlation_results.csv")
print("=" * 80)
