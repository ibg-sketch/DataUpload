#!/usr/bin/env python3
"""
Validate optimized formula on REAL signals with ACTUAL results
Check the 241 high-quality signals and their effectiveness
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("="*80)
print("VALIDATING OPTIMIZED FORMULA ON REAL SIGNALS")
print("="*80)
print()

# Load signals and effectiveness logs
signals_df = pd.read_csv('signals_log.csv')
signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])

try:
    effectiveness_df = pd.read_csv('effectiveness_log.csv')
    effectiveness_df['timestamp'] = pd.to_datetime(effectiveness_df['timestamp_sent'])
    print(f"✅ Loaded {len(effectiveness_df)} effectiveness records")
except Exception as e:
    print(f"❌ Error loading effectiveness_log.csv: {e}")
    effectiveness_df = pd.DataFrame()

# Filter last 2 days
today = datetime.now().date()
yesterday = today - timedelta(days=1)
recent = signals_df[signals_df['timestamp'].dt.date.isin([yesterday, today])].copy()

print(f"📊 Total signals from last 2 days: {len(recent)}")
print()

# Apply optimized formula filters
# Requirements: VWAP + at least 2 other key indicators (ADX, RSI, Volume)
high_quality = []

for _, sig in recent.iterrows():
    components = sig.get('components', '')
    if pd.notna(components):
        has_vwap = 'Price_below_VWAP' in components or 'Price_above_VWAP' in components
        has_rsi = 'RSI_oversold' in components or 'RSI_overbought' in components
        has_adx = 'ADX_strong_trend' in components
        has_vol = 'Vol_spike' in components
        
        # Count key indicators (matching optimized formula)
        match_count = sum([has_vwap, has_rsi, has_adx, has_vol])
        
        # Require VWAP + at least 2 others
        if has_vwap and match_count >= 3:
            high_quality.append(sig)

hq_df = pd.DataFrame(high_quality)
print(f"✅ High-quality signals (optimized formula): {len(hq_df)}/{len(recent)} ({len(hq_df)/len(recent)*100:.1f}%)")
print()

# Match with effectiveness results
if len(effectiveness_df) > 0 and len(hq_df) > 0:
    print("="*80)
    print("MATCHING WITH EFFECTIVENESS RESULTS")
    print("="*80)
    print()
    
    # Create matching key
    hq_df['match_key'] = hq_df['symbol'] + '_' + hq_df['verdict'] + '_' + hq_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    effectiveness_df['match_key'] = effectiveness_df['symbol'] + '_' + effectiveness_df['verdict'] + '_' + effectiveness_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Merge
    matched = hq_df.merge(effectiveness_df[['match_key', 'result', 'profit_pct']], 
                          on='match_key', how='left')
    
    # Count matched vs unmatched
    has_result = matched['result'].notna()
    matched_count = has_result.sum()
    
    print(f"Matched signals: {matched_count}/{len(hq_df)} ({matched_count/len(hq_df)*100:.1f}%)")
    print(f"Unmatched (still active): {len(hq_df) - matched_count}")
    print()
    
    if matched_count > 0:
        completed = matched[has_result].copy()
        
        print("="*80)
        print("OPTIMIZED FORMULA PERFORMANCE ON REAL SIGNALS")
        print("="*80)
        print()
        
        # Results breakdown
        wins = (completed['result'] == 'WIN').sum()
        losses = (completed['result'] == 'LOSS').sum()
        cancelled = (completed['result'] == 'CANCELLED').sum()
        
        win_rate = wins / matched_count * 100 if matched_count > 0 else 0
        
        print(f"📊 Results ({matched_count} completed signals):")
        print(f"   WIN: {wins} ({wins/matched_count*100:.1f}%)")
        print(f"   LOSS: {losses} ({losses/matched_count*100:.1f}%)")
        print(f"   CANCELLED: {cancelled} ({cancelled/matched_count*100:.1f}%)")
        print()
        print(f"🎯 WIN RATE: {win_rate:.1f}%")
        print()
        
        # Profit analysis
        avg_profit = completed['profit_pct'].mean()
        win_profit = completed[completed['result'] == 'WIN']['profit_pct'].mean()
        loss_profit = completed[completed['result'] == 'LOSS']['profit_pct'].mean()
        
        print(f"💰 Profit Analysis:")
        print(f"   Average: {avg_profit:.2f}%")
        print(f"   WIN avg: {win_profit:.2f}%")
        print(f"   LOSS avg: {loss_profit:.2f}%")
        print()
        
        # Breakdown by direction
        print("="*80)
        print("BREAKDOWN BY DIRECTION")
        print("="*80)
        print()
        
        for verdict in ['BUY', 'SELL']:
            verdict_data = completed[completed['verdict'] == verdict]
            if len(verdict_data) > 0:
                v_wins = (verdict_data['result'] == 'WIN').sum()
                v_total = len(verdict_data)
                v_wr = v_wins / v_total * 100
                v_profit = verdict_data['profit_pct'].mean()
                
                print(f"{verdict:4s}: {v_total:3d} signals | WR: {v_wr:5.1f}% | Avg: {v_profit:+.2f}%")
        
        print()
        print("="*80)
        print("COMPARISON WITH BACKTEST")
        print("="*80)
        print()
        
        backtest_wr = 82.9
        print(f"Backtest WR (VWAP Max, TTL=30min): {backtest_wr:.1f}%")
        print(f"Real signals WR (last 2 days):     {win_rate:.1f}%")
        print()
        
        if win_rate >= backtest_wr * 0.9:
            print("✅ EXCELLENT! Real performance matches backtest expectations")
        elif win_rate >= 60:
            print("✅ GOOD! Real performance is acceptable for 50x leverage")
        elif win_rate >= 50:
            print("⚠️  CAUTION! Performance below expected, need more data")
        else:
            print("❌ WARNING! Performance significantly below backtest")
        
        print()
        print("="*80)
        print("TOP PERFORMING SYMBOLS")
        print("="*80)
        print()
        
        symbol_stats = completed.groupby('symbol').agg({
            'result': lambda x: (x == 'WIN').sum() / len(x) * 100,
            'profit_pct': 'mean',
            'symbol': 'count'
        }).rename(columns={'result': 'win_rate', 'symbol': 'count'})
        
        symbol_stats = symbol_stats[symbol_stats['count'] >= 3]  # Min 3 signals
        symbol_stats = symbol_stats.sort_values('win_rate', ascending=False)
        
        print("Symbol       Signals  Win Rate  Avg Profit")
        print("-" * 50)
        for symbol, row in symbol_stats.iterrows():
            print(f"{symbol:12s} {int(row['count']):3d}      {row['win_rate']:5.1f}%    {row['profit_pct']:+6.2f}%")
    else:
        print("⚠️  No completed signals found yet (all still active)")
        print("   Need to wait for signals to reach target or expire")
else:
    print("⚠️  Cannot validate - missing effectiveness data")
    print("   Signals are still being tracked by Signal Tracker")

print()
print("="*80)
print("CONCLUSION")
print("="*80)
print()

if len(effectiveness_df) > 0 and matched_count > 0:
    if win_rate >= 60:
        print("✅ Optimized formula shows STRONG performance on real signals")
        print(f"   Win rate: {win_rate:.1f}% is suitable for 50x leverage")
        print()
        print("💡 RECOMMENDATION:")
        print("   ✓ Formula is validated on real data")
        print("   ✓ Ready to integrate into signal_generator.py")
        print("   ✓ Start Paper Trading with optimized parameters")
    else:
        print("⚠️  Formula needs more validation data")
        print(f"   Current win rate: {win_rate:.1f}%")
        print()
        print("💡 RECOMMENDATION:")
        print("   • Collect more data (7+ days)")
        print("   • Monitor performance trends")
        print("   • Adjust thresholds if needed")
else:
    print("📊 High-quality signals identified: {len(hq_df)}")
    print("⏳ Waiting for effectiveness results to validate formula")
    print()
    print("💡 RECOMMENDATION:")
    print("   • Let Signal Tracker complete current signals")
    print("   • Run this validation again in 4-6 hours")
    print("   • Or start Paper Trading to generate new data")
