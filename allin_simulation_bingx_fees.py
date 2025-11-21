#!/usr/bin/env python3
"""
All-In Trading Simulation for November 17, 2025 - WITH BINGX FEES
Now includes ALL signals (previously CANCELLED ones also trade to SL/TP/TTL)
Uses actual BingX fee structure: Entry 0.05% (taker), Exit TP 0.02% (maker), Exit SL/TTL 0.05% (taker)
All signals run until TP, SL, or TTL - no cancellations
Current parameters: SL 10%, Hybrid TP strategy
"""

import pandas as pd
from datetime import datetime, timedelta

# Configuration
INITIAL_BALANCE = 1000.0
LEVERAGE = 50
STOP_LOSS_PCT = 10  # 10% of position size (0.2% price movement at 50x)
TP_STRATEGY = "hybrid"  # BUY->target_min, SELL->target_max

# BingX Fee Structure
ENTRY_FEE_RATE = 0.0005  # 0.05% taker
EXIT_FEE_TP = 0.0002     # 0.02% maker (limit order)
EXIT_FEE_SL_TTL = 0.0005 # 0.05% taker (market order)

def calculate_pnl(entry_price, exit_price, position_size, direction, leverage, exit_reason):
    """Calculate P&L with BingX fee structure"""
    notional = position_size * leverage
    
    # Calculate price movement P&L
    if direction == "BUY":
        price_change_pct = (exit_price - entry_price) / entry_price
    else:  # SELL
        price_change_pct = (entry_price - exit_price) / entry_price
    
    gross_pnl = notional * price_change_pct
    
    # Calculate fees based on exit type
    entry_fee = notional * ENTRY_FEE_RATE
    if exit_reason == "TP":
        exit_fee = notional * EXIT_FEE_TP  # Limit order (maker)
    else:  # SL or TTL
        exit_fee = notional * EXIT_FEE_SL_TTL  # Market order (taker)
    
    total_fees = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fees
    
    return net_pnl, total_fees, entry_fee, exit_fee

def simulate_position(signal, balance):
    """Simulate a single position with current balance"""
    entry_price = signal['entry_price']
    direction = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    target_min = signal['target_min']
    target_max = signal['target_max']
    
    # Use all available balance
    position_size = balance
    notional = position_size * LEVERAGE
    
    # Calculate stop-loss price
    sl_amount = position_size * (STOP_LOSS_PCT / 100)  # 10% of position
    if direction == "BUY":
        sl_price = entry_price * (1 - (sl_amount / notional))
    else:  # SELL
        sl_price = entry_price * (1 + (sl_amount / notional))
    
    # Determine take-profit target
    # For signals that were previously CANCELLED (target=0), we won't have TP
    tp_price = None
    if TP_STRATEGY == "hybrid":
        if direction == "BUY" and target_min > 0:
            tp_price = target_min
        elif direction == "SELL" and target_max > 0:
            tp_price = target_max
    
    # Simulate price action - estimate exit time
    exit_price = None
    exit_reason = None
    exit_minutes = signal['duration_minutes'] if signal['duration_minutes'] > 0 else 30  # Default TTL
    
    if direction == "BUY":
        # Check stop-loss first (takes priority)
        if lowest <= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2  # Assume SL hit quickly
        # Check take-profit
        elif tp_price and highest >= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5  # Assume TP hit within 5 minutes
        # TTL expiry
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
            # Keep full duration
    else:  # SELL
        # Check stop-loss first (takes priority)
        if highest >= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2  # Assume SL hit quickly
        # Check take-profit
        elif tp_price and lowest <= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5  # Assume TP hit within 5 minutes
        # TTL expiry
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
            # Keep full duration
    
    # Calculate P&L
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
    
    # Filter for November 17, 2025
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    today_signals = df[df['timestamp_sent'].dt.date == pd.Timestamp('2025-11-17').date()].copy()
    
    # Sort by timestamp
    today_signals = today_signals.sort_values('timestamp_sent')
    
    print(f"=== ALL-IN TRADING SIMULATION - BINGX FEES ===")
    print(f"Date: November 17, 2025")
    print(f"Total signals today: {len(today_signals)}")
    print(f"Initial balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Stop-Loss: {STOP_LOSS_PCT}% of position (0.2% price move at 50x)")
    print(f"TP Strategy: {TP_STRATEGY}")
    print(f"Fee structure (BingX):")
    print(f"  - Entry (taker): {ENTRY_FEE_RATE*100}%")
    print(f"  - Exit TP (maker): {EXIT_FEE_TP*100}%")
    print(f"  - Exit SL/TTL (taker): {EXIT_FEE_SL_TTL*100}%")
    print(f"NOTE: Trading ALL signals (no cancellations - all run to TP/SL/TTL)")
    print()
    
    # Track state
    balance = INITIAL_BALANCE
    position_close_time = None  # When current position will close
    
    trades = []
    skipped_position_open = 0
    
    for idx, signal in today_signals.iterrows():
        timestamp = signal['timestamp_sent']
        
        # Check if previous position has closed
        if position_close_time and timestamp < position_close_time:
            skipped_position_open += 1
            continue
        
        # Trade ALL signals (including previously CANCELLED ones)
        # Open new position
        result = simulate_position(signal, balance)
        
        # Update balance
        new_balance = balance + result['pnl']
        
        # Calculate when this position will close
        position_close_time = timestamp + timedelta(minutes=result['exit_minutes'])
        
        # Record trade
        trade = {
            'timestamp': timestamp,
            'symbol': signal['symbol'],
            'direction': signal['verdict'],
            'confidence': signal['confidence'],
            'entry_price': signal['entry_price'],
            'exit_price': result['exit_price'],
            'exit_reason': result['exit_reason'],
            'exit_minutes': result['exit_minutes'],
            'position_size': result['position_size'],
            'notional': result['notional'],
            'sl_price': result['sl_price'],
            'tp_price': result['tp_price'],
            'pnl': result['pnl'],
            'total_fees': result['total_fees'],
            'entry_fee': result['entry_fee'],
            'exit_fee': result['exit_fee'],
            'balance_before': balance,
            'balance_after': new_balance,
            'roi_pct': (result['pnl'] / balance) * 100,
            'had_target': 1 if (signal['target_min'] > 0 or signal['target_max'] > 0) else 0
        }
        trades.append(trade)
        
        # Print first 10 and last 10 trades
        if len(trades) <= 10 or len(trades) % 10 == 0:
            print(f"Trade #{len(trades)} - {timestamp.strftime('%H:%M:%S')}")
            print(f"  {signal['symbol']} {signal['verdict']} (conf: {signal['confidence']:.2f})")
            print(f"  Entry: ${signal['entry_price']:,.4f} → Exit: ${result['exit_price']:,.4f} ({result['exit_reason']})")
            tp_str = f"${result['tp_price']:,.4f}" if result['tp_price'] else "N/A"
            print(f"  SL: ${result['sl_price']:,.4f}, TP: {tp_str}")
            print(f"  P&L: ${result['pnl']:,.2f} ({trade['roi_pct']:+.2f}%) | Fees: ${result['total_fees']:,.2f}")
            print(f"  Balance: ${balance:,.2f} → ${new_balance:,.2f}")
            print()
        
        balance = new_balance
        
        # If balance is depleted, stop
        if balance <= 1:
            print("❌ ACCOUNT LIQUIDATED - Balance depleted")
            print(f"Liquidated after {len(trades)} trades")
            break
    
    # Summary statistics
    trades_df = pd.DataFrame(trades)
    
    if len(trades_df) > 0:
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]
        
        tp_exits = trades_df[trades_df['exit_reason'] == 'TP']
        sl_exits = trades_df[trades_df['exit_reason'] == 'SL']
        ttl_exits = trades_df[trades_df['exit_reason'] == 'TTL']
        
        with_targets = trades_df[trades_df['had_target'] == 1]
        without_targets = trades_df[trades_df['had_target'] == 0]
        
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total signals: {len(today_signals)}")
        print(f"Trades executed: {len(trades_df)}")
        print(f"  - With targets (original): {len(with_targets)}")
        print(f"  - Without targets (was CANCELLED): {len(without_targets)}")
        print(f"Signals skipped (position open): {skipped_position_open}")
        print()
        print(f"Final balance: ${balance:,.2f}")
        print(f"Total P&L: ${balance - INITIAL_BALANCE:,.2f}")
        print(f"Total ROI: {((balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100:+.2f}%")
        print()
        print(f"Win rate: {len(wins)}/{len(trades_df)} = {len(wins)/len(trades_df)*100:.1f}%")
        if len(wins) > 0:
            print(f"Average win: ${wins['pnl'].mean():.2f}")
            print(f"Total wins: ${wins['pnl'].sum():.2f}")
        if len(losses) > 0:
            print(f"Average loss: ${losses['pnl'].mean():.2f}")
            print(f"Total losses: ${losses['pnl'].sum():.2f}")
        print()
        print("Exit distribution:")
        print(f"  TP exits: {len(tp_exits)} ({len(tp_exits)/len(trades_df)*100:.1f}%)")
        print(f"  SL exits: {len(sl_exits)} ({len(sl_exits)/len(trades_df)*100:.1f}%)")
        print(f"  TTL exits: {len(ttl_exits)} ({len(ttl_exits)/len(trades_df)*100:.1f}%)")
        print()
        print(f"Total fees paid: ${trades_df['total_fees'].sum():,.2f}")
        print(f"  - Entry fees: ${trades_df['entry_fee'].sum():,.2f}")
        print(f"  - Exit fees: ${trades_df['exit_fee'].sum():,.2f}")
        print(f"Gross P&L (before fees): ${trades_df['pnl'].sum() + trades_df['total_fees'].sum():,.2f}")
        
        # Save detailed trades to CSV
        trades_df.to_csv('allin_trades_bingx_fees.csv', index=False)
        print(f"\nDetailed trades saved to: allin_trades_bingx_fees.csv")
    else:
        print("No trades executed!")

if __name__ == '__main__':
    main()
