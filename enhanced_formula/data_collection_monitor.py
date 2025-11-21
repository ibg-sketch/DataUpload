#!/usr/bin/env python3
"""
Monitor data collection progress for Enhanced Formula v2
Shows statistics on collected signals for future ML training
"""

import pandas as pd
from datetime import datetime

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def main():
    print("="*70)
    print("ENHANCED FORMULA V2 - DATA COLLECTION MONITOR")
    print("="*70)
    print(f"Training cutoff: {TRAINING_CUTOFF}")
    print(f"Report time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_sig = pd.read_csv('signals_log.csv')
    
    # Filter to new data after training
    df_new = df_eff[df_eff['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    
    # Convert timestamp for hourly calc
    df_new['timestamp_dt'] = pd.to_datetime(df_new['timestamp_sent'])
    one_hour_ago = pd.Timestamp.now() - pd.Timedelta(hours=1)
    
    print("OVERALL STATISTICS")
    print("-"*70)
    print(f"Total signals in database:  {len(df_eff):,}")
    print(f"Signals after training:     {len(df_new):,}")
    print(f"New signals in last hour:   {len(df_new[df_new['timestamp_dt'] >= one_hour_ago]):,}")
    print()
    
    # Result distribution
    print("RESULT DISTRIBUTION (After Training)")
    print("-"*70)
    result_counts = df_new['result'].value_counts()
    total = len(df_new)
    
    for result_type in ['WIN', 'LOSS', 'CANCELLED']:
        count = result_counts.get(result_type, 0)
        pct = count / total * 100 if total > 0 else 0
        print(f"{result_type:12s}: {count:4d} signals ({pct:5.1f}%)")
    
    completed = result_counts.get('WIN', 0) + result_counts.get('LOSS', 0)
    print(f"{'COMPLETED':12s}: {completed:4d} signals ({completed/total*100 if total > 0 else 0:5.1f}%)")
    print()
    
    # Win rate on completed signals
    if completed > 0:
        win_rate = result_counts.get('WIN', 0) / completed * 100
        print(f"Win Rate (completed): {win_rate:.1f}%")
        print()
    
    # Symbol distribution
    print("TOP 10 SYMBOLS BY SIGNAL COUNT")
    print("-"*70)
    symbol_counts = df_new['symbol'].value_counts().head(10)
    for symbol, count in symbol_counts.items():
        wins = ((df_new['symbol'] == symbol) & (df_new['result'] == 'WIN')).sum()
        losses = ((df_new['symbol'] == symbol) & (df_new['result'] == 'LOSS')).sum()
        cancelled = ((df_new['symbol'] == symbol) & (df_new['result'] == 'CANCELLED')).sum()
        wr = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        print(f"{symbol:10s}: {count:3d} total | W:{wins:2d} L:{losses:2d} C:{cancelled:2d} | WR:{wr:5.1f}%")
    print()
    
    # Verdict distribution
    print("SIGNAL DIRECTION DISTRIBUTION")
    print("-"*70)
    verdict_counts = df_new['verdict'].value_counts()
    for verdict, count in verdict_counts.items():
        pct = count / len(df_new) * 100
        print(f"{verdict:8s}: {count:4d} signals ({pct:5.1f}%)")
    print()
    
    # Confidence distribution
    print("CONFIDENCE DISTRIBUTION (Completed signals)")
    print("-"*70)
    df_completed = df_new[df_new['result'].isin(['WIN', 'LOSS'])]
    if len(df_completed) > 0:
        conf_ranges = [(0.5, 0.6, '50-60%'), (0.6, 0.7, '60-70%'), 
                       (0.7, 0.8, '70-80%'), (0.8, 1.0, '80-100%')]
        for low, high, label in conf_ranges:
            mask = (df_completed['confidence'] >= low) & (df_completed['confidence'] < high)
            count = mask.sum()
            wins = ((df_completed[mask]['result'] == 'WIN').sum())
            wr = wins / count * 100 if count > 0 else 0
            print(f"{label:10s}: {count:3d} signals | {wins:2d} WIN | WR:{wr:5.1f}%")
    print()
    
    # Data quality recommendations
    print("="*70)
    print("DATA COLLECTION TARGETS FOR ML TRAINING")
    print("="*70)
    
    targets = [
        ("Minimum for testing", 50),
        ("Recommended for training", 200),
        ("Optimal dataset", 500),
        ("High-quality dataset", 1000)
    ]
    
    for label, target in targets:
        icon = "✅" if completed >= target else "⏳"
        progress = min(100, completed / target * 100)
        print(f"{icon} {label:25s}: {completed:4d}/{target:4d} ({progress:5.1f}%)")
    print()
    
    # Cancellation analysis
    cancelled_pct = result_counts.get('CANCELLED', 0) / total * 100 if total > 0 else 0
    if cancelled_pct > 50:
        print("⚠️  WARNING: High cancellation rate ({:.1f}%)".format(cancelled_pct))
        print("   Consider reviewing signal confidence thresholds")
        print()
    
    # Average PnL
    if len(df_completed) > 0:
        avg_win = df_completed[df_completed['result'] == 'WIN']['profit_pct'].mean()
        avg_loss = df_completed[df_completed['result'] == 'LOSS']['profit_pct'].mean()
        print("AVERAGE PNL (Completed signals)")
        print("-"*70)
        print(f"Average WIN:  +{avg_win:.2f}%")
        print(f"Average LOSS: {avg_loss:.2f}%")
        print(f"Overall:      {df_completed['profit_pct'].mean():+.2f}%")
        print()
    
    print("="*70)
    print("📁 Data files:")
    print("   - effectiveness_log.csv (results & PnL)")
    print("   - signals_log.csv (signal parameters)")
    print()
    print("🔄 Data collection is ongoing...")
    print("   Run this script periodically to monitor progress")

if __name__ == '__main__':
    main()
