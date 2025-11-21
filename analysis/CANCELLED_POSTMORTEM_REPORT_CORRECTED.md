# CANCELLED Signal Postmortem Analysis Report (CORRECTED)

**Generated:** 2025-11-10 12:44:06
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
- **Total CANCELLED signals analyzed:** 40 (of 1000+ available)
- **Signals that hit target after cancellation:** 19 (47.5%)
- **Signals that did NOT hit target:** 21 (52.5%)

### By Signal Type

#### BUY Signals
- **Total:** 10
- **Hit target zone after cancellation:** 5 (50.0%)
- **Did NOT hit target:** 5 (50.0%)

#### SELL Signals
- **Total:** 30
- **Hit target zone after cancellation:** 14 (46.7%)
- **Did NOT hit target:** 16 (53.3%)

---

## Adverse Deviation Analysis

**Adverse deviation** = Maximum price movement in the OPPOSITE direction of the signal:
- For BUY signals: maximum drop below entry price  
- For SELL signals: maximum rise above entry price

### Statistics
- **Average adverse deviation:** +0.32%
- **Maximum adverse deviation:** +1.36%
- **Minimum adverse deviation:** -0.66%

---

## Interpretation

### Target Hit Rate After Cancellation: 47.5%

**⚠ PRELIMINARY FINDING:** Nearly half (47.5%) of analysed cancelled signals
reached their target zone after cancellation. IF this pattern holds on larger sample, it would
suggest cancellation logic may be too aggressive.

**CAVEAT:** This conclusion is based on a LIMITED SAMPLE of 40 signals with potential
survivorship bias. Larger sample needed for definitive conclusions.

### Key Observations (Preliminary):

1. **Both BUY and SELL show ~50% target hit after cancellation**
   - BUY: 50.0%
   - SELL: 46.7%
   - Similar aggressiveness for both signal types (in this sample)

2. **Possible Overly Aggressive Cancellation**
   - Almost half of cancelled signals in this sample would have been successful
   - May indicate potential profit being left on the table
   - Requires validation on larger dataset

3. **Low Adverse Deviation: +0.32% average**
   - Minimal adverse price movement after cancellation
   - Signals cancelled early, limiting both risk AND reward
   - Suggests risk-averse cancellation strategy

---

## Detailed Statistics by Symbol

| Symbol | Total | Target Hit | Hit Rate | Avg Adverse Dev |
|--------|-------|------------|----------|-----------------|
| ADAUSDT | 6 | 4 | 66.7% | -0.42% |
| BNBUSDT | 2 | 0 | 0.0% | +0.76% |
| BTCUSDT | 8 | 5 | 62.5% | +0.14% |
| ETHUSDT | 9 | 4 | 44.4% | +0.11% |
| HYPEUSDT | 7 | 2 | 28.6% | +0.95% |
| LINKUSDT | 1 | 0 | 0.0% | -0.15% |
| SOLUSDT | 7 | 4 | 57.1% | +0.73% |


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

### 2. **IF Larger Sample Confirms ~48% Hit Rate:**
   - Review and potentially relax cancellation criteria
   - Investigate if increased TTL tolerance would improve profitability
   - Consider symbol-specific cancellation thresholds

### 3. **Risk vs Reward Balance**
Current strategy (in this sample):
- ✅ Minimizes adverse deviation (+0.32% avg)
- ❌ May cancel too many potentially profitable signals (47.5%)

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
- Corrected SELL hit rate: 46.7% (CORRECT - enters target zone)
- Overall impact: 27.5% → 47.5% total hit rate

The corrected logic now properly reflects that **entering** the target zone (reaching target_max
for SELL signals, target_min for BUY signals) constitutes a successful target hit.

---

**Full data:** `cancelled_postmortem_results_CORRECTED.csv`

**Script:** `analysis/scripts/cancelled_signal_postmortem.py` (with corrected logic)
