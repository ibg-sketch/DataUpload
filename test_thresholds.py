#!/usr/bin/env python3
"""
Test different threshold configurations on historical signal data
"""
import pandas as pd
from datetime import datetime, timedelta

def test_threshold_configs():
    """Test different min_score_pct_buy/sell configurations."""
    
    # Load analysis log
    print("Loading analysis_log.csv...")
    df = pd.read_csv('analysis_log.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter last 2 days (Nov 8-9, 2025)
    cutoff = datetime.now() - timedelta(days=2)
    recent = df[df['timestamp'] >= cutoff].copy()
    
    print(f"\n📊 DATASET: {len(recent)} analyses from {recent['timestamp'].min()} to {recent['timestamp'].max()}")
    print(f"   Time range: {(recent['timestamp'].max() - recent['timestamp'].min()).total_seconds() / 3600:.1f} hours")
    
    # Count by verdict
    verdict_counts = recent['verdict'].value_counts()
    print(f"\n🔍 VERDICT DISTRIBUTION:")
    for verdict, count in verdict_counts.items():
        pct = (count / len(recent)) * 100
        print(f"   {verdict}: {count} ({pct:.1f}%)")
    
    # Filter only BUY/SELL
    signals = recent[recent['verdict'].isin(['BUY', 'SELL'])].copy()
    print(f"\n💡 POTENTIAL SIGNALS: {len(signals)} (BUY + SELL only)")
    
    # Test different configurations
    configs = [
        {'name': 'Nov 1 (CURRENT)', 'buy': 0.68, 'sell': 0.72, 'oi': 0.1},
        {'name': 'Nov 4 (AGGRESSIVE)', 'buy': 0.62, 'sell': 0.65, 'oi': 0.2},
        {'name': 'PROPOSED (Golden Mean)', 'buy': 0.60, 'sell': 0.65, 'oi': 0.15},
        {'name': 'VERY AGGRESSIVE', 'buy': 0.55, 'sell': 0.60, 'oi': 0.2},
    ]
    
    results = []
    
    for config in configs:
        buy_signals = signals[(signals['verdict'] == 'BUY') & (signals['confidence'] >= config['buy'])]
        sell_signals = signals[(signals['verdict'] == 'SELL') & (signals['confidence'] >= config['sell'])]
        total_passed = len(buy_signals) + len(sell_signals)
        
        # Calculate stats
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        
        buy_avg_conf = buy_signals['confidence'].mean() if len(buy_signals) > 0 else 0
        sell_avg_conf = sell_signals['confidence'].mean() if len(sell_signals) > 0 else 0
        
        # Calculate signals per hour
        hours = (recent['timestamp'].max() - recent['timestamp'].min()).total_seconds() / 3600
        signals_per_hour = total_passed / hours if hours > 0 else 0
        signals_per_day = signals_per_hour * 24
        
        results.append({
            'config': config['name'],
            'buy_threshold': config['buy'],
            'sell_threshold': config['sell'],
            'oi_weight': config['oi'],
            'buy_count': buy_count,
            'sell_count': sell_count,
            'total': total_passed,
            'buy_avg_conf': buy_avg_conf,
            'sell_avg_conf': sell_avg_conf,
            'signals_per_hour': signals_per_hour,
            'signals_per_day': signals_per_day,
            'conversion_rate': (total_passed / len(signals)) * 100 if len(signals) > 0 else 0
        })
    
    # Print results
    print("\n" + "="*100)
    print("THRESHOLD CONFIGURATION TEST RESULTS")
    print("="*100)
    print(f"{'Configuration':<30} {'Buy≥':<6} {'Sell≥':<6} {'OI':<5} {'BUY':<5} {'SELL':<5} {'Total':<6} {'Signals/Day':<12} {'Conv%':<7}")
    print("-"*100)
    
    for r in results:
        print(f"{r['config']:<30} {r['buy_threshold']:<6.2f} {r['sell_threshold']:<6.2f} {r['oi_weight']:<5.2f} "
              f"{r['buy_count']:<5} {r['sell_count']:<5} {r['total']:<6} "
              f"{r['signals_per_day']:<12.1f} {r['conversion_rate']:<7.1f}%")
    
    print("\n" + "="*100)
    print("DETAILED BREAKDOWN")
    print("="*100)
    
    for r in results:
        print(f"\n📋 {r['config']}")
        print(f"   Thresholds: BUY ≥ {r['buy_threshold']:.0%}, SELL ≥ {r['sell_threshold']:.0%}")
        print(f"   OI Weight: {r['oi_weight']}")
        print(f"   ✅ Passed: {r['total']} signals ({r['buy_count']} BUY + {r['sell_count']} SELL)")
        print(f"   📊 Avg Confidence: BUY {r['buy_avg_conf']:.0%}, SELL {r['sell_avg_conf']:.0%}")
        print(f"   ⏱️  Rate: {r['signals_per_hour']:.1f}/hour, {r['signals_per_day']:.1f}/day")
        print(f"   🎯 Conversion: {r['conversion_rate']:.1f}% of potential signals sent to Telegram")
    
    # Show confidence distribution for each config
    print("\n" + "="*100)
    print("CONFIDENCE DISTRIBUTION ANALYSIS")
    print("="*100)
    
    # Get all BUY/SELL signals and their confidence
    buy_conf = signals[signals['verdict'] == 'BUY']['confidence']
    sell_conf = signals[signals['verdict'] == 'SELL']['confidence']
    
    print(f"\n📊 BUY signals confidence distribution:")
    print(f"   Count: {len(buy_conf)}")
    print(f"   Min: {buy_conf.min():.0%}, Max: {buy_conf.max():.0%}, Avg: {buy_conf.mean():.0%}")
    print(f"   Percentiles:")
    for p in [25, 50, 75, 90, 95]:
        val = buy_conf.quantile(p/100)
        print(f"      P{p}: {val:.0%}")
    
    print(f"\n📊 SELL signals confidence distribution:")
    print(f"   Count: {len(sell_conf)}")
    print(f"   Min: {sell_conf.min():.0%}, Max: {sell_conf.max():.0%}, Avg: {sell_conf.mean():.0%}")
    print(f"   Percentiles:")
    for p in [25, 50, 75, 90, 95]:
        val = sell_conf.quantile(p/100)
        print(f"      P{p}: {val:.0%}")
    
    # Show what % of signals fall into different confidence buckets
    print(f"\n📊 Confidence buckets (BUY):")
    for threshold in [0.45, 0.50, 0.55, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75, 0.80]:
        count = len(buy_conf[buy_conf >= threshold])
        pct = (count / len(buy_conf)) * 100 if len(buy_conf) > 0 else 0
        print(f"   ≥ {threshold:.0%}: {count} signals ({pct:.1f}%)")
    
    print(f"\n📊 Confidence buckets (SELL):")
    for threshold in [0.45, 0.50, 0.55, 0.60, 0.62, 0.65, 0.68, 0.70, 0.72, 0.75, 0.80]:
        count = len(sell_conf[sell_conf >= threshold])
        pct = (count / len(sell_conf)) * 100 if len(sell_conf) > 0 else 0
        print(f"   ≥ {threshold:.0%}: {count} signals ({pct:.1f}%)")
    
    # Recommendation
    print("\n" + "="*100)
    print("💡 RECOMMENDATION")
    print("="*100)
    
    # Find best config (balance between quantity and quality)
    best = None
    for r in results:
        if 10 <= r['signals_per_day'] <= 30:  # Sweet spot: 10-30 signals/day
            if best is None or r['signals_per_day'] > best['signals_per_day']:
                best = r
    
    if best:
        print(f"\n✅ RECOMMENDED CONFIG: {best['config']}")
        print(f"   Rationale:")
        print(f"   • {best['signals_per_day']:.1f} signals/day (balanced, not too few/many)")
        print(f"   • {best['conversion_rate']:.1f}% conversion (not too restrictive)")
        print(f"   • Avg confidence: BUY {best['buy_avg_conf']:.0%}, SELL {best['sell_avg_conf']:.0%}")
        print(f"\n   Apply these settings:")
        print(f"   min_score_pct_buy:  {best['buy_threshold']}")
        print(f"   min_score_pct_sell: {best['sell_threshold']}")
        print(f"   oi: {best['oi_weight']}")
    else:
        print("\n⚠️  No config found in optimal range (10-30 signals/day)")
        print("   Consider further adjustment")

if __name__ == '__main__':
    test_threshold_configs()
