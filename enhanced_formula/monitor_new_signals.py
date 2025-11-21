#!/usr/bin/env python3
"""
Monitor new signals and test Enhanced Formula v2 predictions
Automatically tests model on signals that weren't in training set
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
import time

TRAINING_CUTOFF = "2025-11-04 12:21:00"  # Training completed at this time

def load_model():
    with open('enhanced_formula/enhanced_formula_v2.pkl', 'rb') as f:
        return pickle.load(f)

def prepare_features(df, feature_names):
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
    
    return df.dropna(subset=feature_names).copy()

def get_new_completed_signals():
    """Get completed signals after training cutoff"""
    df_signals = pd.read_csv('signals_log.csv')
    df_effectiveness = pd.read_csv('effectiveness_log.csv')
    
    # Filter effectiveness to only after training
    df_effectiveness = df_effectiveness[df_effectiveness['timestamp_checked'] > TRAINING_CUTOFF].copy()
    df_effectiveness = df_effectiveness[df_effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    
    if len(df_effectiveness) == 0:
        return None
    
    df_signals['merge_key'] = df_signals['timestamp'] + '_' + df_signals['symbol']
    df_effectiveness['merge_key'] = df_effectiveness['timestamp_sent'] + '_' + df_effectiveness['symbol']
    
    df_merged = df_signals.merge(
        df_effectiveness[['merge_key', 'result', 'profit_pct', 'duration_actual', 'timestamp_checked']], 
        on='merge_key', 
        how='inner'
    )
    
    return df_merged

def main():
    print("="*70)
    print("ENHANCED FORMULA V2 - NEW SIGNALS MONITOR")
    print("="*70)
    print(f"Training cutoff: {TRAINING_CUTOFF}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    model_data = load_model()
    model = model_data['model']
    scaler = model_data['scaler']
    feature_names = model_data['feature_names']
    
    print("Waiting for new completed signals...")
    print("Press Ctrl+C to stop\n")
    
    last_count = 0
    
    while True:
        df_new = get_new_completed_signals()
        
        if df_new is None or len(df_new) == 0:
            if last_count == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No new completed signals yet...")
            time.sleep(30)
            continue
        
        if len(df_new) > last_count:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Found {len(df_new)} new completed signals!")
            
            df_clean = prepare_features(df_new, feature_names)
            
            if len(df_clean) > 0:
                X = df_clean[feature_names]
                y_actual = df_clean['profit_pct']
                
                X_scaled = scaler.transform(X)
                y_pred = model.predict(X_scaled)
                
                from sklearn.metrics import r2_score, mean_absolute_error
                r2 = r2_score(y_actual, y_pred)
                mae = mean_absolute_error(y_actual, y_pred)
                
                print("\n" + "="*70)
                print("TEST ON NEW DATA")
                print("="*70)
                print(f"Samples:      {len(df_clean)}")
                print(f"R² Score:     {r2:.4f} ({r2*100:.1f}% variance explained)")
                print(f"MAE:          {mae:.4f}%")
                print(f"Improvement:  {r2/0.014:.1f}x vs baseline")
                
                df_results = df_clean[['timestamp', 'symbol', 'verdict', 'confidence']].copy()
                df_results['actual_pnl'] = y_actual.values
                df_results['predicted_pnl'] = y_pred
                df_results['error'] = np.abs(y_actual.values - y_pred)
                df_results['result'] = df_clean['result'].values
                
                print("\nLATEST PREDICTIONS:")
                print("-"*70)
                for idx, row in df_results.tail(5).iterrows():
                    status = "✅" if row['result'] == 'WIN' else "❌"
                    print(f"{status} {row['timestamp']} {row['symbol']:10s} {row['verdict']:4s} "
                          f"Actual: {row['actual_pnl']:+6.2f}% | Pred: {row['predicted_pnl']:+6.2f}% | "
                          f"Error: {row['error']:.3f}%")
                
                df_results.to_csv('enhanced_formula/new_signals_test_results.csv', index=False)
                print(f"\n✅ Results saved to: enhanced_formula/new_signals_test_results.csv")
            
            last_count = len(df_new)
        
        time.sleep(30)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
