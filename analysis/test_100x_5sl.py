#!/usr/bin/env python3
"""
Симуляция торговли по параметрам:
- All-In режим (весь баланс в одну позицию)
- Плечо: 100x
- Stop-Loss: 5% от позиции (0.05% движения цены)
- Take-Profit: ближайший таргет (target_min)
"""

import pandas as pd
from datetime import datetime, timedelta

# Параметры тестирования
LEVERAGE = 100
STOP_LOSS_PCT = 5  # 5% от позиции = 0.05% движения цены при 100x
INITIAL_BALANCE = 1000.0

# Комиссии BingX
ENTRY_FEE = 0.0005  # 0.05% taker
TP_FEE_MAKER = 0.0002  # 0.02% maker
SL_FEE = 0.0005  # 0.05% taker

def calculate_pnl(entry_price, exit_price, side, leverage, position_size, is_tp=True):
    """Рассчитать PnL позиции с учетом комиссий"""
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
    total_pnl_pct = (total_pnl / position_size) * 100
    
    return total_pnl, total_pnl_pct

def check_sl_before_target(row, target_price, leverage, sl_pct):
    """
    Проверить, был ли достигнут SL ДО таргета
    Возвращает: (sl_hit, sl_price)
    """
    entry_price = row['entry_price']
    side = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    
    # Рассчитать SL цену
    sl_price_change_pct = sl_pct / 100 / leverage
    
    if side == 'BUY':
        # BUY: SL ниже входа
        sl_price = entry_price * (1 - sl_price_change_pct)
        target_reached = highest >= target_price if target_price > 0 else False
        sl_hit = lowest <= sl_price
        
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

def simulate_trading():
    """Симуляция торговли по заданным параметрам"""
    
    print("=" * 80)
    print("СИМУЛЯЦИЯ ТОРГОВЛИ - ALL-IN 100x LEVERAGE, 5% SL")
    print("=" * 80)
    
    # Загрузить сигналы за сегодня
    today = datetime.now().strftime('%Y-%m-%d')
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    
    # Фильтр: только сегодня + не отмененные
    df = effectiveness[
        (effectiveness['timestamp_sent'].dt.strftime('%Y-%m-%d') == today) &
        (effectiveness['result'] != 'CANCELLED')
    ].copy()
    
    df = df.sort_values('timestamp_sent')
    
    print(f"\n📊 Параметры тестирования:")
    print(f"   Режим: All-In (весь баланс в одну позицию)")
    print(f"   Плечо: {LEVERAGE}x")
    print(f"   Stop-Loss: {STOP_LOSS_PCT}% от позиции ({STOP_LOSS_PCT/LEVERAGE:.3f}% движения цены)")
    print(f"   Take-Profit: target_min (ближайший таргет)")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    
    print(f"\n📈 Сигналы за сегодня:")
    print(f"   Всего сигналов: {len(df)}")
    print(f"   BUY: {len(df[df['verdict']=='BUY'])}")
    print(f"   SELL: {len(df[df['verdict']=='SELL'])}")
    
    # Симуляция
    balance = INITIAL_BALANCE
    trades = []
    position_open = False
    last_close_time = None
    
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
        entry_price = signal['entry_price']
        target_min = signal['target_min']
        side = signal['verdict']
        
        if target_min <= 0:
            continue
        
        position_size = balance
        
        # Проверить, был ли SL до target_min
        sl_hit, sl_price = check_sl_before_target(signal, target_min, LEVERAGE, STOP_LOSS_PCT)
        
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
        pnl, pnl_pct = calculate_pnl(
            entry_price, exit_price, side, LEVERAGE, 
            position_size, is_tp
        )
        
        # Обновить баланс
        balance += pnl
        
        # Если баланс упал до нуля или ниже - стоп
        if balance <= 0:
            balance = 0
            trades.append({
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
            print(f"\n⛔ БАЛАНС ОБНУЛЕН НА {len(trades)} СДЕЛКЕ!")
            break
        
        # Сохранить результат
        trades.append({
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
    
    df_trades = pd.DataFrame(trades)
    
    # Результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ТОРГОВЛИ")
    print("=" * 80)
    
    print(f"\n📈 Статистика сделок:")
    print(f"   Всего сделок: {len(df_trades)}")
    
    tp_count = len(df_trades[df_trades['exit_reason']=='TP'])
    sl_count = len(df_trades[df_trades['exit_reason']=='SL'])
    ttl_count = len(df_trades[df_trades['exit_reason']=='TTL'])
    
    print(f"   ✅ TP: {tp_count} ({tp_count/len(df_trades)*100:.1f}%)")
    print(f"   🛑 SL: {sl_count} ({sl_count/len(df_trades)*100:.1f}%)")
    print(f"   ⏱️ TTL: {ttl_count} ({ttl_count/len(df_trades)*100:.1f}%)")
    
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] <= 0]
    
    print(f"\n🎯 Win Rate:")
    print(f"   Выигрышных: {len(wins)} ({len(wins)/len(df_trades)*100:.1f}%)")
    print(f"   Убыточных: {len(losses)} ({len(losses)/len(df_trades)*100:.1f}%)")
    
    if len(wins) > 0:
        print(f"\n💚 Анализ выигрышных сделок:")
        print(f"   Средний WIN: ${wins['pnl'].mean():.2f} ({wins['pnl_pct'].mean():.1f}%)")
        print(f"   Максимальный WIN: ${wins['pnl'].max():.2f} ({wins['pnl_pct'].max():.1f}%)")
        print(f"   Минимальный WIN: ${wins['pnl'].min():.2f} ({wins['pnl_pct'].min():.1f}%)")
        print(f"   Общая прибыль: ${wins['pnl'].sum():.2f}")
    
    if len(losses) > 0:
        print(f"\n💔 Анализ убыточных сделок:")
        print(f"   Средний LOSS: ${losses['pnl'].mean():.2f} ({losses['pnl_pct'].mean():.1f}%)")
        print(f"   Максимальный LOSS: ${losses['pnl'].min():.2f} ({losses['pnl_pct'].min():.1f}%)")
        print(f"   Минимальный LOSS: ${losses['pnl'].max():.2f} ({losses['pnl_pct'].max():.1f}%)")
        print(f"   Общий убыток: ${losses['pnl'].sum():.2f}")
    
    print(f"\n💰 Итоговые финансы:")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    print(f"   Конечный баланс: ${balance:.2f}")
    print(f"   Чистый PnL: ${balance - INITIAL_BALANCE:.2f}")
    print(f"   ROI: {(balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100:.2f}%")
    
    # Топ-5 лучших сделок
    print(f"\n🏆 ТОП-5 ЛУЧШИХ СДЕЛОК:")
    print("-" * 80)
    top_wins = df_trades.nlargest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_wins.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} - {trade['exit_reason']}")
        print(f"    Entry: ${trade['entry_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    Position: ${trade['position_size']:.2f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance: ${trade['balance']:.2f}")
    
    # Топ-5 худших сделок
    print(f"\n💔 ТОП-5 ХУДШИХ СДЕЛОК:")
    print("-" * 80)
    top_losses = df_trades.nsmallest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_losses.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} - {trade['exit_reason']}")
        print(f"    Entry: ${trade['entry_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    Position: ${trade['position_size']:.2f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance: ${trade['balance']:.2f}")
    
    # График баланса
    print(f"\n📈 ДИНАМИКА БАЛАНСА:")
    print("-" * 80)
    
    # Показать каждую 10-ю сделку
    step = max(1, len(df_trades) // 10)
    for i in range(0, len(df_trades), step):
        trade = df_trades.iloc[i]
        bar_length = int(trade['balance'] / INITIAL_BALANCE * 50)
        bar = '█' * bar_length
        print(f"Сделка {i+1:3d}: {bar} ${trade['balance']:.2f}")
    
    # Последняя сделка
    if len(df_trades) > 0:
        last_trade = df_trades.iloc[-1]
        bar_length = int(last_trade['balance'] / INITIAL_BALANCE * 50)
        bar = '█' * bar_length
        print(f"Сделка {len(df_trades):3d}: {bar} ${last_trade['balance']:.2f}")
    
    # Сохранить результаты
    df_trades.to_csv('analysis/results/test_100x_5sl_trades.csv', index=False)
    
    print("\n" + "=" * 80)
    print("✅ Детальные результаты сохранены: analysis/results/test_100x_5sl_trades.csv")
    print("=" * 80)
    
    # Выводы
    print("\n" + "=" * 80)
    print("💡 ВЫВОДЫ")
    print("=" * 80)
    
    if balance > INITIAL_BALANCE:
        roi = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
        print(f"\n✅ СТРАТЕГИЯ ПРИБЫЛЬНАЯ!")
        print(f"   💰 Прибыль: ${balance - INITIAL_BALANCE:.2f}")
        print(f"   📈 ROI: {roi:.2f}%")
        print(f"   🎯 Win Rate: {len(wins)/len(df_trades)*100:.1f}%")
        
        if roi > 500:
            print(f"\n   🚀 ОЧЕНЬ ВЫСОКАЯ ДОХОДНОСТЬ!")
            print(f"   ⚠️ Но помните: прошлые результаты не гарантируют будущие")
    else:
        loss = INITIAL_BALANCE - balance
        loss_pct = loss / INITIAL_BALANCE * 100
        print(f"\n⛔ СТРАТЕГИЯ УБЫТОЧНАЯ")
        print(f"   💸 Убыток: ${loss:.2f}")
        print(f"   📉 Loss: {loss_pct:.2f}%")
        print(f"   🎯 Win Rate: {len(wins)/len(df_trades)*100:.1f}%")
        
        print(f"\n   Причины убытков:")
        print(f"   - SL слишком узкий ({STOP_LOSS_PCT/LEVERAGE:.3f}% цены)")
        print(f"   - Высокая волатильность рынка")
        print(f"   - {sl_count/len(df_trades)*100:.1f}% сделок закрылись по SL")
        
        print(f"\n   💡 Рекомендации:")
        print(f"   - Увеличить SL до 10-15% от позиции")
        print(f"   - Уменьшить плечо до 50x")
        print(f"   - Использовать Partial режим вместо All-In")

if __name__ == '__main__':
    simulate_trading()
