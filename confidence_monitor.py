#!/usr/bin/env python3
"""
Confidence Distribution Monitor
Tracks confidence score distributions to ensure algorithm changes don't over-compress scores.
Analyzes confidence patterns before and after OI weight reduction.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

def load_signal_data():
    """Load historical signal data with confidence scores."""
    try:
        df = pd.read_csv('signals_log.csv')
        print(f"📊 Loaded {len(df)} signals from signals_log.csv\n")
        return df
    except FileNotFoundError:
        print("⚠️  signals_log.csv not found, trying analysis_log.csv...")
        try:
            df = pd.read_csv('analysis_log.csv')
            df = df[df['signal'] != 'NO_TRADE']
            print(f"📊 Loaded {len(df)} signals from analysis_log.csv\n")
            return df
        except FileNotFoundError:
            print("❌ No signal data available")
            return None

def analyze_confidence_distribution(df):
    """Analyze confidence score distribution patterns."""
    
    if 'confidence' not in df.columns:
        print("❌ Missing 'confidence' column in data")
        return
    
    df = df[df['confidence'] > 0]
    
    if len(df) == 0:
        print("❌ No signals with confidence scores found")
        return
    
    print("="*70)
    print("CONFIDENCE DISTRIBUTION ANALYSIS")
    print("="*70)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Signals Analyzed: {len(df)}")
    print()
    
    print("📊 OVERALL CONFIDENCE STATISTICS")
    print("-" * 70)
    print(f"Min Confidence: {df['confidence'].min():.1f}%")
    print(f"25th Percentile: {df['confidence'].quantile(0.25):.1f}%")
    print(f"Median (50th): {df['confidence'].median():.1f}%")
    print(f"Mean: {df['confidence'].mean():.1f}%")
    print(f"75th Percentile: {df['confidence'].quantile(0.75):.1f}%")
    print(f"Max Confidence: {df['confidence'].max():.1f}%")
    print(f"Std Deviation: {df['confidence'].std():.1f}%")
    print()
    
    print("📈 CONFIDENCE DISTRIBUTION BINS")
    print("-" * 70)
    bins = [0, 60, 70, 75, 80, 85, 90, 95, 100]
    bin_labels = ['< 60%', '60-70%', '70-75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%']
    
    df['conf_bin'] = pd.cut(df['confidence'], bins=bins, labels=bin_labels, include_lowest=True)
    bin_counts = df['conf_bin'].value_counts().sort_index()
    
    for label in bin_labels:
        count = bin_counts.get(label, 0)
        pct = (count / len(df) * 100) if len(df) > 0 else 0
        bar = '█' * int(pct / 2)
        print(f"{label:12s}: {count:4d} ({pct:5.1f}%) {bar}")
    
    print()
    print("🎯 CONFIDENCE VS WIN RATE ANALYSIS")
    print("-" * 70)
    
    if 'result' in df.columns:
        for label in bin_labels:
            bin_signals = df[df['conf_bin'] == label]
            if len(bin_signals) > 0:
                wins = len(bin_signals[bin_signals['result'] == 'WIN'])
                win_rate = wins / len(bin_signals) * 100
                status = "✅" if win_rate >= 60 else "⚠️ " if win_rate >= 50 else "❌"
                print(f"{label:12s}: {win_rate:5.1f}% win rate ({wins}W-{len(bin_signals)-wins}L) {status}")
    else:
        print("⚠️  No 'result' column - cannot analyze win rates")
    
    print()
    print("⚠️  COMPRESSION WARNING CHECKS")
    print("-" * 70)
    
    # Check for over-compression (too many signals at same confidence)
    top_3_values = df['confidence'].value_counts().head(3)
    if len(top_3_values) > 0:
        most_common_conf = top_3_values.index[0]
        most_common_count = top_3_values.values[0]
        most_common_pct = most_common_count / len(df) * 100
        
        if most_common_pct > 50:
            print(f"⚠️  WARNING: {most_common_pct:.1f}% of signals have {most_common_conf:.1f}% confidence")
            print(f"   This suggests over-compression - confidence scores may be too similar")
        else:
            print(f"✅ Confidence distribution appears healthy")
            print(f"   Most common: {most_common_conf:.1f}% ({most_common_pct:.1f}% of signals)")
    
    std = df['confidence'].std()
    if std < 5:
        print(f"⚠️  WARNING: Very low standard deviation ({std:.1f}%)")
        print(f"   Confidence scores are very compressed (not much variation)")
    elif std < 10:
        print(f"⚠️  Low standard deviation ({std:.1f}%)")
        print(f"   Confidence scores have limited variation")
    else:
        print(f"✅ Good standard deviation ({std:.1f}%)")
        print(f"   Confidence scores show healthy variation")
    
    range_val = df['confidence'].max() - df['confidence'].min()
    if range_val < 20:
        print(f"⚠️  WARNING: Narrow confidence range ({range_val:.1f}%)")
        print(f"   All signals fall within a narrow confidence band")
    else:
        print(f"✅ Good confidence range ({range_val:.1f}%)")
        print(f"   Signals span a healthy confidence range")
    
    print()
    print("📅 TIME-BASED ANALYSIS")
    print("-" * 70)
    
    if 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        recent_cutoff = datetime.now() - timedelta(days=7)
        
        df_recent = df[pd.to_datetime(df['timestamp']) >= recent_cutoff]
        df_older = df[pd.to_datetime(df['timestamp']) < recent_cutoff]
        
        if len(df_recent) > 0 and len(df_older) > 0:
            print(f"Recent (last 7 days): {len(df_recent)} signals")
            print(f"  Mean confidence: {df_recent['confidence'].mean():.1f}%")
            print(f"  Std deviation: {df_recent['confidence'].std():.1f}%")
            print()
            print(f"Older (>7 days ago): {len(df_older)} signals")
            print(f"  Mean confidence: {df_older['confidence'].mean():.1f}%")
            print(f"  Std deviation: {df_older['confidence'].std():.1f}%")
            print()
            
            conf_change = df_recent['confidence'].mean() - df_older['confidence'].mean()
            std_change = df_recent['confidence'].std() - df_older['confidence'].std()
            
            if abs(conf_change) > 5:
                print(f"⚠️  Significant mean confidence change: {conf_change:+.1f}%")
            else:
                print(f"✅ Stable mean confidence: {conf_change:+.1f}%")
            
            if abs(std_change) > 3:
                print(f"⚠️  Significant std deviation change: {std_change:+.1f}%")
            else:
                print(f"✅ Stable std deviation: {std_change:+.1f}%")
        else:
            print("⚠️  Insufficient data for time-based comparison")
    else:
        print("⚠️  No timestamp column - cannot analyze trends")
    
    print()
    print("💡 RECOMMENDATIONS")
    print("-" * 70)
    
    if std < 5 or range_val < 20 or most_common_pct > 50:
        print("⚠️  Confidence scores show signs of over-compression")
        print("   Actions to consider:")
        print("   1. Review indicator weight balance")
        print("   2. Check if any single indicator dominates scoring")
        print("   3. Ensure confidence formula allows full 70-95% range")
    else:
        print("✅ Confidence distribution appears healthy")
        print("   Scores show good variation and spread")
    
    if 'result' in df.columns:
        # Check if higher confidence correlates with higher win rate
        high_conf = df[df['confidence'] >= 80]
        low_conf = df[df['confidence'] < 80]
        
        if len(high_conf) > 0 and len(low_conf) > 0:
            high_wr = len(high_conf[high_conf['result'] == 'WIN']) / len(high_conf) * 100
            low_wr = len(low_conf[low_conf['result'] == 'WIN']) / len(low_conf) * 100
            
            if high_wr > low_wr + 10:
                print("✅ Confidence correlates well with win rate")
                print(f"   High conf (≥80%): {high_wr:.1f}% WR | Low conf (<80%): {low_wr:.1f}% WR")
            elif high_wr < low_wr:
                print("⚠️  WARNING: Higher confidence has LOWER win rate!")
                print(f"   High conf (≥80%): {high_wr:.1f}% WR | Low conf (<80%): {low_wr:.1f}% WR")
                print("   Confidence formula may be inverted or broken")
    
    print()
    print("="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    
    return {
        'mean_confidence': df['confidence'].mean(),
        'median_confidence': df['confidence'].median(),
        'std_confidence': df['confidence'].std(),
        'min_confidence': df['confidence'].min(),
        'max_confidence': df['confidence'].max(),
        'total_signals': len(df)
    }

def main():
    print("\n" + "="*70)
    print("CONFIDENCE DISTRIBUTION MONITOR")
    print("="*70)
    print("Analyzing confidence score patterns and distribution health")
    print("="*70 + "\n")
    
    df = load_signal_data()
    
    if df is None or len(df) == 0:
        print("❌ No data available for analysis")
        return
    
    results = analyze_confidence_distribution(df)
    
    if results:
        print(f"\n📄 Analysis complete - results shown above")

if __name__ == "__main__":
    main()
