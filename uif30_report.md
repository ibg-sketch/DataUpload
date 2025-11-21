# UIF-12 Backtest Report

**Generated:** 2025-11-11 12:09:42

**Horizon:** 30 minutes
**Thresholds:** 0.5, 1.0%

## Features Analyzed

Available: 8/12 UIF-12 features

- zcvd
- doi_pct
- dev_sigma
- rsi_dist
- adx14
- psar
- momentum5
- vol_accel

## Overall Metrics

| Threshold | AUROC | PR-AUC | Lift (Top20%) | Hit-Rate | Avg Time-to-Hit | Samples |
|-----------|-------|--------|---------------|----------|-----------------|----------|
| 0.5% | 0.507 | 0.146 | 0.93x | 14.2% | 19.2m | 760 |
| 1.0% | 0.927 | 0.017 | 5.00x | 0.3% | 27.4m | 760 |

## Per-Symbol Metrics (0.5% threshold)

| Symbol | AUROC | Lift | Hit-Rate | Samples |
|--------|-------|------|----------|----------|
| BNBUSDT | 0.812 | 2.63x | 2.5% | 79 |
| XRPUSDT | 0.767 | 2.62x | 6.3% | 63 |
| HYPEUSDT | 0.576 | 0.67x | 20.0% | 75 |
| LINKUSDT | 0.575 | 1.36x | 29.3% | 75 |
| DOGEUSDT | 0.506 | 1.18x | 28.2% | 78 |
| AVAXUSDT | 0.475 | 0.83x | 21.8% | 55 |
| SOLUSDT | 0.427 | 1.33x | 17.4% | 69 |
| ETHUSDT | 0.333 | 0.00x | 11.4% | 79 |
| ADAUSDT | 0.298 | 0.00x | 16.9% | 59 |
| BTCUSDT | nan | nanx | 0.0% | 57 |
| TRXUSDT | nan | nanx | 0.0% | 71 |

## Data Availability Warning

⚠️ **INSUFFICIENT DATA**: Only 8/12 features available

**Recommendation:** Run UIF Feature Engine for 1-2 days to collect comprehensive data before production wiring.


## Next Steps

1. ✅ Phase 3: Wire features with zero weights for diagnostic logging
2. 📊 Collect 1-2 days of comprehensive UIF data
3. 🔄 Re-run backtest with full dataset
4. 🎯 Optimize weights using ML-based feature selection
