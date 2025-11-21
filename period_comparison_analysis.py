#!/usr/bin/env python3
"""
Period Comparison Analysis - Yesterday vs Today
Find what changed and why performance degraded
"""

import csv
import json
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

def parse_ts(ts_str):
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None

# Load all data
signals = []
with open('signals_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        signals.append(row)

effectiveness = {}
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        verdict = row.get('verdict', '')
        side = verdict.split()[0] if verdict else ''
        key = f"{row['symbol']}_{side}_{row['timestamp_sent']}"
        effectiveness[key] = row

# Match signals with results
matched_data = []
for sig in signals:
    verdict = sig.get('verdict', '')
    side = verdict.split()[0] if verdict else ''
    key = f"{sig['symbol']}_{side}_{sig['timestamp']}"
    
    if key in effectiveness:
        matched_data.append({
            'timestamp': parse_ts(sig['timestamp']),
            'symbol': sig['symbol'],
            'side': side,
            'confidence': float(sig.get('confidence', 0)) * 100,  # Convert to %
            'score': float(sig.get('score', 0)),
            'entry_price': float(sig.get('entry_price', 0)),
            'vwap': float(sig.get('vwap', 0)),
            'oi': float(sig.get('oi', 0)),
            'oi_change': float(sig.get('oi_change', 0)),
            'volume_spike': sig.get('volume_spike', 'False') == 'True',
            'components': sig.get('components', ''),
            'result': effectiveness[key].get('result'),
            'profit_pct': float(effectiveness[key].get('profit_pct', 0)),
        })

# Define periods
now = datetime.now()
cutoff_yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
cutoff_yesterday_end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)
cutoff_today_start = now.replace(hour=0, minute=0, second=0)

# Split data by periods
today_data = [d for d in matched_data if d['timestamp'] >= cutoff_today_start]
yesterday_data = [d for d in matched_data if cutoff_yesterday_start <= d['timestamp'] <= cutoff_yesterday_end]

print("="*80)
print("🔬 PERIOD COMPARISON ANALYSIS")
print("="*80)
print(f"\nYesterday (Nov 7): {len(yesterday_data)} signals")
print(f"Today (Nov 8):     {len(today_data)} signals")

# === PERIOD COMPARISON ===
def analyze_period(data, period_name):
    if not data:
        return None
    
    results = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0}
    pnl_list = []
    conf_list = []
    score_list = []
    buy_data = []
    sell_data = []
    
    for d in data:
        results[d['result']] = results.get(d['result'], 0) + 1
        pnl_list.append(d['profit_pct'])
        conf_list.append(d['confidence'])
        score_list.append(d['score'])
        
        if d['side'] == 'BUY':
            buy_data.append(d)
        else:
            sell_data.append(d)
    
    total = sum(results.values())
    wr = (results['WIN'] / total * 100) if total > 0 else 0
    cancel_rate = (results['CANCELLED'] / total * 100) if total > 0 else 0
    
    return {
        'period': period_name,
        'total': total,
        'win': results['WIN'],
        'loss': results['LOSS'],
        'cancelled': results['CANCELLED'],
        'win_rate': wr,
        'cancel_rate': cancel_rate,
        'total_pnl': sum(pnl_list),
        'avg_pnl': statistics.mean(pnl_list) if pnl_list else 0,
        'avg_conf': statistics.mean(conf_list) if conf_list else 0,
        'avg_score': statistics.mean(score_list) if score_list else 0,
        'buy_count': len(buy_data),
        'sell_count': len(sell_data),
        'data': data,
        'buy_data': buy_data,
        'sell_data': sell_data,
    }

yesterday = analyze_period(yesterday_data, "Yesterday")
today = analyze_period(today_data, "Today")

print("\n" + "="*80)
print("📊 OVERALL PERFORMANCE COMPARISON")
print("="*80)

print(f"\n{'Metric':<20} {'Yesterday':<15} {'Today':<15} {'Change':<15}")
print("-" * 70)

if yesterday and today:
    print(f"{'Total Signals':<20} {yesterday['total']:<15} {today['total']:<15} {today['total']-yesterday['total']:+d}")
    print(f"{'Win Rate':<20} {yesterday['win_rate']:<14.1f}% {today['win_rate']:<14.1f}% {today['win_rate']-yesterday['win_rate']:+.1f}%")
    print(f"{'Cancel Rate':<20} {yesterday['cancel_rate']:<14.1f}% {today['cancel_rate']:<14.1f}% {today['cancel_rate']-yesterday['cancel_rate']:+.1f}%")
    print(f"{'Total PnL':<20} {yesterday['total_pnl']:<14.2f}% {today['total_pnl']:<14.2f}% {today['total_pnl']-yesterday['total_pnl']:+.2f}%")
    print(f"{'Avg PnL':<20} {yesterday['avg_pnl']:<14.4f}% {today['avg_pnl']:<14.4f}% {today['avg_pnl']-yesterday['avg_pnl']:+.4f}%")
    print(f"{'Avg Confidence':<20} {yesterday['avg_conf']:<14.1f}% {today['avg_conf']:<14.1f}% {today['avg_conf']-yesterday['avg_conf']:+.1f}%")
    print(f"{'Avg Score':<20} {yesterday['avg_score']:<14.2f} {today['avg_score']:<14.2f} {today['avg_score']-yesterday['avg_score']:+.2f}")
    print(f"{'BUY/SELL Ratio':<20} {yesterday['buy_count']}/{yesterday['sell_count']:<8} {today['buy_count']}/{today['sell_count']:<8}")

# === INDICATOR ANALYSIS ===
print("\n" + "="*80)
print("🔬 INDICATOR CORRELATION - WIN vs LOSS")
print("="*80)

def analyze_indicators(data, period_name):
    win_data = [d for d in data if d['result'] == 'WIN']
    loss_data = [d for d in data if d['result'] == 'LOSS']
    
    if not win_data or not loss_data:
        print(f"\n⚠️ {period_name}: Insufficient data")
        return
    
    win_oi = statistics.mean([d['oi_change'] for d in win_data])
    loss_oi = statistics.mean([d['oi_change'] for d in loss_data])
    
    win_vwap = statistics.mean([abs((d['entry_price'] - d['vwap']) / d['vwap'] * 100) for d in win_data if d['vwap'] > 0])
    loss_vwap = statistics.mean([abs((d['entry_price'] - d['vwap']) / d['vwap'] * 100) for d in loss_data if d['vwap'] > 0])
    
    win_vol = sum([1 for d in win_data if d['volume_spike']]) / len(win_data) * 100
    loss_vol = sum([1 for d in loss_data if d['volume_spike']]) / len(loss_data) * 100
    
    win_conf = statistics.mean([d['confidence'] for d in win_data])
    loss_conf = statistics.mean([d['confidence'] for d in loss_data])
    
    win_score = statistics.mean([d['score'] for d in win_data])
    loss_score = statistics.mean([d['score'] for d in loss_data])
    
    print(f"\n📊 {period_name}:")
    print(f"{'Indicator':<18} {'WIN':<12} {'LOSS':<12} {'Diff':<10} {'Predictive?'}")
    print("-" * 65)
    
    # OI
    oi_diff = abs(win_oi - loss_oi)
    oi_pred = "✅ YES" if oi_diff > 100000 else "❌ NO"
    print(f"{'OI Change':<18} {win_oi:>10,.0f}  {loss_oi:>10,.0f}  {oi_diff:>8,.0f}  {oi_pred}")
    
    # VWAP
    vwap_diff = abs(win_vwap - loss_vwap)
    vwap_pred = "✅ YES" if vwap_diff > 0.15 else "❌ NO"
    print(f"{'VWAP Dist %':<18} {win_vwap:>10.2f}  {loss_vwap:>10.2f}  {vwap_diff:>8.2f}  {vwap_pred}")
    
    # Volume
    vol_diff = abs(win_vol - loss_vol)
    vol_pred = "✅ YES" if vol_diff > 10 else "❌ NO"
    print(f"{'Vol Spike %':<18} {win_vol:>10.1f}  {loss_vol:>10.1f}  {vol_diff:>8.1f}  {vol_pred}")
    
    # Confidence
    conf_diff = abs(win_conf - loss_conf)
    conf_pred = "✅ YES" if conf_diff > 5 else "❌ NO"
    print(f"{'Confidence %':<18} {win_conf:>10.1f}  {loss_conf:>10.1f}  {conf_diff:>8.1f}  {conf_pred}")
    
    # Score
    score_diff = abs(win_score - loss_score)
    score_pred = "✅ YES" if score_diff > 0.3 else "❌ NO"
    score_direction = "✅ WIN>LOSS" if win_score > loss_score else "❌ LOSS>WIN"
    print(f"{'Score':<18} {win_score:>10.2f}  {loss_score:>10.2f}  {score_diff:>8.2f}  {score_pred} {score_direction}")

if yesterday:
    analyze_indicators(yesterday['data'], "YESTERDAY (Nov 7)")
if today:
    analyze_indicators(today['data'], "TODAY (Nov 8)")

# === BUY vs SELL ===
print("\n" + "="*80)
print("🔄 BUY vs SELL BREAKDOWN")
print("="*80)

def analyze_side_detail(data, side_name, period_name):
    if not data:
        return
    
    results = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0}
    for d in data:
        results[d['result']] = results.get(d['result'], 0) + 1
    
    total = sum(results.values())
    if total == 0:
        return
    
    wr = (results['WIN'] / total * 100)
    pnl = sum([d['profit_pct'] for d in data])
    avg_pnl = statistics.mean([d['profit_pct'] for d in data])
    
    print(f"\n{period_name} - {side_name} ({total} signals):")
    print(f"  WIN: {results['WIN']} ({results['WIN']/total*100:.1f}%) | LOSS: {results['LOSS']} ({results['LOSS']/total*100:.1f}%) | CANCELLED: {results['CANCELLED']} ({results['CANCELLED']/total*100:.1f}%)")
    print(f"  Win Rate: {wr:.1f}% | Avg PnL: {avg_pnl:+.4f}% | Total PnL: {pnl:+.2f}%")

if yesterday:
    analyze_side_detail(yesterday['buy_data'], "BUY", "Yesterday")
    analyze_side_detail(yesterday['sell_data'], "SELL", "Yesterday")

if today:
    analyze_side_detail(today['buy_data'], "BUY", "Today")
    analyze_side_detail(today['sell_data'], "SELL", "Today")

# === KEY FINDINGS ===
print("\n" + "="*80)
print("🔍 KEY FINDINGS & ROOT CAUSES")
print("="*80)

if yesterday and today:
    print("\n1. PERFORMANCE CHANGE:")
    wr_change = today['win_rate'] - yesterday['win_rate']
    cancel_change = today['cancel_rate'] - yesterday['cancel_rate']
    pnl_change = today['avg_pnl'] - yesterday['avg_pnl']
    
    if wr_change < -5:
        print(f"   ❌ Win Rate DROPPED {wr_change:.1f}%")
    if cancel_change > 5:
        print(f"   ❌ Cancellation INCREASED {cancel_change:+.1f}%")
    if pnl_change < -0.05:
        print(f"   ❌ Avg PnL DROPPED {pnl_change:+.4f}%")
    
    print("\n2. BUY/SELL IMBALANCE:")
    yesterday_ratio = yesterday['sell_count'] / yesterday['buy_count'] if yesterday['buy_count'] > 0 else 0
    today_ratio = today['sell_count'] / today['buy_count'] if today['buy_count'] > 0 else 0
    
    print(f"   Yesterday: {yesterday['sell_count']} SELL / {yesterday['buy_count']} BUY = {yesterday_ratio:.1f}x")
    print(f"   Today:     {today['sell_count']} SELL / {today['buy_count']} BUY = {today_ratio:.1f}x")
    
    if today_ratio > yesterday_ratio * 1.2:
        print(f"   ❌ TOO MANY SELL signals today (ratio increased)")
    
    print("\n3. SIGNAL QUALITY:")
    if today['avg_conf'] < yesterday['avg_conf']:
        print(f"   ❌ Confidence DECREASED ({today['avg_conf']:.1f}% vs {yesterday['avg_conf']:.1f}%)")
    
    # Analyze yesterday vs today indicators
    yesterday_win = [d for d in yesterday['data'] if d['result'] == 'WIN']
    yesterday_loss = [d for d in yesterday['data'] if d['result'] == 'LOSS']
    today_win = [d for d in today['data'] if d['result'] == 'WIN']
    today_loss = [d for d in today['data'] if d['result'] == 'LOSS']
    
    if yesterday_win and yesterday_loss and today_win and today_loss:
        y_score_diff = abs(statistics.mean([d['score'] for d in yesterday_win]) - statistics.mean([d['score'] for d in yesterday_loss]))
        t_score_diff = abs(statistics.mean([d['score'] for d in today_win]) - statistics.mean([d['score'] for d in today_loss]))
        
        print(f"\n4. FORMULA PREDICTIVENESS:")
        print(f"   Yesterday: WIN/LOSS score difference = {y_score_diff:.2f}")
        print(f"   Today:     WIN/LOSS score difference = {t_score_diff:.2f}")
        
        if t_score_diff < y_score_diff:
            print(f"   ❌ Formula became LESS predictive today")
        if t_score_diff < 0.2:
            print(f"   ❌ Formula CANNOT distinguish WIN from LOSS (diff < 0.2)")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE")
print("="*80)
