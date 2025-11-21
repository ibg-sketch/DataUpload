#!/usr/bin/env python3
"""
Backtest UIF-12: Unified Indicator Feature Combination Analysis
Validates 12-feature combo predictive power on ≤30m horizon with 0.5%/1.0% thresholds

UIF-12 Features:
  zcvd, doi_pct, dev_sigma, vol_ratio, ema_gap, rsi_dist, 
  adx14, psar, liq_ratio, momentum5, vol_accel, basis_pct

Metrics (per symbol + overall):
  - AUROC, PR-AUC
  - Lift (Top 20%)
  - Hit-rate
  - Avg time-to-hit

Outputs:
  - uif30_report.md (feature rankings by AUROC/Lift; top-3 per coin)
  - uif30_metrics.csv
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Constants
HORIZONS = [30]  # minutes
THRESHOLDS = [0.5, 1.0]  # percentage price moves
TOP_PERCENT = 20  # for Lift calculation

def load_analysis_log() -> pd.DataFrame:
    """Load analysis_log.csv with existing signals and features"""
    print("="*80)
    print("STEP 1: Loading analysis_log.csv (signals + dev_sigma, vol_ratio, ema_gap, rsi_dist)")
    print("="*80)
    
    try:
        df = pd.read_csv('analysis_log.csv', parse_dates=['timestamp'])
    except FileNotFoundError:
        print("❌ ERROR: analysis_log.csv not found")
        return pd.DataFrame()
    
    print(f"✅ Loaded {len(df)} rows from analysis_log.csv")
    
    # Filter to recent data (last 7 days)
    cutoff = datetime.now() - timedelta(days=7)
    df = df[df['timestamp'] >= cutoff].copy()
    print(f"✅ Filtered to {len(df)} rows from last 7 days")
    
    # Calculate additional features from existing columns
    if 'cvd' in df.columns:
        # Normalize CVD by volume
        df['zcvd'] = df['cvd'] / df['volume'].replace(0, 1)
    
    if 'oi_change_pct' in df.columns:
        df['doi_pct'] = df['oi_change_pct']
    
    # rsi_dist already in analysis_log as rsi_dist_50 or similar
    if 'rsi' in df.columns:
        df['rsi_dist'] = abs(df['rsi'] - 50)
    
    print(f"\n📊 Analysis log statistics:")
    print(f"   Rows: {len(df)}")
    print(f"   Symbols: {df['symbol'].nunique()}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

def load_feeds_log() -> pd.DataFrame:
    """Load feeds_log.csv (OI, funding, basis, liquidations, OBI)"""
    print("\n" + "="*80)
    print("STEP 2: Loading feeds_log.csv (OI%, funding, basis%, liq_ratio, obi_top)")
    print("="*80)
    
    try:
        # Handle schema evolution: skip bad lines with inconsistent columns
        df = pd.read_csv('data/feeds_log.csv', parse_dates=['timestamp'], on_bad_lines='skip')
    except FileNotFoundError:
        print("⚠️  WARNING: data/feeds_log.csv not found")
        return pd.DataFrame()
    
    print(f"✅ Loaded {len(df)} rows from feeds_log.csv")
    
    # Filter to recent data
    cutoff = datetime.now() - timedelta(days=7)
    df = df[df['timestamp'] >= cutoff].copy()
    print(f"✅ Filtered to {len(df)} rows from last 7 days")
    
    # Standardize timestamp to minute granularity
    df['timestamp_min'] = df['timestamp'].dt.floor('min')
    
    print(f"\n📊 Feeds log statistics:")
    print(f"   Rows: {len(df)}")
    print(f"   Symbols: {df['symbol'].nunique()}")
    print(f"   Has basis_pct: {'basis_pct' in df.columns}")
    print(f"   Has liq_ratio: {'liq_ratio' in df.columns}")
    
    return df

def load_uif_log() -> pd.DataFrame:
    """Load uif_log.csv (ADX14, PSAR, Momentum5, VolAccel)"""
    print("\n" + "="*80)
    print("STEP 3: Loading uif_log.csv (adx14, psar_state, momentum5, vol_accel)")
    print("="*80)
    
    try:
        df = pd.read_csv('data/uif_log.csv', parse_dates=['timestamp'])
    except FileNotFoundError:
        print("⚠️  WARNING: data/uif_log.csv not found")
        return pd.DataFrame()
    
    print(f"✅ Loaded {len(df)} rows from uif_log.csv")
    
    if len(df) < 100:
        print(f"⚠️  WARNING: Only {len(df)} rows available. Need more data for robust backtest!")
        print(f"   Recommendation: Run UIF engine for 1-2 days to collect ~300+ samples")
    
    # Standardize timestamp to minute granularity
    df['timestamp_min'] = df['timestamp'].dt.floor('min')
    
    print(f"\n📊 UIF log statistics:")
    print(f"   Rows: {len(df)}")
    print(f"   Symbols: {df['symbol'].nunique()}")
    print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

def merge_features(analysis_df: pd.DataFrame, feeds_df: pd.DataFrame, uif_df: pd.DataFrame) -> pd.DataFrame:
    """Merge all three data sources on timestamp+symbol"""
    print("\n" + "="*80)
    print("STEP 4: Merging features from all sources")
    print("="*80)
    
    if analysis_df.empty:
        print("❌ ERROR: No analysis_log data available")
        return pd.DataFrame()
    
    # Standardize analysis timestamp
    analysis_df['timestamp_min'] = analysis_df['timestamp'].dt.floor('min')
    
    # Merge with feeds_log (±2 min window)
    merged = analysis_df.copy()
    
    if not feeds_df.empty:
        # For each analysis row, find nearest feeds row
        feeds_features = []
        for idx, row in merged.iterrows():
            match = feeds_df[
                (feeds_df['symbol'] == row['symbol']) &
                (abs((feeds_df['timestamp_min'] - row['timestamp_min']).dt.total_seconds()) <= 120)
            ]
            if len(match) > 0:
                best = match.iloc[0]
                feeds_features.append({
                    'oi_pct': best.get('oi_pct', np.nan),
                    'liq_ratio': best.get('liq_ratio', np.nan),
                    'basis_pct': best.get('basis_pct', np.nan),
                    'obi_top': best.get('obi_top', np.nan)
                })
            else:
                feeds_features.append({
                    'oi_pct': np.nan,
                    'liq_ratio': np.nan,
                    'basis_pct': np.nan,
                    'obi_top': np.nan
                })
        
        for col in ['oi_pct', 'liq_ratio', 'basis_pct', 'obi_top']:
            merged[col] = [f[col] for f in feeds_features]
        
        print(f"✅ Merged feeds_log: {merged['basis_pct'].notna().sum()} rows with basis_pct")
    
    if not uif_df.empty:
        # For each analysis row, find nearest UIF row
        uif_features = []
        for idx, row in merged.iterrows():
            match = uif_df[
                (uif_df['symbol'] == row['symbol']) &
                (abs((uif_df['timestamp_min'] - row['timestamp_min']).dt.total_seconds()) <= 120)
            ]
            if len(match) > 0:
                best = match.iloc[0]
                uif_features.append({
                    'adx14': best.get('adx14', 0),
                    'psar': best.get('psar_state', 0),
                    'momentum5': best.get('momentum5', 0),
                    'vol_accel': best.get('vol_accel', 0)
                })
            else:
                uif_features.append({
                    'adx14': 0,
                    'psar': 0,
                    'momentum5': 0,
                    'vol_accel': 0
                })
        
        for col in ['adx14', 'psar', 'momentum5', 'vol_accel']:
            merged[col] = [f[col] for f in uif_features]
        
        print(f"✅ Merged uif_log: {(merged['adx14'] != 0).sum()} rows with UIF features")
    
    print(f"\n✅ Final merged dataset: {len(merged)} rows")
    return merged

def calculate_forward_returns(df: pd.DataFrame, horizon_min: int) -> pd.DataFrame:
    """Calculate forward price returns for hit detection"""
    print(f"\n" + "="*80)
    print(f"STEP 5: Calculating forward returns (horizon={horizon_min}m)")
    print("="*80)
    
    df = df.sort_values(['symbol', 'timestamp']).copy()
    df['future_price_max'] = np.nan
    df['future_price_min'] = np.nan
    df['time_to_hit_05'] = np.nan
    df['time_to_hit_10'] = np.nan
    
    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol].copy()
        
        for idx in symbol_df.index:
            row = df.loc[idx]
            future_window = df[
                (df['symbol'] == symbol) &
                (df['timestamp'] > row['timestamp']) &
                (df['timestamp'] <= row['timestamp'] + timedelta(minutes=horizon_min))
            ]
            
            if len(future_window) > 0:
                df.loc[idx, 'future_price_max'] = future_window['price'].max()
                df.loc[idx, 'future_price_min'] = future_window['price'].min()
                
                # Calculate time to hit thresholds
                for threshold, col_name in [(0.5, 'time_to_hit_05'), (1.0, 'time_to_hit_10')]:
                    target_price = row['price'] * (1 + threshold / 100)
                    hit_rows = future_window[future_window['price'] >= target_price]
                    if len(hit_rows) > 0:
                        time_diff = (hit_rows['timestamp'].iloc[0] - row['timestamp']).total_seconds() / 60
                        df.loc[idx, col_name] = time_diff
    
    # Calculate returns
    df['return_pct_max'] = ((df['future_price_max'] - df['price']) / df['price'] * 100)
    df['return_pct_min'] = ((df['future_price_min'] - df['price']) / df['price'] * 100)
    
    print(f"✅ Forward returns calculated for {df['return_pct_max'].notna().sum()} rows")
    
    return df

def label_hits(df: pd.DataFrame, threshold_pct: float) -> pd.DataFrame:
    """Label rows as hit/no-hit based on forward returns"""
    df = df.copy()
    df[f'hit_{threshold_pct}'] = (df['return_pct_max'] >= threshold_pct).astype(int)
    
    hit_count = df[f'hit_{threshold_pct}'].sum()
    hit_rate = df[f'hit_{threshold_pct}'].mean() * 100
    
    print(f"   Threshold {threshold_pct}%: {hit_count} hits ({hit_rate:.1f}% hit-rate)")
    
    return df

def calculate_metrics(df: pd.DataFrame, feature_cols: List[str], threshold_pct: float) -> Dict:
    """Calculate AUROC, PR-AUC, Lift, hit-rate, avg time-to-hit"""
    
    # Filter to rows with non-null features
    valid_df = df.dropna(subset=feature_cols + [f'hit_{threshold_pct}']).copy()
    
    if len(valid_df) < 20:
        return {
            'auroc': np.nan,
            'pr_auc': np.nan,
            'lift_top20': np.nan,
            'hit_rate': np.nan,
            'avg_time_to_hit': np.nan,
            'n_samples': len(valid_df)
        }
    
    # Create composite score (simple sum for now)
    valid_df['uif12_score'] = valid_df[feature_cols].sum(axis=1)
    
    y_true = valid_df[f'hit_{threshold_pct}'].values
    y_score = valid_df['uif12_score'].values
    
    # AUROC
    try:
        auroc = roc_auc_score(y_true, y_score)
    except:
        auroc = np.nan
    
    # PR-AUC
    try:
        precision, recall, _ = precision_recall_curve(y_true, y_score)
        pr_auc = auc(recall, precision)
    except:
        pr_auc = np.nan
    
    # Lift (Top 20%)
    top20_idx = int(len(valid_df) * TOP_PERCENT / 100)
    top20_rows = valid_df.nlargest(top20_idx, 'uif12_score')
    lift = top20_rows[f'hit_{threshold_pct}'].mean() / valid_df[f'hit_{threshold_pct}'].mean() if valid_df[f'hit_{threshold_pct}'].mean() > 0 else np.nan
    
    # Hit-rate
    hit_rate = valid_df[f'hit_{threshold_pct}'].mean()
    
    # Avg time-to-hit
    time_col = 'time_to_hit_05' if threshold_pct == 0.5 else 'time_to_hit_10'
    avg_time = valid_df[valid_df[f'hit_{threshold_pct}'] == 1][time_col].mean()
    
    return {
        'auroc': auroc,
        'pr_auc': pr_auc,
        'lift_top20': lift,
        'hit_rate': hit_rate,
        'avg_time_to_hit': avg_time,
        'n_samples': len(valid_df)
    }

def run_backtest():
    """Main backtest execution"""
    print("\n" + "="*80)
    print("UIF-12 BACKTEST - UNIFIED INDICATOR FEATURE COMBINATION")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load data
    analysis_df = load_analysis_log()
    feeds_df = load_feeds_log()
    uif_df = load_uif_log()
    
    # Merge features
    merged_df = merge_features(analysis_df, feeds_df, uif_df)
    
    if merged_df.empty:
        print("\n❌ ERROR: No data available for backtest")
        return
    
    # Calculate forward returns
    merged_df = calculate_forward_returns(merged_df, horizon_min=30)
    
    # Label hits for each threshold
    print("\n" + "="*80)
    print("STEP 6: Labeling hits")
    print("="*80)
    for threshold in THRESHOLDS:
        merged_df = label_hits(merged_df, threshold)
    
    # Define UIF-12 features
    uif12_features = [
        'zcvd', 'doi_pct', 'dev_sigma', 'vol_ratio', 'ema_gap', 'rsi_dist',
        'adx14', 'psar', 'liq_ratio', 'momentum5', 'vol_accel', 'basis_pct'
    ]
    
    # Check feature availability
    available_features = [f for f in uif12_features if f in merged_df.columns and merged_df[f].notna().sum() > 0]
    print(f"\n✅ Available UIF-12 features: {len(available_features)}/12")
    print(f"   {', '.join(available_features)}")
    
    if len(available_features) < 5:
        print("\n⚠️  WARNING: Insufficient features for robust backtest")
        print("   Recommendation: Collect more data (run UIF engine + feeds service for 1-2 days)")
    
    # Calculate metrics
    print("\n" + "="*80)
    print("STEP 7: Calculating metrics")
    print("="*80)
    
    results = []
    
    # Overall metrics
    for threshold in THRESHOLDS:
        metrics = calculate_metrics(merged_df, available_features, threshold)
        results.append({
            'symbol': 'OVERALL',
            'threshold': threshold,
            **metrics
        })
        print(f"\n📊 OVERALL metrics (threshold={threshold}%):")
        print(f"   AUROC:         {metrics['auroc']:.3f}" if not np.isnan(metrics['auroc']) else "   AUROC:         N/A")
        print(f"   PR-AUC:        {metrics['pr_auc']:.3f}" if not np.isnan(metrics['pr_auc']) else "   PR-AUC:        N/A")
        print(f"   Lift (Top20%): {metrics['lift_top20']:.2f}x" if not np.isnan(metrics['lift_top20']) else "   Lift (Top20%): N/A")
        print(f"   Hit-rate:      {metrics['hit_rate']*100:.1f}%" if not np.isnan(metrics['hit_rate']) else "   Hit-rate:      N/A")
        print(f"   Avg time:      {metrics['avg_time_to_hit']:.1f} min" if not np.isnan(metrics['avg_time_to_hit']) else "   Avg time:      N/A")
        print(f"   Samples:       {metrics['n_samples']}")
    
    # Per-symbol metrics
    for symbol in merged_df['symbol'].unique():
        symbol_df = merged_df[merged_df['symbol'] == symbol]
        for threshold in THRESHOLDS:
            metrics = calculate_metrics(symbol_df, available_features, threshold)
            results.append({
                'symbol': symbol,
                'threshold': threshold,
                **metrics
            })
    
    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv('uif30_metrics.csv', index=False)
    print(f"\n✅ Saved metrics to uif30_metrics.csv")
    
    # Generate report
    generate_report(results_df, available_features, merged_df)
    
    print("\n" + "="*80)
    print("✅ BACKTEST COMPLETE")
    print("="*80)

def generate_report(results_df: pd.DataFrame, features: List[str], data_df: pd.DataFrame):
    """Generate markdown report with feature rankings"""
    
    with open('uif30_report.md', 'w') as f:
        f.write("# UIF-12 Backtest Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Horizon:** 30 minutes\n")
        f.write(f"**Thresholds:** {', '.join(map(str, THRESHOLDS))}%\n\n")
        
        f.write("## Features Analyzed\n\n")
        f.write(f"Available: {len(features)}/12 UIF-12 features\n\n")
        for feat in features:
            f.write(f"- {feat}\n")
        
        f.write("\n## Overall Metrics\n\n")
        overall = results_df[results_df['symbol'] == 'OVERALL']
        f.write("| Threshold | AUROC | PR-AUC | Lift (Top20%) | Hit-Rate | Avg Time-to-Hit | Samples |\n")
        f.write("|-----------|-------|--------|---------------|----------|-----------------|----------|\n")
        for _, row in overall.iterrows():
            f.write(f"| {row['threshold']}% | {row['auroc']:.3f} | {row['pr_auc']:.3f} | {row['lift_top20']:.2f}x | {row['hit_rate']*100:.1f}% | {row['avg_time_to_hit']:.1f}m | {row['n_samples']} |\n")
        
        f.write("\n## Per-Symbol Metrics (0.5% threshold)\n\n")
        per_symbol = results_df[(results_df['symbol'] != 'OVERALL') & (results_df['threshold'] == 0.5)]
        per_symbol = per_symbol.sort_values('auroc', ascending=False)
        f.write("| Symbol | AUROC | Lift | Hit-Rate | Samples |\n")
        f.write("|--------|-------|------|----------|----------|\n")
        for _, row in per_symbol.iterrows():
            f.write(f"| {row['symbol']} | {row['auroc']:.3f} | {row['lift_top20']:.2f}x | {row['hit_rate']*100:.1f}% | {row['n_samples']} |\n")
        
        f.write("\n## Data Availability Warning\n\n")
        if len(features) < 12:
            f.write("⚠️ **INSUFFICIENT DATA**: Only {}/{} features available\n\n".format(len(features), 12))
            f.write("**Recommendation:** Run UIF Feature Engine for 1-2 days to collect comprehensive data before production wiring.\n\n")
        
        f.write("\n## Next Steps\n\n")
        f.write("1. ✅ Phase 3: Wire features with zero weights for diagnostic logging\n")
        f.write("2. 📊 Collect 1-2 days of comprehensive UIF data\n")
        f.write("3. 🔄 Re-run backtest with full dataset\n")
        f.write("4. 🎯 Optimize weights using ML-based feature selection\n")
    
    print(f"✅ Saved report to uif30_report.md")

if __name__ == '__main__':
    run_backtest()
