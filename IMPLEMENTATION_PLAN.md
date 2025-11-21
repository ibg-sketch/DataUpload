# 5-Minute Lookback Window Implementation Plan

## Objective
Implement 5-minute lookback aggregation based on timeframe optimizer results showing 81.4% prediction accuracy.

## Current Behavior
- `decide_signal()` fetches instant market data (CVD, OI, VWAP, RSI at current moment)
- Makes trading decisions based on single data point
- No temporal aggregation

## Proposed Changes

### 1. Add Aggregation Function
```python
def aggregate_recent_analysis(symbol, minutes=5):
    """
    Aggregate the last N minutes of analysis data from analysis_log.csv
    
    Args:
        symbol: Trading pair
        minutes: Lookback window (default 5 based on optimizer)
    
    Returns:
        Dict with aggregated values or None if insufficient data
    """
    - Read analysis_log.csv
    - Filter for symbol and last N minutes
    - Calculate aggregated metrics:
        * cvd_mean, cvd_std, cvd_max
        * oi_change_mean, oi_change_std
        * vwap_deviation_mean, vwap_deviation_std
        * rsi_mean, rsi_min, rsi_max
        * volume_sum
    - Return None if < 2 data points (insufficient history)
```

### 2. Modify decide_signal()
```python
def decide_signal(symbol, interval, config=None, use_aggregation=True, aggregation_minutes=5, ...):
    """
    New parameters:
    - use_aggregation: Enable/disable 5m lookback (default True)
    - aggregation_minutes: Lookback window (default 5)
    """
    
    # Try to get aggregated data first
    if use_aggregation:
        agg_data = aggregate_recent_analysis(symbol, aggregation_minutes)
        if agg_data:
            # Use aggregated values for decision
            cvd = agg_data['cvd_mean']
            d_oi = agg_data['oi_change_mean']
            price_vs_vwap_pct = agg_data['vwap_deviation_mean']
            rsi = agg_data['rsi_mean']
            # ... etc
        else:
            # Fall back to instant values (first few cycles)
            cvd = compute_cvd(symbol, lb)
            # ... current logic
    else:
        # Legacy mode: instant values
        # ... current logic
```

### 3. Pattern Optimization from Analysis
Based on pattern_analyzer.py results for 60-minute lookback showing 21.4% win rate:

**Winning Pattern Characteristics:**
- RSI median: 85.4 (range 75-87) ← **EXTREME RSI PREDICTS WINS!**
- CVD median: 2.9M (range 2M-5.8M)
- VWAP deviation median: 2.63% (range 1.73-4.19%)
- Signal duration: 28 minutes avg

**Critical Insight:** Current RSI filter BLOCKS extreme RSI, but data shows extreme RSI is the STRONGEST predictor of wins!

### 4. Optional: Reverse RSI Logic
```python
# CURRENT (line ~404 in smart_signal.py):
rsi_ok = not components.get('RSI_overbought', False)  # BLOCKS RSI > 70

# PROPOSED (based on data):
rsi_extreme_bullish = (rsi < 35)  # Oversold = buy opportunity  
rsi_extreme_bearish = (rsi > 65)  # Overbought = sell opportunity
# ADD as PRIMARY signal, not filter!
```

## Implementation Strategy

1. **Phase 1: Add aggregation (non-breaking)**
   - Add `aggregate_recent_analysis()` function
   - Add `use_aggregation` parameter (default False for safety)
   - Test aggregation logic independently

2. **Phase 2: Enable by default**
   - Change `use_aggregation=True` by default
   - Monitor signal generation for 1-2 hours
   - Verify no degradation

3. **Phase 3: RSI optimization (optional)**
   - Modify RSI filter based on empirical data
   - Requires careful testing as this reverses current logic

## Risk Mitigation
- Make aggregation opt-in initially
- Fall back to instant values if aggregation fails
- Preserve all current logic as fallback
- Test thoroughly before enabling by default

## Expected Impact
- Accuracy improvement: +72.1% over baseline (from optimizer)
- Signal quality: Better filtering based on trends vs instant values
- Win rate: Potential increase if RSI logic is also optimized

## Files to Modify
- `smart_signal.py`: Add aggregation function and modify decide_signal()
- `config.yaml`: Optionally add `use_aggregation: true` per symbol
- `main.py`: Pass aggregation parameters if needed

## Testing Plan
1. Run with `use_aggregation=False` (baseline)
2. Run with `use_aggregation=True, aggregation_minutes=5`
3. Compare signal generation frequency and quality
4. Monitor effectiveness_log.csv for win rate changes

## Architect Review Needed
- [ ] Is aggregation approach sound?
- [ ] Should we reverse RSI logic based on empirical data?
- [ ] Are there edge cases we're missing?
- [ ] Should this be symbol-specific or global?
