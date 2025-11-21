"""
Comprehensive Multi-Variable Trading Policy Optimizer

Jointly optimizes:
- Indicator weights (CVD, OI, VWAP, Volume, Liquidations)
- Signal thresholds (min_score, min_confidence)
- Target sizing formula (ATR multiplier, market strength influence)
- Duration/TTL formula parameters

Uses time-aware cross-validation and offline simulation to find optimal policy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, classification_report
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("COMPREHENSIVE MULTI-VARIABLE POLICY OPTIMIZATION")
print("="*80)

# =============================================================================
# STEP 1: DATA UNIFICATION - Merge analysis_log with effectiveness_log
# =============================================================================

print("\nSTEP 1: Loading and merging datasets...")

# Load effectiveness log (outcomes)
effectiveness_df = pd.read_csv('effectiveness_log.csv', parse_dates=['timestamp_sent', 'timestamp_checked'])
print(f"Loaded {len(effectiveness_df)} signals from effectiveness_log.csv")

# Load analysis log (indicator values)
analysis_df = pd.read_csv('analysis_log.csv', parse_dates=['timestamp'])
print(f"Loaded {len(analysis_df)} analysis cycles from analysis_log.csv")

# Focus on recent data (last 11 hours)
cutoff_time = datetime.now() - timedelta(hours=11)
recent_eff = effectiveness_df[effectiveness_df['timestamp_sent'] >= cutoff_time].copy()
recent_analysis = analysis_df[analysis_df['timestamp'] >= cutoff_time].copy()

print(f"Filtered to {len(recent_eff)} recent signals")
print(f"Filtered to {len(recent_analysis)} recent analysis cycles")

# =============================================================================
# STEP 2: MERGE ON TIMESTAMP + SYMBOL + VERDICT
# =============================================================================

print("\nSTEP 2: Merging datasets on timestamp/symbol/verdict...")

# For each signal in effectiveness_log, find matching analysis cycle
# Match within 2-minute window (signals are sent based on analysis)
merged_data = []

for _, sig in recent_eff.iterrows():
    # Find analysis cycles for this symbol around this time
    time_window = timedelta(minutes=2)
    candidates = recent_analysis[
        (recent_analysis['symbol'] == sig['symbol']) &
        (recent_analysis['verdict'] == sig['verdict']) &
        (recent_analysis['timestamp'] >= sig['timestamp_sent'] - time_window) &
        (recent_analysis['timestamp'] <= sig['timestamp_sent'] + time_window)
    ]
    
    if len(candidates) > 0:
        # Take the closest match
        candidates = candidates.copy()
        candidates['time_diff'] = abs((candidates['timestamp'] - sig['timestamp_sent']).dt.total_seconds())
        best_match = candidates.loc[candidates['time_diff'].idxmin()]
        
        # Merge
        merged_row = {
            'timestamp': sig['timestamp_sent'],
            'symbol': sig['symbol'],
            'verdict': sig['verdict'],
            'result': sig['result'],
            'entry_price': sig['entry_price'],
            'target_min': sig['target_min'],
            'target_max': sig['target_max'],
            'highest_reached': sig['highest_reached'],
            'lowest_reached': sig['lowest_reached'],
            'duration_minutes': sig['duration_minutes'],
            # Indicator values from analysis
            'cvd': best_match['cvd'],
            'oi': best_match['oi'],
            'oi_change': best_match['oi_change'],
            'oi_change_pct': best_match['oi_change_pct'],
            'price_vs_vwap_pct': best_match['price_vs_vwap_pct'],
            'volume_spike': best_match['volume_spike'],
            'liq_ratio': best_match['liq_ratio'],
            'rsi': best_match['rsi'],
            'atr': best_match['atr'],
            'ttl_minutes': best_match['ttl_minutes'],
            'base_interval': best_match['base_interval'],
            'score': best_match['score'],
            'confidence': best_match['confidence'],
        }
        merged_data.append(merged_row)

merged_df = pd.DataFrame(merged_data)
print(f"Successfully merged {len(merged_df)} signals with indicator values")

if len(merged_df) == 0:
    print("ERROR: No matches found. Check timestamp alignment.")
    exit(1)

# =============================================================================
# STEP 3: FEATURE ENGINEERING
# =============================================================================

print("\nSTEP 3: Engineering features...")

# Calculate target percentage (what we asked for)
def calc_target_pct(row):
    entry = row['entry_price']
    if row['verdict'] == 'BUY':
        return ((row['target_min'] - entry) / entry) * 100
    else:
        return ((entry - row['target_max']) / entry) * 100

merged_df['target_pct'] = merged_df.apply(calc_target_pct, axis=1)

# Calculate actual move (what happened)
def calc_actual_move(row):
    entry = row['entry_price']
    if row['verdict'] == 'BUY':
        return ((row['highest_reached'] - entry) / entry) * 100
    else:
        return ((entry - row['lowest_reached']) / entry) * 100

merged_df['actual_move_pct'] = merged_df.apply(calc_actual_move, axis=1)

# Calculate market strength multiplier (from volume, CVD, OI alignment)
def calc_market_strength(row):
    strength = 1.0
    
    # Volume boost (up to 0.4x)
    if row['volume_spike'] > 1.5:
        strength += 0.4 * min((row['volume_spike'] - 1.0) / 2.0, 1.0)
    
    # OI alignment boost (0.35x if aligned with verdict)
    if row['verdict'] == 'BUY' and row['oi_change_pct'] > 0:
        strength += 0.35 * min(abs(row['oi_change_pct']) / 5.0, 1.0)
    elif row['verdict'] == 'SELL' and row['oi_change_pct'] < 0:
        strength += 0.35 * min(abs(row['oi_change_pct']) / 5.0, 1.0)
    
    # CVD alignment boost (0.25x if aligned)
    # Note: CVD values vary by symbol, normalize by entry price
    cvd_pct = (row['cvd'] / row['entry_price']) * 100 if row['entry_price'] > 0 else 0
    if row['verdict'] == 'BUY' and cvd_pct > 0:
        strength += 0.25 * min(abs(cvd_pct) / 0.1, 1.0)
    elif row['verdict'] == 'SELL' and cvd_pct < 0:
        strength += 0.25 * min(abs(cvd_pct) / 0.1, 1.0)
    
    return min(strength, 2.5)  # Cap at 2.5x

merged_df['market_strength'] = merged_df.apply(calc_market_strength, axis=1)

# Normalize CVD by entry price (make it symbol-independent)
merged_df['cvd_pct'] = (merged_df['cvd'] / merged_df['entry_price']) * 100

# Calculate ATR as percentage of price
merged_df['atr_pct'] = (merged_df['atr'] / merged_df['entry_price']) * 100

# Outcome label
merged_df['win'] = (merged_df['result'] == 'WIN').astype(int)

print(f"Created features:")
print(f"  - target_pct: {merged_df['target_pct'].mean():.3f}% avg")
print(f"  - actual_move_pct: {merged_df['actual_move_pct'].mean():.3f}% avg")
print(f"  - market_strength: {merged_df['market_strength'].mean():.2f}x avg")
print(f"  - cvd_pct: {merged_df['cvd_pct'].mean():.4f}% avg")
print(f"  - atr_pct: {merged_df['atr_pct'].mean():.3f}% avg")

# =============================================================================
# STEP 4: FEATURE SELECTION
# =============================================================================

print("\nSTEP 4: Selecting features for modeling...")

# Core indicator features
feature_cols = [
    'cvd_pct',              # Normalized CVD
    'oi_change_pct',        # OI change percentage
    'price_vs_vwap_pct',    # VWAP deviation
    'volume_spike',         # Volume vs median
    'liq_ratio',            # Liquidation ratio
    'rsi',                  # RSI
    'atr_pct',              # ATR as % of price
    'market_strength',      # Calculated market strength
    'target_pct',           # Target size we set
    'duration_minutes',     # How long we waited
]

# Add verdict encoding (BUY=1, SELL=0)
merged_df['verdict_buy'] = (merged_df['verdict'] == 'BUY').astype(int)
feature_cols.append('verdict_buy')

# Check for missing values
print(f"\nMissing values:")
for col in feature_cols:
    missing = merged_df[col].isna().sum()
    if missing > 0:
        print(f"  {col}: {missing} ({missing/len(merged_df)*100:.1f}%)")

# Fill missing values with median
for col in feature_cols:
    if merged_df[col].isna().sum() > 0:
        merged_df[col].fillna(merged_df[col].median(), inplace=True)

print(f"\nFinal dataset: {len(merged_df)} samples with {len(feature_cols)} features")
print(f"Wins: {merged_df['win'].sum()} ({merged_df['win'].mean()*100:.1f}%)")
print(f"Losses: {(1-merged_df['win']).sum()} ({(1-merged_df['win']).mean()*100:.1f}%)")

# =============================================================================
# STEP 5: CORRELATION ANALYSIS
# =============================================================================

print("\n" + "="*80)
print("CORRELATION ANALYSIS: Which features predict wins?")
print("="*80)

correlations = []
for col in feature_cols:
    corr = merged_df[col].corr(merged_df['win'])
    correlations.append({'feature': col, 'correlation': corr})

corr_df = pd.DataFrame(correlations).sort_values('correlation', ascending=False)

print(f"\n{'Feature':<25} {'Correlation with WIN':<20} {'Interpretation'}")
print("-"*80)
for _, row in corr_df.iterrows():
    corr = row['correlation']
    if abs(corr) > 0.2:
        strength = "🔥 STRONG"
    elif abs(corr) > 0.1:
        strength = "⚡ MODERATE"
    else:
        strength = "📊 WEAK"
    
    direction = "↑ Positive" if corr > 0 else "↓ Negative"
    print(f"{row['feature']:<25} {corr:>8.3f} {strength:<15} {direction}")

# =============================================================================
# STEP 6: WIN PROBABILITY MODEL - BASELINE LOGISTIC REGRESSION
# =============================================================================

print("\n" + "="*80)
print("STEP 6: Training Win Probability Model (Logistic Regression)")
print("="*80)

# Prepare features
X = merged_df[feature_cols].values
y = merged_df['win'].values

# Standardize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train logistic regression with ElasticNet
lr_model = LogisticRegression(
    penalty='elasticnet',
    solver='saga',
    l1_ratio=0.5,
    max_iter=1000,
    random_state=42
)

lr_model.fit(X_scaled, y)

# Get feature importance (coefficients)
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'coefficient': lr_model.coef_[0]
}).sort_values('coefficient', ascending=False)

print(f"\n📊 LOGISTIC REGRESSION FEATURE IMPORTANCE:")
print(f"\n{'Feature':<25} {'Coefficient':<15} {'Impact'}")
print("-"*70)
for _, row in feature_importance.iterrows():
    coef = row['coefficient']
    if abs(coef) > 0.5:
        impact = "🔥 HIGH"
    elif abs(coef) > 0.2:
        impact = "⚡ MODERATE"
    else:
        impact = "📊 LOW"
    
    print(f"{row['feature']:<25} {coef:>8.3f} {impact}")

# Predict on training data (for now)
y_pred_proba = lr_model.predict_proba(X_scaled)[:, 1]
y_pred = (y_pred_proba >= 0.5).astype(int)

# Metrics
accuracy = (y_pred == y).mean()
auc = roc_auc_score(y, y_pred_proba)

print(f"\n📈 MODEL PERFORMANCE (Training):")
print(f"Accuracy: {accuracy*100:.1f}%")
print(f"AUC-ROC: {auc:.3f}")

# =============================================================================
# STEP 7: SAVE DATASET FOR FURTHER ANALYSIS
# =============================================================================

print("\n" + "="*80)
print("STEP 7: Saving unified dataset...")
print("="*80)

# Save merged dataset
output_file = 'unified_dataset.csv'
merged_df.to_csv(output_file, index=False)
print(f"✅ Saved {len(merged_df)} samples to {output_file}")

# Save feature importance
importance_file = 'feature_importance.csv'
feature_importance.to_csv(importance_file, index=False)
print(f"✅ Saved feature importance to {importance_file}")

print("\n" + "="*80)
print("DATASET PREPARATION COMPLETE")
print("="*80)
print(f"\nNext steps:")
print(f"1. Build offline policy simulator")
print(f"2. Search for optimal parameters (weights, thresholds, target formula)")
print(f"3. Validate with time-series cross-validation")
