#!/usr/bin/env python3
"""BTC Lag Analysis - Find which coins lead/follow BTC"""

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

def calculate_correlation_with_lag(btc_data, alt_data, lag_minutes):
    """Calculate correlation with time lag"""
    btc_changes = []
    alt_changes = []
    
    for i in range(1, len(alt_data)):
        alt_time = alt_data[i][0]
        # Shift BTC time by lag
        btc_target_time = alt_time - timedelta(minutes=lag_minutes)
        
        # Find closest BTC timestamp
        closest_btc_idx = min(range(len(btc_data)), 
                             key=lambda j: abs((btc_data[j][0] - btc_target_time).total_seconds()))
        
        if closest_btc_idx > 0 and closest_btc_idx < len(btc_data):
            btc_pct = ((btc_data[closest_btc_idx][1] - btc_data[closest_btc_idx-1][1]) / 
                      btc_data[closest_btc_idx-1][1]) * 100
            alt_pct = ((alt_data[i][1] - alt_data[i-1][1]) / alt_data[i-1][1]) * 100
            
            btc_changes.append(btc_pct)
            alt_changes.append(alt_pct)
    
    if len(btc_changes) < 10:
        return None
    
    # Calculate correlation
    btc_mean = statistics.mean(btc_changes)
    alt_mean = statistics.mean(alt_changes)
    
    numerator = sum((b - btc_mean) * (a - alt_mean) 
                   for b, a in zip(btc_changes, alt_changes))
    btc_std = (sum((b - btc_mean)**2 for b in btc_changes)) ** 0.5
    alt_std = (sum((a - alt_mean)**2 for a in alt_changes)) ** 0.5
    
    correlation = numerator / (btc_std * alt_std) if btc_std > 0 and alt_std > 0 else 0
    return correlation

# Analyze lag for each coin
print("\n⏱️  LAG ANALYSIS - Who moves first?\n")
print(f"{'Symbol':<12} {'Best Lag':<12} {'Best Corr':<12} {'0-lag Corr':<12} {'Interpretation'}")
print("-" * 90)

lag_results = []
for symbol in sorted(data_by_symbol.keys()):
    if symbol == 'BTCUSDT' or len(data_by_symbol[symbol]) < 20:
        continue
    
    alt_data = data_by_symbol[symbol]
    
    # Test lags from -30min to +30min (5min intervals)
    best_lag = 0
    best_corr = 0
    zero_lag_corr = 0
    
    for lag in range(-6, 7):  # -30 to +30 minutes
        lag_min = lag * 5
        corr = calculate_correlation_with_lag(btc_data, alt_data, lag_min)
        
        if corr is not None:
            if lag == 0:
                zero_lag_corr = corr
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag_min
    
    if zero_lag_corr == 0:
        continue
    
    # Interpretation
    if best_lag < 0:
        interp = f"LEADS BTC by {abs(best_lag)}min 🏃"
    elif best_lag > 0:
        interp = f"FOLLOWS BTC by {best_lag}min 🐌"
    else:
        interp = "SIMULTANEOUS ⚡"
    
    corr_improvement = abs(best_corr) - abs(zero_lag_corr)
    
    lag_results.append({
        'symbol': symbol,
        'best_lag': best_lag,
        'best_corr': best_corr,
        'zero_corr': zero_lag_corr,
        'improvement': corr_improvement,
        'interp': interp
    })

# Sort by absolute lag
lag_results.sort(key=lambda x: abs(x['best_lag']), reverse=True)

for r in lag_results:
    lag_str = f"{r['best_lag']:+d}min" if r['best_lag'] != 0 else "0min"
    print(f"{r['symbol']:<12} {lag_str:<12} {r['best_corr']:>10.3f}  {r['zero_corr']:>10.3f}  {r['interp']}")

# Summary
print("\n" + "="*90)
print("\n📊 SUMMARY:\n")

leaders = [r for r in lag_results if r['best_lag'] < 0]
followers = [r for r in lag_results if r['best_lag'] > 0]
simultaneous = [r for r in lag_results if r['best_lag'] == 0]

if leaders:
    print(f"🏃 LEADING INDICATORS (move BEFORE BTC):")
    for r in sorted(leaders, key=lambda x: x['best_lag']):
        print(f"  • {r['symbol']}: {abs(r['best_lag'])} minutes ahead (corr: {r['best_corr']:.3f})")

if followers:
    print(f"\n🐌 LAGGING INDICATORS (move AFTER BTC):")
    for r in sorted(followers, key=lambda x: x['best_lag'], reverse=True):
        print(f"  • {r['symbol']}: {r['best_lag']} minutes behind (corr: {r['best_corr']:.3f})")

if simultaneous:
    print(f"\n⚡ SIMULTANEOUS MOVERS:")
    for r in simultaneous:
        print(f"  • {r['symbol']}: No detectable lag (corr: {r['best_corr']:.3f})")

# Significant lag improvement
significant = [r for r in lag_results if r['improvement'] > 0.1]
if significant:
    print(f"\n⚠️  SIGNIFICANT LAG EFFECTS (correlation improves by >0.1 when lag applied):")
    for r in sorted(significant, key=lambda x: x['improvement'], reverse=True):
        print(f"  • {r['symbol']}: {r['zero_corr']:.3f} → {r['best_corr']:.3f} "
              f"(+{r['improvement']:.3f}) at {r['best_lag']:+d}min lag")

print("\n" + "="*90)
print("\n💡 INTERPRETATION:")
print("  • NEGATIVE lag: Coin moves BEFORE BTC (leading indicator)")
print("  • POSITIVE lag: Coin moves AFTER BTC (following/lagging)")
print("  • ZERO lag: Coin moves simultaneously with BTC")
print("  • Larger improvement = time lag is more significant for this coin")
