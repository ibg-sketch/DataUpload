#!/usr/bin/env python3
"""
Trading Configuration Simulator
Тестирует разные конфигурации торговли на реальных сигналах за 17-18 ноября
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
import json

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

def calculate_position_outcome(
    signal: pd.Series,
    tp_strategy: str,
    stop_loss_pct: float,
    leverage: int
) -> Tuple[str, float]:
    """
    Рассчитывает исход позиции на основе статистики зон
    
    Returns:
        (outcome, pnl_pct) где outcome = 'TP', 'SL', или 'TTL'
        pnl_pct - процент PnL от размера позиции
    """
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
    
    random_val = np.random.random()
    
    if random_val < reach_prob:
        outcome = 'TP'
        if tp_level == 'target_min':
            target_pct = target_min_pct
        elif tp_level == 'target_mid':
            target_pct = (target_min_pct + target_max_pct) / 2
        else:
            target_pct = target_max_pct
        
        price_move_pct = target_pct
        pnl_pct = price_move_pct * leverage
        
        fee_pct = BINGX_FEES['entry'] + BINGX_FEES['tp_maker']
        pnl_pct -= fee_pct * leverage
        
        return 'TP', pnl_pct
    
    else:
        sl_hit_prob = 0.10
        if np.random.random() < sl_hit_prob:
            outcome = 'SL'
            pnl_pct = -(stop_loss_pct / 100) * leverage
            fee_pct = BINGX_FEES['entry'] + BINGX_FEES['sl_taker']
            pnl_pct -= fee_pct * leverage
            return 'SL', pnl_pct
        else:
            outcome = 'TTL'
            avg_ttl_loss = -0.15
            pnl_pct = avg_ttl_loss * leverage
            fee_pct = BINGX_FEES['entry'] + BINGX_FEES['ttl_taker']
            pnl_pct -= fee_pct * leverage
            return 'TTL', pnl_pct

def simulate_trading(
    signals_df: pd.DataFrame,
    config: Dict,
    initial_balance: float = 1000.0,
    num_runs: int = 100
) -> Dict:
    """
    Симулирует торговлю с заданной конфигурацией
    
    Args:
        signals_df: DataFrame с сигналами
        config: Конфигурация торговли
        initial_balance: Начальный баланс
        num_runs: Количество прогонов для усреднения результатов
    """
    leverage = config['leverage']
    position_size_pct = config['position_size_pct']
    max_positions = config['max_positions']
    tp_strategy = config['tp_strategy']
    stop_loss_pct = config['stop_loss_pct']
    trade_sell_only = config.get('trade_sell_only', False)
    
    results = []
    
    for run in range(num_runs):
        balance = initial_balance
        active_positions = []
        trades = []
        
        for idx, signal in signals_df.iterrows():
            if trade_sell_only and signal['verdict'] == 'BUY':
                continue
            
            if len(active_positions) >= max_positions:
                continue
            
            position_size = balance * (position_size_pct / 100)
            
            if position_size < 10:
                continue
            
            outcome, pnl_pct = calculate_position_outcome(
                signal, tp_strategy, stop_loss_pct, leverage
            )
            
            pnl_dollars = position_size * (pnl_pct / 100)
            balance += pnl_dollars
            
            trades.append({
                'signal_id': signal['signal_id'],
                'coin': signal['symbol'],
                'signal_type': signal['verdict'],
                'outcome': outcome,
                'pnl_pct': pnl_pct,
                'pnl_dollars': pnl_dollars,
                'balance_after': balance
            })
            
            if balance <= 0:
                break
        
        final_balance = balance
        total_pnl = final_balance - initial_balance
        pnl_pct_total = (total_pnl / initial_balance) * 100
        
        win_trades = [t for t in trades if t['pnl_dollars'] > 0]
        lose_trades = [t for t in trades if t['pnl_dollars'] <= 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0
        
        results.append({
            'final_balance': final_balance,
            'total_pnl': total_pnl,
            'pnl_pct': pnl_pct_total,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'trades': trades
        })
    
    avg_final_balance = np.mean([r['final_balance'] for r in results])
    avg_pnl = np.mean([r['total_pnl'] for r in results])
    avg_pnl_pct = np.mean([r['pnl_pct'] for r in results])
    avg_num_trades = np.mean([r['num_trades'] for r in results])
    avg_win_rate = np.mean([r['win_rate'] for r in results])
    
    std_final_balance = np.std([r['final_balance'] for r in results])
    min_final_balance = np.min([r['final_balance'] for r in results])
    max_final_balance = np.max([r['final_balance'] for r in results])
    
    return {
        'config': config,
        'avg_final_balance': avg_final_balance,
        'avg_pnl': avg_pnl,
        'avg_pnl_pct': avg_pnl_pct,
        'avg_num_trades': avg_num_trades,
        'avg_win_rate': avg_win_rate,
        'std_final_balance': std_final_balance,
        'min_final_balance': min_final_balance,
        'max_final_balance': max_final_balance,
        'worst_case_pnl_pct': ((min_final_balance - initial_balance) / initial_balance) * 100,
        'best_case_pnl_pct': ((max_final_balance - initial_balance) / initial_balance) * 100
    }

def main():
    print("=" * 80)
    print("СИМУЛЯТОР ТОРГОВЫХ КОНФИГУРАЦИЙ")
    print("Тестирование на сигналах 17-18 ноября 2025")
    print("=" * 80)
    
    signals_df = pd.read_csv('/tmp/signals_nov17_18_with_header.csv')
    print(f"\n📊 Загружено сигналов: {len(signals_df)}")
    print(f"   BUY: {len(signals_df[signals_df['verdict'] == 'BUY'])}")
    print(f"   SELL: {len(signals_df[signals_df['verdict'] == 'SELL'])}")
    
    initial_balance = 1000.0
    
    configs_to_test = []
    
    for leverage in [5, 10, 20, 50]:
        for position_size_pct in [20, 50, 100]:
            for max_positions in [1, 3]:
                for tp_strategy in ['target_min', 'target_max', 'hybrid']:
                    for stop_loss_pct in [10, 20, 25]:
                        for trade_sell_only in [False, True]:
                            configs_to_test.append({
                                'leverage': leverage,
                                'position_size_pct': position_size_pct,
                                'max_positions': max_positions,
                                'tp_strategy': tp_strategy,
                                'stop_loss_pct': stop_loss_pct,
                                'trade_sell_only': trade_sell_only
                            })
    
    print(f"\n🔍 Тестирую {len(configs_to_test)} конфигураций...")
    print("   (каждая прогоняется 20 раз для стабильности результатов)")
    
    results = []
    for i, config in enumerate(configs_to_test):
        if (i + 1) % 50 == 0:
            print(f"   Прогресс: {i+1}/{len(configs_to_test)} ({(i+1)/len(configs_to_test)*100:.1f}%)")
        
        result = simulate_trading(signals_df, config, initial_balance, num_runs=20)
        results.append(result)
    
    results_sorted = sorted(results, key=lambda x: x['avg_final_balance'], reverse=True)
    
    print("\n" + "=" * 80)
    print("🏆 ТОП-20 САМЫХ ПРИБЫЛЬНЫХ КОНФИГУРАЦИЙ")
    print("=" * 80)
    
    for i, result in enumerate(results_sorted[:20], 1):
        config = result['config']
        print(f"\n#{i} | Баланс: ${result['avg_final_balance']:.2f} | PnL: {result['avg_pnl_pct']:+.1f}%")
        print(f"     Плечо: {config['leverage']}x | Размер позиции: {config['position_size_pct']}% | Макс позиций: {config['max_positions']}")
        print(f"     TP стратегия: {config['tp_strategy']} | SL: {config['stop_loss_pct']}% | SELL-only: {config['trade_sell_only']}")
        print(f"     Винрейт: {result['avg_win_rate']:.1f}% | Трейдов: {result['avg_num_trades']:.0f}")
        print(f"     Диапазон: ${result['min_final_balance']:.2f} - ${result['max_final_balance']:.2f} (±{result['std_final_balance']:.2f})")
    
    print("\n" + "=" * 80)
    print("📉 ТОП-10 ХУДШИХ КОНФИГУРАЦИЙ (для избегания)")
    print("=" * 80)
    
    for i, result in enumerate(results_sorted[-10:], 1):
        config = result['config']
        print(f"\n#{i} | Баланс: ${result['avg_final_balance']:.2f} | PnL: {result['avg_pnl_pct']:+.1f}%")
        print(f"     Плечо: {config['leverage']}x | Размер позиции: {config['position_size_pct']}% | Макс позиций: {config['max_positions']}")
        print(f"     TP стратегия: {config['tp_strategy']} | SL: {config['stop_loss_pct']}% | SELL-only: {config['trade_sell_only']}")
    
    best_config = results_sorted[0]
    print("\n" + "=" * 80)
    print("⭐ ОПТИМАЛЬНАЯ КОНФИГУРАЦИЯ")
    print("=" * 80)
    print(f"\nПлечо: {best_config['config']['leverage']}x")
    print(f"Размер позиции: {best_config['config']['position_size_pct']}% от баланса")
    print(f"Максимум позиций одновременно: {best_config['config']['max_positions']}")
    print(f"TP стратегия: {best_config['config']['tp_strategy']}")
    print(f"Stop-Loss: {best_config['config']['stop_loss_pct']}%")
    print(f"Торговать только SELL: {best_config['config']['trade_sell_only']}")
    print(f"\nОжидаемый результат за 2 дня:")
    print(f"  Баланс: ${initial_balance:.2f} → ${best_config['avg_final_balance']:.2f}")
    print(f"  PnL: {best_config['avg_pnl_pct']:+.1f}%")
    print(f"  Винрейт: {best_config['avg_win_rate']:.1f}%")
    print(f"  Количество трейдов: {best_config['avg_num_trades']:.0f}")
    print(f"  Худший случай: ${best_config['min_final_balance']:.2f} ({best_config['worst_case_pnl_pct']:+.1f}%)")
    print(f"  Лучший случай: ${best_config['max_final_balance']:.2f} ({best_config['best_case_pnl_pct']:+.1f}%)")
    
    with open('/tmp/best_trading_config.json', 'w') as f:
        json.dump(best_config, f, indent=2, default=str)
    
    print("\n✅ Результаты сохранены в /tmp/best_trading_config.json")
    print("=" * 80)

if __name__ == '__main__':
    main()
