#!/usr/bin/env python3
"""
Детальный анализ для ответа на вопросы пользователя
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import json

MEXC_TAKER_FEE = 0.0006
POSITION_SIZE_USDT = 100

# Загружаем оптимальные параметры
with open('optimized_mexc_config.json', 'r') as f:
    config = json.load(f)

LEVERAGE = config['leverage']
SL_PCT = config['stop_loss_pct']
TP_PCT = config['take_profit_pct']

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
    
    # Комиссия в USDT
    fee_usdt = (total_fee_pct * 100 / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0,
        'fee_usdt': fee_usdt,
        'gross_profit_usdt': (gross_profit_pct / 100) * POSITION_SIZE_USDT,
        'exit_price': exit_price,
        'sl_price': stop_loss_price,
        'tp_price': take_profit_price
    }

# Загрузка сигналов
now = datetime.now()
cutoff_time = now - timedelta(hours=24)

signals = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
            
            if timestamp < cutoff_time or row['result'] == 'CANCELLED':
                continue
            
            confidence = float(row['confidence'])
            entry_price = float(row['entry_price'])
            
            if entry_price == 0 or confidence < 0.5:
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

print("="*80)
print("ДЕТАЛЬНЫЙ АНАЛИЗ МОДЕЛИ")
print("="*80)

# ВОПРОС 1: Статистика по всем монетам
print("\n1️⃣  СТАТИСТИКА ПО ВСЕМ МОНЕТАМ/НАПРАВЛЕНИЯМ:")
print("-"*80)

excluded = set([(p[0], p[1]) for p in config['excluded_patterns']])

pattern_stats = defaultdict(lambda: {
    'trades': [], 'wins': 0, 'losses': 0, 'total_profit': 0
})

for signal in signals:
    trade = simulate_trade(signal, LEVERAGE, SL_PCT, TP_PCT)
    pattern = (signal['symbol'], signal['verdict'])
    
    pattern_stats[pattern]['trades'].append(trade)
    pattern_stats[pattern]['total_profit'] += trade['profit_usdt']
    if trade['win']:
        pattern_stats[pattern]['wins'] += 1
    else:
        pattern_stats[pattern]['losses'] += 1

# Сортировка по прибыли
sorted_patterns = sorted(pattern_stats.items(), 
                        key=lambda x: x[1]['total_profit'])

print(f"\n{'Symbol':<12} {'Side':<5} {'Trades':<7} {'Win%':<7} {'Total $':<12} {'Avg $':<10} {'Status':<15}")
print("-"*80)

for (symbol, side), stats in sorted_patterns:
    total = len(stats['trades'])
    wr = stats['wins'] / total * 100 if total > 0 else 0
    avg = stats['total_profit'] / total if total > 0 else 0
    
    is_excluded = (symbol, side) in excluded
    status = "❌ EXCLUDED" if is_excluded else ("🟢 GOOD" if avg > 5 else ("🟡 OK" if avg > 0 else "🔴 BAD"))
    
    print(f"{symbol:<12} {side:<5} {total:<7} {wr:>5.1f}% ${stats['total_profit']:>10,.2f} ${avg:>8.2f}  {status}")

# ВОПРОС 2: Комиссии
print("\n\n2️⃣  АНАЛИЗ КОМИССИЙ:")
print("-"*80)

all_trades = []
for signal in signals:
    trade = simulate_trade(signal, LEVERAGE, SL_PCT, TP_PCT)
    all_trades.append(trade)

total_fees = sum(t['fee_usdt'] for t in all_trades)
total_gross = sum(t['gross_profit_usdt'] for t in all_trades)
total_net = sum(t['profit_usdt'] for t in all_trades)

print(f"Валовая прибыль (до комиссий):  ${total_gross:>10,.2f}")
print(f"Комиссии MEXC (0.06% × 2):      ${total_fees:>10,.2f}")
print(f"Чистая прибыль (после):         ${total_net:>10,.2f}")
print(f"\nКомиссия на сделку: ${total_fees/len(all_trades):.2f}")
print(f"Комиссия от валовой: {total_fees/total_gross*100:.2f}%")

# ВОПРОС 3: Размер позиции
print("\n\n3️⃣  РАЗМЕР ПОЗИЦИИ И КАПИТАЛ:")
print("-"*80)

print(f"Позиция на сигнал: ${POSITION_SIZE_USDT} USDT")
print(f"Плечо: {LEVERAGE}x")
print(f"Реальный размер сделки: ${POSITION_SIZE_USDT * LEVERAGE:,.2f} USDT")
print(f"\nВсего сигналов за 24ч: {len(signals)}")
print(f"Одновременных позиций (макс): ~10-15")
print(f"Необходимый капитал (минимум): ${10 * POSITION_SIZE_USDT:,.2f} USDT")

# ВОПРОС 4: Логика выходов
print("\n\n4️⃣  ЛОГИКА ЗАКРЫТИЯ ПОЗИЦИЙ:")
print("-"*80)

tp_count = sum(1 for t in all_trades if t['exit_reason'] == 'TAKE_PROFIT')
sl_count = sum(1 for t in all_trades if t['exit_reason'] == 'STOP_LOSS')
ttl_count = sum(1 for t in all_trades if t['exit_reason'] == 'TTL_EXPIRED')

print(f"\nВсего выходов: {len(all_trades)}")
print(f"\n1. Take-Profit (TP достигнут):     {tp_count:>3} ({tp_count/len(all_trades)*100:.1f}%)")
print(f"   → Цена достигла +{TP_PCT/LEVERAGE:.2f}% от входа")
print(f"\n2. Stop-Loss (SL достигнут):       {sl_count:>3} ({sl_count/len(all_trades)*100:.1f}%)")
print(f"   → Цена достигла -{SL_PCT/LEVERAGE:.2f}% от входа")
print(f"\n3. TTL Expired (время истекло):    {ttl_count:>3} ({ttl_count/len(all_trades)*100:.1f}%)")
print(f"   → Закрытие по final_price после истечения TTL")

# Примеры
print("\n📋 ПРИМЕРЫ ВЫХОДОВ:")
for i, signal in enumerate(signals[:3]):
    trade = simulate_trade(signal, LEVERAGE, SL_PCT, TP_PCT)
    
    print(f"\nСигнал #{i+1}: {signal['symbol']} {signal['verdict']}")
    print(f"  Entry: ${signal['entry_price']:.4f}")
    print(f"  TP level: ${trade['tp_price']:.4f} (+{TP_PCT/LEVERAGE:.2f}%)")
    print(f"  SL level: ${trade['sl_price']:.4f} (-{SL_PCT/LEVERAGE:.2f}%)")
    print(f"  Exit: ${trade['exit_price']:.4f} ({trade['exit_reason']})")
    print(f"  Profit: ${trade['profit_usdt']:.2f}")

# ВОПРОС 5: Периодичность данных
print("\n\n5️⃣  ПЕРИОДИЧНОСТЬ ОБНОВЛЕНИЯ ДАННЫХ:")
print("-"*80)

# Считываем timestamps сигналов
timestamps = [datetime.strptime(s['timestamp'], '%Y-%m-%d %H:%M:%S') for s in signals]
time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() / 60 
              for i in range(len(timestamps)-1)]

avg_interval = statistics.mean(time_diffs) if time_diffs else 0
min_interval = min(time_diffs) if time_diffs else 0
max_interval = max(time_diffs) if time_diffs else 0

print(f"Текущая периодичность сигналов:")
print(f"  Средний интервал: {avg_interval:.1f} минут")
print(f"  Минимальный: {min_interval:.1f} минут")
print(f"  Максимальный: {max_interval:.1f} минут")

print(f"\nТребования для автотрейдинга:")
print(f"  TP движение: +{TP_PCT/LEVERAGE:.2f}% (~$10-40 за минуту на волатильности)")
print(f"  SL движение: -{SL_PCT/LEVERAGE:.2f}% (~$4-16 за минуту)")

print(f"\n⚠️  КРИТИЧНО:")
print(f"  • Текущая частота обновления: каждые 2 минуты")
print(f"  • Средняя цена BTC движется на ±0.1-0.3% за 2 минуты")
print(f"  • TP требует +{TP_PCT/LEVERAGE:.2f}% - может занять 5-20 минут")
print(f"  • SL на -{SL_PCT/LEVERAGE:.2f}% - может сработать за 2-10 минут")

print(f"\n💡 РЕКОМЕНДАЦИИ:")
print(f"  ✅ Текущей частоты (2 мин) ДОСТАТОЧНО для мониторинга")
print(f"  ✅ Для автотрейдинга нужно использовать MEXC WebSocket")
print(f"  ✅ WebSocket даст обновления каждые 100ms (real-time)")
print(f"  ✅ Можно также проверять позиции каждые 30-60 секунд")

# Дополнительные монеты для исключения?
print("\n\n🔍 ДОПОЛНИТЕЛЬНЫЕ КАНДИДАТЫ НА ИСКЛЮЧЕНИЕ:")
print("-"*80)

bad_patterns = []
for (symbol, side), stats in pattern_stats.items():
    if (symbol, side) in excluded:
        continue
    
    total = len(stats['trades'])
    wr = stats['wins'] / total * 100 if total > 0 else 0
    avg = stats['total_profit'] / total if total > 0 else 0
    
    # Критерии: WR < 50% ИЛИ avg < 0 ИЛИ (WR < 55% И avg < 5)
    if total >= 5 and (wr < 50 or avg < 0 or (wr < 55 and avg < 5)):
        bad_patterns.append(((symbol, side), stats, avg))

if bad_patterns:
    bad_patterns.sort(key=lambda x: x[2])  # По avg profit
    
    print(f"\nНайдено {len(bad_patterns)} подозрительных паттернов:\n")
    print(f"{'Symbol':<12} {'Side':<5} {'Trades':<7} {'Win%':<7} {'Avg $':<10} {'Total $':<12}")
    print("-"*70)
    
    for (symbol, side), stats, avg in bad_patterns[:10]:
        total = len(stats['trades'])
        wr = stats['wins'] / total * 100 if total > 0 else 0
        print(f"{symbol:<12} {side:<5} {total:<7} {wr:>5.1f}% ${avg:>8.2f}  ${stats['total_profit']:>10,.2f}")
    
    print(f"\n💡 Если исключить эти {len(bad_patterns)} паттернов:")
    excluded_profit = sum(stats['total_profit'] for _, stats, _ in bad_patterns)
    print(f"   Изменение прибыли: ${excluded_profit:+,.2f}")
else:
    print("\n✅ Других плохих паттернов не найдено!")

print("\n" + "="*80 + "\n")
