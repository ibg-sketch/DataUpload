# CANCELLED Signal Postmortem Analysis - Yesterday & Today

**Period:** November 9-10, 2025
**Generated:** 2025-11-10 13:15:40
**Total Analyzed:** 156 CANCELLED signals

---

## 📊 Key Findings

### Overall Results
- **Total signals analyzed:** 156
- **Signals that hit target after cancellation:** 66 (42.3%)
- **Signals that did NOT hit target:** 90 (57.7%)

### By Signal Type

#### BUY Signals
- **Total:** 81
- **Hit target zone after cancellation:** 23 (28.4%)
- **Did NOT hit target:** 58 (71.6%)

#### SELL Signals
- **Total:** 75
- **Hit target zone after cancellation:** 43 (57.3%)
- **Did NOT hit target:** 32 (42.7%)

---

## 🎯 Interpretation

### Target Hit Rate: 42.3%

**FINDING:** 42.3% of cancelled signals from yesterday+today reached their
target zone after cancellation. This suggests moderate cancellation aggressiveness.

### Critical Observation: SELL vs BUY Asymmetry

**⚠ SIGNIFICANT FINDING:** SELL signals show **57.3% hit rate** compared to 
BUY signals at **28.4% hit rate**.

**This 28.9% difference indicates:**
- SELL cancellation logic is significantly MORE AGGRESSIVE than needed
- Nearly 57% of cancelled SELL signals would have been profitable
- BUY cancellation logic appears more appropriately calibrated

---

## 💰 Adverse Deviation Analysis

**Adverse deviation** = Maximum price movement against the signal after cancellation:
- For BUY: maximum drop below entry price  
- For SELL: maximum rise above entry price

### Statistics
- **Average adverse deviation:** +0.05%
- **Maximum adverse deviation:** +1.40%
- **Minimum adverse deviation:** -1.33%

**Low average adverse deviation (+0.05%) indicates:**
- Risk-averse cancellation strategy
- Minimal downside after cancellation
- But potentially leaving profits on the table

---

## 🪙 Detailed Statistics by Symbol

| Symbol | Total | Target Hit | Hit Rate | Avg Adverse Dev |
|--------|-------|------------|----------|-----------------|
| AVAXUSDT | 34 | 20 | 58.8% | +0.12% |
| BNBUSDT | 1 | 0 | 0.0% | +0.37% |
| BTCUSDT | 63 | 13 | 20.6% | -0.10% |
| DOGEUSDT | 15 | 10 | 66.7% | +0.09% |
| ETHUSDT | 1 | 0 | 0.0% | +0.37% |
| HYPEUSDT | 27 | 19 | 70.4% | +0.34% |
| LINKUSDT | 15 | 4 | 26.7% | -0.07% |


### Symbol-Specific Insights:
- **HYPEUSDT:** 70.4% hit rate (19/27) - cancellation too aggressive
- **DOGEUSDT:** 66.7% hit rate (10/15) - cancellation too aggressive
- **AVAXUSDT:** 58.8% hit rate (20/34) - cancellation too aggressive

- **BTCUSDT:** 20.6% hit rate (13/63) - cancellation working better
- **BNBUSDT:** 0.0% hit rate (0/1) - cancellation working better
- **ETHUSDT:** 0.0% hit rate (0/1) - cancellation working better


---

## 🎓 Recommendations

Based on analysis of 156 signals from November 9-10, 2025:

### 1. SELL Cancellation Logic Requires Immediate Attention

- **Current SELL hit rate: 57.3%** - critically high
- Nearly 3 out of 5 SELL signals are cancelled prematurely
- Consider relaxing SELL cancellation criteria by 20-30%
- Review RSI, ADX, or other indicators used for SELL cancellation

### 2. BUY Cancellation Logic is Better Calibrated

- **Current BUY hit rate: 28.4%** - more reasonable
- Still room for improvement, but less urgent
- Consider minor adjustment (10-15% relaxation)

### 3. Symbol-Specific Tuning Recommended

Top priorities for cancellation logic review:
- **HYPEUSDT**: 70.4% hit rate - investigate cancellation triggers
- **DOGEUSDT**: 66.7% hit rate - investigate cancellation triggers
- **AVAXUSDT**: 58.8% hit rate - investigate cancellation triggers


### 4. Risk vs Reward Balance

Current strategy (yesterday+today):
- ✅ Minimizes adverse deviation (+0.05% avg)
- ⚠ Potentially missing 42.3% of profitable opportunities
- 💡 Recommendation: Accept slightly higher adverse deviation (up to +0.5%) to capture more profits

---

## 📈 Comparison with Previous Analysis

| Metric | Previous (40 signals) | Current (156 signals) | Change |
|--------|----------------------|----------------------|--------|
| Overall Hit Rate | 47.5% | 42.3% | -5.2% |
| BUY Hit Rate | 50.0% | 28.4% | -21.6% |
| SELL Hit Rate | 46.7% | 57.3% | +10.6% |
| Avg Adverse Dev | +0.32% | +0.05% | -0.27% |

**Note:** Results vary between time periods and symbol distributions. Current analysis 
covers more recent data (Nov 9-10) with larger sample size.

---

## ⚙ Methodology

1. **Data Source:** effectiveness_log.csv (CANCELLED signals) + signals_log.csv (metadata)
2. **Time Period:** November 9-10, 2025 (yesterday + today)
3. **Analysis Window:** From cancellation time to original TTL expiry
4. **Target Detection:**
   - **BUY:** Price high >= target_min (enters target zone)
   - **SELL:** Price low <= target_max (enters target zone - corrected logic)
5. **Optimization:** SQLite kline caching + symbol-grouped batching
6. **Processing:** 156 signals successfully analyzed

---

**Data Files:**
- Detailed Results: 
- This Report: 
- Analysis Script: 
- Kline Cache: 
