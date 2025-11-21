#!/usr/bin/env python3
"""
Сравнение PnL: закрытие по target_min vs target_max
С учетом достижения SL ДО таргета
"""

import pandas as pd
from datetime import datetime

# Константы (текущие настройки)
LEVERAGE = 50
STOP_LOSS_PCT = 10  # 10% от позиции
INITIAL_BALANCE = 1000.0

# Комиссии BingX
ENTRY_FEE = 0.0005  # 0.05% taker
TP_FEE_MAKER = 0.0002  # 0.02% maker
SL_FEE = 0.0005  # 0.05% taker

def calculate_pnl(entry_price, exit_price, side, leverage, position_size, is_tp=True):
    """Рассчитать PnL позиции"""
    # Комиссия входа
    entry_fee_amount = position_size * ENTRY_FEE
    
    # Изменение цены
    if side == 'BUY':
        price_change_pct = (exit_price - entry_price) / entry_price
    else:  # SELL
        price_change_pct = (entry_price - exit_price) / entry_price
    
    # PnL без комиссий
    pnl_before_fees = position_size * leverage * price_change_pct
    
    # Комиссия выхода
    if is_tp:
        exit_fee_amount = position_size * TP_FEE_MAKER
    else:
        exit_fee_amount = position_size * SL_FEE
    
    # Итоговый PnL
    total_pnl = pnl_before_fees - entry_fee_amount - exit_fee_amount
    
    return total_pnl

def check_sl_before_target(row, target_price):
    """
    Проверить, был ли достигнут SL ДО таргета
    Возвращает: (sl_hit, sl_price)
    """
    entry_price = row['entry_price']
    side = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    
    # Рассчитать SL цену (10% от позиции при 50x = 0.2% движения цены)
    sl_price_change_pct = STOP_LOSS_PCT / 100 / LEVERAGE
    
    if side == 'BUY':
        # BUY: SL ниже входа
        sl_price = entry_price * (1 - sl_price_change_pct)
        target_reached = highest >= target_price if target_price > 0 else False
        sl_hit = lowest <= sl_price
        
        # Если оба достигнуты, нужно понять что первое
        # Простое предположение: если SL hit, то он был первым (консервативный подход)
        if sl_hit:
            return True, sl_price
        
    else:  # SELL
        # SELL: SL выше входа
        sl_price = entry_price * (1 + sl_price_change_pct)
        target_reached = lowest <= target_price if target_price > 0 else False
        sl_hit = highest >= sl_price
        
        if sl_hit:
            return True, sl_price
    
    return False, None

def analyze_target_comparison():
    """Сравнить PnL для target_min vs target_max"""
    
    # Загрузить сигналы за сегодня
    today = datetime.now().strftime('%Y-%m-%d')
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    
    # Фильтр: только сегодня + не отмененные + WIN сигналы
    df = effectiveness[
        (effectiveness['timestamp_sent'].dt.strftime('%Y-%m-%d') == today) &
        (effectiveness['result'] != 'CANCELLED')
    ].copy()
    
    print("=" * 80)
    print("СРАВНЕНИЕ СТРАТЕГИЙ ВЫХОДА: TARGET_MIN vs TARGET_MAX")
    print("=" * 80)
    print(f"\n📊 Анализируем {len(df)} сигналов за сегодня")
    print(f"   Настройки: Плечо {LEVERAGE}x, SL {STOP_LOSS_PCT}% от позиции")
    print(f"   SL цена: ±{STOP_LOSS_PCT/LEVERAGE:.3f}% от entry_price")
    
    # Симуляция 1: Закрытие по target_min (консервативная)
    print("\n" + "-" * 80)
    print("🎯 СТРАТЕГИЯ 1: КОНСЕРВАТИВНАЯ (target_min)")
    print("-" * 80)
    
    balance_min = INITIAL_BALANCE
    trades_min = []
    
    for idx, signal in df.iterrows():
        entry_price = signal['entry_price']
        target_min = signal['target_min']
        side = signal['verdict']
        
        if target_min <= 0:
            continue
        
        # Проверить, был ли SL до target_min
        sl_hit, sl_price = check_sl_before_target(signal, target_min)
        
        if sl_hit:
            # SL достигнут до таргета
            exit_price = sl_price
            exit_reason = 'SL'
            is_tp = False
        else:
            # Проверить, достигнут ли target_min
            if side == 'BUY':
                target_reached = signal['highest_reached'] >= target_min
            else:
                target_reached = signal['lowest_reached'] <= target_min
            
            if target_reached:
                exit_price = target_min
                exit_reason = 'TP'
                is_tp = True
            else:
                # Таргет не достигнут - TTL
                exit_price = signal['final_price']
                exit_reason = 'TTL'
                is_tp = False
        
        # Рассчитать PnL
        pnl = calculate_pnl(entry_price, exit_price, side, LEVERAGE, balance_min, is_tp)
        balance_min += pnl
        
        if balance_min <= 0:
            balance_min = 0
            break
        
        trades_min.append({
            'symbol': signal['symbol'],
            'side': side,
            'entry': entry_price,
            'exit': exit_price,
            'reason': exit_reason,
            'pnl': pnl,
            'balance': balance_min
        })
    
    df_min = pd.DataFrame(trades_min)
    
    print(f"\n📈 Результаты:")
    print(f"   Всего сделок: {len(df_min)}")
    print(f"   TP: {len(df_min[df_min['reason']=='TP'])} ({len(df_min[df_min['reason']=='TP'])/len(df_min)*100:.1f}%)")
    print(f"   SL: {len(df_min[df_min['reason']=='SL'])} ({len(df_min[df_min['reason']=='SL'])/len(df_min)*100:.1f}%)")
    print(f"   TTL: {len(df_min[df_min['reason']=='TTL'])} ({len(df_min[df_min['reason']=='TTL'])/len(df_min)*100:.1f}%)")
    print(f"\n💰 Финансы:")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    print(f"   Конечный баланс: ${balance_min:.2f}")
    print(f"   PnL: ${balance_min - INITIAL_BALANCE:.2f}")
    print(f"   ROI: {(balance_min - INITIAL_BALANCE) / INITIAL_BALANCE * 100:.2f}%")
    
    wins = df_min[df_min['pnl'] > 0]
    losses = df_min[df_min['pnl'] <= 0]
    print(f"\n🎯 Win Rate:")
    print(f"   Выигрышных: {len(wins)} ({len(wins)/len(df_min)*100:.1f}%)")
    print(f"   Убыточных: {len(losses)} ({len(losses)/len(df_min)*100:.1f}%)")
    if len(wins) > 0:
        print(f"   Средний WIN: ${wins['pnl'].mean():.2f}")
    if len(losses) > 0:
        print(f"   Средний LOSS: ${losses['pnl'].mean():.2f}")
    
    # Симуляция 2: Закрытие по target_max (агрессивная)
    print("\n" + "-" * 80)
    print("🚀 СТРАТЕГИЯ 2: АГРЕССИВНАЯ (target_max)")
    print("-" * 80)
    
    balance_max = INITIAL_BALANCE
    trades_max = []
    
    for idx, signal in df.iterrows():
        entry_price = signal['entry_price']
        target_max = signal['target_max']
        side = signal['verdict']
        
        if target_max <= 0:
            continue
        
        # Проверить, был ли SL до target_max
        sl_hit, sl_price = check_sl_before_target(signal, target_max)
        
        if sl_hit:
            # SL достигнут до таргета
            exit_price = sl_price
            exit_reason = 'SL'
            is_tp = False
        else:
            # Проверить, достигнут ли target_max
            if side == 'BUY':
                target_reached = signal['highest_reached'] >= target_max
            else:
                target_reached = signal['lowest_reached'] <= target_max
            
            if target_reached:
                exit_price = target_max
                exit_reason = 'TP'
                is_tp = True
            else:
                # Таргет не достигнут - TTL
                exit_price = signal['final_price']
                exit_reason = 'TTL'
                is_tp = False
        
        # Рассчитать PnL
        pnl = calculate_pnl(entry_price, exit_price, side, LEVERAGE, balance_max, is_tp)
        balance_max += pnl
        
        if balance_max <= 0:
            balance_max = 0
            break
        
        trades_max.append({
            'symbol': signal['symbol'],
            'side': side,
            'entry': entry_price,
            'exit': exit_price,
            'reason': exit_reason,
            'pnl': pnl,
            'balance': balance_max
        })
    
    df_max = pd.DataFrame(trades_max)
    
    print(f"\n📈 Результаты:")
    print(f"   Всего сделок: {len(df_max)}")
    print(f"   TP: {len(df_max[df_max['reason']=='TP'])} ({len(df_max[df_max['reason']=='TP'])/len(df_max)*100:.1f}%)")
    print(f"   SL: {len(df_max[df_max['reason']=='SL'])} ({len(df_max[df_max['reason']=='SL'])/len(df_max)*100:.1f}%)")
    print(f"   TTL: {len(df_max[df_max['reason']=='TTL'])} ({len(df_max[df_max['reason']=='TTL'])/len(df_max)*100:.1f}%)")
    print(f"\n💰 Финансы:")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    print(f"   Конечный баланс: ${balance_max:.2f}")
    print(f"   PnL: ${balance_max - INITIAL_BALANCE:.2f}")
    print(f"   ROI: {(balance_max - INITIAL_BALANCE) / INITIAL_BALANCE * 100:.2f}%")
    
    wins = df_max[df_max['pnl'] > 0]
    losses = df_max[df_max['pnl'] <= 0]
    print(f"\n🎯 Win Rate:")
    print(f"   Выигрышных: {len(wins)} ({len(wins)/len(df_max)*100:.1f}%)")
    print(f"   Убыточных: {len(losses)} ({len(losses)/len(df_max)*100:.1f}%)")
    if len(wins) > 0:
        print(f"   Средний WIN: ${wins['pnl'].mean():.2f}")
    if len(losses) > 0:
        print(f"   Средний LOSS: ${losses['pnl'].mean():.2f}")
    
    # Сравнение
    print("\n" + "=" * 80)
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print("=" * 80)
    
    print(f"\n{'Метрика':<25} {'target_min':<20} {'target_max':<20} {'Разница'}")
    print("-" * 80)
    print(f"{'Сделок':<25} {len(df_min):<20} {len(df_max):<20} {len(df_max)-len(df_min)}")
    print(f"{'Конечный баланс':<25} ${balance_min:<19.2f} ${balance_max:<19.2f} ${balance_max-balance_min:.2f}")
    print(f"{'PnL':<25} ${balance_min-INITIAL_BALANCE:<19.2f} ${balance_max-INITIAL_BALANCE:<19.2f} ${(balance_max-INITIAL_BALANCE)-(balance_min-INITIAL_BALANCE):.2f}")
    print(f"{'ROI':<25} {(balance_min-INITIAL_BALANCE)/INITIAL_BALANCE*100:<19.2f}% {(balance_max-INITIAL_BALANCE)/INITIAL_BALANCE*100:<19.2f}% {((balance_max-INITIAL_BALANCE)/INITIAL_BALANCE*100)-((balance_min-INITIAL_BALANCE)/INITIAL_BALANCE*100):.2f}%")
    
    wr_min = len(df_min[df_min['pnl'] > 0]) / len(df_min) * 100 if len(df_min) > 0 else 0
    wr_max = len(df_max[df_max['pnl'] > 0]) / len(df_max) * 100 if len(df_max) > 0 else 0
    print(f"{'Win Rate':<25} {wr_min:<19.1f}% {wr_max:<19.1f}% {wr_max-wr_min:.1f}%")
    
    tp_min = len(df_min[df_min['reason']=='TP']) / len(df_min) * 100 if len(df_min) > 0 else 0
    tp_max = len(df_max[df_max['reason']=='TP']) / len(df_max) * 100 if len(df_max) > 0 else 0
    print(f"{'TP Rate':<25} {tp_min:<19.1f}% {tp_max:<19.1f}% {tp_max-tp_min:.1f}%")
    
    sl_min = len(df_min[df_min['reason']=='SL']) / len(df_min) * 100 if len(df_min) > 0 else 0
    sl_max = len(df_max[df_max['reason']=='SL']) / len(df_max) * 100 if len(df_max) > 0 else 0
    print(f"{'SL Rate':<25} {sl_min:<19.1f}% {sl_max:<19.1f}% {sl_max-sl_min:.1f}%")
    
    # Рекомендация
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИЯ")
    print("=" * 80)
    
    if balance_min > balance_max:
        advantage = (balance_min - balance_max) / balance_max * 100
        print(f"\n✅ target_min (консервативная) ЛУЧШЕ на {advantage:.1f}%")
        print(f"   💰 Больше профита: ${balance_min - balance_max:.2f}")
        print(f"   🎯 Win Rate: {wr_min:.1f}% vs {wr_max:.1f}%")
        print(f"\n   Причина: Меньше риск реверса цены после достижения ближнего таргета")
    else:
        advantage = (balance_max - balance_min) / balance_min * 100
        print(f"\n✅ target_max (агрессивная) ЛУЧШЕ на {advantage:.1f}%")
        print(f"   💰 Больше профита: ${balance_max - balance_min:.2f}")
        print(f"   🎯 Win Rate: {wr_max:.1f}% vs {wr_min:.1f}%")
        print(f"\n   Причина: Цены достигают дальних таргетов без разворота")
    
    print("\n" + "=" * 80)
    
    # Сохранить детальные результаты
    df_min.to_csv('analysis/results/target_min_trades.csv', index=False)
    df_max.to_csv('analysis/results/target_max_trades.csv', index=False)
    print(f"\n✅ Детальные результаты сохранены:")
    print(f"   - analysis/results/target_min_trades.csv")
    print(f"   - analysis/results/target_max_trades.csv")

if __name__ == '__main__':
    analyze_target_comparison()
