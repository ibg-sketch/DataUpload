#!/usr/bin/env python3
"""
Быстрый симулятор ключевых конфигураций
"""

import pandas as pd
import numpy as np
import json

np.random.seed(42)

ZONE_STATS = {
    'target_min': 0.683,
    'target_mid': 0.524,
    'target_max': 0.389
}

BINGX_FEES = {
    'entry': 0.0005,
    'tp_maker': 0.0002,
    'sl_taker': 0.0005,
    'ttl_taker': 0.0005
}

def simulate_trade(signal, tp_strategy, stop_loss_pct, leverage):
    """Симулирует один трейд"""
    signal_type = signal['verdict']
    entry_price = float(signal['entry_price'])
    target_min = float(signal['target_min'])
    target_max = float(signal['target_max'])
    
    if signal_type == 'BUY':
        target_min_pct = ((target_min - entry_price) / entry_price) * 100
        target_max_pct = ((target_max - entry_price) / entry_price) * 100
    else:
        target_min_pct = ((entry_price - target_min) / entry_price) * 100
        target_max_pct = ((entry_price - target_max) / entry_price) * 100
    
    if tp_strategy == 'hybrid':
        tp_level = 'target_min' if signal_type == 'BUY' else 'target_max'
    else:
        tp_level = tp_strategy
    
    reach_prob = ZONE_STATS[tp_level]
    
    if np.random.random() < reach_prob:
        if tp_level == 'target_min':
            target_pct = target_min_pct
        elif tp_level == 'target_mid':
            target_pct = (target_min_pct + target_max_pct) / 2
        else:
            target_pct = target_max_pct
        
        pnl_pct = target_pct * leverage - (BINGX_FEES['entry'] + BINGX_FEES['tp_maker']) * leverage
        return 'TP', pnl_pct
    else:
        if np.random.random() < 0.10:
            pnl_pct = -(stop_loss_pct / 100) * leverage - (BINGX_FEES['entry'] + BINGX_FEES['sl_taker']) * leverage
            return 'SL', pnl_pct
        else:
            pnl_pct = -0.15 * leverage - (BINGX_FEES['entry'] + BINGX_FEES['ttl_taker']) * leverage
            return 'TTL', pnl_pct

def run_config(signals_df, config, initial_balance=1000.0):
    """Прогоняет одну конфигурацию"""
    balance = initial_balance
    trades = []
    
    for _, signal in signals_df.iterrows():
        if config.get('trade_sell_only') and signal['verdict'] == 'BUY':
            continue
        
        position_size = balance * (config['position_size_pct'] / 100)
        
        if position_size < 10 or balance <= 0:
            break
        
        outcome, pnl_pct = simulate_trade(
            signal, config['tp_strategy'], config['stop_loss_pct'], config['leverage']
        )
        
        pnl_dollars = position_size * (pnl_pct / 100)
        balance += pnl_dollars
        
        trades.append({
            'outcome': outcome,
            'pnl_dollars': pnl_dollars
        })
        
        if config['max_positions'] == 1:
            pass
    
    win_trades = [t for t in trades if t['pnl_dollars'] > 0]
    win_rate = len(win_trades) / len(trades) * 100 if trades else 0
    
    return {
        'final_balance': balance,
        'pnl': balance - initial_balance,
        'pnl_pct': ((balance - initial_balance) / initial_balance) * 100,
        'num_trades': len(trades),
        'win_rate': win_rate
    }

print("=" * 80)
print("БЫСТРЫЙ СИМУЛЯТОР ТОРГОВЫХ КОНФИГУРАЦИЙ")
print("=" * 80)

signals_df = pd.read_csv('/tmp/signals_nov17_18_with_header.csv')
print(f"\n📊 Сигналов: {len(signals_df)} (BUY: {len(signals_df[signals_df['verdict']=='BUY'])}, SELL: {len(signals_df[signals_df['verdict']=='SELL'])})")

key_configs = [
    {'name': '1. Текущая (ALL-IN 20x)', 'leverage': 20, 'position_size_pct': 100, 'max_positions': 1, 'tp_strategy': 'hybrid', 'stop_loss_pct': 10, 'trade_sell_only': False},
    {'name': '2. SELL-only 20x 100%', 'leverage': 20, 'position_size_pct': 100, 'max_positions': 1, 'tp_strategy': 'hybrid', 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '3. SELL-only 10x 50%', 'leverage': 10, 'position_size_pct': 50, 'max_positions': 1, 'tp_strategy': 'hybrid', 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '4. SELL-only 10x 20%', 'leverage': 10, 'position_size_pct': 20, 'max_positions': 3, 'tp_strategy': 'hybrid', 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '5. SELL-only 5x 50%', 'leverage': 5, 'position_size_pct': 50, 'max_positions': 1, 'tp_strategy': 'hybrid', 'stop_loss_pct': 25, 'trade_sell_only': True},
    {'name': '6. SELL-only 50x target_max', 'leverage': 50, 'position_size_pct': 20, 'max_positions': 3, 'tp_strategy': 'target_max', 'stop_loss_pct': 10, 'trade_sell_only': True},
    {'name': '7. SELL-only 20x target_max', 'leverage': 20, 'position_size_pct': 50, 'max_positions': 1, 'tp_strategy': 'target_max', 'stop_loss_pct': 20, 'trade_sell_only': True},
    {'name': '8. ALL 10x target_min', 'leverage': 10, 'position_size_pct': 50, 'max_positions': 1, 'tp_strategy': 'target_min', 'stop_loss_pct': 20, 'trade_sell_only': False},
]

results = []
for config in key_configs:
    print(f"\n  Тестирую: {config['name']}...")
    avg_results = {
        'config_name': config['name'],
        'final_balance': 0,
        'pnl': 0,
        'pnl_pct': 0,
        'num_trades': 0,
        'win_rate': 0
    }
    
    for i in range(50):
        result = run_config(signals_df, config)
        for key in ['final_balance', 'pnl', 'pnl_pct', 'num_trades', 'win_rate']:
            avg_results[key] += result[key]
    
    for key in ['final_balance', 'pnl', 'pnl_pct', 'num_trades', 'win_rate']:
        avg_results[key] /= 50
    
    avg_results['config'] = config
    results.append(avg_results)

results_sorted = sorted(results, key=lambda x: x['final_balance'], reverse=True)

print("\n" + "=" * 80)
print("🏆 РЕЗУЛЬТАТЫ (отсортировано по прибыльности)")
print("=" * 80)

for i, r in enumerate(results_sorted, 1):
    c = r['config']
    print(f"\n#{i} {r['config_name']}")
    print(f"   💰 Баланс: $1000 → ${r['final_balance']:.2f} ({r['pnl_pct']:+.1f}%)")
    print(f"   📊 Винрейт: {r['win_rate']:.1f}% | Трейдов: {r['num_trades']:.0f}")
    print(f"   ⚙️  Плечо: {c['leverage']}x | Размер: {c['position_size_pct']}% | Макс поз: {c['max_positions']}")
    print(f"   🎯 TP: {c['tp_strategy']} | SL: {c['stop_loss_pct']}% | SELL-only: {c['trade_sell_only']}")

best = results_sorted[0]
print("\n" + "=" * 80)
print("⭐ ЛУЧШАЯ КОНФИГУРАЦИЯ")
print("=" * 80)
print(f"\n{best['config_name']}")
print(f"Ожидаемый результат за 2 дня: ${1000:.2f} → ${best['final_balance']:.2f} ({best['pnl_pct']:+.1f}%)")
print(f"Винрейт: {best['win_rate']:.1f}%")
print(f"Трейдов: {best['num_trades']:.0f}")

with open('/tmp/quick_backtest_results.json', 'w') as f:
    json.dump([{k: v for k, v in r.items() if k != 'config'} for r in results_sorted], f, indent=2)

print("\n✅ Результаты сохранены в /tmp/quick_backtest_results.json")
print("=" * 80)
