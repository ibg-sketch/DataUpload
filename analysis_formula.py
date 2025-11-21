#!/usr/bin/env python3
"""
Formula Analysis - Check weights and correlation with outcomes
"""

import csv
import yaml
import json
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

print("="*80)
print("🔬 FORMULA & WEIGHTS ANALYSIS")
print("="*80)

# Show current weights
print("\n📊 CURRENT FORMULA WEIGHTS (from config.yaml):")
print("-" * 60)

coins = config.get('coins', {})
for coin, weights in coins.items():
    if coin == 'BTCUSDT':
        print(f"\n{coin} (example coin):")
        print(f"  CVD weight:        {weights.get('cvd_weight', 0)}")
        print(f"  OI weight:         {weights.get('oi_weight', 0)}")
        print(f"  VWAP weight:       {weights.get('vwap_weight', 0)}")
        print(f"  RSI weight:        {weights.get('rsi_weight', 0)}")
        print(f"  Liq weight:        {weights.get('liq_weight', 0)}")
        print(f"  Volume weight:     {weights.get('volume_weight', 0)}")
        print(f"  EMA weight:        {weights.get('ema_weight', 0)}")
        print(f"  Funding weight:    {weights.get('funding_weight', 0)}")
        print(f"  ADX weight:        {weights.get('adx_weight', 0)}")
        break

# Load recent signals
signals = []
with open('signals_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        signals.append(row)

# Load effectiveness
effectiveness = {}
with open('effectiveness_log.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        verdict = row.get('verdict', '')
        side = verdict.split()[0] if verdict else ''
        key = f"{row['symbol']}_{side}_{row['timestamp_sent']}"
        effectiveness[key] = {
            'result': row.get('result'),
            'profit_pct': float(row.get('profit_pct', 0)),
        }

# Filter last 48h
now = datetime.now()
cutoff = now - timedelta(hours=48)

recent_data = []
for sig in signals:
    ts = datetime.strptime(sig['timestamp'], '%Y-%m-%d %H:%M:%S')
    if ts >= cutoff:
        verdict = sig.get('verdict', '')
        side = verdict.split()[0] if verdict else ''
        key = f"{sig['symbol']}_{side}_{sig['timestamp']}"
        
        if key in effectiveness:
            recent_data.append({
                'signal': sig,
                'result': effectiveness[key]
            })

print(f"\n📈 Analyzed {len(recent_data)} matched signals")

# Parse components from signals
component_analysis = defaultdict(lambda: {
    'win_scores': [], 'loss_scores': [], 'cancelled_scores': []
})

for item in recent_data:
    sig = item['signal']
    result = item['result']['result']
    
    try:
        components = json.loads(sig.get('components', '{}'))
        
        for comp_name, score in components.items():
            if result == 'WIN':
                component_analysis[comp_name]['win_scores'].append(float(score))
            elif result == 'LOSS':
                component_analysis[comp_name]['loss_scores'].append(float(score))
            elif result == 'CANCELLED':
                component_analysis[comp_name]['cancelled_scores'].append(float(score))
    except:
        pass

print("\n" + "="*80)
print("📊 COMPONENT SCORES by OUTCOME")
print("="*80)
print(f"{'Component':<20} {'WIN Avg':<12} {'LOSS Avg':<12} {'CANCEL Avg':<12} {'Diff':<10}")
print("-" * 70)

for comp_name in sorted(component_analysis.keys()):
    data = component_analysis[comp_name]
    
    win_avg = statistics.mean(data['win_scores']) if data['win_scores'] else 0
    loss_avg = statistics.mean(data['loss_scores']) if data['loss_scores'] else 0
    cancel_avg = statistics.mean(data['cancelled_scores']) if data['cancelled_scores'] else 0
    
    # Calculate difference (WIN - LOSS)
    diff = win_avg - loss_avg
    indicator = "✅" if diff > 0 else "❌"
    
    print(f"{comp_name:<20} {win_avg:>10.2f}  {loss_avg:>10.2f}  {cancel_avg:>10.2f}  {indicator} {diff:>+7.2f}")

# Analyze raw values (OI, VWAP distance)
print("\n" + "="*80)
print("📊 RAW INDICATOR VALUES by OUTCOME")
print("="*80)

raw_indicators = {
    'oi_change': {'win': [], 'loss': [], 'cancelled': []},
    'vwap_distance': {'win': [], 'loss': [], 'cancelled': []},
    'volume_spike': {'win': [], 'loss': [], 'cancelled': []},
}

for item in recent_data:
    sig = item['signal']
    result = item['result']['result']
    result_key = result.lower()
    
    try:
        oi = float(sig.get('oi_change', 0))
        raw_indicators['oi_change'][result_key].append(oi)
        
        entry = float(sig.get('entry_price', 0))
        vwap = float(sig.get('vwap', 0))
        vwap_dist = abs((entry - vwap) / vwap * 100) if vwap else 0
        raw_indicators['vwap_distance'][result_key].append(vwap_dist)
        
        vol = float(sig.get('volume_spike', 0))
        raw_indicators['volume_spike'][result_key].append(vol)
    except:
        pass

print(f"{'Indicator':<20} {'WIN Avg':<12} {'LOSS Avg':<12} {'CANCEL Avg':<12} {'Predictive?':<12}")
print("-" * 75)

for ind_name, data in raw_indicators.items():
    win_avg = statistics.mean(data['win']) if data['win'] else 0
    loss_avg = statistics.mean(data['loss']) if data['loss'] else 0
    cancel_avg = statistics.mean(data['cancelled']) if data['cancelled'] else 0
    
    # Is it predictive? WIN should be different from LOSS
    diff_pct = abs(win_avg - loss_avg) / max(abs(win_avg), abs(loss_avg), 0.01) * 100
    predictive = "✅ YES" if diff_pct > 10 else "❌ NO"
    
    print(f"{ind_name:<20} {win_avg:>10.2f}  {loss_avg:>10.2f}  {cancel_avg:>10.2f}  {predictive}")

# Confidence analysis
print("\n" + "="*80)
print("📊 CONFIDENCE DISTRIBUTION")
print("="*80)

confidence_data = {
    'win': [], 'loss': [], 'cancelled': []
}

for item in recent_data:
    sig = item['signal']
    result = item['result']['result']
    result_key = result.lower()
    
    try:
        conf = float(sig.get('confidence', 0))
        confidence_data[result_key].append(conf)
    except:
        pass

for result_type in ['win', 'loss', 'cancelled']:
    if confidence_data[result_type]:
        avg = statistics.mean(confidence_data[result_type])
        median = statistics.median(confidence_data[result_type])
        min_val = min(confidence_data[result_type])
        max_val = max(confidence_data[result_type])
        
        print(f"\n{result_type.upper()} signals ({len(confidence_data[result_type])} total):")
        print(f"  Average:   {avg:.1f}%")
        print(f"  Median:    {median:.1f}%")
        print(f"  Range:     {min_val:.1f}% - {max_val:.1f}%")

# Verdict score analysis
print("\n" + "="*80)
print("📊 VERDICT SCORE ANALYSIS")
print("="*80)

score_data = {
    'win': [], 'loss': [], 'cancelled': []
}

for item in recent_data:
    sig = item['signal']
    result = item['result']['result']
    result_key = result.lower()
    
    try:
        score = float(sig.get('score', 0))
        score_data[result_key].append(score)
    except:
        pass

print(f"{'Outcome':<12} {'Count':<8} {'Avg Score':<12} {'Med Score':<12} {'Min':<10} {'Max':<10}")
print("-" * 70)

for result_type in ['win', 'loss', 'cancelled']:
    if score_data[result_type]:
        count = len(score_data[result_type])
        avg = statistics.mean(score_data[result_type])
        median = statistics.median(score_data[result_type])
        min_val = min(score_data[result_type])
        max_val = max(score_data[result_type])
        
        print(f"{result_type.upper():<12} {count:<8} {avg:>10.2f}  {median:>10.2f}  {min_val:>8.2f}  {max_val:>8.2f}")

# Score difference analysis
if score_data['win'] and score_data['loss']:
    win_avg = statistics.mean(score_data['win'])
    loss_avg = statistics.mean(score_data['loss'])
    cancel_avg = statistics.mean(score_data['cancelled']) if score_data['cancelled'] else 0
    
    print(f"\n⚠️ CRITICAL FINDING:")
    print(f"  WIN avg score:    {win_avg:.2f}")
    print(f"  LOSS avg score:   {loss_avg:.2f}")
    print(f"  CANCEL avg score: {cancel_avg:.2f}")
    print(f"  Difference:       {win_avg - loss_avg:+.2f}")
    
    if abs(win_avg - loss_avg) < 5:
        print(f"\n❌ FORMULA IS NOT PREDICTIVE!")
        print(f"   Score差 too small ({abs(win_avg - loss_avg):.2f})")
        print(f"   Formula cannot distinguish WIN from LOSS!")

print("\n" + "="*80)
print("📝 ANALYSIS COMPLETE")
print("="*80)
