#!/usr/bin/env python3
"""
Анализ торговых сценариев на основе сигналов за сегодня
Моделирует разные стратегии: all-in, частичные позиции, разные плечи, SL/TP
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Константы
INITIAL_BALANCE = 1000.0
ENTRY_FEE = 0.0005  # 0.05% taker
TP_FEE_MAKER = 0.0002  # 0.02% maker
TP_FEE_TAKER = 0.0005  # 0.05% taker
SL_FEE = 0.0005  # 0.05% taker

def load_todays_signals():
    """Загрузить все сигналы за сегодня"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Загрузить результаты
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    effectiveness_today = effectiveness[effectiveness['timestamp_sent'].dt.strftime('%Y-%m-%d') == today].copy()
    
    # Фильтровать только не-отмененные
    effectiveness_today = effectiveness_today[effectiveness_today['result'] != 'CANCELLED'].copy()
    
    return effectiveness_today

def calculate_position_pnl(entry_price, exit_price, side, leverage, position_size_usd, is_win):
    """Рассчитать PnL позиции с учетом комиссий"""
    # Комиссия входа
    entry_fee_amount = position_size_usd * ENTRY_FEE
    
    # Изменение цены
    if side == 'BUY':
        price_change_pct = (exit_price - entry_price) / entry_price
    else:  # SELL
        price_change_pct = (entry_price - exit_price) / entry_price
    
    # PnL без комиссий
    pnl_before_fees = position_size_usd * leverage * price_change_pct
    
    # Комиссия выхода
    if is_win:
        exit_fee_amount = position_size_usd * TP_FEE_MAKER
    else:
        exit_fee_amount = position_size_usd * TP_FEE_TAKER
    
    # Итоговый PnL
    total_pnl = pnl_before_fees - entry_fee_amount - exit_fee_amount
    total_pnl_pct = (total_pnl / position_size_usd) * 100
    
    return total_pnl, total_pnl_pct

def simulate_all_in_strategy(effectiveness_df, leverage, stop_loss_pct, use_hybrid_tp=True):
    """
    Симуляция All-In стратегии
    - Одна позиция на весь баланс
    - Следующая позиция только после закрытия предыдущей
    - Старые сигналы игнорируются
    """
    results = []
    balance = INITIAL_BALANCE
    position_open = False
    last_close_time = None
    
    # Сортировать по времени отправки
    df = effectiveness_df.sort_values('timestamp_sent').copy()
    
    for idx, signal in df.iterrows():
        # Пропустить, если позиция открыта
        if position_open:
            position_open = False
            continue
        
        # Пропустить старые сигналы
        signal_time = signal['timestamp_sent']
        if last_close_time and signal_time <= last_close_time:
            continue
        
        # Открыть позицию
        position_size = balance
        entry_price = signal['entry_price']
        side = signal['verdict']
        is_win = signal['result'] == 'WIN'
        
        # Определить выход
        if is_win:
            # WIN - достиг целевой зоны
            if use_hybrid_tp:
                # Hybrid TP: BUY -> target_min, SELL -> target_max
                if side == 'BUY':
                    exit_price = signal['target_min'] if signal['target_min'] > 0 else signal['highest_reached']
                else:
                    exit_price = signal['target_max'] if signal['target_max'] > 0 else signal['lowest_reached']
            else:
                exit_price = signal['target_min'] if signal['target_min'] > 0 else signal['final_price']
            exit_reason = 'TP'
        else:
            # LOSS - не достиг цели, проверяем SL или TTL
            # Используем profit_pct чтобы определить, был ли это SL
            profit_pct = signal.get('profit_pct', 0)
            
            # Если убыток больше SL - это SL
            sl_price_change_pct = stop_loss_pct / 100 / leverage
            if abs(profit_pct) / 100 >= sl_price_change_pct * 0.8:  # 80% от SL
                # SL hit
                if side == 'BUY':
                    exit_price = entry_price * (1 - sl_price_change_pct)
                else:
                    exit_price = entry_price * (1 + sl_price_change_pct)
                exit_reason = 'SL'
            else:
                # TTL
                exit_price = signal['final_price']
                exit_reason = 'TTL'
        
        # Рассчитать PnL
        pnl, pnl_pct = calculate_position_pnl(
            entry_price, exit_price, side, leverage, 
            position_size, is_win
        )
        
        # Обновить баланс
        balance += pnl
        
        # Если баланс упал до нуля или ниже - стоп
        if balance <= 0:
            balance = 0
            break
        
        # Сохранить результат
        results.append({
            'timestamp': signal_time,
            'symbol': signal['symbol'],
            'side': side,
            'confidence': signal['confidence'],
            'position_size': position_size,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'balance': balance
        })
        
        # Обновить время последнего закрытия
        duration = signal.get('duration_minutes', 30)
        last_close_time = signal_time + timedelta(minutes=duration)
        position_open = True
    
    return pd.DataFrame(results), balance

def simulate_partial_strategy(effectiveness_df, leverage, stop_loss_pct, position_size_usd=100, max_positions=5, use_hybrid_tp=True):
    """
    Симуляция стратегии частичных позиций
    - Фиксированный размер позиции
    - Максимум N одновременных позиций
    """
    results = []
    balance = INITIAL_BALANCE
    active_positions = []
    
    # Сортировать по времени отправки
    df = effectiveness_df.sort_values('timestamp_sent').copy()
    
    for idx, signal in df.iterrows():
        signal_time = signal['timestamp_sent']
        
        # Закрыть завершенные позиции
        completed = []
        for pos in active_positions:
            if signal_time >= pos['close_time']:
                completed.append(pos)
        
        for pos in completed:
            active_positions.remove(pos)
        
        # Проверить, можем ли открыть новую позицию
        if len(active_positions) >= max_positions:
            continue
        
        if balance < position_size_usd:
            continue
        
        # Открыть позицию
        entry_price = signal['entry_price']
        side = signal['verdict']
        is_win = signal['result'] == 'WIN'
        
        # Определить выход (аналогично all-in)
        if is_win:
            if use_hybrid_tp:
                if side == 'BUY':
                    exit_price = signal['target_min'] if signal['target_min'] > 0 else signal['highest_reached']
                else:
                    exit_price = signal['target_max'] if signal['target_max'] > 0 else signal['lowest_reached']
            else:
                exit_price = signal['target_min'] if signal['target_min'] > 0 else signal['final_price']
            exit_reason = 'TP'
        else:
            profit_pct = signal.get('profit_pct', 0)
            sl_price_change_pct = stop_loss_pct / 100 / leverage
            if abs(profit_pct) / 100 >= sl_price_change_pct * 0.8:
                if side == 'BUY':
                    exit_price = entry_price * (1 - sl_price_change_pct)
                else:
                    exit_price = entry_price * (1 + sl_price_change_pct)
                exit_reason = 'SL'
            else:
                exit_price = signal['final_price']
                exit_reason = 'TTL'
        
        # Рассчитать PnL
        pnl, pnl_pct = calculate_position_pnl(
            entry_price, exit_price, side, leverage, 
            position_size_usd, is_win
        )
        
        # Обновить баланс
        balance += pnl
        
        if balance <= 0:
            balance = 0
            break
        
        # Добавить в активные позиции
        duration = signal.get('duration_minutes', 30)
        close_time = signal_time + timedelta(minutes=duration)
        active_positions.append({
            'close_time': close_time,
            'pnl': pnl
        })
        
        # Сохранить результат
        results.append({
            'timestamp': signal_time,
            'symbol': signal['symbol'],
            'side': side,
            'confidence': signal['confidence'],
            'position_size': position_size_usd,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'balance': balance
        })
    
    return pd.DataFrame(results), balance

def analyze_scenarios():
    """Анализ всех сценариев"""
    print("=" * 80)
    print("АНАЛИЗ ТОРГОВЫХ СЦЕНАРИЕВ - СИГНАЛЫ ЗА СЕГОДНЯ")
    print("=" * 80)
    
    # Загрузить данные
    effectiveness = load_todays_signals()
    
    print(f"\n📊 СТАТИСТИКА СИГНАЛОВ ЗА СЕГОДНЯ (не-отмененные):")
    print(f"   Всего сигналов: {len(effectiveness)}")
    print(f"   BUY: {len(effectiveness[effectiveness['verdict'] == 'BUY'])}")
    print(f"   SELL: {len(effectiveness[effectiveness['verdict'] == 'SELL'])}")
    
    # Распределение результатов
    win_count = len(effectiveness[effectiveness['result'] == 'WIN'])
    loss_count = len(effectiveness[effectiveness['result'] == 'LOSS'])
    
    print(f"\n📈 РАСПРЕДЕЛЕНИЕ РЕЗУЛЬТАТОВ:")
    print(f"   WIN: {win_count} ({win_count/len(effectiveness)*100:.1f}%)")
    print(f"   LOSS: {loss_count} ({loss_count/len(effectiveness)*100:.1f}%)")
    
    # Средние движения цены
    print(f"\n💹 СРЕДНИЙ ПРОФИТ:")
    print(f"   WIN сигналы: {effectiveness[effectiveness['result']=='WIN']['profit_pct'].mean():.3f}%")
    print(f"   LOSS сигналы: {effectiveness[effectiveness['result']=='LOSS']['profit_pct'].mean():.3f}%")
    print(f"   Все: {effectiveness['profit_pct'].mean():.3f}%")
    
    # Тестирование сценариев
    scenarios = []
    
    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ СЦЕНАРИЕВ")
    print("=" * 80)
    
    total_tests = 0
    
    # 1. All-In с разными параметрами
    for leverage in [20, 50, 100]:
        for sl_pct in [5, 10, 15, 20]:
            for hybrid_tp in [True, False]:
                total_tests += 1
                print(f"\r  Тест {total_tests}...", end='', flush=True)
                
                trades_df, final_balance = simulate_all_in_strategy(
                    effectiveness, leverage, sl_pct, hybrid_tp
                )
                
                if len(trades_df) > 0:
                    win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100
                    avg_pnl = trades_df['pnl'].mean()
                    
                    scenarios.append({
                        'strategy': 'All-In',
                        'leverage': leverage,
                        'sl_pct': sl_pct,
                        'tp_mode': 'Hybrid' if hybrid_tp else 'Conservative',
                        'trades': len(trades_df),
                        'win_rate': win_rate,
                        'avg_pnl': avg_pnl,
                        'total_pnl': final_balance - INITIAL_BALANCE,
                        'final_balance': final_balance,
                        'roi': (final_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
                    })
    
    # 2. Частичные позиции с разными параметрами
    for leverage in [20, 50, 100]:
        for sl_pct in [5, 10, 15, 20]:
            for pos_size in [50, 100, 200]:
                for max_pos in [1, 3, 5]:
                    total_tests += 1
                    print(f"\r  Тест {total_tests}...", end='', flush=True)
                    
                    trades_df, final_balance = simulate_partial_strategy(
                        effectiveness, leverage, sl_pct, pos_size, max_pos, True
                    )
                    
                    if len(trades_df) > 0:
                        win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) * 100
                        avg_pnl = trades_df['pnl'].mean()
                        
                        scenarios.append({
                            'strategy': 'Partial',
                            'leverage': leverage,
                            'sl_pct': sl_pct,
                            'tp_mode': 'Hybrid',
                            'position_size': pos_size,
                            'max_positions': max_pos,
                            'trades': len(trades_df),
                            'win_rate': win_rate,
                            'avg_pnl': avg_pnl,
                            'total_pnl': final_balance - INITIAL_BALANCE,
                            'final_balance': final_balance,
                            'roi': (final_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
                        })
    
    print(f"\r  ✅ Завершено {total_tests} тестов")
    
    # Создать DataFrame результатов
    results_df = pd.DataFrame(scenarios)
    
    # Топ-10 по ROI
    print("\n\n🏆 ТОП-10 СТРАТЕГИЙ ПО ROI:")
    print("-" * 80)
    top_roi = results_df.nlargest(10, 'roi')
    for i, (idx, row) in enumerate(top_roi.iterrows(), 1):
        if row['strategy'] == 'All-In':
            print(f"\n#{i} {row['strategy']} | Плечо: {row['leverage']}x | SL: {row['sl_pct']}% | TP: {row['tp_mode']}")
        else:
            print(f"\n#{i} {row['strategy']} | Плечо: {row['leverage']}x | SL: {row['sl_pct']}% | Поз: ${row['position_size']:.0f} | Max: {row['max_positions']}")
        
        print(f"    Сделок: {row['trades']} | Win Rate: {row['win_rate']:.1f}%")
        print(f"    ROI: {row['roi']:.2f}% | Баланс: ${row['final_balance']:.2f} | PnL: ${row['total_pnl']:.2f}")
    
    # Топ-10 по стабильности (Win Rate)
    print("\n\n🎯 ТОП-10 СТРАТЕГИЙ ПО WIN RATE:")
    print("-" * 80)
    top_wr = results_df.nlargest(10, 'win_rate')
    for i, (idx, row) in enumerate(top_wr.iterrows(), 1):
        if row['strategy'] == 'All-In':
            print(f"\n#{i} {row['strategy']} | Плечо: {row['leverage']}x | SL: {row['sl_pct']}% | TP: {row['tp_mode']}")
        else:
            print(f"\n#{i} {row['strategy']} | Плечо: {row['leverage']}x | SL: {row['sl_pct']}% | Поз: ${row['position_size']:.0f} | Max: {row['max_positions']}")
        
        print(f"    Сделок: {row['trades']} | Win Rate: {row['win_rate']:.1f}%")
        print(f"    ROI: {row['roi']:.2f}% | Баланс: ${row['final_balance']:.2f} | PnL: ${row['total_pnl']:.2f}")
    
    # Сохранить результаты
    results_df.to_csv('analysis/results/trading_scenarios_today.csv', index=False)
    print(f"\n\n✅ Результаты сохранены: analysis/results/trading_scenarios_today.csv")
    
    # Рекомендации
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ")
    print("=" * 80)
    
    best_roi = results_df.loc[results_df['roi'].idxmax()]
    best_wr = results_df.loc[results_df['win_rate'].idxmax()]
    
    # Найти сбалансированную стратегию (хороший ROI + хороший WR)
    results_df['score'] = results_df['roi'] * 0.5 + results_df['win_rate'] * 0.5
    balanced = results_df.loc[results_df['score'].idxmax()]
    
    print(f"\n🥇 ЛУЧШАЯ СТРАТЕГИЯ ПО ROI:")
    if best_roi['strategy'] == 'All-In':
        print(f"   ✅ All-In режим")
        print(f"   📊 Плечо: {best_roi['leverage']}x")
        print(f"   🛑 Stop-Loss: {best_roi['sl_pct']}% от позиции ({best_roi['sl_pct']/best_roi['leverage']*100:.2f}% движения цены)")
        print(f"   🎯 Take-Profit: {best_roi['tp_mode']}")
    else:
        print(f"   ✅ Частичные позиции")
        print(f"   💰 Размер позиции: ${best_roi['position_size']:.0f}")
        print(f"   🔢 Макс. позиций: {best_roi['max_positions']}")
        print(f"   📊 Плечо: {best_roi['leverage']}x")
        print(f"   🛑 Stop-Loss: {best_roi['sl_pct']}% ({best_roi['sl_pct']/best_roi['leverage']*100:.2f}% движения цены)")
    print(f"   📈 Результат: ROI {best_roi['roi']:.2f}%, Win Rate {best_roi['win_rate']:.1f}%")
    print(f"   💵 Баланс: ${best_roi['final_balance']:.2f} (PnL: ${best_roi['total_pnl']:.2f})")
    
    print(f"\n🎯 САМАЯ СТАБИЛЬНАЯ СТРАТЕГИЯ (Win Rate):")
    if best_wr['strategy'] == 'All-In':
        print(f"   ✅ All-In режим")
        print(f"   📊 Плечо: {best_wr['leverage']}x")
        print(f"   🛑 Stop-Loss: {best_wr['sl_pct']}% ({best_wr['sl_pct']/best_wr['leverage']*100:.2f}% движения цены)")
        print(f"   🎯 Take-Profit: {best_wr['tp_mode']}")
    else:
        print(f"   ✅ Частичные позиции")
        print(f"   💰 Размер позиции: ${best_wr['position_size']:.0f}")
        print(f"   🔢 Макс. позиций: {best_wr['max_positions']}")
        print(f"   📊 Плечо: {best_wr['leverage']}x")
        print(f"   🛑 Stop-Loss: {best_wr['sl_pct']}%")
    print(f"   📈 Результат: Win Rate {best_wr['win_rate']:.1f}%, ROI {best_wr['roi']:.2f}%")
    print(f"   💵 Баланс: ${best_wr['final_balance']:.2f} (PnL: ${best_wr['total_pnl']:.2f})")
    
    print(f"\n⚖️ СБАЛАНСИРОВАННАЯ СТРАТЕГИЯ (ROI + Win Rate):")
    if balanced['strategy'] == 'All-In':
        print(f"   ✅ All-In режим")
        print(f"   📊 Плечо: {balanced['leverage']}x")
        print(f"   🛑 Stop-Loss: {balanced['sl_pct']}% ({balanced['sl_pct']/balanced['leverage']*100:.2f}% движения цены)")
        print(f"   🎯 Take-Profit: {balanced['tp_mode']}")
    else:
        print(f"   ✅ Частичные позиции")
        print(f"   💰 Размер позиции: ${balanced['position_size']:.0f}")
        print(f"   🔢 Макс. позиций: {balanced['max_positions']}")
        print(f"   📊 Плечо: {balanced['leverage']}x")
        print(f"   🛑 Stop-Loss: {balanced['sl_pct']}%")
    print(f"   📈 Результат: ROI {balanced['roi']:.2f}%, Win Rate {balanced['win_rate']:.1f}%")
    print(f"   💵 Баланс: ${balanced['final_balance']:.2f} (PnL: ${balanced['total_pnl']:.2f})")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_scenarios()
