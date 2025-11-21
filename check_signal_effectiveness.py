"""
Check Signal Effectiveness - Verify if targets were hit
Fetches actual price data after signals to calculate win rate
"""

import csv
import requests
import time
from datetime import datetime, timedelta

def fetch_binance_klines(symbol, interval, start_time, limit=100):
    """Fetch historical klines from Binance"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': int(start_time * 1000),
        'limit': limit
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching klines for {symbol}: {e}")
    return None

def check_target_hit(entry_price, target_min, target_max, verdict, klines):
    """
    Check if target was hit within the klines data
    Returns: (hit, max_profit_pct, hit_time_minutes)
    """
    if not klines:
        return False, 0.0, 0
    
    max_profit = 0.0
    hit = False
    hit_time = 0
    
    for i, kline in enumerate(klines):
        high = float(kline[2])
        low = float(kline[3])
        
        if verdict == 'BUY':
            # For BUY, check if high reached target
            if high >= target_min:
                hit = True
                hit_time = i * 15  # 15min candles
                max_profit = ((high - entry_price) / entry_price) * 100
                break
            # Track maximum loss
            current_profit = ((high - entry_price) / entry_price) * 100
            max_profit = max(max_profit, current_profit)
            
        elif verdict == 'SELL':
            # For SELL, check if low reached target
            if low <= target_max:
                hit = True
                hit_time = i * 15  # 15min candles
                max_profit = ((entry_price - low) / entry_price) * 100
                break
            # Track maximum loss
            current_profit = ((entry_price - low) / entry_price) * 100
            max_profit = max(max_profit, current_profit)
    
    return hit, max_profit, hit_time

def parse_timestamp(ts_str):
    """Parse timestamp string"""
    return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')

def analyze_effectiveness(hours=3):
    """Analyze signal effectiveness by checking actual price movements"""
    
    print("="*70)
    print("SIGNAL EFFECTIVENESS ANALYSIS - Target Hit Verification")
    print("="*70)
    
    # Load signals
    signals = []
    with open('signals_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            signals.append(row)
    
    # Filter to recent signals
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)
    
    recent_signals = []
    for sig in signals:
        sig_time = parse_timestamp(sig['timestamp'])
        # Only check signals that have had time to complete
        if cutoff <= sig_time <= now - timedelta(minutes=15):
            recent_signals.append(sig)
    
    print(f"\nAnalyzing {len(recent_signals)} signals from last {hours} hours")
    print(f"(Excluding last 15 minutes to allow completion time)\n")
    
    wins = 0
    losses = 0
    total_profit = 0.0
    results = []
    
    for i, sig in enumerate(recent_signals):
        if i >= 20:  # Limit to 20 signals to avoid rate limits
            print(f"\nLimiting to first 20 signals to avoid API rate limits...")
            break
            
        symbol = sig['symbol']
        verdict = sig['verdict']
        entry_price = float(sig['entry_price'])
        confidence = float(sig['confidence']) * 100
        sig_time = parse_timestamp(sig['timestamp'])
        
        # Calculate targets from signal data
        # Parse targets from the logged data if available, or estimate
        # For now, estimate based on confidence (simplified)
        if confidence >= 85:
            # Intraday signal
            target_pct = 2.0  # ~2% target for intraday
            duration_mins = 60  # Check 4 hours
        else:
            # Scalping signal
            target_pct = 0.5  # ~0.5% target for scalp
            duration_mins = 60  # Check 1 hour
        
        if verdict == 'BUY':
            target_min = entry_price * (1 + target_pct / 100)
            target_max = entry_price * (1 + target_pct * 1.5 / 100)
        else:
            target_min = entry_price * (1 - target_pct * 1.5 / 100)
            target_max = entry_price * (1 - target_pct / 100)
        
        # Fetch klines after signal
        start_time = sig_time.timestamp()
        klines = fetch_binance_klines(symbol, '15m', start_time, limit=int(duration_mins/15)+1)
        
        if klines:
            hit, profit, hit_time = check_target_hit(entry_price, target_min, target_max, verdict, klines)
            
            if hit:
                wins += 1
                status = "✅ WIN"
            else:
                losses += 1
                status = "❌ LOSS"
            
            total_profit += profit
            
            results.append({
                'symbol': symbol,
                'verdict': verdict,
                'confidence': confidence,
                'entry': entry_price,
                'profit': profit,
                'hit': hit,
                'hit_time': hit_time
            })
            
            print(f"{status} | {symbol:10} {verdict:4} @ {confidence:5.1f}% | Entry: ${entry_price:,.2f} | Profit: {profit:+.2f}% | Time: {hit_time}min")
        else:
            print(f"⚠️  | {symbol:10} {verdict:4} @ {confidence:5.1f}% | Could not fetch price data")
        
        time.sleep(0.2)  # Rate limit protection
    
    # Summary
    total = wins + losses
    if total > 0:
        win_rate = (wins / total) * 100
        avg_profit = total_profit / total
        
        print("\n" + "="*70)
        print("RESULTS SUMMARY")
        print("="*70)
        print(f"Total Signals Checked: {total}")
        print(f"Wins: {wins} ({win_rate:.1f}%)")
        print(f"Losses: {losses} ({100-win_rate:.1f}%)")
        print(f"Average Profit per Trade: {avg_profit:+.2f}%")
        print(f"Total Profit: {total_profit:+.2f}%")
        print("="*70)
        
        # Breakdown by confidence
        print("\n📊 Win Rate by Confidence Level:")
        high_conf = [r for r in results if r['confidence'] >= 80]
        low_conf = [r for r in results if r['confidence'] < 80]
        
        if high_conf:
            high_wins = sum(1 for r in high_conf if r['hit'])
            print(f"  High Confidence (≥80%): {high_wins}/{len(high_conf)} = {high_wins/len(high_conf)*100:.1f}%")
        
        if low_conf:
            low_wins = sum(1 for r in low_conf if r['hit'])
            print(f"  Normal Confidence (<80%): {low_wins}/{len(low_conf)} = {low_wins/len(low_conf)*100:.1f}%")
        
        # Breakdown by verdict
        print("\n📈 Win Rate by Direction:")
        buy_signals = [r for r in results if r['verdict'] == 'BUY']
        sell_signals = [r for r in results if r['verdict'] == 'SELL']
        
        if buy_signals:
            buy_wins = sum(1 for r in buy_signals if r['hit'])
            print(f"  BUY signals: {buy_wins}/{len(buy_signals)} = {buy_wins/len(buy_signals)*100:.1f}%")
        
        if sell_signals:
            sell_wins = sum(1 for r in sell_signals if r['hit'])
            print(f"  SELL signals: {sell_wins}/{len(sell_signals)} = {sell_wins/len(sell_signals)*100:.1f}%")
    else:
        print("\nNo signals to analyze.")

if __name__ == "__main__":
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    analyze_effectiveness(hours)
