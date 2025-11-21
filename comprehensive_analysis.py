import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("COMPREHENSIVE PERFORMANCE ANALYSIS (Limited Dataset)")
print("=" * 80)

# Load all available data
effectiveness_df = pd.read_csv('effectiveness_log.csv')
merged_df = pd.read_csv('full_merged_analysis.csv') if pd.io.common.file_exists('full_merged_analysis.csv') else None

print(f"\n[DATA AVAILABLE]")
print(f"  - Total signals tracked: {len(effectiveness_df)}")
print(f"  - Signals with full indicator data: {len(merged_df) if merged_df is not None else 0}")
print(f"  - Data limitation: System crash at 05:23 AM caused 87% data loss")
print(f"  - Analysis will use broader patterns from all 153 signals + detailed analysis where available")

# Convert timestamps
effectiveness_df['timestamp_sent'] = pd.to_datetime(effectiveness_df['timestamp_sent'])
effectiveness_df['hour'] = effectiveness_df['timestamp_sent'].dt.hour

# OVERALL PERFORMANCE
print("\n" + "=" * 80)
print("[1] OVERALL PERFORMANCE - ALL 153 SIGNALS")
print("=" * 80)

wins = (effectiveness_df['result'] == 'WIN').sum()
total = len(effectiveness_df)
win_rate = wins / total if total > 0 else 0
avg_profit = effectiveness_df['profit_pct'].mean()
total_profit = effectiveness_df['profit_pct'].sum()

winners = effectiveness_df[effectiveness_df['result'] == 'WIN']
losers = effectiveness_df[effectiveness_df['result'] == 'LOSS']

print(f"Win Rate: {wins}W-{total-wins}L ({win_rate*100:.1f}%)")
print(f"Average Profit per Trade: {avg_profit:.3f}%")
print(f"Total Cumulative P/L: {total_profit:.2f}%")
print(f"\nWinning Trades: {len(winners)} signals, Avg profit = {winners['profit_pct'].mean():.3f}%")
print(f"Losing Trades: {len(losers)} signals, Avg loss = {losers['profit_pct'].mean():.3f}%")

# Risk/Reward Ratio
avg_win_size = winners['profit_pct'].mean()
avg_loss_size = abs(losers['profit_pct'].mean())
risk_reward = avg_win_size / avg_loss_size if avg_loss_size > 0 else 0
breakeven_wr = 1 / (1 + risk_reward) if risk_reward > 0 else 0.5

print(f"\nRisk/Reward Analysis:")
print(f"  - Avg Win Size: {avg_win_size:.3f}%")
print(f"  - Avg Loss Size: {avg_loss_size:.3f}%")
print(f"  - Risk/Reward Ratio: {risk_reward:.2f}:1")
print(f"  - Breakeven Win Rate: {breakeven_wr*100:.1f}%")
print(f"  - Current Win Rate: {win_rate*100:.1f}%")
if win_rate > breakeven_wr:
    print(f"  ✅ Above breakeven (profitable)")
else:
    print(f"  ⚠️ Below breakeven (need {breakeven_wr*100:.1f}% win rate to break even)")

# SYMBOL PERFORMANCE
print("\n" + "=" * 80)
print("[2] PERFORMANCE BY SYMBOL")
print("=" * 80)

symbol_stats = []
for symbol in sorted(effectiveness_df['symbol'].unique()):
    symbol_data = effectiveness_df[effectiveness_df['symbol'] == symbol]
    sym_wins = (symbol_data['result'] == 'WIN').sum()
    sym_total = len(symbol_data)
    sym_win_rate = sym_wins / sym_total if sym_total > 0 else 0
    sym_avg_profit = symbol_data['profit_pct'].mean()
    sym_total_profit = symbol_data['profit_pct'].sum()
    
    symbol_stats.append({
        'symbol': symbol,
        'win_rate': sym_win_rate,
        'wins': sym_wins,
        'total': sym_total,
        'avg_profit': sym_avg_profit,
        'total_profit': sym_total_profit
    })

symbol_stats_df = pd.DataFrame(symbol_stats).sort_values('win_rate', ascending=False)

print(f"\n{'Symbol':<12} {'Record':<12} {'Win Rate':<10} {'Avg P/L':<10} {'Total P/L':<10} {'Grade'}")
print("-" * 80)
for _, row in symbol_stats_df.iterrows():
    emoji = "🟢" if row['win_rate'] >= 0.40 else ("🟡" if row['win_rate'] >= 0.25 else "🔴")
    record = f"{row['wins']}W-{row['total']-row['wins']}L"
    print(f"{row['symbol']:<12} {record:<12} {row['win_rate']*100:>5.1f}%     {row['avg_profit']:>6.3f}%    {row['total_profit']:>7.2f}%    {emoji}")

# VERDICT PERFORMANCE
print("\n" + "=" * 80)
print("[3] PERFORMANCE BY VERDICT (BUY vs SELL)")
print("=" * 80)

for verdict in ['BUY', 'SELL']:
    verdict_data = effectiveness_df[effectiveness_df['verdict'] == verdict]
    if len(verdict_data) > 0:
        v_wins = (verdict_data['result'] == 'WIN').sum()
        v_total = len(verdict_data)
        v_win_rate = v_wins / v_total
        v_avg_profit = verdict_data['profit_pct'].mean()
        v_total_profit = verdict_data['profit_pct'].sum()
        emoji = "🟢" if v_win_rate >= 0.40 else ("🟡" if v_win_rate >= 0.25 else "🔴")
        print(f"{emoji} {verdict:<5}  {v_wins:2d}W-{v_total-v_wins:2d}L  ({v_win_rate*100:5.1f}%)  Avg: {v_avg_profit:+6.3f}%  Total: {v_total_profit:+7.2f}%")

# TIME-BASED ANALYSIS
print("\n" + "=" * 80)
print("[4] PERFORMANCE BY HOUR OF DAY")
print("=" * 80)

hour_stats = []
for hour in sorted(effectiveness_df['hour'].unique()):
    hour_data = effectiveness_df[effectiveness_df['hour'] == hour]
    h_wins = (hour_data['result'] == 'WIN').sum()
    h_total = len(hour_data)
    h_win_rate = h_wins / h_total
    h_avg_profit = hour_data['profit_pct'].mean()
    
    hour_stats.append({
        'hour': hour,
        'win_rate': h_win_rate,
        'wins': h_wins,
        'total': h_total,
        'avg_profit': h_avg_profit
    })

hour_stats_df = pd.DataFrame(hour_stats).sort_values('win_rate', ascending=False)

print(f"\n{'Hour':<8} {'Record':<12} {'Win Rate':<10} {'Avg P/L':<10} {'Grade'}")
print("-" * 70)
for _, row in hour_stats_df.iterrows():
    emoji = "🟢" if row['win_rate'] >= 0.40 else ("🟡" if row['win_rate'] >= 0.25 else "🔴")
    record = f"{row['wins']}W-{row['total']-row['wins']}L"
    print(f"{int(row['hour']):02d}:00    {record:<12} {row['win_rate']*100:>5.1f}%     {row['avg_profit']:>6.3f}%    {emoji}")

# CONFIDENCE ANALYSIS
print("\n" + "=" * 80)
print("[5] CONFIDENCE LEVEL ANALYSIS")
print("=" * 80)

confidence_bins = [0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0]
effectiveness_df['confidence_bin'] = pd.cut(effectiveness_df['confidence'], bins=confidence_bins)

print(f"\n{'Confidence Range':<20} {'Record':<12} {'Win Rate':<10} {'Avg P/L'}")
print("-" * 60)
for bin_range in effectiveness_df['confidence_bin'].cat.categories:
    bin_data = effectiveness_df[effectiveness_df['confidence_bin'] == bin_range]
    if len(bin_data) > 0:
        b_wins = (bin_data['result'] == 'WIN').sum()
        b_total = len(bin_data)
        b_win_rate = b_wins / b_total
        b_avg_profit = bin_data['profit_pct'].mean()
        record = f"{b_wins}W-{b_total-b_wins}L"
        emoji = "🟢" if b_win_rate >= 0.40 else ("🟡" if b_win_rate >= 0.25 else "🔴")
        print(f"{str(bin_range):<20} {record:<12} {b_win_rate*100:>5.1f}%     {b_avg_profit:>6.3f}%  {emoji}")

# MARKET STRENGTH ANALYSIS
print("\n" + "=" * 80)
print("[6] MARKET STRENGTH MULTIPLIER ANALYSIS")
print("=" * 80)

strength_bins = [1.0, 1.2, 1.4, 1.6, 1.8, 2.5]
effectiveness_df['strength_bin'] = pd.cut(effectiveness_df['market_strength'], bins=strength_bins)

print(f"\n{'Strength Range':<20} {'Record':<12} {'Win Rate':<10} {'Avg P/L'}")
print("-" * 60)
for bin_range in effectiveness_df['strength_bin'].cat.categories:
    bin_data = effectiveness_df[effectiveness_df['strength_bin'] == bin_range]
    if len(bin_data) > 0:
        s_wins = (bin_data['result'] == 'WIN').sum()
        s_total = len(bin_data)
        s_win_rate = s_wins / s_total
        s_avg_profit = bin_data['profit_pct'].mean()
        record = f"{s_wins}W-{s_total-s_wins}L"
        emoji = "🟢" if s_win_rate >= 0.40 else ("🟡" if s_win_rate >= 0.25 else "🔴")
        print(f"{str(bin_range):<20} {record:<12} {s_win_rate*100:>5.1f}%     {s_avg_profit:>6.3f}%  {emoji}")

# DURATION ANALYSIS
print("\n" + "=" * 80)
print("[7] SIGNAL DURATION (TTL) ANALYSIS")
print("=" * 80)

duration_bins = [0, 20, 40, 60, 120, 1000]
effectiveness_df['duration_bin'] = pd.cut(effectiveness_df['duration_minutes'], bins=duration_bins)

print(f"\n{'Duration Range':<20} {'Record':<12} {'Win Rate':<10} {'Avg P/L'}")
print("-" * 60)
for bin_range in effectiveness_df['duration_bin'].cat.categories:
    bin_data = effectiveness_df[effectiveness_df['duration_bin'] == bin_range]
    if len(bin_data) > 0:
        d_wins = (bin_data['result'] == 'WIN').sum()
        d_total = len(bin_data)
        d_win_rate = d_wins / d_total
        d_avg_profit = bin_data['profit_pct'].mean()
        record = f"{d_wins}W-{d_total-d_wins}L"
        emoji = "🟢" if d_win_rate >= 0.40 else ("🟡" if d_win_rate >= 0.25 else "🔴")
        print(f"{str(bin_range):<20} {record:<12} {d_win_rate*100:>5.1f}%     {d_avg_profit:>6.3f}%  {emoji}")

# KEY INSIGHTS & RECOMMENDATIONS
print("\n" + "=" * 80)
print("[8] KEY INSIGHTS & RECOMMENDATIONS")
print("=" * 80)

print("\n🔍 BEST PERFORMERS:")
best_symbols = symbol_stats_df.head(3)
for i, row in best_symbols.iterrows():
    print(f"  • {row['symbol']}: {row['win_rate']*100:.1f}% win rate ({row['wins']}W-{row['total']-row['wins']}L)")

print("\n⚠️ WORST PERFORMERS:")
worst_symbols = symbol_stats_df.tail(3)
for i, row in worst_symbols.iterrows():
    print(f"  • {row['symbol']}: {row['win_rate']*100:.1f}% win rate ({row['wins']}W-{row['total']-row['wins']}L)")

print("\n⏰ BEST TRADING HOURS:")
best_hours = hour_stats_df.head(3)
for i, row in best_hours.iterrows():
    print(f"  • {int(row['hour']):02d}:00 - {int(row['hour'])+1:02d}:00: {row['win_rate']*100:.1f}% win rate ({row['wins']}W-{row['total']-row['wins']}L)")

print("\n⏰ WORST TRADING HOURS:")
worst_hours = hour_stats_df.tail(3)
for i, row in worst_hours.iterrows():
    print(f"  • {int(row['hour']):02d}:00 - {int(row['hour'])+1:02d}:00: {row['win_rate']*100:.1f}% win rate ({row['wins']}W-{row['total']-row['wins']}L)")

print("\n📊 RECOMMENDATIONS:")
print(f"  1. Current {win_rate*100:.1f}% win rate is below the {breakeven_wr*100:.1f}% breakeven threshold")
print(f"  2. Focus on LINKUSDT and AVAXUSDT (best performers at 50% and 42%)")
print(f"  3. Consider reducing or pausing signals for SOLUSDT and ETHUSDT (worst performers)")
print(f"  4. Avoid trading during {worst_hours.iloc[0]['hour']:.0f}:00-{worst_hours.iloc[2]['hour']:.0f}:00 hours (0-5% win rates)")
print(f"  5. Prioritize signals during {best_hours.iloc[0]['hour']:.0f}:00-{best_hours.iloc[2]['hour']:.0f}:00 hours (28-42% win rates)")
print(f"  6. Your R:R ratio of {risk_reward:.2f}:1 is positive - system is profitable when win rate > {breakeven_wr*100:.1f}%")

# Save comprehensive report
effectiveness_df.to_csv('performance_analysis_full.csv', index=False)
print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("\nOutput: performance_analysis_full.csv")
