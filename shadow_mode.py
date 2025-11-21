"""
Shadow Mode Signal Evaluator
Wraps dual_formula.py with direction-specific filters and thresholds for validation.

Filters (data-driven optimized with adaptive VWAP thresholds by market regime):
- LONG: threshold = 0.30, RSI 40-70, VWAP regime-adaptive (1.5-2.2%), volume_ratio 0.5-1.2
  * strong_bull: 2.2% (unlock 88 blocked opportunities)
  * bull_warning: 1.5% (conservative optimal)
  * sideways: 1.5% (reduce noise)
  * bear_warning: 2.0% (unlock 49 opportunities)
  * strong_bear: 2.0% (counter-trend working well)
  * neutral/bear_trend: 2.0% (default)
- SHORT: threshold = 0.50, RSI <50, VWAP ≤0.3%, volume_ratio ≤1.0
"""

from typing import Tuple, Optional
from dual_formula import evaluate_signal as dual_formula_evaluate

# Shadow mode configuration
SHADOW_MODE_ENABLED = True
ROLLBACK_ENABLED = True

# Direction-specific thresholds (as specified in requirements)
THRESHOLD_LONG = 0.30   # 30% probability for LONG signals
THRESHOLD_SHORT = 0.50  # 50% probability for SHORT signals (more conservative)

# Adaptive VWAP distance thresholds by market regime (data-driven optimization)
# Based on 24h analysis of 8,808 market checks revealing regime-specific patterns
VWAP_DIST_MAX_BY_REGIME = {
    'strong_bull': 2.2,   # 130 blocked, avg 2.16% VWAP dist → unlock 88 opportunities
    'bull_warning': 1.5,  # 17 BUY signals, 0 blocked → conservative optimal
    'sideways': 1.5,      # 51 BUY signals, 7 blocked → reduce noise
    'bear_warning': 2.0,  # 49 blocked, avg 1.70% VWAP dist → unlock opportunities
    'strong_bear': 2.0,   # 86 BUY signals, 50-60% conversion → counter-trend working well
    'bear_trend': 2.0,    # Default for backwards compatibility
    'neutral': 2.0        # Default fallback
}

# Direction-specific filters (VWAP threshold now regime-adaptive)
LONG_FILTERS = {
    'rsi_min': 40.0,
    'rsi_max': 70.0,
    'vwap_dist_max': 2.0,  # Default (overridden by regime-specific value)
    'volume_ratio_min': 0.5,
    'volume_ratio_max': 1.2
}

SHORT_FILTERS = {
    'rsi_max': 50.0,  # RSI must be < 50
    'vwap_dist_max': 0.3,  # 0.3% max distance from VWAP (tighter)
    'volume_ratio_max': 1.0  # Volume must be ≤ median
}

# Risk management parameters
RISK_PARAMS = {
    'ttl_minutes': 15,  # 15 minute time-to-live
    'take_profit_pct': 0.40,  # 0.40% take profit
    'stop_loss_pct': 0.30  # 0.30% stop loss
}


def check_long_filters(rsi: float, vwap_dist_pct: float, volume_ratio: float, regime: str = 'neutral') -> Tuple[bool, Optional[str]]:
    """
    Check if LONG signal passes all filters with regime-adaptive VWAP threshold.
    
    Args:
        rsi: RSI value (0-100)
        vwap_dist_pct: Distance from VWAP as percentage
        volume_ratio: Current volume / median volume
        regime: Market regime (strong_bull, bull_warning, sideways, bear_warning, strong_bear, bear_trend, neutral)
    
    Returns:
        Tuple of (passed, rejection_reason)
    """
    if not (LONG_FILTERS['rsi_min'] <= rsi <= LONG_FILTERS['rsi_max']):
        return False, f"RSI {rsi:.1f} outside range [{LONG_FILTERS['rsi_min']}, {LONG_FILTERS['rsi_max']}]"
    
    # Use regime-specific VWAP threshold
    vwap_threshold = VWAP_DIST_MAX_BY_REGIME.get(regime, LONG_FILTERS['vwap_dist_max'])
    if vwap_dist_pct > vwap_threshold:
        return False, f"VWAP distance {vwap_dist_pct:.2f}% > {vwap_threshold}% ({regime})"
    
    if not (LONG_FILTERS['volume_ratio_min'] <= volume_ratio <= LONG_FILTERS['volume_ratio_max']):
        return False, f"Volume ratio {volume_ratio:.2f} outside range [{LONG_FILTERS['volume_ratio_min']}, {LONG_FILTERS['volume_ratio_max']}]"
    
    return True, None


def check_short_filters(rsi: float, vwap_dist_pct: float, volume_ratio: float) -> Tuple[bool, Optional[str]]:
    """
    Check if SHORT signal passes all filters.
    
    Args:
        rsi: RSI value (0-100)
        vwap_dist_pct: Distance from VWAP as percentage
        volume_ratio: Current volume / median volume
    
    Returns:
        Tuple of (passed, rejection_reason)
    """
    if rsi >= SHORT_FILTERS['rsi_max']:
        return False, f"RSI {rsi:.1f} >= {SHORT_FILTERS['rsi_max']}"
    
    if vwap_dist_pct > SHORT_FILTERS['vwap_dist_max']:
        return False, f"VWAP distance {vwap_dist_pct:.2f}% > {SHORT_FILTERS['vwap_dist_max']}%"
    
    if volume_ratio > SHORT_FILTERS['volume_ratio_max']:
        return False, f"Volume ratio {volume_ratio:.2f} > {SHORT_FILTERS['volume_ratio_max']}"
    
    return True, None


def evaluate_signal_with_filters(
    rsi: float,
    ema_short: float,
    ema_long: float,
    price: float,
    volume: float,
    volume_median: float,
    vwap: float,
    atr: float,
    verdict: str,  # 'BUY' or 'SELL'
    regime: str = 'neutral'  # Market regime for adaptive filtering
) -> Tuple[float, float, bool, bool, Optional[str]]:
    """
    Evaluate signal using dual-formula with direction-specific filters.
    
    Args:
        rsi: RSI value (0-100)
        ema_short: Short-term EMA
        ema_long: Long-term EMA
        price: Current price
        volume: Current volume
        volume_median: Median volume
        vwap: Volume-weighted average price
        atr: Average True Range
        verdict: Signal direction ('BUY' or 'SELL')
    
    Returns:
        Tuple of (logit, probability, should_send_formula, passed_filters, filter_reason)
        - logit: Raw score from dual formula
        - probability: Probability after sigmoid (0-1)
        - should_send_formula: Whether probability exceeds threshold
        - passed_filters: Whether signal passed all direction-specific filters
        - filter_reason: Reason for filter rejection (None if passed)
    """
    # Calculate VWAP distance
    vwap_dist_pct = abs((price - vwap) / price) * 100 if price > 0 and vwap > 0 else 0.0
    volume_ratio = volume / volume_median if volume_median > 0 else 1.0
    
    # Get dual-formula evaluation with appropriate threshold
    threshold = THRESHOLD_LONG if verdict == 'BUY' else THRESHOLD_SHORT
    logit, prob, should_send_formula = dual_formula_evaluate(
        rsi=rsi,
        ema_short=ema_short,
        ema_long=ema_long,
        price=price,
        volume=volume,
        volume_median=volume_median,
        atr=atr,
        verdict=verdict,
        threshold=threshold
    )
    
    # Apply direction-specific filters (with regime-adaptive VWAP threshold for LONG)
    if verdict == 'BUY':
        passed_filters, filter_reason = check_long_filters(rsi, vwap_dist_pct, volume_ratio, regime)
    else:  # SELL
        passed_filters, filter_reason = check_short_filters(rsi, vwap_dist_pct, volume_ratio)
    
    return logit, prob, should_send_formula, passed_filters, filter_reason


def should_send_signal(
    rsi: float,
    ema_short: float,
    ema_long: float,
    price: float,
    volume: float,
    volume_median: float,
    vwap: float,
    atr: float,
    verdict: str,
    regime: str = 'neutral'
) -> Tuple[bool, float, dict]:
    """
    Main decision function: should we send this signal in shadow mode?
    
    Args:
        rsi: RSI value
        ema_short: Short EMA
        ema_long: Long EMA
        price: Current price
        volume: Current volume
        volume_median: Median volume
        vwap: VWAP
        atr: ATR
        verdict: 'BUY' or 'SELL'
        regime: Market regime for adaptive VWAP filtering
    
    Returns:
        Tuple of (send_signal, probability, details)
        - send_signal: Whether to send the signal
        - probability: Probability score (0-1)
        - details: Dictionary with full evaluation details
    """
    logit, prob, should_send_formula, passed_filters, filter_reason = evaluate_signal_with_filters(
        rsi, ema_short, ema_long, price, volume, volume_median, vwap, atr, verdict, regime
    )
    
    # Signal is sent only if BOTH formula threshold AND filters pass
    send_signal = should_send_formula and passed_filters
    
    details = {
        'logit': logit,
        'probability': prob,
        'passed_threshold': should_send_formula,
        'passed_filters': passed_filters,
        'filter_reason': filter_reason,
        'threshold_used': THRESHOLD_LONG if verdict == 'BUY' else THRESHOLD_SHORT,
        'ttl_minutes': RISK_PARAMS['ttl_minutes'],
        'take_profit_pct': RISK_PARAMS['take_profit_pct'],
        'stop_loss_pct': RISK_PARAMS['stop_loss_pct']
    }
    
    return send_signal, prob, details


if __name__ == "__main__":
    # Test shadow mode evaluation
    print("="*80)
    print("SHADOW MODE SIGNAL EVALUATION TESTS")
    print("="*80)
    
    # Test 1: Strong LONG signal (should pass)
    print("\n📈 Test 1: Strong LONG Signal")
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
    print(f"  Probability: {prob:.4f} ({prob*100:.1f}%)")
    print(f"  Threshold: {details['threshold_used']:.2f}")
    print(f"  Passed threshold: {details['passed_threshold']}")
    print(f"  Passed filters: {details['passed_filters']}")
    print(f"  Filter reason: {details['filter_reason']}")
    print(f"  Decision: {'✅ SEND' if send else '❌ SKIP'}")
    
    # Test 2: SHORT signal with high RSI (should fail filter)
    print("\n📉 Test 2: SHORT Signal with High RSI (Filter Test)")
    send, prob, details = should_send_signal(
        rsi=65.0,
        ema_short=3000.0,
        ema_long=3010.0,
        price=3005.0,
        volume=30_000_000,
        volume_median=40_000_000,
        vwap=3003.0,
        atr=15.0,
        verdict='SELL'
    )
    print(f"  Probability: {prob:.4f} ({prob*100:.1f}%)")
    print(f"  Threshold: {details['threshold_used']:.2f}")
    print(f"  Passed threshold: {details['passed_threshold']}")
    print(f"  Passed filters: {details['passed_filters']}")
    print(f"  Filter reason: {details['filter_reason']}")
    print(f"  Decision: {'✅ SEND' if send else '❌ SKIP'}")
    
    # Test 3: LONG with high volume (should fail filter)
    print("\n📈 Test 3: LONG with High Volume (Filter Test)")
    send, prob, details = should_send_signal(
        rsi=50.0,
        ema_short=50100.0,
        ema_long=50000.0,
        price=50000.0,
        volume=60_000_000,
        volume_median=40_000_000,
        vwap=49950.0,
        atr=200.0,
        verdict='BUY'
    )
    print(f"  Probability: {prob:.4f} ({prob*100:.1f}%)")
    print(f"  Threshold: {details['threshold_used']:.2f}")
    print(f"  Passed threshold: {details['passed_threshold']}")
    print(f"  Passed filters: {details['passed_filters']}")
    print(f"  Filter reason: {details['filter_reason']}")
    print(f"  Decision: {'✅ SEND' if send else '❌ SKIP'}")
    
    print("\n" + "="*80)
    print(f"Shadow Mode: {'ENABLED' if SHADOW_MODE_ENABLED else 'DISABLED'}")
    print(f"Rollback: {'ENABLED' if ROLLBACK_ENABLED else 'DISABLED'}")
    print("="*80)
