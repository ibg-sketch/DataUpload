#!/usr/bin/env python3
"""Simple BTC Correlation Analysis using csv module"""

import csv
from datetime import datetime
from collections import defaultdict
import statistics

# Load data
data_by_symbol = defaultdict(list)
start_time = datetime(2025, 11, 4, 0, 0, 0)

print("Loading data from analysis_log.csv...")
with open('analysis_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            ts = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            if ts >= start_time:
                symbol = row['symbol']
                price = float(row['price'])
                data_by_symbol[symbol].append((ts, price))
        except (ValueError, KeyError) as e:
            continue

# Sort data by timestamp
for symbol in data_by_symbol:
    data_by_symbol[symbol].sort(key=lambda x: x[0])

print(f"\nLoaded data for {len(data_by_symbol)} symbols")
for symbol in sorted(data_by_symbol.keys()):
    print(f"  {symbol}: {len(data_by_symbol[symbol])} data points")

# Calculate BTC changes
if 'BTCUSDT' not in data_by_symbol or len(data_by_symbol['BTCUSDT']) < 2:
    print("\nERROR: Insufficient BTC data")
    exit(1)

btc_data = data_by_symbol['BTCUSDT']
btc_first_price = btc_data[0][1]
btc_last_price = btc_data[-1][1]
btc_change_pct = ((btc_last_price - btc_first_price) / btc_first_price) * 100

print(f"\nBTC: {btc_first_price:.2f} → {btc_last_price:.2f} ({btc_change_pct:+.2f}%)")
print(f"Time period: {btc_data[0][0]} to {btc_data[-1][0]}")
print(f"Duration: {(btc_data[-1][0] - btc_data[0][0]).total_seconds() / 3600:.1f} hours")
print("\n" + "="*80)

# Analyze other coins
results = []
for symbol in sorted(data_by_symbol.keys()):
    if symbol == 'BTCUSDT' or len(data_by_symbol[symbol]) < 2:
        continue
    
    alt_data = data_by_symbol[symbol]
    alt_first_price = alt_data[0][1]
    alt_last_price = alt_data[-1][1]
    alt_change_pct = ((alt_last_price - alt_first_price) / alt_first_price) * 100
    
    # Calculate simple correlation using price changes at each timestamp
    btc_changes = []
    alt_changes = []
    
    # Match timestamps (use closest BTC price for each alt timestamp)
    for i in range(1, len(alt_data)):
        alt_time = alt_data[i][0]
        
        # Find closest BTC timestamp
        closest_btc_idx = min(range(len(btc_data)), 
                             key=lambda j: abs((btc_data[j][0] - alt_time).total_seconds()))
        
        if closest_btc_idx > 0:
            btc_pct = ((btc_data[closest_btc_idx][1] - btc_data[closest_btc_idx-1][1]) / 
                      btc_data[closest_btc_idx-1][1]) * 100
            alt_pct = ((alt_data[i][1] - alt_data[i-1][1]) / alt_data[i-1][1]) * 100
            
            btc_changes.append(btc_pct)
            alt_changes.append(alt_pct)
    
    if len(btc_changes) < 10:
        continue
    
    # Calculate correlation
    btc_mean = statistics.mean(btc_changes)
    alt_mean = statistics.mean(alt_changes)
    
    numerator = sum((b - btc_mean) * (a - alt_mean) 
                   for b, a in zip(btc_changes, alt_changes))
    btc_std = (sum((b - btc_mean)**2 for b in btc_changes)) ** 0.5
    alt_std = (sum((a - alt_mean)**2 for a in alt_changes)) ** 0.5
    
    correlation = numerator / (btc_std * alt_std) if btc_std > 0 and alt_std > 0 else 0
    
    # Calculate beta (alt_change / btc_change ratio)
    beta = alt_change_pct / btc_change_pct if btc_change_pct != 0 else 0
    
    results.append({
        'symbol': symbol,
        'correlation': correlation,
        'beta': beta,
        'alt_change_pct': alt_change_pct,
        'price_ratio': beta,
        'data_points': len(btc_changes)
    })

# Sort by correlation
results.sort(key=lambda x: abs(x['correlation']), reverse=True)

# Print results
print("\n📊 CORRELATION WITH BTC:\n")
print(f"{'Symbol':<12} {'Corr':<8} {'Beta':<8} {'BTC Δ%':<10} {'Alt Δ%':<10} {'Ratio':<8} {'Points'}")
print("-" * 75)

for r in results:
    corr_icon = "🟢" if r['correlation'] > 0.7 else "🟡" if r['correlation'] > 0.4 else "🔴"
    
    print(f"{corr_icon} {r['symbol']:<10} {r['correlation']:>6.3f}  "
          f"{r['beta']:>6.2f}  "
          f"{btc_change_pct:>8.2f}%  "
          f"{r['alt_change_pct']:>8.2f}%  "
          f"{r['price_ratio']:>6.2f}  "
          f"{r['data_points']}")

# Summary
print("\n" + "="*80)
print("\n📈 SUMMARY:\n")

avg_corr = statistics.mean([r['correlation'] for r in results])
avg_beta = statistics.mean([r['beta'] for r in results])

print(f"Average Correlation: {avg_corr:.3f}")
print(f"Average Beta: {avg_beta:.3f}")

# High/Low volatility coins
high_vol = [r for r in results if r['beta'] > 1.2]
low_vol = [r for r in results if r['beta'] < 0.8]

if high_vol:
    print(f"\n⚡ HIGH VOLATILITY (Beta > 1.2):")
    for r in sorted(high_vol, key=lambda x: x['beta'], reverse=True):
        print(f"  • {r['symbol']}: {r['beta']:.2f}x ({r['alt_change_pct']:+.2f}%)")

if low_vol:
    print(f"\n🛡️  LOW VOLATILITY (Beta < 0.8):")
    for r in sorted(low_vol, key=lambda x: x['beta']):
        print(f"  • {r['symbol']}: {r['beta']:.2f}x ({r['alt_change_pct']:+.2f}%)")

# Strong/Weak correlation
strong_corr = [r for r in results if r['correlation'] > 0.7]
weak_corr = [r for r in results if r['correlation'] < 0.4]

if strong_corr:
    print(f"\n💪 STRONG CORRELATION (> 0.7):")
    for r in sorted(strong_corr, key=lambda x: x['correlation'], reverse=True):
        print(f"  • {r['symbol']}: {r['correlation']:.3f}")

if weak_corr:
    print(f"\n🤷 WEAK CORRELATION (< 0.4):")
    for r in sorted(weak_corr, key=lambda x: x['correlation']):
        print(f"  • {r['symbol']}: {r['correlation']:.3f}")

print("\n" + "="*80)
print("\n📝 INTERPRETATION:")
print(f"  • Beta > 1.0: Altcoin moves MORE than BTC (amplified moves)")
print(f"  • Beta = 1.0: Altcoin moves SAME as BTC")
print(f"  • Beta < 1.0: Altcoin moves LESS than BTC (dampened moves)")
print(f"  • Correlation shows how consistently they move together")
