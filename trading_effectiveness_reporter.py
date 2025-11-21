"""
Trading Effectiveness Reporter
Generates separate effectiveness reports for PAPER and LIVE trading modes
Sends reports to Trading Bot Telegram channel
"""

import csv
import time
import os
from datetime import datetime, timedelta
from pathlib import Path
from telegram_utils import send_to_trading_channel

TRADES_LOG = 'bingx_trader/logs/trades_log.csv'
TRADING_CHANNEL_ID = os.getenv('TRADING_TELEGRAM_CHAT_ID')
REPORT_INTERVAL = 3600  # 1 hour in seconds

def parse_timestamp(ts_str):
    """Parse timestamp from trades log"""
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        try:
            return datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S.%f')
        except:
            return None

def get_trading_stats(hours=None, mode='PAPER'):
    """
    Calculate win/loss stats from trades_log.csv for specific mode.
    If hours=None, returns all-time stats.
    Returns (wins, losses, win_rate, total_trades, total_pnl, avg_duration)
    """
    if not Path(TRADES_LOG).exists():
        return (0, 0, 0.0, 0, 0.0, 0.0)
    
    now = datetime.now()
    cutoff = now - timedelta(hours=hours) if hours else None
    
    wins = 0
    losses = 0
    total_pnl = 0.0
    total_duration = 0.0
    
    with open(TRADES_LOG, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter by mode
            if row.get('mode', 'PAPER') != mode:
                continue
            
            # Filter by time
            if cutoff:
                ts = parse_timestamp(row.get('timestamp_close', ''))
                if not ts or ts < cutoff:
                    continue
            
            # Count wins/losses based on profit
            try:
                profit_pct = float(row.get('actual_profit_pct', 0))
                duration_min = float(row.get('duration_minutes', 0))
                
                if profit_pct > 0:
                    wins += 1
                else:
                    losses += 1
                
                total_pnl += profit_pct
                total_duration += duration_min
            except (ValueError, TypeError):
                pass
    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    avg_duration = (total_duration / total) if total > 0 else 0
    
    return (wins, losses, win_rate, total, total_pnl, avg_duration)

def format_trading_report(mode='PAPER'):
    """Generate effectiveness report for specific trading mode"""
    mode_name = "📝 PAPER MODE" if mode == "PAPER" else "💰 LIVE MODE"
    
    periods = [
        (1, '1h'),
        (6, '6h'),
        (12, '12h'),
        (24, '24h'),
        (72, '3d'),
        (168, '7d'),
        (336, '14d'),
        (720, '30d')
    ]
    
    lines = [f"📊 <b>{mode_name} TRADING REPORT</b>\n"]
    has_any_data = False
    
    for hours, label in periods:
        wins, losses, win_rate, total, total_pnl, avg_duration = get_trading_stats(hours, mode)
        
        # Always show recent periods (1h, 6h) even if zero
        if total == 0:
            if hours <= 6:
                lines.append(f"⚪️ <b>{label:>4}:</b> No trades")
            continue
        
        has_any_data = True
        
        # Icon based on win rate
        if win_rate >= 60:
            icon = "🟢"
        elif win_rate >= 50:
            icon = "🟡"
        else:
            icon = "🔴"
        
        # Build stats line
        stats = f"{wins}W-{losses}L | {total_pnl:+.2f}% | {avg_duration:.0f}m avg"
        
        lines.append(f"{icon} <b>{label:>4}:</b> {win_rate:.0f}% ({stats})")
    
    if not has_any_data:
        return None
    
    return '\n'.join(lines)

def calculate_next_report_time(target_minute=5):
    """Calculate next scheduled report time (at :05 of next hour)"""
    now = datetime.now()
    
    if now.minute >= target_minute:
        next_hour = now.replace(minute=target_minute, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_hour = now.replace(minute=target_minute, second=0, microsecond=0)
    
    return next_hour

def main():
    """Main reporting loop"""
    REPORT_MINUTE = 5  # Send reports at :05 of each hour
    
    print("="*60, flush=True)
    print("TRADING EFFECTIVENESS REPORTER", flush=True)
    print("="*60, flush=True)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S GMT+3')}", flush=True)
    print(f"Schedule: Every hour at :{REPORT_MINUTE:02d} minutes", flush=True)
    print(f"Channel: {TRADING_CHANNEL_ID}", flush=True)
    print(f"Heartbeat: 60s (keeps workflow alive)", flush=True)
    print("="*60, flush=True)
    
    if not TRADING_CHANNEL_ID:
        print("[ERROR] TRADING_TELEGRAM_CHAT_ID not configured!", flush=True)
        print("[ERROR] Cannot send reports. Exiting...", flush=True)
        return
    
    next_report_time = calculate_next_report_time(REPORT_MINUTE)
    print(f"[SCHEDULE] Next report: {next_report_time.strftime('%H:%M:%S')}", flush=True)
    
    loop_count = 0
    while True:
        try:
            loop_count += 1
            now = datetime.now()
            
            # Check if it's time to send report
            if now >= next_report_time:
                print(f"\n[REPORT] {now.strftime('%H:%M:%S')} - Sending trading effectiveness reports", flush=True)
                
                # Generate PAPER report
                paper_report = format_trading_report('PAPER')
                if paper_report:
                    send_to_trading_channel(paper_report, TRADING_CHANNEL_ID)
                    print(f"[REPORT] ✅ PAPER report sent", flush=True)
                else:
                    print(f"[REPORT] ⚪️ No PAPER data yet", flush=True)
                
                # Small delay between reports
                time.sleep(2)
                
                # Generate LIVE report
                live_report = format_trading_report('LIVE')
                if live_report:
                    send_to_trading_channel(live_report, TRADING_CHANNEL_ID)
                    print(f"[REPORT] ✅ LIVE report sent", flush=True)
                else:
                    print(f"[REPORT] ⚪️ No LIVE data yet", flush=True)
                
                # Schedule next report
                next_report_time = calculate_next_report_time(REPORT_MINUTE)
                print(f"[SCHEDULE] Next report: {next_report_time.strftime('%H:%M:%S')}", flush=True)
            else:
                # Heartbeat to keep workflow alive
                time_until = (next_report_time - now).total_seconds()
                mins_left = int(time_until / 60)
                secs_left = int(time_until % 60)
                print(f"[HEARTBEAT] {now.strftime('%H:%M:%S')} - Next report at {next_report_time.strftime('%H:%M')} ({mins_left}m {secs_left}s)", flush=True)
            
            # Sleep 60 seconds between checks
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n\n[REPORT] Shutting down...", flush=True)
            break
        except Exception as e:
            print(f"[REPORT ERROR] {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(60)

if __name__ == '__main__':
    main()
