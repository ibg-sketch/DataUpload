#!/usr/bin/env python3
"""
ПЕРЕСЧЕТ МОДЕЛИ С КОМИССИЯМИ BYBIT
Сравнение: MEXC vs Bybit
"""

import csv
from datetime import datetime
import json

# Загружаем оптимальную конфигурацию
with open('backtesting_analysis/FINAL_OPTIMAL_CONFIG.json', 'r') as f:
    CONFIG = json.load(f)

LEVERAGE = CONFIG['parameters']['leverage']
SL_PCT = CONFIG['parameters']['sl']
TP_PCT = CONFIG['parameters']['tp']
TOP_COINS = set(CONFIG['top_coins'])
EXCLUDED_COINS = set(CONFIG['excluded_coins'])

POSITION_SIZE = 100

# КОМИССИИ
MEXC_FEE = 0.0006  # 0.06% (старая модель)
BYBIT_TAKER_FEE = 0.00055  # 0.055% (актуальная!)
BYBIT_MAKER_FEE = 0.0002   # 0.02% (если лимит ордера)

def calculate_trade_pnl(signal, fee_rate):
    """Расчет PnL с учетом комиссии"""
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
    
    # Комиссия на вход и выход
    fee_cost = (fee_rate * 2 * 100)
    net_profit = gross_profit - fee_cost
    profit_usdt = (net_profit / 100) * POSITION_SIZE
    
    return {
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'gross_profit_pct': gross_profit,
        'fee_cost_pct': fee_cost,
        'net_profit_pct': net_profit,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

# Загрузка данных
print("="*80)
print("📊 ПЕРЕСЧЕТ МОДЕЛИ С КОМИССИЯМИ BYBIT")
print("="*80)

cutoff = datetime.strptime('2025-11-04 16:00:00', '%Y-%m-%d %H:%M:%S')

signals = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
            
            if timestamp < cutoff or row['result'] == 'CANCELLED':
                continue
            
            symbol = row['symbol']
            if symbol in EXCLUDED_COINS or symbol not in TOP_COINS:
                continue
            
            confidence = float(row['confidence'])
            entry_price = float(row['entry_price'])
            
            if entry_price == 0 or confidence < 0.5:
                continue
            
            signal = {
                'symbol': symbol,
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

print(f"\n📈 Данные: NEW версия бота (после 2025-11-04 16:00 UTC)")
print(f"📊 Всего сигналов: {len(signals)}")
print(f"🎯 Торговать: {', '.join(sorted(TOP_COINS))}")

# СРАВНЕНИЕ ТРЕХ ВАРИАНТОВ
print(f"\n{'='*80}")
print("💰 СРАВНЕНИЕ КОМИССИЙ")
print(f"{'='*80}\n")

scenarios = {
    'MEXC (0.06%)': MEXC_FEE,
    'Bybit Taker (0.055%)': BYBIT_TAKER_FEE,
    'Bybit Maker (0.02%)': BYBIT_MAKER_FEE,
}

results = {}

for name, fee in scenarios.items():
    trades = []
    total_profit = 0
    wins = 0
    total_fees_paid = 0
    
    for signal in signals:
        trade = calculate_trade_pnl(signal, fee)
        trades.append(trade)
        total_profit += trade['profit_usdt']
        total_fees_paid += trade['fee_cost_pct'] / 100 * POSITION_SIZE
        if trade['win']:
            wins += 1
    
    win_rate = (wins / len(trades) * 100) if trades else 0
    roi = (total_profit / (len(trades) * POSITION_SIZE)) * 100 if trades else 0
    
    winning_profits = [t['profit_usdt'] for t in trades if t['win']]
    losing_profits = [t['profit_usdt'] for t in trades if not t['win']]
    
    total_wins = sum(winning_profits) if winning_profits else 0
    total_losses = abs(sum(losing_profits)) if losing_profits else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    tp_count = sum(1 for t in trades if t['exit_reason'] == 'TP')
    sl_count = sum(1 for t in trades if t['exit_reason'] == 'SL')
    
    results[name] = {
        'total_profit': total_profit,
        'roi': roi,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_fees': total_fees_paid,
        'trades': len(trades),
        'tp_rate': tp_count / len(trades) * 100 if trades else 0,
        'sl_rate': sl_count / len(trades) * 100 if trades else 0,
    }

# Вывод сравнения
print(f"{'Биржа':<25} {'Прибыль':<12} {'ROI':<10} {'Win%':<8} {'PF':<6} {'Комиссии':<10}")
print("-"*80)

for name, stats in results.items():
    print(f"{name:<25} ${stats['total_profit']:>8.2f}   {stats['roi']:>6.1f}%   "
          f"{stats['win_rate']:>5.1f}%  {stats['profit_factor']:>4.2f}  ${stats['total_fees']:>7.2f}")

# ДЕТАЛЬНОЕ СРАВНЕНИЕ MEXC vs Bybit Taker
print(f"\n{'='*80}")
print("🔍 ДЕТАЛЬНОЕ СРАВНЕНИЕ: MEXC vs BYBIT")
print(f"{'='*80}\n")

mexc_stats = results['MEXC (0.06%)']
bybit_stats = results['Bybit Taker (0.055%)']

profit_diff = bybit_stats['total_profit'] - mexc_stats['total_profit']
profit_diff_pct = (profit_diff / mexc_stats['total_profit'] * 100) if mexc_stats['total_profit'] > 0 else 0
roi_diff = bybit_stats['roi'] - mexc_stats['roi']
fee_savings = mexc_stats['total_fees'] - bybit_stats['total_fees']

print(f"📊 ПРИБЫЛЬ:")
print(f"  MEXC:          ${mexc_stats['total_profit']:,.2f}")
print(f"  Bybit:         ${bybit_stats['total_profit']:,.2f}")
print(f"  Разница:       ${profit_diff:+,.2f} ({profit_diff_pct:+.1f}%)")

print(f"\n📈 ROI:")
print(f"  MEXC:          {mexc_stats['roi']:.1f}%")
print(f"  Bybit:         {bybit_stats['roi']:.1f}%")
print(f"  Разница:       {roi_diff:+.1f}%")

print(f"\n💸 КОМИССИИ:")
print(f"  MEXC:          ${mexc_stats['total_fees']:,.2f}")
print(f"  Bybit:         ${bybit_stats['total_fees']:,.2f}")
print(f"  Экономия:      ${fee_savings:+,.2f}")

print(f"\n🎯 СТАТИСТИКА:")
print(f"  Сделок:        {mexc_stats['trades']}")
print(f"  Win Rate:      {mexc_stats['win_rate']:.1f}% (одинаково)")
print(f"  Profit Factor: {mexc_stats['profit_factor']:.2f} (одинаково)")

# ВЛИЯНИЕ КОМИССИЙ НА РАЗНЫЕ СЦЕНАРИИ
print(f"\n{'='*80}")
print("📉 ВЛИЯНИЕ КОМИССИЙ НА УБЫТОЧНЫЕ/ПРИБЫЛЬНЫЕ СДЕЛКИ")
print(f"{'='*80}\n")

# Пример расчета на одной сделке
example_trade_sizes = [
    {'name': 'SL Hit (-0.8%)', 'price_move': -0.8},
    {'name': 'Small Win (+0.5%)', 'price_move': 0.5},
    {'name': 'Medium Win (+1.0%)', 'price_move': 1.0},
    {'name': 'TP Hit (+1.5%)', 'price_move': 1.5},
]

print(f"{'Сценарий':<20} {'Движение':<12} {'MEXC Profit':<14} {'Bybit Profit':<14} {'Разница'}")
print("-"*80)

for scenario in example_trade_sizes:
    name = scenario['name']
    move = scenario['price_move']
    
    # Gross profit
    gross = move * LEVERAGE
    
    # MEXC
    mexc_net = gross - (MEXC_FEE * 2 * 100)
    mexc_usdt = (mexc_net / 100) * POSITION_SIZE
    
    # Bybit
    bybit_net = gross - (BYBIT_TAKER_FEE * 2 * 100)
    bybit_usdt = (bybit_net / 100) * POSITION_SIZE
    
    diff = bybit_usdt - mexc_usdt
    
    print(f"{name:<20} {move:>+6.2f}%      ${mexc_usdt:>+8.2f}      ${bybit_usdt:>+8.2f}      ${diff:>+6.2f}")

# ВЫВОД
print(f"\n{'='*80}")
print("✅ ВЫВОДЫ")
print(f"{'='*80}\n")

if profit_diff > 0:
    print(f"🎉 BYBIT ЛУЧШЕ MEXC!")
    print(f"   Дополнительная прибыль: ${profit_diff:,.2f} (+{profit_diff_pct:.1f}%)")
    print(f"   Экономия на комиссиях: ${fee_savings:,.2f}")
elif profit_diff < 0:
    print(f"⚠️  BYBIT ХУЖЕ MEXC")
    print(f"   Потеря прибыли: ${profit_diff:,.2f} ({profit_diff_pct:.1f}%)")
    print(f"   Переплата комиссий: ${-fee_savings:,.2f}")
else:
    print(f"🤝 ОДИНАКОВЫЕ РЕЗУЛЬТАТЫ")

print(f"\n💡 РЕКОМЕНДАЦИЯ:")
print(f"   Использовать Bybit с MARKET ORDERS (taker)")
print(f"   Комиссия: 0.055% (очень близко к MEXC 0.06%)")
print(f"   Плюсы Bybit:")
print(f"     ✅ Разрешает торговлю фьючерсами через API")
print(f"     ✅ Чуть ниже комиссии ({BYBIT_TAKER_FEE*100:.3f}% vs {MEXC_FEE*100:.2f}%)")
print(f"     ✅ Экономия: ${fee_savings:,.2f} на {mexc_stats['trades']} сделках")
print(f"     ✅ Надежный API и WebSocket")

print(f"\n📝 ВАЖНО:")
print(f"   - Используем MARKET ORDERS (taker 0.055%)")
print(f"   - Limit orders (maker 0.02%) требуют ожидания исполнения")
print(f"   - Для нашей стратегии важна скорость = market orders")

# Сохранение конфигурации для Bybit
bybit_config = CONFIG.copy()
bybit_config['exchange'] = 'Bybit'
bybit_config['fee_rate'] = BYBIT_TAKER_FEE
bybit_config['fee_type'] = 'taker (market orders)'
bybit_config['performance'] = {
    'total_profit': bybit_stats['total_profit'],
    'roi': bybit_stats['roi'],
    'win_rate': bybit_stats['win_rate'],
    'profit_factor': bybit_stats['profit_factor'],
    'total_fees_paid': bybit_stats['total_fees'],
    'fee_savings_vs_mexc': fee_savings
}

with open('backtesting_analysis/BYBIT_OPTIMAL_CONFIG.json', 'w') as f:
    json.dump(bybit_config, f, indent=2)

print(f"\n💾 Конфигурация для Bybit сохранена: backtesting_analysis/BYBIT_OPTIMAL_CONFIG.json")
print(f"\n{'='*80}\n")
