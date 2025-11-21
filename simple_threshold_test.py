#!/usr/bin/env python3
"""
Simple test: What if we just changed thresholds to 0.55/0.60?
Use existing confidence values, don't recalculate
"""
import pandas as pd
from datetime import datetime, timedelta

def test_thresholds():
    print("="*80)
    print("SIMPLE THRESHOLD TEST: 0.55/0.60 vs OLD")
    print("="*80)
    
    # Load effectiveness data
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    # Filter last 2 days
    cutoff = datetime.now() - timedelta(days=2)
    df = df[df['timestamp_sent'] >= cutoff]
    
    print(f"\n📊 Dataset: {len(df)} signals from last 2 days\n")
    
    # Define thresholds
    OLD_BUY = 0.68
    OLD_SELL = 0.72
    NEW_BUY = 0.55
    NEW_SELL = 0.60
    
    # Filter by OLD thresholds
    old_buy = df[(df['verdict'] == 'BUY') & (df['confidence'] >= OLD_BUY)]
    old_sell = df[(df['verdict'] == 'SELL') & (df['confidence'] >= OLD_SELL)]
    old_filtered = pd.concat([old_buy, old_sell])
    
    # Filter by NEW thresholds  
    new_buy = df[(df['verdict'] == 'BUY') & (df['confidence'] >= NEW_BUY)]
    new_sell = df[(df['verdict'] == 'SELL') & (df['confidence'] >= NEW_SELL)]
    new_filtered = pd.concat([new_buy, new_sell])
    
    # Calculate win rates
    print("="*80)
    print("RESULTS")
    print("="*80)
    
    # OLD thresholds
    old_wins = len(old_filtered[old_filtered['result'] == 'WIN'])
    old_total = len(old_filtered)
    old_wr = old_wins / old_total if old_total > 0 else 0
    
    # NEW thresholds
    new_wins = len(new_filtered[new_filtered['result'] == 'WIN'])
    new_total = len(new_filtered)
    new_wr = new_wins / new_total if new_total > 0 else 0
    
    # ALL signals (no filtering)
    all_wins = len(df[df['result'] == 'WIN'])
    all_total = len(df)
    all_wr = all_wins / all_total if all_total > 0 else 0
    
    print(f"\n{'Configuration':<25} {'Signals':<10} {'Wins':<10} {'Win Rate'}")
    print("-"*80)
    print(f"{'ALL (no filter)':<25} {all_total:<10} {all_wins:<10} {all_wr:.1%}")
    print(f"{'OLD (0.68/0.72)':<25} {old_total:<10} {old_wins:<10} {old_wr:.1%}")
    print(f"{'NEW (0.55/0.60)':<25} {new_total:<10} {new_wins:<10} {new_wr:.1%}")
    
    print("\n" + "="*80)
    print("BUY vs SELL BREAKDOWN")
    print("="*80)
    
    # OLD
    old_buy_wins = len(old_buy[old_buy['result'] == 'WIN'])
    old_buy_wr = old_buy_wins / len(old_buy) if len(old_buy) > 0 else 0
    old_sell_wins = len(old_sell[old_sell['result'] == 'WIN'])
    old_sell_wr = old_sell_wins / len(old_sell) if len(old_sell) > 0 else 0
    
    # NEW
    new_buy_wins = len(new_buy[new_buy['result'] == 'WIN'])
    new_buy_wr = new_buy_wins / len(new_buy) if len(new_buy) > 0 else 0
    new_sell_wins = len(new_sell[new_sell['result'] == 'WIN'])
    new_sell_wr = new_sell_wins / len(new_sell) if len(new_sell) > 0 else 0
    
    print(f"\n{'Type':<10} {'Config':<15} {'Signals':<10} {'Wins':<10} {'WR'}")
    print("-"*80)
    print(f"{'BUY':<10} {'OLD (0.68)':<15} {len(old_buy):<10} {old_buy_wins:<10} {old_buy_wr:.1%}")
    print(f"{'BUY':<10} {'NEW (0.55)':<15} {len(new_buy):<10} {new_buy_wins:<10} {new_buy_wr:.1%}")
    print()
    print(f"{'SELL':<10} {'OLD (0.72)':<15} {len(old_sell):<10} {old_sell_wins:<10} {old_sell_wr:.1%}")
    print(f"{'SELL':<10} {'NEW (0.60)':<15} {len(new_sell):<10} {new_sell_wins:<10} {new_sell_wr:.1%}")
    
    # Confidence distribution
    print("\n" + "="*80)
    print("CONFIDENCE DISTRIBUTION")
    print("="*80)
    
    print(f"\nBUY signals by confidence range:")
    buy_signals = df[df['verdict'] == 'BUY']
    print(f"  0.25-0.35: {len(buy_signals[(buy_signals['confidence'] >= 0.25) & (buy_signals['confidence'] < 0.35)])} signals")
    print(f"  0.35-0.45: {len(buy_signals[(buy_signals['confidence'] >= 0.35) & (buy_signals['confidence'] < 0.45)])} signals")
    print(f"  0.45-0.55: {len(buy_signals[(buy_signals['confidence'] >= 0.45) & (buy_signals['confidence'] < 0.55)])} signals")
    print(f"  0.55-0.65: {len(buy_signals[(buy_signals['confidence'] >= 0.55) & (buy_signals['confidence'] < 0.65)])} signals ← NEW threshold")
    print(f"  0.65-0.68: {len(buy_signals[(buy_signals['confidence'] >= 0.65) & (buy_signals['confidence'] < 0.68)])} signals")
    print(f"  0.68+:     {len(buy_signals[buy_signals['confidence'] >= 0.68])} signals ← OLD threshold")
    
    print(f"\nSELL signals by confidence range:")
    sell_signals = df[df['verdict'] == 'SELL']
    print(f"  0.40-0.50: {len(sell_signals[(sell_signals['confidence'] >= 0.40) & (sell_signals['confidence'] < 0.50)])} signals")
    print(f"  0.50-0.60: {len(sell_signals[(sell_signals['confidence'] >= 0.50) & (sell_signals['confidence'] < 0.60)])} signals")
    print(f"  0.60-0.70: {len(sell_signals[(sell_signals['confidence'] >= 0.60) & (sell_signals['confidence'] < 0.70)])} signals ← NEW threshold")
    print(f"  0.70-0.72: {len(sell_signals[(sell_signals['confidence'] >= 0.70) & (sell_signals['confidence'] < 0.72)])} signals")
    print(f"  0.72+:     {len(sell_signals[sell_signals['confidence'] >= 0.72])} signals ← OLD threshold")
    
    print("\n" + "="*80)
    print("🎯 VERDICT")
    print("="*80)
    
    if new_wr > old_wr:
        print(f"✅ NEW thresholds are BETTER: {old_wr:.1%} → {new_wr:.1%} (+{(new_wr-old_wr)*100:.1f}%)")
    elif new_wr == old_wr:
        print(f"⚠️  NO CHANGE: {new_wr:.1%}")
    else:
        print(f"❌ NEW thresholds are WORSE: {old_wr:.1%} → {new_wr:.1%} ({(new_wr-old_wr)*100:.1f}%)")
    
    print(f"\nSignal volume change: {old_total} → {new_total} ({new_total-old_total:+d} signals)")
    
    if new_total == 0:
        print("\n⚠️  PROBLEM: No signals pass new thresholds!")
        print("   This means confidence values are TOO LOW")
        print("   Need to optimize WEIGHTS to increase confidence")

if __name__ == '__main__':
    test_thresholds()
