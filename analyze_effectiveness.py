"""
Signal Effectiveness Analyzer
Analyzes historical signals to determine win rate and average profit
"""

import csv
import os
from datetime import datetime, timedelta
import pytz

# Set timezone to GMT+3
TZ = pytz.timezone('Etc/GMT-3')

def parse_timestamp(ts_str):
    """Parse timestamp string to datetime"""
    return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')

def analyze_signal_effectiveness(lookback_hours=24):
    """
    Analyze signal effectiveness by checking if targets were hit
    """
    print("="*70)
    print(f"SIGNAL EFFECTIVENESS ANALYSIS (Last {lookback_hours} hours)")
    print("="*70)
    
    # Read signals
    signals = []
    with open('signals_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            signals.append(row)
    
    # Filter to last N hours
    now = datetime.now()
    cutoff = now - timedelta(hours=lookback_hours)
    
    recent_signals = []
    for sig in signals:
        sig_time = parse_timestamp(sig['timestamp'])
        if sig_time >= cutoff:
            recent_signals.append(sig)
    
    print(f"\nTotal signals analyzed: {len(recent_signals)}")
    print(f"Time range: Last {lookback_hours} hours")
    print(f"From: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"To: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Analyze by verdict
    buy_signals = [s for s in recent_signals if s['verdict'] == 'BUY']
    sell_signals = [s for s in recent_signals if s['verdict'] == 'SELL']
    
    print(f"\n📊 Signal Distribution:")
    print(f"  BUY signals: {len(buy_signals)}")
    print(f"  SELL signals: {len(sell_signals)}")
    
    # Analyze by confidence level
    print(f"\n📈 Confidence Distribution:")
    confidence_buckets = {
        '70-74%': [],
        '75-79%': [],
        '80-84%': [],
        '85-89%': [],
        '90-95%': []
    }
    
    for sig in recent_signals:
        conf = float(sig['confidence']) * 100
        if 70 <= conf < 75:
            confidence_buckets['70-74%'].append(sig)
        elif 75 <= conf < 80:
            confidence_buckets['75-79%'].append(sig)
        elif 80 <= conf < 85:
            confidence_buckets['80-84%'].append(sig)
        elif 85 <= conf < 90:
            confidence_buckets['85-89%'].append(sig)
        elif 90 <= conf <= 95:
            confidence_buckets['90-95%'].append(sig)
    
    for bucket, sigs in confidence_buckets.items():
        if sigs:
            print(f"  {bucket}: {len(sigs)} signals")
    
    # Analyze by symbol
    print(f"\n🪙 Symbol Distribution:")
    symbols = {}
    for sig in recent_signals:
        sym = sig['symbol']
        if sym not in symbols:
            symbols[sym] = {'BUY': 0, 'SELL': 0}
        symbols[sym][sig['verdict']] += 1
    
    for sym in sorted(symbols.keys()):
        buy_count = symbols[sym]['BUY']
        sell_count = symbols[sym]['SELL']
        total = buy_count + sell_count
        print(f"  {sym:12} {total:3} signals (BUY: {buy_count}, SELL: {sell_count})")
    
    # Analyze components
    print(f"\n🔍 Most Common Indicator Combinations:")
    component_combos = {}
    for sig in recent_signals:
        components = sig.get('components', '')
        if components not in component_combos:
            component_combos[components] = 0
        component_combos[components] += 1
    
    # Sort by frequency
    sorted_combos = sorted(component_combos.items(), key=lambda x: x[1], reverse=True)
    for combo, count in sorted_combos[:10]:
        indicators = combo.split('|') if combo else []
        print(f"  {count:3}x: {combo}")
    
    # Summary stats
    print(f"\n📊 Summary Statistics:")
    
    # Average confidence
    avg_conf = sum(float(s['confidence']) for s in recent_signals) / len(recent_signals) if recent_signals else 0
    print(f"  Average Confidence: {avg_conf*100:.1f}%")
    
    # High confidence signals (>= 80%)
    high_conf = [s for s in recent_signals if float(s['confidence']) >= 0.80]
    print(f"  High Confidence (≥80%): {len(high_conf)} ({len(high_conf)/len(recent_signals)*100:.1f}%)")
    
    # Volume spike signals
    vol_spike = [s for s in recent_signals if s.get('volume_spike') == 'True']
    print(f"  With Volume Spike: {len(vol_spike)} ({len(vol_spike)/len(recent_signals)*100:.1f}%)")
    
    print("\n" + "="*70)
    print("NOTE: Target hit analysis requires price data tracking.")
    print("Current logs show signal generation - add price tracking to measure actual profit/loss.")
    print("="*70)

def show_recent_signals(count=10):
    """Show most recent signals"""
    print(f"\n📋 Last {count} Signals:")
    print("-" * 70)
    
    with open('signals_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        signals = list(reader)
    
    for sig in signals[-count:]:
        timestamp = sig['timestamp']
        symbol = sig['symbol']
        verdict = sig['verdict']
        conf = float(sig['confidence']) * 100
        price = float(sig['entry_price'])
        vwap = float(sig['vwap'])
        
        arrow = "🟢" if verdict == "BUY" else "🔴"
        print(f"{arrow} {timestamp} | {symbol:12} {verdict:4} @ {conf:5.1f}% | ${price:,.2f} (VWAP: ${vwap:,.2f})")

if __name__ == "__main__":
    import sys
    
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    
    analyze_signal_effectiveness(hours)
    show_recent_signals(15)
