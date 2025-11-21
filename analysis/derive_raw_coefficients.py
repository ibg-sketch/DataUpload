"""
Derive formula coefficients for RAW (unnormalized) values
so they can be applied directly without StandardScaler
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

def derive_raw_formulas():
    """Derive formulas using raw values (no normalization)"""
    
    # Load data
    df_analysis = pd.read_csv('analysis_log.csv')
    df_analysis['timestamp'] = pd.to_datetime(df_analysis['timestamp'])
    
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_eff['timestamp_sent'] = pd.to_datetime(df_eff['timestamp_sent'])
    
    # Merge
    merged = []
    for _, sig in df_eff.iterrows():
        analysis = df_analysis[
            (df_analysis['symbol'] == sig['symbol']) &
            (df_analysis['timestamp'] <= sig['timestamp_sent']) &
            (df_analysis['timestamp'] >= sig['timestamp_sent'] - pd.Timedelta(minutes=2))
        ].tail(1)
        
        if len(analysis) > 0:
            row = analysis.iloc[0]
            merged.append({
                'verdict': sig['verdict'],
                'result': 1 if sig['result'] == 'WIN' else 0,
                'profit_pct': sig['profit_pct'],
                'rsi': row['rsi'],
                'ema_short': row['ema_short'],
                'ema_long': row['ema_long'],
                'price': row['price'],
                'volume': row['volume'],
                'volume_median': row['volume_median'],
                'atr': row['atr'],
            })
    
    df = pd.DataFrame(merged)
    
    # Feature engineering with RAW values
    df['volume_ratio'] = df['volume'] / df['volume_median']
    df['ema_diff_pct'] = ((df['ema_short'] - df['ema_long']) / df['price']) * 100  # as percentage
    df['atr_pct'] = (df['atr'] / df['price']) * 100  # as percentage
    
    # Split by direction
    df_long = df[df['verdict'] == 'BUY'].copy()
    df_short = df[df['verdict'] == 'SELL'].copy()
    
    print("="*90)
    print("RAW-VALUE FORMULAS (No Normalization Required)")
    print("="*90)
    
    # Train LONG formula on raw values
    features = ['rsi', 'ema_diff_pct', 'volume_ratio', 'atr_pct']
    
    X_long = df_long[features].fillna(0)
    y_long = df_long['result']
    
    X_train_l, X_test_l, y_train_l, y_test_l = train_test_split(
        X_long, y_long, test_size=0.2, random_state=42, stratify=y_long
    )
    
    lr_long = LogisticRegression(max_iter=1000, random_state=42)
    lr_long.fit(X_train_l, y_train_l)
    
    long_acc = lr_long.score(X_test_l, y_test_l)
    long_pred = lr_long.predict_proba(X_test_l)[:, 1]
    long_auc = roc_auc_score(y_test_l, long_pred)
    
    print("\n📈 LONG FORMULA (for RAW values):")
    print("-"*90)
    print("Signal_Long = ", end="")
    terms = []
    for feat, coef in zip(features, lr_long.coef_[0]):
        terms.append(f"{coef:+.6f} * {feat}")
    print(" \n              ".join(terms))
    print(f"              {lr_long.intercept_[0]:+.6f}")
    print(f"\nTest Accuracy: {long_acc:.4f}")
    print(f"ROC-AUC: {long_auc:.4f}")
    
    # Generate Python code
    print("\nPython Implementation:")
    print("```python")
    print("def signal_long(rsi, ema_diff_pct, volume_ratio, atr_pct):")
    print("    return (")
    for feat, coef in zip(features, lr_long.coef_[0]):
        print(f"        {coef:+.6f} * {feat}")
    print(f"        {lr_long.intercept_[0]:+.6f}")
    print("    )")
    print("```")
    
    # Train SHORT formula on raw values
    X_short = df_short[features].fillna(0)
    y_short = df_short['result']
    
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(
        X_short, y_short, test_size=0.2, random_state=42, stratify=y_short
    )
    
    lr_short = LogisticRegression(max_iter=1000, random_state=42)
    lr_short.fit(X_train_s, y_train_s)
    
    short_acc = lr_short.score(X_test_s, y_test_s)
    short_pred = lr_short.predict_proba(X_test_s)[:, 1]
    short_auc = roc_auc_score(y_test_s, short_pred)
    
    print("\n📉 SHORT FORMULA (for RAW values):")
    print("-"*90)
    print("Signal_Short = ", end="")
    terms = []
    for feat, coef in zip(features, lr_short.coef_[0]):
        terms.append(f"{coef:+.6f} * {feat}")
    print(" \n               ".join(terms))
    print(f"               {lr_short.intercept_[0]:+.6f}")
    print(f"\nTest Accuracy: {short_acc:.4f}")
    print(f"ROC-AUC: {short_auc:.4f}")
    
    # Generate Python code
    print("\nPython Implementation:")
    print("```python")
    print("def signal_short(rsi, ema_diff_pct, volume_ratio, atr_pct):")
    print("    return (")
    for feat, coef in zip(features, lr_short.coef_[0]):
        print(f"        {coef:+.6f} * {feat}")
    print(f"        {lr_short.intercept_[0]:+.6f}")
    print("    )")
    print("```")
    
    # Find optimal thresholds
    print("\n" + "="*90)
    print("OPTIMAL THRESHOLDS")
    print("="*90)
    
    # Test different thresholds on full datasets
    X_long_full = df_long[features].fillna(0)
    y_long_full = df_long['result']
    long_scores = lr_long.predict_proba(X_long_full)[:, 1]
    
    print("\n📈 LONG Signal Thresholds:")
    print("-"*90)
    for thresh in [0.2, 0.3, 0.4, 0.5, 0.6]:
        subset = y_long_full[long_scores > thresh]
        if len(subset) > 0:
            wr = subset.mean() * 100
            print(f"  Threshold > {thresh:.1f}: {wr:5.1f}% WR | {len(subset):3} signals")
    
    X_short_full = df_short[features].fillna(0)
    y_short_full = df_short['result']
    short_scores = lr_short.predict_proba(X_short_full)[:, 1]
    
    print("\n📉 SHORT Signal Thresholds:")
    print("-"*90)
    for thresh in [0.2, 0.3, 0.4, 0.5, 0.6]:
        subset = y_short_full[short_scores > thresh]
        if len(subset) > 0:
            wr = subset.mean() * 100
            print(f"  Threshold > {thresh:.1f}: {wr:5.1f}% WR | {len(subset):3} signals")
    
    print("\n" + "="*90)
    print("📝 NOTES")
    print("="*90)
    print("These formulas work directly on RAW values (no StandardScaler needed):")
    print("  - rsi: 0-100 range")
    print("  - ema_diff_pct: EMA difference as percentage (-10% to +10% typical)")
    print("  - volume_ratio: Current volume / median volume (0.5 to 3.0 typical)")
    print("  - atr_pct: ATR as percentage of price (0.1% to 5% typical)")

if __name__ == "__main__":
    derive_raw_formulas()
