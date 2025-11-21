#!/usr/bin/env python3
"""
MEXC Futures Trading Backtesting
Симуляция автоматической торговли на исторических сигналах
"""

import csv
from datetime import datetime
from collections import defaultdict
import statistics

# MEXC Trading Parameters
MEXC_TAKER_FEE = 0.0006  # 0.06% комиссия за market orders
POSITION_SIZE_USDT = 100  # Размер позиции в USDT
STOP_LOSS_PCT = 1.5  # Stop-loss в процентах (1.5%)
LEVERAGE_OPTIONS = [3, 5, 10, 20]  # Тестируем разные плечи

# Filters
MIN_CONFIDENCE = 0.65  # Минимальная уверенность для входа
MIN_QUALITY = None  # None = все, 0.75 = только "Excellent"/"Good"

def calculate_quality_rating(confidence, verdict):
    """Calculate signal quality rating"""
    if verdict == "BUY":
        if confidence >= 0.60:
            return "Excellent"
        elif confidence >= 0.50:
            return "Good"
        elif confidence >= 0.40:
            return "Fair"
        else:
            return "Weak"
    else:  # SELL
        if confidence >= 0.75:
            return "Excellent"
        elif confidence >= 0.65:
            return "Good"
        elif confidence >= 0.55:
            return "Fair"
        else:
            return "Weak"

def simulate_trade(signal, leverage):
    """
    Simulate a single MEXC futures trade
    
    Returns: dict with trade results
    """
    entry_price = signal['entry_price']
    verdict = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    final_price = signal['final_price']
    target_min = signal['target_min']
    
    # Entry fee
    entry_fee_pct = MEXC_TAKER_FEE
    
    # Calculate stop-loss and take-profit prices
    if verdict == "SELL":
        # Short position
        stop_loss_price = entry_price * (1 + STOP_LOSS_PCT / 100)
        take_profit_price = target_min if target_min > 0 else entry_price * 0.995
        
        # Check what happened first
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
        stop_loss_price = entry_price * (1 - STOP_LOSS_PCT / 100)
        take_profit_price = target_min if target_min > 0 else entry_price * 1.005
        
        # Check what happened first
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
        'price_change_pct': price_change_pct,
        'gross_profit_pct': gross_profit_pct,
        'net_profit_pct': net_profit_pct,
        'profit_usdt': profit_usdt,
        'win': profit_usdt > 0
    }

# Load data
print("\n" + "="*80)
print("MEXC FUTURES BACKTESTING - Historical Signal Analysis")
print("="*80)

signals = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            # Skip cancelled signals
            if row['result'] == 'CANCELLED':
                continue
            
            confidence = float(row['confidence'])
            entry_price = float(row['entry_price'])
            
            # Skip if no price data
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
            
            # Filter by confidence
            if confidence < MIN_CONFIDENCE:
                continue
            
            # Filter by quality if set
            if MIN_QUALITY:
                quality = calculate_quality_rating(confidence, signal['verdict'])
                if quality not in ["Excellent", "Good"]:
                    continue
            
            signals.append(signal)
            
        except (ValueError, KeyError) as e:
            continue

print(f"\n📊 Loaded {len(signals)} completed signals (confidence >= {MIN_CONFIDENCE*100}%)")

# Run backtesting for different leverage levels
results_by_leverage = {}

for leverage in LEVERAGE_OPTIONS:
    print(f"\n{'='*80}")
    print(f"TESTING WITH LEVERAGE: {leverage}x")
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
    
    # Overall statistics
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
    
    # Profit factor
    total_wins = sum(winning_profits) if winning_profits else 0
    total_losses = abs(sum(losing_profits)) if losing_profits else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Max drawdown (simplified)
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
    
    # Store results
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
    
    # Print summary
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
    print(f"  Stop-loss hit: {stop_losses} ({stop_losses/total_trades*100:.1f}%)")
    print(f"  Take-profit hit: {take_profits} ({take_profits/total_trades*100:.1f}%)")
    print(f"  TTL expired: {ttl_expired} ({ttl_expired/total_trades*100:.1f}%)")
    
    # Top performers
    print(f"\n🏆 TOP 5 BEST TRADES:")
    best_trades = sorted(trades, key=lambda x: x['profit_usdt'], reverse=True)[:5]
    for i, trade in enumerate(best_trades, 1):
        sig = trade['signal']
        print(f"  {i}. {sig['symbol']} {sig['verdict']} @ ${sig['entry_price']:.2f} → "
              f"${trade['exit_price']:.2f} ({trade['exit_reason']}) = "
              f"${trade['profit_usdt']:.2f} (+{trade['net_profit_pct']:.2f}%)")
    
    print(f"\n💀 TOP 5 WORST TRADES:")
    worst_trades = sorted(trades, key=lambda x: x['profit_usdt'])[:5]
    for i, trade in enumerate(worst_trades, 1):
        sig = trade['signal']
        print(f"  {i}. {sig['symbol']} {sig['verdict']} @ ${sig['entry_price']:.2f} → "
              f"${trade['exit_price']:.2f} ({trade['exit_reason']}) = "
              f"${trade['profit_usdt']:.2f} ({trade['net_profit_pct']:.2f}%)")

# Comparison table
print(f"\n{'='*80}")
print("LEVERAGE COMPARISON")
print(f"{'='*80}")
print(f"\n{'Leverage':<10} {'Total $':<15} {'Avg/Trade':<15} {'Win Rate':<12} {'Profit Factor':<15} {'Max DD':<12}")
print("-"*80)

for leverage in LEVERAGE_OPTIONS:
    r = results_by_leverage[leverage]
    print(f"{leverage}x{' '*7} "
          f"${r['total_profit_usdt']:>10,.2f}    "
          f"${r['avg_profit_per_trade']:>10,.2f}    "
          f"{r['win_rate']:>6.1f}%     "
          f"{r['profit_factor']:>10.2f}     "
          f"${r['max_drawdown']:>8,.2f}")

# ROI calculation (assuming starting capital)
starting_capital = 1000  # $1000 starting balance
print(f"\n{'='*80}")
print(f"ROI ANALYSIS (Starting capital: ${starting_capital:,.2f} USDT)")
print(f"{'='*80}")
print(f"\n{'Leverage':<10} {'Final Balance':<18} {'ROI':<12} {'Days to 2x':<12}")
print("-"*80)

# Estimate days (based on signal frequency)
if signals:
    first_signal = datetime.strptime(signals[0]['timestamp'], '%Y-%m-%d %H:%M:%S')
    last_signal = datetime.strptime(signals[-1]['timestamp'], '%Y-%m-%d %H:%M:%S')
    days_total = (last_signal - first_signal).days
    signals_per_day = len(signals) / days_total if days_total > 0 else 0
else:
    days_total = 0
    signals_per_day = 0

for leverage in LEVERAGE_OPTIONS:
    r = results_by_leverage[leverage]
    final_balance = starting_capital + r['total_profit_usdt']
    roi = ((final_balance - starting_capital) / starting_capital) * 100
    
    # Days to double money
    if r['avg_profit_per_trade'] > 0 and signals_per_day > 0:
        days_to_double = starting_capital / (r['avg_profit_per_trade'] * signals_per_day)
    else:
        days_to_double = float('inf')
    
    days_str = f"{days_to_double:.1f}" if days_to_double != float('inf') else "∞"
    
    print(f"{leverage}x{' '*7} "
          f"${final_balance:>12,.2f}      "
          f"{roi:>8.1f}%     "
          f"{days_str:>8} days")

print(f"\n{'='*80}")
print(f"💡 KEY INSIGHTS:")
print(f"{'='*80}")

# Find best leverage
best_leverage = max(LEVERAGE_OPTIONS, key=lambda x: results_by_leverage[x]['total_profit_usdt'])
best_result = results_by_leverage[best_leverage]

print(f"\n✅ Best leverage: {best_leverage}x")
print(f"   - Total profit: ${best_result['total_profit_usdt']:,.2f} USDT")
print(f"   - Win rate: {best_result['win_rate']:.1f}%")
print(f"   - ROI: {((starting_capital + best_result['total_profit_usdt']) / starting_capital - 1) * 100:.1f}%")

print(f"\n⚠️  Risk analysis:")
print(f"   - Stop-loss frequency: {best_result['stop_losses']}/{best_result['total_trades']} ({best_result['stop_losses']/best_result['total_trades']*100:.1f}%)")
print(f"   - Max drawdown: ${best_result['max_drawdown']:,.2f} USDT ({best_result['max_drawdown']/starting_capital*100:.1f}% of capital)")
print(f"   - Average loss: ${best_result['avg_loss']:,.2f} USDT")

print(f"\n📊 Signal quality:")
print(f"   - Minimum confidence used: {MIN_CONFIDENCE*100}%")
print(f"   - Take-profit hit rate: {best_result['take_profits']}/{best_result['total_trades']} ({best_result['take_profits']/best_result['total_trades']*100:.1f}%)")
print(f"   - Signals tested: {len(signals)}")
print(f"   - Test period: {days_total} days")
print(f"   - Signals per day: {signals_per_day:.1f}")

print(f"\n{'='*80}")
print("⚠️  DISCLAIMER:")
print("  This is historical backtesting. Real trading involves:")
print("  - Slippage (market orders may execute at worse prices)")
print("  - API delays and failures")
print("  - Funding rates (positive or negative)")
print("  - Liquidation risk (if balance drops below maintenance margin)")
print("  - Emotional stress and decision-making under pressure")
print(f"{'='*80}\n")
