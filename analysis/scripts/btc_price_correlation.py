#!/usr/bin/env python3
"""
BTC Price Correlation Analyzer
Analyzes correlation between Bitcoin and altcoins:
- Lag correlation (speed of following BTC)
- Directional similarity (candle pattern matching)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import yaml
import json
from datetime import datetime
from analysis.tools.btc_correlation import (
    fetch_all_symbols,
    align_timestamps,
    save_aligned_data,
    analyze_all_coins
)
from analysis.tools.btc_correlation.correlation_analyzer import generate_summary_report


def main():
    print("="*80)
    print("BTC PRICE CORRELATION ANALYZER")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    symbols = config['symbols']
    print(f"\nMonitored symbols: {', '.join(symbols)}")
    
    DAYS = 7
    MAX_LAG = 12
    
    print(f"\nConfiguration:")
    print(f"  Days of data: {DAYS}")
    print(f"  Max lag: ±{MAX_LAG} periods (±{MAX_LAG*5} minutes)")
    print(f"  Candle interval: 5 minutes")
    
    print("\n" + "="*80)
    print("STEP 1: FETCH DATA FROM LOCAL ANALYSIS LOG")
    print("="*80)
    
    raw_data = fetch_all_symbols(symbols, days=DAYS)
    
    if 'BTCUSDT' not in raw_data:
        print("\n❌ ERROR: Failed to fetch BTCUSDT data")
        return 1
    
    if len(raw_data) < 2:
        print(f"\n❌ ERROR: Insufficient data (need at least 2 symbols, got {len(raw_data)})")
        return 1
    
    print("\n" + "="*80)
    print("STEP 2: ALIGN TIMESTAMPS")
    print("="*80)
    
    aligned_data = align_timestamps(raw_data)
    
    print("\n" + "="*80)
    print("STEP 3: SAVE ALIGNED DATA")
    print("="*80)
    
    save_aligned_data(aligned_data, output_dir='data/btc_corr')
    
    print("\n" + "="*80)
    print("STEP 4: CORRELATION ANALYSIS")
    print("="*80)
    
    results_df = analyze_all_coins(aligned_data, max_lag=MAX_LAG)
    
    print("\n" + "="*80)
    print("STEP 5: SAVE RESULTS")
    print("="*80)
    
    os.makedirs('analysis/results', exist_ok=True)
    
    csv_path = 'analysis/results/btc_corr_summary.csv'
    results_df.to_csv(csv_path, index=False)
    print(f"\n  ✅ CSV: {csv_path}")
    
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'analysis_config': {
            'days': DAYS,
            'max_lag_periods': MAX_LAG,
            'max_lag_minutes': MAX_LAG * 5,
            'candle_interval': '5m'
        },
        'correlations': results_df.to_dict(orient='records')
    }
    
    json_path = 'analysis/results/btc_corr_summary.json'
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"  ✅ JSON: {json_path}")
    
    report = generate_summary_report(results_df)
    
    txt_path = 'analysis/results/btc_corr_report.txt'
    with open(txt_path, 'w') as f:
        f.write(report)
    print(f"  ✅ Report: {txt_path}")
    
    print(report)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nOutput files:")
    print(f"  1. {csv_path} - Full metrics table")
    print(f"  2. {json_path} - JSON for AI integration")
    print(f"  3. {txt_path} - Human-readable report")
    print(f"  4. data/btc_corr/*.csv - Aligned OHLCV data")
    
    return 0


if __name__ == '__main__':
    exit(main())
