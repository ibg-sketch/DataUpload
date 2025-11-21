#!/usr/bin/env python3
"""
ПРАВИЛЬНЫЙ анализ торговых сценариев
С проверкой достижения SL ДО таргета через highest_reached/lowest_reached
"""

import pandas as pd
from datetime import datetime, timedelta

# Константы
INITIAL_BALANCE = 1000.0
ENTRY_FEE = 0.0005  # 0.05% taker
TP_FEE_MAKER = 0.0002  # 0.02% maker
SL_FEE = 0.0005  # 0.05% taker

def calculate_pnl(entry_price, exit_price, side, leverage, position_size, is_tp=True):
    """Рассчитать PnL позиции с учетом комиссий"""
    entry_fee_amount = position_size * ENTRY_FEE
    
    if side == 'BUY':
        price_change_pct = (exit_price - entry_price) / entry_price
    else:
        price_change_pct = (entry_price - exit_price) / entry_price
    
    pnl_before_fees = position_size * leverage * price_change_pct
    
    if is_tp:
        exit_fee_amount = position_size * TP_FEE_MAKER
    else:
        exit_fee_amount = position_size * SL_FEE
    
    total_pnl = pnl_before_fees - entry_fee_amount - exit_fee_amount
    return total_pnl

def check_exit(signal, target_price, leverage, sl_pct):
    """
    Определить реальную точку выхода с учетом порядка событий
    Возвращает: (exit_price, exit_reason, is_tp)
    """
    entry_price = signal['entry_price']
    side = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    
    # Рассчитать SL цену
    sl_price_change_pct = sl_pct / 100 / leverage
    
    if side == 'BUY':
        sl_price = entry_price * (1 - sl_price_change_pct)
        sl_hit = lowest <= sl_price
        target_reached = highest >= target_price if target_price > 0 else False
        
        if sl_hit:
            return sl_price, 'SL', False
        elif target_reached:
            return target_price, 'TP', True
        else:
            return signal['final_price'], 'TTL', False
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_change_pct)
        sl_hit = highest >= sl_price
        target_reached = lowest <= target_price if target_price > 0 else False
        
        if sl_hit:
            return sl_price, 'SL', False
        elif target_reached:
            return target_price, 'TP', True
        else:
            return signal['final_price'], 'TTL', False

def simulate_all_in(df, leverage, sl_pct, use_target_max=False):
    """All-In стратегия с правильной проверкой SL"""
    balance = INITIAL_BALANCE
    trades = []
    position_open = False
    last_close_time = None
    
    df_sorted = df.sort_values('timestamp_sent')
    
    for idx, signal in df_sorted.iterrows():
        if position_open:
            position_open = False
            continue
        
        signal_time = signal['timestamp_sent']
        if last_close_time and signal_time <= last_close_time:
            continue
        
        # Определить таргет
        if use_target_max:
            target = signal['target_max']
        else:
            target = signal['target_min']
        
        if target <= 0:
            continue
        
        position_size = balance
        
        # Определить выход
        exit_price, exit_reason, is_tp = check_exit(signal, target, leverage, sl_pct)
        
        # Рассчитать PnL
        pnl = calculate_pnl(
            signal['entry_price'], exit_price, signal['verdict'],
            leverage, position_size, is_tp
        )
        
        balance += pnl
        
        if balance <= 0:
            balance = 0
            trades.append({
                'exit_reason': exit_reason,
                'pnl': pnl
            })
            break
        
        trades.append({
            'exit_reason': exit_reason,
            'pnl': pnl
        })
        
        duration = signal.get('duration_minutes', 30)
        last_close_time = signal_time + timedelta(minutes=duration)
        position_open = True
    
    return trades, balance

def simulate_partial(df, leverage, sl_pct, pos_size, max_pos, use_target_max=False):
    """Partial стратегия с правильной проверкой SL"""
    balance = INITIAL_BALANCE
    trades = []
    active_positions = []
    
    df_sorted = df.sort_values('timestamp_sent')
    
    for idx, signal in df_sorted.iterrows():
        signal_time = signal['timestamp_sent']
        
        # Закрыть завершенные
        active_positions = [p for p in active_positions if signal_time < p['close_time']]
        
        if len(active_positions) >= max_pos or balance < pos_size:
            continue
        
        # Определить таргет
        if use_target_max:
            target = signal['target_max']
        else:
            target = signal['target_min']
        
        if target <= 0:
            continue
        
        # Определить выход
        exit_price, exit_reason, is_tp = check_exit(signal, target, leverage, sl_pct)
        
        # Рассчитать PnL
        pnl = calculate_pnl(
            signal['entry_price'], exit_price, signal['verdict'],
            leverage, pos_size, is_tp
        )
        
        balance += pnl
        
        if balance <= 0:
            balance = 0
            break
        
        trades.append({
            'exit_reason': exit_reason,
            'pnl': pnl
        })
        
        duration = signal.get('duration_minutes', 30)
        close_time = signal_time + timedelta(minutes=duration)
        active_positions.append({'close_time': close_time})
    
    return trades, balance

def analyze_all_scenarios():
    """Анализ всех сценариев с правильной логикой"""
    
    print("=" * 80)
    print("ПРАВИЛЬНЫЙ АНАЛИЗ ТОРГОВЫХ СЦЕНАРИЕВ")
    print("С проверкой достижения SL ДО таргета")
    print("=" * 80)
    
    # Загрузить данные
    today = datetime.now().strftime('%Y-%m-%d')
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    
    df = effectiveness[
        (effectiveness['timestamp_sent'].dt.strftime('%Y-%m-%d') == today) &
        (effectiveness['result'] != 'CANCELLED')
    ].copy()
    
    print(f"\n📊 Сигналы за сегодня: {len(df)}")
    print(f"   BUY: {len(df[df['verdict']=='BUY'])}")
    print(f"   SELL: {len(df[df['verdict']=='SELL'])}")
    
    scenarios = []
    total_tests = 0
    
    print("\n⏳ Тестирование сценариев...")
    
    # All-In сценарии
    for leverage in [20, 50, 100]:
        for sl_pct in [5, 10, 15, 20]:
            for use_max in [False, True]:
                total_tests += 1
                print(f"\r  Тест {total_tests}/132...", end='', flush=True)
                
                trades, final_balance = simulate_all_in(df, leverage, sl_pct, use_max)
                
                if len(trades) > 0:
                    tp_count = len([t for t in trades if t['exit_reason'] == 'TP'])
                    sl_count = len([t for t in trades if t['exit_reason'] == 'SL'])
                    win_count = len([t for t in trades if t['pnl'] > 0])
                    
                    scenarios.append({
                        'strategy': 'All-In',
                        'leverage': leverage,
                        'sl_pct': sl_pct,
                        'target': 'max' if use_max else 'min',
                        'trades': len(trades),
                        'tp_rate': tp_count / len(trades) * 100,
                        'sl_rate': sl_count / len(trades) * 100,
                        'win_rate': win_count / len(trades) * 100,
                        'final_balance': final_balance,
                        'roi': (final_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
                    })
    
    # Partial сценарии
    for leverage in [20, 50, 100]:
        for sl_pct in [5, 10, 15, 20]:
            for pos_size in [50, 100, 200]:
                for max_pos in [1, 3, 5]:
                    total_tests += 1
                    print(f"\r  Тест {total_tests}/132...", end='', flush=True)
                    
                    trades, final_balance = simulate_partial(df, leverage, sl_pct, pos_size, max_pos, False)
                    
                    if len(trades) > 0:
                        tp_count = len([t for t in trades if t['exit_reason'] == 'TP'])
                        sl_count = len([t for t in trades if t['exit_reason'] == 'SL'])
                        win_count = len([t for t in trades if t['pnl'] > 0])
                        
                        scenarios.append({
                            'strategy': 'Partial',
                            'leverage': leverage,
                            'sl_pct': sl_pct,
                            'target': 'min',
                            'pos_size': pos_size,
                            'max_pos': max_pos,
                            'trades': len(trades),
                            'tp_rate': tp_count / len(trades) * 100,
                            'sl_rate': sl_count / len(trades) * 100,
                            'win_rate': win_count / len(trades) * 100,
                            'final_balance': final_balance,
                            'roi': (final_balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
                        })
    
    print(f"\r✅ Завершено {total_tests} тестов")
    
    results_df = pd.DataFrame(scenarios)
    
    # Топ-10 по ROI
    print("\n\n🏆 ТОП-10 СТРАТЕГИЙ ПО ROI:")
    print("=" * 80)
    top_roi = results_df.nlargest(10, 'roi')
    for i, (idx, row) in enumerate(top_roi.iterrows(), 1):
        if row['strategy'] == 'All-In':
            print(f"\n#{i} All-In | {row['leverage']}x | SL {row['sl_pct']}% | Target: {row['target']}")
        else:
            print(f"\n#{i} Partial | {row['leverage']}x | SL {row['sl_pct']}% | ${row['pos_size']:.0f} | Max {row['max_pos']}")
        
        print(f"    Сделок: {row['trades']} | Win Rate: {row['win_rate']:.1f}%")
        print(f"    TP: {row['tp_rate']:.1f}% | SL: {row['sl_rate']:.1f}%")
        print(f"    ROI: {row['roi']:.2f}% | Баланс: ${row['final_balance']:.2f}")
    
    # Топ-10 по Win Rate
    print("\n\n🎯 ТОП-10 СТРАТЕГИЙ ПО WIN RATE:")
    print("=" * 80)
    top_wr = results_df.nlargest(10, 'win_rate')
    for i, (idx, row) in enumerate(top_wr.iterrows(), 1):
        if row['strategy'] == 'All-In':
            print(f"\n#{i} All-In | {row['leverage']}x | SL {row['sl_pct']}% | Target: {row['target']}")
        else:
            print(f"\n#{i} Partial | {row['leverage']}x | SL {row['sl_pct']}% | ${row['pos_size']:.0f} | Max {row['max_pos']}")
        
        print(f"    Сделок: {row['trades']} | Win Rate: {row['win_rate']:.1f}%")
        print(f"    TP: {row['tp_rate']:.1f}% | SL: {row['sl_rate']:.1f}%")
        print(f"    ROI: {row['roi']:.2f}% | Баланс: ${row['final_balance']:.2f}")
    
    # Сохранить
    results_df.to_csv('analysis/results/correct_scenarios.csv', index=False)
    
    # Рекомендации
    print("\n\n" + "=" * 80)
    print("💡 РЕАЛЬНЫЕ РЕКОМЕНДАЦИИ")
    print("=" * 80)
    
    # Найти прибыльные стратегии
    profitable = results_df[results_df['roi'] > 0]
    
    if len(profitable) > 0:
        best = profitable.loc[profitable['roi'].idxmax()]
        
        print(f"\n✅ НАЙДЕНО {len(profitable)} ПРИБЫЛЬНЫХ СТРАТЕГИЙ")
        print(f"\n🥇 ЛУЧШАЯ:")
        if best['strategy'] == 'All-In':
            print(f"   Режим: All-In")
            print(f"   Плечо: {best['leverage']}x")
            print(f"   Stop-Loss: {best['sl_pct']}% ({best['sl_pct']/best['leverage']:.3f}% цены)")
            print(f"   Target: {best['target']}")
        else:
            print(f"   Режим: Partial")
            print(f"   Плечо: {best['leverage']}x")
            print(f"   Stop-Loss: {best['sl_pct']}%")
            print(f"   Размер позиции: ${best['pos_size']:.0f}")
            print(f"   Макс. позиций: {best['max_pos']}")
        
        print(f"\n   📈 Результаты:")
        print(f"   ROI: {best['roi']:.2f}%")
        print(f"   Баланс: ${best['final_balance']:.2f}")
        print(f"   Win Rate: {best['win_rate']:.1f}%")
        print(f"   TP Rate: {best['tp_rate']:.1f}%")
        print(f"   SL Rate: {best['sl_rate']:.1f}%")
        print(f"   Сделок: {best['trades']}")
    else:
        print("\n⛔ НЕ НАЙДЕНО ПРИБЫЛЬНЫХ СТРАТЕГИЙ")
        print("\n   Причины:")
        print("   - Сегодняшний день неудачный для торговли")
        print("   - Высокая волатильность рынка")
        print("   - Сигналы не подходят для All-In режима с высоким плечом")
        
        # Найти наименее убыточную
        best_loss = results_df.loc[results_df['roi'].idxmax()]
        print(f"\n   💡 Наименее убыточная стратегия:")
        if best_loss['strategy'] == 'All-In':
            print(f"   All-In | {best_loss['leverage']}x | SL {best_loss['sl_pct']}%")
        else:
            print(f"   Partial | {best_loss['leverage']}x | SL {best_loss['sl_pct']}% | ${best_loss['pos_size']:.0f}")
        print(f"   ROI: {best_loss['roi']:.2f}% | Win Rate: {best_loss['win_rate']:.1f}%")
    
    print("\n" + "=" * 80)
    print("✅ Результаты: analysis/results/correct_scenarios.csv")
    print("=" * 80)

if __name__ == '__main__':
    analyze_all_scenarios()
