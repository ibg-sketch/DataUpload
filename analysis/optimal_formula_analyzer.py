"""
Optimal Formula Analyzer
Analyzes historical data to derive the best predictive formula for price movements
"""

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

def load_and_prepare_data():
    """Load and merge analysis and effectiveness logs"""
    print("="*80)
    print("STEP 1: LOADING AND PREPARING DATA")
    print("="*80)
    
    # Load analysis log
    df_analysis = pd.read_csv('analysis_log.csv')
    df_analysis['timestamp'] = pd.to_datetime(df_analysis['timestamp'])
    
    # Load effectiveness log
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_eff['timestamp_sent'] = pd.to_datetime(df_eff['timestamp_sent'])
    
    # Merge to get indicator values at signal time
    merged = []
    for _, sig in df_eff.iterrows():
        # Find the analysis entry closest to signal time
        analysis = df_analysis[
            (df_analysis['symbol'] == sig['symbol']) &
            (df_analysis['timestamp'] <= sig['timestamp_sent']) &
            (df_analysis['timestamp'] >= sig['timestamp_sent'] - pd.Timedelta(minutes=2))
        ].tail(1)
        
        if len(analysis) > 0:
            row = analysis.iloc[0]
            merged.append({
                'symbol': sig['symbol'],
                'verdict': sig['verdict'],
                'result': 1 if sig['result'] == 'WIN' else 0,  # Binary: WIN=1, LOSS=0
                'profit_pct': sig['profit_pct'],
                'confidence': sig['confidence'],
                'cvd': row['cvd'],
                'oi_change': row['oi_change'],
                'oi_change_pct': row['oi_change_pct'],
                'volume': row['volume'],
                'volume_median': row['volume_median'],
                'rsi': row['rsi'],
                'price': row['price'],
                'vwap': row['vwap'],
                'price_vs_vwap_pct': row['price_vs_vwap_pct'],
                'ema_short': row['ema_short'],
                'ema_long': row['ema_long'],
                'atr': row['atr'],
                'funding_rate': row['funding_rate'],
                'liq_long_usd': row['liq_long_usd'],
                'liq_short_usd': row['liq_short_usd'],
            })
    
    df = pd.DataFrame(merged)
    
    # Feature engineering
    df['volume_ratio'] = df['volume'] / df['volume_median']
    df['cvd_millions'] = df['cvd'] / 1_000_000
    df['oi_change_abs'] = abs(df['oi_change_pct'])
    df['vwap_dist_abs'] = abs(df['price_vs_vwap_pct'])
    df['ema_diff'] = df['ema_short'] - df['ema_long']
    df['ema_diff_pct'] = (df['ema_diff'] / df['price']) * 100
    df['liq_ratio'] = df['liq_long_usd'] / (df['liq_short_usd'] + 1)
    df['cvd_abs'] = abs(df['cvd'])
    
    print(f"✓ Loaded {len(df)} signals with indicator data")
    print(f"✓ Win Rate: {df['result'].mean()*100:.1f}%")
    print(f"✓ Avg Profit (wins): {df[df['result']==1]['profit_pct'].mean():.2f}%")
    print(f"✓ Avg Loss (losses): {df[df['result']==0]['profit_pct'].mean():.2f}%")
    print()
    
    return df

def compute_individual_correlations(df):
    """Compute correlation between each indicator and win/loss"""
    print("="*80)
    print("STEP 2: INDIVIDUAL INDICATOR CORRELATIONS")
    print("="*80)
    
    indicators = [
        'cvd_millions', 'oi_change_pct', 'oi_change_abs', 'volume_ratio', 
        'rsi', 'vwap_dist_abs', 'ema_diff_pct', 'atr', 'funding_rate',
        'liq_ratio', 'confidence'
    ]
    
    correlations = []
    for ind in indicators:
        if ind in df.columns:
            # Pearson correlation
            pearson_r, pearson_p = stats.pearsonr(df[ind].fillna(0), df['result'])
            # Spearman correlation (non-linear)
            spearman_r, spearman_p = stats.spearmanr(df[ind].fillna(0), df['result'])
            
            correlations.append({
                'indicator': ind,
                'pearson_r': pearson_r,
                'pearson_p': pearson_p,
                'spearman_r': spearman_r,
                'spearman_p': spearman_p,
                'abs_correlation': abs(pearson_r)
            })
    
    corr_df = pd.DataFrame(correlations).sort_values('abs_correlation', ascending=False)
    
    print("\nIndicator Correlations with WIN/LOSS (sorted by strength):")
    print("-"*80)
    for _, row in corr_df.iterrows():
        sig = "***" if row['pearson_p'] < 0.001 else "**" if row['pearson_p'] < 0.01 else "*" if row['pearson_p'] < 0.05 else ""
        print(f"{row['indicator']:20} | Pearson: {row['pearson_r']:+.4f}{sig:3} | Spearman: {row['spearman_r']:+.4f}")
    
    print("\n*** p<0.001, ** p<0.01, * p<0.05")
    print()
    
    return corr_df

def find_best_combinations(df, top_indicators, max_combo_size=3):
    """Find best indicator combinations"""
    print("="*80)
    print("STEP 3: OPTIMAL INDICATOR COMBINATIONS")
    print("="*80)
    
    indicators = top_indicators['indicator'].head(8).tolist()
    
    best_combos = []
    
    # Test 2-indicator combinations
    print("\n2-Indicator Combinations:")
    print("-"*80)
    for combo in combinations(indicators, 2):
        X = df[list(combo)].fillna(0)
        y = df['result']
        
        # Logistic regression
        lr = LogisticRegression(max_iter=1000)
        lr.fit(X, y)
        score = lr.score(X, y)
        
        best_combos.append({
            'combo': combo,
            'size': 2,
            'score': score
        })
    
    # Show top 5
    best_2 = sorted(best_combos, key=lambda x: x['score'], reverse=True)[:5]
    for i, c in enumerate(best_2, 1):
        print(f"{i}. {' + '.join(c['combo']):50} | Accuracy: {c['score']:.4f}")
    
    # Test 3-indicator combinations
    print("\n3-Indicator Combinations:")
    print("-"*80)
    best_combos_3 = []
    for combo in combinations(indicators, 3):
        X = df[list(combo)].fillna(0)
        y = df['result']
        
        lr = LogisticRegression(max_iter=1000)
        lr.fit(X, y)
        score = lr.score(X, y)
        
        best_combos_3.append({
            'combo': combo,
            'size': 3,
            'score': score
        })
    
    best_3 = sorted(best_combos_3, key=lambda x: x['score'], reverse=True)[:5]
    for i, c in enumerate(best_3, 1):
        print(f"{i}. {' + '.join(c['combo']):60} | Accuracy: {c['score']:.4f}")
    
    print()
    return best_3[0] if best_3 else None

def derive_optimal_formula(df):
    """Derive the optimal predictive formula using multiple approaches"""
    print("="*80)
    print("STEP 4: OPTIMAL FORMULA DERIVATION")
    print("="*80)
    
    # Select features
    features = [
        'cvd_millions', 'oi_change_pct', 'volume_ratio', 'vwap_dist_abs',
        'rsi', 'ema_diff_pct', 'atr', 'liq_ratio'
    ]
    
    X = df[features].fillna(0)
    y = df['result']
    
    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, columns=features)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print("\n1. LINEAR FORMULA (Logistic Regression):")
    print("-"*80)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)
    
    train_acc = lr.score(X_train, y_train)
    test_acc = lr.score(X_test, y_test)
    
    y_pred_proba = lr.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print(f"Training Accuracy: {train_acc:.4f}")
    print(f"Test Accuracy: {test_acc:.4f}")
    print(f"ROC-AUC Score: {auc:.4f}")
    print("\nFormula Coefficients (normalized):")
    
    coefficients = sorted(zip(features, lr.coef_[0]), key=lambda x: abs(x[1]), reverse=True)
    for feat, coef in coefficients:
        print(f"  {feat:20} : {coef:+.4f}")
    
    print(f"\nIntercept: {lr.intercept_[0]:.4f}")
    
    # Generate formula
    print("\nOPTIMAL LINEAR FORMULA:")
    print("-"*80)
    print("Signal = ", end="")
    terms = []
    for feat, coef in coefficients:
        if abs(coef) > 0.001:
            terms.append(f"{coef:+.4f} * {feat}")
    print(" ".join(terms[:5]))  # Top 5 terms
    print(f"         {lr.intercept_[0]:+.4f}")
    print("\nif Signal > 0 → UP (BUY/SELL based on verdict)")
    print("if Signal < 0 → NO TRADE")
    
    print("\n2. NON-LINEAR FORMULA (Random Forest):")
    print("-"*80)
    rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X_train, y_train)
    
    rf_train_acc = rf.score(X_train, y_train)
    rf_test_acc = rf.score(X_test, y_test)
    
    y_pred_proba_rf = rf.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, y_pred_proba_rf)
    
    print(f"Training Accuracy: {rf_train_acc:.4f}")
    print(f"Test Accuracy: {rf_test_acc:.4f}")
    print(f"ROC-AUC Score: {rf_auc:.4f}")
    print("\nFeature Importances:")
    
    importances = sorted(zip(features, rf.feature_importances_), key=lambda x: x[1], reverse=True)
    for feat, imp in importances:
        print(f"  {feat:20} : {imp:.4f}")
    
    print()
    
    # Simplified formula based on top features
    print("="*80)
    print("STEP 5: SIMPLIFIED OPTIMAL FORMULA")
    print("="*80)
    
    # Use only top 4 features
    top_features = [feat for feat, _ in coefficients[:4]]
    
    X_simple = df[top_features].fillna(0)
    X_simple_scaled = scaler.fit_transform(X_simple)
    
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(
        X_simple_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    lr_simple = LogisticRegression(max_iter=1000)
    lr_simple.fit(X_train_s, y_train_s)
    
    simple_acc = lr_simple.score(X_test_s, y_test_s)
    y_pred_simple = lr_simple.predict_proba(X_test_s)[:, 1]
    simple_auc = roc_auc_score(y_test_s, y_pred_simple)
    
    print(f"\nSimplified Model Performance:")
    print(f"  Test Accuracy: {simple_acc:.4f}")
    print(f"  ROC-AUC Score: {simple_auc:.4f}")
    print("\nSIMPLIFIED FORMULA (4 indicators):")
    print("-"*80)
    
    simple_coeffs = list(zip(top_features, lr_simple.coef_[0]))
    print("\nSignal = ", end="")
    for i, (feat, coef) in enumerate(simple_coeffs):
        print(f"{coef:+.4f} * {feat}", end="")
        if i < len(simple_coeffs) - 1:
            print(" + ", end="")
    print(f" {lr_simple.intercept_[0]:+.4f}")
    
    print("\nDECISION RULES:")
    print("  if Signal > 0.5  → STRONG CONFIDENCE (send signal)")
    print("  if Signal > 0.0  → MODERATE CONFIDENCE")
    print("  if Signal < 0.0  → NO TRADE")
    
    return lr, lr_simple, scaler, features, top_features

def backtest_formula(df, model, scaler, features):
    """Backtest the formula on historical data"""
    print("\n" + "="*80)
    print("STEP 6: BACKTEST RESULTS")
    print("="*80)
    
    X = df[features].fillna(0)
    X_scaled = scaler.transform(X)
    
    df['predicted_signal'] = model.predict_proba(X_scaled)[:, 1]
    df['predicted_class'] = model.predict(X_scaled)
    
    # Test different thresholds
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    
    print("\nPerformance by Confidence Threshold:")
    print("-"*80)
    print(f"{'Threshold':<12} | {'Signals':<10} | {'Win Rate':<10} | {'Avg Profit':<12} | {'Total P&L'}")
    print("-"*80)
    
    for threshold in thresholds:
        subset = df[df['predicted_signal'] >= threshold]
        if len(subset) > 0:
            win_rate = subset['result'].mean() * 100
            avg_profit = subset['profit_pct'].mean()
            total_pnl = subset['profit_pct'].sum()
            print(f"{threshold:<12.1f} | {len(subset):<10} | {win_rate:<10.1f}% | {avg_profit:<12.2f}% | {total_pnl:+.2f}%")
    
    print()

if __name__ == "__main__":
    # Load data
    df = load_and_prepare_data()
    
    # Individual correlations
    correlations = compute_individual_correlations(df)
    
    # Best combinations
    best_combo = find_best_combinations(df, correlations)
    
    # Derive optimal formula
    model, simple_model, scaler, features, top_features = derive_optimal_formula(df)
    
    # Backtest
    backtest_formula(df, simple_model, scaler, top_features)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nRecommendation: Use the simplified 4-indicator formula with threshold > 0.5")
    print("This balances accuracy, interpretability, and practical implementation.")
