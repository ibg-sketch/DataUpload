"""
Target Size Optimization Analysis
Determines what target sizes would have converted losing signals into wins
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("="*80)
print("TARGET SIZE OPTIMIZATION ANALYSIS")
print("="*80)

# Load effectiveness data
effectiveness_df = pd.read_csv('effectiveness_log.csv', parse_dates=['timestamp_sent', 'timestamp_checked'])

# Filter last 11 hours
cutoff_time = datetime.now() - timedelta(hours=11)
recent_eff = effectiveness_df[effectiveness_df['timestamp_sent'] >= cutoff_time].copy()

print(f"\nAnalyzing {len(recent_eff)} completed signals from last 11 hours")
print(f"Wins: {(recent_eff['result'] == 'WIN').sum()}")
print(f"Losses: {(recent_eff['result'] == 'LOSS').sum()}")
print(f"Current Win Rate: {(recent_eff['result'] == 'WIN').sum() / len(recent_eff) * 100:.1f}%")

# Calculate actual price movement for each signal
def calculate_actual_movement(row):
    """Calculate how far price actually moved in the predicted direction"""
    entry = row['entry_price']
    
    if row['verdict'] == 'BUY':
        # For BUY: check how high it went
        best_move = ((row['highest_reached'] - entry) / entry) * 100
    else:  # SELL
        # For SELL: check how low it went
        best_move = ((entry - row['lowest_reached']) / entry) * 100
    
    return best_move

recent_eff['actual_move_pct'] = recent_eff.apply(calculate_actual_movement, axis=1)

# Calculate what the target was (percentage)
def calculate_target_pct(row):
    """Calculate target as percentage from entry"""
    entry = row['entry_price']
    target_min = row['target_min']
    target_max = row['target_max']
    
    if row['verdict'] == 'BUY':
        target_pct = ((target_min - entry) / entry) * 100
    else:  # SELL
        target_pct = ((entry - target_max) / entry) * 100
    
    return target_pct

recent_eff['target_pct'] = recent_eff.apply(calculate_target_pct, axis=1)

print("\n" + "="*80)
print("SECTION 1: CURRENT TARGET ANALYSIS")
print("="*80)

print(f"\n📊 AVERAGE TARGET SIZES:")
print(f"Overall average target: {recent_eff['target_pct'].mean():.3f}%")
print(f"BUY signals average target: {recent_eff[recent_eff['verdict'] == 'BUY']['target_pct'].mean():.3f}%")
print(f"SELL signals average target: {recent_eff[recent_eff['verdict'] == 'SELL']['target_pct'].mean():.3f}%")

print(f"\n📊 AVERAGE ACTUAL MOVES:")
print(f"Overall average move: {recent_eff['actual_move_pct'].mean():.3f}%")
print(f"BUY signals average move: {recent_eff[recent_eff['verdict'] == 'BUY']['actual_move_pct'].mean():.3f}%")
print(f"SELL signals average move: {recent_eff[recent_eff['verdict'] == 'SELL']['actual_move_pct'].mean():.3f}%")

# Winners vs Losers analysis
winners = recent_eff[recent_eff['result'] == 'WIN']
losers = recent_eff[recent_eff['result'] == 'LOSS']

print(f"\n📊 WINNERS:")
print(f"Average target: {winners['target_pct'].mean():.3f}%")
print(f"Average actual move: {winners['actual_move_pct'].mean():.3f}%")

print(f"\n📊 LOSERS:")
print(f"Average target: {losers['target_pct'].mean():.3f}%")
print(f"Average actual move: {losers['actual_move_pct'].mean():.3f}%")

print("\n" + "="*80)
print("SECTION 2: WHAT IF WE REDUCED TARGETS?")
print("="*80)

# Test different target multipliers
multipliers = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

results = []
for mult in multipliers:
    # Calculate how many would win with this multiplier
    recent_eff['would_win'] = recent_eff['actual_move_pct'] >= (recent_eff['target_pct'] * mult)
    wins = recent_eff['would_win'].sum()
    win_rate = (wins / len(recent_eff)) * 100
    
    results.append({
        'multiplier': mult,
        'target_size': f"{recent_eff['target_pct'].mean() * mult:.3f}%",
        'wins': wins,
        'losses': len(recent_eff) - wins,
        'win_rate': win_rate
    })

results_df = pd.DataFrame(results)

print("\n🎯 WIN RATE WITH DIFFERENT TARGET SIZES:")
print("\n" + "-"*80)
print(f"{'Multiplier':<12} {'Avg Target':<12} {'Wins':<8} {'Losses':<8} {'Win Rate':<10} {'vs 80% Target':<15}")
print("-"*80)

for _, row in results_df.iterrows():
    status = "✅" if row['win_rate'] >= 80 else "⚠️" if row['win_rate'] >= 60 else "❌"
    gap = row['win_rate'] - 80
    print(f"{row['multiplier']:<12.1f} {row['target_size']:<12} {row['wins']:<8} {row['losses']:<8} {row['win_rate']:<9.1f}% {gap:+.1f}pp {status}")

print("-"*80)

# Find optimal multiplier
optimal = results_df.loc[results_df['win_rate'].idxmax()]
print(f"\n🏆 OPTIMAL TARGET SIZE:")
print(f"Multiplier: {optimal['multiplier']:.1f}x")
print(f"Average target: {optimal['target_size']}")
print(f"Win rate: {optimal['win_rate']:.1f}%")
print(f"Gap to 80%: {optimal['win_rate'] - 80:+.1f}pp")

# Find minimum multiplier to hit 80%
target_80 = results_df[results_df['win_rate'] >= 80]
if len(target_80) > 0:
    min_80 = target_80.iloc[0]
    print(f"\n🎯 MINIMUM TO HIT 80% WIN RATE:")
    print(f"Multiplier: {min_80['multiplier']:.1f}x")
    print(f"Average target: {min_80['target_size']}")
    print(f"Win rate: {min_80['win_rate']:.1f}%")
else:
    print(f"\n⚠️ CANNOT REACH 80% by reducing targets alone")
    print(f"Maximum achievable: {optimal['win_rate']:.1f}%")

print("\n" + "="*80)
print("SECTION 3: DETAILED BREAKDOWN OF LOSING SIGNALS")
print("="*80)

print(f"\n❌ ANALYZING {len(losers)} LOSING SIGNALS:")

# Categorize losses
categories = {
    'Moved 50%+ of target': losers[losers['actual_move_pct'] >= losers['target_pct'] * 0.5],
    'Moved 30-50% of target': losers[(losers['actual_move_pct'] >= losers['target_pct'] * 0.3) & 
                                      (losers['actual_move_pct'] < losers['target_pct'] * 0.5)],
    'Moved <30% of target': losers[losers['actual_move_pct'] < losers['target_pct'] * 0.3],
    'Moved opposite direction': losers[losers['actual_move_pct'] < 0]
}

for category, data in categories.items():
    pct = len(data) / len(losers) * 100 if len(losers) > 0 else 0
    print(f"{category}: {len(data)} ({pct:.1f}%)")

print("\n📊 SAMPLE OF NEAR-MISS SIGNALS (moved 50%+ of target):")
near_misses = losers[losers['actual_move_pct'] >= losers['target_pct'] * 0.5].head(10)

if len(near_misses) > 0:
    print(f"\n{'Symbol':<12} {'Type':<6} {'Entry':<10} {'Target':<8} {'Moved':<8} {'Completion':<12}")
    print("-"*70)
    for _, row in near_misses.iterrows():
        completion = (row['actual_move_pct'] / row['target_pct']) * 100
        print(f"{row['symbol']:<12} {row['verdict']:<6} ${row['entry_price']:<9.2f} {row['target_pct']:.2f}% {row['actual_move_pct']:.2f}% {completion:.0f}%")

print("\n" + "="*80)
print("SECTION 4: BY-SYMBOL TARGET ANALYSIS")
print("="*80)

print(f"\n📊 OPTIMAL TARGETS BY SYMBOL:")
print(f"\n{'Symbol':<12} {'Current Avg':<14} {'Actual Avg':<14} {'Suggested':<14} {'Current WR':<12} {'New WR (0.5x)':<15}")
print("-"*85)

for symbol in sorted(recent_eff['symbol'].unique()):
    sym_data = recent_eff[recent_eff['symbol'] == symbol].copy()
    
    current_target = sym_data['target_pct'].mean()
    actual_move = sym_data['actual_move_pct'].mean()
    suggested = actual_move * 0.8  # 80% of average actual move
    
    current_wr = (sym_data['result'] == 'WIN').sum() / len(sym_data) * 100
    
    # Calculate WR with 0.5x targets
    sym_data['would_win_half'] = sym_data['actual_move_pct'] >= (sym_data['target_pct'] * 0.5)
    new_wr = sym_data['would_win_half'].sum() / len(sym_data) * 100
    
    improvement = new_wr - current_wr
    print(f"{symbol:<12} {current_target:>6.3f}% {actual_move:>6.3f}% {suggested:>6.3f}% {current_wr:>7.1f}% {new_wr:>8.1f}% (+{improvement:.1f}pp)")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

print(f"\n💡 KEY FINDINGS:")
print(f"1. Current average target: {recent_eff['target_pct'].mean():.3f}%")
print(f"2. Average actual move: {recent_eff['actual_move_pct'].mean():.3f}%")
print(f"3. Current win rate: {(recent_eff['result'] == 'WIN').sum() / len(recent_eff) * 100:.1f}%")

if optimal['win_rate'] >= 80:
    print(f"\n✅ SOLUTION FOUND:")
    print(f"   Reduce targets to {optimal['multiplier']:.1f}x current size")
    print(f"   Expected win rate: {optimal['win_rate']:.1f}%")
    print(f"   This achieves the 80% target!")
else:
    print(f"\n⚠️ PARTIAL SOLUTION:")
    print(f"   Reducing targets to {optimal['multiplier']:.1f}x improves win rate to {optimal['win_rate']:.1f}%")
    print(f"   Still {80 - optimal['win_rate']:.1f}pp short of 80% target")
    print(f"   Additional optimizations needed:")
    print(f"   - Improve signal quality (better indicators)")
    print(f"   - Suspend underperforming symbols")
    print(f"   - Adjust durations")

print("\n" + "="*80)
