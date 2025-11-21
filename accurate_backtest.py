#!/usr/bin/env python3
"""
Точный симулятор на основе РЕАЛЬНОЙ статистики
- BUY Win Rate: 67.1%
- SELL Win Rate: 78.0%
- Target Zone Statistics: 68.3% start, 52.4% mid, 38.9% end
"""

import pandas as pd
import numpy as np
import json

np.random.seed(42)

REAL_WIN_RATES = {
    'BUY': 0.671,
    'SELL': 0.780
}

TARGET_DISTRIBUTION = {
    'BUY': {
        'target_min_pct': 0.20,
        'target_max_pct': 0.40
    },
    'SELL': {
        'target_min_pct': 0.15,
        'target_max_pct': 0.35
    }
}

BINGX_FEES = {
    'entry_taker': 0.0005,
    'tp_maker': 0.0002,
    'sl_taker': 0.0005,
    'ttl_taker': 0.0005
}

def simulate_single_trade(signal_type, leverage, stop_loss_pct):
    """
    Симулирует один трейд используя РЕАЛЬНУЮ статистику
    
    Returns:
        (outcome, pnl_pct)
    """
    win_rate = REAL_WIN_RATES[signal_type]
    
    if np.random.random() < win_rate:
        avg_target_pct = np.mean([
            TARGET_DISTRIBUTION[signal_type]['target_min_pct'],
            TARGET_DISTRIBUTION[signal_type]['target_max_pct']
        ])
        
        price_move_pct = avg_target_pct
        
        gross_pnl_pct = price_move_pct * leverage
        
        fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['tp_maker']) * leverage
        
        net_pnl_pct = gross_pnl_pct - fees_pct
        
        return 'WIN', net_pnl_pct
    
    else:
        sl_hit_rate = 0.15
        
        if np.random.random() < sl_hit_rate:
            gross_loss_pct = (stop_loss_pct / 100) * leverage
            fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['sl_taker']) * leverage
            net_pnl_pct = -(gross_loss_pct + fees_pct)
            return 'SL', net_pnl_pct
        else:
            avg_ttl_loss_pct = 0.10
            gross_loss_pct = avg_ttl_loss_pct * leverage
            fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['ttl_taker']) * leverage
            net_pnl_pct = -(gross_loss_pct + fees_pct)
            return 'TTL', net_pnl_pct

def run_strategy(signals_df, config, initial_balance=1000.0, num_runs=50):
    """Прогоняет стратегию несколько раз для усреднения"""
    all_results = []
    
    for run in range(num_runs):
        balance = initial_balance
        trades = []
        
        for _, signal in signals_df.iterrows():
            if config.get('trade_sell_only') and signal['verdict'] == 'BUY':
                continue
            
            if balance <= 0:
                break
            
            position_size = balance * (config['position_size_pct'] / 100)
            
            if position_size < 10:
                break
            
            outcome, pnl_pct = simulate_single_trade(
                signal['verdict'],
                config['leverage'],
                config['stop_loss_pct']
            )
            
            pnl_dollars = position_size * (pnl_pct / 100)
            balance += pnl_dollars
            
            trades.append({
                'outcome': outcome,
                'pnl_pct': pnl_pct,
                'pnl_dollars': pnl_dollars,
                'signal_type': signal['verdict']
            })
        
        win_trades = [t for t in trades if t['pnl_dollars'] > 0]
        lose_trades = [t for t in trades if t['pnl_dollars'] <= 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        
        all_results.append({
            'final_balance': balance,
            'pnl': balance - initial_balance,
            'pnl_pct': ((balance - initial_balance) / initial_balance) * 100,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'trades': trades
        })
    
    avg_balance = np.mean([r['final_balance'] for r in all_results])
    avg_pnl = np.mean([r['pnl'] for r in all_results])
    avg_pnl_pct = np.mean([r['pnl_pct'] for r in all_results])
    avg_trades = np.mean([r['num_trades'] for r in all_results])
    avg_win_rate = np.mean([r['win_rate'] for r in all_results])
    
    min_balance = np.min([r['final_balance'] for r in all_results])
    max_balance = np.max([r['final_balance'] for r in all_results])
    std_balance = np.std([r['final_balance'] for r in all_results])
    
    return {
        'avg_final_balance': avg_balance,
        'avg_pnl': avg_pnl,
        'avg_pnl_pct': avg_pnl_pct,
        'avg_num_trades': avg_trades,
        'avg_win_rate': avg_win_rate,
        'min_final_balance': min_balance,
        'max_final_balance': max_balance,
        'std_final_balance': std_balance,
        'config': config
    }

print("=" * 90)
print("ТОЧНЫЙ СИМУЛЯТОР ТОРГОВЫХ КОНФИГУРАЦИЙ")
print("Реальная статистика: BUY WR=67.1%, SELL WR=78.0%")
print("=" * 90)

signals_df = pd.read_csv('/tmp/signals_nov17_18_with_header.csv')
num_buy = len(signals_df[signals_df['verdict'] == 'BUY'])
num_sell = len(signals_df[signals_df['verdict'] == 'SELL'])

print(f"\n📊 Сигналов за 17-18 ноября: {len(signals_df)}")
print(f"   BUY: {num_buy} ({num_buy/len(signals_df)*100:.1f}%)")
print(f"   SELL: {num_sell} ({num_sell/len(signals_df)*100:.1f}%)")

strategies = [
    {'name': '✅ Текущая (ALL-IN 20x hybrid)', 'leverage': 20, 'position_size_pct': 100, 'stop_loss_pct': 10, 'trade_sell_only': False},
    {'name': '1. SELL-only 20x 100%', 'leverage': 20, 'position_size_pct': 100, 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '2. SELL-only 10x 50%', 'leverage': 10, 'position_size_pct': 50, 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '3. SELL-only 10x 20%', 'leverage': 10, 'position_size_pct': 20, 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '4. SELL-only 5x 50%', 'leverage': 5, 'position_size_pct': 50, 'stop_loss_pct': 25, 'trade_sell_only': True},
    {'name': '5. SELL-only 5x 100%', 'leverage': 5, 'position_size_pct': 100, 'stop_loss_pct': 25, 'trade_sell_only': True},
    {'name': '6. ALL 10x 50%', 'leverage': 10, 'position_size_pct': 50, 'stop_loss_pct': 20, 'trade_sell_only': False},
    {'name': '7. ALL 10x 20%', 'leverage': 10, 'position_size_pct': 20, 'stop_loss_pct': 20, 'trade_sell_only': False},
    {'name': '8. ALL 5x 50%', 'leverage': 5, 'position_size_pct': 50, 'stop_loss_pct': 25, 'trade_sell_only': False},
    {'name': '9. SELL-only 50x 20%', 'leverage': 50, 'position_size_pct': 20, 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '10. SELL-only 20x 50%', 'leverage': 20, 'position_size_pct': 50, 'stop_loss_pct': 15, 'trade_sell_only': True},
    {'name': '11. SELL-only 15x 33%', 'leverage': 15, 'position_size_pct': 33, 'stop_loss_pct': 20, 'trade_sell_only': True},
]

results = []
print("\n🔄 Тестирование конфигураций...")
for strat in strategies:
    print(f"   → {strat['name']}")
    result = run_strategy(signals_df, strat)
    results.append(result)

results_sorted = sorted(results, key=lambda x: x['avg_final_balance'], reverse=True)

print("\n" + "=" * 90)
print("🏆 ТОП-12 КОНФИГУРАЦИЙ (отсортировано по итоговому балансу)")
print("=" * 90)

for i, r in enumerate(results_sorted, 1):
    c = r['config']
    risk_level = "🔴 ВЫСОКИЙ" if c['leverage'] >= 20 else "🟡 СРЕДНИЙ" if c['leverage'] >= 10 else "🟢 НИЗКИЙ"
    
    print(f"\n#{i} | {c['name']}")
    print(f"     💰 Баланс: $1000 → ${r['avg_final_balance']:.2f} ({r['avg_pnl_pct']:+.1f}%)")
    print(f"     📊 Винрейт: {r['avg_win_rate']:.1f}% | Трейдов: {r['avg_num_trades']:.0f}")
    print(f"     ⚙️  Плечо: {c['leverage']}x | Размер: {c['position_size_pct']}% | SL: {c['stop_loss_pct']}%")
    print(f"     🎯 Риск: {risk_level} | SELL-only: {c['trade_sell_only']}")
    print(f"     📈 Диапазон: ${r['min_final_balance']:.2f} - ${r['max_final_balance']:.2f} (±${r['std_final_balance']:.2f})")

best = results_sorted[0]
print("\n" + "=" * 90)
print("⭐ РЕКОМЕНДАЦИЯ: ОПТИМАЛЬНАЯ КОНФИГУРАЦИЯ")
print("=" * 90)
print(f"\n{best['config']['name']}")
print(f"\n📍 Параметры:")
print(f"   Плечо: {best['config']['leverage']}x")
print(f"   Размер позиции: {best['config']['position_size_pct']}% от баланса")
print(f"   Stop-Loss: {best['config']['stop_loss_pct']}%")
print(f"   Торговать только SELL: {best['config']['trade_sell_only']}")
print(f"\n💵 Ожидаемый результат за 2 дня:")
print(f"   Начальный баланс: $1,000.00")
print(f"   Средний финал: ${best['avg_final_balance']:.2f}")
print(f"   Средний PnL: ${best['avg_pnl']:.2f} ({best['avg_pnl_pct']:+.1f}%)")
print(f"   Худший случай: ${best['min_final_balance']:.2f}")
print(f"   Лучший случай: ${best['max_final_balance']:.2f}")
print(f"\n📊 Торговая статистика:")
print(f"   Винрейт: {best['avg_win_rate']:.1f}%")
print(f"   Количество трейдов: {best['avg_num_trades']:.0f}")

print("\n" + "=" * 90)
print("💡 АНАЛИЗ И ВЫВОДЫ")
print("=" * 90)

current = [r for r in results_sorted if 'Текущая' in r['config']['name']][0]
current_pos = results_sorted.index(current) + 1

print(f"\n📌 Ваша текущая конфигурация:")
print(f"   Позиция: #{current_pos} из {len(results_sorted)}")
print(f"   Ожидаемый баланс: ${current['avg_final_balance']:.2f}")
print(f"   PnL: {current['avg_pnl_pct']:+.1f}%")

if current_pos == 1:
    print(f"\n✅ Ваша текущая конфигурация ОПТИМАЛЬНА!")
else:
    improvement_pct = ((best['avg_final_balance'] - current['avg_final_balance']) / current['avg_final_balance']) * 100
    improvement_dollars = best['avg_final_balance'] - current['avg_final_balance']
    print(f"\n📈 Переход на лучшую конфигурацию даст улучшение:")
    print(f"   +${improvement_dollars:.2f} (+{improvement_pct:.1f}%)")

sell_only = [r for r in results_sorted if r['config']['trade_sell_only']]
all_signals = [r for r in results_sorted if not r['config']['trade_sell_only']]

if sell_only and all_signals:
    best_sell = sell_only[0]
    best_all = all_signals[0]
    print(f"\n🔍 SELL-only vs ALL signals:")
    print(f"   Лучшая SELL-only: ${best_sell['avg_final_balance']:.2f}")
    print(f"   Лучшая ALL: ${best_all['avg_final_balance']:.2f}")
    if best_sell['avg_final_balance'] > best_all['avg_final_balance']:
        print(f"   ✅ SELL-only превосходит на {((best_sell['avg_final_balance']/best_all['avg_final_balance'])-1)*100:.1f}%")
    else:
        print(f"   ❌ ALL signals лучше на {((best_all['avg_final_balance']/best_sell['avg_final_balance'])-1)*100:.1f}%")

print("\n" + "=" * 90)

with open('/tmp/accurate_backtest_results.json', 'w') as f:
    json.dump([{k: v for k, v in r.items() if k != 'config'} for r in results_sorted], f, indent=2, default=str)

print("✅ Результаты сохранены в /tmp/accurate_backtest_results.json")
print("=" * 90)
