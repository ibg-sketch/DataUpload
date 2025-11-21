#!/usr/bin/env python3
"""
Backtest new optimized weights on historical data
Calculate REAL win rate if we had used these weights
"""
import pandas as pd
import json
import yaml
from datetime import datetime, timedelta

def load_optimized_weights():
    """Load optimized weights from weight_optimization_results.json"""
    with open('weight_optimization_results.json', 'r') as f:
        results = json.load(f)
    
    weights_by_coin = {}
    for symbol, data in results.items():
        weights_by_coin[symbol] = data['optimized_weights']
    
    return weights_by_coin

def calculate_confidence_with_new_weights(row, weights, symbol):
    """
    Recalculate confidence using NEW optimized weights
    This mimics the bot's confidence calculation logic
    """
    
    # Get raw indicator values
    cvd = abs(row.get('cvd', 0))
    oi_change = abs(row.get('oi_change_pct', 0))
    vwap_dist = abs(row.get('price_vs_vwap_pct', 0))
    volume_spike = int(row.get('volume_spike', 0))
    liq_ratio = abs(row.get('liq_ratio', 0))
    rsi = row.get('rsi', 50)
    
    # Get NEW weights
    cvd_w = weights.get('cvd_weight', 1.0)
    oi_w = weights.get('oi_weight', 1.0)
    vwap_w = weights.get('vwap_weight', 1.0)
    vol_w = weights.get('volume_weight', 1.0)
    liq_w = weights.get('liq_weight', 1.0)
    
    # Simplified scoring (mimics bot logic)
    score = 0.0
    
    # CVD contribution (normalized)
    if cvd > 0:
        score += min(cvd / 100_000_000, 1.0) * cvd_w
    
    # OI contribution
    if oi_change > 0:
        score += min(oi_change / 5.0, 1.0) * oi_w
    
    # VWAP contribution
    if vwap_dist > 0:
        score += min(vwap_dist / 2.0, 1.0) * vwap_w
    
    # Volume spike
    if volume_spike:
        score += vol_w
    
    # Liquidations
    if liq_ratio > 0:
        score += min(liq_ratio / 3.0, 1.0) * liq_w
    
    # Normalize to 0-100%
    max_possible = cvd_w + oi_w + vwap_w + vol_w + liq_w
    confidence = min(score / max_possible, 1.0) if max_possible > 0 else 0
    
    return confidence

def backtest_weights():
    print("="*80)
    print("BACKTESTING NEW OPTIMIZED WEIGHTS ON HISTORICAL DATA")
    print("="*80)
    
    # Load optimized weights
    optimized_weights = load_optimized_weights()
    
    # Load effectiveness data
    eff_df = pd.read_csv('effectiveness_log.csv')
    eff_df['timestamp_sent'] = pd.to_datetime(eff_df['timestamp_sent'])
    
    # Load analysis data
    analysis_df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
    analysis_df = analysis_df[analysis_df['verdict'].isin(['BUY', 'SELL'])]
    analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'], errors='coerce')
    
    # Filter last 2 days
    cutoff = datetime.now() - timedelta(days=2)
    eff_df = eff_df[eff_df['timestamp_sent'] >= cutoff]
    analysis_df = analysis_df[analysis_df['timestamp'] >= cutoff]
    
    print(f"\n📊 Dataset: {len(eff_df)} signals from last 2 days")
    
    # Merge effectiveness with analysis
    merged_data = []
    for idx, eff_row in eff_df.iterrows():
        time_diff = abs(analysis_df['timestamp'] - eff_row['timestamp_sent'])
        matches = analysis_df[
            (analysis_df['symbol'] == eff_row['symbol']) &
            (analysis_df['verdict'] == eff_row['verdict']) &
            (time_diff < timedelta(minutes=2))
        ]
        
        if len(matches) > 0:
            closest_match = matches.loc[time_diff[matches.index].idxmin()]
            
            merged_row = {
                'symbol': eff_row['symbol'],
                'verdict': eff_row['verdict'],
                'result': eff_row['result'],
                'old_confidence': eff_row['confidence'],
                'cvd': closest_match.get('cvd', 0),
                'oi_change_pct': closest_match.get('oi_change_pct', 0),
                'price_vs_vwap_pct': closest_match.get('price_vs_vwap_pct', 0),
                'volume_spike': int(closest_match.get('volume_spike', 0)),
                'liq_ratio': closest_match.get('liq_ratio', 0),
                'rsi': closest_match.get('rsi', 50),
            }
            merged_data.append(merged_row)
    
    df = pd.DataFrame(merged_data)
    print(f"✅ Matched {len(df)} signals with indicator data\n")
    
    # Recalculate confidence with NEW weights
    df['new_confidence'] = df.apply(
        lambda row: calculate_confidence_with_new_weights(
            row, 
            optimized_weights.get(row['symbol'], {}),
            row['symbol']
        ),
        axis=1
    )
    
    # Apply NEW thresholds
    NEW_THRESHOLD_BUY = 0.55
    NEW_THRESHOLD_SELL = 0.60
    
    # Filter signals that would pass new thresholds
    df['would_signal'] = df.apply(
        lambda row: (
            (row['verdict'] == 'BUY' and row['new_confidence'] >= NEW_THRESHOLD_BUY) or
            (row['verdict'] == 'SELL' and row['new_confidence'] >= NEW_THRESHOLD_SELL)
        ),
        axis=1
    )
    
    # Calculate win rates
    print("="*80)
    print("BACKTEST RESULTS: OLD WEIGHTS vs NEW WEIGHTS")
    print("="*80)
    
    # OLD weights (all signals that were actually sent)
    old_total = len(df)
    old_wins = len(df[df['result'] == 'WIN'])
    old_wr = old_wins / old_total if old_total > 0 else 0
    
    # NEW weights (only signals that would pass new thresholds)
    new_df = df[df['would_signal']]
    new_total = len(new_df)
    new_wins = len(new_df[new_df['result'] == 'WIN'])
    new_wr = new_wins / new_total if new_total > 0 else 0
    
    print(f"\n{'Configuration':<20} {'Signals':<10} {'Wins':<10} {'Win Rate':<15} {'Diff'}")
    print("-"*80)
    print(f"{'OLD weights':<20} {old_total:<10} {old_wins:<10} {old_wr:<15.1%} -")
    print(f"{'NEW weights':<20} {new_total:<10} {new_wins:<10} {new_wr:<15.1%} {(new_wr-old_wr)*100:+.1f}%")
    
    # Per-coin breakdown
    print("\n" + "="*80)
    print("PER-COIN BREAKDOWN")
    print("="*80)
    print(f"{'Symbol':<12} {'Old Sig':<10} {'New Sig':<10} {'Old WR':<12} {'New WR':<12} {'Change'}")
    print("-"*80)
    
    for symbol in sorted(df['symbol'].unique()):
        old_sym = df[df['symbol'] == symbol]
        new_sym = new_df[new_df['symbol'] == symbol]
        
        old_sym_wins = len(old_sym[old_sym['result'] == 'WIN'])
        old_sym_wr = old_sym_wins / len(old_sym) if len(old_sym) > 0 else 0
        
        new_sym_wins = len(new_sym[new_sym['result'] == 'WIN'])
        new_sym_wr = new_sym_wins / len(new_sym) if len(new_sym) > 0 else 0
        
        change = (new_sym_wr - old_sym_wr) * 100 if len(new_sym) > 0 else 0
        change_str = f"{change:+.1f}%" if len(new_sym) > 0 else "N/A"
        
        print(f"{symbol:<12} {len(old_sym):<10} {len(new_sym):<10} "
              f"{old_sym_wr:<12.1%} {new_sym_wr:<12.1%} {change_str}")
    
    # Signal volume analysis
    print("\n" + "="*80)
    print("SIGNAL VOLUME ANALYSIS")
    print("="*80)
    
    hours_analyzed = (df['old_confidence'].index.max() - df['old_confidence'].index.min()) / 3600 if len(df) > 0 else 1
    old_signals_per_day = (old_total / 2) if hours_analyzed > 0 else 0  # 2 days
    new_signals_per_day = (new_total / 2) if hours_analyzed > 0 else 0
    
    print(f"Old weights: ~{old_signals_per_day:.0f} signals/day")
    print(f"New weights: ~{new_signals_per_day:.0f} signals/day")
    print(f"Change: {new_signals_per_day - old_signals_per_day:+.0f} signals/day ({(new_signals_per_day/old_signals_per_day-1)*100:+.1f}%)")
    
    # BUY vs SELL breakdown
    print("\n" + "="*80)
    print("BUY vs SELL BREAKDOWN")
    print("="*80)
    
    old_buy = df[df['verdict'] == 'BUY']
    old_sell = df[df['verdict'] == 'SELL']
    new_buy = new_df[new_df['verdict'] == 'BUY']
    new_sell = new_df[new_df['verdict'] == 'SELL']
    
    print(f"\n{'Type':<10} {'Old Sig':<12} {'New Sig':<12} {'Old WR':<12} {'New WR':<12}")
    print("-"*80)
    
    old_buy_wr = len(old_buy[old_buy['result'] == 'WIN']) / len(old_buy) if len(old_buy) > 0 else 0
    new_buy_wr = len(new_buy[new_buy['result'] == 'WIN']) / len(new_buy) if len(new_buy) > 0 else 0
    print(f"{'BUY':<10} {len(old_buy):<12} {len(new_buy):<12} {old_buy_wr:<12.1%} {new_buy_wr:<12.1%}")
    
    old_sell_wr = len(old_sell[old_sell['result'] == 'WIN']) / len(old_sell) if len(old_sell) > 0 else 0
    new_sell_wr = len(new_sell[new_sell['result'] == 'WIN']) / len(new_sell) if len(new_sell) > 0 else 0
    print(f"{'SELL':<10} {len(old_sell):<12} {len(new_sell):<12} {old_sell_wr:<12.1%} {new_sell_wr:<12.1%}")
    
    print("\n" + "="*80)
    print("🎯 FINAL VERDICT")
    print("="*80)
    
    if new_wr > old_wr:
        improvement = (new_wr - old_wr) * 100
        print(f"✅ NEW weights are BETTER: +{improvement:.1f}% win rate improvement")
        print(f"   {old_wr:.1%} → {new_wr:.1%}")
    elif new_wr == old_wr:
        print(f"⚠️  NEW weights show NO CHANGE: {new_wr:.1%} win rate")
    else:
        decline = (old_wr - new_wr) * 100
        print(f"❌ NEW weights are WORSE: -{decline:.1f}% win rate decline")
        print(f"   {old_wr:.1%} → {new_wr:.1%}")
    
    print(f"\nSignal volume: {old_total} → {new_total} ({new_total-old_total:+d})")
    
    if new_wr < 0.45:
        print("\n⚠️  WARNING: Win rate still below 45% target!")
        print("   Problem is likely in base formula, not just weights")

if __name__ == '__main__':
    backtest_weights()
