#!/usr/bin/env python3
"""
All-In Trading Simulation - Last 3 Hours
Simulates all-in trading for signals from last 3 hours (13:22-16:22 UTC)
Uses realistic strategy: after position close, only trade NEW signals
BingX fees: Entry 0.05% (taker), TP 0.02% (maker), SL/TTL 0.05% (taker)
"""

import pandas as pd
from datetime import datetime, timedelta

# Configuration
INITIAL_BALANCE = 1000.0
LEVERAGE = 50
STOP_LOSS_PCT = 10
TP_STRATEGY = "hybrid"

# BingX Fees
ENTRY_FEE_RATE = 0.0005
EXIT_FEE_TP = 0.0002
EXIT_FEE_SL_TTL = 0.0005

def calculate_pnl(entry_price, exit_price, position_size, direction, leverage, exit_reason):
    notional = position_size * leverage
    
    if direction == "BUY":
        price_change_pct = (exit_price - entry_price) / entry_price
    else:
        price_change_pct = (entry_price - exit_price) / entry_price
    
    gross_pnl = notional * price_change_pct
    entry_fee = notional * ENTRY_FEE_RATE
    exit_fee = notional * (EXIT_FEE_TP if exit_reason == "TP" else EXIT_FEE_SL_TTL)
    total_fees = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fees
    
    return net_pnl, total_fees, entry_fee, exit_fee

def simulate_position(signal, balance):
    entry_price = signal['entry_price']
    direction = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    target_min = signal['target_min']
    target_max = signal['target_max']
    duration_minutes = signal['duration_minutes'] if signal['duration_minutes'] > 0 else 30
    
    position_size = balance
    notional = position_size * LEVERAGE
    
    sl_amount = position_size * (STOP_LOSS_PCT / 100)
    if direction == "BUY":
        sl_price = entry_price * (1 - (sl_amount / notional))
    else:
        sl_price = entry_price * (1 + (sl_amount / notional))
    
    tp_price = None
    if TP_STRATEGY == "hybrid":
        if direction == "BUY" and target_min > 0:
            tp_price = target_min
        elif direction == "SELL" and target_max > 0:
            tp_price = target_max
    
    exit_price = None
    exit_reason = None
    exit_minutes = duration_minutes
    
    if direction == "BUY":
        if lowest <= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2
        elif tp_price and highest >= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
    else:
        if highest >= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2
        elif tp_price and lowest <= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
    
    pnl, total_fees, entry_fee, exit_fee = calculate_pnl(
        entry_price, exit_price, position_size, direction, LEVERAGE, exit_reason
    )
    
    return {
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'exit_minutes': exit_minutes,
        'pnl': pnl,
        'total_fees': total_fees,
        'entry_fee': entry_fee,
        'exit_fee': exit_fee,
        'position_size': position_size,
        'notional': notional,
        'sl_price': sl_price,
        'tp_price': tp_price
    }

def main():
    # Load signals
    df = pd.read_csv('effectiveness_log.csv')
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    
    # Get current time from last signal
    last_signal_time = df['timestamp_sent'].max()
    three_hours_ago = last_signal_time - timedelta(hours=3)
    
    # Filter for last 3 hours
    recent_signals = df[df['timestamp_sent'] >= three_hours_ago].copy()
    recent_signals = recent_signals.sort_values('timestamp_sent').reset_index(drop=True)
    
    print(f"=== ALL-IN SIMULATION - LAST 3 HOURS ===")
    print(f"Period: {three_hours_ago.strftime('%H:%M')} - {last_signal_time.strftime('%H:%M')} UTC")
    print(f"Total signals: {len(recent_signals)}")
    print(f"Initial balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Leverage: {LEVERAGE}x | SL: {STOP_LOSS_PCT}% | TP: {TP_STRATEGY}")
    print(f"BingX Fees: Entry 0.05%, TP 0.02%, SL/TTL 0.05%")
    print()
    
    balance = INITIAL_BALANCE
    last_position_close_time = None
    trades = []
    skipped_old = 0
    
    for idx, signal in recent_signals.iterrows():
        signal_timestamp = signal['timestamp_sent']
        
        # Skip old signals (before last position close)
        if last_position_close_time and signal_timestamp <= last_position_close_time:
            skipped_old += 1
            continue
        
        # Open position
        result = simulate_position(signal, balance)
        position_close_time = signal_timestamp + timedelta(minutes=result['exit_minutes'])
        new_balance = balance + result['pnl']
        
        trade = {
            'trade_num': len(trades) + 1,
            'timestamp': signal_timestamp,
            'symbol': signal['symbol'],
            'direction': signal['verdict'],
            'confidence': signal['confidence'],
            'entry_price': signal['entry_price'],
            'exit_price': result['exit_price'],
            'exit_reason': result['exit_reason'],
            'exit_minutes': result['exit_minutes'],
            'close_time': position_close_time,
            'pnl': result['pnl'],
            'total_fees': result['total_fees'],
            'balance_before': balance,
            'balance_after': new_balance,
            'roi_pct': (result['pnl'] / balance) * 100
        }
        trades.append(trade)
        
        print(f"Trade #{len(trades)} - {signal_timestamp.strftime('%H:%M:%S')} → {position_close_time.strftime('%H:%M:%S')}")
        print(f"  {signal['symbol']} {signal['verdict']} (conf: {signal['confidence']:.2f})")
        print(f"  ${signal['entry_price']:,.4f} → ${result['exit_price']:,.4f} ({result['exit_reason']})")
        print(f"  P&L: ${result['pnl']:,.2f} ({trade['roi_pct']:+.2f}%) | Balance: ${balance:,.2f} → ${new_balance:,.2f}")
        print()
        
        balance = new_balance
        last_position_close_time = position_close_time
        
        if balance <= 1:
            print("❌ LIQUIDATED")
            break
    
    # Summary
    trades_df = pd.DataFrame(trades)
    
    if len(trades_df) > 0:
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]
        tp = trades_df[trades_df['exit_reason'] == 'TP']
        sl = trades_df[trades_df['exit_reason'] == 'SL']
        ttl = trades_df[trades_df['exit_reason'] == 'TTL']
        
        print("=" * 60)
        print("SUMMARY - LAST 3 HOURS")
        print("=" * 60)
        print(f"Time period: {three_hours_ago.strftime('%H:%M')} - {last_signal_time.strftime('%H:%M')} UTC")
        print(f"Total signals: {len(recent_signals)}")
        print(f"Trades executed: {len(trades_df)}")
        print(f"Signals skipped: {skipped_old}")
        print()
        print(f"Final balance: ${balance:,.2f}")
        print(f"Total P&L: ${balance - INITIAL_BALANCE:,.2f}")
        print(f"ROI: {((balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100:+.2f}%")
        print()
        print(f"Win rate: {len(wins)}/{len(trades_df)} = {len(wins)/len(trades_df)*100:.1f}%")
        if len(wins) > 0:
            print(f"Avg win: ${wins['pnl'].mean():.2f} | Total: ${wins['pnl'].sum():.2f}")
        if len(losses) > 0:
            print(f"Avg loss: ${losses['pnl'].mean():.2f} | Total: ${losses['pnl'].sum():.2f}")
        print()
        print(f"TP: {len(tp)} ({len(tp)/len(trades_df)*100:.1f}%)")
        print(f"SL: {len(sl)} ({len(sl)/len(trades_df)*100:.1f}%)")
        print(f"TTL: {len(ttl)} ({len(ttl)/len(trades_df)*100:.1f}%)")
        print()
        print(f"Total fees: ${trades_df['total_fees'].sum():.2f}")
        
        trades_df.to_csv('allin_last_3h.csv', index=False)
        print(f"\nSaved to: allin_last_3h.csv")

if __name__ == '__main__':
    main()
