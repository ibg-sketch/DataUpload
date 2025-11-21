#!/usr/bin/env python3
"""
Backtest UIF-30: Unified Indicator Features with basis_pct integration
Validates basis_pct predictive power before wiring into scoring system
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.metrics import roc_auc_score
import warnings
warnings.filterwarnings('ignore')

def load_feeds_data():
    """Load feeds_log.csv and extract basis_pct feature"""
    print("\n" + "="*80)
    print("STEP 1: Loading Data Feeds (basis_pct)")
    print("="*80)
    
    # Define expected column names (handle schema evolution)
    # Original 15 columns + basis_pct + basis_provider = 17 columns
    expected_cols = [
        'timestamp', 'symbol', 'oi', 'oi_pct', 'funding', 'basis',
        'liq_long_usd', 'liq_short_usd', 'liq_ratio', 'obi_top',
        'basis_pct', 'basis_provider',  # NEW columns added
        'latency_ms', 'source_errors', 'provider_oi', 'provider_funding', 'provider_basis'
    ]
    
    # Load feeds_log.csv with explicit column names (skip bad lines)
    try:
        feeds_df = pd.read_csv('data/feeds_log.csv', 
                               names=expected_cols,
                               skiprows=1,  # Skip old header
                               parse_dates=['timestamp'],
                               on_bad_lines='skip')  # Skip malformed rows
    except Exception as e:
        print(f"❌ ERROR loading feeds_log.csv: {e}")
        return None
    
    print(f"✅ Loaded {len(feeds_df)} rows from feeds_log.csv")
    
    # Check if basis_pct column exists
    if 'basis_pct' in feeds_df.columns and 'basis_provider' in feeds_df.columns:
        # Filter rows with valid basis_pct
        feeds_df = feeds_df[feeds_df['basis_pct'].notna()].copy()
        print(f"✅ Filtered to {len(feeds_df)} rows with valid basis_pct")
    else:
        print(f"⚠️  WARNING: basis_pct column not found in feeds_log.csv")
        print(f"   Available columns: {', '.join(feeds_df.columns)}")
        return None
    
    # Standardize to minute granularity for merging
    feeds_df['timestamp_minute'] = feeds_df['timestamp'].dt.floor('min')
    
    # Select relevant columns
    feeds_df = feeds_df[['timestamp_minute', 'symbol', 'basis_pct', 'basis_provider', 'oi', 'oi_pct', 'funding']].copy()
    
    print(f"\n📊 Basis_pct statistics:")
    print(f"   Mean:   {feeds_df['basis_pct'].mean():.4f}%")
    print(f"   Median: {feeds_df['basis_pct'].median():.4f}%")
    print(f"   Std:    {feeds_df['basis_pct'].std():.4f}%")
    print(f"   Range:  [{feeds_df['basis_pct'].min():.4f}%, {feeds_df['basis_pct'].max():.4f}%]")
    
    return feeds_df

def load_effectiveness_data():
    """Load effectiveness_log.csv with WIN/LOSS outcomes"""
    print("\n" + "="*80)
    print("STEP 2: Loading Effectiveness Log (WIN/LOSS outcomes)")
    print("="*80)
    
    try:
        eff_df = pd.read_csv('effectiveness_log.csv', parse_dates=['timestamp_sent', 'timestamp_checked'])
    except FileNotFoundError:
        print("⚠️  ERROR: effectiveness_log.csv not found")
        return None
    
    print(f"✅ Loaded {len(eff_df)} signals from effectiveness_log.csv")
    
    # Filter to recent data (last 7 days to match feeds_log availability)
    cutoff = datetime.now() - timedelta(days=7)
    eff_df = eff_df[eff_df['timestamp_sent'] >= cutoff].copy()
    print(f"✅ Filtered to {len(eff_df)} signals from last 7 days")
    
    # Standardize to minute granularity
    eff_df['timestamp_minute'] = eff_df['timestamp_sent'].dt.floor('min')
    
    # Create binary win flag
    eff_df['win'] = (eff_df['result'] == 'WIN').astype(int)
    
    print(f"\n📊 Effectiveness statistics:")
    print(f"   Total signals: {len(eff_df)}")
    print(f"   Wins:  {eff_df['win'].sum()} ({eff_df['win'].mean()*100:.1f}%)")
    print(f"   Losses: {(1-eff_df['win']).sum()} ({(1-eff_df['win'].mean())*100:.1f}%)")
    
    return eff_df

def merge_feeds_with_effectiveness(feeds_df, eff_df):
    """Merge feeds_log basis_pct with effectiveness outcomes"""
    print("\n" + "="*80)
    print("STEP 3: Merging feeds_log with effectiveness_log")
    print("="*80)
    
    merged_data = []
    match_count = 0
    no_match_count = 0
    
    for idx, eff_row in eff_df.iterrows():
        # Find matching feeds_log row within ±2 minutes
        time_window = timedelta(minutes=2)
        candidates = feeds_df[
            (feeds_df['symbol'] == eff_row['symbol']) &
            (feeds_df['timestamp_minute'] >= eff_row['timestamp_minute'] - time_window) &
            (feeds_df['timestamp_minute'] <= eff_row['timestamp_minute'] + time_window)
        ]
        
        if len(candidates) > 0:
            # Take nearest match
            candidates = candidates.copy()
            candidates['time_diff'] = abs((candidates['timestamp_minute'] - eff_row['timestamp_minute']).dt.total_seconds())
            best_match = candidates.loc[candidates['time_diff'].idxmin()]
            
            merged_row = {
                'timestamp': eff_row['timestamp_sent'],
                'symbol': eff_row['symbol'],
                'verdict': eff_row['verdict'],
                'result': eff_row['result'],
                'win': eff_row['win'],
                'confidence': eff_row.get('confidence', 0),
                'entry_price': eff_row.get('entry_price', 0),
                # Feeds data
                'basis_pct': best_match['basis_pct'],
                'basis_provider': best_match['basis_provider'],
                'oi': best_match.get('oi', 0),
                'oi_pct': best_match.get('oi_pct', 0),
                'funding': best_match.get('funding', 0),
            }
            merged_data.append(merged_row)
            match_count += 1
        else:
            no_match_count += 1
    
    merged_df = pd.DataFrame(merged_data)
    
    print(f"✅ Matched {match_count} signals with feeds data")
    print(f"⚠️  {no_match_count} signals without feeds data (skipped)")
    
    if len(merged_df) == 0:
        print("❌ ERROR: No matches found between feeds_log and effectiveness_log")
        return None
    
    # Drop duplicates (keep first)
    merged_df = merged_df.drop_duplicates(subset=['timestamp', 'symbol', 'verdict'], keep='first')
    print(f"✅ Final dataset: {len(merged_df)} unique signals")
    
    return merged_df

def calculate_auroc(df, feature='basis_pct'):
    """Calculate AUROC (Area Under ROC Curve) for a feature"""
    if len(df) < 30:
        return None, "Insufficient samples (<30)"
    
    X = df[feature].values
    y = df['win'].values
    
    # Drop NaN values
    valid_mask = ~np.isnan(X)
    X_clean = X[valid_mask]
    y_clean = y[valid_mask]
    
    if len(X_clean) < 30:
        return None, "Insufficient non-NaN samples"
    
    if len(np.unique(y_clean)) < 2:
        return None, "Only one class present"
    
    try:
        auroc = roc_auc_score(y_clean, X_clean)
        return auroc, "OK"
    except Exception as e:
        return None, f"Error: {str(e)}"

def calculate_lift(df, feature='basis_pct', top_pct=0.20):
    """Calculate lift: top 20% win rate vs baseline win rate"""
    if len(df) < 30:
        return None, None, "Insufficient samples (<30)"
    
    # Sort by feature descending (assuming higher basis_pct = better signal)
    df_sorted = df.sort_values(feature, ascending=False)
    
    # Top 20% bucket
    top_n = int(len(df_sorted) * top_pct)
    if top_n < 5:
        return None, None, "Top bucket too small (<5 samples)"
    
    top_bucket = df_sorted.head(top_n)
    
    # Calculate win rates
    baseline_wr = df['win'].mean()
    top_bucket_wr = top_bucket['win'].mean()
    
    # Lift = top bucket WR / baseline WR
    lift = top_bucket_wr / baseline_wr if baseline_wr > 0 else 0
    
    return lift, top_bucket_wr, f"OK (n={top_n})"

def backtest_basis_pct():
    """Main backtest pipeline for basis_pct predictive power"""
    print("\n" + "="*80)
    print("UIF-30 BACKTEST: BASIS_PCT PREDICTIVE POWER ANALYSIS")
    print("="*80)
    
    # Load data
    feeds_df = load_feeds_data()
    if feeds_df is None:
        print("\n❌ FAILED: Could not load feeds_log.csv")
        return
    
    eff_df = load_effectiveness_data()
    if eff_df is None:
        print("\n❌ FAILED: Could not load effectiveness_log.csv")
        return
    
    # Merge datasets
    merged_df = merge_feeds_with_effectiveness(feeds_df, eff_df)
    if merged_df is None:
        print("\n❌ FAILED: Could not merge datasets")
        return
    
    # Calculate overall metrics
    print("\n" + "="*80)
    print("STEP 4: Overall Metrics (basis_pct)")
    print("="*80)
    
    auroc_overall, auroc_msg = calculate_auroc(merged_df, 'basis_pct')
    lift_overall, top_wr_overall, lift_msg = calculate_lift(merged_df, 'basis_pct')
    baseline_wr = merged_df['win'].mean()
    
    print(f"\n📊 OVERALL RESULTS (n={len(merged_df)}):")
    print(f"   Baseline Win Rate: {baseline_wr:.1%}")
    
    if auroc_overall is not None:
        print(f"   AUROC:             {auroc_overall:.3f} {auroc_msg}")
    else:
        print(f"   AUROC:             N/A ({auroc_msg})")
    
    if lift_overall is not None:
        print(f"   Lift (top 20%):    {lift_overall:.2f}x")
        print(f"   Top 20% Win Rate:  {top_wr_overall:.1%}")
    else:
        print(f"   Lift (top 20%):    N/A ({lift_msg})")
    
    # Per-symbol metrics
    print("\n" + "="*80)
    print("STEP 5: Per-Symbol Metrics")
    print("="*80)
    
    print(f"\n{'Symbol':<12} {'Samples':<10} {'AUROC':<10} {'Lift':<10} {'Top20% WR':<12} {'Baseline WR'}")
    print("-"*80)
    
    symbol_results = []
    
    for symbol in sorted(merged_df['symbol'].unique()):
        sym_df = merged_df[merged_df['symbol'] == symbol].copy()
        
        auroc_sym, auroc_sym_msg = calculate_auroc(sym_df, 'basis_pct')
        lift_sym, top_wr_sym, lift_sym_msg = calculate_lift(sym_df, 'basis_pct')
        baseline_sym = sym_df['win'].mean()
        
        auroc_str = f"{auroc_sym:.3f}" if auroc_sym is not None else "N/A"
        lift_str = f"{lift_sym:.2f}x" if lift_sym is not None else "N/A"
        top_wr_str = f"{top_wr_sym:.1%}" if top_wr_sym is not None else "N/A"
        
        print(f"{symbol:<12} {len(sym_df):<10} {auroc_str:<10} {lift_str:<10} {top_wr_str:<12} {baseline_sym:.1%}")
        
        symbol_results.append({
            'symbol': symbol,
            'samples': len(sym_df),
            'auroc': auroc_sym,
            'lift': lift_sym,
            'baseline_wr': baseline_sym
        })
    
    # Decision logic
    print("\n" + "="*80)
    print("STEP 6: Decision (Activate basis_pct in scoring?)")
    print("="*80)
    
    if auroc_overall is None or lift_overall is None:
        print("\n❌ INSUFFICIENT DATA: Cannot make decision")
        print("   Recommendation: Wait for more data (need 30+ matched signals)")
        decision = False
    elif auroc_overall > 0.55 and lift_overall > 1.2:
        print(f"\n✅ PASS: AUROC={auroc_overall:.3f} > 0.55 AND Lift={lift_overall:.2f}x > 1.2")
        print(f"   Recommendation: ACTIVATE basis_pct with weight=0.10 (cap 0.15)")
        decision = True
    else:
        print(f"\n❌ FAIL: AUROC={auroc_overall:.3f} {'≤' if auroc_overall <= 0.55 else '>'} 0.55 OR Lift={lift_overall:.2f}x {'≤' if lift_overall <= 1.2 else '>'} 1.2")
        print(f"   Recommendation: DO NOT ACTIVATE basis_pct (insufficient predictive power)")
        decision = False
    
    # Save results
    print("\n" + "="*80)
    print("STEP 7: Saving Results")
    print("="*80)
    
    # Save merged dataset
    merged_df.to_csv('backtest_uif30_merged.csv', index=False)
    print(f"✅ Saved merged dataset to backtest_uif30_merged.csv ({len(merged_df)} rows)")
    
    # Save metrics summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_samples': len(merged_df),
        'baseline_wr': baseline_wr,
        'auroc_overall': auroc_overall,
        'lift_overall': lift_overall,
        'decision': 'ACTIVATE' if decision else 'DO_NOT_ACTIVATE',
        'recommended_weight': 0.10 if decision else 0.0,
    }
    
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv('backtest_uif30_summary.csv', index=False)
    print(f"✅ Saved summary to backtest_uif30_summary.csv")
    
    print("\n" + "="*80)
    print("BACKTEST COMPLETE")
    print("="*80)
    
    return decision, auroc_overall, lift_overall

if __name__ == '__main__':
    decision, auroc, lift = backtest_basis_pct()
    
    print(f"\n📋 FINAL DECISION: {'ACTIVATE basis_pct' if decision else 'DO NOT ACTIVATE basis_pct'}")
    if decision:
        print(f"   Next step: Set scoring_weights.basis_pct = 0.10 in config.yaml")
    else:
        print(f"   Next step: Keep scoring_weights.basis_pct = 0.0 (wait for more data)")
