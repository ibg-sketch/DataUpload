# Shadow Mode Deployment Report

## Overview
Successfully implemented and deployed dual-formula signal evaluation system in shadow mode for validation before full production release.

## Deployment Date
October 22, 2025

## System Components

### 1. Core Modules

#### `dual_formula.py`
- Production-ready dual-formula evaluation system
- Separate formulas for LONG and SHORT signals (opposite RSI/EMA correlations)
- RAW-value inputs (no normalization required)
- Sigmoid transform for probability scoring (0-1 range)
- Functions:
  - `evaluate_signal()`: Main evaluation function
  - `get_formula_confidence()`: Backward-compatible 0-100 scale function

#### `shadow_mode.py`
- Wraps dual-formula with direction-specific filters
- **LONG filters:**
  - Threshold: 0.30 probability
  - RSI: 40-70
  - VWAP distance: ≤1.0%
  - Volume ratio: 0.5-1.2

- **SHORT filters:**
  - Threshold: 0.50 probability (more conservative)
  - RSI: <50
  - VWAP distance: ≤0.3% (tighter)
  - Volume ratio: ≤1.0

- **Risk parameters:**
  - TTL: 15 minutes
  - Take profit: 0.40%
  - Stop loss: 0.30%

#### `shadow_logger.py`
- Thread-safe CSV logging system
- Logs all required fields:
  - Timestamp, symbol, verdict
  - Dual-formula outputs (logit, probability, decision)
  - Market indicators (RSI, EMA, price, VWAP, volume, ATR, CVD, OI)
  - Old system comparison (decision, score)
  - Performance metrics (latency, spread, fees, slippage)
  - Filter results (passed/failed, reason)

#### `shadow_integration.py`
- Clean integration wrapper for main bot
- Non-blocking shadow mode logging
- Error handling to prevent disrupting main system
- Adds `shadow_mode` data to signal results

#### `metrics_reporter.py`
- Daily and weekly performance analysis
- Calculates:
  - Precision (average probability of sent signals)
  - Coverage (signals per day)
  - Net expectancy (theoretical profit after fees)
  - Signal reduction vs old system
  - Latency metrics
- Automated alerts:
  - Coverage drop >30%
  - Precision <30%
  - Latency >500ms
  - Negative expectancy

### 2. Integration Points

#### `main.py` (Line 277-282)
```python
# Pass full config to decide_signal for weighted scoring
start_time = time.time()
res=decide_signal(sym, interval, config=cfg, lookback_minutes=lookback, vwap_window=vwap_window, volume_spike_mult=volume_spike_mult, min_components=min_components)

# SHADOW MODE: Log dual-formula evaluation for A/B comparison (non-blocking)
from shadow_integration import evaluate_with_shadow_mode
res = evaluate_with_shadow_mode(res, start_time)
```

## Backtest Performance

Validated on 391 historical signals:

| Metric | Baseline | Shadow Mode | Improvement |
|--------|----------|-------------|-------------|
| **Overall WR** | 25.1% | **39.6%** | **+14.5%** ✅ |
| **LONG WR** | 33.6% | **40.2%** | **+6.6%** |
| **SHORT WR** | 20.0% | **37.5%** | **+17.5%** 🚀 |
| **Signal Count** | 391 | 134 | -66% (quality over quantity) |

**Key Achievement:** Filtered out 257 low-quality signals (17.5% WR), kept 134 high-quality signals (39.6% WR)

## Safety Features

1. **Shadow Mode Flag:** `SHADOW_MODE_ENABLED = True` (can be disabled instantly)
2. **Rollback Flag:** `ROLLBACK_ENABLED = True`
3. **Non-blocking:** Shadow logging wrapped in try/except to prevent disrupting main bot
4. **Error logging:** Errors recorded but don't stop signal generation

## Data Collection

### Log File: `shadow_predictions.csv`

**Fields logged:**
- Identification: ts, symbol, verdict
- Dual-formula: logit, prob, should_send
- Indicators: rsi, ema_short, ema_long, ema_diff_pct, price, vwap, vwap_dist, volume, volume_median, volume_ratio, atr
- Market data: cvd, cvd_5m, oi_change
- Comparison: old_system_decision, old_system_score
- Performance: latency_ms, spread, fee_bps, slippage_bps
- Filters: passed_filters, filter_reason

## Monitoring & Reporting

### Automated Reports
- **Daily report:** Generated via `metrics_reporter.py`
- **Metrics tracked:**
  - Total evaluations
  - Passed threshold count
  - Passed filters count
  - Would-send signals (LONG/SHORT breakdown)
  - Average probability
  - Coverage per day
  - Signal reduction vs old system
  - Latency (avg/max)
  - Net expectancy

### Alert Conditions
⚠️ Alerts triggered when:
- Coverage drops >30%
- Average probability <0.30
- Max latency >500ms
- Negative net expectancy

## Usage Instructions

### 1. Monitor Shadow Logs
```bash
# View recent predictions
tail -20 shadow_predictions.csv

# Count total logged predictions
wc -l shadow_predictions.csv

# Search for specific symbols
grep "BTCUSDT" shadow_predictions.csv
```

### 2. Generate Reports
```python
from metrics_reporter import MetricsReporter

# Daily report
reporter = MetricsReporter("shadow_predictions.csv")
print(reporter.generate_report("daily"))

# Weekly report
print(reporter.generate_report("weekly"))

# Check alerts
metrics = reporter.get_daily_metrics()
alerts = reporter.check_alerts(metrics)
for alert in alerts:
    print(alert)
```

### 3. Test Predictions
```python
from shadow_mode import should_send_signal

# Evaluate a potential signal
send, prob, details = should_send_signal(
    rsi=55.0,
    ema_short=50100.0,
    ema_long=50000.0,
    price=50000.0,
    volume=40_000_000,
    volume_median=40_000_000,
    vwap=49900.0,
    atr=200.0,
    verdict='BUY'
)

print(f"Send: {send}, Probability: {prob:.2%}")
print(f"Details: {details}")
```

## Validation Period

**Recommended:** Run shadow mode for 7-14 days to collect sufficient data before full integration.

**Success Criteria:**
- ✅ Average probability ≥30% for sent signals
- ✅ Coverage reduction acceptable for improved quality
- ✅ Latency <500ms consistently
- ✅ Positive net expectancy
- ✅ No technical errors or crashes

## Transition to Production

Once validation is complete:

1. **Review metrics:** Analyze shadow_predictions.csv and reports
2. **Compare performance:** Verify dual-formula outperforms current system
3. **Decision point:** Determine if ready for full deployment
4. **Integration:** Replace current scoring in `decide_signal()` with dual-formula
5. **Gradual rollout:** Consider A/B testing or phased deployment

## Technical Notes

- **Thread-safe:** All logging operations are thread-safe
- **Performance:** Shadow mode adds ~10-20ms latency (negligible)
- **Compatibility:** Backward compatible with existing `get_formula_confidence()` API
- **Dependencies:** Uses existing libraries (numpy, pandas)

## Files Structure

```
project_root/
├── dual_formula.py              # Core dual-formula logic
├── shadow_mode.py                # Filters and thresholds
├── shadow_logger.py              # CSV logging system
├── shadow_integration.py         # Integration wrapper
├── metrics_reporter.py           # Analysis and reporting
├── shadow_predictions.csv        # Log file (generated)
├── main.py                       # Bot (MODIFIED at line 277-282)
├── analysis/
│   ├── OPTIMAL_FORMULA_SUMMARY.md
│   ├── backtest_dual_formula.py
│   ├── directional_formula_analysis.py
│   └── derive_raw_coefficients.py
└── SHADOW_MODE_REPORT.md         # This file
```

## Next Steps

1. ✅ Shadow mode deployed and integrated
2. ⏳ **Current:** Collect data for 7-14 days
3. ⏳ **Pending:** Analyze shadow mode performance
4. ⏳ **Pending:** Decision on full production deployment
5. ⏳ **Pending:** Replace current system if validation successful

---

**Status:** ✅ **SHADOW MODE ACTIVE AND LOGGING**

**Created:** October 22, 2025
**Last Updated:** October 22, 2025
