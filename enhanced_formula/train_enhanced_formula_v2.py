#!/usr/bin/env python3
"""
Enhanced Formula v2 Training - Full Feature Multi-Factor Regression
Uses analysis_log.csv (546 signals) + effectiveness_log.csv (results)
Target: R² improvement from 0.014 to 0.2-0.4
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import pickle
from datetime import datetime
import json

MIN_SAMPLES = 50

def load_signals_log():
    """Load signals_log.csv - contains all sent trading signals"""
    print("📥 Loading signals_log.csv...")
    
    df = pd.read_csv('signals_log.csv')
    
    print(f"   Total signals: {len(df)}")
    print(f"   Columns: {len(df.columns)}")
    
    # Filter only trade signals
    df_trades = df[df['verdict'].isin(['BUY', 'SELL'])].copy()
    print(f"   Trade signals: {len(df_trades)}")
    
    return df_trades

def load_effectiveness_log():
    """Load effectiveness_log.csv with results"""
    print("\n📥 Loading effectiveness_log.csv...")
    
    df = pd.read_csv('effectiveness_log.csv')
    print(f"   Total results: {len(df)}")
    
    # Filter only WIN/LOSS (exclude CANCELLED)
    df_results = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    print(f"   WIN/LOSS results: {len(df_results)}")
    
    return df_results

def merge_data(df_analysis, df_effectiveness):
    """Merge analysis log with effectiveness results"""
    print("\n🔗 Merging datasets...")
    
    # Create merge keys - use timestamp + symbol
    df_analysis['merge_key'] = df_analysis['timestamp'] + '_' + df_analysis['symbol']
    df_effectiveness['merge_key'] = df_effectiveness['timestamp_sent'] + '_' + df_effectiveness['symbol']
    
    # Merge
    df_merged = df_analysis.merge(
        df_effectiveness[['merge_key', 'result', 'profit_pct', 'duration_actual']], 
        on='merge_key', 
        how='inner'
    )
    
    print(f"   Merged records: {len(df_merged)}")
    
    return df_merged

def prepare_features(df):
    """Prepare feature set from signals_log data"""
    print("\n🔧 Preparing features...")
    
    # Ensure numeric types - only fields from signals_log.csv
    numeric_cols = [
        'score', 'confidence', 'entry_price', 'vwap', 
        'oi', 'oi_change', 'liq_long', 'liq_short',
        'ttl_minutes', 'profit_pct'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Calculate derived features
    
    # 1. Price vs VWAP percentage
    df['price_vs_vwap_pct'] = ((df['entry_price'] - df['vwap']) / df['vwap'] * 100).fillna(0)
    
    # 2. Liquidation pressure
    df['liq_pressure'] = np.where(
        (df['liq_long'] + df['liq_short']) > 0,
        (df['liq_short'] - df['liq_long']) / (df['liq_long'] + df['liq_short']),
        0
    )
    
    # 3. OI change (already in dataset)
    
    # 4. Direction multiplier (BUY=1, SELL=-1)
    df['direction'] = df['verdict'].map({'BUY': 1, 'SELL': -1})
    
    # 5. Volume spike (boolean to int)
    df['volume_spike_int'] = df['volume_spike'].astype(int) if 'volume_spike' in df.columns else 0
    
    # 6. Parse components for additional features
    df['has_cvd_signal'] = df['components'].str.contains('CVD', na=False).astype(int)
    df['has_oi_signal'] = df['components'].str.contains('OI', na=False).astype(int)
    df['has_vwap_signal'] = df['components'].str.contains('VWAP', na=False).astype(int)
    df['has_ema_signal'] = df['components'].str.contains('EMA', na=False).astype(int)
    df['has_rsi_signal'] = df['components'].str.contains('RSI', na=False).astype(int)
    
    # Define feature set
    feature_cols = [
        # Signal quality (2)
        'score',
        'confidence',
        
        # Market data (3)
        'oi_change',
        'price_vs_vwap_pct',
        'liq_pressure',
        
        # Signal duration (1)
        'ttl_minutes',
        
        # Direction (1)
        'direction',
        
        # Volume (1)
        'volume_spike_int',
        
        # Component flags (5)
        'has_cvd_signal',
        'has_oi_signal',
        'has_vwap_signal',
        'has_ema_signal',
        'has_rsi_signal'
    ]
    
    # Filter available features
    available_features = [f for f in feature_cols if f in df.columns]
    
    # Remove rows with NaN in critical features
    df_clean = df.dropna(subset=available_features + ['profit_pct']).copy()
    
    print(f"✅ Features available: {len(available_features)}")
    for i, feat in enumerate(available_features, 1):
        non_null = df_clean[feat].notna().sum()
        print(f"   {i:2d}. {feat:<20s} - {non_null} values")
    
    print(f"\n✅ Clean samples: {len(df_clean)} (removed {len(df) - len(df_clean)} with NaN)")
    
    return df_clean, available_features

def train_models(X, y, feature_names):
    """Train multiple models and compare"""
    print("\n🚀 Training models...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"   Training set: {len(X_train)} samples")
    print(f"   Test set: {len(X_test)} samples")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train multiple models
    models = {
        'Linear Regression': LinearRegression(),
        'Ridge (L2)': Ridge(alpha=1.0),
        'Lasso (L1)': Lasso(alpha=0.01, max_iter=10000),
        'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    }
    
    results = {}
    
    print("\n" + "="*70)
    print("MODEL COMPARISON")
    print("="*70)
    
    for name, model in models.items():
        # Train
        model.fit(X_train_scaled, y_train)
        
        # Predict
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        # Metrics
        r2_train = r2_score(y_train, y_train_pred)
        r2_test = r2_score(y_test, y_test_pred)
        mae_test = mean_absolute_error(y_test, y_test_pred)
        rmse_test = np.sqrt(mean_squared_error(y_test, y_test_pred))
        
        # Cross-validation
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='r2')
        
        results[name] = {
            'model': model,
            'r2_train': r2_train,
            'r2_test': r2_test,
            'mae_test': mae_test,
            'rmse_test': rmse_test,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std()
        }
        
        # Print results
        print(f"\n{name}:")
        print(f"  R² Train:  {r2_train:7.4f}")
        print(f"  R² Test:   {r2_test:7.4f}")
        print(f"  CV Mean:   {cv_scores.mean():7.4f} (±{cv_scores.std():.4f})")
        print(f"  MAE Test:  {mae_test:7.4f}%")
        print(f"  RMSE Test: {rmse_test:7.4f}%")
        
        # Improvement vs baseline
        baseline_r2 = 0.014
        improvement = r2_test / baseline_r2
        print(f"  Improvement: {improvement:.1f}x better than baseline (R²=0.014)")
    
    # Select best model based on test R²
    best_name = max(results.keys(), key=lambda k: results[k]['r2_test'])
    best_result = results[best_name]
    
    print("\n" + "="*70)
    print(f"🏆 BEST MODEL: {best_name}")
    print("="*70)
    print(f"  R² Test: {best_result['r2_test']:.4f}")
    print(f"  CV Mean: {best_result['cv_mean']:.4f} (±{best_result['cv_std']:.4f})")
    print(f"  Improvement: {best_result['r2_test']/0.014:.1f}x better than baseline")
    
    # Interpretation
    if best_result['r2_test'] >= 0.3:
        print(f"\n✅ EXCELLENT: Model explains {best_result['r2_test']*100:.1f}% of variance")
    elif best_result['r2_test'] >= 0.2:
        print(f"\n✅ GOOD: Significant improvement from baseline")
    elif best_result['r2_test'] >= 0.1:
        print(f"\n⚡ MODERATE: Some predictive power")
    else:
        print(f"\n⚠️  WEAK: Limited predictive power")
    
    return best_result['model'], scaler, best_name, results

def analyze_feature_importance(model, feature_names, model_name):
    """Analyze feature importance"""
    print("\n" + "="*70)
    print("FEATURE IMPORTANCE")
    print("="*70)
    
    if hasattr(model, 'coef_'):
        # Linear models
        coefficients = pd.DataFrame({
            'Feature': feature_names,
            'Coefficient': model.coef_,
            'Abs_Coefficient': np.abs(model.coef_)
        }).sort_values('Abs_Coefficient', ascending=False)
        
        print(f"{'Feature':<20} {'Coefficient':>12} {'Impact':>10}")
        print("-"*70)
        for _, row in coefficients.iterrows():
            impact = "🔴 High" if row['Abs_Coefficient'] > 0.5 else \
                     "🟡 Med" if row['Abs_Coefficient'] > 0.2 else "🟢 Low"
            print(f"{row['Feature']:<20} {row['Coefficient']:>12.4f} {impact:>10}")
        
        if hasattr(model, 'intercept_'):
            print(f"\nIntercept: {model.intercept_:.4f}")
    
    elif hasattr(model, 'feature_importances_'):
        # Tree-based models
        importances = pd.DataFrame({
            'Feature': feature_names,
            'Importance': model.feature_importances_
        }).sort_values('Importance', ascending=False)
        
        print(f"{'Feature':<20} {'Importance':>12} {'Impact':>10}")
        print("-"*70)
        for _, row in importances.iterrows():
            impact = "🔴 High" if row['Importance'] > 0.15 else \
                     "🟡 Med" if row['Importance'] > 0.05 else "🟢 Low"
            print(f"{row['Feature']:<20} {row['Importance']:>12.4f} {impact:>10}")

def save_model(model, scaler, feature_names, model_name, metrics):
    """Save trained model"""
    
    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'model_type': model_name,
        'r2_test': metrics['r2_test'],
        'cv_mean': metrics['cv_mean'],
        'cv_std': metrics['cv_std'],
        'trained_at': datetime.now().isoformat(),
        'version': 'enhanced_v2_full_features',
        'training_samples': len(feature_names)
    }
    
    with open('enhanced_formula/enhanced_formula_v2.pkl', 'wb') as f:
        pickle.dump(model_data, f)
    
    # Metadata
    metadata = {
        'model_type': model_name,
        'feature_names': feature_names,
        'r2_test': float(metrics['r2_test']),
        'cv_mean': float(metrics['cv_mean']),
        'cv_std': float(metrics['cv_std']),
        'mae_test': float(metrics['mae_test']),
        'rmse_test': float(metrics['rmse_test']),
        'trained_at': datetime.now().isoformat(),
        'version': 'enhanced_v2_full_features',
        'baseline_r2': 0.014,
        'improvement_factor': float(metrics['r2_test'] / 0.014)
    }
    
    if hasattr(model, 'coef_'):
        metadata['coefficients'] = {name: float(coef) for name, coef in zip(feature_names, model.coef_)}
        metadata['intercept'] = float(model.intercept_)
    
    with open('enhanced_formula/enhanced_formula_v2_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Model saved to: enhanced_formula/enhanced_formula_v2.pkl")
    print(f"✅ Metadata saved to: enhanced_formula/enhanced_formula_v2_metadata.json")

def main():
    print("="*70)
    print("ENHANCED FORMULA V2 TRAINING - Full Feature Model")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    df_signals = load_signals_log()
    df_effectiveness = load_effectiveness_log()
    
    # Merge
    df_merged = merge_data(df_signals, df_effectiveness)
    
    if len(df_merged) < MIN_SAMPLES:
        print(f"\n⚠️  NOT ENOUGH DATA!")
        print(f"   Current samples: {len(df_merged)}")
        print(f"   Minimum required: {MIN_SAMPLES}")
        return
    
    # Prepare features
    df_clean, feature_names = prepare_features(df_merged)
    
    if len(df_clean) < MIN_SAMPLES:
        print(f"\n⚠️  NOT ENOUGH CLEAN DATA!")
        print(f"   Clean samples: {len(df_clean)}")
        print(f"   Minimum required: {MIN_SAMPLES}")
        return
    
    X = df_clean[feature_names]
    y = df_clean['profit_pct']
    
    # Train models
    best_model, scaler, model_name, all_results = train_models(X, y, feature_names)
    
    # Analyze features
    analyze_feature_importance(best_model, feature_names, model_name)
    
    # Save best model
    best_metrics = all_results[model_name]
    save_model(best_model, scaler, feature_names, model_name, best_metrics)
    
    print("\n" + "="*70)
    print("🎯 TRAINING COMPLETE!")
    print("="*70)
    print(f"Best Model: {model_name}")
    print(f"R² Score: {best_metrics['r2_test']:.4f}")
    print(f"Improvement: {best_metrics['r2_test']/0.014:.1f}x better than baseline")
    print("\n🎯 NEXT STEPS:")
    print("1. Review feature importance above")
    print("2. Integrate model into smart_signal.py")
    print("3. Test on new signals")
    print("4. Monitor real-world performance")
    print("="*70)

if __name__ == '__main__':
    main()
