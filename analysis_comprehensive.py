#!/usr/bin/env python3
"""
Comprehensive Signal Analysis
Analyzes signal effectiveness, formula correlations, and market patterns
"""

import csv
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Parse timestamp
def parse_ts(ts_str):
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Load effectiveness log
effectiveness_data = []
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        effectiveness_data.append(row)

# Load signals log
signals_data = []
with open('signals_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        signals_data.append(row)

# Filter last 48 hours
now = datetime.now()
cutoff_48h = now - timedelta(hours=48)
cutoff_24h = now - timedelta(hours=24)

print("="*80)
print("📊 COMPREHENSIVE SIGNAL ANALYSIS - Last 48 Hours")
print("="*80)
print(f"Analysis time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Period: {cutoff_48h.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')}")
print("="*80)

# Filter data
recent_effectiveness = []
for row in effectiveness_data:
    ts = parse_ts(row.get('timestamp_sent', ''))
    if ts and ts >= cutoff_48h:
        recent_effectiveness.append(row)

recent_signals = []
for row in signals_data:
    ts = parse_ts(row.get('timestamp', ''))
    if ts and ts >= cutoff_48h:
        recent_signals.append(row)

print(f"\n📈 Data Volume:")
print(f"  Total signals analyzed: {len(recent_signals)}")
print(f"  Completed signals: {len(recent_effectiveness)}")

# === 1. OVERALL EFFECTIVENESS ===
print("\n" + "="*80)
print("🎯 1. OVERALL EFFECTIVENESS")
print("="*80)

results_48h = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0}
results_24h = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0}
pnl_48h = []
pnl_24h = []

for row in recent_effectiveness:
    ts = parse_ts(row.get('timestamp_sent', ''))
    result = row.get('result', '')
    pnl = float(row.get('profit_pct', 0))
    
    results_48h[result] = results_48h.get(result, 0) + 1
    pnl_48h.append(pnl)
    
    if ts >= cutoff_24h:
        results_24h[result] = results_24h.get(result, 0) + 1
        pnl_24h.append(pnl)

total_48h = sum(results_48h.values())
total_24h = sum(results_24h.values())

if total_48h > 0:
    wr_48h = (results_48h['WIN'] / total_48h) * 100
    cancel_rate_48h = (results_48h['CANCELLED'] / total_48h) * 100
    avg_pnl_48h = statistics.mean(pnl_48h) if pnl_48h else 0
    
    print(f"\n📊 Last 48 Hours ({total_48h} signals):")
    print(f"  ✅ WIN:       {results_48h['WIN']:4d} ({results_48h['WIN']/total_48h*100:.1f}%)")
    print(f"  ❌ LOSS:      {results_48h['LOSS']:4d} ({results_48h['LOSS']/total_48h*100:.1f}%)")
    print(f"  🚫 CANCELLED: {results_48h['CANCELLED']:4d} ({cancel_rate_48h:.1f}%)")
    print(f"  📈 Win Rate:  {wr_48h:.1f}%")
    print(f"  💰 Avg PnL:   {avg_pnl_48h:+.3f}%")
    print(f"  💵 Total PnL: {sum(pnl_48h):+.2f}%")

if total_24h > 0:
    wr_24h = (results_24h['WIN'] / total_24h) * 100
    cancel_rate_24h = (results_24h['CANCELLED'] / total_24h) * 100
    avg_pnl_24h = statistics.mean(pnl_24h) if pnl_24h else 0
    
    print(f"\n📊 Last 24 Hours ({total_24h} signals):")
    print(f"  ✅ WIN:       {results_24h['WIN']:4d} ({results_24h['WIN']/total_24h*100:.1f}%)")
    print(f"  ❌ LOSS:      {results_24h['LOSS']:4d} ({results_24h['LOSS']/total_24h*100:.1f}%)")
    print(f"  🚫 CANCELLED: {results_24h['CANCELLED']:4d} ({cancel_rate_24h:.1f}%)")
    print(f"  📈 Win Rate:  {wr_24h:.1f}%")
    print(f"  💰 Avg PnL:   {avg_pnl_24h:+.3f}%")
    print(f"  💵 Total PnL: {sum(pnl_24h):+.2f}%")

# === 2. CANCELLATION ANALYSIS ===
print("\n" + "="*80)
print("🚫 2. CANCELLATION PATTERN ANALYSIS")
print("="*80)

cancelled_signals = [row for row in recent_effectiveness if row.get('result') == 'CANCELLED']
print(f"\nTotal cancelled: {len(cancelled_signals)}")

# Time to cancellation
cancel_times = []
for row in cancelled_signals:
    ts_sent = parse_ts(row.get('timestamp_sent', ''))
    ts_checked = parse_ts(row.get('timestamp_checked', ''))
    if ts_sent and ts_checked:
        delta = (ts_checked - ts_sent).total_seconds() / 60
        cancel_times.append(delta)

if cancel_times:
    print(f"\n⏱️ Time Until Cancellation:")
    print(f"  Average: {statistics.mean(cancel_times):.1f} minutes")
    print(f"  Median:  {statistics.median(cancel_times):.1f} minutes")
    print(f"  Min:     {min(cancel_times):.1f} minutes")
    print(f"  Max:     {max(cancel_times):.1f} minutes")
    
    # Distribution
    quick_cancel = len([t for t in cancel_times if t <= 5])
    early_cancel = len([t for t in cancel_times if 5 < t <= 15])
    late_cancel = len([t for t in cancel_times if t > 15])
    
    print(f"\n📊 Distribution:")
    print(f"  ⚡ Quick (<= 5 min):  {quick_cancel:3d} ({quick_cancel/len(cancel_times)*100:.1f}%)")
    print(f"  🕐 Early (5-15 min):  {early_cancel:3d} ({early_cancel/len(cancel_times)*100:.1f}%)")
    print(f"  🕑 Late (> 15 min):   {late_cancel:3d} ({late_cancel/len(cancel_times)*100:.1f}%)")

# === 3. CONFIDENCE ANALYSIS ===
print("\n" + "="*80)
print("📊 3. CONFIDENCE vs EFFECTIVENESS")
print("="*80)

confidence_buckets = {
    '50-60%': {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []},
    '60-70%': {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []},
    '70-80%': {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []},
    '80-90%': {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []},
    '90%+':   {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []},
}

for row in recent_effectiveness:
    try:
        conf = float(row.get('confidence', 0))
        result = row.get('result', '')
        pnl = float(row.get('profit_pct', 0))
        
        if conf >= 90:
            bucket = '90%+'
        elif conf >= 80:
            bucket = '80-90%'
        elif conf >= 70:
            bucket = '70-80%'
        elif conf >= 60:
            bucket = '60-70%'
        else:
            bucket = '50-60%'
        
        if result == 'WIN':
            confidence_buckets[bucket]['win'] += 1
        elif result == 'LOSS':
            confidence_buckets[bucket]['loss'] += 1
        elif result == 'CANCELLED':
            confidence_buckets[bucket]['cancelled'] += 1
        
        confidence_buckets[bucket]['pnl'].append(pnl)
    except:
        pass

print("\n📊 Performance by Confidence Level:")
print(f"{'Confidence':<12} {'Total':<8} {'Win Rate':<10} {'Cancel':<10} {'Avg PnL':<10}")
print("-" * 60)

for bucket_name in ['50-60%', '60-70%', '70-80%', '80-90%', '90%+']:
    data = confidence_buckets[bucket_name]
    total = data['win'] + data['loss'] + data['cancelled']
    
    if total > 0:
        wr = (data['win'] / total) * 100
        cr = (data['cancelled'] / total) * 100
        avg_pnl = statistics.mean(data['pnl']) if data['pnl'] else 0
        
        print(f"{bucket_name:<12} {total:<8} {wr:>6.1f}%    {cr:>6.1f}%    {avg_pnl:>+7.3f}%")

# === 4. SIDE ANALYSIS (BUY vs SELL) ===
print("\n" + "="*80)
print("🔄 4. BUY vs SELL PERFORMANCE")
print("="*80)

buy_stats = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0, 'pnl': []}
sell_stats = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0, 'pnl': []}

for row in recent_effectiveness:
    # Extract side from verdict
    verdict = row.get('verdict', '')
    side = verdict.split()[0] if verdict else ''
    result = row.get('result', '')
    pnl = float(row.get('profit_pct', 0))
    
    if side == 'BUY':
        buy_stats[result] = buy_stats.get(result, 0) + 1
        buy_stats['pnl'].append(pnl)
    elif side == 'SELL':
        sell_stats[result] = sell_stats.get(result, 0) + 1
        sell_stats['pnl'].append(pnl)

for side_name, stats in [('BUY', buy_stats), ('SELL', sell_stats)]:
    total = stats['WIN'] + stats['LOSS'] + stats['CANCELLED']
    if total > 0:
        wr = (stats['WIN'] / total) * 100
        cr = (stats['CANCELLED'] / total) * 100
        avg_pnl = statistics.mean(stats['pnl']) if stats['pnl'] else 0
        
        print(f"\n{side_name} Signals ({total} total):")
        print(f"  ✅ WIN:       {stats['WIN']:3d} ({stats['WIN']/total*100:.1f}%)")
        print(f"  ❌ LOSS:      {stats['LOSS']:3d} ({stats['LOSS']/total*100:.1f}%)")
        print(f"  🚫 CANCELLED: {stats['CANCELLED']:3d} ({cr:.1f}%)")
        print(f"  📈 Win Rate:  {wr:.1f}%")
        print(f"  💰 Avg PnL:   {avg_pnl:+.3f}%")
        print(f"  💵 Total PnL: {sum(stats['pnl']):+.2f}%")

# === 5. INDICATOR CORRELATION ANALYSIS ===
print("\n" + "="*80)
print("🔬 5. INDICATOR CORRELATION with WIN/LOSS")
print("="*80)

# Collect indicator data from signals
indicator_data = {
    'cvd': {'win': [], 'loss': [], 'cancelled': []},
    'oi_change': {'win': [], 'loss': [], 'cancelled': []},
    'vwap_dist': {'win': [], 'loss': [], 'cancelled': []},
    'rsi': {'win': [], 'loss': [], 'cancelled': []},
    'volume_change': {'win': [], 'loss': [], 'cancelled': []},
}

# Match signals with results
signal_results = {}
for row in recent_effectiveness:
    # Extract side from verdict (e.g., "BUY @ 52%" -> "BUY")
    verdict = row.get('verdict', '')
    side = verdict.split()[0] if verdict else ''
    key = f"{row['symbol']}_{side}_{row['timestamp_sent']}"
    signal_results[key] = row['result']

for sig in recent_signals:
    # Extract side from verdict
    verdict = sig.get('verdict', '')
    side = verdict.split()[0] if verdict else ''
    key = f"{sig['symbol']}_{side}_{sig['timestamp']}"
    result = signal_results.get(key)
    
    if result and result in ['WIN', 'LOSS', 'CANCELLED']:
        try:
            # Parse components JSON to get CVD and RSI
            import json
            components_str = sig.get('components', '{}')
            components = json.loads(components_str) if components_str else {}
            
            cvd = float(components.get('cvd_score', 0))
            oi = float(sig.get('oi_change', 0))
            vwap_entry = float(sig.get('entry_price', 0))
            vwap_val = float(sig.get('vwap', 0))
            vwap = abs((vwap_entry - vwap_val) / vwap_val * 100) if vwap_val else 0
            rsi = float(components.get('rsi_score', 0))
            vol = float(sig.get('volume_spike', 0))
            
            result_key = result.lower()
            indicator_data['cvd'][result_key].append(cvd)
            indicator_data['oi_change'][result_key].append(oi)
            indicator_data['vwap_dist'][result_key].append(vwap)
            indicator_data['rsi'][result_key].append(rsi)
            indicator_data['volume_change'][result_key].append(vol)
        except:
            pass

print("\n📊 Average Indicator Values by Outcome:")
print(f"{'Indicator':<20} {'WIN':<15} {'LOSS':<15} {'CANCELLED':<15}")
print("-" * 65)

for ind_name, data in indicator_data.items():
    win_avg = statistics.mean(data['win']) if data['win'] else 0
    loss_avg = statistics.mean(data['loss']) if data['loss'] else 0
    cancel_avg = statistics.mean(data['cancelled']) if data['cancelled'] else 0
    
    print(f"{ind_name:<20} {win_avg:>12.2f}   {loss_avg:>12.2f}   {cancel_avg:>12.2f}")

# === 6. HOURLY PATTERN ANALYSIS ===
print("\n" + "="*80)
print("🕐 6. HOURLY PERFORMANCE PATTERNS")
print("="*80)

hourly_stats = defaultdict(lambda: {'win': 0, 'loss': 0, 'cancelled': 0, 'total': 0})

for row in recent_effectiveness:
    ts = parse_ts(row.get('timestamp_sent', ''))
    if ts:
        hour = ts.hour
        result = row.get('result', '')
        
        hourly_stats[hour]['total'] += 1
        if result == 'WIN':
            hourly_stats[hour]['win'] += 1
        elif result == 'LOSS':
            hourly_stats[hour]['loss'] += 1
        elif result == 'CANCELLED':
            hourly_stats[hour]['cancelled'] += 1

print("\n📊 Performance by Hour (GMT+3):")
print(f"{'Hour':<6} {'Total':<8} {'Win Rate':<12} {'Cancel Rate':<12}")
print("-" * 40)

sorted_hours = sorted(hourly_stats.keys())
for hour in sorted_hours:
    stats = hourly_stats[hour]
    total = stats['total']
    wr = (stats['win'] / total * 100) if total > 0 else 0
    cr = (stats['cancelled'] / total * 100) if total > 0 else 0
    
    print(f"{hour:02d}:00  {total:<8} {wr:>7.1f}%      {cr:>7.1f}%")

# === 7. SYMBOL ANALYSIS ===
print("\n" + "="*80)
print("💎 7. SYMBOL PERFORMANCE")
print("="*80)

symbol_stats = defaultdict(lambda: {'win': 0, 'loss': 0, 'cancelled': 0, 'pnl': []})

for row in recent_effectiveness:
    symbol = row.get('symbol', '')
    result = row.get('result', '')
    pnl = float(row.get('profit_pct', 0))
    
    if result == 'WIN':
        symbol_stats[symbol]['win'] += 1
    elif result == 'LOSS':
        symbol_stats[symbol]['loss'] += 1
    elif result == 'CANCELLED':
        symbol_stats[symbol]['cancelled'] += 1
    
    symbol_stats[symbol]['pnl'].append(pnl)

print("\n📊 Top Performers:")
print(f"{'Symbol':<12} {'Total':<8} {'Win Rate':<12} {'Avg PnL':<12}")
print("-" * 50)

symbol_list = []
for symbol, stats in symbol_stats.items():
    total = stats['win'] + stats['loss'] + stats['cancelled']
    wr = (stats['win'] / total * 100) if total > 0 else 0
    avg_pnl = statistics.mean(stats['pnl']) if stats['pnl'] else 0
    symbol_list.append((symbol, total, wr, avg_pnl))

symbol_list.sort(key=lambda x: x[3], reverse=True)

for symbol, total, wr, avg_pnl in symbol_list[:11]:
    print(f"{symbol:<12} {total:<8} {wr:>7.1f}%      {avg_pnl:>+7.3f}%")

# === 8. REGIME ANALYSIS ===
print("\n" + "="*80)
print("🌊 8. MARKET REGIME PERFORMANCE")
print("="*80)

regime_stats = defaultdict(lambda: {'win': 0, 'loss': 0, 'cancelled': 0, 'total': 0})

for sig in recent_signals:
    key = f"{sig['symbol']}_{sig['side']}_{sig['timestamp']}"
    result = signal_results.get(key)
    
    if result:
        regime = sig.get('regime', 'unknown')
        regime_stats[regime]['total'] += 1
        
        if result == 'WIN':
            regime_stats[regime]['win'] += 1
        elif result == 'LOSS':
            regime_stats[regime]['loss'] += 1
        elif result == 'CANCELLED':
            regime_stats[regime]['cancelled'] += 1

print("\n📊 Performance by Market Regime:")
print(f"{'Regime':<20} {'Total':<8} {'Win Rate':<12} {'Cancel Rate':<12}")
print("-" * 55)

for regime in sorted(regime_stats.keys()):
    stats = regime_stats[regime]
    total = stats['total']
    wr = (stats['win'] / total * 100) if total > 0 else 0
    cr = (stats['cancelled'] / total * 100) if total > 0 else 0
    
    print(f"{regime:<20} {total:<8} {wr:>7.1f}%      {cr:>7.1f}%")

print("\n" + "="*80)
print("📝 ANALYSIS COMPLETE")
print("="*80)
