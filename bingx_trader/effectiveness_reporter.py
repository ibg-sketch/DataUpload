"""
BingX Auto-Trader Effectiveness Reporter
Analyzes trades_log.csv and generates performance reports
"""
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

TRADES_LOG = "bingx_trader/logs/trades_log.csv"

def calculate_period_stats(hours: int):
    """Calculate trading statistics for a given period"""
    if not Path(TRADES_LOG).exists():
        return None
    
    cutoff = datetime.now() - timedelta(hours=hours)
    
    total_trades = 0
    wins = 0
    losses = 0
    total_pnl = 0.0
    
    tp_count = 0
    sl_count = 0
    ttl_count = 0
    
    try:
        with open(TRADES_LOG, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    close_time = datetime.fromisoformat(row['timestamp_close'])
                    
                    if close_time < cutoff:
                        continue
                    
                    total_trades += 1
                    profit = float(row['actual_profit_usd'])
                    total_pnl += profit
                    
                    if profit > 0:
                        wins += 1
                    else:
                        losses += 1
                    
                    exit_reason = row['exit_reason']
                    if 'Take-Profit' in exit_reason or 'TP' in exit_reason:
                        tp_count += 1
                    elif 'Stop-Loss' in exit_reason or 'SL' in exit_reason:
                        sl_count += 1
                    elif 'TTL' in exit_reason or 'Expired' in exit_reason:
                        ttl_count += 1
                
                except (ValueError, KeyError, TypeError):
                    continue
    
    except Exception as e:
        print(f"[EFFECTIVENESS ERROR] Failed to read trades log: {e}")
        return None
    
    if total_trades == 0:
        return None
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_profit = total_pnl / total_trades if total_trades > 0 else 0
    
    return {
        'total': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_profit': avg_profit,
        'tp_count': tp_count,
        'sl_count': sl_count,
        'ttl_count': ttl_count
    }

def format_bingx_effectiveness_report():
    """Generate formatted BingX Auto-Trader effectiveness report"""
    periods = [
        (1, '1h'),
        (6, '6h'),
        (12, '12h'),
        (24, '24h'),
        (72, '3d'),
        (168, '7d')
    ]
    
    lines = []
    lines.append("📊 <b>BingX AUTO-TRADER EFFECTIVENESS REPORT</b>")
    lines.append("=" * 35)
    
    has_data = False
    
    for hours, label in periods:
        stats = calculate_period_stats(hours)
        
        if stats is None:
            continue
        
        has_data = True
        
        pnl_emoji = "🟢" if stats['total_pnl'] >= 0 else "🔴"
        wr_emoji = "✅" if stats['win_rate'] >= 50 else "⚠️"
        
        lines.append(f"\n<b>{label.upper()}</b>")
        lines.append(f"Trades: {stats['total']} ({stats['wins']}W/{stats['losses']}L)")
        lines.append(f"{wr_emoji} Win Rate: {stats['win_rate']:.1f}%")
        lines.append(f"{pnl_emoji} PnL: ${stats['total_pnl']:+.2f}")
        lines.append(f"Avg/Trade: ${stats['avg_profit']:+.2f}")
        
        if stats['total'] > 0:
            lines.append(f"Exits: TP:{stats['tp_count']} SL:{stats['sl_count']} TTL:{stats['ttl_count']}")
    
    if not has_data:
        return None
    
    lines.append("\n" + "=" * 35)
    lines.append(f"<i>Updated: {datetime.now().strftime('%H:%M GMT+3')}</i>")
    
    return "\n".join(lines)
