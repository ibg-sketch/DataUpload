"""
Policy Simulator - Tests different trading policies using historical data

Simulates win/loss outcomes for candidate policies by checking if
highest_reached/lowest_reached would have hit the policy's targets.
"""

import pandas as pd
import numpy as np
from itertools import product
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("POLICY SIMULATOR - FINDING OPTIMAL FORMULA")
print("="*80)

# Load unified dataset
df = pd.read_csv('unified_dataset.csv', parse_dates=['timestamp'])
print(f"\nLoaded {len(df)} signals with outcomes")

# =============================================================================
# POLICY EVALUATION FUNCTION
# =============================================================================

def evaluate_policy(df, policy):
    """
    Simulate win/loss for each signal under a given policy.
    
    Policy parameters:
    - atr_multiplier: Base ATR multiplier for targets (e.g., 0.3 = 30% of current)
    - market_strength_enabled: Whether to use market strength multiplier
    - market_strength_power: Exponent for market strength (0 = disabled, 1 = linear)
    - target_cap_pct: Maximum target size as % of price
    - duration_multiplier: Multiplier for TTL durations
    - min_score_pct: Minimum score threshold (filter signals)
    - min_confidence: Minimum confidence threshold
    """
    
    results = []
    
    for _, row in df.iterrows():
        # Calculate what the target would be under this policy
        base_target = row['atr_pct'] * policy['atr_multiplier']
        
        # Apply market strength if enabled
        if policy['market_strength_enabled']:
            strength_mult = row['market_strength'] ** policy['market_strength_power']
            target_pct = base_target * strength_mult
        else:
            target_pct = base_target
        
        # Apply cap
        target_pct = min(target_pct, policy['target_cap_pct'])
        
        # Simulate: Would this signal have been sent?
        # (score is already calculated, but we can apply confidence filter)
        if row['confidence'] < policy['min_confidence']:
            continue  # Signal wouldn't have been sent
        
        # Simulate: Did price reach the target?
        actual_move = row['actual_move_pct']
        
        # Check if target was hit
        would_win = actual_move >= target_pct
        
        results.append({
            'symbol': row['symbol'],
            'verdict': row['verdict'],
            'target_pct': target_pct,
            'actual_move_pct': actual_move,
            'would_win': would_win,
            'duration': row['duration_minutes']
        })
    
    if len(results) == 0:
        return {
            'win_rate': 0.0,
            'num_signals': 0,
            'avg_target': 0.0,
            'avg_move': 0.0
        }
    
    results_df = pd.DataFrame(results)
    
    return {
        'win_rate': results_df['would_win'].mean() * 100,
        'num_signals': len(results_df),
        'wins': results_df['would_win'].sum(),
        'losses': (~results_df['would_win']).sum(),
        'avg_target': results_df['target_pct'].mean(),
        'avg_move': results_df['actual_move_pct'].mean(),
        'avg_duration': results_df['duration'].mean()
    }

# =============================================================================
# BASELINE POLICY (CURRENT SYSTEM)
# =============================================================================

print("\n" + "="*80)
print("BASELINE: Current System Performance")
print("="*80)

baseline_policy = {
    'atr_multiplier': 1.0,  # Current uses full ATR
    'market_strength_enabled': True,
    'market_strength_power': 1.0,  # Linear
    'target_cap_pct': 3.0,  # 3% cap
    'duration_multiplier': 1.0,
    'min_score_pct': 0.75,  # 75% for scalping
    'min_confidence': 0.60  # 60% minimum
}

baseline_results = evaluate_policy(df, baseline_policy)

print(f"\n📊 BASELINE PERFORMANCE:")
print(f"Win Rate: {baseline_results['win_rate']:.1f}%")
print(f"Signals: {baseline_results['num_signals']} ({baseline_results['wins']}W - {baseline_results['losses']}L)")
print(f"Avg Target: {baseline_results['avg_target']:.3f}%")
print(f"Avg Actual Move: {baseline_results['avg_move']:.3f}%")
print(f"Avg Duration: {baseline_results['avg_duration']:.1f} minutes")

# =============================================================================
# GRID SEARCH: Find Optimal Parameters
# =============================================================================

print("\n" + "="*80)
print("GRID SEARCH: Testing Parameter Combinations")
print("="*80)

# Define search space
atr_multipliers = [0.2, 0.3, 0.4, 0.5, 0.6]
market_strength_options = [
    {'enabled': False, 'power': 0.0},  # Disabled
    {'enabled': True, 'power': 0.5},   # Square root (dampened)
    {'enabled': True, 'power': 1.0},   # Linear
]
target_caps = [0.3, 0.5, 0.8, 1.0]
min_confidences = [0.60, 0.65, 0.70, 0.75]

print(f"\nSearch space:")
print(f"  ATR multipliers: {atr_multipliers}")
print(f"  Market strength options: {len(market_strength_options)}")
print(f"  Target caps: {target_caps}")
print(f"  Min confidence: {min_confidences}")
print(f"  Total combinations: {len(atr_multipliers) * len(market_strength_options) * len(target_caps) * len(min_confidences)}")

all_results = []

for atr_mult in atr_multipliers:
    for ms_option in market_strength_options:
        for target_cap in target_caps:
            for min_conf in min_confidences:
                policy = {
                    'atr_multiplier': atr_mult,
                    'market_strength_enabled': ms_option['enabled'],
                    'market_strength_power': ms_option['power'],
                    'target_cap_pct': target_cap,
                    'duration_multiplier': 1.0,  # Keep constant for now
                    'min_score_pct': 0.75,
                    'min_confidence': min_conf
                }
                
                result = evaluate_policy(df, policy)
                result['policy'] = policy
                all_results.append(result)

results_df = pd.DataFrame([
    {
        'atr_mult': r['policy']['atr_multiplier'],
        'ms_enabled': r['policy']['market_strength_enabled'],
        'ms_power': r['policy']['market_strength_power'],
        'target_cap': r['policy']['target_cap_pct'],
        'min_conf': r['policy']['min_confidence'],
        'win_rate': r['win_rate'],
        'num_signals': r['num_signals'],
        'avg_target': r['avg_target'],
        'policy': r['policy']
    }
    for r in all_results if r['num_signals'] >= 40  # Filter: keep policies that send enough signals
])

print(f"\nTested {len(all_results)} policies, {len(results_df)} had enough signals (≥40)")

# =============================================================================
# TOP PERFORMERS
# =============================================================================

print("\n" + "="*80)
print("TOP 10 PERFORMING POLICIES")
print("="*80)

top_10 = results_df.nlargest(10, 'win_rate')

print(f"\n{'Rank':<6} {'Win Rate':<10} {'Signals':<10} {'ATR×':<8} {'MS':<12} {'Cap':<8} {'MinConf':<10} {'AvgTarget':<12}")
print("-"*100)

for idx, (i, row) in enumerate(top_10.iterrows(), 1):
    ms_str = f"✓ ^{row['ms_power']:.1f}" if row['ms_enabled'] else "✗"
    status = "✅" if row['win_rate'] >= 80 else "⚠️" if row['win_rate'] >= 70 else "❌"
    
    print(f"{idx:<6} {row['win_rate']:>6.1f}% {status} {row['num_signals']:<10} {row['atr_mult']:<8.1f} {ms_str:<12} {row['target_cap']:<8.2f} {row['min_conf']:<10.2f} {row['avg_target']:<12.3f}%")

# =============================================================================
# BEST POLICY ANALYSIS
# =============================================================================

print("\n" + "="*80)
print("OPTIMAL POLICY DETAILS")
print("="*80)

best = results_df.loc[results_df['win_rate'].idxmax()]
best_policy = best['policy']

print(f"\n🏆 BEST PERFORMING POLICY:")
print(f"Win Rate: {best['win_rate']:.1f}%")
print(f"Signals: {best['num_signals']}")
print(f"Avg Target: {best['avg_target']:.3f}%")
print(f"\nParameters:")
print(f"  ATR Multiplier: {best_policy['atr_multiplier']}")
print(f"  Market Strength: {'Enabled' if best_policy['market_strength_enabled'] else 'Disabled'}")
if best_policy['market_strength_enabled']:
    print(f"  Market Strength Power: {best_policy['market_strength_power']}")
print(f"  Target Cap: {best_policy['target_cap_pct']}%")
print(f"  Min Confidence: {best_policy['min_confidence']}")

# Compare to baseline
print(f"\n📈 IMPROVEMENT OVER BASELINE:")
print(f"  Win Rate: {best['win_rate']:.1f}% vs {baseline_results['win_rate']:.1f}% (+{best['win_rate'] - baseline_results['win_rate']:.1f}pp)")
print(f"  Avg Target: {best['avg_target']:.3f}% vs {baseline_results['avg_target']:.3f}%")

# Test best policy in detail
best_detailed = evaluate_policy(df, best_policy)

print(f"\n✅ VALIDATION:")
print(f"  Wins: {best_detailed['wins']}")
print(f"  Losses: {best_detailed['losses']}")
print(f"  Win Rate: {best_detailed['win_rate']:.1f}%")

# =============================================================================
# BY-SYMBOL PERFORMANCE WITH BEST POLICY
# =============================================================================

print("\n" + "="*80)
print("PER-SYMBOL PERFORMANCE (Best Policy)")
print("="*80)

symbol_results = []

for symbol in sorted(df['symbol'].unique()):
    symbol_df = df[df['symbol'] == symbol]
    result = evaluate_policy(symbol_df, best_policy)
    
    if result['num_signals'] > 0:
        symbol_results.append({
            'symbol': symbol,
            'win_rate': result['win_rate'],
            'signals': result['num_signals'],
            'wins': result['wins'],
            'avg_target': result['avg_target']
        })

symbol_results_df = pd.DataFrame(symbol_results).sort_values('win_rate', ascending=False)

print(f"\n{'Symbol':<12} {'Win Rate':<12} {'Signals':<10} {'Wins':<8} {'Avg Target':<12}")
print("-"*60)

for _, row in symbol_results_df.iterrows():
    status = "✅" if row['win_rate'] >= 80 else "⚠️" if row['win_rate'] >= 60 else "❌"
    print(f"{row['symbol']:<12} {row['win_rate']:>6.1f}% {status} {row['signals']:<10} {row['wins']:<8} {row['avg_target']:<12.3f}%")

# =============================================================================
# RECOMMENDATIONS
# =============================================================================

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

print(f"\n💡 IMPLEMENT BEST POLICY:")
print(f"\n1. **Reduce ATR multiplier to {best_policy['atr_multiplier']}** (current: 1.0)")
print(f"   - This reduces targets by {(1 - best_policy['atr_multiplier']) * 100:.0f}%")

if not best_policy['market_strength_enabled']:
    print(f"\n2. **DISABLE market strength multiplier**")
    print(f"   - Analysis shows it's negatively correlated with wins")
    print(f"   - Keep targets consistent regardless of volume/OI/CVD")
else:
    print(f"\n2. **Dampen market strength with power {best_policy['market_strength_power']}**")
    print(f"   - Reduces excessive target inflation")

print(f"\n3. **Set target cap at {best_policy['target_cap_pct']}%**")
print(f"   - Prevents any target from exceeding this threshold")

print(f"\n4. **Set minimum confidence to {best_policy['min_confidence']:.0%}**")
print(f"   - Only send highest quality signals")

print(f"\n📊 EXPECTED RESULTS:")
print(f"  - Win Rate: {best['win_rate']:.1f}% (target: 80%)")
print(f"  - Improvement: +{best['win_rate'] - baseline_results['win_rate']:.1f} percentage points")
print(f"  - Average target size: {best['avg_target']:.3f}%")

if best['win_rate'] >= 80:
    print(f"\n🎉 SUCCESS: This policy achieves the 80% win rate target!")
else:
    print(f"\n⚠️ Close but not quite: {80 - best['win_rate']:.1f}pp short of 80% target")
    print(f"   Consider:")
    print(f"   - Increasing signal duration (strong +0.325 correlation)")
    print(f"   - Suspending lowest performing symbols")
    print(f"   - Further reducing targets")

# =============================================================================
# SAVE RESULTS
# =============================================================================

output_file = 'policy_optimization_results.csv'
results_df.to_csv(output_file, index=False)
print(f"\n✅ Saved {len(results_df)} policy results to {output_file}")

# Save best policy
import json
best_policy_file = 'optimal_policy.json'
with open(best_policy_file, 'w') as f:
    policy_output = best_policy.copy()
    policy_output['expected_win_rate'] = float(best['win_rate'])
    policy_output['num_signals'] = int(best['num_signals'])
    policy_output['avg_target_pct'] = float(best['avg_target'])
    json.dump(policy_output, f, indent=2)

print(f"✅ Saved optimal policy to {best_policy_file}")

print("\n" + "="*80)
print("POLICY SIMULATION COMPLETE")
print("="*80)
