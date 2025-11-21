#!/usr/bin/env python3
"""
PAPER TRADING - Последние 3 часа
Симуляция реальной торговли с оптимальными параметрами
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import json

# Оптимальные параметры из анализа
with open('backtesting_analysis/FINAL_OPTIMAL_CONFIG.json', 'r') as f:
    CONFIG = json.load(f)

LEVERAGE = CONFIG['parameters']['leverage']
SL_PCT = CONFIG['parameters']['sl']
TP_PCT = CONFIG['parameters']['tp']
TOP_COINS = set(CONFIG['top_coins'])
EXCLUDED_COINS = set(CONFIG['excluded_coins'])

POSITION_SIZE = 100
MEXC_FEE = 0.0006
STARTING_CAPITAL = 1000

def simulate_trade(signal):
    """Симуляция одной сделки"""
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    
    sl_price_move = SL_PCT / LEVERAGE
    tp_price_move = TP_PCT / LEVERAGE
    
    if verdict == "SELL":
        sl_price = entry_price * (1 + sl_price_move / 100)
        tp_price = entry_price * (1 - tp_price_move / 100)
        
        if highest >= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
        elif lowest <= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
        else:
            exit_price = final_price
            exit_reason = "TTL"
        
        price_change = ((entry_price - exit_price) / entry_price) * 100
    else:
        sl_price = entry_price * (1 - sl_price_move / 100)
        tp_price = entry_price * (1 + tp_price_move / 100)
        
        if lowest <= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
        elif highest >= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
        else:
            exit_price = final_price
            exit_reason = "TTL"
        
        price_change = ((exit_price - entry_price) / entry_price) * 100
    
    gross_profit = price_change * LEVERAGE
    net_profit = gross_profit - (MEXC_FEE * 2 * 100)
    profit_usdt = (net_profit / 100) * POSITION_SIZE
    
    return {
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'profit_usdt': profit_usdt,
        'profit_pct': net_profit,
        'win': profit_usdt > 0
    }

# Load signals from last 3 hours
now = datetime.now()
cutoff = now - timedelta(hours=3)

signals = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
            
            if timestamp < cutoff or row['result'] == 'CANCELLED':
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
                'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                'final_price': float(row['final_price']) if row['final_price'] else entry_price,
            }
            
            signals.append(signal)
        except (ValueError, KeyError):
            continue

print("="*80)
print("📊 PAPER TRADING - ПОСЛЕДНИЕ 3 ЧАСА")
print("="*80)
print(f"\n⏰ Период: {cutoff.strftime('%Y-%m-%d %H:%M')} - {now.strftime('%Y-%m-%d %H:%M')}")
print(f"📈 Всего сигналов: {len(signals)}")

if len(signals) == 0:
    print("\n⚠️  Нет сигналов за последние 3 часа!")
    exit(0)

print(f"\n⚙️  ПАРАМЕТРЫ ТОРГОВЛИ:")
print(f"  Leverage:     {LEVERAGE}x")
print(f"  Stop-Loss:    {SL_PCT}% депозита (-{SL_PCT/LEVERAGE:.2f}% цены)")
print(f"  Take-Profit:  {TP_PCT}% депозита (+{TP_PCT/LEVERAGE:.2f}% цены)")
print(f"  Position:     ${POSITION_SIZE} USDT")
print(f"  Capital:      ${STARTING_CAPITAL} USDT")

print(f"\n🎯 ФИЛЬТРЫ:")
print(f"  Торговать:    {', '.join(TOP_COINS)}")
print(f"  Исключить:    {', '.join(EXCLUDED_COINS)}")

# Simulate trading
trades = []
capital = STARTING_CAPITAL
peak_capital = STARTING_CAPITAL
max_drawdown = 0

print(f"\n{'='*80}")
print("💰 ТОРГОВЛЯ В РЕАЛЬНОМ ВРЕМЕНИ")
print(f"{'='*80}\n")

for i, signal in enumerate(signals, 1):
    # Фильтрация
    if signal['symbol'] in EXCLUDED_COINS:
        print(f"⏭️  #{i} {signal['timestamp']} {signal['symbol']} {signal['verdict']} - ПРОПУЩЕН (excluded)")
        continue
    
    if signal['symbol'] not in TOP_COINS:
        print(f"⏭️  #{i} {signal['timestamp']} {signal['symbol']} {signal['verdict']} - ПРОПУЩЕН (not in top)")
        continue
    
    # Проверка капитала
    if capital < POSITION_SIZE:
        print(f"⚠️  #{i} {signal['timestamp']} {signal['symbol']} {signal['verdict']} - НЕТ КАПИТАЛА!")
        break
    
    # Открытие позиции
    trade = simulate_trade(signal)
    trade['signal'] = signal
    trades.append(trade)
    
    # Обновление капитала
    old_capital = capital
    capital += trade['profit_usdt']
    
    # Обновление drawdown
    if capital > peak_capital:
        peak_capital = capital
    drawdown = peak_capital - capital
    if drawdown > max_drawdown:
        max_drawdown = drawdown
    
    # Вывод
    emoji = "✅" if trade['win'] else "❌"
    print(f"{emoji} #{i} {signal['timestamp']} {signal['symbol']:10s} {signal['verdict']:4s} "
          f"conf:{signal['confidence']:.0%} -> {trade['exit_reason']:3s} "
          f"{trade['profit_usdt']:>+7.2f}$ ({trade['profit_pct']:>+5.1f}%) "
          f"Balance: ${capital:,.2f}")

# Summary
print(f"\n{'='*80}")
print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
print(f"{'='*80}")

total_trades = len(trades)
wins = sum(1 for t in trades if t['win'])
losses = total_trades - wins
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

total_profit = sum(t['profit_usdt'] for t in trades)
winning_profits = [t['profit_usdt'] for t in trades if t['win']]
losing_profits = [t['profit_usdt'] for t in trades if not t['win']]

avg_win = sum(winning_profits) / len(winning_profits) if winning_profits else 0
avg_loss = sum(losing_profits) / len(losing_profits) if losing_profits else 0

total_wins = sum(winning_profits) if winning_profits else 0
total_losses = abs(sum(losing_profits)) if losing_profits else 0
profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

sl_count = sum(1 for t in trades if t['exit_reason'] == 'SL')
tp_count = sum(1 for t in trades if t['exit_reason'] == 'TP')
ttl_count = sum(1 for t in trades if t['exit_reason'] == 'TTL')

roi = ((capital - STARTING_CAPITAL) / STARTING_CAPITAL) * 100

print(f"\n💼 КАПИТАЛ:")
print(f"  Начальный:        ${STARTING_CAPITAL:,.2f}")
print(f"  Финальный:        ${capital:,.2f}")
print(f"  Чистая прибыль:   ${total_profit:+,.2f}")
print(f"  ROI:              {roi:+.1f}%")
print(f"  Max Drawdown:     ${max_drawdown:,.2f} ({max_drawdown/STARTING_CAPITAL*100:.1f}%)")

print(f"\n📈 СТАТИСТИКА:")
print(f"  Всего сделок:     {total_trades}")
print(f"  Выигрышей:        {wins} ({win_rate:.1f}%)")
print(f"  Проигрышей:       {losses} ({100-win_rate:.1f}%)")
print(f"  Profit Factor:    {profit_factor:.2f}")

print(f"\n💰 СРЕДНИЕ:")
print(f"  Avg Win:          ${avg_win:,.2f}")
print(f"  Avg Loss:         ${avg_loss:,.2f}")
print(f"  Avg Trade:        ${total_profit/total_trades:,.2f}")

print(f"\n🎯 ВЫХОДЫ:")
print(f"  Take-Profit:      {tp_count} ({tp_count/total_trades*100:.1f}%)")
print(f"  Stop-Loss:        {sl_count} ({sl_count/total_trades*100:.1f}%)")
print(f"  TTL Expired:      {ttl_count} ({ttl_count/total_trades*100:.1f}%)")

# По монетам
print(f"\n📊 ПО МОНЕТАМ:")
coin_stats = defaultdict(lambda: {'profit': 0, 'trades': 0, 'wins': 0})
for trade in trades:
    symbol = trade['signal']['symbol']
    coin_stats[symbol]['profit'] += trade['profit_usdt']
    coin_stats[symbol]['trades'] += 1
    if trade['win']:
        coin_stats[symbol]['wins'] += 1

sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
print(f"\n{'Symbol':<12} {'Trades':<8} {'Wins':<6} {'Win%':<8} {'Profit':<12}")
print("-"*55)
for symbol, stats in sorted_coins:
    wr = stats['wins'] / stats['trades'] * 100
    print(f"{symbol:<12} {stats['trades']:<8} {stats['wins']:<6} {wr:>5.1f}%  ${stats['profit']:>8.2f}")

# Экстраполяция
hours_traded = (now - cutoff).total_seconds() / 3600
roi_per_hour = roi / hours_traded if hours_traded > 0 else 0
roi_24h = roi_per_hour * 24

print(f"\n{'='*80}")
print("🚀 ЭКСТРАПОЛЯЦИЯ НА 24 ЧАСА")
print(f"{'='*80}")
print(f"\n  Торговали:        {hours_traded:.1f} часов")
print(f"  ROI/час:          {roi_per_hour:+.1f}%")
print(f"  Ожидаемый ROI/24h: {roi_24h:+.1f}%")
print(f"  Ожидаемая прибыль: ${(STARTING_CAPITAL * roi_24h / 100):+,.2f}")

if roi > 0:
    print(f"\n✅ МОДЕЛЬ РАБОТАЕТ! Прибыль за {hours_traded:.1f}ч: ${total_profit:+,.2f} ({roi:+.1f}%)")
else:
    print(f"\n⚠️  УБЫТОК за {hours_traded:.1f}ч: ${total_profit:+,.2f} ({roi:+.1f}%)")

print(f"\n{'='*80}\n")
