#!/usr/bin/env python3
"""
Simulate trading on TODAY's signals only
"""
import pandas as pd
from datetime import datetime, timedelta

# Trading parameters
STARTING_BALANCE = 1000
LEVERAGE = 50
TAKER_FEE = 0.0005
STOP_LOSS_PCT = 10

def calculate_position_size(balance):
    """All-in strategy: use full balance"""
    return balance * LEVERAGE

def calculate_sl_price(entry_price, direction):
    """Calculate SL price based on 10% position loss at 50x leverage"""
    sl_distance_pct = (STOP_LOSS_PCT / 100) / LEVERAGE
    
    if direction == 'SELL':
        return entry_price * (1 + sl_distance_pct)
    else:
        return entry_price * (1 - sl_distance_pct)

def simulate_position(signal, balance):
    """Simulate position using REAL historical outcome"""
    symbol = signal['symbol']
    direction = signal['verdict']
    entry_price = float(signal['entry_price'])
    confidence = float(signal['confidence'])
    duration_minutes = int(signal['duration_minutes']) if pd.notna(signal.get('duration_minutes')) else 30
    outcome = signal['result']
    
    # Entry timestamp
    entry_time = pd.to_datetime(signal['timestamp_sent'])
    
    # Calculate quantity and fees based on leveraged notional
    quantity = (balance * LEVERAGE) / entry_price
    entry_notional = quantity * entry_price
    entry_fee = entry_notional * TAKER_FEE
    
    # Determine exit based on REAL outcome
    tp_price = float(signal['target_min']) if pd.notna(signal.get('target_min')) and float(signal['target_min']) > 0 else entry_price * 0.98
    sl_price = calculate_sl_price(entry_price, direction)
    
    if outcome == 'WIN':
        exit_price = tp_price
        exit_reason = "Take-Profit"
    elif outcome == 'LOSS':
        exit_price = sl_price
        exit_reason = "Stop-Loss"
    else:
        exit_price = float(signal['final_price']) if pd.notna(signal.get('final_price')) else entry_price
        exit_reason = "Cancelled"
    
    # Calculate P&L with correct fees
    exit_notional = quantity * exit_price
    exit_fee = exit_notional * TAKER_FEE
    
    if direction == 'SELL':
        raw_pnl = entry_notional - exit_notional
    else:
        raw_pnl = exit_notional - entry_notional
    
    pnl_usd = raw_pnl - entry_fee - exit_fee
    new_balance = balance + pnl_usd
    
    return {
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'entry_time': entry_time,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'outcome': outcome,
        'balance_before': balance,
        'pnl_usd': pnl_usd,
        'pnl_pct': (pnl_usd / balance) * 100,
        'balance_after': new_balance,
        'duration_minutes': duration_minutes
    }

def main():
    print("=" * 100)
    print("СЕГОДНЯШНЯЯ ТОРГОВЛЯ (17 НОЯБРЯ 2025)")
    print("=" * 100)
    
    # Load effectiveness log
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    # Filter TODAY only
    today = datetime.now().date()
    df_today = df[df['timestamp_sent'].dt.date == today].copy()
    df_today = df_today[(df_today['target_min'].notna()) & (df_today['target_min'] > 0)].copy()
    
    print(f"\n📅 Дата: {today}")
    print(f"📊 Всего сигналов за сегодня: {len(df[df['timestamp_sent'].dt.date == today])}")
    print(f"📊 С валидными targets: {len(df_today)}")
    
    if len(df_today) == 0:
        print("\n⚠️  Сегодня нет сигналов с валидными targets!")
        return
    
    print(f"📅 Период: {df_today['timestamp_sent'].min().strftime('%H:%M')} → {df_today['timestamp_sent'].max().strftime('%H:%M')}")
    print(f"\n💰 Стартовый баланс: ${STARTING_BALANCE:,.2f}")
    print(f"📈 Leverage: {LEVERAGE}x")
    print(f"🎯 Стратегия: Sequential (one position at a time)")
    print("=" * 100)
    
    # Simulate sequential trading
    balance = STARTING_BALANCE
    trades = []
    position_close_time = None
    
    df_sorted = df_today.sort_values('timestamp_sent').reset_index(drop=True)
    
    for idx, signal in df_sorted.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # Skip if position still open
        if position_close_time is not None and signal_time < position_close_time:
            continue
        
        # Enter position
        result = simulate_position(signal, balance)
        balance = result['balance_after']
        
        # Update close time
        position_close_time = signal_time + timedelta(minutes=result['duration_minutes'])
        
        trades.append(result)
        
        # Print trade
        pnl_emoji = "✅" if result['pnl_usd'] > 0 else "❌"
        print(f"\n{pnl_emoji} Сделка #{len(trades)}: {result['symbol']} {result['direction']} @ {result['entry_time'].strftime('%H:%M')}")
        print(f"   Entry: ${result['entry_price']:.8f} → Exit: ${result['exit_price']:.8f}")
        print(f"   P&L: ${result['pnl_usd']:+.2f} ({result['pnl_pct']:+.2f}%)")
        print(f"   Баланс: ${result['balance_before']:.2f} → ${result['balance_after']:.2f}")
        print(f"   Результат: {result['outcome']} ({result['exit_reason']})")
        
        # Stop if balance depleted
        if balance <= 10:
            print(f"\n⚠️  Баланс упал до ${balance:.2f}, остановка симуляции")
            break
    
    # Summary
    print("\n" + "=" * 100)
    print("📊 ИТОГИ ДНЯ")
    print("=" * 100)
    
    if len(trades) == 0:
        print("Сделок не было")
        return
    
    trades_df = pd.DataFrame(trades)
    
    wins = len(trades_df[trades_df['pnl_usd'] > 0])
    losses = len(trades_df[trades_df['pnl_usd'] < 0])
    win_rate = (wins / len(trades) * 100) if len(trades) > 0 else 0
    
    total_pnl = balance - STARTING_BALANCE
    total_pnl_pct = (balance / STARTING_BALANCE - 1) * 100
    
    print(f"\n💰 Начальный баланс: ${STARTING_BALANCE:,.2f}")
    print(f"💵 Конечный баланс: ${balance:,.2f}")
    print(f"📊 Прибыль/Убыток: ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
    
    print(f"\n📈 Статистика:")
    print(f"   Всего сделок: {len(trades)}")
    print(f"   Выигрышей: {wins} ({win_rate:.1f}%)")
    print(f"   Проигрышей: {losses} ({100-win_rate:.1f}%)")
    
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
        print(f"   {outcome}: {count} ({count/len(trades)*100:.1f}%)")
    
    # Best and worst
    if len(trades_df) > 0:
        best = trades_df.loc[trades_df['pnl_usd'].idxmax()]
        worst = trades_df.loc[trades_df['pnl_usd'].idxmin()]
        
        print(f"\n🏆 Лучшая сделка: ${best['pnl_usd']:.2f}")
        print(f"   {best['symbol']} {best['direction']} @ {best['entry_time'].strftime('%H:%M')}")
        
        print(f"\n💔 Худшая сделка: ${worst['pnl_usd']:.2f}")
        print(f"   {worst['symbol']} {worst['direction']} @ {worst['entry_time'].strftime('%H:%M')}")
    
    # Save report
    trades_df.to_csv('analysis/results/today_trading_report.csv', index=False)
    print(f"\n💾 Отчёт сохранён: analysis/results/today_trading_report.csv")
    print("=" * 100)

if __name__ == '__main__':
    main()
