"""
Rigorous Validation Framework v3
FIXES critical bugs identified by architect:
1. Direction-aware target_pct (always positive, uses near edge)
2. Realized PnL from final_price (not extremes)
3. Proper handling of BUY vs SELL signals

Uses effectiveness_log.csv (397 completed signals with full price data)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("RIGOROUS VALIDATION FRAMEWORK V3 (BUG FIXES)")
print("="*80)

# Load effectiveness log (completed signals with outcomes)
print("\nLoading effectiveness_log.csv...")
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df = df.sort_values('timestamp_sent').reset_index(drop=True)

# Create outcome column (1=WIN, 0=LOSS)
df['outcome'] = (df['result'] == 'WIN').astype(int)

# ============================================================================
# FIX #1: Direction-aware target_pct (always positive, uses near edge)
# ============================================================================

def calculate_target_pct(row):
    """
    Calculate profit target as positive percentage
    Uses NEAR edge (first take-profit level):
    - BUY: target_min (lower bound)
    - SELL: target_max (upper bound, becomes lower after inversion)
    """
    if row['verdict'] == 'BUY':
        # BUY signals profit when price goes UP to target_min
        target_pct = ((row['target_min'] - row['entry_price']) / row['entry_price']) * 100
    else:  # SELL
        # SELL signals profit when price goes DOWN to target_max
        target_pct = ((row['entry_price'] - row['target_max']) / row['entry_price']) * 100
    
    return target_pct

df['target_pct'] = df.apply(calculate_target_pct, axis=1)

# Sanity check
assert (df['target_pct'] > 0).all(), "All target_pct should be positive!"

print(f"\nTotal samples: {len(df)}")
print(f"Date range: {df['timestamp_sent'].min()} to {df['timestamp_sent'].max()}")
print(f"Days covered: {(df['timestamp_sent'].max() - df['timestamp_sent'].min()).days}")
print(f"Win rate baseline: {df['outcome'].mean():.1%}")
print(f"Symbols: {df['symbol'].nunique()} ({', '.join(sorted(df['symbol'].unique()))})")
print(f"Average target: {df['target_pct'].mean():.3f}% (should be positive!)")
print(f"Target range: {df['target_pct'].min():.3f}% to {df['target_pct'].max():.3f}%")

# ============================================================================
# EXECUTION COST MODEL
# ============================================================================

def calculate_execution_costs(stress_multiplier=1.0):
    """
    Realistic execution costs for crypto futures
    
    Fees (typical):
    - Maker: 0.02% (limit orders)
    - Taker: 0.05% (market orders)
    - Average: ~0.035% per side = 0.07% round-trip
    
    Slippage (typical):
    - Low volatility: 0.01-0.02%
    - High volatility: 0.03-0.05%
    - Average: ~0.02% per side = 0.04% round-trip
    
    Total typical: 0.11% round-trip
    Conservative: 0.15-0.22% (with partial fills, volatility spikes)
    
    stress_multiplier allows 2-3x testing
    """
    base_fees = 0.07  # 0.07% round-trip
    base_slippage = 0.04  # 0.04% round-trip
    
    total_cost_pct = (base_fees + base_slippage) * stress_multiplier
    
    return total_cost_pct

# ============================================================================
# FIX #2: Calculate realized PnL from final_price (not extremes)
# ============================================================================

def calculate_realized_pnl(row):
    """
    Calculate REALIZED gross PnL from actual exit (final_price)
    NOT worst-case extremes (highest/lowest_reached)
    
    Returns:
        gross_pnl_pct: Actual realized profit/loss before costs
    """
    if row['verdict'] == 'BUY':
        # BUY: profit if final > entry
        gross_pnl_pct = ((row['final_price'] - row['entry_price']) / row['entry_price']) * 100
    else:  # SELL
        # SELL: profit if entry > final
        gross_pnl_pct = ((row['entry_price'] - row['final_price']) / row['entry_price']) * 100
    
    return gross_pnl_pct

df['gross_pnl_pct'] = df.apply(calculate_realized_pnl, axis=1)

# Verify against profit_pct column if available
if 'profit_pct' in df.columns:
    correlation = df['gross_pnl_pct'].corr(df['profit_pct'])
    print(f"Gross PnL vs profit_pct correlation: {correlation:.3f} (should be ~1.0)")

# ============================================================================
# WILSON CONFIDENCE INTERVALS
# ============================================================================

def wilson_score_interval(wins, total, confidence=0.95):
    """
    Wilson score confidence interval for binomial proportion
    More accurate than normal approximation for small samples
    """
    if total == 0:
        return 0.0, 0.0, 0.0
    
    p = wins / total
    z = stats.norm.ppf((1 + confidence) / 2)
    
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator
    
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    
    return lower, upper, p

# ============================================================================
# POLICY EVALUATOR WITH FIXED PNL CALCULATION
# ============================================================================

def evaluate_policy_with_costs(df_subset, params, stress_multiplier=1.0):
    """
    Evaluate a policy on a dataset with execution costs
    Uses REALIZED PnL (not worst-case extremes)
    """
    # Filter trades based on policy params
    filtered = df_subset.copy()
    
    # Apply thresholds
    if 'min_confidence' in params:
        filtered = filtered[filtered['confidence'] >= params['min_confidence']]
    
    # Apply target size filter (now using positive target_pct)
    if 'min_target' in params:
        filtered = filtered[filtered['target_pct'] >= params['min_target']]
    if 'max_target' in params:
        filtered = filtered[filtered['target_pct'] <= params['max_target']]
    
    # Apply duration filter
    if 'min_duration' in params:
        filtered = filtered[filtered['duration_minutes'] >= params['min_duration']]
    if 'max_duration' in params:
        filtered = filtered[filtered['duration_minutes'] <= params['max_duration']]
    
    if len(filtered) == 0:
        return {
            'n_trades': 0,
            'win_rate': 0.0,
            'avg_pnl_pct': 0.0,
            'expected_value': 0.0,
            'sharpe_estimate': 0.0,
            'total_pnl_pct': 0.0,
            'gross_win_rate': 0.0,
            'ci_lower': 0.0,
            'ci_upper': 0.0
        }
    
    # Calculate net PnL for each trade (gross - costs)
    execution_cost = calculate_execution_costs(stress_multiplier)
    net_pnls = filtered['gross_pnl_pct'] - execution_cost
    
    # Metrics
    wins_net = np.sum(net_pnls > 0)
    total = len(net_pnls)
    
    win_rate_net = wins_net / total
    gross_win_rate = filtered['outcome'].mean()
    avg_pnl = np.mean(net_pnls)
    std_pnl = np.std(net_pnls) if len(net_pnls) > 1 else 0.0
    sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0.0
    total_pnl = np.sum(net_pnls)
    
    # Wilson confidence interval
    ci_lower, ci_upper, _ = wilson_score_interval(wins_net, total, confidence=0.95)
    
    return {
        'n_trades': total,
        'win_rate': win_rate_net,
        'avg_pnl_pct': avg_pnl,
        'expected_value': avg_pnl,
        'sharpe_estimate': sharpe,
        'total_pnl_pct': total_pnl,
        'gross_win_rate': gross_win_rate,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'std_pnl': std_pnl,
        'avg_gross_pnl': np.mean(filtered['gross_pnl_pct'])
    }

# ============================================================================
# WALK-FORWARD CROSS-VALIDATION
# ============================================================================

def walk_forward_cv(df, n_splits=3):
    """
    Time-series aware cross-validation
    Each fold uses past data for training, future for validation
    NO LOOKAHEAD
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    folds = []
    for train_idx, val_idx in tscv.split(df):
        train_df = df.iloc[train_idx].copy()
        val_df = df.iloc[val_idx].copy()
        
        folds.append({
            'train': train_df,
            'val': val_df,
            'train_dates': (train_df['timestamp_sent'].min(), train_df['timestamp_sent'].max()),
            'val_dates': (val_df['timestamp_sent'].min(), val_df['timestamp_sent'].max())
        })
    
    return folds

# ============================================================================
# PARAMETER SEARCH
# ============================================================================

def grid_search_policies(df_train, stress_multiplier=1.0):
    """
    Search parameter space using ONLY training data
    Returns top N policies ranked by expected value
    """
    
    print(f"\nGrid searching policies on training data...")
    print(f"Stress multiplier: {stress_multiplier}x (execution costs = {calculate_execution_costs(stress_multiplier):.2f}%)")
    
    # Define search grid
    min_confidences = [0.60, 0.70, 0.75, 0.80, 0.85, 0.90]
    min_targets = [0.0, 0.3, 0.5, 0.8]
    max_targets = [1.5, 2.0, 3.0, 5.0]
    min_durations = [0, 30, 60]
    max_durations = [120, 240, 360]
    
    results = []
    
    for min_conf in min_confidences:
        for min_tgt in min_targets:
            for max_tgt in max_targets:
                for min_dur in min_durations:
                    for max_dur in max_durations:
                        if min_tgt >= max_tgt:
                            continue
                        if min_dur >= max_dur:
                            continue
                        
                        params = {
                            'min_confidence': min_conf,
                            'min_target': min_tgt,
                            'max_target': max_tgt,
                            'min_duration': min_dur,
                            'max_duration': max_dur
                        }
                        
                        metrics = evaluate_policy_with_costs(
                            df_train, 
                            params, 
                            stress_multiplier
                        )
                        
                        if metrics['n_trades'] >= 10:  # Minimum sample size
                            results.append({
                                **params,
                                **metrics
                            })
    
    # Convert to DataFrame and sort by expected value
    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
        print("  No policies met minimum trade count (10)")
        return results_df
    
    results_df = results_df.sort_values('expected_value', ascending=False)
    
    print(f"  Found {len(results_df)} viable policies")
    print(f"  Best EV: {results_df.iloc[0]['expected_value']:+.3f}%")
    print(f"  Best WR (net): {results_df['win_rate'].max():.1%}")
    print(f"  Best WR (gross): {results_df['gross_win_rate'].max():.1%}")
    
    return results_df

# ============================================================================
# MAIN VALIDATION PIPELINE
# ============================================================================

print("\n" + "="*80)
print("STEP 1: TRAIN/HOLDOUT SPLIT (70/30, TIME-AWARE)")
print("="*80)

# Split by time (no shuffling!)
split_idx = int(len(df) * 0.7)
train_df = df.iloc[:split_idx].copy()
holdout_df = df.iloc[split_idx:].copy()

print(f"\nTrain set: {len(train_df)} samples")
print(f"  Dates: {train_df['timestamp_sent'].min()} to {train_df['timestamp_sent'].max()}")
print(f"  Win rate: {train_df['outcome'].mean():.1%}")
print(f"  Avg target: {train_df['target_pct'].mean():.3f}%")
print(f"  Avg gross PnL: {train_df['gross_pnl_pct'].mean():+.3f}%")

print(f"\nHoldout set: {len(holdout_df)} samples")
print(f"  Dates: {holdout_df['timestamp_sent'].min()} to {holdout_df['timestamp_sent'].max()}")
print(f"  Win rate: {holdout_df['outcome'].mean():.1%}")
print(f"  Avg target: {holdout_df['target_pct'].mean():.3f}%")
print(f"  Avg gross PnL: {holdout_df['gross_pnl_pct'].mean():+.3f}%")

# ============================================================================
print("\n" + "="*80)
print("STEP 2: WALK-FORWARD CV ON TRAINING SET")
print("="*80)

cv_folds = walk_forward_cv(train_df, n_splits=3)

print(f"\nCreated {len(cv_folds)} CV folds:")
for i, fold in enumerate(cv_folds):
    print(f"  Fold {i+1}: Train {len(fold['train'])} samples ({fold['train_dates'][0].date()} to {fold['train_dates'][1].date()})")
    print(f"          Val   {len(fold['val'])} samples ({fold['val_dates'][0].date()} to {fold['val_dates'][1].date()})")

# ============================================================================
print("\n" + "="*80)
print("STEP 3: POLICY SEARCH (TRAINING DATA ONLY)")
print("="*80)

# Search at different stress levels
stress_levels = {
    'normal': 1.0,
    'conservative': 1.5,
    'stress': 2.0
}

best_policies_by_stress = {}

for stress_name, stress_mult in stress_levels.items():
    print(f"\n{'='*80}")
    print(f"STRESS SCENARIO: {stress_name.upper()} ({stress_mult}x execution costs)")
    print(f"{'='*80}")
    
    # Search on full training set
    policies = grid_search_policies(train_df, stress_multiplier=stress_mult)
    
    if len(policies) == 0:
        print(f"  No viable policies for {stress_name} scenario")
        continue
    
    # Validate top policies on CV folds
    print(f"\n  Validating top 10 policies on CV folds...")
    
    cv_results = []
    
    for idx in range(min(10, len(policies))):
        policy = policies.iloc[idx]
        params = {
            'min_confidence': policy['min_confidence'],
            'min_target': policy['min_target'],
            'max_target': policy['max_target'],
            'min_duration': policy['min_duration'],
            'max_duration': policy['max_duration']
        }
        
        fold_metrics = []
        for fold in cv_folds:
            metrics = evaluate_policy_with_costs(
                fold['val'], 
                params, 
                stress_mult
            )
            if metrics['n_trades'] > 0:
                fold_metrics.append(metrics)
        
        if fold_metrics:
            avg_wr = np.mean([m['win_rate'] for m in fold_metrics])
            avg_ev = np.mean([m['expected_value'] for m in fold_metrics])
            avg_trades = np.mean([m['n_trades'] for m in fold_metrics])
            std_wr = np.std([m['win_rate'] for m in fold_metrics])
            
            cv_results.append({
                **params,
                'cv_win_rate': avg_wr,
                'cv_win_rate_std': std_wr,
                'cv_expected_value': avg_ev,
                'cv_avg_trades': avg_trades,
                'train_win_rate': policy['win_rate'],
                'train_ev': policy['expected_value'],
                'train_trades': policy['n_trades']
            })
    
    if cv_results:
        cv_df = pd.DataFrame(cv_results)
        cv_df = cv_df.sort_values('cv_expected_value', ascending=False)
        
        best_policy = cv_df.iloc[0]
        best_policies_by_stress[stress_name] = best_policy
        
        print(f"\n  Best policy for {stress_name}:")
        print(f"    min_confidence: {best_policy['min_confidence']:.2f}")
        print(f"    target_range: {best_policy['min_target']:.2f}%-{best_policy['max_target']:.2f}%")
        print(f"    duration_range: {best_policy['min_duration']:.0f}-{best_policy['max_duration']:.0f} min")
        print(f"    CV Win Rate: {best_policy['cv_win_rate']:.1%} (±{best_policy['cv_win_rate_std']:.1%})")
        print(f"    CV Expected Value: {best_policy['cv_expected_value']:+.3f}%")
        print(f"    Train Win Rate: {best_policy['train_win_rate']:.1%}")
        print(f"    Train EV: {best_policy['train_ev']:+.3f}%")

# ============================================================================
print("\n" + "="*80)
print("STEP 4: HOLDOUT EVALUATION (NO PEEKING!)")
print("="*80)

print("\nEvaluating best policies on unseen holdout set...")

holdout_results = []

for stress_name, best_policy in best_policies_by_stress.items():
    params = {
        'min_confidence': best_policy['min_confidence'],
        'min_target': best_policy['min_target'],
        'max_target': best_policy['max_target'],
        'min_duration': best_policy['min_duration'],
        'max_duration': best_policy['max_duration']
    }
    
    stress_mult = stress_levels[stress_name]
    
    metrics = evaluate_policy_with_costs(
        holdout_df,
        params,
        stress_mult
    )
    
    holdout_results.append({
        'stress_scenario': stress_name,
        'stress_multiplier': stress_mult,
        **params,
        **metrics,
        'cv_win_rate': best_policy['cv_win_rate'],
        'cv_expected_value': best_policy['cv_expected_value']
    })

# ============================================================================
print("\n" + "="*80)
print("FINAL RESULTS")
print("="*80)

for result in holdout_results:
    print(f"\n{'='*80}")
    print(f"SCENARIO: {result['stress_scenario'].upper()} ({result['stress_multiplier']}x costs)")
    print(f"{'='*80}")
    print(f"\nPolicy Parameters:")
    print(f"  min_confidence: {result['min_confidence']:.2f}")
    print(f"  target_range: {result['min_target']:.2f}%-{result['max_target']:.2f}%")
    print(f"  duration_range: {result['min_duration']:.0f}-{result['max_duration']:.0f} min")
    
    print(f"\nCV Performance (Training):")
    print(f"  Win Rate: {result['cv_win_rate']:.1%}")
    print(f"  Expected Value: {result['cv_expected_value']:+.3f}%")
    
    print(f"\nHoldout Performance (Unseen):")
    print(f"  Trades: {result['n_trades']}")
    print(f"  Win Rate (net): {result['win_rate']:.1%} (95% CI: {result['ci_lower']:.1%}-{result['ci_upper']:.1%})")
    print(f"  Win Rate (gross): {result['gross_win_rate']:.1%}")
    print(f"  Avg Gross PnL: {result['avg_gross_pnl']:+.3f}%")
    print(f"  Avg Net PnL: {result['avg_pnl_pct']:+.3f}%")
    print(f"  Expected Value: {result['expected_value']:+.3f}%")
    print(f"  Sharpe Estimate: {result['sharpe_estimate']:.2f}")
    print(f"  Total PnL: {result['total_pnl_pct']:+.2f}%")
    
    # Economic viability check
    execution_cost = calculate_execution_costs(result['stress_multiplier'])
    viable = result['expected_value'] > 0
    
    print(f"\nEconomic Viability:")
    print(f"  Execution Cost: {execution_cost:.2f}%")
    print(f"  Break-even: {'✅ PROFITABLE' if viable else '❌ NOT VIABLE'}")

# Save results
results_df = pd.DataFrame(holdout_results)
results_df.to_csv('rigorous_validation_results_v3.csv', index=False)

print(f"\n✅ Results saved to rigorous_validation_results_v3.csv")

# ============================================================================
print("\n" + "="*80)
print("SUMMARY & RECOMMENDATIONS")
print("="*80)

# Find best viable policy
viable_policies = results_df[results_df['expected_value'] > 0]

if len(viable_policies) > 0:
    best = viable_policies.iloc[0]
    print(f"\n✅ BEST VIABLE POLICY ({best['stress_scenario']} scenario):")
    print(f"   Expected Value: {best['expected_value']:+.3f}%")
    print(f"   Win Rate (net): {best['win_rate']:.1%} (CI: {best['ci_lower']:.1%}-{best['ci_upper']:.1%})")
    print(f"   Avg PnL/trade: {best['avg_pnl_pct']:+.3f}%")
    print(f"   Sharpe: {best['sharpe_estimate']:.2f}")
    print(f"   Trades: {best['n_trades']}")
    print(f"\n   Implementation ready: {'YES' if best['ci_lower'] >= 0.50 else 'MARGINAL (low confidence bound)'}")
else:
    print(f"\n⚠️ NO ECONOMICALLY VIABLE POLICIES FOUND")
    print(f"   All policies have negative expected value after costs")
    print(f"   Recommendation: Collect more data or revise strategy")

print("\n" + "="*80)
