#!/usr/bin/env python3
"""
MEXC Trading Strategy Optimizer - TARGET_MIN VERSION
Использует target_min из сигнала для Take-Profit
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

MEXC_TAKER_FEE = 0.0006
POSITION_SIZE_USDT = 100
MIN_CONFIDENCE = 0.50

def simulate_trade_with_target(signal, leverage, sl_pct):
    """
    Симуляция сделки с target_min для TP
    SL остается фиксированным (% от депозита)
    TP = target_min из сигнала
    """
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    target_min = signal['target_min']
    
    # Если target_min не задан, пропускаем сигнал
    if target_min == 0 or target_min == entry_price:
        return None
    
    entry_fee_pct = MEXC_TAKER_FEE
    
    # SL от депозита
    sl_price_move_pct = sl_pct / leverage
    
    if verdict == "SELL":
        # Short: target_min должен быть НИЖЕ entry (цена падает)
        if target_min >= entry_price:
            return None
        
        stop_loss_price = entry_price * (1 + sl_price_move_pct / 100)
        take_profit_price = target_min  # ← Используем target_min!
        
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
        
    else:  # BUY
        # Long: target_min должен быть ВЫШЕ entry (цена растет)
        if target_min <= entry_price:
            return None
        
        stop_loss_price = entry_price * (1 - sl_price_move_pct / 100)
        take_profit_price = target_min  # ← Используем target_min!
        
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
    
    # Рассчитываем какой % от депозита это составляет
    tp_deposit_pct = abs(price_change_pct) * leverage
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0,
        'exit_price': exit_price,
        'tp_price': take_profit_price,
        'sl_price': stop_loss_price,
        'tp_deposit_pct': tp_deposit_pct,
        'price_change_pct': price_change_pct
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
                    'target_min': float(row['target_min']) if row['target_min'] else 0,
                    'target_max': float(row['target_max']) if row['target_max'] else 0,
                    'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                    'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                    'final_price': float(row['final_price']) if row['final_price'] else entry_price,
                    'duration_actual': int(row['duration_actual']) if row['duration_actual'] else 0,
                }
                
                signals.append(signal)
                
            except (ValueError, KeyError):
                continue
    
    return signals

def evaluate_strategy(signals, leverage, sl_pct, excluded_patterns=None):
    """Оценка стратегии на сигналах"""
    filtered_signals = signals
    
    if excluded_patterns:
        filtered_signals = [s for s in signals if (s['symbol'], s['verdict']) not in excluded_patterns]
    
    trades = []
    for signal in filtered_signals:
        trade = simulate_trade_with_target(signal, leverage, sl_pct)
        if trade is not None:
            trades.append((signal, trade))
    
    if len(trades) == 0:
        return None
    
    total_profit = sum(t['profit_usdt'] for _, t in trades)
    wins = sum(1 for _, t in trades if t['win'])
    win_rate = wins / len(trades) * 100 if trades else 0
    
    winning_profits = [t['profit_usdt'] for _, t in trades if t['win']]
    losing_profits = [t['profit_usdt'] for _, t in trades if not t['win']]
    
    total_wins = sum(winning_profits) if winning_profits else 0
    total_losses = abs(sum(losing_profits)) if losing_profits else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    sl_count = sum(1 for _, t in trades if t['exit_reason'] == 'STOP_LOSS')
    tp_count = sum(1 for _, t in trades if t['exit_reason'] == 'TAKE_PROFIT')
    
    # Средний TP в % от депозита
    avg_tp_deposit_pct = statistics.mean([t['tp_deposit_pct'] for _, t in trades if t['exit_reason'] == 'TAKE_PROFIT']) if tp_count > 0 else 0
    
    return {
        'total_profit': total_profit,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_trades': len(trades),
        'sl_rate': sl_count / len(trades) * 100,
        'tp_rate': tp_count / len(trades) * 100,
        'avg_profit': total_profit / len(trades) if trades else 0,
        'avg_tp_deposit_pct': avg_tp_deposit_pct
    }

def find_worst_patterns(signals, leverage, sl_pct, n=5):
    """Находит N худших паттернов"""
    pattern_stats = defaultdict(lambda: {'profit': 0, 'count': 0})
    
    for signal in signals:
        trade = simulate_trade_with_target(signal, leverage, sl_pct)
        if trade is None:
            continue
        
        pattern = (signal['symbol'], signal['verdict'])
        pattern_stats[pattern]['profit'] += trade['profit_usdt']
        pattern_stats[pattern]['count'] += 1
    
    pattern_avg = {}
    for pattern, stats in pattern_stats.items():
        if stats['count'] >= 3:
            pattern_avg[pattern] = stats['profit'] / stats['count']
    
    worst = sorted(pattern_avg.items(), key=lambda x: x[1])[:n]
    return [p[0] for p in worst]

# STEP 1: Загрузка данных
print("\n" + "="*80)
print("MEXC OPTIMIZER - TARGET_MIN VERSION")
print("="*80)
print("\n💡 Используем target_min из сигнала для Take-Profit")
print("   SL остается фиксированным (% от депозита)\n")

signals = load_signals_24h()
print(f"📊 Loaded {len(signals)} signals from last 24 hours")

# STEP 2: Поиск оптимальных параметров
print("\n🔍 STEP 1: Searching for Optimal Leverage and SL...")

leverage_options = [10, 15, 20, 25, 30, 40, 50]
sl_options = [15, 20, 25, 30, 35, 40]

best_result = None
best_params = None

for leverage in leverage_options:
    for sl_pct in sl_options:
        result = evaluate_strategy(signals, leverage, sl_pct)
        
        if result and result['total_profit'] > 0:
            if (result['win_rate'] > 40 and 
                result['profit_factor'] > 1.2 and
                result['sl_rate'] < 60):
                
                if best_result is None or result['total_profit'] > best_result['total_profit']:
                    best_result = result
                    best_params = {
                        'leverage': leverage,
                        'sl_pct': sl_pct
                    }

if best_params is None:
    print("❌ No profitable strategy found with target_min!")
    exit(1)

print(f"\n🏆 BEST PARAMETERS:")
print(f"  Leverage: {best_params['leverage']}x")
print(f"  Stop-Loss: {best_params['sl_pct']}% от депозита")
print(f"  Take-Profit: target_min из сигнала (динамический)")
print(f"  → Price SL: -{best_params['sl_pct']/best_params['leverage']:.3f}%")
print(f"  → Avg TP: ~{best_result['avg_tp_deposit_pct']:.1f}% от депозита")

print(f"\n📈 RESULTS:")
print(f"  Total profit: ${best_result['total_profit']:,.2f}")
print(f"  Win rate: {best_result['win_rate']:.1f}%")
print(f"  Profit factor: {best_result['profit_factor']:.2f}")
print(f"  SL rate: {best_result['sl_rate']:.1f}%")
print(f"  TP rate: {best_result['tp_rate']:.1f}%")

# STEP 3: Анализ по монетам
print(f"\n🔍 STEP 2: Analyzing Performance by Symbol/Direction...")

pattern_stats = defaultdict(lambda: {
    'trades': [], 'wins': 0, 'losses': 0, 'total_profit': 0
})

for signal in signals:
    trade = simulate_trade_with_target(signal, best_params['leverage'], best_params['sl_pct'])
    if trade is None:
        continue
    
    pattern = (signal['symbol'], signal['verdict'])
    pattern_stats[pattern]['trades'].append(trade)
    pattern_stats[pattern]['total_profit'] += trade['profit_usdt']
    if trade['win']:
        pattern_stats[pattern]['wins'] += 1
    else:
        pattern_stats[pattern]['losses'] += 1

sorted_patterns = sorted(pattern_stats.items(), 
                        key=lambda x: x[1]['total_profit'])

print(f"\n{'Symbol':<12} {'Side':<5} {'Trades':<7} {'Win%':<7} {'Total $':<12} {'Avg $':<10}")
print("-"*70)

for (symbol, side), stats in sorted_patterns:
    total = len(stats['trades'])
    wr = stats['wins'] / total * 100 if total > 0 else 0
    avg = stats['total_profit'] / total if total > 0 else 0
    
    print(f"{symbol:<12} {side:<5} {total:<7} {wr:>5.1f}% ${stats['total_profit']:>10,.2f} ${avg:>8.2f}")

# STEP 4: Поиск худших паттернов
print(f"\n🔍 STEP 3: Finding Worst Patterns...")

worst_patterns = find_worst_patterns(
    signals, 
    best_params['leverage'], 
    best_params['sl_pct'],
    n=7  # Топ-7 худших
)

print(f"\n❌ 7 WORST PATTERNS TO EXCLUDE:")
for i, (symbol, verdict) in enumerate(worst_patterns, 1):
    pattern_signals = [s for s in signals if s['symbol'] == symbol and s['verdict'] == verdict]
    trades = []
    for s in pattern_signals:
        t = simulate_trade_with_target(s, best_params['leverage'], best_params['sl_pct'])
        if t:
            trades.append(t)
    
    total_p = sum(t['profit_usdt'] for t in trades)
    avg_p = total_p / len(trades) if trades else 0
    
    print(f"  {i}. {symbol} {verdict:4s} - {len(trades):3d} trades, avg: ${avg_p:>7.2f}")

# STEP 5: Тест с исключением
print(f"\n🔍 STEP 4: Testing with Excluded Patterns...")

improved_result = evaluate_strategy(
    signals,
    best_params['leverage'],
    best_params['sl_pct'],
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

# STEP 6: Финальная модель
print(f"\n{'='*80}")
print("🎯 FINAL OPTIMIZED MODEL - TARGET_MIN VERSION")
print(f"{'='*80}")

starting_capital = 1000
final_balance = starting_capital + improved_result['total_profit']
roi = ((final_balance - starting_capital) / starting_capital) * 100

print(f"\n⚙️  PARAMETERS:")
print(f"  • Leverage: {best_params['leverage']}x")
print(f"  • Stop-Loss: {best_params['sl_pct']}% от депозита (цена: -{best_params['sl_pct']/best_params['leverage']:.3f}%)")
print(f"  • Take-Profit: target_min из сигнала (динамический)")
print(f"  • Avg TP when hit: ~{improved_result['avg_tp_deposit_pct']:.1f}% от депозита")
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
    'take_profit_type': 'target_min',
    'avg_take_profit_pct': improved_result['avg_tp_deposit_pct'],
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

with open('optimized_mexc_config_target_min.json', 'w') as f:
    json.dump(optimized_config, f, indent=2)

print(f"\n💾 Configuration saved to: optimized_mexc_config_target_min.json")

# Сравнение с фиксированным TP
print(f"\n{'='*80}")
print("📊 COMPARISON: TARGET_MIN vs FIXED TP")
print(f"{'='*80}")

try:
    with open('optimized_mexc_config.json', 'r') as f:
        fixed_config = json.load(f)
    
    print(f"\n{'Metric':<25} {'Fixed TP (50%)':<18} {'Target_min':<18} {'Winner':<10}")
    print("-"*75)
    
    fixed_profit = fixed_config['performance']['total_profit']
    target_profit = improved_result['total_profit']
    winner = "🏆 TARGET" if target_profit > fixed_profit else "🏆 FIXED"
    print(f"{'Total Profit':<25} ${fixed_profit:>14,.2f}   ${target_profit:>14,.2f}   {winner}")
    
    fixed_roi = fixed_config['performance']['roi']
    target_roi = roi
    winner = "🏆 TARGET" if target_roi > fixed_roi else "🏆 FIXED"
    print(f"{'ROI':<25} {fixed_roi:>14.1f}%   {target_roi:>14.1f}%   {winner}")
    
    fixed_wr = fixed_config['performance']['win_rate']
    target_wr = improved_result['win_rate']
    winner = "🏆 TARGET" if target_wr > fixed_wr else "🏆 FIXED"
    print(f"{'Win Rate':<25} {fixed_wr:>14.1f}%   {target_wr:>14.1f}%   {winner}")
    
    fixed_pf = fixed_config['performance']['profit_factor']
    target_pf = improved_result['profit_factor']
    winner = "🏆 TARGET" if target_pf > fixed_pf else "🏆 FIXED"
    print(f"{'Profit Factor':<25} {fixed_pf:>14.2f}   {target_pf:>14.2f}   {winner}")
    
    fixed_trades = fixed_config['performance']['total_trades']
    target_trades = improved_result['total_trades']
    print(f"{'Total Trades':<25} {fixed_trades:>14}   {target_trades:>14}")

except FileNotFoundError:
    print("\n⚠️  Previous config not found, skipping comparison")

print(f"\n{'='*80}")
print("✅ OPTIMIZATION COMPLETE!")
print(f"{'='*80}\n")
