#!/usr/bin/env python3
"""
MEXC Trading Strategy Optimizer
Находит оптимальное плечо, стопы и фильтры сигналов
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

MEXC_TAKER_FEE = 0.0006
POSITION_SIZE_USDT = 100
MIN_CONFIDENCE = 0.50

def simulate_trade(signal, leverage, sl_pct, tp_pct):
    """Симуляция сделки с заданными параметрами"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    
    entry_fee_pct = MEXC_TAKER_FEE
    
    # SL/TP от депозита -> движение цены
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

def load_signals_24h():
    """Загрузка сигналов за последние 24 часа"""
    now = datetime.now()
    cutoff_time = now - timedelta(hours=24)
    
    signals = []
    with open('effectiveness_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
                
                if timestamp < cutoff_time:
                    continue
                
                if row['result'] == 'CANCELLED':
                    continue
                
                confidence = float(row['confidence'])
                entry_price = float(row['entry_price'])
                
                if entry_price == 0 or confidence < MIN_CONFIDENCE:
                    continue
                
                signal = {
                    'timestamp': row['timestamp_sent'],
                    'symbol': row['symbol'],
                    'verdict': row['verdict'],
                    'confidence': confidence,
                    'entry_price': entry_price,
                    'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                    'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                    'final_price': float(row['final_price']) if row['final_price'] else entry_price,
                    'duration_actual': int(row['duration_actual']) if row['duration_actual'] else 0,
                }
                
                signals.append(signal)
                
            except (ValueError, KeyError):
                continue
    
    return signals

def evaluate_strategy(signals, leverage, sl_pct, tp_pct, excluded_patterns=None):
    """Оценка стратегии на сигналах"""
    filtered_signals = signals
    
    # Фильтрация худших паттернов
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

def find_worst_patterns(signals, leverage, sl_pct, tp_pct, n=5):
    """Находит N худших паттернов (символ + направление)"""
    pattern_stats = defaultdict(lambda: {'profit': 0, 'count': 0})
    
    for signal in signals:
        trade = simulate_trade(signal, leverage, sl_pct, tp_pct)
        pattern = (signal['symbol'], signal['verdict'])
        pattern_stats[pattern]['profit'] += trade['profit_usdt']
        pattern_stats[pattern]['count'] += 1
    
    # Сортировка по средней прибыли
    pattern_avg = {}
    for pattern, stats in pattern_stats.items():
        if stats['count'] >= 3:  # Минимум 3 сделки
            pattern_avg[pattern] = stats['profit'] / stats['count']
    
    # Худшие N паттернов
    worst = sorted(pattern_avg.items(), key=lambda x: x[1])[:n]
    return [p[0] for p in worst]

# STEP 1: Загрузка данных
print("\n" + "="*80)
print("MEXC TRADING STRATEGY OPTIMIZER")
print("="*80)

signals = load_signals_24h()
print(f"\n📊 Loaded {len(signals)} signals from last 24 hours")

if len(signals) < 50:
    print("⚠️  Not enough signals for optimization!")
    exit(1)

# STEP 2: Грид-поиск оптимальных параметров
print("\n🔍 STEP 1: Grid Search for Optimal Parameters...")
print("Testing combinations:")

leverage_options = [10, 15, 20, 25, 30, 40, 50, 75, 100]
sl_options = [10, 15, 20, 25, 30, 35, 40]
tp_options = [15, 20, 25, 30, 35, 40, 50]

best_result = None
best_params = None

counter = 0
total_combinations = len(leverage_options) * len(sl_options) * len(tp_options)

for leverage in leverage_options:
    for sl_pct in sl_options:
        for tp_pct in tp_options:
            if tp_pct <= sl_pct:  # TP должен быть больше SL
                continue
            
            result = evaluate_strategy(signals, leverage, sl_pct, tp_pct)
            
            if result and result['total_profit'] > 0:
                counter += 1
                
                # Критерии: profit > 0, win_rate > 40%, profit_factor > 1.2
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

if best_params is None:
    print("❌ No profitable strategy found! Using default...")
    best_params = {'leverage': 20, 'sl_pct': 20, 'tp_pct': 30}
    best_result = evaluate_strategy(signals, 20, 20, 30)

print(f"\n✅ Found {counter} profitable combinations")
print(f"\n🏆 BEST PARAMETERS:")
print(f"  Leverage: {best_params['leverage']}x")
print(f"  Stop-Loss: {best_params['sl_pct']}% от депозита")
print(f"  Take-Profit: {best_params['tp_pct']}% от депозита")
print(f"  → Price SL: -{best_params['sl_pct']/best_params['leverage']:.3f}%")
print(f"  → Price TP: +{best_params['tp_pct']/best_params['leverage']:.3f}%")
print(f"\n📈 RESULTS:")
print(f"  Total profit: ${best_result['total_profit']:,.2f}")
print(f"  Win rate: {best_result['win_rate']:.1f}%")
print(f"  Profit factor: {best_result['profit_factor']:.2f}")
print(f"  SL rate: {best_result['sl_rate']:.1f}%")
print(f"  TP rate: {best_result['tp_rate']:.1f}%")

# STEP 3: Поиск худших паттернов
print(f"\n🔍 STEP 2: Finding Worst Patterns...")

worst_patterns = find_worst_patterns(
    signals, 
    best_params['leverage'], 
    best_params['sl_pct'], 
    best_params['tp_pct'],
    n=5
)

print(f"\n❌ 5 WORST PATTERNS TO EXCLUDE:")
for i, (symbol, verdict) in enumerate(worst_patterns, 1):
    # Подсчитываем статистику по паттерну
    pattern_signals = [s for s in signals if s['symbol'] == symbol and s['verdict'] == verdict]
    trades = [simulate_trade(s, best_params['leverage'], best_params['sl_pct'], best_params['tp_pct']) 
              for s in pattern_signals]
    
    total_p = sum(t['profit_usdt'] for t in trades)
    avg_p = total_p / len(trades) if trades else 0
    
    print(f"  {i}. {symbol} {verdict:4s} - {len(trades):3d} trades, avg: ${avg_p:>7.2f}")

# STEP 4: Тест с исключением худших
print(f"\n🔍 STEP 3: Testing with Excluded Patterns...")

improved_result = evaluate_strategy(
    signals,
    best_params['leverage'],
    best_params['sl_pct'],
    best_params['tp_pct'],
    excluded_patterns=set(worst_patterns)
)

print(f"\n📊 COMPARISON:")
print(f"\n{'Metric':<20} {'Original':<15} {'Optimized':<15} {'Change':<15}")
print("-" * 65)
print(f"{'Total Profit':<20} ${best_result['total_profit']:>10,.2f}   ${improved_result['total_profit']:>10,.2f}   "
      f"{improved_result['total_profit'] - best_result['total_profit']:>+10,.2f}")
print(f"{'Win Rate':<20} {best_result['win_rate']:>10,.1f}%   {improved_result['win_rate']:>10,.1f}%   "
      f"{improved_result['win_rate'] - best_result['win_rate']:>+10,.1f}%")
print(f"{'Profit Factor':<20} {best_result['profit_factor']:>10,.2f}   {improved_result['profit_factor']:>10,.2f}   "
      f"{improved_result['profit_factor'] - best_result['profit_factor']:>+10,.2f}")
print(f"{'Total Trades':<20} {best_result['total_trades']:>10}   {improved_result['total_trades']:>10}   "
      f"{improved_result['total_trades'] - best_result['total_trades']:>+10}")

# STEP 5: Финальная модель
print(f"\n{'='*80}")
print("🎯 FINAL OPTIMIZED MODEL")
print(f"{'='*80}")

starting_capital = 1000
final_balance = starting_capital + improved_result['total_profit']
roi = ((final_balance - starting_capital) / starting_capital) * 100

print(f"\n⚙️  PARAMETERS:")
print(f"  • Leverage: {best_params['leverage']}x")
print(f"  • Stop-Loss: {best_params['sl_pct']}% от депозита (цена: -{best_params['sl_pct']/best_params['leverage']:.3f}%)")
print(f"  • Take-Profit: {best_params['tp_pct']}% от депозита (цена: +{best_params['tp_pct']/best_params['leverage']:.3f}%)")
print(f"  • Position Size: ${POSITION_SIZE_USDT} USDT")
print(f"  • Min Confidence: {MIN_CONFIDENCE*100}%")

print(f"\n🚫 EXCLUDED PATTERNS:")
for symbol, verdict in worst_patterns:
    print(f"  • {symbol} {verdict}")

print(f"\n📈 PERFORMANCE (Last 24 hours):")
print(f"  • Total Profit: ${improved_result['total_profit']:,.2f} USDT")
print(f"  • Starting Capital: ${starting_capital:,.2f} USDT")
print(f"  • Final Balance: ${final_balance:,.2f} USDT")
print(f"  • ROI: {roi:.1f}%")
print(f"  • Win Rate: {improved_result['win_rate']:.1f}%")
print(f"  • Profit Factor: {improved_result['profit_factor']:.2f}")
print(f"  • Avg Profit/Trade: ${improved_result['avg_profit']:.2f}")
print(f"  • Total Trades: {improved_result['total_trades']}")
print(f"  • Stop-Loss Rate: {improved_result['sl_rate']:.1f}%")
print(f"  • Take-Profit Rate: {improved_result['tp_rate']:.1f}%")

# Сохранение результатов
import json

optimized_config = {
    'leverage': best_params['leverage'],
    'stop_loss_pct': best_params['sl_pct'],
    'take_profit_pct': best_params['tp_pct'],
    'position_size_usdt': POSITION_SIZE_USDT,
    'min_confidence': MIN_CONFIDENCE,
    'excluded_patterns': [[s, v] for s, v in worst_patterns],
    'performance': {
        'total_profit': improved_result['total_profit'],
        'roi': roi,
        'win_rate': improved_result['win_rate'],
        'profit_factor': improved_result['profit_factor'],
        'total_trades': improved_result['total_trades']
    },
    'tested_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'test_period_hours': 24
}

with open('optimized_mexc_config.json', 'w') as f:
    json.dump(optimized_config, f, indent=2)

print(f"\n💾 Configuration saved to: optimized_mexc_config.json")

print(f"\n{'='*80}")
print("✅ OPTIMIZATION COMPLETE!")
print(f"{'='*80}\n")
