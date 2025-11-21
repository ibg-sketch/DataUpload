#!/usr/bin/env python3
"""
Multi-Day Validation Analysis
Validates Nov 11 findings across historical data (Nov 5-11)
"""

import csv
from collections import defaultdict
from datetime import datetime

def safe_float(val):
    try:
        return float(val) if val and val != '' else 0.0
    except:
        return 0.0

def categorize_time(ts):
    """Categorize by hour"""
    hour = int(ts[11:13])
    if 4 <= hour <= 9:
        return 'MORNING'
    elif 10 <= hour <= 13:
        return 'MIDDAY'
    elif 14 <= hour <= 16:
        return 'AFTERNOON'
    else:
        return 'OTHER'

def load_signals_by_date():
    """Load all signals grouped by date"""
    by_date = defaultdict(list)
    
    with open('effectiveness_log.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get('timestamp_sent', '')
            if ts.startswith('2025-11'):
                date = ts[:10]
                by_date[date].append(row)
    
    return by_date

def analyze_time_performance(signals):
    """Analyze performance by time category"""
    by_time = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0.0, 'signals': []})
    
    for sig in signals:
        time_cat = categorize_time(sig['timestamp_sent'])
        result = sig.get('result', '')
        
        by_time[time_cat]['signals'].append(sig)
        
        if result == 'WIN':
            by_time[time_cat]['wins'] += 1
            by_time[time_cat]['total_pnl'] += safe_float(sig.get('profit_pct'))
        elif result == 'LOSS':
            by_time[time_cat]['losses'] += 1
            by_time[time_cat]['total_pnl'] += safe_float(sig.get('profit_pct'))
    
    return by_time

def analyze_symbol_performance(signals, time_category):
    """Analyze symbol performance in specific time window"""
    by_symbol = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0.0})
    
    for sig in signals:
        if categorize_time(sig['timestamp_sent']) != time_category:
            continue
        
        symbol = sig['symbol']
        result = sig.get('result', '')
        
        if result == 'WIN':
            by_symbol[symbol]['wins'] += 1
            by_symbol[symbol]['total_pnl'] += safe_float(sig.get('profit_pct'))
        elif result == 'LOSS':
            by_symbol[symbol]['losses'] += 1
            by_symbol[symbol]['total_pnl'] += safe_float(sig.get('profit_pct'))
    
    return by_symbol

def analyze_hourly_pattern(signals):
    """Get hourly win rate pattern"""
    by_hour = defaultdict(lambda: {'wins': 0, 'losses': 0})
    
    for sig in signals:
        hour = sig['timestamp_sent'][11:13]
        result = sig.get('result', '')
        
        if result == 'WIN':
            by_hour[hour]['wins'] += 1
        elif result == 'LOSS':
            by_hour[hour]['losses'] += 1
    
    return by_hour

def analyze_confidence_distribution(signals, time_category):
    """Analyze confidence vs PnL in specific time window"""
    conf_buckets = {
        'Low (0.40-0.49)': [],
        'Med (0.50-0.59)': [],
        'High (0.60-0.69)': [],
        'VHigh (0.70+)': []
    }
    
    for sig in signals:
        if categorize_time(sig['timestamp_sent']) != time_category:
            continue
        if sig.get('result') not in ['WIN', 'LOSS']:
            continue
        
        conf = safe_float(sig.get('confidence'))
        pnl = safe_float(sig.get('profit_pct'))
        
        if 0.40 <= conf < 0.50:
            conf_buckets['Low (0.40-0.49)'].append(pnl)
        elif 0.50 <= conf < 0.60:
            conf_buckets['Med (0.50-0.59)'].append(pnl)
        elif 0.60 <= conf < 0.70:
            conf_buckets['High (0.60-0.69)'].append(pnl)
        elif conf >= 0.70:
            conf_buckets['VHigh (0.70+)'].append(pnl)
    
    return conf_buckets

def main():
    print("=" * 100)
    print("MULTI-DAY VALIDATION ANALYSIS (Nov 5-11, 2025)")
    print("Validating Morning Success Pattern Across Historical Data")
    print("=" * 100)
    
    # Load all data
    by_date = load_signals_by_date()
    
    print(f"\n📅 Available dates: {len(by_date)}")
    for date in sorted(by_date.keys()):
        print(f"   {date}: {len(by_date[date])} signals")
    
    # Daily summary
    print("\n" + "=" * 100)
    print("SECTION 1: DAILY OVERVIEW")
    print("=" * 100)
    print(f"{'Date':<12} | {'Signals':<8} | {'W/L':<10} | {'WR%':<8} | {'Total PnL':<12} | {'Avg PnL':<10}")
    print("-" * 100)
    
    daily_summary = []
    
    for date in sorted(by_date.keys()):
        signals = by_date[date]
        wins = sum(1 for s in signals if s.get('result') == 'WIN')
        losses = sum(1 for s in signals if s.get('result') == 'LOSS')
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        
        pnls = [safe_float(s.get('profit_pct')) for s in signals if s.get('result') in ['WIN', 'LOSS']]
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(pnls) if pnls else 0
        
        marker = "🔥" if wr >= 70 else "✅" if wr >= 50 else "⚠️" if wr >= 30 else "❌"
        
        print(f"{date} {marker} | {len(signals):<8} | {wins:3d}/{losses:<3d}  | {wr:>6.1f}% | {total_pnl:>+10.2f}% | {avg_pnl:>+9.3f}%")
        
        daily_summary.append({
            'date': date,
            'signals': signals,
            'wr': wr,
            'wins': wins,
            'losses': losses
        })
    
    # Time category analysis across all days
    print("\n" + "=" * 100)
    print("SECTION 2: TIME CATEGORY PERFORMANCE (ALL DAYS COMBINED)")
    print("=" * 100)
    
    all_signals = []
    for signals in by_date.values():
        all_signals.extend(signals)
    
    time_performance = analyze_time_performance(all_signals)
    
    print(f"\n{'Category':<12} | {'Signals':<8} | {'W/L':<10} | {'WR%':<8} | {'Total PnL':<12} | {'Avg PnL':<10}")
    print("-" * 100)
    
    for cat in ['MORNING', 'MIDDAY', 'AFTERNOON', 'OTHER']:
        if cat in time_performance:
            t = time_performance[cat]
            total = t['wins'] + t['losses']
            wr = (t['wins'] / total * 100) if total > 0 else 0
            avg_pnl = t['total_pnl'] / total if total > 0 else 0
            
            marker = "🔥" if wr >= 70 else "✅" if wr >= 50 else "⚠️"
            
            print(f"{cat:<12} {marker} | {len(t['signals']):<8} | {t['wins']:3d}/{t['losses']:<3d}  | {wr:>6.1f}% | "
                  f"{t['total_pnl']:>+10.2f}% | {avg_pnl:>+9.3f}%")
    
    # Day-by-day time analysis
    print("\n" + "=" * 100)
    print("SECTION 3: MORNING vs MIDDAY COMPARISON (DAY-BY-DAY)")
    print("=" * 100)
    print(f"{'Date':<12} | {'Morning WR':<12} | {'Midday WR':<12} | {'Gap':<8} | {'Morning Wins':<13} | {'Midday Wins':<12}")
    print("-" * 100)
    
    morning_wins_count = 0
    midday_wins_count = 0
    
    for day in daily_summary:
        if len(day['signals']) < 20:  # Skip low-sample days
            continue
        
        time_perf = analyze_time_performance(day['signals'])
        
        morning = time_perf.get('MORNING', {'wins': 0, 'losses': 0})
        midday = time_perf.get('MIDDAY', {'wins': 0, 'losses': 0})
        
        morning_total = morning['wins'] + morning['losses']
        midday_total = midday['wins'] + midday['losses']
        
        morning_wr = (morning['wins'] / morning_total * 100) if morning_total > 0 else 0
        midday_wr = (midday['wins'] / midday_total * 100) if midday_total > 0 else 0
        
        gap = morning_wr - midday_wr
        
        if morning_wr > midday_wr:
            morning_wins_count += 1
        else:
            midday_wins_count += 1
        
        marker = "✅" if gap > 0 else "⚠️"
        
        print(f"{day['date']} {marker} | {morning_wr:>10.1f}% | {midday_wr:>10.1f}% | {gap:>+6.1f}% | "
              f"{morning['wins']:2d}/{morning_total:<2d}       | {midday['wins']:2d}/{midday_total:<2d}")
    
    print(f"\n📊 Morning outperformed Midday: {morning_wins_count} days")
    print(f"📊 Midday outperformed Morning: {midday_wins_count} days")
    
    # Hourly pattern consistency
    print("\n" + "=" * 100)
    print("SECTION 4: HOURLY WIN RATE PATTERN (ALL DAYS)")
    print("=" * 100)
    
    hourly_pattern = analyze_hourly_pattern(all_signals)
    
    print(f"{'Hour':<6} | {'W/L':<10} | {'WR%':<8}")
    print("-" * 50)
    
    for hour in sorted(hourly_pattern.keys()):
        h = hourly_pattern[hour]
        total = h['wins'] + h['losses']
        wr = (h['wins'] / total * 100) if total > 0 else 0
        
        marker = "🔥" if wr >= 70 else "✅" if wr >= 50 else "⚠️" if wr >= 30 else "❌"
        
        print(f"{hour}:00 {marker} | {h['wins']:3d}/{h['losses']:<3d}  | {wr:>6.1f}%")
    
    # Symbol performance validation
    print("\n" + "=" * 100)
    print("SECTION 5: SYMBOL PERFORMANCE IN MORNING (ALL DAYS)")
    print("=" * 100)
    
    morning_symbols = analyze_symbol_performance(all_signals, 'MORNING')
    
    symbol_stats = []
    for symbol, stats in morning_symbols.items():
        total = stats['wins'] + stats['losses']
        if total >= 5:  # Min 5 trades
            wr = (stats['wins'] / total * 100) if total > 0 else 0
            symbol_stats.append({
                'symbol': symbol,
                'wins': stats['wins'],
                'losses': stats['losses'],
                'wr': wr,
                'total_pnl': stats['total_pnl']
            })
    
    symbol_stats.sort(key=lambda x: x['wr'], reverse=True)
    
    print(f"{'Symbol':<12} | {'W/L':<10} | {'WR%':<8} | {'Total PnL':<12}")
    print("-" * 60)
    
    for stat in symbol_stats[:10]:
        marker = "🔥" if stat['wr'] >= 80 else "✅" if stat['wr'] >= 60 else "⚠️"
        print(f"{marker} {stat['symbol']:<9} | {stat['wins']:3d}/{stat['losses']:<3d}  | {stat['wr']:>6.1f}% | {stat['total_pnl']:>+10.2f}%")
    
    # Confidence pattern validation
    print("\n" + "=" * 100)
    print("SECTION 6: CONFIDENCE vs PnL (MORNING, ALL DAYS)")
    print("=" * 100)
    
    conf_dist = analyze_confidence_distribution(all_signals, 'MORNING')
    
    print(f"{'Confidence Range':<20} | {'Samples':<8} | {'Avg PnL':<10} | {'Total PnL':<12}")
    print("-" * 70)
    
    for bucket, pnls in conf_dist.items():
        if pnls:
            avg_pnl = sum(pnls) / len(pnls)
            total_pnl = sum(pnls)
            print(f"{bucket:<20} | {len(pnls):<8} | {avg_pnl:>+9.3f}% | {total_pnl:>+10.2f}%")
    
    # VALIDATION SUMMARY
    print("\n" + "=" * 100)
    print("VALIDATION SUMMARY: Nov 11 Findings")
    print("=" * 100)
    
    # Calculate overall stats
    morning_all = time_performance.get('MORNING', {'wins': 0, 'losses': 0})
    midday_all = time_performance.get('MIDDAY', {'wins': 0, 'losses': 0})
    
    morning_total = morning_all['wins'] + morning_all['losses']
    midday_total = midday_all['wins'] + midday_all['losses']
    
    morning_wr_overall = (morning_all['wins'] / morning_total * 100) if morning_total > 0 else 0
    midday_wr_overall = (midday_all['wins'] / midday_total * 100) if midday_total > 0 else 0
    
    print(f"\n✅ Finding #1: Morning outperforms Midday")
    print(f"   Morning WR (ALL DAYS): {morning_wr_overall:.1f}%")
    print(f"   Midday WR (ALL DAYS): {midday_wr_overall:.1f}%")
    print(f"   Gap: {morning_wr_overall - midday_wr_overall:+.1f} p.p.")
    print(f"   Consistent across: {morning_wins_count}/{morning_wins_count + midday_wins_count} days")
    if morning_wins_count > midday_wins_count:
        print(f"   ✅ VALIDATED: Morning consistently outperforms")
    else:
        print(f"   ⚠️ NOT VALIDATED: Pattern inconsistent")
    
    # Top symbols validation
    top_morning_symbols = [s['symbol'] for s in symbol_stats[:3]]
    print(f"\n✅ Finding #2: Alt-coins dominate morning")
    print(f"   Top 3 symbols: {', '.join(top_morning_symbols)}")
    nov11_top = ['XRPUSDT', 'SOLUSDT', 'DOGEUSDT']
    overlap = len(set(top_morning_symbols) & set(nov11_top))
    print(f"   Overlap with Nov 11 top-3: {overlap}/3")
    if overlap >= 2:
        print(f"   ✅ VALIDATED: Alt-coins consistently strong")
    else:
        print(f"   ⚠️ PARTIAL: Some variation in top symbols")
    
    # Confidence paradox
    low_conf_pnls = conf_dist.get('Low (0.40-0.49)', [])
    high_conf_pnls = conf_dist.get('VHigh (0.70+)', [])
    
    if low_conf_pnls and high_conf_pnls:
        low_avg = sum(low_conf_pnls) / len(low_conf_pnls)
        high_avg = sum(high_conf_pnls) / len(high_conf_pnls)
        
        print(f"\n✅ Finding #3: Low confidence can be profitable")
        print(f"   Low conf (0.40-0.49) avg PnL: {low_avg:+.3f}%")
        print(f"   High conf (0.70+) avg PnL: {high_avg:+.3f}%")
        if low_avg > high_avg:
            print(f"   ✅ VALIDATED: Low conf outperforms high conf in morning")
        else:
            print(f"   ⚠️ NOT VALIDATED: High conf performs better overall")
    
    print("\n" + "=" * 100)
    print("Analysis Complete!")
    print("=" * 100)

if __name__ == '__main__':
    main()
