#!/usr/bin/env python3
"""
All-In Trading Simulation for November 17, 2025 - FIXED VERSION
Correctly tracks position exit time (TP/SL can close position early)
Uses all available balance for each position with 50x leverage
Current parameters: SL 10%, Hybrid TP strategy
"""

import pandas as pd
from datetime import datetime, timedelta

# Configuration
INITIAL_BALANCE = 1000.0
LEVERAGE = 50
STOP_LOSS_PCT = 10  # 10% of position size
FEE_RATE = 0.001  # 0.1%
TP_STRATEGY = "hybrid"  # BUY->target_min, SELL->target_max

def calculate_pnl(entry_price, exit_price, position_size, direction, leverage, fee_rate):
    """Calculate P&L with fees"""
    notional = position_size * leverage
    
    if direction == "BUY":
        price_change_pct = (exit_price - entry_price) / entry_price
    else:  # SELL
        price_change_pct = (entry_price - exit_price) / entry_price
    
    gross_pnl = notional * price_change_pct
    entry_fee = notional * fee_rate
    exit_fee = notional * fee_rate
    total_fees = entry_fee + exit_fee
    net_pnl = gross_pnl - total_fees
    
    return net_pnl, total_fees

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
    if TP_STRATEGY == "hybrid":
        if direction == "BUY":
            tp_price = target_min if target_min > 0 else None
        else:  # SELL
            tp_price = target_max if target_max > 0 else None
    
    # Simulate price action - estimate exit time
    # We assume TP/SL hit quickly (within 1-5 minutes on average)
    # TTL takes full duration
    exit_price = None
    exit_reason = None
    exit_minutes = signal['duration_minutes']  # Default to TTL
    
    if direction == "BUY":
        # Check stop-loss
        if lowest <= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2  # Assume SL hit quickly
        # Check take-profit
        elif tp_price and highest >= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5  # Assume TP hit within 5 minutes on average
        # TTL expiry
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
            # Keep full duration
    else:  # SELL
        # Check stop-loss
        if highest >= sl_price:
            exit_price = sl_price
            exit_reason = "SL"
            exit_minutes = 2  # Assume SL hit quickly
        # Check take-profit
        elif tp_price and lowest <= tp_price:
            exit_price = tp_price
            exit_reason = "TP"
            exit_minutes = 5  # Assume TP hit within 5 minutes on average
        # TTL expiry
        else:
            exit_price = signal['final_price']
            exit_reason = "TTL"
            # Keep full duration
    
    # Calculate P&L
    pnl, fees = calculate_pnl(entry_price, exit_price, position_size, direction, LEVERAGE, FEE_RATE)
    
    return {
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'exit_minutes': exit_minutes,
        'pnl': pnl,
        'fees': fees,
        'position_size': position_size,
        'notional': notional,
        'sl_price': sl_price,
        'tp_price': tp_price if tp_price else None
    }

def main():
    # Load signals
    df = pd.read_csv('effectiveness_log.csv')
    
    # Filter for November 17, 2025
    df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
    today_signals = df[df['timestamp_sent'].dt.date == pd.Timestamp('2025-11-17').date()].copy()
    
    # Sort by timestamp
    today_signals = today_signals.sort_values('timestamp_sent')
    
    print(f"=== ALL-IN TRADING SIMULATION (FIXED) ===")
    print(f"Date: November 17, 2025")
    print(f"Total signals today: {len(today_signals)}")
    print(f"Initial balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Stop-Loss: {STOP_LOSS_PCT}% of position (0.2% price move)")
    print(f"TP Strategy: {TP_STRATEGY}")
    print(f"Fee rate: {FEE_RATE*100}%")
    print()
    
    # Track state
    balance = INITIAL_BALANCE
    position_close_time = None  # When current position will close
    
    trades = []
    skipped_cancelled = 0
    skipped_position_open = 0
    
    for idx, signal in today_signals.iterrows():
        timestamp = signal['timestamp_sent']
        
        # Check if previous position has closed
        if position_close_time and timestamp < position_close_time:
            skipped_position_open += 1
            continue
        
        # Only trade signals with targets (not CANCELLED immediately)
        if signal['target_min'] == 0 and signal['target_max'] == 0:
            skipped_cancelled += 1
            continue
        
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
            'fees': result['fees'],
            'balance_before': balance,
            'balance_after': new_balance,
            'roi_pct': (result['pnl'] / balance) * 100
        }
        trades.append(trade)
        
        # Print trade details
        print(f"Trade #{len(trades)} - {timestamp.strftime('%H:%M:%S')}")
        print(f"  Symbol: {signal['symbol']}")
        print(f"  Direction: {signal['verdict']} (confidence: {signal['confidence']:.2f})")
        print(f"  Entry: ${signal['entry_price']:,.4f}")
        tp_str = f"${result['tp_price']:,.4f}" if result['tp_price'] else "N/A"
        print(f"  Exit: ${result['exit_price']:,.4f} ({result['exit_reason']}) after {result['exit_minutes']} min")
        print(f"  SL: ${result['sl_price']:,.4f}, TP: {tp_str}")
        print(f"  Position: ${result['position_size']:,.2f} @ {LEVERAGE}x = ${result['notional']:,.2f} notional")
        print(f"  P&L: ${result['pnl']:,.2f} ({trade['roi_pct']:+.2f}%)")
        print(f"  Balance: ${balance:,.2f} → ${new_balance:,.2f}")
        print()
        
        balance = new_balance
        
        # If balance is depleted, stop
        if balance <= 0:
            print("❌ ACCOUNT LIQUIDATED - Balance depleted to $0")
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
        
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total signals: {len(today_signals)}")
        print(f"  - With targets: {len(today_signals) - skipped_cancelled}")
        print(f"  - Cancelled: {skipped_cancelled}")
        print(f"Trades executed: {len(trades_df)}")
        print(f"Signals skipped (position open): {skipped_position_open}")
        print()
        print(f"Final balance: ${balance:,.2f}")
        print(f"Total P&L: ${balance - INITIAL_BALANCE:,.2f}")
        print(f"Total ROI: {((balance - INITIAL_BALANCE) / INITIAL_BALANCE) * 100:+.2f}%")
        print()
        print(f"Win rate: {len(wins)}/{len(trades_df)} = {len(wins)/len(trades_df)*100:.1f}%")
        print(f"Average win: ${wins['pnl'].mean():.2f}" if len(wins) > 0 else "Average win: $0.00")
        print(f"Average loss: ${losses['pnl'].mean():.2f}" if len(losses) > 0 else "Average loss: $0.00")
        print()
        print("Exit distribution:")
        print(f"  TP exits: {len(tp_exits)} ({len(tp_exits)/len(trades_df)*100:.1f}%)")
        print(f"  SL exits: {len(sl_exits)} ({len(sl_exits)/len(trades_df)*100:.1f}%)")
        print(f"  TTL exits: {len(ttl_exits)} ({len(ttl_exits)/len(trades_df)*100:.1f}%)")
        print()
        print(f"Total fees paid: ${trades_df['fees'].sum():,.2f}")
        print(f"Gross P&L (before fees): ${trades_df['pnl'].sum() + trades_df['fees'].sum():,.2f}")
        
        # Save detailed trades to CSV
        trades_df.to_csv('allin_trades_nov17_fixed.csv', index=False)
        print(f"\nDetailed trades saved to: allin_trades_nov17_fixed.csv")
    else:
        print("No trades executed!")

if __name__ == '__main__':
    main()
