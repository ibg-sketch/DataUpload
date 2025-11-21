#!/usr/bin/env python3
"""
ФИНАЛЬНЫЙ КОМПЛЕКСНЫЙ АНАЛИЗ - NEW BOT VERSION ONLY
Данные: после 2025-11-04 16:00:00 UTC (18:00 Киев)

Тестируем 3 стратегии TP:
1. Fixed TP (фиксированный % от депозита)
2. Target_min TP (начало таргет зоны)
3. Target_max TP (конец таргет зоны)

Анализируем каждую монету отдельно
"""

import csv
from datetime import datetime
from collections import defaultdict
import statistics
import json

MEXC_TAKER_FEE = 0.0006
POSITION_SIZE_USDT = 100
MIN_CONFIDENCE = 0.50
CUTOFF_TIME = datetime(2025, 11, 4, 16, 0, 0)  # 18:00 Kyiv

def simulate_trade_fixed_tp(signal, leverage, sl_pct, tp_pct):
    """Стратегия 1: Фиксированный TP"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    
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
    
    gross_profit_pct = price_change_pct * leverage
    net_profit_pct = gross_profit_pct - (MEXC_TAKER_FEE * 2 * 100)
    profit_usdt = (net_profit_pct / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

def simulate_trade_target_min(signal, leverage, sl_pct):
    """Стратегия 2: TP = target_min"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    target_min = signal['target_min']
    
    if target_min == 0 or target_min == entry_price:
        return None
    
    if verdict == "SELL" and target_min >= entry_price:
        return None
    if verdict == "BUY" and target_min <= entry_price:
        return None
    
    sl_price_move_pct = sl_pct / leverage
    
    if verdict == "SELL":
        stop_loss_price = entry_price * (1 + sl_price_move_pct / 100)
        take_profit_price = target_min
        
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
        take_profit_price = target_min
        
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
    
    gross_profit_pct = price_change_pct * leverage
    net_profit_pct = gross_profit_pct - (MEXC_TAKER_FEE * 2 * 100)
    profit_usdt = (net_profit_pct / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

def simulate_trade_target_max(signal, leverage, sl_pct):
    """Стратегия 3: TP = target_max"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    target_max = signal['target_max']
    
    if target_max == 0 or target_max == entry_price:
        return None
    
    if verdict == "SELL" and target_max >= entry_price:
        return None
    if verdict == "BUY" and target_max <= entry_price:
        return None
    
    sl_price_move_pct = sl_pct / leverage
    
    if verdict == "SELL":
        stop_loss_price = entry_price * (1 + sl_price_move_pct / 100)
        take_profit_price = target_max
        
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
        take_profit_price = target_max
        
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
    
    gross_profit_pct = price_change_pct * leverage
    net_profit_pct = gross_profit_pct - (MEXC_TAKER_FEE * 2 * 100)
    profit_usdt = (net_profit_pct / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

def load_new_signals():
    """Загрузка ТОЛЬКО новых сигналов"""
    signals = []
    
    with open('effectiveness_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
                
                if timestamp < CUTOFF_TIME or row['result'] == 'CANCELLED':
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
                    'target_min': float(row['target_min']) if row['target_min'] else 0,
                    'target_max': float(row['target_max']) if row['target_max'] else 0,
                    'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                    'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                    'final_price': float(row['final_price']) if row['final_price'] else entry_price,
                }
                
                signals.append(signal)
                
            except (ValueError, KeyError):
                continue
    
    return signals

def evaluate_strategy(trades):
    """Оценка результатов"""
    if not trades:
        return None
    
    total_profit = sum(t['profit_usdt'] for t in trades)
    wins = sum(1 for t in trades if t['win'])
    win_rate = wins / len(trades) * 100
    
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
        'avg_profit': total_profit / len(trades)
    }

# Load data
print("="*80)
print("ФИНАЛЬНЫЙ КОМПЛЕКСНЫЙ АНАЛИЗ - NEW BOT VERSION")
print("="*80)
print(f"\n📅 Данные: после {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M')} UTC (18:00 Киев)")
print(f"🤖 Версия: 5m candles + Enhanced Formula v2 + Hybrid Regime")

signals = load_new_signals()
print(f"\n📊 Загружено сигналов: {len(signals)}")

if len(signals) < 50:
    print("\n⚠️  Недостаточно данных для анализа!")
    exit(1)

# Статистика по монетам
symbols_stats = defaultdict(lambda: {'total': 0, 'buy': 0, 'sell': 0})
for s in signals:
    symbols_stats[s['symbol']]['total'] += 1
    if s['verdict'] == 'BUY':
        symbols_stats[s['symbol']]['buy'] += 1
    else:
        symbols_stats[s['symbol']]['sell'] += 1

print(f"\n📈 Распределение по монетам:")
for symbol in sorted(symbols_stats.keys()):
    stats = symbols_stats[symbol]
    print(f"  {symbol:<12} {stats['total']:>3} сигналов (BUY: {stats['buy']:>2}, SELL: {stats['sell']:>2})")

# СТРАТЕГИЯ 1: Fixed TP
print(f"\n{'='*80}")
print("СТРАТЕГИЯ 1: ФИКСИРОВАННЫЙ TP")
print(f"{'='*80}")

leverage_options = [20, 25, 30, 40, 50]
sl_options = [15, 20, 25, 30, 35, 40]
tp_options = [30, 40, 50, 60, 75]

best_fixed = None
best_fixed_params = None

for leverage in leverage_options:
    for sl_pct in sl_options:
        for tp_pct in tp_options:
            if tp_pct <= sl_pct:
                continue
            
            trades = [simulate_trade_fixed_tp(s, leverage, sl_pct, tp_pct) for s in signals]
            result = evaluate_strategy(trades)
            
            if result and result['total_profit'] > 0:
                if (result['win_rate'] > 40 and result['profit_factor'] > 1.2):
                    if best_fixed is None or result['total_profit'] > best_fixed['total_profit']:
                        best_fixed = result
                        best_fixed_params = {'leverage': leverage, 'sl': sl_pct, 'tp': tp_pct}

if best_fixed_params:
    print(f"\n🏆 Оптимальные параметры:")
    print(f"  Leverage: {best_fixed_params['leverage']}x")
    print(f"  SL: {best_fixed_params['sl']}% депозита")
    print(f"  TP: {best_fixed_params['tp']}% депозита")
    print(f"\n📈 Результаты:")
    for key, value in best_fixed.items():
        if 'profit' in key or 'rate' in key:
            if isinstance(value, float):
                if 'rate' in key or 'win' in key:
                    print(f"  {key}: {value:.1f}%")
                else:
                    print(f"  {key}: ${value:,.2f}")
        else:
            print(f"  {key}: {value}")

# СТРАТЕГИЯ 2: Target_min
print(f"\n{'='*80}")
print("СТРАТЕГИЯ 2: TP = TARGET_MIN (начало таргет зоны)")
print(f"{'='*80}")

best_target_min = None
best_target_min_params = None

for leverage in leverage_options:
    for sl_pct in sl_options:
        trades = []
        for s in signals:
            trade = simulate_trade_target_min(s, leverage, sl_pct)
            if trade:
                trades.append(trade)
        
        result = evaluate_strategy(trades)
        
        if result and result['total_profit'] > 0:
            if (result['win_rate'] > 40 and result['profit_factor'] > 1.2):
                if best_target_min is None or result['total_profit'] > best_target_min['total_profit']:
                    best_target_min = result
                    best_target_min_params = {'leverage': leverage, 'sl': sl_pct}

if best_target_min_params:
    print(f"\n🏆 Оптимальные параметры:")
    print(f"  Leverage: {best_target_min_params['leverage']}x")
    print(f"  SL: {best_target_min_params['sl']}% депозита")
    print(f"  TP: target_min (динамический)")
    print(f"\n📈 Результаты:")
    for key, value in best_target_min.items():
        if 'profit' in key or 'rate' in key:
            if isinstance(value, float):
                if 'rate' in key or 'win' in key:
                    print(f"  {key}: {value:.1f}%")
                else:
                    print(f"  {key}: ${value:,.2f}")
        else:
            print(f"  {key}: {value}")

# СТРАТЕГИЯ 3: Target_max
print(f"\n{'='*80}")
print("СТРАТЕГИЯ 3: TP = TARGET_MAX (конец таргет зоны)")
print(f"{'='*80}")

best_target_max = None
best_target_max_params = None

for leverage in leverage_options:
    for sl_pct in sl_options:
        trades = []
        for s in signals:
            trade = simulate_trade_target_max(s, leverage, sl_pct)
            if trade:
                trades.append(trade)
        
        result = evaluate_strategy(trades)
        
        if result and result['total_profit'] > 0:
            if (result['win_rate'] > 40 and result['profit_factor'] > 1.2):
                if best_target_max is None or result['total_profit'] > best_target_max['total_profit']:
                    best_target_max = result
                    best_target_max_params = {'leverage': leverage, 'sl': sl_pct}

if best_target_max_params:
    print(f"\n🏆 Оптимальные параметры:")
    print(f"  Leverage: {best_target_max_params['leverage']}x")
    print(f"  SL: {best_target_max_params['sl']}% депозита")
    print(f"  TP: target_max (динамический)")
    print(f"\n📈 Результаты:")
    for key, value in best_target_max.items():
        if 'profit' in key or 'rate' in key:
            if isinstance(value, float):
                if 'rate' in key or 'win' in key:
                    print(f"  {key}: {value:.1f}%")
                else:
                    print(f"  {key}: ${value:,.2f}")
        else:
            print(f"  {key}: {value}")

# СРАВНЕНИЕ СТРАТЕГИЙ
print(f"\n{'='*80}")
print("📊 СРАВНЕНИЕ СТРАТЕГИЙ")
print(f"{'='*80}")

strategies = []
if best_fixed:
    strategies.append(('Fixed TP', best_fixed, best_fixed_params))
if best_target_min:
    strategies.append(('Target_min', best_target_min, best_target_min_params))
if best_target_max:
    strategies.append(('Target_max', best_target_max, best_target_max_params))

if strategies:
    print(f"\n{'Strategy':<15} {'Profit':<15} {'ROI':<12} {'Win%':<8} {'PF':<8} {'TP%':<8}")
    print("-"*70)
    
    for name, result, params in strategies:
        roi = (result['total_profit'] / 1000) * 100
        print(f"{name:<15} ${result['total_profit']:>10,.2f}   {roi:>6.1f}%   {result['win_rate']:>5.1f}%  {result['profit_factor']:>5.2f}  {result['tp_rate']:>5.1f}%")
    
    # Лучшая стратегия
    best_strategy = max(strategies, key=lambda x: x[1]['total_profit'])
    print(f"\n🏆 ЛУЧШАЯ СТРАТЕГИЯ: {best_strategy[0]}")
    print(f"   Profit: ${best_strategy[1]['total_profit']:,.2f}")
    print(f"   ROI: {(best_strategy[1]['total_profit'] / 1000) * 100:.1f}%")

# АНАЛИЗ ПО МОНЕТАМ (для лучшей стратегии)
print(f"\n{'='*80}")
print(f"АНАЛИЗ ПО МОНЕТАМ - {best_strategy[0]}")
print(f"{'='*80}")

coin_performance = defaultdict(lambda: {'profit': 0, 'trades': 0, 'wins': 0})

if best_strategy[0] == 'Fixed TP':
    params = best_strategy[2]
    for signal in signals:
        trade = simulate_trade_fixed_tp(signal, params['leverage'], params['sl'], params['tp'])
        coin_performance[signal['symbol']]['profit'] += trade['profit_usdt']
        coin_performance[signal['symbol']]['trades'] += 1
        if trade['win']:
            coin_performance[signal['symbol']]['wins'] += 1
elif best_strategy[0] == 'Target_min':
    params = best_strategy[2]
    for signal in signals:
        trade = simulate_trade_target_min(signal, params['leverage'], params['sl'])
        if trade:
            coin_performance[signal['symbol']]['profit'] += trade['profit_usdt']
            coin_performance[signal['symbol']]['trades'] += 1
            if trade['win']:
                coin_performance[signal['symbol']]['wins'] += 1
else:  # Target_max
    params = best_strategy[2]
    for signal in signals:
        trade = simulate_trade_target_max(signal, params['leverage'], params['sl'])
        if trade:
            coin_performance[signal['symbol']]['profit'] += trade['profit_usdt']
            coin_performance[signal['symbol']]['trades'] += 1
            if trade['win']:
                coin_performance[signal['symbol']]['wins'] += 1

sorted_coins = sorted(coin_performance.items(), key=lambda x: x[1]['profit'], reverse=True)

print(f"\n{'Symbol':<12} {'Trades':<8} {'Win%':<8} {'Total Profit':<15} {'Avg/Trade':<12} {'Рейтинг':<10}")
print("-"*75)

for symbol, stats in sorted_coins:
    wr = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
    avg = stats['profit'] / stats['trades'] if stats['trades'] > 0 else 0
    
    if stats['profit'] > 500 and wr > 65:
        rating = "⭐⭐⭐ TOP"
    elif stats['profit'] > 200 and wr > 55:
        rating = "⭐⭐ GOOD"
    elif stats['profit'] > 0:
        rating = "⭐ OK"
    else:
        rating = "❌ BAD"
    
    print(f"{symbol:<12} {stats['trades']:<8} {wr:>5.1f}%  ${stats['profit']:>12,.2f}  ${avg:>10,.2f}  {rating}")

# ТОП монеты
top_coins = [symbol for symbol, stats in sorted_coins if stats['profit'] > 200 and stats['wins'] / stats['trades'] > 0.55]
bad_coins = [symbol for symbol, stats in sorted_coins if stats['profit'] < 0]

print(f"\n✅ ТОП МОНЕТЫ (для торговли):")
for coin in top_coins:
    stats = coin_performance[coin]
    print(f"   {coin}: ${stats['profit']:,.2f} прибыли, {stats['wins']/stats['trades']*100:.1f}% WR")

print(f"\n❌ ПЛОХИЕ МОНЕТЫ (исключить):")
for coin in bad_coins:
    stats = coin_performance[coin]
    print(f"   {coin}: ${stats['profit']:,.2f} убытка")

# ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ
print(f"\n{'='*80}")
print("🎯 ФИНАЛЬНАЯ РЕКОМЕНДАЦИЯ")
print(f"{'='*80}")

print(f"\n📋 ОПТИМАЛЬНАЯ МОДЕЛЬ ТОРГОВЛИ:")
print(f"\n  Стратегия: {best_strategy[0]}")
print(f"  Параметры:")
for key, value in best_strategy[2].items():
    if key == 'leverage':
        print(f"    Leverage: {value}x")
    elif key == 'sl':
        print(f"    Stop-Loss: {value}% от депозита (-{value/best_strategy[2]['leverage']:.2f}% цены)")
    elif key == 'tp':
        print(f"    Take-Profit: {value}% от депозита (+{value/best_strategy[2]['leverage']:.2f}% цены)")

print(f"\n  Торговать только:")
for coin in top_coins[:5]:
    print(f"    ✅ {coin}")

if bad_coins:
    print(f"\n  Исключить из торговли:")
    for coin in bad_coins:
        print(f"    ❌ {coin}")

print(f"\n  Ожидаемые результаты:")
print(f"    ROI: {(best_strategy[1]['total_profit'] / 1000) * 100:.1f}% за 17 часов")
print(f"    Экстраполяция на 24ч: ~{(best_strategy[1]['total_profit'] / 17 * 24 / 1000) * 100:.1f}%")
print(f"    Win Rate: {best_strategy[1]['win_rate']:.1f}%")
print(f"    Profit Factor: {best_strategy[1]['profit_factor']:.2f}")
print(f"    Avg Profit/Trade: ${best_strategy[1]['avg_profit']:.2f}")

# Сохранение конфигурации
final_config = {
    'version': 'NEW (5m candles, Enhanced Formula v2, Hybrid Regime)',
    'strategy': best_strategy[0],
    'parameters': best_strategy[2],
    'top_coins': top_coins[:5],
    'excluded_coins': bad_coins,
    'performance': {
        'total_profit': best_strategy[1]['total_profit'],
        'roi': (best_strategy[1]['total_profit'] / 1000) * 100,
        'win_rate': best_strategy[1]['win_rate'],
        'profit_factor': best_strategy[1]['profit_factor'],
        'avg_profit': best_strategy[1]['avg_profit'],
        'tp_rate': best_strategy[1]['tp_rate'],
        'sl_rate': best_strategy[1]['sl_rate']
    },
    'tested_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'data_period': f"NEW version (after {CUTOFF_TIME.strftime('%Y-%m-%d %H:%M')} UTC)"
}

with open('FINAL_OPTIMAL_CONFIG.json', 'w') as f:
    json.dump(final_config, f, indent=2)

print(f"\n💾 Конфигурация сохранена: FINAL_OPTIMAL_CONFIG.json")

print(f"\n{'='*80}\n")
