#!/usr/bin/env python3
"""Fast BTC Lag Analysis - key lags only"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Load data
data_by_symbol = defaultdict(list)
start_time = datetime(2025, 11, 4, 0, 0, 0)

with open('analysis_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            ts = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            if ts >= start_time:
                symbol = row['symbol']
                price = float(row['price'])
                data_by_symbol[symbol].append((ts, price))
        except (ValueError, KeyError):
            continue

# Sort data
for symbol in data_by_symbol:
    data_by_symbol[symbol].sort(key=lambda x: x[0])

btc_data = data_by_symbol['BTCUSDT']

def simple_correlation(btc_changes, alt_changes):
    """Calculate simple correlation"""
    if len(btc_changes) < 10:
        return None
    
    btc_mean = statistics.mean(btc_changes)
    alt_mean = statistics.mean(alt_changes)
    
    numerator = sum((b - btc_mean) * (a - alt_mean) 
                   for b, a in zip(btc_changes, alt_changes))
    btc_std = (sum((b - btc_mean)**2 for b in btc_changes)) ** 0.5
    alt_std = (sum((a - alt_mean)**2 for a in alt_changes)) ** 0.5
    
    return numerator / (btc_std * alt_std) if btc_std > 0 and alt_std > 0 else 0

print("\n⏱️  FAST LAG ANALYSIS\n")
print("Testing key lags: 0, ±2, ±4, ±6, ±8, ±10 minutes\n")
print(f"{'Symbol':<12} {'0min':<8} {'-2min':<8} {'+2min':<8} {'-4min':<8} {'+4min':<8} {'Best':<8} {'Best Lag':<12}")
print("-" * 90)

for symbol in sorted(data_by_symbol.keys()):
    if symbol == 'BTCUSDT' or len(data_by_symbol[symbol]) < 20:
        continue
    
    alt_data = data_by_symbol[symbol]
    
    # Test only key lags: 0, ±2, ±4, ±6, ±8, ±10
    test_lags = [0, -2, 2, -4, 4, -6, 6, -8, 8, -10, 10]
    correlations = {}
    
    for lag_min in test_lags:
        btc_changes = []
        alt_changes = []
        
        for i in range(1, min(len(alt_data), 400)):  # Limit to 400 points for speed
            alt_time = alt_data[i][0]
            btc_target_time = alt_time - timedelta(minutes=lag_min)
            
            # Find closest BTC timestamp (within 3 minutes)
            candidates = [(j, abs((btc_data[j][0] - btc_target_time).total_seconds())) 
                         for j in range(len(btc_data))]
            closest_btc_idx, time_diff = min(candidates, key=lambda x: x[1])
            
            if time_diff > 180:  # Skip if more than 3 minutes off
                continue
            
            if closest_btc_idx > 0 and closest_btc_idx < len(btc_data):
                btc_pct = ((btc_data[closest_btc_idx][1] - btc_data[closest_btc_idx-1][1]) / 
                          btc_data[closest_btc_idx-1][1]) * 100
                alt_pct = ((alt_data[i][1] - alt_data[i-1][1]) / alt_data[i-1][1]) * 100
                
                btc_changes.append(btc_pct)
                alt_changes.append(alt_pct)
        
        corr = simple_correlation(btc_changes, alt_changes)
        if corr is not None:
            correlations[lag_min] = corr
    
    if not correlations:
        continue
    
    # Find best
    best_lag = max(correlations.keys(), key=lambda k: abs(correlations[k]))
    best_corr = correlations[best_lag]
    
    lag_str = f"{best_lag:+d}min" if best_lag != 0 else "0min"
    
    print(f"{symbol:<12} "
          f"{correlations.get(0, 0):>6.3f}  "
          f"{correlations.get(-2, 0):>6.3f}  "
          f"{correlations.get(2, 0):>6.3f}  "
          f"{correlations.get(-4, 0):>6.3f}  "
          f"{correlations.get(4, 0):>6.3f}  "
          f"{best_corr:>6.3f}  "
          f"{lag_str:<12}")

print("\n" + "="*90)
print("\n💡 INTERPRETATION:")
print("  • Negative lag (-2, -4...): Alt moves BEFORE BTC")
print("  • Zero lag (0): Alt moves WITH BTC simultaneously")
print("  • Positive lag (+2, +4...): Alt moves AFTER BTC")
print("  • Best: Lag that gives highest absolute correlation")
print("  • Data precision: 2 minutes (bot collects every 2min)")
