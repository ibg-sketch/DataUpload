#!/usr/bin/env python3
"""
MEXC Futures Trading Backtesting - CORRECT LOGIC
SL/TP от ДЕПОЗИТА, а не от цены входа!

SL = 20% от депозита
TP = 30% от депозита
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# MEXC Trading Parameters (USER SPECIFIED)
MEXC_TAKER_FEE = 0.0006  # 0.06% комиссия за market orders
POSITION_SIZE_USDT = 100  # Размер позиции в USDT
STOP_LOSS_DEPOSIT_PCT = 20.0  # Stop-loss 20% ОТ ДЕПОЗИТА (USER SPECIFIED)
TAKE_PROFIT_DEPOSIT_PCT = 30.0  # Take-profit 30% ОТ ДЕПОЗИТА (USER SPECIFIED)
LEVERAGE_OPTIONS = [20, 50, 75, 100, 125, 150]  # EXTREME LEVERAGE TEST

# Filters
MIN_CONFIDENCE = 0.50  # 50% минимум (USER SPECIFIED)
LAST_24_HOURS_ONLY = True  # Только за последние 24 часа (USER SPECIFIED)

def simulate_trade(signal, leverage):
    """
    Simulate MEXC futures trade with SL/TP от ДЕПОЗИТА
    
    На позицию $100 USDT с leverage 100x:
    - SL = -20% от $100 = -$20
    - TP = +30% от $100 = +$30
    
    Это означает движение цены:
    - SL: -$20 / (100x × $100) = -0.2% цены
    - TP: +$30 / (100x × $100) = +0.3% цены
    """
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    
    # Entry fee
    entry_fee_pct = MEXC_TAKER_FEE
    
    # Calculate price movement needed for SL/TP
    # SL: loss_pct_from_deposit / leverage = price_movement_pct
    sl_price_move_pct = STOP_LOSS_DEPOSIT_PCT / leverage
    tp_price_move_pct = TAKE_PROFIT_DEPOSIT_PCT / leverage
    
    # Calculate actual SL/TP prices
    if verdict == "SELL":
        # Short position
        stop_loss_price = entry_price * (1 + sl_price_move_pct / 100)
        take_profit_price = entry_price * (1 - tp_price_move_pct / 100)
        
        # Check what happened first (приоритет: сначала проверяем худшее)
        # Нужно понять, какая цена была достигнута РАНЬШЕ
        
        # Для SHORT: худшее = цена идет ВВЕРХ (к SL)
        # Лучшее = цена идет ВНИЗ (к TP)
        
        if highest >= stop_loss_price:
            # Stop-loss hit
            exit_price = stop_loss_price
            exit_reason = "STOP_LOSS"
        elif lowest <= take_profit_price:
            # Take-profit hit
            exit_price = take_profit_price
            exit_reason = "TAKE_PROFIT"
        else:
            # Expired by TTL
            exit_price = final_price
            exit_reason = "TTL_EXPIRED"
        
        # Calculate profit (short: profit when price goes down)
        price_change_pct = ((entry_price - exit_price) / entry_price) * 100
        
    else:  # BUY
        # Long position
        stop_loss_price = entry_price * (1 - sl_price_move_pct / 100)
        take_profit_price = entry_price * (1 + tp_price_move_pct / 100)
        
        # Для LONG: худшее = цена идет ВНИЗ (к SL)
        # Лучшее = цена идет ВВЕРХ (к TP)
        
        if lowest <= stop_loss_price:
            # Stop-loss hit
            exit_price = stop_loss_price
            exit_reason = "STOP_LOSS"
        elif highest >= take_profit_price:
            # Take-profit hit
            exit_price = take_profit_price
            exit_reason = "TAKE_PROFIT"
        else:
            # Expired by TTL
            exit_price = final_price
            exit_reason = "TTL_EXPIRED"
        
        # Calculate profit (long: profit when price goes up)
        price_change_pct = ((exit_price - entry_price) / entry_price) * 100
    
    # Exit fee
    exit_fee_pct = MEXC_TAKER_FEE
    
    # Total fees
    total_fee_pct = entry_fee_pct + exit_fee_pct
    
    # Net profit with leverage (before fees)
    gross_profit_pct = price_change_pct * leverage
    
    # Net profit after fees
    net_profit_pct = gross_profit_pct - (total_fee_pct * 100)
    
    # Profit in USDT
    profit_usdt = (net_profit_pct / 100) * POSITION_SIZE_USDT
    
    return {
        'exit_reason': exit_reason,
        'exit_price': exit_price,
        'stop_loss_price': stop_loss_price,
        'take_profit_price': take_profit_price,
        'price_change_pct': price_change_pct,
        'gross_profit_pct': gross_profit_pct,
        'net_profit_pct': net_profit_pct,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

# Load data
print("\n" + "="*80)
print("MEXC FUTURES BACKTESTING - CORRECT SL/TP FROM DEPOSIT")
print("="*80)
print(f"\n⚙️  PARAMETERS:")
print(f"  • Stop-Loss: {STOP_LOSS_DEPOSIT_PCT}% от депозита")
print(f"  • Take-Profit: {TAKE_PROFIT_DEPOSIT_PCT}% от депозита")
print(f"  • Min Confidence: {MIN_CONFIDENCE*100}%")
print(f"  • Position Size: ${POSITION_SIZE_USDT} USDT")
print(f"  • Time Filter: Last 24 hours only")
print(f"\n📐 При 100x leverage это означает:")
print(f"  • SL срабатывает при движении цены -{STOP_LOSS_DEPOSIT_PCT/100:.2f}%")
print(f"  • TP срабатывает при движении цены +{TAKE_PROFIT_DEPOSIT_PCT/100:.2f}%")

# Calculate cutoff time
now = datetime.now()
cutoff_time = now - timedelta(hours=24)

signals = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            timestamp = datetime.strptime(row['timestamp_sent'], '%Y-%m-%d %H:%M:%S')
            
            if LAST_24_HOURS_ONLY and timestamp < cutoff_time:
                continue
            
            if row['result'] == 'CANCELLED':
                continue
            
            confidence = float(row['confidence'])
            entry_price = float(row['entry_price'])
            
            if entry_price == 0:
                continue
            
            signal = {
                'timestamp': row['timestamp_sent'],
                'symbol': row['symbol'],
                'verdict': row['verdict'],
                'confidence': confidence,
                'entry_price': entry_price,
                'target_min': float(row['target_min']) if row['target_min'] else 0,
                'target_max': float(row['target_max']) if row['target_max'] else 0,
                'highest_reached': float(row['highest_reached']) if row['highest_reached'] else entry_price,
                'lowest_reached': float(row['lowest_reached']) if row['lowest_reached'] else entry_price,
                'final_price': float(row['final_price']) if row['final_price'] else entry_price,
                'duration_actual': int(row['duration_actual']) if row['duration_actual'] else 0,
                'original_result': row['result'],
                'original_profit': float(row['profit_pct']) if row['profit_pct'] else 0
            }
            
            if confidence < MIN_CONFIDENCE:
                continue
            
            signals.append(signal)
            
        except (ValueError, KeyError) as e:
            continue

print(f"\n📊 Loaded {len(signals)} signals from last 24 hours (confidence >= {MIN_CONFIDENCE*100}%)")

if len(signals) == 0:
    print("\n⚠️  NO SIGNALS FOUND!")
    exit(0)

if signals:
    first = datetime.strptime(signals[0]['timestamp'], '%Y-%m-%d %H:%M:%S')
    last = datetime.strptime(signals[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
    print(f"  ⏰ Time range: {first.strftime('%Y-%m-%d %H:%M')} to {last.strftime('%Y-%m-%d %H:%M')}")
    print(f"  ⏱️  Duration: {(last - first).total_seconds() / 3600:.1f} hours")

# Run backtesting
results_by_leverage = {}

for leverage in LEVERAGE_OPTIONS:
    print(f"\n{'='*80}")
    print(f"TESTING WITH LEVERAGE: {leverage}x")
    print(f"  → SL @ price movement: -{STOP_LOSS_DEPOSIT_PCT/leverage:.3f}%")
    print(f"  → TP @ price movement: +{TAKE_PROFIT_DEPOSIT_PCT/leverage:.3f}%")
    print(f"{'='*80}")
    
    trades = []
    stats_by_symbol = defaultdict(lambda: {
        'total': 0, 'wins': 0, 'losses': 0,
        'profit_usdt': 0, 'stop_losses': 0, 'take_profits': 0, 'ttl_expired': 0
    })
    
    for signal in signals:
        trade = simulate_trade(signal, leverage)
        trade['signal'] = signal
        trades.append(trade)
        
        symbol = signal['symbol']
        stats = stats_by_symbol[symbol]
        stats['total'] += 1
        if trade['win']:
            stats['wins'] += 1
        else:
            stats['losses'] += 1
        stats['profit_usdt'] += trade['profit_usdt']
        
        if trade['exit_reason'] == 'STOP_LOSS':
            stats['stop_losses'] += 1
        elif trade['exit_reason'] == 'TAKE_PROFIT':
            stats['take_profits'] += 1
        else:
            stats['ttl_expired'] += 1
    
    # Statistics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t['win'])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    total_profit_usdt = sum(t['profit_usdt'] for t in trades)
    avg_profit_per_trade = total_profit_usdt / total_trades if total_trades > 0 else 0
    
    winning_profits = [t['profit_usdt'] for t in trades if t['win']]
    losing_profits = [t['profit_usdt'] for t in trades if not t['win']]
    
    avg_win = statistics.mean(winning_profits) if winning_profits else 0
    avg_loss = statistics.mean(losing_profits) if losing_profits else 0
    
    stop_losses = sum(1 for t in trades if t['exit_reason'] == 'STOP_LOSS')
    take_profits = sum(1 for t in trades if t['exit_reason'] == 'TAKE_PROFIT')
    ttl_expired = sum(1 for t in trades if t['exit_reason'] == 'TTL_EXPIRED')
    
    total_wins = sum(winning_profits) if winning_profits else 0
    total_losses = abs(sum(losing_profits)) if losing_profits else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Max drawdown
    cumulative_pnl = []
    running_total = 0
    for trade in trades:
        running_total += trade['profit_usdt']
        cumulative_pnl.append(running_total)
    
    max_drawdown = 0
    peak = cumulative_pnl[0] if cumulative_pnl else 0
    for pnl in cumulative_pnl:
        if pnl > peak:
            peak = pnl
        drawdown = peak - pnl
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    results_by_leverage[leverage] = {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_profit_usdt': total_profit_usdt,
        'avg_profit_per_trade': avg_profit_per_trade,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'stop_losses': stop_losses,
        'take_profits': take_profits,
        'ttl_expired': ttl_expired,
        'trades': trades
    }
    
    print(f"\n📈 OVERALL RESULTS:")
    print(f"  Total trades: {total_trades}")
    print(f"  Win rate: {win_rate:.1f}% ({winning_trades} wins, {losing_trades} losses)")
    print(f"  Total profit: ${total_profit_usdt:,.2f} USDT")
    print(f"  Average per trade: ${avg_profit_per_trade:,.2f} USDT")
    print(f"  Average win: ${avg_win:,.2f} USDT")
    print(f"  Average loss: ${avg_loss:,.2f} USDT")
    print(f"  Profit factor: {profit_factor:.2f}")
    print(f"  Max drawdown: ${max_drawdown:,.2f} USDT")
    
    print(f"\n🎯 EXIT REASONS:")
    print(f"  Stop-loss hit (-{STOP_LOSS_DEPOSIT_PCT}% deposit): {stop_losses} ({stop_losses/total_trades*100:.1f}%)")
    print(f"  Take-profit hit (+{TAKE_PROFIT_DEPOSIT_PCT}% deposit): {take_profits} ({take_profits/total_trades*100:.1f}%)")
    print(f"  TTL expired: {ttl_expired} ({ttl_expired/total_trades*100:.1f}%)")
    
    if len(stats_by_symbol) > 0:
        print(f"\n📊 TOP 5 BY PROFIT:")
        sorted_symbols = sorted(stats_by_symbol.items(), 
                               key=lambda x: x[1]['profit_usdt'], reverse=True)
        for symbol, stats in sorted_symbols[:5]:
            wr = stats['wins'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {symbol:<12} {stats['total']:>3} trades | "
                  f"WR: {wr:>5.1f}% | SL: {stats['stop_losses']:>3} | TP: {stats['take_profits']:>3} | "
                  f"Profit: ${stats['profit_usdt']:>8,.2f}")

# Comparison
print(f"\n{'='*80}")
print("LEVERAGE COMPARISON")
print(f"{'='*80}")
print(f"\n{'Leverage':<10} {'Total $':<15} {'Avg/Trade':<15} {'Win Rate':<12} {'SL Hit%':<12} {'TP Hit%':<12}")
print("-"*90)

for leverage in LEVERAGE_OPTIONS:
    r = results_by_leverage[leverage]
    sl_rate = (r['stop_losses'] / r['total_trades'] * 100) if r['total_trades'] > 0 else 0
    tp_rate = (r['take_profits'] / r['total_trades'] * 100) if r['total_trades'] > 0 else 0
    print(f"{leverage}x{' '*7} "
          f"${r['total_profit_usdt']:>10,.2f}    "
          f"${r['avg_profit_per_trade']:>10,.2f}    "
          f"{r['win_rate']:>6.1f}%     "
          f"{sl_rate:>6.1f}%     "
          f"{tp_rate:>6.1f}%")

# ROI
starting_capital = 1000
print(f"\n{'='*80}")
print(f"ROI ANALYSIS (Starting capital: ${starting_capital:,.2f} USDT)")
print(f"{'='*80}")
print(f"\n{'Leverage':<10} {'Final Balance':<18} {'ROI':<15} {'Risk Rating':<20}")
print("-"*80)

for leverage in LEVERAGE_OPTIONS:
    r = results_by_leverage[leverage]
    final_balance = starting_capital + r['total_profit_usdt']
    roi = ((final_balance - starting_capital) / starting_capital) * 100
    
    sl_rate = (r['stop_losses'] / r['total_trades'] * 100) if r['total_trades'] > 0 else 0
    
    if sl_rate > 30:
        risk = "🔴 HIGH RISK"
    elif sl_rate > 15:
        risk = "🟡 MEDIUM RISK"
    elif sl_rate > 5:
        risk = "🟢 LOW RISK"
    else:
        risk = "✅ VERY LOW RISK"
    
    print(f"{leverage}x{' '*7} "
          f"${final_balance:>12,.2f}      "
          f"{roi:>10.1f}%     "
          f"{risk:<20}")

print(f"\n{'='*80}")
print(f"💡 KEY INSIGHTS - 100x LEVERAGE:")
print(f"{'='*80}")

r100 = results_by_leverage[100]
print(f"\n✅ Performance:")
print(f"   - Total profit: ${r100['total_profit_usdt']:,.2f} USDT")
print(f"   - Win rate: {r100['win_rate']:.1f}%")
print(f"   - ROI: {((starting_capital + r100['total_profit_usdt']) / starting_capital - 1) * 100:.1f}%")
print(f"   - Profit factor: {r100['profit_factor']:.2f}")

print(f"\n🎯 Exit distribution:")
print(f"   - Stop-loss: {r100['stop_losses']}/{r100['total_trades']} ({r100['stop_losses']/r100['total_trades']*100:.1f}%)")
print(f"   - Take-profit: {r100['take_profits']}/{r100['total_trades']} ({r100['take_profits']/r100['total_trades']*100:.1f}%)")
print(f"   - TTL expired: {r100['ttl_expired']}/{r100['total_trades']} ({r100['ttl_expired']/r100['total_trades']*100:.1f}%)")

print(f"\n⚠️  Risk metrics:")
print(f"   - Max drawdown: ${r100['max_drawdown']:,.2f} USDT ({r100['max_drawdown']/starting_capital*100:.1f}% of capital)")
print(f"   - Average loss: ${r100['avg_loss']:,.2f} USDT")
print(f"   - Worst case: Stop-loss = -${STOP_LOSS_DEPOSIT_PCT} per trade")

print(f"\n{'='*80}\n")
