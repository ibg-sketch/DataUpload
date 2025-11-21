"""
Directional Formula Analysis
Check if the optimal formula works for both LONG and SHORT signals
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

def analyze_by_direction():
    """Analyze formula performance split by LONG vs SHORT"""
    
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
                'cvd': row['cvd'],
                'oi_change_pct': row['oi_change_pct'],
                'volume': row['volume'],
                'volume_median': row['volume_median'],
                'rsi': row['rsi'],
                'price_vs_vwap_pct': row['price_vs_vwap_pct'],
                'ema_short': row['ema_short'],
                'ema_long': row['ema_long'],
                'atr': row['atr'],
                'price': row['price'],
            })
    
    df = pd.DataFrame(merged)
    
    # Feature engineering
    df['volume_ratio'] = df['volume'] / df['volume_median']
    df['vwap_dist_abs'] = abs(df['price_vs_vwap_pct'])
    df['ema_diff_pct'] = ((df['ema_short'] - df['ema_long']) / df['price']) * 100
    
    print("="*90)
    print("DIRECTIONAL FORMULA ANALYSIS: LONG vs SHORT")
    print("="*90)
    
    # Overall stats
    print(f"\n📊 OVERALL DATASET:")
    print(f"Total signals: {len(df)}")
    print(f"Win rate: {df['result'].mean()*100:.1f}%")
    
    # Split by direction (BUY = LONG, SELL = SHORT)
    df_long = df[df['verdict'] == 'BUY']
    df_short = df[df['verdict'] == 'SELL']
    
    print(f"\n📈 LONG SIGNALS:")
    print(f"Count: {len(df_long)}")
    print(f"Win rate: {df_long['result'].mean()*100:.1f}%")
    print(f"Avg profit: {df_long['profit_pct'].mean():+.2f}%")
    
    print(f"\n📉 SHORT SIGNALS:")
    print(f"Count: {len(df_short)}")
    print(f"Win rate: {df_short['result'].mean()*100:.1f}%")
    print(f"Avg profit: {df_short['profit_pct'].mean():+.2f}%")
    
    # Indicator correlations by direction
    print("\n" + "="*90)
    print("INDICATOR CORRELATIONS WITH WIN/LOSS BY DIRECTION")
    print("="*90)
    
    indicators = ['rsi', 'volume_ratio', 'oi_change_pct', 'vwap_dist_abs', 'ema_diff_pct', 'atr']
    
    print(f"\n{'Indicator':<20} | {'LONG Corr':<12} | {'SHORT Corr':<12} | {'Same Sign?'}")
    print("-"*90)
    
    for ind in indicators:
        corr_long = df_long[ind].corr(df_long['result'])
        corr_short = df_short[ind].corr(df_short['result'])
        same_sign = '✅ Yes' if (corr_long * corr_short) > 0 else '❌ No (OPPOSITE!)'
        print(f"{ind:<20} | {corr_long:+.4f}      | {corr_short:+.4f}      | {same_sign}")
    
    # Test formula on each direction
    print("\n" + "="*90)
    print("FORMULA PERFORMANCE BY DIRECTION")
    print("="*90)
    
    features = ['rsi', 'ema_diff_pct', 'volume_ratio', 'atr']
    
    # Train unified formula
    X_all = df[features].fillna(0)
    y_all = df['result']
    scaler = StandardScaler()
    X_all_scaled = scaler.fit_transform(X_all)
    
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_all_scaled, y_all)
    
    print("\n🔄 UNIFIED FORMULA (trained on all signals):")
    print("-"*90)
    for feat, coef in zip(features, lr.coef_[0]):
        print(f"  {feat:<20} : {coef:+.4f}")
    print(f"  Intercept: {lr.intercept_[0]:+.4f}")
    
    # Test on LONG signals
    X_long = df_long[features].fillna(0)
    y_long = df_long['result']
    X_long_scaled = scaler.transform(X_long)
    
    long_acc = lr.score(X_long_scaled, y_long)
    long_proba = lr.predict_proba(X_long_scaled)[:, 1]
    long_auc = roc_auc_score(y_long, long_proba)
    
    print(f"\n📈 Performance on LONG signals:")
    print(f"  Accuracy: {long_acc:.4f}")
    print(f"  ROC-AUC: {long_auc:.4f}")
    
    # Test on SHORT signals
    X_short = df_short[features].fillna(0)
    y_short = df_short['result']
    X_short_scaled = scaler.transform(X_short)
    
    short_acc = lr.score(X_short_scaled, y_short)
    short_proba = lr.predict_proba(X_short_scaled)[:, 1]
    short_auc = roc_auc_score(y_short, short_proba)
    
    print(f"\n📉 Performance on SHORT signals:")
    print(f"  Accuracy: {short_acc:.4f}")
    print(f"  ROC-AUC: {short_auc:.4f}")
    
    # Train separate formulas
    print("\n" + "="*90)
    print("SEPARATE FORMULAS FOR EACH DIRECTION")
    print("="*90)
    
    # LONG-specific formula
    scaler_long = StandardScaler()
    X_long_scaled_sep = scaler_long.fit_transform(X_long)
    lr_long = LogisticRegression(max_iter=1000)
    lr_long.fit(X_long_scaled_sep, y_long)
    
    print("\n📈 LONG-SPECIFIC FORMULA:")
    print("-"*90)
    for feat, coef in zip(features, lr_long.coef_[0]):
        print(f"  {feat:<20} : {coef:+.4f}")
    print(f"  Intercept: {lr_long.intercept_[0]:+.4f}")
    print(f"  Accuracy: {lr_long.score(X_long_scaled_sep, y_long):.4f}")
    
    # SHORT-specific formula
    scaler_short = StandardScaler()
    X_short_scaled_sep = scaler_short.fit_transform(X_short)
    lr_short = LogisticRegression(max_iter=1000)
    lr_short.fit(X_short_scaled_sep, y_short)
    
    print("\n📉 SHORT-SPECIFIC FORMULA:")
    print("-"*90)
    for feat, coef in zip(features, lr_short.coef_[0]):
        print(f"  {feat:<20} : {coef:+.4f}")
    print(f"  Intercept: {lr_short.intercept_[0]:+.4f}")
    print(f"  Accuracy: {lr_short.score(X_short_scaled_sep, y_short):.4f}")
    
    # Best parameter ranges by direction
    print("\n" + "="*90)
    print("OPTIMAL PARAMETER RANGES BY DIRECTION")
    print("="*90)
    
    print("\n📈 LONG SIGNALS - Best Conditions:")
    print("-"*90)
    
    # RSI for longs
    for low, high in [(0, 30), (30, 50), (50, 70), (70, 100)]:
        subset = df_long[(df_long['rsi'] >= low) & (df_long['rsi'] < high)]
        if len(subset) > 3:
            wr = subset['result'].mean() * 100
            print(f"  RSI {low:3}-{high:3}: {wr:5.1f}% WR | {len(subset):3} signals")
    
    # VWAP for longs
    print("\n  VWAP Distance:")
    for low, high in [(0, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 5.0)]:
        subset = df_long[(df_long['vwap_dist_abs'] >= low) & (df_long['vwap_dist_abs'] < high)]
        if len(subset) > 3:
            wr = subset['result'].mean() * 100
            print(f"    {low:.1f}%-{high:.1f}%: {wr:5.1f}% WR | {len(subset):3} signals")
    
    print("\n📉 SHORT SIGNALS - Best Conditions:")
    print("-"*90)
    
    # RSI for shorts
    for low, high in [(0, 30), (30, 50), (50, 70), (70, 100)]:
        subset = df_short[(df_short['rsi'] >= low) & (df_short['rsi'] < high)]
        if len(subset) > 3:
            wr = subset['result'].mean() * 100
            print(f"  RSI {low:3}-{high:3}: {wr:5.1f}% WR | {len(subset):3} signals")
    
    # VWAP for shorts
    print("\n  VWAP Distance:")
    for low, high in [(0, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 5.0)]:
        subset = df_short[(df_short['vwap_dist_abs'] >= low) & (df_short['vwap_dist_abs'] < high)]
        if len(subset) > 3:
            wr = subset['result'].mean() * 100
            print(f"    {low:.1f}%-{high:.1f}%: {wr:5.1f}% WR | {len(subset):3} signals")
    
    # Final recommendation
    print("\n" + "="*90)
    print("🎯 RECOMMENDATION")
    print("="*90)
    
    if abs(long_acc - short_acc) < 0.05:
        print("\n✅ UNIFIED FORMULA WORKS FOR BOTH DIRECTIONS")
        print("The formula performs similarly for LONG and SHORT signals.")
        print("You can use the same formula for both directions.")
    else:
        print("\n⚠️ CONSIDER SEPARATE FORMULAS")
        print(f"Performance gap: {abs(long_acc - short_acc):.2%}")
        print("Long and short signals may benefit from different formulas.")

if __name__ == "__main__":
    analyze_by_direction()
