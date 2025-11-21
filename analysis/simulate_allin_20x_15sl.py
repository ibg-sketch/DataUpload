#!/usr/bin/env python3
"""
Симуляция All-In стратегии с параметрами лучшей Partial стратегии
All-In: 20x leverage, SL 15%, target_min
"""

import pandas as pd
from datetime import datetime, timedelta

# Параметры
LEVERAGE = 20
STOP_LOSS_PCT = 15  # 15% от позиции = 0.75% движения цены
INITIAL_BALANCE = 1000.0

# Комиссии BingX
ENTRY_FEE = 0.0005
TP_FEE_MAKER = 0.0002
SL_FEE = 0.0005

def calculate_pnl(entry_price, exit_price, side, leverage, position_size, is_tp=True):
    """Рассчитать PnL с комиссиями"""
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

def simulate_allin():
    """Симуляция All-In стратегии"""
    
    print("=" * 80)
    print("СИМУЛЯЦИЯ ALL-IN СТРАТЕГИИ")
    print("=" * 80)
    
    print(f"\n📊 ПАРАМЕТРЫ:")
    print(f"   Режим: All-In (весь баланс в одну позицию)")
    print(f"   Плечо: {LEVERAGE}x")
    print(f"   Stop-Loss: {STOP_LOSS_PCT}% от позиции ({STOP_LOSS_PCT/LEVERAGE:.3f}% движения цены)")
    print(f"   Take-Profit: target_min (ближайший таргет)")
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
    position_open = False
    last_close_time = None
    
    print("\n" + "=" * 80)
    print("ТОРГОВЛЯ")
    print("=" * 80)
    
    for idx, signal in df.iterrows():
        if position_open:
            position_open = False
            continue
        
        signal_time = signal['timestamp_sent']
        if last_close_time and signal_time <= last_close_time:
            continue
        
        target = signal['target_min']
        
        if target <= 0:
            continue
        
        position_size = balance
        
        # Определить выход
        exit_price, exit_reason, is_tp = check_exit(signal, target, LEVERAGE, STOP_LOSS_PCT)
        
        # Рассчитать PnL
        pnl, pnl_pct = calculate_pnl(
            signal['entry_price'], exit_price, signal['verdict'],
            LEVERAGE, position_size, is_tp
        )
        
        balance += pnl
        
        # Вывод сделки
        profit_emoji = "✅" if pnl > 0 else "❌"
        exit_emoji = {"TP": "🎯", "SL": "🛑", "TTL": "⏱️"}[exit_reason]
        
        print(f"\n{profit_emoji} Сделка #{len(trades)+1} | {signal['symbol']} {signal['verdict']} | {exit_emoji} {exit_reason}")
        print(f"   Позиция: ${position_size:.2f} | Вход: ${signal['entry_price']:.4f} → Выход: ${exit_price:.4f}")
        print(f"   PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | Баланс: ${balance:.2f}")
        
        if balance <= 0:
            balance = 0
            trades.append({
                'trade_num': len(trades) + 1,
                'timestamp': signal_time,
                'symbol': signal['symbol'],
                'side': signal['verdict'],
                'position_size': position_size,
                'entry_price': signal['entry_price'],
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'balance': balance
            })
            print(f"\n⛔ БАЛАНС ОБНУЛЕН!")
            break
        
        trades.append({
            'trade_num': len(trades) + 1,
            'timestamp': signal_time,
            'symbol': signal['symbol'],
            'side': signal['verdict'],
            'position_size': position_size,
            'entry_price': signal['entry_price'],
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'balance': balance
        })
        
        duration = signal.get('duration_minutes', 30)
        last_close_time = signal_time + timedelta(minutes=duration)
        position_open = True
    
    df_trades = pd.DataFrame(trades)
    
    # Результаты
    print("\n\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 80)
    
    print(f"\n📈 Статистика сделок:")
    print(f"   Всего сделок: {len(df_trades)}")
    
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
        print(f"      Общая прибыль: ${wins['pnl'].sum():.2f}")
    
    if len(losses) > 0:
        print(f"   ❌ LOSS сделки:")
        print(f"      Средний: ${losses['pnl'].mean():.2f} ({losses['pnl_pct'].mean():.1f}%)")
        print(f"      Максимум: ${losses['pnl'].min():.2f} ({losses['pnl_pct'].min():.1f}%)")
        print(f"      Общий убыток: ${losses['pnl'].sum():.2f}")
    
    print(f"\n💵 ИТОГОВЫЕ ФИНАНСЫ:")
    print(f"   Начальный баланс: ${INITIAL_BALANCE:.2f}")
    print(f"   Конечный баланс: ${balance:.2f}")
    print(f"   Чистый PnL: ${balance - INITIAL_BALANCE:.2f}")
    print(f"   ROI: {(balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100:.2f}%")
    
    # Топ сделки
    print(f"\n\n🏆 ТОП-5 ЛУЧШИХ СДЕЛОК:")
    print("-" * 80)
    top_wins = df_trades.nlargest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_wins.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} → {trade['exit_reason']}")
        print(f"    Entry: ${trade['entry_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    Position: ${trade['position_size']:.2f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance после: ${trade['balance']:.2f}")
    
    print(f"\n\n💔 ТОП-5 ХУДШИХ СДЕЛОК:")
    print("-" * 80)
    top_losses = df_trades.nsmallest(5, 'pnl')
    for i, (idx, trade) in enumerate(top_losses.iterrows(), 1):
        print(f"\n#{i} {trade['symbol']} {trade['side']} → {trade['exit_reason']}")
        print(f"    Entry: ${trade['exit_price']:.4f} → Exit: ${trade['exit_price']:.4f}")
        print(f"    Position: ${trade['position_size']:.2f}")
        print(f"    PnL: ${trade['pnl']:.2f} ({trade['pnl_pct']:.1f}%)")
        print(f"    Balance после: ${trade['balance']:.2f}")
    
    # График баланса
    print(f"\n\n📈 ДИНАМИКА БАЛАНСА:")
    print("-" * 80)
    
    max_balance = df_trades['balance'].max()
    min_balance = df_trades['balance'].min()
    
    # Показать каждую сделку или каждую 2-ю
    step = 1 if len(df_trades) <= 30 else 2
    for i in range(0, len(df_trades), step):
        trade = df_trades.iloc[i]
        bar_length = int((trade['balance'] / INITIAL_BALANCE) * 50)
        bar = '█' * max(0, bar_length)
        emoji = "🟢" if trade['balance'] >= INITIAL_BALANCE else "🔴"
        print(f"#{trade['trade_num']:3d} {emoji} {bar} ${trade['balance']:.2f}")
    
    # Последняя
    if len(df_trades) > 0:
        last = df_trades.iloc[-1]
        bar_length = int((last['balance'] / INITIAL_BALANCE) * 50)
        bar = '█' * max(0, bar_length)
        emoji = "🟢" if last['balance'] >= INITIAL_BALANCE else "🔴"
        print(f"#{last['trade_num']:3d} {emoji} {bar} ${last['balance']:.2f} (ФИНАЛ)")
    
    print(f"\nМакс. баланс: ${max_balance:.2f} (+{(max_balance-INITIAL_BALANCE)/INITIAL_BALANCE*100:.1f}%)")
    print(f"Мин. баланс: ${min_balance:.2f} ({(min_balance-INITIAL_BALANCE)/INITIAL_BALANCE*100:.1f}%)")
    
    # Сравнение с Partial
    print("\n\n" + "=" * 80)
    print("📊 СРАВНЕНИЕ: ALL-IN vs PARTIAL")
    print("=" * 80)
    
    partial_roi = 39.33  # Из предыдущей симуляции
    partial_trades = 72
    partial_wr = 66.0
    
    allin_roi = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    allin_wr = len(wins) / len(df_trades) * 100 if len(df_trades) > 0 else 0
    
    print(f"\n{'Метрика':<25} {'All-In':<20} {'Partial':<20} {'Разница'}")
    print("-" * 80)
    print(f"{'ROI':<25} {allin_roi:<19.2f}% {partial_roi:<19.2f}% {allin_roi-partial_roi:+.2f}%")
    print(f"{'Конечный баланс':<25} ${balance:<19.2f} ${INITIAL_BALANCE+partial_roi*10:<19.2f} ${balance-(INITIAL_BALANCE+partial_roi*10):.2f}")
    print(f"{'Win Rate':<25} {allin_wr:<19.1f}% {partial_wr:<19.1f}% {allin_wr-partial_wr:+.1f}%")
    print(f"{'Сделок':<25} {len(df_trades):<20} {partial_trades:<20} {len(df_trades)-partial_trades}")
    print(f"{'TP Rate':<25} {tp_count/len(df_trades)*100:<19.1f}% {'~75':<19} ")
    print(f"{'SL Rate':<25} {sl_count/len(df_trades)*100:<19.1f}% {'~8':<19} ")
    
    # Выводы
    print("\n\n" + "=" * 80)
    print("💡 ВЫВОДЫ")
    print("=" * 80)
    
    roi = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    
    if roi > partial_roi:
        diff = roi - partial_roi
        print(f"\n✅ ALL-IN ЛУЧШЕ НА {diff:.2f}%!")
        print(f"   💰 ROI: {roi:.2f}% vs {partial_roi:.2f}%")
        print(f"   🎯 Конечный баланс: ${balance:.2f} vs ${INITIAL_BALANCE+partial_roi*10:.2f}")
        
        print(f"\n   📊 Причины:")
        print(f"   • Compound эффект: прибыль реинвестируется полностью")
        print(f"   • {tp_count/len(df_trades)*100:.1f}% сделок достигли TP")
        print(f"   • Широкий SL (15%) защищает от преждевременного выхода")
        
        print(f"\n   ⚠️ Риски All-In:")
        print(f"   • Одна серия убытков может уничтожить баланс")
        print(f"   • Меньше сделок ({len(df_trades)} vs {partial_trades})")
        print(f"   • Высокая волатильность баланса")
        
    else:
        diff = partial_roi - roi
        print(f"\n⚖️ PARTIAL ЛУЧШЕ НА {diff:.2f}%")
        print(f"   💰 ROI: {partial_roi:.2f}% vs {roi:.2f}%")
        print(f"   🎯 Конечный баланс: ${INITIAL_BALANCE+partial_roi*10:.2f} vs ${balance:.2f}")
        
        print(f"\n   📊 Причины:")
        print(f"   • Больше сделок ({partial_trades} vs {len(df_trades)})")
        print(f"   • Меньше риска (фиксированные позиции)")
        print(f"   • Стабильнее (диверсификация)")
    
    print("\n" + "=" * 80)
    
    # Сохранить
    df_trades.to_csv('analysis/results/allin_20x_15sl_trades.csv', index=False)
    print("✅ Результаты: analysis/results/allin_20x_15sl_trades.csv")
    print("=" * 80)

if __name__ == '__main__':
    simulate_allin()
