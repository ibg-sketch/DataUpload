#!/usr/bin/env python3
"""
Correlation Analysis: Formula Predictions vs Actual Results (Last Hour)
Analyzes how well the formula predicts actual price movement
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats

def analyze_formula_correlation():
    """Analyze correlation between formula predictions and actual results"""
    
    # Read effectiveness log (only first 16 columns to handle old format)
    # New format has 21 columns (added rsi, ema_short, ema_long, adx, funding_rate)
    # but we only need the first 16 for correlation analysis
    col_names = ['timestamp_sent', 'timestamp_checked', 'symbol', 'verdict', 'confidence',
                 'entry_price', 'target_min', 'target_max', 'duration_minutes',
                 'result', 'highest_reached', 'lowest_reached', 'final_price', 
                 'profit_pct', 'duration_actual', 'market_strength']
    df = pd.read_csv('effectiveness_log.csv', names=col_names, usecols=range(16), header=None)
    
    # Parse timestamps
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    df['timestamp_checked'] = pd.to_datetime(df['timestamp_checked'])
    
    # Filter last hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    df_hour = df[df['timestamp_sent'] >= one_hour_ago].copy()
    
    print("="*70)
    print("CORRELATION ANALYSIS: Formula vs Reality (Last Hour)")
    print("="*70)
    print(f"Analysis period: {one_hour_ago.strftime('%H:%M:%S')} - {datetime.now().strftime('%H:%M:%S')}")
    print(f"Total signals: {len(df_hour)}")
    print()
    
    # Remove duplicates (same timestamp + symbol)
    df_hour['dup_key'] = df_hour['timestamp_sent'].astype(str) + '_' + df_hour['symbol']
    df_unique = df_hour.drop_duplicates(subset='dup_key', keep='first').copy()
    print(f"After deduplication: {len(df_unique)} unique signals")
    print()
    
    # Filter only completed signals (exclude CANCELLED)
    df_completed = df_unique[df_unique['result'] != 'CANCELLED'].copy()
    print(f"Completed signals: {len(df_completed)} (excluding CANCELLED)")
    
    if len(df_completed) == 0:
        print("\n⚠️  No completed signals yet. All signals are either active or cancelled.")
        return
    
    # Calculate predicted movement magnitude
    # For SELL: target_min = entry * (1 - max_pct/100), so max_pct = (entry - target_min) / entry * 100
    # We'll use the minimum target as the conservative prediction
    df_completed['predicted_pct'] = 0.0
    
    for idx, row in df_completed.iterrows():
        entry = row['entry_price']
        target_min = row['target_min']
        
        if row['verdict'] == 'SELL':
            # For SELL: predicted drop = (entry - target_min) / entry * 100
            predicted = ((entry - target_min) / entry) * 100
        else:  # BUY
            # For BUY: predicted rise = (target_min - entry) / entry * 100
            predicted = ((target_min - entry) / entry) * 100
        
        df_completed.at[idx, 'predicted_pct'] = predicted
    
    # Actual movement
    df_completed['actual_pct'] = df_completed['profit_pct']
    
    # Analysis
    print("\n" + "="*70)
    print("PREDICTED vs ACTUAL MOVEMENT")
    print("="*70)
    
    # Remove any rows with NaN
    df_analysis = df_completed[['symbol', 'verdict', 'confidence', 'predicted_pct', 'actual_pct', 'result', 'market_strength']].dropna()
    
    if len(df_analysis) == 0:
        print("No valid data for analysis")
        return
    
    # Overall statistics
    predicted_mean = df_analysis['predicted_pct'].mean()
    actual_mean = df_analysis['actual_pct'].mean()
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Predicted movement: {predicted_mean:.2f}% (average)")
    print(f"   Actual movement:    {actual_mean:.2f}% (average)")
    print(f"   Prediction error:   {abs(predicted_mean - actual_mean):.2f}%")
    
    # Correlation
    if len(df_analysis) >= 3:
        correlation = df_analysis['predicted_pct'].corr(df_analysis['actual_pct'])
        r_squared = correlation ** 2
        
        # Spearman rank correlation (non-parametric)
        spearman_corr, spearman_p = stats.spearmanr(df_analysis['predicted_pct'], df_analysis['actual_pct'])
        
        print(f"\n📈 CORRELATION METRICS:")
        print(f"   Pearson correlation: {correlation:.4f}")
        print(f"   R²:                  {r_squared:.4f} ({r_squared*100:.2f}% variance explained)")
        print(f"   Spearman rank:       {spearman_corr:.4f} (p={spearman_p:.4f})")
        
        if r_squared < 0.1:
            print(f"   ⚠️  R²={r_squared:.3f} means formula explains only {r_squared*100:.1f}% of price movement!")
        elif r_squared < 0.3:
            print(f"   ⚡ R²={r_squared:.3f} - weak correlation, needs improvement")
        else:
            print(f"   ✅ R²={r_squared:.3f} - moderate to strong correlation")
    else:
        print(f"\n⚠️  Need at least 3 samples for correlation (have {len(df_analysis)})")
    
    # Win rate
    wins = len(df_analysis[df_analysis['result'] == 'WIN'])
    losses = len(df_analysis[df_analysis['result'] == 'LOSS'])
    win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
    
    print(f"\n🎯 SIGNAL EFFECTIVENESS:")
    print(f"   WIN:  {wins}")
    print(f"   LOSS: {losses}")
    print(f"   Win Rate: {win_rate:.1f}%")
    
    # Detailed breakdown
    print("\n" + "="*70)
    print("DETAILED SIGNAL BREAKDOWN")
    print("="*70)
    print(f"{'Symbol':<10} {'Pred%':<8} {'Actual%':<9} {'Error%':<8} {'Result':<6} {'Strength':<8}")
    print("-"*70)
    
    for _, row in df_analysis.iterrows():
        error = abs(row['predicted_pct'] - row['actual_pct'])
        print(f"{row['symbol']:<10} {row['predicted_pct']:>6.2f}%  {row['actual_pct']:>7.2f}%  {error:>6.2f}%  {row['result']:<6} {row['market_strength']:>6.2f}")
    
    # Accuracy analysis
    print("\n" + "="*70)
    print("PREDICTION ACCURACY ANALYSIS")
    print("="*70)
    
    # Calculate if actual movement exceeded predicted minimum
    df_analysis['target_hit'] = df_analysis['actual_pct'] >= df_analysis['predicted_pct']
    hit_rate = df_analysis['target_hit'].sum() / len(df_analysis) * 100
    
    print(f"Target Hit Rate: {hit_rate:.1f}% ({df_analysis['target_hit'].sum()}/{len(df_analysis)} signals)")
    print(f"   Formula predicted minimum {predicted_mean:.2f}% movement")
    print(f"   Market delivered average {actual_mean:.2f}% movement")
    
    # Overperformance vs underperformance
    overperform = len(df_analysis[df_analysis['actual_pct'] > df_analysis['predicted_pct']])
    underperform = len(df_analysis[df_analysis['actual_pct'] < df_analysis['predicted_pct']])
    
    print(f"\n   Overperformed: {overperform} signals ({overperform/len(df_analysis)*100:.1f}%)")
    print(f"   Underperformed: {underperform} signals ({underperform/len(df_analysis)*100:.1f}%)")
    
    # Market strength correlation
    if len(df_analysis) >= 3:
        strength_corr = df_analysis['market_strength'].corr(df_analysis['actual_pct'])
        print(f"\n📊 Market Strength vs Actual Movement:")
        print(f"   Correlation: {strength_corr:.4f}")
        if abs(strength_corr) < 0.2:
            print(f"   ⚠️  Weak correlation - market_strength multiplier not effective")
        elif abs(strength_corr) > 0.5:
            print(f"   ✅ Strong correlation - market_strength multiplier is effective")
    
    print("\n" + "="*70)
    print("🔍 INSIGHTS:")
    print("="*70)
    
    if len(df_analysis) >= 3:
        if r_squared < 0.1:
            print("❌ Formula has very weak predictive power (R² < 0.1)")
            print("   Current factors (ATR, CVD, OI, Volume, VWAP) explain <10% of movement")
            print("   💡 SOLUTION: Add RSI, EMA, ADX, Funding Rate to improve R² to 0.2-0.4")
        
        if hit_rate < 50:
            print(f"⚠️  Low target hit rate ({hit_rate:.1f}%)")
            print("   Formula is overestimating expected movement")
        elif hit_rate > 80:
            print(f"⚡ High target hit rate ({hit_rate:.1f}%)")
            print("   Formula might be too conservative")
        
        if win_rate > 70:
            print(f"✅ Strong win rate ({win_rate:.1f}%)")
        elif win_rate < 50:
            print(f"❌ Low win rate ({win_rate:.1f}%)")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    analyze_formula_correlation()
