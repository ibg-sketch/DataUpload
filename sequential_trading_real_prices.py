"""
Sequential Trading Simulation with REAL historical prices
Two scenarios:
1. After closing, enter the OLDEST existing signal
2. After closing, enter only the FIRST NEW signal that appears
"""
import pandas as pd
from datetime import datetime, timedelta
import json

# Trading parameters (from optimized config)
LEVERAGE = 50
STOP_LOSS_PCT = 10  # 10% of position size
TP_STRATEGY = "hybrid"
STARTING_BALANCE = 1000
TAKER_FEE = 0.0005

def calculate_position_size(balance):
    """Calculate position size based on available balance"""
    return balance * LEVERAGE

def calculate_tp_price(signal, entry_price):
    """Calculate TP based on hybrid strategy"""
    direction = signal['verdict']
    target_min = float(signal['target_min'])
    target_max = float(signal['target_max'])
    
    if direction == 'SELL':
        # SELL: target_min is furthest (end of zone/aggressive)
        return target_min
    else:
        # BUY: target_min is closest (start of zone/conservative)
        return target_min

def calculate_sl_price(entry_price, direction):
    """Calculate SL price based on 10% position loss at 50x leverage"""
    # 10% position loss = 0.20% price movement
    sl_distance_pct = (STOP_LOSS_PCT / 100) / LEVERAGE
    
    if direction == 'SELL':
        return entry_price * (1 + sl_distance_pct)
    else:
        return entry_price * (1 - sl_distance_pct)

def simulate_position_outcome(signal, balance):
    """Simulate position using REAL historical outcome from effectiveness_log.csv"""
    symbol = signal['symbol']
    direction = signal['verdict']
    entry_price = float(signal['entry_price'])
    confidence = float(signal['confidence'])
    duration_minutes = int(signal['duration_minutes']) if pd.notna(signal.get('duration_minutes')) else 30
    outcome = signal['result']
    
    # Calculate position parameters
    position_size = calculate_position_size(balance)
    tp_price = float(signal['target_min']) if pd.notna(signal.get('target_min')) and float(signal['target_min']) > 0 else entry_price * 0.98
    sl_price = calculate_sl_price(entry_price, direction)
    
    # Entry timestamp
    entry_time = pd.to_datetime(signal['timestamp_sent'])
    
    # Calculate quantity and fees based on leveraged notional
    quantity = (balance * LEVERAGE) / entry_price
    entry_notional = quantity * entry_price
    entry_fee = entry_notional * TAKER_FEE
    
    # Determine exit based on REAL outcome
    if outcome == 'WIN':
        # Position hit TP
        exit_price = tp_price
        exit_reason = "Take-Profit"
    elif outcome == 'LOSS':
        # Position hit SL
        exit_price = sl_price
        exit_reason = "Stop-Loss"
    else:
        # CANCELLED - use final_price from log
        exit_price = float(signal['final_price']) if pd.notna(signal.get('final_price')) else entry_price
        exit_reason = "Signal Cancelled"
    
    # Calculate P&L with correct fees
    exit_notional = quantity * exit_price
    exit_fee = exit_notional * TAKER_FEE
    
    if direction == 'SELL':
        raw_pnl = entry_notional - exit_notional
    else:
        raw_pnl = exit_notional - entry_notional
    
    # Total P&L: raw P&L from position minus fees
    # Note: raw_pnl is already the full notional profit, fees are also from notional
    # So we DON'T divide by leverage - the margin gains/losses are the full notional changes
    pnl_usd = raw_pnl - entry_fee - exit_fee
    new_balance = balance + pnl_usd
    position_pnl_pct = (pnl_usd / balance) * 100 if balance > 0 else 0
    
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
        'position_size': position_size,
        'pnl_usd': pnl_usd,
        'pnl_pct': (new_balance / balance - 1) * 100,
        'balance_after': new_balance,
        'duration_minutes': duration_minutes
    }

def scenario_1_oldest_signal(df):
    """
    Scenario 1: After closing, enter the OLDEST existing signal
    """
    print("\n" + "="*80)
    print("SCENARIO 1: Enter OLDEST existing signal after closing")
    print("="*80)
    
    balance = STARTING_BALANCE
    trades = []
    current_position_close_time = None
    
    # Sort by timestamp_sent
    df_sorted = df.sort_values('timestamp_sent').reset_index(drop=True)
    
    for idx, signal in df_sorted.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # Skip if we're still in a position
        if current_position_close_time is not None and signal_time < current_position_close_time:
            continue
        
        # Enter position
        result = simulate_position_outcome(signal, balance)
        balance = result['balance_after']
        
        # Update close time (entry + duration)
        current_position_close_time = signal_time + timedelta(minutes=result['duration_minutes'])
        
        trades.append(result)
        
        # Stop if balance depleted
        if balance <= 10:
            print(f"⚠️  Balance depleted to ${balance:.2f}, stopping simulation")
            break
    
    return pd.DataFrame(trades), balance

def scenario_2_next_new_signal(df):
    """
    Scenario 2: After closing, enter only the FIRST NEW signal that appears
    """
    print("\n" + "="*80)
    print("SCENARIO 2: Enter only FIRST NEW signal after closing")
    print("="*80)
    
    balance = STARTING_BALANCE
    trades = []
    current_position_close_time = None
    
    # Sort by timestamp_sent
    df_sorted = df.sort_values('timestamp_sent').reset_index(drop=True)
    
    for idx, signal in df_sorted.iterrows():
        signal_time = pd.to_datetime(signal['timestamp_sent'])
        
        # If we have a position, skip all signals until it closes
        if current_position_close_time is not None:
            if signal_time < current_position_close_time:
                # Position still open, skip
                continue
            # This is the first signal after position closed - enter it!
        
        # Enter position
        result = simulate_position_outcome(signal, balance)
        balance = result['balance_after']
        
        # Update close time (entry + duration)
        current_position_close_time = signal_time + timedelta(minutes=result['duration_minutes'])
        
        trades.append(result)
        
        # Stop if balance depleted
        if balance <= 10:
            print(f"⚠️  Balance depleted to ${balance:.2f}, stopping simulation")
            break
    
    return pd.DataFrame(trades), balance

def print_summary(scenario_name, trades_df, final_balance):
    """Print detailed summary for a scenario"""
    print("\n" + "="*80)
    print(f"📈 RESULTS: {scenario_name}")
    print("="*80)
    
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df['pnl_usd'] > 0])
    losses = len(trades_df[trades_df['pnl_usd'] < 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = final_balance - STARTING_BALANCE
    total_pnl_pct = (final_balance / STARTING_BALANCE - 1) * 100
    
    avg_win = trades_df[trades_df['pnl_usd'] > 0]['pnl_usd'].mean() if wins > 0 else 0
    avg_loss = trades_df[trades_df['pnl_usd'] < 0]['pnl_usd'].mean() if losses > 0 else 0
    
    print(f"\n💰 Starting Balance: ${STARTING_BALANCE:.2f}")
    print(f"💵 Final Balance: ${final_balance:.2f}")
    print(f"📊 Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
    
    print(f"\n📈 Trading Statistics:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate:.1f}%)")
    print(f"   Losses: {losses} ({100-win_rate:.1f}%)")
    
    if wins > 0 and losses > 0:
        print(f"   Average Win: ${avg_win:.2f}")
        print(f"   Average Loss: ${avg_loss:.2f}")
        profit_factor = abs(avg_win * wins / (avg_loss * losses)) if avg_loss != 0 else float('inf')
        print(f"   Profit Factor: {profit_factor:.2f}")
    
    # Outcome distribution
    print(f"\n🎯 Outcome Distribution:")
    outcome_counts = trades_df['outcome'].value_counts()
    for outcome, count in outcome_counts.items():
        print(f"   {outcome}: {count} ({count/total_trades*100:.1f}%)")
    
    # Exit reasons
    print(f"\n🚪 Exit Distribution:")
    exit_counts = trades_df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        print(f"   {reason}: {count} ({count/total_trades*100:.1f}%)")
    
    # Best and worst trades
    if len(trades_df) > 0:
        print(f"\n🏆 Best Trade: ${trades_df['pnl_usd'].max():.2f}")
        best_trade = trades_df.loc[trades_df['pnl_usd'].idxmax()]
        print(f"   {best_trade['symbol']} {best_trade['direction']} @ {best_trade['entry_time'].strftime('%Y-%m-%d %H:%M')}")
        
        print(f"\n💔 Worst Trade: ${trades_df['pnl_usd'].min():.2f}")
        worst_trade = trades_df.loc[trades_df['pnl_usd'].idxmin()]
        print(f"   {worst_trade['symbol']} {worst_trade['direction']} @ {worst_trade['entry_time'].strftime('%Y-%m-%d %H:%M')}")
    
    print("\n" + "="*80)

def main():
    print("="*80)
    print("SEQUENTIAL TRADING SIMULATION WITH REAL HISTORICAL PRICES")
    print("="*80)
    print(f"Starting Balance: ${STARTING_BALANCE:.2f}")
    print(f"Strategy: One position at a time, all available funds")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Stop-Loss: {STOP_LOSS_PCT}% of position (0.20% price at {LEVERAGE}x)")
    print(f"Take-Profit: Hybrid strategy (BUY=conservative, SELL=aggressive)")
    print(f"Data Source: effectiveness_log.csv (REAL historical outcomes)")
    print("="*80)
    
    # Load effectiveness log (real historical data)
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    # Filter last 7 days and valid targets
    seven_days_ago = datetime.now() - timedelta(days=7)
    df = df[df['timestamp_sent'] >= seven_days_ago].copy()
    df = df[df['target_min'] > 0].copy()  # Only signals with valid targets
    
    print(f"\n📊 Loaded {len(df)} signals from last 7 days (with valid targets)")
    print(f"📅 Period: {df['timestamp_sent'].min().strftime('%Y-%m-%d %H:%M')} → {df['timestamp_sent'].max().strftime('%Y-%m-%d %H:%M')}")
    
    # Run both scenarios
    trades_s1, balance_s1 = scenario_1_oldest_signal(df.copy())
    trades_s2, balance_s2 = scenario_2_next_new_signal(df.copy())
    
    # Print summaries
    print_summary("SCENARIO 1 (Oldest Existing Signal)", trades_s1, balance_s1)
    print_summary("SCENARIO 2 (Next New Signal Only)", trades_s2, balance_s2)
    
    # Comparison
    print("\n" + "="*80)
    print("🔄 SCENARIO COMPARISON")
    print("="*80)
    print(f"\nScenario 1 (Oldest Signal):")
    print(f"   Trades: {len(trades_s1)}")
    print(f"   Final Balance: ${balance_s1:.2f}")
    print(f"   ROI: {(balance_s1/STARTING_BALANCE - 1)*100:+.2f}%")
    
    print(f"\nScenario 2 (Next New Signal):")
    print(f"   Trades: {len(trades_s2)}")
    print(f"   Final Balance: ${balance_s2:.2f}")
    print(f"   ROI: {(balance_s2/STARTING_BALANCE - 1)*100:+.2f}%")
    
    diff = balance_s1 - balance_s2
    print(f"\n{'📈' if diff > 0 else '📉'} Difference:")
    print(f"   ${diff:+.2f} ({(diff/balance_s2)*100:+.2f}%)")
    print(f"   Better Strategy: {'Scenario 1 (Oldest)' if diff > 0 else 'Scenario 2 (Next New)'}")
    
    # Save reports
    trades_s1.to_csv('analysis/results/scenario1_oldest_signal.csv', index=False)
    trades_s2.to_csv('analysis/results/scenario2_next_new_signal.csv', index=False)
    
    print(f"\n💾 Reports saved:")
    print(f"   - analysis/results/scenario1_oldest_signal.csv")
    print(f"   - analysis/results/scenario2_next_new_signal.csv")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
