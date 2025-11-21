# Indicator Combination Analysis

This directory contains the complete analysis for discovering high win-rate indicator combinations.

## Structure

### `/scripts/`
- `forward_opportunity_finder.py` - Labels candles with forward-looking outcomes (BUY/SELL opportunities)
- `combination_tester.py` - Tests 2-way and 3-way indicator combinations
- `indicator_discovery.py` - Univariate analysis of individual indicators
- `forward_pattern_discovery.py` - Original pattern discovery script

### `/results/`
- `combination_test_results.json` - Full database of tested combinations
- `opportunity_patterns.json` - Single indicator analysis results

### Reports
- `COMBINATION_ANALYSIS_REPORT.md` - **MAIN REPORT** with findings and recommendations

## Key Findings

**Best 2-Way Combinations:**
- BUY: OI Change > +0.22% AND RSI < 35.19 → **49.1% WR** (318 signals/week)
- SELL: VWAP > +0.09% AND RSI < 42.19 → **64.9% WR** (151 signals/week)

**Best 3-Way Combination:**
- VWAP < -1.26% AND OI > +0.22% AND RSI < 35.19 → **52.4% WR** (275 signals)

## Next Steps

See `COMBINATION_ANALYSIS_REPORT.md` for full implementation roadmap.
