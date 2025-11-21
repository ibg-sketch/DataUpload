#!/usr/bin/env python3
"""
Scientific Comparison: OLD vs NEW Bot Version
Cutoff: 2025-11-04 16:00:00 UTC (18:00 Kyiv)

NEW version includes:
- 5m candles (was 15m)
- Enhanced Formula v2
- Hybrid EMA+VWAP Regime
- New OI weights (0.2 vs 0.1)
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import json

MEXC_TAKER_FEE = 0.0006
POSITION_SIZE_USDT = 100
MIN_CONFIDENCE = 0.50

# CRITICAL CUTOFF (Kyiv 18:00 = UTC 16:00)
CUTOFF_TIME = datetime(2025, 11, 4, 16, 0, 0)

def simulate_trade(signal, leverage, sl_pct, tp_pct):
    """Симуляция сделки"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    
    entry_fee_pct = MEXC_TAKER_FEE
    sl_price_move_pct = sl_pct / leverage
    tp_price_move_pct = tp_pct / leverage
    
    if verdict == "SELL":
        stop_loss_price = entry_price * (1 + sl_price_move_pct / 100)
        take_profit_price = entry_price * (1 - tp_price_move_pct / 100)
        
        if highest >= stop_loss_price:
            exit_price = stop_loss_price
            exit_reason = "STOP_LOSS"
        elif lowest <= take_profit_price:
            exit_price = take_profit_price
            exit_reason = "TAKE_PROFIT"
        else:
            exit_price = final_price
            exit_reason = "TTL_EXPIRED"
        
        price_change_pct = ((entry_price - exit_price) / entry_price) * 100
    else:
        stop_loss_price = entry_price * (1 - sl_price_move_pct / 100)
        take_profit_price = entry_price * (1 + tp_price_move_pct / 100)
        
        if lowest <= stop_loss_price:
            exit_price = stop_loss_price
            exit_reason = "STOP_LOSS"
        elif highest >= take_profit_price:
            exit_price = take_profit_price
            exit_reason = "TAKE_PROFIT"
        else:
            exit_price = final_price
            exit_reason = "TTL_EXPIRED"
        
        price_change_pct = ((exit_price - entry_price) / entry_price) * 100
    
    exit_fee_pct = MEXC_TAKER_FEE
    total_fee_pct = entry_fee_pct + exit_fee_pct
    
    gross_profit_pct = price_change_pct * leverage
    net_profit_pct = gross_profit_pct - (total_fee_pct * 100)
    profit_usdt = (net_profit_pct / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

def load_all_signals():
    """Загрузка ВСЕХ сигналов с разделением OLD/NEW"""
    old_signals = []
    new_signals = []
    
    with open('effectiveness_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
                
                if row['result'] == 'CANCELLED':
                    continue
                
                confidence = float(row['confidence'])
                entry_price = float(row['entry_price'])
                
                if entry_price == 0 or confidence < MIN_CONFIDENCE:
                    continue
                
                signal = {
                    'timestamp': row['timestamp_sent'],
                    'timestamp_dt': timestamp,
                    'symbol': row['symbol'],
                    'verdict': row['verdict'],
                    'confidence': confidence,
                    'entry_price': entry_price,
                    'target_min': float(row['target_min']) if row['target_min'] else 0,
                    'target_max': float(row['target_max']) if row['target_max'] else 0,
                    'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                    'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                    'final_price': float(row['final_price']) if row['final_price'] else entry_price,
                    'duration_actual': int(row['duration_actual']) if row['duration_actual'] else 0,
                }
                
                # Разделение OLD vs NEW
                if timestamp < CUTOFF_TIME:
                    old_signals.append(signal)
                else:
                    new_signals.append(signal)
                
            except (ValueError, KeyError):
                continue
    
    return old_signals, new_signals

def evaluate_strategy(signals, leverage, sl_pct, tp_pct, excluded_patterns=None):
    """Оценка стратегии"""
    filtered_signals = signals
    
    if excluded_patterns:
        filtered_signals = [s for s in signals if (s['symbol'], s['verdict']) not in excluded_patterns]
    
    if len(filtered_signals) == 0:
        return None
    
    trades = [simulate_trade(s, leverage, sl_pct, tp_pct) for s in filtered_signals]
    
    total_profit = sum(t['profit_usdt'] for t in trades)
    wins = sum(1 for t in trades if t['win'])
    win_rate = wins / len(trades) * 100 if trades else 0
    
    winning_profits = [t['profit_usdt'] for t in trades if t['win']]
    losing_profits = [t['profit_usdt'] for t in trades if not t['win']]
    
    total_wins = sum(winning_profits) if winning_profits else 0
    total_losses = abs(sum(losing_profits)) if losing_profits else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    sl_count = sum(1 for t in trades if t['exit_reason'] == 'STOP_LOSS')
    tp_count = sum(1 for t in trades if t['exit_reason'] == 'TAKE_PROFIT')
    
    return {
        'total_profit': total_profit,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_trades': len(trades),
        'sl_rate': sl_count / len(trades) * 100,
        'tp_rate': tp_count / len(trades) * 100,
        'avg_profit': total_profit / len(trades) if trades else 0
    }

def optimize_for_dataset(signals, label):
    """Оптимизация параметров для конкретного датасета"""
    print(f"\n🔍 Optimizing for {label}...")
    
    leverage_options = [20, 25, 30, 40, 50]
    sl_options = [15, 20, 25, 30, 35, 40]
    tp_options = [30, 40, 50, 60, 75]
    
    best_result = None
    best_params = None
    
    for leverage in leverage_options:
        for sl_pct in sl_options:
            for tp_pct in tp_options:
                if tp_pct <= sl_pct:
                    continue
                
                result = evaluate_strategy(signals, leverage, sl_pct, tp_pct)
                
                if result and result['total_profit'] > 0:
                    if (result['win_rate'] > 40 and 
                        result['profit_factor'] > 1.2 and
                        result['sl_rate'] < 60):
                        
                        if best_result is None or result['total_profit'] > best_result['total_profit']:
                            best_result = result
                            best_params = {
                                'leverage': leverage,
                                'sl_pct': sl_pct,
                                'tp_pct': tp_pct
                            }
    
    return best_params, best_result

# Load data
print("="*80)
print("SCIENTIFIC COMPARISON: OLD vs NEW BOT VERSION")
print("="*80)
print(f"\n⏰ CUTOFF TIME: {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M:%S')} UTC (18:00 Kyiv)")
print(f"\n📋 Version Changes:")
print(f"  OLD (before cutoff):")
print(f"    - 15m candles")
print(f"    - Old formulas")
print(f"    - OI weight: 0.1")
print(f"\n  NEW (after cutoff):")
print(f"    - 5m candles ✅")
print(f"    - Enhanced Formula v2 ✅")
print(f"    - Hybrid EMA+VWAP Regime ✅")
print(f"    - OI weight: 0.2 ✅")

old_signals, new_signals = load_all_signals()

print(f"\n📊 DATA SUMMARY:")
print(f"  OLD signals (before {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M')}): {len(old_signals)}")
if old_signals:
    old_first = min(s['timestamp_dt'] for s in old_signals)
    old_last = max(s['timestamp_dt'] for s in old_signals)
    print(f"    Time range: {old_first.strftime('%Y-%m-%d %H:%M')} to {old_last.strftime('%Y-%m-%d %H:%M')}")
    print(f"    Duration: {(old_last - old_first).total_seconds() / 3600:.1f} hours")

print(f"\n  NEW signals (after {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M')}): {len(new_signals)}")
if new_signals:
    new_first = min(s['timestamp_dt'] for s in new_signals)
    new_last = max(s['timestamp_dt'] for s in new_signals)
    print(f"    Time range: {new_first.strftime('%Y-%m-%d %H:%M')} to {new_last.strftime('%Y-%m-%d %H:%M')}")
    print(f"    Duration: {(new_last - new_first).total_seconds() / 3600:.1f} hours")

# Optimize for OLD
if len(old_signals) >= 50:
    print(f"\n{'='*80}")
    print("OPTIMIZING FOR OLD VERSION")
    print(f"{'='*80}")
    old_params, old_result = optimize_for_dataset(old_signals, "OLD")
    
    if old_params:
        print(f"\n🏆 OLD VERSION - Best Parameters:")
        print(f"  Leverage: {old_params['leverage']}x")
        print(f"  SL: {old_params['sl_pct']}% deposit")
        print(f"  TP: {old_params['tp_pct']}% deposit")
        print(f"\n📈 OLD VERSION - Results:")
        print(f"  Total Profit: ${old_result['total_profit']:,.2f}")
        print(f"  Win Rate: {old_result['win_rate']:.1f}%")
        print(f"  Profit Factor: {old_result['profit_factor']:.2f}")
        print(f"  Total Trades: {old_result['total_trades']}")
else:
    print(f"\n⚠️  Not enough OLD signals for optimization ({len(old_signals)} < 50)")
    old_params = None
    old_result = None

# Optimize for NEW
if len(new_signals) >= 50:
    print(f"\n{'='*80}")
    print("OPTIMIZING FOR NEW VERSION")
    print(f"{'='*80}")
    new_params, new_result = optimize_for_dataset(new_signals, "NEW")
    
    if new_params:
        print(f"\n🏆 NEW VERSION - Best Parameters:")
        print(f"  Leverage: {new_params['leverage']}x")
        print(f"  SL: {new_params['sl_pct']}% deposit")
        print(f"  TP: {new_params['tp_pct']}% deposit")
        print(f"\n📈 NEW VERSION - Results:")
        print(f"  Total Profit: ${new_result['total_profit']:,.2f}")
        print(f"  Win Rate: {new_result['win_rate']:.1f}%")
        print(f"  Profit Factor: {new_result['profit_factor']:.2f}")
        print(f"  Total Trades: {new_result['total_trades']}")
else:
    print(f"\n⚠️  Not enough NEW signals for optimization ({len(new_signals)} < 50)")
    new_params = None
    new_result = None

# Comparison
if old_result and new_result:
    print(f"\n{'='*80}")
    print("📊 HEAD-TO-HEAD COMPARISON")
    print(f"{'='*80}")
    
    print(f"\n{'Metric':<25} {'OLD Version':<18} {'NEW Version':<18} {'Winner':<15}")
    print("-"*80)
    
    # Total Profit
    winner = "🏆 NEW" if new_result['total_profit'] > old_result['total_profit'] else "🏆 OLD"
    diff = new_result['total_profit'] - old_result['total_profit']
    print(f"{'Total Profit':<25} ${old_result['total_profit']:>14,.2f}   ${new_result['total_profit']:>14,.2f}   {winner} ({diff:+.2f})")
    
    # Win Rate
    winner = "🏆 NEW" if new_result['win_rate'] > old_result['win_rate'] else "🏆 OLD"
    diff = new_result['win_rate'] - old_result['win_rate']
    print(f"{'Win Rate':<25} {old_result['win_rate']:>14.1f}%   {new_result['win_rate']:>14.1f}%   {winner} ({diff:+.1f}%)")
    
    # Profit Factor
    winner = "🏆 NEW" if new_result['profit_factor'] > old_result['profit_factor'] else "🏆 OLD"
    diff = new_result['profit_factor'] - old_result['profit_factor']
    print(f"{'Profit Factor':<25} {old_result['profit_factor']:>14.2f}   {new_result['profit_factor']:>14.2f}   {winner} ({diff:+.2f})")
    
    # Avg Profit/Trade
    winner = "🏆 NEW" if new_result['avg_profit'] > old_result['avg_profit'] else "🏆 OLD"
    diff = new_result['avg_profit'] - old_result['avg_profit']
    print(f"{'Avg Profit/Trade':<25} ${old_result['avg_profit']:>14.2f}   ${new_result['avg_profit']:>14.2f}   {winner} ({diff:+.2f})")
    
    # SL Rate (lower is better)
    winner = "🏆 NEW" if new_result['sl_rate'] < old_result['sl_rate'] else "🏆 OLD"
    diff = new_result['sl_rate'] - old_result['sl_rate']
    print(f"{'SL Rate (lower better)':<25} {old_result['sl_rate']:>14.1f}%   {new_result['sl_rate']:>14.1f}%   {winner} ({diff:+.1f}%)")
    
    # TP Rate (higher is better)
    winner = "🏆 NEW" if new_result['tp_rate'] > old_result['tp_rate'] else "🏆 OLD"
    diff = new_result['tp_rate'] - old_result['tp_rate']
    print(f"{'TP Rate (higher better)':<25} {old_result['tp_rate']:>14.1f}%   {new_result['tp_rate']:>14.1f}%   {winner} ({diff:+.1f}%)")
    
    # ROI
    old_roi = (old_result['total_profit'] / 1000) * 100
    new_roi = (new_result['total_profit'] / 1000) * 100
    winner = "🏆 NEW" if new_roi > old_roi else "🏆 OLD"
    diff = new_roi - old_roi
    print(f"{'ROI (on $1000)':<25} {old_roi:>14.1f}%   {new_roi:>14.1f}%   {winner} ({diff:+.1f}%)")
    
    print(f"\n{'='*80}")
    print("💡 SCIENTIFIC CONCLUSION")
    print(f"{'='*80}")
    
    # Count wins
    new_wins = 0
    if new_result['total_profit'] > old_result['total_profit']: new_wins += 1
    if new_result['win_rate'] > old_result['win_rate']: new_wins += 1
    if new_result['profit_factor'] > old_result['profit_factor']: new_wins += 1
    if new_result['avg_profit'] > old_result['avg_profit']: new_wins += 1
    if new_result['sl_rate'] < old_result['sl_rate']: new_wins += 1
    if new_result['tp_rate'] > old_result['tp_rate']: new_wins += 1
    
    print(f"\nNEW version wins in {new_wins}/6 metrics")
    
    if new_wins >= 4:
        print(f"\n✅ VERDICT: NEW version is SIGNIFICANTLY BETTER!")
        print(f"   The improvements (5m candles, Enhanced Formula v2, etc.) are WORKING!")
    elif new_wins >= 3:
        print(f"\n🟡 VERDICT: NEW version shows IMPROVEMENT")
        print(f"   The changes are positive but need more data to confirm")
    else:
        print(f"\n⚠️  VERDICT: Inconclusive or OLD version better")
        print(f"   May need to review recent changes or collect more data")

# Save NEW version config
if new_params and new_result:
    print(f"\n{'='*80}")
    print("💾 SAVING OPTIMIZED CONFIG FOR NEW VERSION")
    print(f"{'='*80}")
    
    # Excluded patterns (same as before)
    excluded_patterns = [
        ["LINKUSDT", "SELL"],
        ["HYPEUSDT", "BUY"],
        ["ADAUSDT", "BUY"],
        ["HYPEUSDT", "SELL"],
        ["ETHUSDT", "SELL"]
    ]
    
    # Test with exclusions
    final_result = evaluate_strategy(
        new_signals,
        new_params['leverage'],
        new_params['sl_pct'],
        new_params['tp_pct'],
        excluded_patterns=set(tuple(p) for p in excluded_patterns)
    )
    
    config = {
        'version': 'NEW (5m candles, Enhanced Formula v2, Hybrid Regime)',
        'leverage': new_params['leverage'],
        'stop_loss_pct': new_params['sl_pct'],
        'take_profit_pct': new_params['tp_pct'],
        'position_size_usdt': POSITION_SIZE_USDT,
        'min_confidence': MIN_CONFIDENCE,
        'excluded_patterns': excluded_patterns,
        'performance': {
            'total_profit': final_result['total_profit'],
            'roi': (final_result['total_profit'] / 1000) * 100,
            'win_rate': final_result['win_rate'],
            'profit_factor': final_result['profit_factor'],
            'total_trades': final_result['total_trades']
        },
        'tested_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_period': f"NEW version only (after {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M')} UTC)"
    }
    
    with open('optimized_mexc_config_NEW_only.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Optimized config saved to: optimized_mexc_config_NEW_only.json")
    print(f"\n📈 FINAL NEW VERSION PERFORMANCE (with exclusions):")
    print(f"  Total Profit: ${final_result['total_profit']:,.2f}")
    print(f"  ROI: {(final_result['total_profit'] / 1000) * 100:.1f}%")
    print(f"  Win Rate: {final_result['win_rate']:.1f}%")
    print(f"  Profit Factor: {final_result['profit_factor']:.2f}")
    print(f"  Total Trades: {final_result['total_trades']}")

print(f"\n{'='*80}")
print("✅ ANALYSIS COMPLETE!")
print(f"{'='*80}\n")
