#!/usr/bin/env python3
"""
Retrospective testing of Enhanced Formula v2
Tests on historical completed signals from effectiveness_log.csv
"""

import pandas as pd
import numpy as np
import pickle
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

def load_model():
    """Load trained model"""
    with open('enhanced_formula/enhanced_formula_v2.pkl', 'rb') as f:
        model_data = pickle.load(f)
    return model_data

def load_test_data():
    """Load signals and effectiveness data"""
    df_signals = pd.read_csv('signals_log.csv')
    df_effectiveness = pd.read_csv('effectiveness_log.csv')
    
    df_signals['merge_key'] = df_signals['timestamp'] + '_' + df_signals['symbol']
    df_effectiveness['merge_key'] = df_effectiveness['timestamp_sent'] + '_' + df_effectiveness['symbol']
    
    df_merged = df_signals.merge(
        df_effectiveness[['merge_key', 'result', 'profit_pct', 'duration_actual']], 
        on='merge_key', 
        how='inner'
    )
    
    df_merged = df_merged[df_merged['result'].isin(['WIN', 'LOSS'])].copy()
    
    return df_merged

def prepare_features(df, feature_names):
    """Prepare same features as training"""
    numeric_cols = ['score', 'confidence', 'entry_price', 'vwap', 'oi', 'oi_change', 
                    'liq_long', 'liq_short', 'ttl_minutes']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['price_vs_vwap_pct'] = ((df['entry_price'] - df['vwap']) / df['vwap'] * 100).fillna(0)
    df['liq_pressure'] = np.where(
        (df['liq_long'] + df['liq_short']) > 0,
        (df['liq_short'] - df['liq_long']) / (df['liq_long'] + df['liq_short']),
        0
    )
    df['direction'] = df['verdict'].map({'BUY': 1, 'SELL': -1})
    df['volume_spike_int'] = df['volume_spike'].astype(int) if 'volume_spike' in df.columns else 0
    df['has_cvd_signal'] = df['components'].str.contains('CVD', na=False).astype(int)
    df['has_oi_signal'] = df['components'].str.contains('OI', na=False).astype(int)
    df['has_vwap_signal'] = df['components'].str.contains('VWAP', na=False).astype(int)
    df['has_ema_signal'] = df['components'].str.contains('EMA', na=False).astype(int)
    df['has_rsi_signal'] = df['components'].str.contains('RSI', na=False).astype(int)
    
    df_clean = df.dropna(subset=feature_names + ['profit_pct']).copy()
    
    return df_clean

def main():
    print("="*70)
    print("ENHANCED FORMULA V2 - RETROSPECTIVE TEST")
    print("="*70)
    
    print("\n📥 Loading model...")
    model_data = load_model()
    model = model_data['model']
    scaler = model_data['scaler']
    feature_names = model_data['feature_names']
    
    print(f"   Model: {model_data['model_type']}")
    print(f"   Features: {len(feature_names)}")
    print(f"   Trained R²: {model_data['r2_test']:.4f}")
    
    print("\n📥 Loading test data...")
    df = load_test_data()
    print(f"   Available samples: {len(df)}")
    
    df_clean = prepare_features(df, feature_names)
    print(f"   Clean samples: {len(df_clean)}")
    
    X = df_clean[feature_names]
    y_actual = df_clean['profit_pct']
    
    X_scaled = scaler.transform(X)
    y_pred = model.predict(X_scaled)
    
    r2 = r2_score(y_actual, y_pred)
    mae = mean_absolute_error(y_actual, y_pred)
    rmse = np.sqrt(mean_squared_error(y_actual, y_pred))
    
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"R² Score:     {r2:.4f} ({r2*100:.1f}% variance explained)")
    print(f"MAE:          {mae:.4f}%")
    print(f"RMSE:         {rmse:.4f}%")
    
    baseline_r2 = 0.014
    print(f"\nImprovement:  {r2/baseline_r2:.1f}x better than baseline")
    
    print("\n" + "="*70)
    print("PREDICTION ANALYSIS")
    print("="*70)
    
    df_results = df_clean[['timestamp', 'symbol', 'verdict', 'confidence']].copy()
    df_results['actual_pnl'] = y_actual.values
    df_results['predicted_pnl'] = y_pred
    df_results['error'] = np.abs(y_actual.values - y_pred)
    df_results['result'] = df_clean['result'].values
    
    print(f"\n{'Metric':<25} {'Actual':>10} {'Predicted':>10}")
    print("-"*70)
    print(f"{'Mean PnL':<25} {y_actual.mean():>9.2f}% {y_pred.mean():>9.2f}%")
    print(f"{'Median PnL':<25} {y_actual.median():>9.2f}% {np.median(y_pred):>9.2f}%")
    print(f"{'Std Dev':<25} {y_actual.std():>9.2f}% {y_pred.std():>9.2f}%")
    
    print("\n" + "="*70)
    print("TOP 5 BEST PREDICTIONS (lowest error)")
    print("="*70)
    best = df_results.nsmallest(5, 'error')
    for idx, row in best.iterrows():
        print(f"{row['timestamp']} {row['symbol']:10s} {row['verdict']:4s} "
              f"Actual: {row['actual_pnl']:+6.2f}% | Pred: {row['predicted_pnl']:+6.2f}% | "
              f"Error: {row['error']:.3f}% | {row['result']}")
    
    print("\n" + "="*70)
    print("TOP 5 WORST PREDICTIONS (highest error)")
    print("="*70)
    worst = df_results.nlargest(5, 'error')
    for idx, row in worst.iterrows():
        print(f"{row['timestamp']} {row['symbol']:10s} {row['verdict']:4s} "
              f"Actual: {row['actual_pnl']:+6.2f}% | Pred: {row['predicted_pnl']:+6.2f}% | "
              f"Error: {row['error']:.3f}% | {row['result']}")
    
    wins = df_results[df_results['result'] == 'WIN']
    losses = df_results[df_results['result'] == 'LOSS']
    
    print("\n" + "="*70)
    print("PREDICTION BY OUTCOME")
    print("="*70)
    print(f"\nWIN signals ({len(wins)}):")
    print(f"  Actual avg:    {wins['actual_pnl'].mean():+.3f}%")
    print(f"  Predicted avg: {wins['predicted_pnl'].mean():+.3f}%")
    print(f"  MAE:           {mean_absolute_error(wins['actual_pnl'], wins['predicted_pnl']):.3f}%")
    
    print(f"\nLOSS signals ({len(losses)}):")
    print(f"  Actual avg:    {losses['actual_pnl'].mean():+.3f}%")
    print(f"  Predicted avg: {losses['predicted_pnl'].mean():+.3f}%")
    print(f"  MAE:           {mean_absolute_error(losses['actual_pnl'], losses['predicted_pnl']):.3f}%")
    
    print("\n" + "="*70)
    print("VERDICT")
    print("="*70)
    
    if r2 >= 0.3:
        print("✅ Model performs well on historical data")
        print("   Ready for production integration")
    elif r2 >= 0.15:
        print("⚡ Model shows moderate predictive power")
        print("   Consider collecting more data or feature engineering")
    else:
        print("⚠️  Model needs improvement")
        print("   Collect more training data")
    
    df_results.to_csv('enhanced_formula/retrospective_test_results.csv', index=False)
    print(f"\n✅ Detailed results saved to: enhanced_formula/retrospective_test_results.csv")

if __name__ == '__main__':
    main()
