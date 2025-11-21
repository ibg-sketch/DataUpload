"""
Dual-Formula Signal Scoring System
Separate predictive formulas for LONG and SHORT signals based on machine learning analysis
of 391 historical signals. Achieves 39.6% win rate vs 25.1% baseline (+14.5% improvement).

Usage:
    from dual_formula import evaluate_signal
    
    score, probability, verdict = evaluate_signal(
        rsi=55.0,
        ema_short=100.5,
        ema_long=100.0,
        price=100.0,
        volume=35_000_000,
        volume_median=40_000_000,
        atr=0.35,
        verdict='BUY'  # or 'SELL'
    )
    
    if probability > 0.30:
        send_signal(verdict, probability)

Performance (backtested on 391 signals):
- LONG:  33.6% → 40.2% WR (+6.6%)
- SHORT: 20.0% → 37.5% WR (+17.5%)
- Overall: 25.1% → 39.6% WR (+14.5%)
- Signal reduction: 66% (quality over quantity)
"""

import numpy as np
from typing import Tuple

# Optimal thresholds (probability after sigmoid)
THRESHOLD_LONG = 0.30   # 40.2% WR with 102 signals
THRESHOLD_SHORT = 0.30  # 37.5% WR with 32 signals


def signal_long_logit(rsi: float, ema_diff_pct: float, volume_ratio: float, atr_pct: float) -> float:
    """
    Compute raw LONG logit score (before sigmoid).
    
    Args:
        rsi: RSI value (0-100)
        ema_diff_pct: (EMA_short - EMA_long) / price * 100 (as percentage)
        volume_ratio: current_volume / median_volume
        atr_pct: ATR / price * 100 (as percentage)
    
    Returns:
        Raw logit score (can be negative)
    """
    return (
        -0.001468 * rsi
        +0.794991 * ema_diff_pct
        -0.211934 * volume_ratio
        +0.222079 * atr_pct
        -0.224266
    )


def signal_short_logit(rsi: float, ema_diff_pct: float, volume_ratio: float, atr_pct: float) -> float:
    """
    Compute raw SHORT logit score (before sigmoid).
    
    Args:
        rsi: RSI value (0-100)
        ema_diff_pct: (EMA_short - EMA_long) / price * 100 (as percentage)
        volume_ratio: current_volume / median_volume
        atr_pct: ATR / price * 100 (as percentage)
    
    Returns:
        Raw logit score (can be negative)
    """
    return (
        -0.065756 * rsi
        +1.106601 * ema_diff_pct
        -0.136820 * volume_ratio
        -0.951073 * atr_pct
        +2.836546
    )


def sigmoid(x: float) -> float:
    """
    Convert logit score to probability (0-1 range).
    
    Args:
        x: Logit score
    
    Returns:
        Probability between 0 and 1
    """
    return 1 / (1 + np.exp(-x))


def evaluate_signal(
    rsi: float,
    ema_short: float,
    ema_long: float,
    price: float,
    volume: float,
    volume_median: float,
    atr: float,
    verdict: str,  # 'BUY' or 'SELL'
    threshold: float = None
) -> Tuple[float, float, bool]:
    """
    Evaluate signal quality using dual-formula approach.
    
    Args:
        rsi: RSI value (0-100)
        ema_short: Short-term EMA value
        ema_long: Long-term EMA value
        price: Current price
        volume: Current volume (USDT)
        volume_median: Median volume over lookback period
        atr: Average True Range
        verdict: Signal direction ('BUY' for LONG, 'SELL' for SHORT)
        threshold: Optional custom threshold (default: 0.30 for both)
    
    Returns:
        Tuple of (logit_score, probability, should_send)
        - logit_score: Raw score before sigmoid
        - probability: Score after sigmoid (0-1 range)
        - should_send: True if probability > threshold
    """
    # Calculate features
    ema_diff_pct = ((ema_short - ema_long) / price) * 100 if price > 0 else 0.0
    volume_ratio = volume / volume_median if volume_median > 0 else 1.0
    atr_pct = (atr / price) * 100 if price > 0 else 0.0
    
    # Select formula based on direction
    if verdict == 'BUY':
        logit = signal_long_logit(rsi, ema_diff_pct, volume_ratio, atr_pct)
        thresh = threshold if threshold is not None else THRESHOLD_LONG
    else:  # SELL
        logit = signal_short_logit(rsi, ema_diff_pct, volume_ratio, atr_pct)
        thresh = threshold if threshold is not None else THRESHOLD_SHORT
    
    # Convert to probability
    probability = sigmoid(logit)
    
    # Determine if signal should be sent
    should_send = probability > thresh
    
    return logit, probability, should_send


def get_formula_confidence(
    rsi: float,
    ema_short: float,
    ema_long: float,
    price: float,
    volume: float,
    volume_median: float,
    atr: float,
    verdict: str
) -> float:
    """
    Get formula-based confidence score (0-100 scale) for backward compatibility.
    
    This is a convenience function that returns the probability scaled to 0-100
    for easier integration with existing confidence systems.
    
    Returns:
        Confidence score (0-100)
    """
    _, probability, _ = evaluate_signal(
        rsi, ema_short, ema_long, price, volume, volume_median, atr, verdict
    )
    return probability * 100


if __name__ == "__main__":
    # Example usage
    print("="*80)
    print("DUAL-FORMULA SIGNAL EVALUATION EXAMPLES")
    print("="*80)
    
    # Example 1: Strong LONG signal
    print("\n📈 Example 1: Potential LONG Signal")
    logit, prob, send = evaluate_signal(
        rsi=45.0,
        ema_short=100.5,
        ema_long=100.0,
        price=100.0,
        volume=35_000_000,
        volume_median=40_000_000,
        atr=0.35,
        verdict='BUY'
    )
    print(f"  Logit: {logit:.4f}")
    print(f"  Probability: {prob:.4f} ({prob*100:.1f}%)")
    print(f"  Decision: {'✅ SEND SIGNAL' if send else '❌ SKIP'}")
    
    # Example 2: Potential SHORT signal
    print("\n📉 Example 2: Potential SHORT Signal")
    logit, prob, send = evaluate_signal(
        rsi=65.0,
        ema_short=100.0,
        ema_long=100.5,
        price=100.0,
        volume=30_000_000,
        volume_median=40_000_000,
        atr=0.40,
        verdict='SELL'
    )
    print(f"  Logit: {logit:.4f}")
    print(f"  Probability: {prob:.4f} ({prob*100:.1f}%)")
    print(f"  Decision: {'✅ SEND SIGNAL' if send else '❌ SKIP'}")
    
    print("\n" + "="*80)
