#!/usr/bin/env python3
"""Generate fully corrected CANCELLED signal postmortem report"""

import pandas as pd
from datetime import datetime

def generate_report():
    df = pd.read_csv('analysis/cancelled_postmortem_results_CORRECTED.csv')
    
    total_signals = len(df)
    target_hit_count = int(df['target_hit_after_cancel'].sum())
    target_hit_rate = (target_hit_count / total_signals) * 100
    
    buy_df = df[df['verdict'] == 'BUY']
    sell_df = df[df['verdict'] == 'SELL']
    
    buy_hit = int(buy_df['target_hit_after_cancel'].sum())
    buy_total = len(buy_df)
    buy_rate = (buy_hit / buy_total * 100) if buy_total > 0 else 0
    
    sell_hit = int(sell_df['target_hit_after_cancel'].sum())
    sell_total = len(sell_df)
    sell_rate = (sell_hit / sell_total * 100) if sell_total > 0 else 0
    
    avg_dev = df['adverse_deviation_pct'].mean()
    max_dev = df['adverse_deviation_pct'].max()
    min_dev = df['adverse_deviation_pct'].min()
    
    report = f"""# CANCELLED Signal Postmortem Analysis Report (CORRECTED)

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Status:** ⚠ LIMITED SAMPLE - 40 signals analyzed (rate-limit constrained)
**Note:** Contains corrected SELL target detection logic

---

## ⚠ **IMPORTANT: Sample Size Limitation**

This analysis is based on **only 40 signals** from 1000+ available, due to strict API rate limits.
This small sample may not be statistically representative and could suffer from **survivorship bias**.

**Recommendation:** Treat findings as preliminary. Full analysis with persistent caching and
batching is needed for production-grade conclusions.

---

## Summary

This analysis examines CANCELLED signals to determine:
1. **Did price reach target zone** after cancellation but within original TTL?
2. **Maximum adverse deviation** in the opposite direction after cancellation

---

## Key Findings

### Overall Results
- **Total CANCELLED signals analyzed:** {total_signals} (of 1000+ available)
- **Signals that hit target after cancellation:** {target_hit_count} ({target_hit_rate:.1f}%)
- **Signals that did NOT hit target:** {total_signals - target_hit_count} ({100 - target_hit_rate:.1f}%)

### By Signal Type

#### BUY Signals
- **Total:** {buy_total}
- **Hit target zone after cancellation:** {buy_hit} ({buy_rate:.1f}%)
- **Did NOT hit target:** {buy_total - buy_hit} ({100 - buy_rate if buy_total > 0 else 0:.1f}%)

#### SELL Signals
- **Total:** {sell_total}
- **Hit target zone after cancellation:** {sell_hit} ({sell_rate:.1f}%)
- **Did NOT hit target:** {sell_total - sell_hit} ({100 - sell_rate if sell_total > 0 else 0:.1f}%)

---

## Adverse Deviation Analysis

**Adverse deviation** = Maximum price movement in the OPPOSITE direction of the signal:
- For BUY signals: maximum drop below entry price  
- For SELL signals: maximum rise above entry price

### Statistics
- **Average adverse deviation:** {avg_dev:+.2f}%
- **Maximum adverse deviation:** {max_dev:+.2f}%
- **Minimum adverse deviation:** {min_dev:+.2f}%

---

## Interpretation

### Target Hit Rate After Cancellation: {target_hit_rate:.1f}%

**⚠ PRELIMINARY FINDING:** Nearly half ({target_hit_rate:.1f}%) of analysed cancelled signals
reached their target zone after cancellation. IF this pattern holds on larger sample, it would
suggest cancellation logic may be too aggressive.

**CAVEAT:** This conclusion is based on a LIMITED SAMPLE of 40 signals with potential
survivorship bias. Larger sample needed for definitive conclusions.

### Key Observations (Preliminary):

1. **Both BUY and SELL show ~50% target hit after cancellation**
   - BUY: {buy_rate:.1f}%
   - SELL: {sell_rate:.1f}%
   - Similar aggressiveness for both signal types (in this sample)

2. **Possible Overly Aggressive Cancellation**
   - Almost half of cancelled signals in this sample would have been successful
   - May indicate potential profit being left on the table
   - Requires validation on larger dataset

3. **Low Adverse Deviation: {avg_dev:+.2f}% average**
   - Minimal adverse price movement after cancellation
   - Signals cancelled early, limiting both risk AND reward
   - Suggests risk-averse cancellation strategy

---

## Detailed Statistics by Symbol

| Symbol | Total | Target Hit | Hit Rate | Avg Adverse Dev |
|--------|-------|------------|----------|-----------------|
"""
    
    for symbol in sorted(df['symbol'].unique()):
        sym_df = df[df['symbol'] == symbol]
        sym_total = len(sym_df)
        sym_hit = int(sym_df['target_hit_after_cancel'].sum())
        sym_hit_rate = (sym_hit / sym_total * 100)
        sym_avg_dev = sym_df['adverse_deviation_pct'].mean()
        
        report += f"| {symbol} | {sym_total} | {sym_hit} | {sym_hit_rate:.1f}% | {sym_avg_dev:+.2f}% |\n"
    
    report += f"""

### Symbol-Specific Insights (Preliminary):

- **ADAUSDT:** 66.7% hit rate (4/6) - highest in sample, potential cancellation issue
- **BTCUSDT:** 62.5% hit rate (5/8) - high rate, review needed
- **SOLUSDT:** 57.1% hit rate (4/7) - moderate-high rate
- **ETHUSDT:** 44.4% hit rate (4/9) - moderate rate
- **HYPEUSDT:** 28.6% hit rate (2/7) - lower rate, cancellation working better
- **BNBUSDT, LINKUSDT:** 0.0% hit rate - effective cancellation (very small sample)

**Note:** Symbol-level conclusions especially unreliable due to tiny sample sizes (1-9 signals per symbol).

---

## Recommendations

Based on this **preliminary** analysis:

### 1. **Expand Sample Size (CRITICAL)**
- Current 40-signal sample too small for production decisions
- Implement persistent caching and batching to process 1000+ signals
- Re-run analysis on full dataset before making strategy changes

### 2. **IF Larger Sample Confirms ~{target_hit_rate:.0f}% Hit Rate:**
   - Review and potentially relax cancellation criteria
   - Investigate if increased TTL tolerance would improve profitability
   - Consider symbol-specific cancellation thresholds

### 3. **Risk vs Reward Balance**
Current strategy (in this sample):
- ✅ Minimizes adverse deviation ({avg_dev:+.2f}% avg)
- ❌ May cancel too many potentially profitable signals ({target_hit_rate:.1f}%)

IF confirmed on larger sample: Accept slightly higher adverse deviation to capture more profits.

### 4. **Next Steps**
- Implement symbol-grouped batching with persistent kline caching
- Expand analysis to 1000+ signals for statistical confidence
- Analyze temporal patterns (time-of-day, market conditions)
- Enable granular symbol-specific cancellation tuning

---

## Methodology

1. **Data Source:** effectiveness_log.csv (CANCELLED signals) matched with signals_log.csv (original metadata)
2. **Time Window:** From cancellation timestamp to original TTL expiry time
3. **Target Zone Check (CORRECTED LOGIC):**
   - **BUY:** Price high >= target_min (enters target zone from below)
   - **SELL:** Price low <= target_max (enters target zone from above - FIXED from target_min)
4. **Adverse Deviation:**
   - BUY: Minimum price drop from entry (max downward movement)
   - SELL: Maximum price rise from entry (max upward movement)
5. **Price Data:** 5-minute candles from Coinalyze API

### Sample Limitations:
- Only 40 of 100+ attempted signals processed (API rate limits)
- Survivorship bias: failed API requests may not be random
- Non-representative temporal coverage due to rate-limit dropouts
- Symbol distribution: 1-9 signals per symbol (statistically insufficient)

---

## Correction Note

**Critical bug fixed:** Initial report contained incorrect SELL target detection logic
that checked if price reached the FAR edge (target_min) instead of the NEAR edge (target_max).

Impact of fix:
- Old SELL hit rate: 20.0% (INCORRECT - too restrictive)
- Corrected SELL hit rate: {sell_rate:.1f}% (CORRECT - enters target zone)
- Overall impact: 27.5% → {target_hit_rate:.1f}% total hit rate

The corrected logic now properly reflects that **entering** the target zone (reaching target_max
for SELL signals, target_min for BUY signals) constitutes a successful target hit.

---

**Full data:** `cancelled_postmortem_results_CORRECTED.csv`

**Script:** `analysis/scripts/cancelled_signal_postmortem.py` (with corrected logic)
"""
    
    # Write report
    with open('analysis/CANCELLED_POSTMORTEM_REPORT_CORRECTED.md', 'w') as f:
        f.write(report)
    
    print("✅ Corrected report generated successfully")
    print(f"   Total signals: {total_signals}")
    print(f"   Target hit rate: {target_hit_rate:.1f}%")
    print(f"   BUY hit rate: {buy_rate:.1f}%")
    print(f"   SELL hit rate: {sell_rate:.1f}%")

if __name__ == '__main__':
    generate_report()
