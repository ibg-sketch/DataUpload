"""
Sequential Trading Simulation
Simulates trading with $1000 deposit, one position at a time, all available funds
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

def get_historical_prices(symbol, start_time, end_time):
    """Get historical price data from Data Feeds Service logs"""
    try:
        df = pd.read_csv('services/data_feeds/logs/market_features.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        mask = (df['symbol'] == symbol) & \
               (df['timestamp'] >= start_time) & \
               (df['timestamp'] <= end_time)
        
        prices = df[mask][['timestamp', 'close', 'high', 'low']].copy()
        return prices.sort_values('timestamp')
    except Exception as e:
        print(f"⚠️  Could not load historical prices: {e}")
        return None

def simulate_position(signal, balance, signal_num, total_signals):
    """Simulate a single position from open to close"""
    symbol = signal['symbol']
    direction = signal['verdict']
    entry_price = float(signal['entry_price'])
    confidence = float(signal['confidence'])
    ttl_minutes = int(signal['ttl_minutes'])
    
    # Calculate position parameters
    position_size = calculate_position_size(balance)
    tp_price = calculate_tp_price(signal, entry_price)
    sl_price = calculate_sl_price(entry_price, direction)
    
    # Entry timestamp
    entry_time = pd.to_datetime(signal['timestamp'])
    ttl_expiry = entry_time + timedelta(minutes=ttl_minutes)
    
    # Calculate entry fee
    entry_fee = balance * TAKER_FEE
    
    print(f"\n{'='*80}")
    print(f"📊 SIGNAL {signal_num}/{total_signals}: {symbol} {direction} @ {confidence*100:.0f}%")
    print(f"{'='*80}")
    print(f"💰 Entry Time: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💵 Balance: ${balance:.2f}")
    print(f"📈 Position Size: ${position_size:.2f} ({LEVERAGE}x leverage)")
    print(f"💲 Entry Price: ${entry_price:.6f}")
    print(f"🎯 TP: ${tp_price:.6f} ({((tp_price/entry_price - 1) if direction == 'BUY' else (1 - tp_price/entry_price)) * 100 * LEVERAGE:.2f}%)")
    print(f"🛑 SL: ${sl_price:.6f} ({-STOP_LOSS_PCT:.1f}%)")
    print(f"⏱️  TTL: {ttl_minutes} minutes (expires {ttl_expiry.strftime('%H:%M:%S')})")
    
    # Get historical prices
    prices = get_historical_prices(symbol, entry_time, ttl_expiry + timedelta(minutes=5))
    
    if prices is None or len(prices) == 0:
        print(f"⚠️  No price data available, simulating based on target prices...")
        # Fallback: assume 70% reach TP, 30% hit SL (based on backtest stats)
        import random
        if random.random() < 0.419:  # 41.9% win rate from backtest
            exit_price = tp_price
            exit_reason = "Take-Profit"
        else:
            exit_price = sl_price
            exit_reason = "Stop-Loss"
        exit_time = ttl_expiry
    else:
        # Simulate position with real prices
        exit_price = None
        exit_reason = None
        exit_time = None
        
        for _, row in prices.iterrows():
            timestamp = row['timestamp']
            high = row['high']
            low = row['low']
            
            # Check SL first (more conservative)
            if direction == 'SELL':
                if high >= sl_price:
                    exit_price = sl_price
                    exit_reason = "Stop-Loss"
                    exit_time = timestamp
                    break
                elif low <= tp_price:
                    exit_price = tp_price
                    exit_reason = "Take-Profit"
                    exit_time = timestamp
                    break
            else:  # BUY
                if low <= sl_price:
                    exit_price = sl_price
                    exit_reason = "Stop-Loss"
                    exit_time = timestamp
                    break
                elif high >= tp_price:
                    exit_price = tp_price
                    exit_reason = "Take-Profit"
                    exit_time = timestamp
                    break
        
        # If no TP/SL hit, close at TTL
        if exit_price is None:
            exit_price = prices.iloc[-1]['close'] if len(prices) > 0 else entry_price
            exit_reason = "TTL Expired"
            exit_time = ttl_expiry
    
    # Calculate P&L
    if direction == 'SELL':
        price_change_pct = (entry_price - exit_price) / entry_price
    else:
        price_change_pct = (exit_price - entry_price) / entry_price
    
    position_pnl_pct = price_change_pct * LEVERAGE
    exit_fee = balance * (1 + position_pnl_pct) * TAKER_FEE if position_pnl_pct > -1 else 0
    
    pnl_usd = balance * position_pnl_pct - entry_fee - exit_fee
    new_balance = balance + pnl_usd
    
    # Duration
    duration = (exit_time - entry_time).total_seconds() / 60
    
    # Display results
    print(f"\n{'─'*80}")
    print(f"{'✅' if pnl_usd > 0 else '❌'} EXIT: {exit_reason}")
    print(f"⏰ Duration: {duration:.1f} minutes")
    print(f"💲 Exit Price: ${exit_price:.6f}")
    print(f"📊 Price Change: {price_change_pct * 100:.2f}% → Position P&L: {position_pnl_pct * 100:.2f}%")
    print(f"💵 Profit/Loss: ${pnl_usd:.2f}")
    print(f"💰 New Balance: ${new_balance:.2f} ({(new_balance/balance - 1) * 100:+.2f}%)")
    
    return {
        'signal_num': signal_num,
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'entry_time': entry_time,
        'exit_time': exit_time,
        'duration_minutes': duration,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'exit_reason': exit_reason,
        'balance_before': balance,
        'position_size': position_size,
        'pnl_usd': pnl_usd,
        'pnl_pct': (new_balance / balance - 1) * 100,
        'balance_after': new_balance
    }

def main():
    print("="*80)
    print("SEQUENTIAL TRADING SIMULATION")
    print("="*80)
    print(f"Starting Balance: ${STARTING_BALANCE:.2f}")
    print(f"Strategy: One position at a time, all available funds")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Stop-Loss: {STOP_LOSS_PCT}% of position (0.20% price at {LEVERAGE}x)")
    print(f"Take-Profit: Hybrid strategy (BUY=conservative, SELL=aggressive)")
    print(f"Period: Last 7 days")
    print("="*80)
    
    # Load signals
    df = pd.read_csv('signals_log.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter last 7 days
    seven_days_ago = datetime.now() - timedelta(days=7)
    df = df[df['timestamp'] >= seven_days_ago].copy()
    df = df.sort_values('timestamp')
    
    print(f"\n📊 Loaded {len(df)} signals from last 7 days")
    print(f"📅 Period: {df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} → {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}")
    
    # Simulate sequential trading
    balance = STARTING_BALANCE
    current_position = None
    trades = []
    
    for idx, (_, signal) in enumerate(df.iterrows(), 1):
        # If we have a position, check if it would be closed by now
        if current_position is not None:
            if pd.to_datetime(signal['timestamp']) < current_position['exit_time']:
                # Position still open, skip this signal
                continue
        
        # Open new position
        result = simulate_position(signal, balance, idx, len(df))
        balance = result['balance_after']
        current_position = result
        trades.append(result)
        
        # Stop if balance is depleted
        if balance <= 10:
            print(f"\n⚠️  Balance depleted to ${balance:.2f}, stopping simulation")
            break
    
    # Generate summary
    print("\n" + "="*80)
    print("📈 FINAL RESULTS")
    print("="*80)
    
    trades_df = pd.DataFrame(trades)
    
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df['pnl_usd'] > 0])
    losses = len(trades_df[trades_df['pnl_usd'] < 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    total_pnl = balance - STARTING_BALANCE
    total_pnl_pct = (balance / STARTING_BALANCE - 1) * 100
    
    avg_win = trades_df[trades_df['pnl_usd'] > 0]['pnl_usd'].mean() if wins > 0 else 0
    avg_loss = trades_df[trades_df['pnl_usd'] < 0]['pnl_usd'].mean() if losses > 0 else 0
    
    print(f"\n💰 Starting Balance: ${STARTING_BALANCE:.2f}")
    print(f"💵 Final Balance: ${balance:.2f}")
    print(f"📊 Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
    
    print(f"\n📈 Trading Statistics:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Wins: {wins} ({win_rate:.1f}%)")
    print(f"   Losses: {losses} ({100-win_rate:.1f}%)")
    print(f"   Average Win: ${avg_win:.2f}")
    print(f"   Average Loss: ${avg_loss:.2f}")
    print(f"   Profit Factor: {abs(avg_win * wins / (avg_loss * losses)) if losses > 0 and avg_loss != 0 else float('inf'):.2f}")
    
    # Exit reasons
    print(f"\n🎯 Exit Distribution:")
    exit_counts = trades_df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        print(f"   {reason}: {count} ({count/total_trades*100:.1f}%)")
    
    # Best and worst trades
    print(f"\n🏆 Best Trade: ${trades_df['pnl_usd'].max():.2f}")
    best_trade = trades_df.loc[trades_df['pnl_usd'].idxmax()]
    print(f"   {best_trade['symbol']} {best_trade['direction']} @ {best_trade['entry_time'].strftime('%Y-%m-%d %H:%M')}")
    
    print(f"\n💔 Worst Trade: ${trades_df['pnl_usd'].min():.2f}")
    worst_trade = trades_df.loc[trades_df['pnl_usd'].idxmin()]
    print(f"   {worst_trade['symbol']} {worst_trade['direction']} @ {worst_trade['entry_time'].strftime('%Y-%m-%d %H:%M')}")
    
    # Save detailed report
    trades_df.to_csv('analysis/results/sequential_trading_simulation.csv', index=False)
    print(f"\n💾 Detailed report saved to: analysis/results/sequential_trading_simulation.csv")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
