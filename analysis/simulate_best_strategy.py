#!/usr/bin/env python3
"""
Детальная симуляция ЛУЧШЕЙ СТРАТЕГИИ на сегодняшних сигналах
Partial: 20x leverage, SL 15%, $200 позиции, Max 5 одновременно
"""

import pandas as pd
from datetime import datetime, timedelta

# Параметры лучшей стратегии
LEVERAGE = 20
STOP_LOSS_PCT = 15  # 15% от позиции = 0.75% движения цены
POSITION_SIZE_USD = 200
MAX_POSITIONS = 5
INITIAL_BALANCE = 1000.0
USE_TARGET_MIN = True

# Комиссии BingX
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
    pnl_pct = (total_pnl / position_size) * 100
    
    return total_pnl, pnl_pct

def check_exit(signal, target_price, leverage, sl_pct):
    """Определить реальную точку выхода"""
    entry_price = signal['entry_price']
    side = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    
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
    else:
        sl_price = entry_price * (1 + sl_price_change_pct)
        sl_hit = highest >= sl_price
        target_reached = lowest <= target_price if target_price > 0 else False
        
        if sl_hit:
            return sl_price, 'SL', False
        elif target_reached:
            return target_price, 'TP', True
        else:
            return signal['final_price'], 'TTL', False

def simulate_best_strategy():
    """Детальная симуляция лучшей стратегии"""
    
    print("=" * 80)
    print("СИМУЛЯЦИЯ ЛУЧШЕЙ СТРАТЕГИИ")
    print("=" * 80)
    
    print(f"\n📊 ПАРАМЕТРЫ:")
    print(f"   Режим: Partial (частичные позиции)")
    print(f"   Плечо: {LEVERAGE}x")
    print(f"   Stop-Loss: {STOP_LOSS_PCT}% от позиции ({STOP_LOSS_PCT/LEVERAGE:.3f}% движения цены)")
    print(f"   Take-Profit: target_min (ближайший таргет)")
    print(f"   Размер позиции: ${POSITION_SIZE_USD}")
    print(f"   Макс. одновременных позиций: {MAX_POSITIONS}")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    
    # Загрузить данные
    today = datetime.now().strftime('%Y-%m-%d')
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    
    df = effectiveness[
        (effectiveness['timestamp_sent'].dt.strftime('%Y-%m-%d') == today) &
        (effectiveness['result'] != 'CANCELLED')
    ].copy()
    
    df = df.sort_values('timestamp_sent')
    
    print(f"\n📈 СИГНАЛЫ ЗА СЕГОДНЯ:")
    print(f"   Всего: {len(df)}")
    print(f"   BUY: {len(df[df['verdict']=='BUY'])}")
    print(f"   SELL: {len(df[df['verdict']=='SELL'])}")
    
    # Симуляция
    balance = INITIAL_BALANCE
    trades = []
    active_positions = []
    skipped_signals = 0
    
    print("\n" + "=" * 80)
    print("ТОРГОВЛЯ")
    print("=" * 80)
    
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
        if len(active_positions) >= MAX_POSITIONS:
            skipped_signals += 1
            continue
        
        if balance < POSITION_SIZE_USD:
            print(f"\n⚠️ Недостаточно средств для новой позиции (баланс: ${balance:.2f})")
            break
        
        # Определить таргет
        target = signal['target_min']
        
        if target <= 0:
            skipped_signals += 1
            continue
        
        # Определить выход
        exit_price, exit_reason, is_tp = check_exit(signal, target, LEVERAGE, STOP_LOSS_PCT)
        
        # Рассчитать PnL
        pnl, pnl_pct = calculate_pnl(
            signal['entry_price'], exit_price, signal['verdict'],
            LEVERAGE, POSITION_SIZE_USD, is_tp
        )
        
        # Обновить баланс
        balance += pnl
        
        # Вывод сделки
        profit_emoji = "✅" if pnl > 0 else "❌"
        exit_emoji = {"TP": "🎯", "SL": "🛑", "TTL": "⏱️"}[exit_reason]
        
        print(f"\n{profit_emoji} Сделка #{len(trades)+1} | {signal['symbol']} {signal['verdict']} | {exit_emoji} {exit_reason}")
        print(f"   Вход: ${signal['entry_price']:.4f} → Выход: ${exit_price:.4f}")
        print(f"   PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | Баланс: ${balance:.2f}")
        print(f"   Активных позиций: {len(active_positions)+1}/{MAX_POSITIONS}")
        
        if balance <= 0:
            balance = 0
            print(f"\n⛔ БАЛАНС ОБНУЛЕН!")
            break
        
        # Сохранить сделку
        trades.append({
            'trade_num': len(trades) + 1,
            'timestamp': signal_time,
            'symbol': signal['symbol'],
            'side': signal['verdict'],
            'confidence': signal['confidence'],
            'entry_price': signal['entry_price'],
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'balance': balance,
            'active_positions': len(active_positions) + 1
        })
        
        # Добавить в активные позиции
        duration = signal.get('duration_minutes', 30)
        close_time = signal_time + timedelta(minutes=duration)
        active_positions.append({'close_time': close_time})
    
    df_trades = pd.DataFrame(trades)
    
    # Результаты
    print("\n\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 80)
    
    print(f"\n📈 Статистика сделок:")
    print(f"   Всего сделок: {len(df_trades)}")
    print(f"   Пропущено сигналов: {skipped_signals} (нет мест или баланса)")
    
    tp_count = len(df_trades[df_trades['exit_reason']=='TP'])
    sl_count = len(df_trades[df_trades['exit_reason']=='SL'])
    ttl_count = len(df_trades[df_trades['exit_reason']=='TTL'])
    
    print(f"\n   Распределение по выходу:")
    print(f"   🎯 TP: {tp_count} ({tp_count/len(df_trades)*100:.1f}%)")
    print(f"   🛑 SL: {sl_count} ({sl_count/len(df_trades)*100:.1f}%)")
    print(f"   ⏱️ TTL: {ttl_count} ({ttl_count/len(df_trades)*100:.1f}%)")
    
    wins = df_trades[df_trades['pnl'] > 0]
    losses = df_trades[df_trades['pnl'] <= 0]
    
    print(f"\n🎯 Win Rate:")
    print(f"   ✅ Выигрышных: {len(wins)} ({len(wins)/len(df_trades)*100:.1f}%)")
    print(f"   ❌ Убыточных: {len(losses)} ({len(losses)/len(df_trades)*100:.1f}%)")
    
    print(f"\n💰 Анализ прибыли/убытков:")
    if len(wins) > 0:
        print(f"   ✅ WIN сделки:")
        print(f"      Средний: ${wins['pnl'].mean():.2f} ({wins['pnl_pct'].mean():.1f}%)")
        print(f"      Максимум: ${wins['pnl'].max():.2f} ({wins['pnl_pct'].max():.1f}%)")
        print(f"      Минимум: ${wins['pnl'].min():.2f} ({wins['pnl_pct'].min():.1f}%)")
        print(f"      Общая прибыль: ${wins['pnl'].sum():.2f}")
    
    if len(losses) > 0:
        print(f"   ❌ LOSS сделки:")
        print(f"      Средний: ${losses['pnl'].mean():.2f} ({losses['pnl_pct'].mean():.1f}%)")
        print(f"      Максимум: ${losses['pnl'].min():.2f} ({losses['pnl_pct'].min():.1f}%)")
        print(f"      Минимум: ${losses['pnl'].max():.2f} ({losses['pnl_pct'].max():.1f}%)")
        print(f"      Общий убыток: ${losses['pnl'].sum():.2f}")
    
    print(f"\n💵 ИТОГОВЫЕ ФИНАНСЫ:")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    print(f"   Конечный баланс: ${balance:.2f}")
    print(f"   Чистый PnL: ${balance - INITIAL_BALANCE:.2f}")
    print(f"   ROI: {(balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100:.2f}%")
    
    # Топ-5 лучших
    print(f"\n\n🏆 ТОП-5 ЛУЧШИХ СДЕЛОК:")
    print("-" * 80)
    top_wins = df_trades.nlargest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_wins.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} → {trade['exit_reason']}")
        print(f"    Entry: ${trade['entry_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance после: ${trade['balance']:.2f}")
    
    # Топ-5 худших
    print(f"\n\n💔 ТОП-5 ХУДШИХ СДЕЛОК:")
    print("-" * 80)
    top_losses = df_trades.nsmallest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_losses.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} → {trade['exit_reason']}")
        print(f"    Entry: ${trade['entry_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance после: ${trade['balance']:.2f}")
    
    # График баланса
    print(f"\n\n📈 ДИНАМИКА БАЛАНСА:")
    print("-" * 80)
    
    max_balance = df_trades['balance'].max()
    min_balance = df_trades['balance'].min()
    
    print(f"Начало: ${INITIAL_BALANCE:.2f}")
    
    # Показать каждую 5-ю сделку
    step = max(1, len(df_trades) // 15)
    for i in range(0, len(df_trades), step):
        trade = df_trades.iloc[i]
        bar_length = int((trade['balance'] / INITIAL_BALANCE) * 50)
        bar = '█' * max(0, bar_length)
        emoji = "🟢" if trade['balance'] >= INITIAL_BALANCE else "🟡" if trade['balance'] >= INITIAL_BALANCE * 0.9 else "🔴"
        print(f"#{trade['trade_num']:3d} {emoji} {bar} ${trade['balance']:.2f}")
    
    # Последняя сделка
    if len(df_trades) > 0:
        last_trade = df_trades.iloc[-1]
        bar_length = int((last_trade['balance'] / INITIAL_BALANCE) * 50)
        bar = '█' * max(0, bar_length)
        emoji = "🟢" if last_trade['balance'] >= INITIAL_BALANCE else "🟡" if last_trade['balance'] >= INITIAL_BALANCE * 0.9 else "🔴"
        print(f"#{last_trade['trade_num']:3d} {emoji} {bar} ${last_trade['balance']:.2f} (ФИНАЛ)")
    
    print(f"\nМакс. баланс: ${max_balance:.2f}")
    print(f"Мин. баланс: ${min_balance:.2f}")
    
    # Анализ по монетам
    print(f"\n\n💎 СТАТИСТИКА ПО МОНЕТАМ:")
    print("-" * 80)
    
    coin_stats = df_trades.groupby('symbol').agg({
        'pnl': ['count', 'sum', 'mean'],
        'exit_reason': lambda x: (x == 'TP').sum()
    }).round(2)
    
    coin_stats.columns = ['Сделок', 'PnL', 'Avg PnL', 'TP']
    coin_stats['Win%'] = (coin_stats['TP'] / coin_stats['Сделок'] * 100).round(1)
    coin_stats = coin_stats.sort_values('PnL', ascending=False)
    
    print(f"\n{'Монета':<12} {'Сделок':>7} {'PnL':>10} {'Avg':>8} {'TP':>5} {'Win%':>6}")
    print("-" * 80)
    for symbol, row in coin_stats.head(10).iterrows():
        print(f"{symbol:<12} {int(row['Сделок']):>7} ${row['PnL']:>9.2f} ${row['Avg']:>7.2f} {int(row['TP']):>5} {row['Win%']:>5.1f}%")
    
    # Сохранить
    df_trades.to_csv('analysis/results/best_strategy_trades.csv', index=False)
    
    print("\n\n" + "=" * 80)
    print("✅ Детальные результаты: analysis/results/best_strategy_trades.csv")
    print("=" * 80)
    
    # Выводы
    print("\n\n" + "=" * 80)
    print("💡 ВЫВОДЫ")
    print("=" * 80)
    
    roi = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    
    if roi > 0:
        print(f"\n✅ СТРАТЕГИЯ ПРИБЫЛЬНАЯ!")
        print(f"   💰 Прибыль: ${balance - INITIAL_BALANCE:.2f}")
        print(f"   📈 ROI: {roi:.2f}%")
        print(f"   🎯 Win Rate: {len(wins)/len(df_trades)*100:.1f}%")
        print(f"   🎯 TP Rate: {tp_count/len(df_trades)*100:.1f}%")
        
        print(f"\n   📊 Ключевые факторы успеха:")
        print(f"   • Широкий SL ({STOP_LOSS_PCT}%) дает цене дышать")
        print(f"   • Только {sl_count/len(df_trades)*100:.1f}% сделок закрылись по SL")
        print(f"   • {tp_count} сделок достигли таргета")
        print(f"   • Плечо {LEVERAGE}x - оптимальный баланс риска/прибыли")
        print(f"   • Частичные позиции защищают от полной потери баланса")
        
        print(f"\n   🎯 Рекомендация: ПРИМЕНИТЬ ЭТУ СТРАТЕГИЮ")
        print(f"      Можно использовать для реальной торговли после")
        print(f"      дополнительного тестирования на нескольких днях")
    else:
        print(f"\n⛔ СТРАТЕГИЯ УБЫТОЧНАЯ")
        print(f"   💸 Убыток: ${INITIAL_BALANCE - balance:.2f}")
        print(f"   📉 Loss: {abs(roi):.2f}%")
        print(f"   Требуется доработка параметров")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    simulate_best_strategy()
