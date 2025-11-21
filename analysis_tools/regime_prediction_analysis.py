#!/usr/bin/env python3
"""
Market Regime Prediction Analysis
Identifies leading indicators for high-WR periods
"""

import csv
from collections import defaultdict
from datetime import datetime, timedelta

def safe_float(val):
    try:
        return float(val) if val and val != '' else 0.0
    except:
        return 0.0

def parse_timestamp(ts):
    """Parse timestamp to datetime"""
    try:
        return datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
    except:
        return None

def load_all_signals_chronological():
    """Load ALL signals (including NO_TRADE) chronologically"""
    signals = []
    
    with open('effectiveness_log.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get('timestamp_sent', '')
            if ts.startswith('2025-11'):
                dt = parse_timestamp(ts)
                if dt:
                    row['datetime'] = dt
                    signals.append(row)
    
    # Sort chronologically
    signals.sort(key=lambda x: x['datetime'])
    return signals

def calculate_rolling_winrate(signals, window_size=20):
    """Calculate rolling win rate for each signal"""
    
    results = []
    
    for i in range(len(signals)):
        # Look back at previous N completed trades
        lookback = []
        j = i - 1
        
        while len(lookback) < window_size and j >= 0:
            if signals[j].get('result') in ['WIN', 'LOSS']:
                lookback.append(signals[j])
            j -= 1
        
        if len(lookback) >= 10:  # Min sample
            wins = sum(1 for s in lookback if s['result'] == 'WIN')
            wr = wins / len(lookback) * 100
            
            results.append({
                'index': i,
                'timestamp': signals[i]['timestamp_sent'],
                'rolling_wr': wr,
                'sample_size': len(lookback),
                'signal': signals[i]
            })
    
    return results

def identify_regime_changes(rolling_data, threshold_high=65, threshold_low=45):
    """Identify when market enters/exits high-WR regime"""
    
    regime_changes = []
    current_regime = 'UNKNOWN'
    
    for i in range(1, len(rolling_data)):
        prev_wr = rolling_data[i-1]['rolling_wr']
        curr_wr = rolling_data[i]['rolling_wr']
        
        # Entering HIGH regime
        if prev_wr < threshold_high and curr_wr >= threshold_high and current_regime != 'HIGH':
            regime_changes.append({
                'type': 'ENTER_HIGH',
                'timestamp': rolling_data[i]['timestamp'],
                'wr_before': prev_wr,
                'wr_after': curr_wr,
                'index': i
            })
            current_regime = 'HIGH'
        
        # Exiting HIGH regime
        elif prev_wr >= threshold_high and curr_wr < threshold_high and current_regime == 'HIGH':
            regime_changes.append({
                'type': 'EXIT_HIGH',
                'timestamp': rolling_data[i]['timestamp'],
                'wr_before': prev_wr,
                'wr_after': curr_wr,
                'index': i
            })
            current_regime = 'MEDIUM'
        
        # Entering LOW regime
        elif prev_wr > threshold_low and curr_wr <= threshold_low and current_regime != 'LOW':
            regime_changes.append({
                'type': 'ENTER_LOW',
                'timestamp': rolling_data[i]['timestamp'],
                'wr_before': prev_wr,
                'wr_after': curr_wr,
                'index': i
            })
            current_regime = 'LOW'
        
        # Exiting LOW regime
        elif prev_wr <= threshold_low and curr_wr > threshold_low and current_regime == 'LOW':
            regime_changes.append({
                'type': 'EXIT_LOW',
                'timestamp': rolling_data[i]['timestamp'],
                'wr_before': prev_wr,
                'wr_after': curr_wr,
                'index': i
            })
            current_regime = 'MEDIUM'
    
    return regime_changes

def analyze_pre_high_regime_indicators(signals, regime_changes, rolling_data):
    """Analyze indicators BEFORE entering high-WR regime"""
    
    enter_high_events = [rc for rc in regime_changes if rc['type'] == 'ENTER_HIGH']
    
    pre_indicators = []
    
    for event in enter_high_events:
        idx = event['index']
        
        # Look at 10 signals BEFORE the regime change
        lookback_range = range(max(0, idx-10), idx)
        
        lookback_signals = [rolling_data[i]['signal'] for i in lookback_range 
                           if rolling_data[i]['signal'].get('result') in ['WIN', 'LOSS']]
        
        if len(lookback_signals) >= 5:
            # Calculate pre-regime characteristics
            wins = sum(1 for s in lookback_signals if s['result'] == 'WIN')
            pre_wr = wins / len(lookback_signals) * 100
            
            avg_conf = sum(safe_float(s.get('confidence')) for s in lookback_signals) / len(lookback_signals)
            avg_strength = sum(safe_float(s.get('market_strength')) for s in lookback_signals) / len(lookback_signals)
            
            # Count verdicts
            buy_count = sum(1 for s in lookback_signals if s.get('verdict') == 'BUY')
            sell_count = sum(1 for s in lookback_signals if s.get('verdict') == 'SELL')
            
            pre_indicators.append({
                'timestamp': event['timestamp'],
                'pre_wr': pre_wr,
                'avg_conf': avg_conf,
                'avg_strength': avg_strength,
                'buy_ratio': buy_count / len(lookback_signals) if lookback_signals else 0,
                'sell_ratio': sell_count / len(lookback_signals) if lookback_signals else 0,
                'sample_size': len(lookback_signals)
            })
    
    return pre_indicators

def analyze_high_regime_duration(regime_changes, rolling_data):
    """Analyze how long high-WR regimes last"""
    
    durations = []
    
    enter_events = [rc for rc in regime_changes if rc['type'] == 'ENTER_HIGH']
    exit_events = [rc for rc in regime_changes if rc['type'] == 'EXIT_HIGH']
    
    for enter in enter_events:
        # Find corresponding exit
        exit_event = None
        for exit in exit_events:
            if exit['index'] > enter['index']:
                exit_event = exit
                break
        
        if exit_event:
            enter_dt = parse_timestamp(enter['timestamp'])
            exit_dt = parse_timestamp(exit_event['timestamp'])
            
            if enter_dt and exit_dt:
                duration = (exit_dt - enter_dt).total_seconds() / 3600  # hours
                
                # Count signals in this period
                signals_in_period = [rd for rd in rolling_data 
                                    if rd['index'] >= enter['index'] and rd['index'] < exit_event['index']]
                
                durations.append({
                    'enter_time': enter['timestamp'],
                    'exit_time': exit_event['timestamp'],
                    'duration_hours': duration,
                    'signals_count': len(signals_in_period),
                    'enter_wr': enter['wr_after'],
                    'exit_wr': exit_event['wr_before']
                })
    
    return durations

def find_time_patterns_in_regimes(regime_changes):
    """Find time-of-day patterns for regime changes"""
    
    by_hour = defaultdict(lambda: {'enter_high': 0, 'exit_high': 0, 'enter_low': 0, 'exit_low': 0})
    
    for rc in regime_changes:
        hour = rc['timestamp'][11:13]
        
        if rc['type'] == 'ENTER_HIGH':
            by_hour[hour]['enter_high'] += 1
        elif rc['type'] == 'EXIT_HIGH':
            by_hour[hour]['exit_high'] += 1
        elif rc['type'] == 'ENTER_LOW':
            by_hour[hour]['enter_low'] += 1
        elif rc['type'] == 'EXIT_LOW':
            by_hour[hour]['exit_low'] += 1
    
    return by_hour

def main():
    print("=" * 100)
    print("MARKET REGIME PREDICTION ANALYSIS")
    print("Can we predict high-WR periods BEFORE they happen?")
    print("=" * 100)
    
    # Load data
    print("\n📊 Loading chronological signal data...")
    signals = load_all_signals_chronological()
    print(f"   Loaded {len(signals)} signals")
    
    # Calculate rolling win rate
    print("\n🔄 Calculating rolling 20-signal win rate...")
    rolling_data = calculate_rolling_winrate(signals, window_size=20)
    print(f"   Calculated for {len(rolling_data)} data points")
    
    # Identify regime changes
    print("\n🎯 Identifying regime changes (threshold: 65% high, 45% low)...")
    regime_changes = identify_regime_changes(rolling_data, threshold_high=65, threshold_low=45)
    
    enter_high = [rc for rc in regime_changes if rc['type'] == 'ENTER_HIGH']
    exit_high = [rc for rc in regime_changes if rc['type'] == 'EXIT_HIGH']
    
    print(f"   Found {len(enter_high)} entries into HIGH regime")
    print(f"   Found {len(exit_high)} exits from HIGH regime")
    
    # Section 1: Regime change events
    print("\n" + "=" * 100)
    print("SECTION 1: REGIME CHANGE TIMELINE")
    print("=" * 100)
    
    for rc in regime_changes[:20]:  # First 20
        marker = "🟢" if 'ENTER' in rc['type'] else "🔴"
        print(f"{marker} {rc['type']:<15} | {rc['timestamp']} | WR: {rc['wr_before']:.1f}% → {rc['wr_after']:.1f}%")
    
    if len(regime_changes) > 20:
        print(f"... and {len(regime_changes) - 20} more regime changes")
    
    # Section 2: Pre-high regime indicators
    print("\n" + "=" * 100)
    print("SECTION 2: INDICATORS BEFORE ENTERING HIGH REGIME")
    print("=" * 100)
    
    pre_indicators = analyze_pre_high_regime_indicators(signals, regime_changes, rolling_data)
    
    if pre_indicators:
        print(f"\n{'Timestamp':<20} | {'Pre-WR':<8} | {'Avg Conf':<10} | {'Strength':<10} | {'SELL%':<8}")
        print("-" * 100)
        
        for pi in pre_indicators[:10]:
            print(f"{pi['timestamp']:<20} | {pi['pre_wr']:>6.1f}% | {pi['avg_conf']:>9.3f} | "
                  f"{pi['avg_strength']:>9.2f} | {pi['sell_ratio']*100:>6.1f}%")
        
        # Averages
        avg_pre_wr = sum(p['pre_wr'] for p in pre_indicators) / len(pre_indicators)
        avg_conf = sum(p['avg_conf'] for p in pre_indicators) / len(pre_indicators)
        avg_strength = sum(p['avg_strength'] for p in pre_indicators) / len(pre_indicators)
        avg_sell = sum(p['sell_ratio'] for p in pre_indicators) / len(pre_indicators) * 100
        
        print("\n📊 AVERAGE CONDITIONS BEFORE HIGH REGIME:")
        print(f"   Pre-regime WR: {avg_pre_wr:.1f}%")
        print(f"   Avg Confidence: {avg_conf:.3f}")
        print(f"   Avg Strength: {avg_strength:.2f}")
        print(f"   SELL signals: {avg_sell:.1f}%")
    
    # Section 3: High regime duration
    print("\n" + "=" * 100)
    print("SECTION 3: HIGH REGIME DURATION ANALYSIS")
    print("=" * 100)
    
    durations = analyze_high_regime_duration(regime_changes, rolling_data)
    
    if durations:
        print(f"\n{'Enter Time':<20} | {'Exit Time':<20} | {'Duration':<12} | {'Signals':<10}")
        print("-" * 100)
        
        for d in durations:
            print(f"{d['enter_time']:<20} | {d['exit_time']:<20} | {d['duration_hours']:>10.1f}h | {d['signals_count']:>8d}")
        
        avg_duration = sum(d['duration_hours'] for d in durations) / len(durations)
        avg_signals = sum(d['signals_count'] for d in durations) / len(durations)
        
        print(f"\n📊 AVERAGE HIGH REGIME:")
        print(f"   Duration: {avg_duration:.1f} hours")
        print(f"   Signals: {avg_signals:.0f} trades")
    
    # Section 4: Time patterns
    print("\n" + "=" * 100)
    print("SECTION 4: TIME-OF-DAY PATTERNS FOR REGIME CHANGES")
    print("=" * 100)
    
    time_patterns = find_time_patterns_in_regimes(regime_changes)
    
    print(f"\n{'Hour':<6} | {'Enter HIGH':<12} | {'Exit HIGH':<12} | {'Enter LOW':<12} | {'Exit LOW':<12}")
    print("-" * 100)
    
    for hour in sorted(time_patterns.keys()):
        tp = time_patterns[hour]
        if any([tp['enter_high'], tp['exit_high'], tp['enter_low'], tp['exit_low']]):
            marker = "🟢" if tp['enter_high'] > 0 else "🔴" if tp['exit_high'] > 0 else "  "
            print(f"{hour}:00 {marker} | {tp['enter_high']:>10d} | {tp['exit_high']:>10d} | "
                  f"{tp['enter_low']:>10d} | {tp['exit_low']:>10d}")
    
    # Section 5: Predictability analysis
    print("\n" + "=" * 100)
    print("SECTION 5: PREDICTABILITY ASSESSMENT")
    print("=" * 100)
    
    print("\n🎯 CAN WE PREDICT HIGH-WR PERIODS?")
    
    if pre_indicators:
        # Check if pre-WR is consistently below threshold
        low_pre_wr = sum(1 for p in pre_indicators if p['pre_wr'] < 55) / len(pre_indicators) * 100
        
        print(f"\n✅ Pattern #1: Pre-regime WR")
        print(f"   {low_pre_wr:.0f}% of high regimes started from WR < 55%")
        if low_pre_wr > 60:
            print(f"   💡 INSIGHT: High regimes often emerge from RECOVERY")
        else:
            print(f"   ⚠️ No strong pre-WR pattern")
    
    if durations:
        short_regimes = sum(1 for d in durations if d['duration_hours'] < 3) / len(durations) * 100
        medium_regimes = sum(1 for d in durations if 3 <= d['duration_hours'] < 8) / len(durations) * 100
        long_regimes = sum(1 for d in durations if d['duration_hours'] >= 8) / len(durations) * 100
        
        print(f"\n✅ Pattern #2: Regime Duration Stability")
        print(f"   Short (<3h): {short_regimes:.0f}%")
        print(f"   Medium (3-8h): {medium_regimes:.0f}%")
        print(f"   Long (>8h): {long_regimes:.0f}%")
        
        if medium_regimes > 50:
            print(f"   💡 INSIGHT: High regimes typically last 3-8 hours")
    
    # Time-based prediction
    top_enter_hours = sorted(time_patterns.items(), key=lambda x: x[1]['enter_high'], reverse=True)[:5]
    
    if top_enter_hours:
        print(f"\n✅ Pattern #3: Time-Based Entry Points")
        print(f"   Most common hours for entering HIGH regime:")
        for hour, tp in top_enter_hours:
            if tp['enter_high'] > 0:
                print(f"   {hour}:00 → {tp['enter_high']} times")
    
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS FOR ALERT SYSTEM")
    print("=" * 100)
    
    print("\n🔔 ALERT #1: HIGH REGIME ENTRY (When to expect success)")
    print("   Trigger conditions:")
    print("   • Rolling 20-signal WR crosses above 65%")
    print("   • Pre-regime WR was recovering from <55%")
    print("   • Time: Watch for entries during peak hours")
    print("   • Expected duration: 3-8 hours")
    
    print("\n🔔 ALERT #2: HIGH REGIME EXIT (Period weakening)")
    print("   Trigger conditions:")
    print("   • Rolling 20-signal WR drops below 65%")
    print("   • Or: 8+ hours in high regime (natural expiry)")
    print("   • Message: 'High-WR period ending, reduce position sizes'")
    
    print("\n🔔 ALERT #3: LOW REGIME WARNING (Avoid trading)")
    print("   Trigger conditions:")
    print("   • Rolling 20-signal WR drops below 45%")
    print("   • Message: 'Low-WR period detected, pause automated trading'")
    
    print("\n" + "=" * 100)
    print("Analysis Complete!")
    print("=" * 100)

if __name__ == '__main__':
    main()
