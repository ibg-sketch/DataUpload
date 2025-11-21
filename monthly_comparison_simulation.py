#!/usr/bin/env python3
"""
Compare two strategies over 11 days of historical data:
1. Fixed $50 positions (current strategy)
2. All-in $1000 sequential (aggressive)
"""
import pandas as pd
from datetime import datetime, timedelta

# Trading parameters
DEPOSIT = 1000
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
    """Simulate position with given size"""
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

def strategy_fixed_50(df):
    """Strategy 1: Fixed $50 positions with parallel trading"""
    POSITION_SIZE = 50
    MAX_POSITIONS = DEPOSIT // POSITION_SIZE
    
    active_positions = []
    completed_trades = []
    skipped_signals = 0
    free_capital = DEPOSIT
    
    for idx, signal in df.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # Close expired positions
        still_active = []
        for close_time, trade in active_positions:
            if signal_time >= close_time:
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
    
    # Close remaining active positions
    for close_time, trade in active_positions:
        completed_trades.append(trade)
    
    return pd.DataFrame(completed_trades), skipped_signals

def strategy_all_in_sequential(df):
    """Strategy 2: All-in $1000 sequential trading"""
    balance = DEPOSIT
    trades = []
    position_close_time = None
    
    for idx, signal in df.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # Skip if position still open
        if position_close_time is not None and signal_time < position_close_time:
            continue
        
        # Enter position with full balance
        trade = simulate_position(signal, balance)
        balance = balance + trade['pnl_usd']
        
        # Update close time
        position_close_time = signal_time + timedelta(minutes=trade['duration_minutes'])
        
        trades.append(trade)
        
        # Stop if balance depleted
        if balance <= 10:
            break
    
    return pd.DataFrame(trades), balance

def print_strategy_results(name, trades_df, final_balance, skipped=0):
    """Print results for a strategy"""
    print("\n" + "=" * 100)
    print(f"📊 {name}")
    print("=" * 100)
    
    if len(trades_df) == 0:
        print("Нет сделок")
        return
    
    total_pnl = trades_df['pnl_usd'].sum()
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
    
    if skipped > 0:
        print(f"   Пропущено сигналов: {skipped}")
    
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
        pct = (count / len(trades_df)) * 100
        print(f"   {outcome}: {count} ({pct:.1f}%)")
    
    # Best and worst
    best = trades_df.loc[trades_df['pnl_usd'].idxmax()]
    worst = trades_df.loc[trades_df['pnl_usd'].idxmin()]
    
    print(f"\n🏆 Лучшая сделка: ${best['pnl_usd']:.2f} ({best['pnl_pct']:+.2f}%)")
    print(f"   {best['symbol']} {best['direction']} @ {best['entry_time'].strftime('%Y-%m-%d %H:%M')}")
    
    print(f"\n💔 Худшая сделка: ${worst['pnl_usd']:.2f} ({worst['pnl_pct']:+.2f}%)")
    print(f"   {worst['symbol']} {worst['direction']} @ {worst['entry_time'].strftime('%Y-%m-%d %H:%M')}")

def main():
    print("=" * 100)
    print("СРАВНЕНИЕ СТРАТЕГИЙ ЗА 11 ДНЕЙ (2025-11-05 → 2025-11-17)")
    print("=" * 100)
    
    # Load historical data
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    # Filter valid signals
    df = df[(df['target_min'].notna()) & (df['target_min'] > 0)].copy()
    df = df.sort_values('timestamp_sent').reset_index(drop=True)
    
    print(f"\n📊 Всего сигналов с валидными targets: {len(df)}")
    print(f"📅 Период: {df['timestamp_sent'].min().strftime('%Y-%m-%d')} → {df['timestamp_sent'].max().strftime('%Y-%m-%d')}")
    print(f"📈 Leverage: {LEVERAGE}x")
    print(f"💰 Депозит: ${DEPOSIT:,.2f}")
    
    # Strategy 1: Fixed $50
    print("\n🔄 Запуск стратегии 1: Fixed $50 positions...")
    trades_s1, skipped_s1 = strategy_fixed_50(df)
    final_balance_s1 = DEPOSIT + trades_s1['pnl_usd'].sum()
    
    # Strategy 2: All-in sequential
    print("🔄 Запуск стратегии 2: All-in $1000 sequential...")
    trades_s2, final_balance_s2 = strategy_all_in_sequential(df)
    
    # Print results
    print_strategy_results("СТРАТЕГИЯ 1: Fixed $50 Positions (Параллельно)", trades_s1, final_balance_s1, skipped_s1)
    print_strategy_results("СТРАТЕГИЯ 2: All-in $1000 Sequential (Последовательно)", trades_s2, final_balance_s2)
    
    # Comparison
    print("\n" + "=" * 100)
    print("🔄 СРАВНЕНИЕ СТРАТЕГИЙ")
    print("=" * 100)
    
    roi_s1 = ((final_balance_s1 - DEPOSIT) / DEPOSIT) * 100
    roi_s2 = ((final_balance_s2 - DEPOSIT) / DEPOSIT) * 100
    
    print(f"\nСтратегия 1 (Fixed $50):")
    print(f"   Сделок: {len(trades_s1)}")
    print(f"   Конечный баланс: ${final_balance_s1:,.2f}")
    print(f"   ROI: {roi_s1:+.2f}%")
    
    print(f"\nСтратегия 2 (All-in Sequential):")
    print(f"   Сделок: {len(trades_s2)}")
    print(f"   Конечный баланс: ${final_balance_s2:,.2f}")
    print(f"   ROI: {roi_s2:+.2f}%")
    
    if roi_s1 > roi_s2:
        print(f"\n✅ Победитель: Стратегия 1 (Fixed $50)")
        print(f"   Превосходство: {roi_s1 - roi_s2:+.2f}% ROI")
    else:
        print(f"\n✅ Победитель: Стратегия 2 (All-in Sequential)")
        print(f"   Превосходство: {roi_s2 - roi_s1:+.2f}% ROI")
    
    # Extrapolate to 30 days
    days_covered = (df['timestamp_sent'].max() - df['timestamp_sent'].min()).days
    multiplier = 30 / days_covered if days_covered > 0 else 1
    
    print(f"\n📅 ЭКСТРАПОЛЯЦИЯ НА 30 ДНЕЙ:")
    print(f"   (Период данных: {days_covered} дней, множитель: {multiplier:.2f}x)")
    
    # Extrapolate using compound growth
    roi_30d_s1 = ((1 + roi_s1/100) ** multiplier - 1) * 100
    roi_30d_s2 = ((1 + roi_s2/100) ** multiplier - 1) * 100
    
    balance_30d_s1 = DEPOSIT * (1 + roi_30d_s1/100)
    balance_30d_s2 = DEPOSIT * (1 + roi_30d_s2/100)
    
    print(f"\nСтратегия 1 (30 дней):")
    print(f"   Прогноз баланса: ${balance_30d_s1:,.2f}")
    print(f"   Прогноз ROI: {roi_30d_s1:+.2f}%")
    
    print(f"\nСтратегия 2 (30 дней):")
    print(f"   Прогноз баланса: ${balance_30d_s2:,.2f}")
    print(f"   Прогноз ROI: {roi_30d_s2:+.2f}%")
    
    # Save reports
    trades_s1.to_csv('analysis/results/strategy1_fixed50_11days.csv', index=False)
    trades_s2.to_csv('analysis/results/strategy2_allin_11days.csv', index=False)
    
    print(f"\n💾 Отчёты сохранены:")
    print(f"   - analysis/results/strategy1_fixed50_11days.csv")
    print(f"   - analysis/results/strategy2_allin_11days.csv")
    print("=" * 100)

if __name__ == '__main__':
    main()
