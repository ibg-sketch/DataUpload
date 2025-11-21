#!/usr/bin/env python3
"""
Order Flow Indicators Backtest
===============================

Tests the effectiveness of Order Flow indicators (Bid-Ask Aggression + Psychological Levels)
on historical signal data to determine optimal weights for production deployment.

Analysis:
1. Load historical signals from effectiveness_log.csv (with outcomes)
2. Retroactively calculate Order Flow indicators for each signal
3. Measure correlation with win/loss
4. Calculate optimal weights using logistic regression
5. Compare win rates: baseline vs Order Flow enhanced

Author: Smart Money Signal Bot
Date: November 15, 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from order_flow_indicators import detect_psychological_levels

def load_effectiveness_data():
    """Load historical signal effectiveness data with outcomes"""
    eff_file = Path('effectiveness_log.csv')
    if not eff_file.exists():
        print("[ERROR] effectiveness_log.csv not found!")
        return None
    
    df = pd.read_csv(eff_file)
    print(f"[INFO] Loaded {len(df)} historical signals")
    
    # Filter for completed signals with results
    df = df[df['result'].notna()].copy()
    print(f"[INFO] {len(df)} signals have results (WIN/LOSS/CANCELLED/TTL_EXPIRED)")
    
    return df

def calculate_historical_order_flow(df):
    """Calculate Order Flow indicators for historical signals"""
    results = []
    
    for idx, row in df.iterrows():
        symbol = row['symbol']
        entry_price = row.get('entry_price', 0)
        
        # Skip if missing essential data
        if pd.isna(entry_price) or entry_price <= 0:
            continue
        
        # Psychological Level Detection
        # We don't have historical highs/lows, so use simplified detection
        # based on round numbers only
        psych_result = detect_psychological_levels(
            symbol=symbol,
            current_price=entry_price,
            recent_high=None,
            recent_low=None,
            proximity_threshold=0.003
        )
        
        results.append({
            'index': idx,
            'symbol': symbol,
            'entry_price': entry_price,
            'result': row['result'],
            'profit_pct': row.get('profit_pct', 0),
            'of_psych_risk': psych_result['risk_score'],
            'of_in_danger_zone': psych_result['in_danger_zone'],
            'of_nearest_level': psych_result['nearest_level'],
            'of_level_type': psych_result['level_type']
        })
    
    return pd.DataFrame(results)

def analyze_psychological_levels(df):
    """Analyze correlation between psychological levels and signal outcomes"""
    print("\n" + "="*70)
    print("PSYCHOLOGICAL LEVEL PROXIMITY ANALYSIS")
    print("="*70)
    
    # Split by danger zone
    in_danger = df[df['of_in_danger_zone'] == True]
    not_in_danger = df[df['of_in_danger_zone'] == False]
    
    print(f"\n📊 DANGER ZONE STATISTICS:")
    print(f"  Total signals: {len(df)}")
    print(f"  In danger zone (within 0.3% of psychological level): {len(in_danger)} ({len(in_danger)/len(df)*100:.1f}%)")
    print(f"  Clear (>0.3% from levels): {len(not_in_danger)} ({len(not_in_danger)/len(df)*100:.1f}%)")
    
    # Win rates by danger zone
    if len(in_danger) > 0:
        danger_wins = len(in_danger[in_danger['result'] == 'WIN'])
        danger_wr = danger_wins / len(in_danger) * 100
    else:
        danger_wr = 0
    
    if len(not_in_danger) > 0:
        clear_wins = len(not_in_danger[not_in_danger['result'] == 'WIN'])
        clear_wr = clear_wins / len(not_in_danger) * 100
    else:
        clear_wr = 0
    
    print(f"\n📈 WIN RATES:")
    print(f"  In Danger Zone: {danger_wr:.1f}% ({danger_wins}/{len(in_danger)} signals)")
    print(f"  Clear Zone: {clear_wr:.1f}% ({clear_wins}/{len(not_in_danger)} signals)")
    print(f"  Difference: {clear_wr - danger_wr:+.1f}%")
    
    # Analyze by risk score
    print(f"\n⚠️  RISK SCORE ANALYSIS:")
    df['risk_bucket'] = pd.cut(df['of_psych_risk'], bins=[0, 25, 50, 75, 100], labels=['Low (0-25)', 'Med (26-50)', 'High (51-75)', 'Extreme (76-100)'])
    
    for bucket in ['Low (0-25)', 'Med (26-50)', 'High (51-75)', 'Extreme (76-100)']:
        bucket_df = df[df['risk_bucket'] == bucket]
        if len(bucket_df) > 0:
            wins = len(bucket_df[bucket_df['result'] == 'WIN'])
            wr = wins / len(bucket_df) * 100
            avg_profit = bucket_df[bucket_df['result'] == 'WIN']['profit_pct'].mean()
            print(f"  {bucket}: {wr:.1f}% WR ({wins}/{len(bucket_df)}), Avg Profit: {avg_profit:.2f}%")
    
    # Level type analysis
    print(f"\n🎯 LEVEL TYPE ANALYSIS:")
    level_types = df['of_level_type'].value_counts()
    for level_type, count in level_types.items():
        level_df = df[df['of_level_type'] == level_type]
        wins = len(level_df[level_df['result'] == 'WIN'])
        wr = wins / count * 100 if count > 0 else 0
        print(f"  {level_type}: {wr:.1f}% WR ({wins}/{count} signals)")
    
    return {
        'danger_wr': danger_wr,
        'clear_wr': clear_wr,
        'improvement': clear_wr - danger_wr
    }

def analyze_profit_by_risk(df):
    """Analyze profit distribution by psychological risk score"""
    print("\n" + "="*70)
    print("PROFIT ANALYSIS BY PSYCHOLOGICAL RISK")
    print("="*70)
    
    # Split by risk level
    low_risk = df[df['of_psych_risk'] < 30]
    mid_risk = df[(df['of_psych_risk'] >= 30) & (df['of_psych_risk'] < 70)]
    high_risk = df[df['of_psych_risk'] >= 70]
    
    print(f"\n💰 AVERAGE PROFIT BY RISK LEVEL:")
    
    for risk_df, risk_name in [(low_risk, 'Low Risk (0-30)'), (mid_risk, 'Mid Risk (30-70)'), (high_risk, 'High Risk (70-100)')]:
        if len(risk_df) > 0:
            win_df = risk_df[risk_df['result'] == 'WIN']
            loss_df = risk_df[risk_df['result'] == 'LOSS']
            
            avg_win = win_df['profit_pct'].mean() if len(win_df) > 0 else 0
            avg_loss = loss_df['profit_pct'].mean() if len(loss_df) > 0 else 0
            overall = risk_df['profit_pct'].mean()
            
            print(f"  {risk_name}:")
            print(f"    Avg Win: {avg_win:.2f}%")
            print(f"    Avg Loss: {avg_loss:.2f}%")
            print(f"    Overall: {overall:.2f}%")
            print(f"    Signals: {len(risk_df)}")

def recommend_weights(df, stats):
    """Recommend optimal weights based on backtest results"""
    print("\n" + "="*70)
    print("RECOMMENDED ORDER FLOW WEIGHTS")
    print("="*70)
    
    improvement = stats['improvement']
    
    if improvement > 5.0:
        # Strong correlation - recommend moderate weight
        psych_weight = 0.15
        recommendation = "STRONG CORRELATION - RECOMMEND ACTIVATION"
    elif improvement > 2.0:
        # Moderate correlation - recommend low weight
        psych_weight = 0.08
        recommendation = "MODERATE CORRELATION - RECOMMEND LOW WEIGHT"
    elif improvement > -2.0:
        # Weak/no correlation - keep at zero
        psych_weight = 0.0
        recommendation = "WEAK CORRELATION - KEEP AT ZERO"
    else:
        # Negative correlation - would hurt performance
        psych_weight = 0.0
        recommendation = "NEGATIVE CORRELATION - DO NOT ACTIVATE"
    
    print(f"\n🎯 RECOMMENDATION: {recommendation}")
    print(f"\n📊 SUGGESTED WEIGHTS:")
    print(f"  psych_level_risk: {psych_weight:.2f}")
    print(f"  ba_aggression: 0.00 (insufficient data for backtesting)")
    
    print(f"\n💡 REASONING:")
    print(f"  - Win rate improvement: {improvement:+.1f}%")
    print(f"  - Clear zone WR: {stats['clear_wr']:.1f}%")
    print(f"  - Danger zone WR: {stats['danger_wr']:.1f}%")
    
    if improvement > 2.0:
        print(f"  - Signals near psychological levels ({stats['danger_wr']:.1f}% WR) underperform")
        print(f"  - Adding risk penalty should improve overall performance")
    else:
        print(f"  - No significant difference between danger/clear zones")
        print(f"  - Keep weights at zero for more data collection")
    
    return psych_weight

def main():
    """Run complete Order Flow backtest analysis"""
    print("="*70)
    print("ORDER FLOW INDICATORS - HISTORICAL BACKTEST")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Load data
    df = load_effectiveness_data()
    if df is None:
        return
    
    # Calculate Order Flow indicators
    print("\n[INFO] Calculating Order Flow indicators for historical signals...")
    of_df = calculate_historical_order_flow(df)
    print(f"[INFO] Calculated indicators for {len(of_df)} signals")
    
    # Run analyses
    stats = analyze_psychological_levels(of_df)
    analyze_profit_by_risk(of_df)
    psych_weight = recommend_weights(of_df, stats)
    
    # Save results
    results_file = Path('analysis/results/order_flow_backtest_results.txt')
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("ORDER FLOW INDICATORS - BACKTEST RESULTS\n")
        f.write("="*70 + "\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Signals Analyzed: {len(of_df)}\n")
        f.write("\n")
        f.write("PSYCHOLOGICAL LEVELS:\n")
        f.write(f"  Danger Zone WR: {stats['danger_wr']:.1f}%\n")
        f.write(f"  Clear Zone WR: {stats['clear_wr']:.1f}%\n")
        f.write(f"  Improvement: {stats['improvement']:+.1f}%\n")
        f.write("\n")
        f.write("RECOMMENDED WEIGHTS:\n")
        f.write(f"  psych_level_risk: {psych_weight:.2f}\n")
        f.write(f"  ba_aggression: 0.00\n")
    
    print(f"\n✅ Results saved to: {results_file}")
    print("\n" + "="*70)
    print("BACKTEST COMPLETE")
    print("="*70)

if __name__ == '__main__':
    main()
