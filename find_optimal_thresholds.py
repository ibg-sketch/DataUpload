#!/usr/bin/env python3
"""
Find optimal thresholds for 10-30 signals/day target
"""
import pandas as pd
from datetime import datetime, timedelta

def find_optimal():
    # Load data
    df = pd.read_csv('analysis_log.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    cutoff = datetime.now() - timedelta(days=2)
    recent = df[df['timestamp'] >= cutoff].copy()
    
    hours = (recent['timestamp'].max() - recent['timestamp'].min()).total_seconds() / 3600
    signals = recent[recent['verdict'].isin(['BUY', 'SELL'])].copy()
    
    print("="*80)
    print("FINDING OPTIMAL THRESHOLDS (TARGET: 10-30 signals/day)")
    print("="*80)
    
    # Test range of thresholds
    buy_thresholds = [0.55, 0.58, 0.60, 0.62, 0.65]
    sell_thresholds = [0.65, 0.68, 0.70, 0.72, 0.75, 0.78]
    
    optimal_configs = []
    
    for buy_t in buy_thresholds:
        for sell_t in sell_thresholds:
            buy_count = len(signals[(signals['verdict'] == 'BUY') & (signals['confidence'] >= buy_t)])
            sell_count = len(signals[(signals['verdict'] == 'SELL') & (signals['confidence'] >= sell_t)])
            total = buy_count + sell_count
            
            signals_per_day = (total / hours) * 24 if hours > 0 else 0
            
            # Find configs in target range
            if 10 <= signals_per_day <= 30:
                optimal_configs.append({
                    'buy_threshold': buy_t,
                    'sell_threshold': sell_t,
                    'buy_count': buy_count,
                    'sell_count': sell_count,
                    'total': total,
                    'signals_per_day': signals_per_day
                })
    
    if optimal_configs:
        print(f"\n✅ FOUND {len(optimal_configs)} OPTIMAL CONFIGURATIONS:\n")
        print(f"{'BUY≥':<8} {'SELL≥':<8} {'BUY':<6} {'SELL':<6} {'Total':<6} {'Signals/Day':<12} {'Balance'}")
        print("-"*80)
        
        for cfg in sorted(optimal_configs, key=lambda x: abs(x['signals_per_day'] - 20)):
            balance = "⚖️ BALANCED" if abs(cfg['buy_count'] - cfg['sell_count']) < 20 else "⚠️ IMBALANCED"
            print(f"{cfg['buy_threshold']:<8.2f} {cfg['sell_threshold']:<8.2f} "
                  f"{cfg['buy_count']:<6} {cfg['sell_count']:<6} {cfg['total']:<6} "
                  f"{cfg['signals_per_day']:<12.1f} {balance}")
        
        # Recommend best
        best = sorted(optimal_configs, key=lambda x: abs(x['signals_per_day'] - 20))[0]
        
        print("\n" + "="*80)
        print("🏆 RECOMMENDED CONFIGURATION")
        print("="*80)
        print(f"\nmin_score_pct_buy:  {best['buy_threshold']}")
        print(f"min_score_pct_sell: {best['sell_threshold']}")
        print(f"\n📊 Expected output: {best['signals_per_day']:.1f} signals/day")
        print(f"   ({best['buy_count']} BUY + {best['sell_count']} SELL over 46.4 hours)")
        print(f"\n✅ This balances quality (confidence) with quantity (not too many/few)")
    else:
        print("\n❌ NO CONFIGURATION FOUND IN OPTIMAL RANGE")
        print("   Trying wider search...\n")
        
        # Try wider range
        for buy_t in [0.50, 0.55, 0.60, 0.65]:
            for sell_t in [0.70, 0.75, 0.80]:
                buy_count = len(signals[(signals['verdict'] == 'BUY') & (signals['confidence'] >= buy_t)])
                sell_count = len(signals[(signals['verdict'] == 'SELL') & (signals['confidence'] >= sell_t)])
                total = buy_count + sell_count
                signals_per_day = (total / hours) * 24 if hours > 0 else 0
                
                print(f"BUY≥{buy_t:.0%}, SELL≥{sell_t:.0%}: {signals_per_day:.1f}/day ({buy_count} BUY, {sell_count} SELL)")

if __name__ == '__main__':
    find_optimal()
