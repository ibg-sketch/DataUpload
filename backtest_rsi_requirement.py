#!/usr/bin/env python3
"""
Backtest RSI Requirement
Validates the strict RSI extreme requirement using historical data.
Compares win rates with and without the new filter.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_effectiveness_data():
    """Load historical effectiveness data merged with analysis indicators."""
    try:
        eff_df = pd.read_csv('effectiveness_log.csv')
        print(f"📊 Loaded {len(eff_df)} signals from effectiveness_log.csv")
        
        try:
            analysis_df = pd.read_csv('analysis_log.csv')
            print(f"📊 Loaded {len(analysis_df)} analysis records from analysis_log.csv")
            
            eff_df['timestamp'] = pd.to_datetime(eff_df['timestamp_sent'])
            analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'])
            
            merged = []
            for _, eff_row in eff_df.iterrows():
                time_window = timedelta(minutes=2)
                matching = analysis_df[
                    (analysis_df['symbol'] == eff_row['symbol']) &
                    (analysis_df['verdict'] == eff_row['verdict']) &
                    (abs(analysis_df['timestamp'] - eff_row['timestamp']) <= time_window)
                ]
                
                if len(matching) > 0:
                    closest = matching.iloc[(matching['timestamp'] - eff_row['timestamp']).abs().argmin()]
                    merged_row = {**eff_row.to_dict(), **closest.to_dict()}
                    merged.append(merged_row)
            
            if len(merged) > 0:
                df = pd.DataFrame(merged)
                print(f"✅ Merged {len(df)} signals with analysis data\n")
                return df
            else:
                print("⚠️  No matching records found between logs")
                return eff_df
        
        except FileNotFoundError:
            print("⚠️  analysis_log.csv not found - cannot merge RSI data")
            return eff_df
    
    except FileNotFoundError:
        print("❌ effectiveness_log.csv not found")
        return None

def analyze_rsi_impact(df):
    """
    Analyze impact of strict RSI requirement.
    OLD: Signals sent regardless of RSI
    NEW: BUY requires RSI < 30, SELL requires RSI > 70
    """
    
    if 'rsi' not in df.columns or 'verdict' not in df.columns or 'result' not in df.columns:
        print("⚠️  Missing required columns (rsi, verdict, result)")
        print(f"Available columns: {df.columns.tolist()}")
        return
    
    total_signals = len(df)
    wins = df[df['result'] == 'WIN']
    losses = df[df['result'] == 'LOSS']
    
    print("="*70)
    print("BACKTEST: STRICT RSI REQUIREMENT VALIDATION")
    print("="*70)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Historical Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print()
    
    print("📈 BASELINE PERFORMANCE (ALL SIGNALS)")
    print("-" * 70)
    print(f"Total Signals: {total_signals}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}")
    baseline_win_rate = (len(wins) / total_signals * 100) if total_signals > 0 else 0
    print(f"Win Rate: {baseline_win_rate:.1f}%")
    print()
    
    buy_signals = df[df['verdict'] == 'BUY']
    sell_signals = df[df['verdict'] == 'SELL']
    
    buy_strict_rsi = buy_signals[buy_signals['rsi'] < 30]
    sell_strict_rsi = sell_signals[sell_signals['rsi'] > 70]
    
    buy_fails_rsi = buy_signals[buy_signals['rsi'] >= 30]
    sell_fails_rsi = sell_signals[sell_signals['rsi'] <= 70]
    
    print("🎯 NEW FILTER: STRICT RSI REQUIREMENT")
    print("-" * 70)
    print("Requirements:")
    print("  - BUY signals: RSI < 30 (oversold)")
    print("  - SELL signals: RSI > 70 (overbought)")
    print()
    
    print("📊 BUY SIGNALS ANALYSIS")
    print("-" * 70)
    print(f"Total BUY signals: {len(buy_signals)}")
    print(f"  Pass RSI filter (RSI < 30): {len(buy_strict_rsi)} ({len(buy_strict_rsi)/len(buy_signals)*100 if len(buy_signals) > 0 else 0:.1f}%)")
    print(f"  Fail RSI filter (RSI >= 30): {len(buy_fails_rsi)} ({len(buy_fails_rsi)/len(buy_signals)*100 if len(buy_signals) > 0 else 0:.1f}%)")
    
    if len(buy_strict_rsi) > 0:
        buy_strict_wins = len(buy_strict_rsi[buy_strict_rsi['result'] == 'WIN'])
        buy_strict_wr = buy_strict_wins / len(buy_strict_rsi) * 100
        print(f"  Win Rate (RSI < 30): {buy_strict_wr:.1f}% ({buy_strict_wins}W-{len(buy_strict_rsi)-buy_strict_wins}L)")
    
    if len(buy_fails_rsi) > 0:
        buy_fails_wins = len(buy_fails_rsi[buy_fails_rsi['result'] == 'WIN'])
        buy_fails_wr = buy_fails_wins / len(buy_fails_rsi) * 100
        print(f"  Win Rate (RSI >= 30): {buy_fails_wr:.1f}% ({buy_fails_wins}W-{len(buy_fails_rsi)-buy_fails_wins}L) ❌ WOULD BE BLOCKED")
    
    print()
    print("📊 SELL SIGNALS ANALYSIS")
    print("-" * 70)
    print(f"Total SELL signals: {len(sell_signals)}")
    print(f"  Pass RSI filter (RSI > 70): {len(sell_strict_rsi)} ({len(sell_strict_rsi)/len(sell_signals)*100 if len(sell_signals) > 0 else 0:.1f}%)")
    print(f"  Fail RSI filter (RSI <= 70): {len(sell_fails_rsi)} ({len(sell_fails_rsi)/len(sell_signals)*100 if len(sell_signals) > 0 else 0:.1f}%)")
    
    if len(sell_strict_rsi) > 0:
        sell_strict_wins = len(sell_strict_rsi[sell_strict_rsi['result'] == 'WIN'])
        sell_strict_wr = sell_strict_wins / len(sell_strict_rsi) * 100
        print(f"  Win Rate (RSI > 70): {sell_strict_wr:.1f}% ({sell_strict_wins}W-{len(sell_strict_rsi)-sell_strict_wins}L)")
    
    if len(sell_fails_rsi) > 0:
        sell_fails_wins = len(sell_fails_rsi[sell_fails_rsi['result'] == 'WIN'])
        sell_fails_wr = sell_fails_wins / len(sell_fails_rsi) * 100
        print(f"  Win Rate (RSI <= 70): {sell_fails_wr:.1f}% ({sell_fails_wins}W-{len(sell_fails_rsi)-sell_fails_wins}L) ❌ WOULD BE BLOCKED")
    
    print()
    print("🎯 COMBINED RESULTS WITH NEW FILTER")
    print("-" * 70)
    
    passing_signals = pd.concat([buy_strict_rsi, sell_strict_rsi])
    blocked_signals = pd.concat([buy_fails_rsi, sell_fails_rsi])
    
    if len(passing_signals) > 0:
        passing_wins = len(passing_signals[passing_signals['result'] == 'WIN'])
        passing_wr = passing_wins / len(passing_signals) * 100
        print(f"✅ Signals PASSING new filter: {len(passing_signals)}")
        print(f"   Win Rate: {passing_wr:.1f}% ({passing_wins}W-{len(passing_signals)-passing_wins}L)")
    else:
        print(f"✅ Signals PASSING new filter: 0 (filter is TOO STRICT!)")
        passing_wr = 0
    
    if len(blocked_signals) > 0:
        blocked_wins = len(blocked_signals[blocked_signals['result'] == 'WIN'])
        blocked_wr = blocked_wins / len(blocked_signals) * 100
        print(f"❌ Signals BLOCKED by new filter: {len(blocked_signals)}")
        print(f"   Win Rate: {blocked_wr:.1f}% ({blocked_wins}W-{len(blocked_signals)-blocked_wins}L)")
        print(f"   IMPACT: These signals would NOT be sent")
    
    print()
    print("📈 PERFORMANCE COMPARISON")
    print("-" * 70)
    print(f"Baseline Win Rate (all signals): {baseline_win_rate:.1f}%")
    if len(passing_signals) > 0:
        print(f"New Win Rate (strict RSI only): {passing_wr:.1f}%")
        improvement = passing_wr - baseline_win_rate
        print(f"Improvement: {improvement:+.1f} percentage points")
        
        if improvement > 0:
            print(f"✅ VALIDATION: Strict RSI filter IMPROVES win rate")
        else:
            print(f"⚠️  WARNING: Strict RSI filter REDUCES win rate")
    
    signal_frequency_reduction = (len(blocked_signals) / total_signals * 100) if total_signals > 0 else 0
    print(f"\nSignal Frequency:")
    print(f"  Before: {total_signals} signals")
    print(f"  After: {len(passing_signals)} signals ({-signal_frequency_reduction:.1f}% reduction)")
    
    print()
    print("📊 RSI DISTRIBUTION ANALYSIS")
    print("-" * 70)
    
    winning_signals = df[df['result'] == 'WIN']
    losing_signals = df[df['result'] == 'LOSS']
    
    if len(winning_signals) > 0:
        print(f"Winning Signals RSI:")
        print(f"  Min: {winning_signals['rsi'].min():.1f}")
        print(f"  Median: {winning_signals['rsi'].median():.1f}")
        print(f"  Mean: {winning_signals['rsi'].mean():.1f}")
        print(f"  Max: {winning_signals['rsi'].max():.1f}")
        
        win_extreme = len(winning_signals[(winning_signals['rsi'] < 30) | (winning_signals['rsi'] > 70)])
        win_neutral = len(winning_signals[(winning_signals['rsi'] >= 30) & (winning_signals['rsi'] <= 70)])
        print(f"  Extreme (< 30 or > 70): {win_extreme} ({win_extreme/len(winning_signals)*100:.1f}%)")
        print(f"  Neutral (30-70): {win_neutral} ({win_neutral/len(winning_signals)*100:.1f}%)")
    
    if len(losing_signals) > 0:
        print(f"\nLosing Signals RSI:")
        print(f"  Min: {losing_signals['rsi'].min():.1f}")
        print(f"  Median: {losing_signals['rsi'].median():.1f}")
        print(f"  Mean: {losing_signals['rsi'].mean():.1f}")
        print(f"  Max: {losing_signals['rsi'].max():.1f}")
        
        loss_extreme = len(losing_signals[(losing_signals['rsi'] < 30) | (losing_signals['rsi'] > 70)])
        loss_neutral = len(losing_signals[(losing_signals['rsi'] >= 30) & (losing_signals['rsi'] <= 70)])
        print(f"  Extreme (< 30 or > 70): {loss_extreme} ({loss_extreme/len(losing_signals)*100:.1f}%)")
        print(f"  Neutral (30-70): {loss_neutral} ({loss_neutral/len(losing_signals)*100:.1f}%)")
    
    print()
    print("💡 RECOMMENDATIONS")
    print("-" * 70)
    
    if len(passing_signals) == 0:
        print("⚠️  CRITICAL: Filter is TOO STRICT - blocks ALL signals!")
        print("   Recommendation: Relax RSI thresholds (e.g., RSI < 40 for BUY, > 60 for SELL)")
    elif len(passing_signals) < total_signals * 0.1:
        print("⚠️  WARNING: Filter blocks >90% of signals")
        print(f"   Only {len(passing_signals)} out of {total_signals} signals would pass")
        print("   Recommendation: Consider slightly relaxed thresholds")
    elif passing_wr > baseline_win_rate + 10:
        print(f"✅ EXCELLENT: Filter improves win rate by {improvement:.1f}pp")
        print("   Recommendation: Keep strict RSI requirement")
    elif passing_wr > baseline_win_rate:
        print(f"✅ GOOD: Filter improves win rate by {improvement:.1f}pp")
        print("   Recommendation: Keep strict RSI requirement")
    else:
        print(f"⚠️  Filter REDUCES win rate by {abs(improvement):.1f}pp")
        print("   Recommendation: Reconsider strict RSI requirement")
    
    print()
    print("="*70)
    print("BACKTEST COMPLETE")
    print("="*70)
    
    return {
        'baseline_win_rate': baseline_win_rate,
        'new_win_rate': passing_wr if len(passing_signals) > 0 else 0,
        'signals_passing': len(passing_signals),
        'signals_blocked': len(blocked_signals),
        'improvement': improvement if len(passing_signals) > 0 else -baseline_win_rate
    }

def main():
    print("\n" + "="*70)
    print("RSI REQUIREMENT BACKTEST")
    print("="*70)
    print("Validating strict RSI extreme requirement with historical data")
    print("="*70 + "\n")
    
    df = load_effectiveness_data()
    
    if df is None or len(df) == 0:
        print("❌ No data available for analysis")
        return
    
    results = analyze_rsi_impact(df)
    
    if results:
        print(f"\n📄 Results saved for documentation")

if __name__ == "__main__":
    main()
