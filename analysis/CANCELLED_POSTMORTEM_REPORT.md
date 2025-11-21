# CANCELLED Signal Postmortem Analysis Report

**Generated:** 2025-11-10 12:37:43
**Status:** Preliminary results (40 signals analyzed from 100+ available)

## Summary

This analysis examines CANCELLED signals to determine:
1. **Did price reach target zone** after cancellation but within original TTL?
2. **Maximum adverse deviation** in the opposite direction after cancellation

---

## Key Findings

### Overall Results
- **Total CANCELLED signals analyzed:** 40
- **Signals that hit target after cancellation:** 11 (27.5%)
- **Signals that did NOT hit target:** 29 (72.5%)

### By Signal Type

#### BUY Signals
- **Total:** 10
- **Hit target zone after cancellation:** 5 (50.0%)
- **Did NOT hit target:** 5 (50.0%)

#### SELL Signals
- **Total:** 30
- **Hit target zone after cancellation:** 6 (20.0%)
- **Did NOT hit target:** 24 (80.0%)

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

### Target Hit Rate After Cancellation: 27.5%

**✅ GOOD:** Most cancelled signals (72.5%) did not reach target zone after cancellation.
This suggests the cancellation logic is reasonably effective - signals are being cancelled
when market conditions truly deteriorate.

**However:** 27.5% of cancelled signals DID reach their target zone after cancellation,
particularly BUY signals (50% hit rate). This suggests there may be room for improvement
in the BUY signal cancellation criteria to reduce premature cancellations.

### Key Observations:

1. **BUY vs SELL asymmetry:** BUY signals show 50% target hit after cancellation, while
   SELL signals only 20%. This suggests BUY cancellation logic may be too aggressive.

2. **Symbol variation:** Some symbols like ADAUSDT (66.7% hit) and ETHUSDT (44.4% hit)
   frequently reached targets after cancellation, while others like SOLUSDT and BNBUSDT
   (0% hit) show effective cancellation.

3. **Low adverse deviation:** Average +0.32% suggests minimal risk exposure
   after cancellation. Signals are being cancelled relatively close to entry price.

---

## Detailed Statistics by Symbol

| Symbol | Total | Target Hit | Hit Rate | Avg Adverse Dev |
|--------|-------|------------|----------|-----------------|
| ADAUSDT | 6 | 4 | 66.7% | -0.42% |
| BNBUSDT | 2 | 0 | 0.0% | +0.76% |
| BTCUSDT | 8 | 2 | 25.0% | +0.14% |
| ETHUSDT | 9 | 4 | 44.4% | +0.11% |
| HYPEUSDT | 7 | 1 | 14.3% | +0.95% |
| LINKUSDT | 1 | 0 | 0.0% | -0.15% |
| SOLUSDT | 7 | 0 | 0.0% | +0.73% |


---

## Recommendations

Based on this preliminary analysis:

1. **BUY Signal Cancellation:** Consider relaxing cancellation criteria for BUY signals,
   as 50% of cancelled BUY signals reached their target zone.

2. **Symbol-Specific Tuning:** ADAUSDT shows 66.7% target hit after cancellation - review
   cancellation logic specifically for this symbol.

3. **SELL Logic Working Well:** Only 20% of cancelled SELL signals reached targets,
   indicating effective cancellation logic for SELL signals.

4. **Further Analysis Needed:** This is based on 40 signals. Full analysis of 1000+
   signals would provide more statistical confidence.

---

## Methodology

1. **Data Source:** effectiveness_log.csv (CANCELLED signals) matched with signals_log.csv (original metadata)
2. **Time Window:** From cancellation timestamp to original TTL expiry time
3. **Target Zone Check:**
   - BUY: Price high >= target_min
   - SELL: Price low <= target_min
4. **Adverse Deviation:**
   - BUY: Minimum price drop from entry
   - SELL: Maximum price rise from entry
5. **Price Data:** 5-minute candles from Coinalyze API

---

**Note:** This is a preliminary report based on 40 signals. API rate limits prevented
analysis of the full dataset. Full results available in: `cancelled_postmortem_results.csv`
