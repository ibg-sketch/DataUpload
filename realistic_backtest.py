#!/usr/bin/env python3
"""
РЕАЛИСТИЧНЫЙ СИМУЛЯТОР торговли с учетом временных перекрытий
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

np.random.seed(42)

# Реальная статистика из ваших данных
REAL_WIN_RATES = {
    'BUY': 0.671,
    'SELL': 0.780
}

# Средние проценты таргетов из signals_log
TARGET_STATS = {
    'BUY': {
        'avg_target_pct': 0.25  # среднее между min и max
    },
    'SELL': {
        'avg_target_pct': 0.22  # среднее между min и max
    }
}

BINGX_FEES = {
    'entry_taker': 0.0005,
    'tp_maker': 0.0002,
    'sl_taker': 0.0005,
    'ttl_taker': 0.0005
}

def simulate_trade_outcome(signal_type, leverage, stop_loss_pct):
    """
    Симулирует исход одного трейда
    Returns: (outcome, pnl_pct, duration_minutes)
    """
    win_rate = REAL_WIN_RATES[signal_type]
    
    # Определяем исход
    if np.random.random() < win_rate:
        # WIN (TP)
        avg_target_pct = TARGET_STATS[signal_type]['avg_target_pct']
        
        # Добавляем небольшую вариацию ±20%
        target_pct = avg_target_pct * np.random.uniform(0.8, 1.2)
        
        gross_pnl_pct = target_pct * leverage
        fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['tp_maker']) * leverage
        net_pnl_pct = gross_pnl_pct - fees_pct
        
        # Среднее время до TP: 10-20 минут
        duration = np.random.randint(10, 21)
        
        return 'TP', net_pnl_pct, duration
    
    else:
        # LOSS
        sl_hit_rate = 0.15  # 15% из проигрышей бьют SL
        
        if np.random.random() < sl_hit_rate:
            # SL
            gross_loss_pct = (stop_loss_pct / 100) * leverage
            fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['sl_taker']) * leverage
            net_pnl_pct = -(gross_loss_pct + fees_pct)
            
            # SL бьет быстро: 3-10 минут
            duration = np.random.randint(3, 11)
            
            return 'SL', net_pnl_pct, duration
        else:
            # TTL
            avg_ttl_loss_pct = 0.10
            ttl_loss_pct = avg_ttl_loss_pct * np.random.uniform(0.5, 1.5)
            
            gross_loss_pct = ttl_loss_pct * leverage
            fees_pct = (BINGX_FEES['entry_taker'] + BINGX_FEES['ttl_taker']) * leverage
            net_pnl_pct = -(gross_loss_pct + fees_pct)
            
            # TTL - полная длительность сигнала
            # Используем реальный TTL из сигнала (будет передан отдельно)
            duration = None  # Будет взят из signal['ttl_minutes']
            
            return 'TTL', net_pnl_pct, duration

def run_realistic_simulation(signals_df, config, initial_balance=1000.0, num_runs=100):
    """
    Прогоняет симуляцию с учетом временных перекрытий
    """
    leverage = config['leverage']
    position_size_pct = config['position_size_pct']
    max_positions = config['max_positions']
    stop_loss_pct = config['stop_loss_pct']
    trade_sell_only = config.get('trade_sell_only', False)
    
    all_runs = []
    
    for run in range(num_runs):
        balance = initial_balance
        trades = []
        skipped = 0
        
        # Сортируем по времени
        signals_sorted = signals_df.sort_values('timestamp').reset_index(drop=True)
        
        current_position = None  # (end_time, signal_info)
        
        for idx, signal in signals_sorted.iterrows():
            signal_time = pd.to_datetime(signal['timestamp'])
            signal_type = signal['verdict']
            ttl_minutes = signal['ttl_minutes']
            
            # Фильтр: SELL-only
            if trade_sell_only and signal_type == 'BUY':
                continue
            
            # Проверяем: есть ли открытая позиция?
            if current_position is not None:
                position_end_time = current_position[0]
                
                if signal_time < position_end_time:
                    # Позиция еще открыта - ПРОПУСКАЕМ
                    skipped += 1
                    continue
                else:
                    # Позиция закрылась - можем открыть новую
                    current_position = None
            
            # Проверяем баланс
            if balance <= 0:
                break
            
            position_size = balance * (position_size_pct / 100)
            
            if position_size < 10:
                break
            
            # Симулируем трейд
            outcome, pnl_pct, duration = simulate_trade_outcome(
                signal_type, leverage, stop_loss_pct
            )
            
            # Если TTL, используем реальный TTL из сигнала
            if outcome == 'TTL' and duration is None:
                duration = ttl_minutes
            
            # Рассчитываем PnL
            pnl_dollars = position_size * (pnl_pct / 100)
            balance += pnl_dollars
            
            # Время закрытия позиции
            position_end_time = signal_time + timedelta(minutes=duration)
            
            # Сохраняем трейд
            trades.append({
                'timestamp': signal_time,
                'signal_type': signal_type,
                'outcome': outcome,
                'pnl_pct': pnl_pct,
                'pnl_dollars': pnl_dollars,
                'duration': duration,
                'balance_after': balance
            })
            
            # Устанавливаем текущую позицию
            if max_positions == 1:
                current_position = (position_end_time, signal)
        
        # Статистика прогона
        win_trades = [t for t in trades if t['pnl_dollars'] > 0]
        lose_trades = [t for t in trades if t['pnl_dollars'] <= 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        
        all_runs.append({
            'final_balance': balance,
            'pnl': balance - initial_balance,
            'pnl_pct': ((balance - initial_balance) / initial_balance) * 100,
            'num_trades': len(trades),
            'num_skipped': skipped,
            'win_rate': win_rate,
            'trades': trades
        })
    
    # Агрегируем результаты
    return {
        'avg_final_balance': np.mean([r['final_balance'] for r in all_runs]),
        'avg_pnl': np.mean([r['pnl'] for r in all_runs]),
        'avg_pnl_pct': np.mean([r['pnl_pct'] for r in all_runs]),
        'avg_num_trades': np.mean([r['num_trades'] for r in all_runs]),
        'avg_num_skipped': np.mean([r['num_skipped'] for r in all_runs]),
        'avg_win_rate': np.mean([r['win_rate'] for r in all_runs]),
        'min_final_balance': np.min([r['final_balance'] for r in all_runs]),
        'max_final_balance': np.max([r['final_balance'] for r in all_runs]),
        'std_final_balance': np.std([r['final_balance'] for r in all_runs]),
        'config': config,
        'sample_run': all_runs[0]  # Первый прогон для примера
    }

print("=" * 90)
print("🎯 РЕАЛИСТИЧНЫЙ СИМУЛЯТОР с учетом временных перекрытий")
print("=" * 90)

# Загружаем данные
signals_df = pd.read_csv('/tmp/signals_nov17_18_with_header.csv')

print(f"\n📊 Загружено сигналов: {len(signals_df)}")
print(f"   BUY: {len(signals_df[signals_df['verdict'] == 'BUY'])}")
print(f"   SELL: {len(signals_df[signals_df['verdict'] == 'SELL'])}")
print(f"   Период: {signals_df['timestamp'].min()} → {signals_df['timestamp'].max()}")

# Конфигурации для тестирования
strategies = [
    {'name': '✅ Текущая (ALL-IN 20x)', 'leverage': 20, 'position_size_pct': 100, 'max_positions': 1, 'stop_loss_pct': 10, 'trade_sell_only': False},
    {'name': '1. SELL-only 20x 100%', 'leverage': 20, 'position_size_pct': 100, 'max_positions': 1, 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '2. SELL-only 10x 50%', 'leverage': 10, 'position_size_pct': 50, 'max_positions': 1, 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '3. SELL-only 10x 20%', 'leverage': 10, 'position_size_pct': 20, 'max_positions': 1, 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '4. SELL-only 5x 50%', 'leverage': 5, 'position_size_pct': 50, 'max_positions': 1, 'stop_loss_pct': 25, 'trade_sell_only': True},
    {'name': '5. SELL-only 5x 100%', 'leverage': 5, 'position_size_pct': 100, 'max_positions': 1, 'stop_loss_pct': 25, 'trade_sell_only': True},
    {'name': '6. ALL 10x 50%', 'leverage': 10, 'position_size_pct': 50, 'max_positions': 1, 'stop_loss_pct': 20, 'trade_sell_only': False},
    {'name': '7. ALL 10x 20%', 'leverage': 10, 'position_size_pct': 20, 'max_positions': 1, 'stop_loss_pct': 20, 'trade_sell_only': False},
    {'name': '8. ALL 5x 50%', 'leverage': 5, 'position_size_pct': 50, 'max_positions': 1, 'stop_loss_pct': 25, 'trade_sell_only': False},
    {'name': '9. SELL-only 50x 20%', 'leverage': 50, 'position_size_pct': 20, 'max_positions': 1, 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '10. SELL-only 20x 50%', 'leverage': 20, 'position_size_pct': 50, 'max_positions': 1, 'stop_loss_pct': 15, 'trade_sell_only': True},
    {'name': '11. SELL-only 15x 33%', 'leverage': 15, 'position_size_pct': 33, 'max_positions': 1, 'stop_loss_pct': 20, 'trade_sell_only': True},
]

print("\n🔄 Запуск симуляций (по 20 прогонов каждой)...")
results = []
for i, strat in enumerate(strategies, 1):
    print(f"   [{i}/{len(strategies)}] {strat['name']}")
    result = run_realistic_simulation(signals_df, strat, num_runs=20)
    results.append(result)

# Сортируем по прибыльности
results_sorted = sorted(results, key=lambda x: x['avg_final_balance'], reverse=True)

print("\n" + "=" * 90)
print("🏆 РЕЗУЛЬТАТЫ (отсортировано по итоговому балансу)")
print("=" * 90)

for i, r in enumerate(results_sorted, 1):
    c = r['config']
    risk = "🔴 ВЫСОКИЙ" if c['leverage'] >= 20 else "🟡 СРЕДНИЙ" if c['leverage'] >= 10 else "🟢 НИЗКИЙ"
    
    print(f"\n#{i} | {c['name']}")
    print(f"     💰 $1000 → ${r['avg_final_balance']:.2f} ({r['avg_pnl_pct']:+.1f}%)")
    print(f"     📊 Винрейт: {r['avg_win_rate']:.1f}% | Трейдов: {r['avg_num_trades']:.0f} | Пропущено: {r['avg_num_skipped']:.0f}")
    print(f"     ⚙️  Плечо: {c['leverage']}x | Размер: {c['position_size_pct']}% | SL: {c['stop_loss_pct']}% | Риск: {risk}")
    print(f"     📈 Диапазон: ${r['min_final_balance']:.2f} - ${r['max_final_balance']:.2f}")

# Детальный отчет по лучшей конфигурации
best = results_sorted[0]
current = [r for r in results_sorted if '✅ Текущая' in r['config']['name']][0]

print("\n" + "=" * 90)
print("⭐ ОПТИМАЛЬНАЯ КОНФИГУРАЦИЯ")
print("=" * 90)
print(f"\n{best['config']['name']}")
print(f"\n📍 Параметры:")
print(f"   Плечо: {best['config']['leverage']}x")
print(f"   Размер позиции: {best['config']['position_size_pct']}%")
print(f"   Stop-Loss: {best['config']['stop_loss_pct']}%")
print(f"   Max позиций: {best['config']['max_positions']}")
print(f"   SELL-only: {best['config']['trade_sell_only']}")

print(f"\n💵 Ожидаемый результат за 2 дня (17-18 ноя):")
print(f"   Начальный: $1,000")
print(f"   Средний финал: ${best['avg_final_balance']:.2f}")
print(f"   Средний PnL: ${best['avg_pnl']:.2f} ({best['avg_pnl_pct']:+.1f}%)")
print(f"   Худший случай: ${best['min_final_balance']:.2f}")
print(f"   Лучший случай: ${best['max_final_balance']:.2f}")

print(f"\n📊 Торговая статистика:")
print(f"   Исполнено трейдов: {best['avg_num_trades']:.0f}")
print(f"   Пропущено (позиция открыта): {best['avg_num_skipped']:.0f}")
print(f"   Винрейт: {best['avg_win_rate']:.1f}%")

# Сравнение с текущей
current_pos = results_sorted.index(current) + 1
print(f"\n" + "=" * 90)
print(f"📊 ВАША ТЕКУЩАЯ КОНФИГУРАЦИЯ")
print("=" * 90)
print(f"\nПозиция в рейтинге: #{current_pos} из {len(results_sorted)}")
print(f"Ожидаемый баланс: ${current['avg_final_balance']:.2f} ({current['avg_pnl_pct']:+.1f}%)")
print(f"Трейдов: {current['avg_num_trades']:.0f} | Пропущено: {current['avg_num_skipped']:.0f}")
print(f"Винрейт: {current['avg_win_rate']:.1f}%")

if current_pos != 1:
    improvement = best['avg_final_balance'] - current['avg_final_balance']
    improvement_pct = (improvement / current['avg_final_balance']) * 100
    print(f"\n💡 Переход на #{1} даст улучшение:")
    print(f"   +${improvement:.2f} (+{improvement_pct:.1f}%)")
else:
    print(f"\n✅ Ваша конфигурация ОПТИМАЛЬНА!")

# Анализ SELL-only vs ALL
print(f"\n" + "=" * 90)
print("🔍 АНАЛИЗ: SELL-only vs ALL signals")
print("=" * 90)

sell_results = [r for r in results_sorted if r['config']['trade_sell_only']]
all_results = [r for r in results_sorted if not r['config']['trade_sell_only']]

if sell_results and all_results:
    best_sell = sell_results[0]
    best_all = all_results[0]
    
    print(f"\nЛучшая SELL-only: {best_sell['config']['name']}")
    print(f"  Баланс: ${best_sell['avg_final_balance']:.2f}")
    print(f"  Трейдов: {best_sell['avg_num_trades']:.0f} | Пропущено: {best_sell['avg_num_skipped']:.0f}")
    
    print(f"\nЛучшая ALL signals: {best_all['config']['name']}")
    print(f"  Баланс: ${best_all['avg_final_balance']:.2f}")
    print(f"  Трейдов: {best_all['avg_num_trades']:.0f} | Пропущено: {best_all['avg_num_skipped']:.0f}")
    
    if best_sell['avg_final_balance'] > best_all['avg_final_balance']:
        diff_pct = ((best_sell['avg_final_balance'] / best_all['avg_final_balance']) - 1) * 100
        print(f"\n✅ SELL-only превосходит на {diff_pct:+.1f}%")
    else:
        diff_pct = ((best_all['avg_final_balance'] / best_sell['avg_final_balance']) - 1) * 100
        print(f"\n✅ ALL signals превосходят на {diff_pct:+.1f}%")

# Пример трейдов из одного прогона
print(f"\n" + "=" * 90)
print("📋 ПРИМЕР ТРЕЙДОВ (первый прогон лучшей конфигурации)")
print("=" * 90)

sample_trades = best['sample_run']['trades'][:10]  # Первые 10 трейдов
print(f"\nПоказано первых 10 из {len(best['sample_run']['trades'])} трейдов:")

for i, trade in enumerate(sample_trades, 1):
    outcome_emoji = "✅" if trade['outcome'] == 'TP' else "❌" if trade['outcome'] == 'SL' else "⏱️"
    print(f"\n{i}. {trade['timestamp']} | {trade['signal_type']} | {outcome_emoji} {trade['outcome']}")
    print(f"   PnL: {trade['pnl_pct']:+.2f}% (${trade['pnl_dollars']:+.2f}) | Длительность: {trade['duration']}м")
    print(f"   Баланс после: ${trade['balance_after']:.2f}")

# Сохраняем результаты
output = {
    'summary': {
        'best_config': best['config'],
        'best_avg_balance': best['avg_final_balance'],
        'best_avg_pnl_pct': best['avg_pnl_pct'],
        'current_config_rank': current_pos
    },
    'all_results': [{
        'config': r['config'],
        'avg_final_balance': r['avg_final_balance'],
        'avg_pnl_pct': r['avg_pnl_pct'],
        'avg_num_trades': r['avg_num_trades'],
        'avg_num_skipped': r['avg_num_skipped'],
        'avg_win_rate': r['avg_win_rate']
    } for r in results_sorted]
}

with open('/tmp/realistic_backtest_results.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

print("\n" + "=" * 90)
print("✅ Результаты сохранены в /tmp/realistic_backtest_results.json")
print("=" * 90)
