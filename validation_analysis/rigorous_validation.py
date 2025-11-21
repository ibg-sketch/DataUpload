"""
Rigorous Validation Framework
Addresses Architect Feedback:
1. Fix selection bias (no peeking at holdout)
2. Add PnL/EV simulation with realistic costs
3. Walk-forward cross-validation
4. Wilson confidence intervals
5. Stress testing with 2-3x fees/slippage
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("RIGOROUS VALIDATION FRAMEWORK")
print("="*80)

# Load unified dataset
print("\nLoading unified dataset...")
df = pd.read_csv('unified_dataset.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"Total samples: {len(df)}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"Win rate baseline: {df['outcome'].mean():.1%}")

# ============================================================================
# EXECUTION COST MODEL
# ============================================================================

def calculate_execution_costs(target_pct, stress_multiplier=1.0):
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
    Conservative: 0.15% (with partial fills, volatility spikes)
    
    stress_multiplier allows 2-3x testing
    """
    base_fees = 0.07  # 0.07% round-trip (0.035% per side)
    base_slippage = 0.04  # 0.04% round-trip
    
    total_cost_pct = (base_fees + base_slippage) * stress_multiplier
    
    return total_cost_pct

def calculate_pnl_after_costs(row, target_pct, stress_multiplier=1.0):
    """
    Calculate PnL for a trade after execution costs
    
    Returns:
        pnl_pct: Net profit/loss percentage after all costs
        gross_pnl_pct: Gross profit/loss before costs (for comparison)
    """
    execution_cost = calculate_execution_costs(target_pct, stress_multiplier)
    
    if row['outcome'] == 1:  # WIN
        # Hit target, gross profit = target_pct
        gross_pnl = target_pct
    else:  # LOSS
        # Calculate how much price moved against us
        if row['verdict'] == 'BUY':
            # BUY signal: loss if price went down
            # worst case = lowest_reached
            gross_pnl = ((row['lowest_reached'] - row['entry_price']) / row['entry_price']) * 100
        else:  # SELL
            # SELL signal: loss if price went up
            # worst case = highest_reached (negative for sell)
            gross_pnl = ((row['entry_price'] - row['highest_reached']) / row['entry_price']) * 100
    
    # Net PnL after costs
    net_pnl = gross_pnl - execution_cost
    
    return net_pnl, gross_pnl

# ============================================================================
# WILSON CONFIDENCE INTERVALS
# ============================================================================

def wilson_score_interval(wins, total, confidence=0.95):
    """
    Wilson score confidence interval for binomial proportion
    More accurate than normal approximation for small samples
    
    Returns: (lower_bound, upper_bound, point_estimate)
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
# POLICY EVALUATOR
# ============================================================================

def evaluate_policy_with_costs(df_subset, params, stress_multiplier=1.0):
    """
    Evaluate a policy on a dataset with execution costs
    
    Returns dict with:
    - win_rate: Percentage of winning trades
    - avg_pnl_pct: Average net PnL per trade (%)
    - expected_value: Expected value per trade (%)
    - sharpe_estimate: PnL Sharpe ratio estimate
    - total_pnl_pct: Cumulative PnL (%)
    - gross_win_rate: Win rate before costs
    """
    # Filter trades based on policy params
    filtered = df_subset.copy()
    
    # Apply thresholds
    if 'min_score_pct' in params:
        filtered = filtered[filtered['score_pct'] >= params['min_score_pct']]
    if 'min_confidence' in params:
        filtered = filtered[filtered['confidence'] >= params['min_confidence']]
    
    # Apply target size filter if specified
    if 'min_target' in params:
        filtered = filtered[filtered['target_pct'] >= params['min_target']]
    if 'max_target' in params:
        filtered = filtered[filtered['target_pct'] <= params['max_target']]
    
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
    
    # Calculate PnL for each trade
    pnls = []
    gross_pnls = []
    
    for _, row in filtered.iterrows():
        net_pnl, gross_pnl = calculate_pnl_after_costs(
            row, 
            row['target_pct'],
            stress_multiplier
        )
        pnls.append(net_pnl)
        gross_pnls.append(gross_pnl)
    
    pnls = np.array(pnls)
    gross_pnls = np.array(gross_pnls)
    
    # Metrics
    wins = np.sum(pnls > 0)
    total = len(pnls)
    
    win_rate = wins / total
    gross_win_rate = filtered['outcome'].mean()
    avg_pnl = np.mean(pnls)
    std_pnl = np.std(pnls)
    sharpe = (avg_pnl / std_pnl) if std_pnl > 0 else 0.0
    total_pnl = np.sum(pnls)
    
    # Wilson confidence interval
    ci_lower, ci_upper, _ = wilson_score_interval(wins, total, confidence=0.95)
    
    return {
        'n_trades': total,
        'win_rate': win_rate,
        'avg_pnl_pct': avg_pnl,
        'expected_value': avg_pnl,  # Same as avg PnL
        'sharpe_estimate': sharpe,
        'total_pnl_pct': total_pnl,
        'gross_win_rate': gross_win_rate,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'std_pnl': std_pnl
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
            'train_dates': (train_df['timestamp'].min(), train_df['timestamp'].max()),
            'val_dates': (val_df['timestamp'].min(), val_df['timestamp'].max())
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
    print(f"Stress multiplier: {stress_multiplier}x (execution costs)")
    
    # Define search grid
    min_score_pcts = [50, 60, 70, 75, 80, 85]
    min_confidences = [0.60, 0.70, 0.75, 0.80]
    min_targets = [0.3, 0.5, 0.8]
    max_targets = [1.5, 2.0, 3.0]
    
    results = []
    
    for min_score in min_score_pcts:
        for min_conf in min_confidences:
            for min_tgt in min_targets:
                for max_tgt in max_targets:
                    if min_tgt >= max_tgt:
                        continue
                    
                    params = {
                        'min_score_pct': min_score,
                        'min_confidence': min_conf,
                        'min_target': min_tgt,
                        'max_target': max_tgt
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
    print(f"  Best EV: {results_df.iloc[0]['expected_value']:.3f}%")
    print(f"  Best WR: {results_df['win_rate'].max():.1%}")
    
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
print(f"  Dates: {train_df['timestamp'].min()} to {train_df['timestamp'].max()}")
print(f"  Win rate: {train_df['outcome'].mean():.1%}")

print(f"\nHoldout set: {len(holdout_df)} samples")
print(f"  Dates: {holdout_df['timestamp'].min()} to {holdout_df['timestamp'].max()}")
print(f"  Win rate: {holdout_df['outcome'].mean():.1%}")

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
    print(f"\n  Validating top 5 policies on CV folds...")
    
    cv_results = []
    
    for idx in range(min(5, len(policies))):
        policy = policies.iloc[idx]
        params = {
            'min_score_pct': policy['min_score_pct'],
            'min_confidence': policy['min_confidence'],
            'min_target': policy['min_target'],
            'max_target': policy['max_target']
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
            
            cv_results.append({
                **params,
                'cv_win_rate': avg_wr,
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
        print(f"    min_score: {best_policy['min_score_pct']}%")
        print(f"    min_confidence: {best_policy['min_confidence']:.2f}")
        print(f"    target_range: {best_policy['min_target']:.2f}%-{best_policy['max_target']:.2f}%")
        print(f"    CV Win Rate: {best_policy['cv_win_rate']:.1%}")
        print(f"    CV Expected Value: {best_policy['cv_expected_value']:.3f}%")
        print(f"    Train Win Rate: {best_policy['train_win_rate']:.1%}")
        print(f"    Train EV: {best_policy['train_ev']:.3f}%")

# ============================================================================
print("\n" + "="*80)
print("STEP 4: HOLDOUT EVALUATION (NO PEEKING!)")
print("="*80)

print("\nEvaluating best policies on unseen holdout set...")

holdout_results = []

for stress_name, best_policy in best_policies_by_stress.items():
    params = {
        'min_score_pct': best_policy['min_score_pct'],
        'min_confidence': best_policy['min_confidence'],
        'min_target': best_policy['min_target'],
        'max_target': best_policy['max_target']
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
    print(f"  min_score_pct: {result['min_score_pct']}%")
    print(f"  min_confidence: {result['min_confidence']:.2f}")
    print(f"  target_range: {result['min_target']:.2f}%-{result['max_target']:.2f}%")
    
    print(f"\nCV Performance (Training):")
    print(f"  Win Rate: {result['cv_win_rate']:.1%}")
    print(f"  Expected Value: {result['cv_expected_value']:.3f}%")
    
    print(f"\nHoldout Performance (Unseen):")
    print(f"  Trades: {result['n_trades']}")
    print(f"  Win Rate: {result['win_rate']:.1%} (95% CI: {result['ci_lower']:.1%}-{result['ci_upper']:.1%})")
    print(f"  Gross Win Rate: {result['gross_win_rate']:.1%} (before costs)")
    print(f"  Avg PnL: {result['avg_pnl_pct']:.3f}%")
    print(f"  Expected Value: {result['expected_value']:.3f}%")
    print(f"  Sharpe Estimate: {result['sharpe_estimate']:.2f}")
    print(f"  Total PnL: {result['total_pnl_pct']:.2f}%")
    
    # Economic viability check
    execution_cost = calculate_execution_costs(1.0, result['stress_multiplier'])
    viable = result['expected_value'] > 0
    
    print(f"\nEconomic Viability:")
    print(f"  Execution Cost: {execution_cost:.2f}%")
    print(f"  Break-even: {'✅ PROFITABLE' if viable else '❌ NOT VIABLE'}")

# Save results
results_df = pd.DataFrame(holdout_results)
results_df.to_csv('rigorous_validation_results.csv', index=False)

print(f"\n✅ Results saved to rigorous_validation_results.csv")

# ============================================================================
print("\n" + "="*80)
print("SUMMARY & RECOMMENDATIONS")
print("="*80)

# Find best viable policy
viable_policies = results_df[results_df['expected_value'] > 0]

if len(viable_policies) > 0:
    best = viable_policies.iloc[0]
    print(f"\n✅ BEST VIABLE POLICY ({best['stress_scenario']} scenario):")
    print(f"   Expected Value: {best['expected_value']:.3f}%")
    print(f"   Win Rate: {best['win_rate']:.1%} (CI: {best['ci_lower']:.1%}-{best['ci_upper']:.1%})")
    print(f"   Avg PnL/trade: {best['avg_pnl_pct']:.3f}%")
    print(f"\n   Implementation ready: YES")
else:
    print(f"\n⚠️ NO ECONOMICALLY VIABLE POLICIES FOUND")
    print(f"   All policies have negative expected value after costs")
    print(f"   Recommendation: Collect more data or revise strategy")

print("\n" + "="*80)
