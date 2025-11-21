#!/usr/bin/env python3
"""
Fixed position size simulation: $50 per position, $1000 deposit
"""
import pandas as pd
from datetime import datetime, timedelta

# Trading parameters
DEPOSIT = 1000
POSITION_SIZE = 50  # Fixed $50 per position
MAX_POSITIONS = DEPOSIT // POSITION_SIZE  # 20 positions max
LEVERAGE = 50
TAKER_FEE = 0.0005
STOP_LOSS_PCT = 10

def calculate_sl_price(entry_price, direction):
    """Calculate SL price based on 10% position loss at 50x leverage"""
    sl_distance_pct = (STOP_LOSS_PCT / 100) / LEVERAGE
    
    if direction == 'SELL':
        return entry_price * (1 + sl_distance_pct)
    else:
        return entry_price * (1 - sl_distance_pct)

def simulate_position(signal, position_size):
    """Simulate position with fixed size"""
    symbol = signal['symbol']
    direction = signal['verdict']
    entry_price = float(signal['entry_price'])
    outcome = signal['result']
    
    entry_time = pd.to_datetime(signal['timestamp_sent'])
    duration_minutes = int(signal['duration_minutes']) if pd.notna(signal.get('duration_minutes')) else 30
    
    # Calculate quantity and fees
    quantity = (position_size * LEVERAGE) / entry_price
    entry_notional = quantity * entry_price
    entry_fee = entry_notional * TAKER_FEE
    
    # Determine exit
    tp_price = float(signal['target_min']) if pd.notna(signal.get('target_min')) and float(signal['target_min']) > 0 else entry_price * 0.98
    sl_price = calculate_sl_price(entry_price, direction)
    
    if outcome == 'WIN':
        exit_price = tp_price
        exit_reason = "TP"
    elif outcome == 'LOSS':
        exit_price = sl_price
        exit_reason = "SL"
    else:
        exit_price = float(signal['final_price']) if pd.notna(signal.get('final_price')) else entry_price
        exit_reason = "CANCELLED"
    
    # Calculate P&L
    exit_notional = quantity * exit_price
    exit_fee = exit_notional * TAKER_FEE
    
    if direction == 'SELL':
        raw_pnl = entry_notional - exit_notional
    else:
        raw_pnl = exit_notional - entry_notional
    
    pnl_usd = raw_pnl - entry_fee - exit_fee
    
    return {
        'symbol': symbol,
        'direction': direction,
        'entry_time': entry_time,
        'close_time': entry_time + timedelta(minutes=duration_minutes),
        'entry_price': entry_price,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'outcome': outcome,
        'position_size': position_size,
        'pnl_usd': pnl_usd,
        'pnl_pct': (pnl_usd / position_size) * 100,
        'duration_minutes': duration_minutes
    }

def main():
    print("=" * 100)
    print("ФИКСИРОВАННАЯ ПОЗИЦИЯ: $50 | ДЕПОЗИТ: $1000 | МАКСИМУМ: 20 ПОЗИЦИЙ")
    print("=" * 100)
    
    # Load today's signals
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    today = datetime.now().date()
    df_today = df[df['timestamp_sent'].dt.date == today].copy()
    df_today = df_today[(df_today['target_min'].notna()) & (df_today['target_min'] > 0)].copy()
    df_today = df_today.sort_values('timestamp_sent').reset_index(drop=True)
    
    print(f"\n📅 Дата: {today}")
    print(f"📊 Сигналов с валидными targets: {len(df_today)}")
    print(f"💰 Депозит: ${DEPOSIT:,.2f}")
    print(f"📏 Размер позиции: ${POSITION_SIZE:,.2f} (фиксированный)")
    print(f"📊 Максимум позиций: {MAX_POSITIONS}")
    print(f"📈 Leverage: {LEVERAGE}x")
    print("=" * 100)
    
    # Track active positions
    active_positions = []  # List of (close_time, trade_data)
    completed_trades = []
    skipped_signals = 0
    free_capital = DEPOSIT
    
    for idx, signal in df_today.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # Close expired positions
        still_active = []
        for close_time, trade in active_positions:
            if signal_time >= close_time:
                # Position closed
                completed_trades.append(trade)
                free_capital += POSITION_SIZE
            else:
                still_active.append((close_time, trade))
        active_positions = still_active
        
        # Check if we can open new position
        if free_capital < POSITION_SIZE:
            skipped_signals += 1
            continue
        
        # Open new position
        trade = simulate_position(signal, POSITION_SIZE)
        active_positions.append((trade['close_time'], trade))
        free_capital -= POSITION_SIZE
        
        # Print status every 10 trades
        if len(completed_trades) > 0 and len(completed_trades) % 10 == 0:
            total_pnl = sum(t['pnl_usd'] for t in completed_trades)
            print(f"⏳ {len(completed_trades)} завершено, {len(active_positions)} активных, капитал: ${free_capital + len(active_positions)*POSITION_SIZE:.2f}, P&L: ${total_pnl:+.2f}")
    
    # Close remaining active positions
    for close_time, trade in active_positions:
        completed_trades.append(trade)
    
    # Results
    print("\n" + "=" * 100)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 100)
    
    trades_df = pd.DataFrame(completed_trades)
    
    total_pnl = trades_df['pnl_usd'].sum()
    final_balance = DEPOSIT + total_pnl
    
    wins = len(trades_df[trades_df['pnl_usd'] > 0])
    losses = len(trades_df[trades_df['pnl_usd'] < 0])
    win_rate = (wins / len(trades_df) * 100) if len(trades_df) > 0 else 0
    
    print(f"\n💰 Начальный депозит: ${DEPOSIT:,.2f}")
    print(f"💵 Конечный баланс: ${final_balance:,.2f}")
    print(f"📊 Прибыль/Убыток: ${total_pnl:+,.2f} ({(total_pnl/DEPOSIT)*100:+.2f}%)")
    
    print(f"\n📈 Статистика:")
    print(f"   Всего сделок: {len(trades_df)}")
    print(f"   Выигрышей: {wins} ({win_rate:.1f}%)")
    print(f"   Проигрышей: {losses} ({100-win_rate:.1f}%)")
    print(f"   Пропущено сигналов: {skipped_signals} (нет свободного капитала)")
    
    if wins > 0:
        avg_win = trades_df[trades_df['pnl_usd'] > 0]['pnl_usd'].mean()
        avg_win_pct = trades_df[trades_df['pnl_usd'] > 0]['pnl_pct'].mean()
        print(f"   Средний WIN: ${avg_win:.2f} ({avg_win_pct:+.2f}%)")
    
    if losses > 0:
        avg_loss = trades_df[trades_df['pnl_usd'] < 0]['pnl_usd'].mean()
        avg_loss_pct = trades_df[trades_df['pnl_usd'] < 0]['pnl_pct'].mean()
        print(f"   Средний LOSS: ${avg_loss:.2f} ({avg_loss_pct:+.2f}%)")
    
    print(f"\n🎯 Распределение результатов:")
    outcome_counts = trades_df['outcome'].value_counts()
    for outcome, count in outcome_counts.items():
        print(f"   {outcome}: {count} ({count/len(trades_df)*100:.1f}%)")
    
    # Best and worst
    if len(trades_df) > 0:
        best = trades_df.loc[trades_df['pnl_usd'].idxmax()]
        worst = trades_df.loc[trades_df['pnl_usd'].idxmin()]
        
        print(f"\n🏆 Лучшая сделка: ${best['pnl_usd']:.2f} ({best['pnl_pct']:+.2f}%)")
        print(f"   {best['symbol']} {best['direction']} @ {best['entry_time'].strftime('%H:%M')}")
        
        print(f"\n💔 Худшая сделка: ${worst['pnl_usd']:.2f} ({worst['pnl_pct']:+.2f}%)")
        print(f"   {worst['symbol']} {worst['direction']} @ {worst['entry_time'].strftime('%H:%M')}")
    
    # Peak concurrent positions
    max_concurrent = 0
    events = []
    for trade in completed_trades:
        events.append((trade['entry_time'], 'open'))
        events.append((trade['close_time'], 'close'))
    events.sort()
    
    current = 0
    for event_time, event_type in events:
        if event_type == 'open':
            current += 1
            max_concurrent = max(max_concurrent, current)
        else:
            current -= 1
    
    print(f"\n📊 Использование капитала:")
    print(f"   Максимум позиций одновременно: {max_concurrent} из {MAX_POSITIONS}")
    print(f"   Задействовано капитала (пик): ${max_concurrent * POSITION_SIZE:,.2f} ({(max_concurrent/MAX_POSITIONS)*100:.1f}%)")
    
    # Save report
    trades_df.to_csv('analysis/results/fixed_position_report.csv', index=False)
    print(f"\n💾 Отчёт сохранён: analysis/results/fixed_position_report.csv")
    print("=" * 100)

if __name__ == '__main__':
    main()
