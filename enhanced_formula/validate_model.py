#!/usr/bin/env python3
"""
One-time validation of Enhanced Formula v2 on new signals
Tests model on all completed signals after training cutoff
Uses analysis_log.csv for full feature data
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def load_model():
    with open('enhanced_formula/enhanced_formula_v2.pkl', 'rb') as f:
        return pickle.load(f)

def get_new_completed_signals():
    """Get all completed signals after training cutoff using signals_log"""
    df_signals = pd.read_csv('signals_log.csv')
    df_effectiveness = pd.read_csv('effectiveness_log.csv')
    
    # Filter to completed signals after training
    df_effectiveness = df_effectiveness[df_effectiveness['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    df_effectiveness = df_effectiveness[df_effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    
    if len(df_effectiveness) == 0:
        return None
    
    print(f"Found {len(df_effectiveness)} completed signals after training")
    
    # Merge signals_log with effectiveness_log - match by timestamp and symbol
    df_merged = pd.merge(
        df_signals,
        df_effectiveness[['timestamp_sent', 'symbol', 'result', 'profit_pct']],
        left_on=['timestamp', 'symbol'],
        right_on=['timestamp_sent', 'symbol'],
        how='inner'
    )
    
    print(f"Successfully merged {len(df_merged)} signals")
    
    return df_merged

def prepare_features(df, feature_names):
    """Prepare features from signals_log format"""
    # Calculate price_vs_vwap_pct from entry_price and vwap
    df['entry_price'] = pd.to_numeric(df['entry_price'], errors='coerce')
    df['vwap'] = pd.to_numeric(df['vwap'], errors='coerce')
    df['price_vs_vwap_pct'] = ((df['entry_price'] - df['vwap']) / df['vwap'] * 100).fillna(0)
    
    # Calculate liq_pressure from liq_long and liq_short
    df['liq_long'] = pd.to_numeric(df['liq_long'], errors='coerce').fillna(0)
    df['liq_short'] = pd.to_numeric(df['liq_short'], errors='coerce').fillna(0)
    df['liq_pressure'] = np.where(
        (df['liq_long'] + df['liq_short']) > 0,
        (df['liq_short'] - df['liq_long']) / (df['liq_long'] + df['liq_short']),
        0
    )
    
    # Map verdict to direction
    df['direction'] = df['verdict'].map({'BUY': 1, 'SELL': -1, 'NO_TRADE': 0})
    
    # Convert volume_spike to int
    df['volume_spike_int'] = df['volume_spike'].astype(int)
    
    # Component flags
    df['has_cvd_signal'] = df['components'].str.contains('CVD', na=False).astype(int)
    df['has_oi_signal'] = df['components'].str.contains('OI', na=False).astype(int)
    df['has_vwap_signal'] = df['components'].str.contains('VWAP', na=False).astype(int)
    df['has_ema_signal'] = df['components'].str.contains('EMA', na=False).astype(int)
    df['has_rsi_signal'] = df['components'].str.contains('RSI', na=False).astype(int)
    
    # Ensure all features are numeric
    for col in ['score', 'confidence', 'oi_change', 'ttl_minutes']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df.dropna(subset=feature_names).copy()

def main():
    print("="*70)
    print("ENHANCED FORMULA V2 - VALIDATION ON NEW SIGNALS")
    print("="*70)
    print(f"Training cutoff: {TRAINING_CUTOFF}")
    print(f"Validation time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load model
    model_data = load_model()
    model = model_data['model']
    scaler = model_data['scaler']
    feature_names = model_data['feature_names']
    
    print(f"Model: {model_data['model_type']}")
    print(f"Training R²: {model_data['r2_test']:.4f}")
    print(f"Features: {', '.join(feature_names)}")
    print()
    
    # Get new signals
    df_new = get_new_completed_signals()
    
    if df_new is None or len(df_new) == 0:
        print("❌ No completed signals found after training cutoff")
        return
    
    print(f"Found {len(df_new)} completed signals after training")
    
    # Prepare features
    df_clean = prepare_features(df_new, feature_names)
    
    if len(df_clean) == 0:
        print("❌ No valid signals after feature preparation")
        print("\nMissing features check:")
        for feat in feature_names:
            if feat not in df_new.columns:
                print(f"  - {feat}: MISSING")
            else:
                nulls = df_new[feat].isna().sum()
                print(f"  - {feat}: {nulls} nulls")
        return
    
    print(f"Valid signals for testing: {len(df_clean)}")
    print()
    
    # Make predictions
    X = df_clean[feature_names]
    y_actual = df_clean['profit_pct']
    
    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    
    # Calculate metrics
    r2 = r2_score(y_actual, y_pred)
    mae = mean_absolute_error(y_actual, y_pred)
    rmse = np.sqrt(mean_squared_error(y_actual, y_pred))
    
    print("="*70)
    print("VALIDATION RESULTS")
    print("="*70)
    print(f"Test Samples:     {len(df_clean)}")
    print(f"R² Score:         {r2:.4f} ({r2*100:.1f}% variance explained)")
    print(f"MAE:              {mae:.4f}%")
    print(f"RMSE:             {rmse:.4f}%")
    print(f"Baseline R²:      0.014")
    if r2 > 0:
        print(f"Improvement:      {r2/0.014:.1f}x")
    else:
        print(f"Improvement:      {r2/0.014:.1f}x (NEGATIVE - worse than baseline!)")
    print()
    
    # Breakdown by result
    df_results = df_clean[['timestamp', 'symbol', 'verdict', 'confidence', 'result']].copy()
    df_results['actual_pnl'] = y_actual.values
    df_results['predicted_pnl'] = y_pred
    df_results['error'] = np.abs(y_actual.values - y_pred)
    
    print("BREAKDOWN BY RESULT:")
    print("-"*70)
    for result_type in ['WIN', 'LOSS']:
        mask = df_results['result'] == result_type
        if mask.sum() > 0:
            count = mask.sum()
            avg_actual = df_results[mask]['actual_pnl'].mean()
            avg_pred = df_results[mask]['predicted_pnl'].mean()
            avg_error = df_results[mask]['error'].mean()
            print(f"{result_type:8s} ({count:2d}): Actual: {avg_actual:+.2f}% | Pred: {avg_pred:+.2f}% | Error: {avg_error:.2f}%")
    
    print()
    print("ALL PREDICTIONS:")
    print("-"*70)
    print(f"{'Time':<16} {'Symbol':<10} {'Side':<5} {'Conf':<5} {'Actual':<8} {'Pred':<8} {'Error':<8} {'Result'}")
    print("-"*70)
    
    for idx, row in df_results.iterrows():
        result_icon = "✅" if row['result'] == 'WIN' else "❌"
        print(f"{result_icon} {row['timestamp'][-8:]} {row['symbol']:<10} {row['verdict']:<5} "
              f"{row['confidence']*100:>4.0f}% {row['actual_pnl']:+7.2f}% {row['predicted_pnl']:+7.2f}% "
              f"{row['error']:7.2f}% {row['result']}")
    
    # Save results
    df_results.to_csv('enhanced_formula/validation_results.csv', index=False)
    print()
    print("✅ Results saved to: enhanced_formula/validation_results.csv")
    print()
    
    # Summary
    print("="*70)
    if r2 > 0.2:
        print("🎉 SUCCESS: Model performs well on new data!")
    elif r2 > 0:
        print("⚠️  MARGINAL: Model has some predictive power but needs improvement")
    else:
        print("❌ FAILURE: Model does not generalize to new data")
        print("   → Severe overfitting detected")
        print("   → Model performs worse than random baseline")

if __name__ == '__main__':
    main()
