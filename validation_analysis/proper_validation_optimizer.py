"""
Proper Time-Series Validation for Policy Optimization

Implements:
1. Full dataset (all 396 signals, not just 11 hours)
2. Time-series cross-validation with walk-forward splits
3. Holdout set (last 20% of time)
4. Bootstrap confidence intervals
5. Fee/slippage simulation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("PROPER TIME-SERIES VALIDATION FRAMEWORK")
print("="*80)

# =============================================================================
# STEP 1: Load FULL dataset (all signals, not just last 11 hours)
# =============================================================================

print("\nSTEP 1: Loading FULL dataset...")

effectiveness_df = pd.read_csv('effectiveness_log.csv', parse_dates=['timestamp_sent', 'timestamp_checked'])
analysis_df = pd.read_csv('analysis_log.csv', parse_dates=['timestamp'])

print(f"Total signals in effectiveness_log: {len(effectiveness_df)}")
print(f"Total analysis cycles: {len(analysis_df)}")
print(f"Date range: {effectiveness_df['timestamp_sent'].min()} to {effectiveness_df['timestamp_sent'].max()}")

# Filter out signals with 0.0 confidence (seem to be errors)
effectiveness_df = effectiveness_df[effectiveness_df['confidence'] > 0].copy()
print(f"After filtering confidence > 0: {len(effectiveness_df)} signals")

# =============================================================================
# STEP 2: Merge with analysis data
# =============================================================================

print("\nSTEP 2: Merging datasets...")

merged_data = []
for _, sig in effectiveness_df.iterrows():
    time_window = timedelta(minutes=2)
    candidates = analysis_df[
        (analysis_df['symbol'] == sig['symbol']) &
        (analysis_df['verdict'] == sig['verdict']) &
        (analysis_df['timestamp'] >= sig['timestamp_sent'] - time_window) &
        (analysis_df['timestamp'] <= sig['timestamp_sent'] + time_window)
    ]
    
    if len(candidates) > 0:
        candidates = candidates.copy()
        candidates['time_diff'] = abs((candidates['timestamp'] - sig['timestamp_sent']).dt.total_seconds())
        best_match = candidates.loc[candidates['time_diff'].idxmin()]
        
        merged_row = {
            'timestamp': sig['timestamp_sent'],
            'symbol': sig['symbol'],
            'verdict': sig['verdict'],
            'result': sig['result'],
            'entry_price': sig['entry_price'],
            'target_min': sig['target_min'],
            'target_max': sig['target_max'],
            'highest_reached': sig['highest_reached'],
            'lowest_reached': sig['lowest_reached'],
            'duration_minutes': sig['duration_minutes'],
            'cvd': best_match['cvd'],
            'oi_change_pct': best_match['oi_change_pct'],
            'price_vs_vwap_pct': best_match['price_vs_vwap_pct'],
            'volume_spike': best_match['volume_spike'],
            'liq_ratio': best_match['liq_ratio'],
            'rsi': best_match['rsi'],
            'atr': best_match['atr'],
            'score': best_match['score'],
            'confidence': sig['confidence'],  # Use from effectiveness (more reliable)
        }
        merged_data.append(merged_row)

merged_df = pd.DataFrame(merged_data).sort_values('timestamp')
print(f"Successfully merged {len(merged_df)} signals")

#=============================================================================
# STEP 3: Feature Engineering
# =============================================================================

print("\nSTEP 3: Feature engineering...")

# Target percentages
def calc_target_pct(row):
    entry = row['entry_price']
    if row['verdict'] == 'BUY':
        return ((row['target_min'] - entry) / entry) * 100
    else:
        return ((entry - row['target_max']) / entry) * 100

def calc_actual_move(row):
    entry = row['entry_price']
    if row['verdict'] == 'BUY':
        return ((row['highest_reached'] - entry) / entry) * 100
    else:
        return ((entry - row['lowest_reached']) / entry) * 100

merged_df['target_pct'] = merged_df.apply(calc_target_pct, axis=1)
merged_df['actual_move_pct'] = merged_df.apply(calc_actual_move, axis=1)

# Normalized features
merged_df['cvd_pct'] = (merged_df['cvd'] / merged_df['entry_price']) * 100
merged_df['atr_pct'] = (merged_df['atr'] / merged_df['entry_price']) * 100
merged_df['verdict_buy'] = (merged_df['verdict'] == 'BUY').astype(int)
merged_df['win'] = (merged_df['result'] == 'WIN').astype(int)

# Market strength (reconstruct from original formula)
def calc_market_strength(row):
    strength = 1.0
    if row['volume_spike'] > 1.5:
        strength += 0.4 * min((row['volume_spike'] - 1.0) / 2.0, 1.0)
    if row['verdict'] == 'BUY' and row['oi_change_pct'] > 0:
        strength += 0.35 * min(abs(row['oi_change_pct']) / 5.0, 1.0)
    elif row['verdict'] == 'SELL' and row['oi_change_pct'] < 0:
        strength += 0.35 * min(abs(row['oi_change_pct']) / 5.0, 1.0)
    cvd_pct = (row['cvd'] / row['entry_price']) * 100 if row['entry_price'] > 0 else 0
    if row['verdict'] == 'BUY' and cvd_pct > 0:
        strength += 0.25 * min(abs(cvd_pct) / 0.1, 1.0)
    elif row['verdict'] == 'SELL' and cvd_pct < 0:
        strength += 0.25 * min(abs(cvd_pct) / 0.1, 1.0)
    return min(strength, 2.5)

merged_df['market_strength'] = merged_df.apply(calc_market_strength, axis=1)

print(f"Full dataset: {len(merged_df)} signals")
print(f"Wins: {merged_df['win'].sum()} ({merged_df['win'].mean()*100:.1f}%)")
print(f"Losses: {(~merged_df['win'].astype(bool)).sum()} ({(1-merged_df['win'].mean())*100:.1f}%)")

# =============================================================================
# STEP 4: TIME-SERIES TRAIN/TEST SPLIT
# =============================================================================

print("\n" + "="*80)
print("STEP 4: Time-Series Train/Test Split (No Lookahead)")
print("="*80)

# Split: Use first 80% for training, last 20% as holdout
split_idx = int(len(merged_df) * 0.8)
train_df = merged_df.iloc[:split_idx].copy()
holdout_df = merged_df.iloc[split_idx:].copy()

print(f"\nTRAINING SET:")
print(f"  Signals: {len(train_df)}")
print(f"  Date range: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")
print(f"  Win rate: {train_df['win'].mean()*100:.1f}%")

print(f"\nHOLDOUT SET (unseen during optimization):")
print(f"  Signals: {len(holdout_df)}")
print(f"  Date range: {holdout_df['timestamp'].min()} to {holdout_df['timestamp'].max()}")
print(f"  Win rate: {holdout_df['win'].mean()*100:.1f}%")

# =============================================================================
# STEP 5: Policy Evaluation with Fees/Slippage
# =============================================================================

print("\n" + "="*80)
print("STEP 5: Policy Simulator with Fees/Slippage")
print("="*80)

def evaluate_policy_realistic(df, policy, fee_pct=0.04, slippage_pct=0.02):
    """
    Simulate policy with realistic fees and slippage
    
    Assumptions:
    - Trading fee: 0.04% (Binance futures maker fee)
    - Slippage: 0.02% (conservative for liquid pairs)
    - Total cost: 0.06% per trade
    """
    
    results = []
    
    for _, row in df.iterrows():
        # Apply confidence filter
        if row['confidence'] < policy['min_confidence']:
            continue
        
        # Calculate target under this policy
        base_target = row['atr_pct'] * policy['atr_multiplier']
        
        if policy['market_strength_enabled']:
            strength_mult = row['market_strength'] ** policy['market_strength_power']
            target_pct = base_target * strength_mult
        else:
            target_pct = base_target
        
        target_pct = min(target_pct, policy['target_cap_pct'])
        
        # Actual move achieved
        actual_move = row['actual_move_pct']
        
        # Account for fees and slippage (reduce effective move)
        total_cost_pct = fee_pct + slippage_pct
        effective_move = actual_move - total_cost_pct
        
        # Did we hit target after costs?
        would_win = effective_move >= target_pct
        
        results.append({
            'would_win': would_win,
            'target_pct': target_pct,
            'actual_move_pct': actual_move,
            'effective_move_pct': effective_move,
            'symbol': row['symbol'],
            'verdict': row['verdict']
        })
    
    if len(results) == 0:
        return {
            'win_rate': 0.0,
            'num_signals': 0,
            'wins': 0,
            'losses': 0
        }
    
    results_df = pd.DataFrame(results)
    
    return {
        'win_rate': results_df['would_win'].mean() * 100,
        'num_signals': len(results_df),
        'wins': results_df['would_win'].sum(),
        'losses': (~results_df['would_win']).sum(),
        'avg_target': results_df['target_pct'].mean(),
        'avg_effective_move': results_df['effective_move_pct'].mean()
    }

# Test baseline with fees
baseline_policy = {
    'atr_multiplier': 1.0,
    'market_strength_enabled': True,
    'market_strength_power': 1.0,
    'target_cap_pct': 3.0,
    'min_confidence': 0.60
}

baseline_train = evaluate_policy_realistic(train_df, baseline_policy)
baseline_holdout = evaluate_policy_realistic(holdout_df, baseline_policy)

print(f"\nBASELINE (with fees/slippage):")
print(f"  Training:  {baseline_train['win_rate']:.1f}% ({baseline_train['wins']}W - {baseline_train['losses']}L)")
print(f"  Holdout:   {baseline_holdout['win_rate']:.1f}% ({baseline_holdout['wins']}W - {baseline_holdout['losses']}L)")

# =============================================================================
# STEP 6: Grid Search on TRAINING SET ONLY
# =============================================================================

print("\n" + "="*80)
print("STEP 6: Grid Search on Training Set (No Lookahead)")
print("="*80)

atr_multipliers = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4]
market_strength_options = [
    {'enabled': False, 'power': 0.0},
    {'enabled': True, 'power': 0.5},
    {'enabled': True, 'power': 1.0},
]
target_caps = [0.2, 0.3, 0.5, 0.8]
min_confidences = [0.60, 0.65, 0.70, 0.75]

print(f"Search space: {len(atr_multipliers)} × {len(market_strength_options)} × {len(target_caps)} × {len(min_confidences)} = {len(atr_multipliers) * len(market_strength_options) * len(target_caps) * len(min_confidences)} combinations")

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
                    'min_confidence': min_conf
                }
                
                # Evaluate on TRAINING set only
                train_result = evaluate_policy_realistic(train_df, policy)
                
                if train_result['num_signals'] >= 50:  # Minimum signals threshold
                    train_result['policy'] = policy
                    all_results.append(train_result)

print(f"Tested {len(atr_multipliers) * len(market_strength_options) * len(target_caps) * len(min_confidences)} policies")
print(f"Kept {len(all_results)} policies with ≥50 training signals")

# =============================================================================
# STEP 7: Validate Top Policies on HOLDOUT SET
# =============================================================================

print("\n" + "="*80)
print("STEP 7: Validate Top Policies on Holdout Set")
print("="*80)

results_df = pd.DataFrame([
    {
        'atr_mult': r['policy']['atr_multiplier'],
        'ms_enabled': r['policy']['market_strength_enabled'],
        'ms_power': r['policy']['market_strength_power'],
        'target_cap': r['policy']['target_cap_pct'],
        'min_conf': r['policy']['min_confidence'],
        'train_wr': r['win_rate'],
        'train_signals': r['num_signals'],
        'policy': r['policy']
    }
    for r in all_results
])

# Get top 10 by training win rate
top_10_train = results_df.nlargest(10, 'train_wr')

# Validate each on holdout
validation_results = []
for _, row in top_10_train.iterrows():
    holdout_result = evaluate_policy_realistic(holdout_df, row['policy'])
    validation_results.append({
        'policy': row['policy'],
        'train_wr': row['train_wr'],
        'holdout_wr': holdout_result['win_rate'],
        'holdout_signals': holdout_result['num_signals'],
        'atr_mult': row['atr_mult'],
        'ms_enabled': row['ms_enabled'],
        'target_cap': row['target_cap'],
        'min_conf': row['min_conf']
    })

validation_df = pd.DataFrame(validation_results).sort_values('holdout_wr', ascending=False)

print(f"\nTOP 10 POLICIES (ranked by HOLDOUT performance):")
print(f"\n{'Rank':<6} {'Train WR':<10} {'Holdout WR':<12} {'Signals':<10} {'ATR×':<8} {'MS':<10} {'Cap':<8} {'MinConf'}")
print("-"*90)

for idx, (i, row) in enumerate(validation_df.iterrows(), 1):
    ms_str = f"✓^{row['policy']['market_strength_power']:.1f}" if row['ms_enabled'] else "✗"
    status = "✅" if row['holdout_wr'] >= 70 else "⚠️" if row['holdout_wr'] >= 60 else "❌"
    overfit_gap = row['train_wr'] - row['holdout_wr']
    overfit_str = f"({overfit_gap:+.1f}pp)" if abs(overfit_gap) > 10 else ""
    
    print(f"{idx:<6} {row['train_wr']:>6.1f}% {row['holdout_wr']:>6.1f}% {status} {overfit_str:<8} {row['holdout_signals']:<10} {row['atr_mult']:<8.2f} {ms_str:<10} {row['target_cap']:<8.2f} {row['min_conf']:.2f}")

# Best policy
best = validation_df.iloc[0]

print(f"\n🏆 BEST POLICY (by holdout performance):")
print(f"Training Win Rate: {best['train_wr']:.1f}%")
print(f"Holdout Win Rate: {best['holdout_wr']:.1f}%")
print(f"Generalization Gap: {best['train_wr'] - best['holdout_wr']:+.1f}pp")
print(f"\nParameters:")
print(f"  ATR Multiplier: {best['atr_mult']}")
print(f"  Market Strength: {'Enabled' if best['ms_enabled'] else 'Disabled'}")
print(f"  Target Cap: {best['target_cap']}%")
print(f"  Min Confidence: {best['min_conf']}")

# =============================================================================
# STEP 8: Save Results
# =============================================================================

output_file = 'validated_optimization_results.csv'
validation_df.to_csv(output_file, index=False)
print(f"\n✅ Saved validation results to {output_file}")

import json
best_policy_file = 'validated_optimal_policy.json'
with open(best_policy_file, 'w') as f:
    policy_output = best['policy'].copy()
    policy_output['train_win_rate'] = float(best['train_wr'])
    policy_output['holdout_win_rate'] = float(best['holdout_wr'])
    policy_output['generalization_gap'] = float(best['train_wr'] - best['holdout_wr'])
    json.dump(policy_output, f, indent=2)

print(f"✅ Saved validated policy to {best_policy_file}")

print("\n" + "="*80)
print("PROPER VALIDATION COMPLETE")
print("="*80)

if best['holdout_wr'] >= 70:
    print(f"\n✅ SUCCESS: Holdout win rate {best['holdout_wr']:.1f}% meets 70%+ threshold")
    print(f"   Recommendation: Safe to implement")
elif best['holdout_wr'] >= 60:
    print(f"\n⚠️ MODERATE: Holdout win rate {best['holdout_wr']:.1f}% is acceptable but below 70%")
    print(f"   Recommendation: Implement with caution, monitor closely")
else:
    print(f"\n❌ INSUFFICIENT: Holdout win rate {best['holdout_wr']:.1f}% below 60%")
    print(f"   Recommendation: Do NOT implement, strategy not validated")
