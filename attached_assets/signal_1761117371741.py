"""
signal.py — minimal decision module with separate LONG/SHORT formulas,
direction-specific filters, and TTL-based risk policy for short-term crypto signals.

Inputs (per bar):
- rsi: float                        # RSI value (0..100)
- ema_diff_pct: float               # (EMA_fast - EMA_slow) / price, in decimal (e.g., 0.002 = 0.2%)
- volume_ratio: float               # current volume / median volume over lookback (unitless)
- atr: float                        # ATR as a percent of price, in decimal (e.g., 0.004 = 0.4%)
- vwap_dist: float                  # |price - vwap| / vwap, in decimal (e.g., 0.003 = 0.3%)

Returns:
- dictionary with side ("LONG"/"SHORT"/None), raw signals, filters, thresholds, TTL/TP/SL

Formulas (from your Replit results):
LONG:
  Signal_Long = -0.0990*RSI + 0.4536*EMA_diff_pct - 0.0426*volume_ratio - 0.1305*ATR - 0.7094
  Trade LONG if Signal_Long > 0.30 and filters pass.

SHORT:
  Signal_Short = -0.7267*RSI + 0.4243*EMA_diff_pct - 0.2561*volume_ratio - 0.1954*ATR - 1.5340
  Trade SHORT if Signal_Short > 0.50 and filters pass.

Filters:
- LONG:  40 <= RSI <= 70,  vwap_dist <= 0.010 (1.0%),  0.5 <= volume_ratio <= 1.2
- SHORT: RSI  < 50,       vwap_dist <= 0.003 (0.3%),  volume_ratio <= 1.0
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


# === Tunable params ===
THRESH_LONG  = 0.30
THRESH_SHORT = 0.50

TTL_MINUTES = 15
TP_PCT = 0.004   # 0.40%
SL_PCT = 0.003   # 0.30%


def signal_long(rsi: float, ema_diff_pct: float, volume_ratio: float, atr: float) -> float:
    """Compute raw LONG signal value."""
    return (
        -0.0990 * rsi
        + 0.4536 * ema_diff_pct
        - 0.0426 * volume_ratio
        - 0.1305 * atr
        - 0.7094
    )


def signal_short(rsi: float, ema_diff_pct: float, volume_ratio: float, atr: float) -> float:
    """Compute raw SHORT signal value."""
    return (
        -0.7267 * rsi
        + 0.4243 * ema_diff_pct
        - 0.2561 * volume_ratio
        - 0.1954 * atr
        - 1.5340
    )


def long_filters_ok(rsi: float, vwap_dist: float, volume_ratio: float, atr: float) -> bool:
    """Direction-specific filters for LONG entries."""
    if not (40.0 <= rsi <= 70.0):
        return False
    if vwap_dist > 0.010:  # <= 1.0%
        return False
    if not (0.5 <= volume_ratio <= 1.2):
        return False
    # Optional: reject extreme ATR (outside 20th..80th percentile) if you track percentiles.
    # Here we keep it simple and accept all ATR to avoid extra state.
    return True


def short_filters_ok(rsi: float, vwap_dist: float, volume_ratio: float, atr: float) -> bool:
    """Direction-specific filters for SHORT entries."""
    if not (rsi < 50.0):
        return False
    if vwap_dist > 0.003:  # <= 0.3%
        return False
    if not (volume_ratio <= 1.0):
        return False
    return True


def decide(
    rsi: float,
    ema_diff_pct: float,
    volume_ratio: float,
    atr: float,
    vwap_dist: float,
    thresh_long: float = THRESH_LONG,
    thresh_short: float = THRESH_SHORT,
    delta_margin: float = 0.10,
) -> Dict[str, Any]:
    """
    Compute both signals, apply filters and thresholds, and pick a single side.
    If both qualify, choose the one with larger normalized margin:
        (signal - threshold) / max(|threshold|, 1e-9)

    If neither qualifies, return side=None.
    """
    s_long  = signal_long(rsi, ema_diff_pct, volume_ratio, atr)
    s_short = signal_short(rsi, ema_diff_pct, volume_ratio, atr)

    long_ok  = (s_long  > thresh_long)  and long_filters_ok(rsi, vwap_dist, volume_ratio, atr)
    short_ok = (s_short > thresh_short) and short_filters_ok(rsi, vwap_dist, volume_ratio, atr)

    chosen_side: Optional[str] = None
    reason = "NO_TRADE"
    margin_long  = (s_long  - thresh_long)  / max(abs(thresh_long), 1e-9)
    margin_short = (s_short - thresh_short) / max(abs(thresh_short), 1e-9)

    if long_ok and not short_ok:
        chosen_side, reason = "LONG", "LONG_ONLY_PASSED"
    elif short_ok and not long_ok:
        chosen_side, reason = "SHORT", "SHORT_ONLY_PASSED"
    elif long_ok and short_ok:
        # pick by higher margin; if close, skip
        if margin_long > margin_short + delta_margin:
            chosen_side, reason = "LONG", "BOTH_PASSED_LONG_STRONGER"
        elif margin_short > margin_long + delta_margin:
            chosen_side, reason = "SHORT", "BOTH_PASSED_SHORT_STRONGER"
        else:
            chosen_side, reason = None, "BOTH_PASSED_TOO_CLOSE_SKIP"

    return {
        "side": chosen_side,
        "reason": reason,
        "signal_long": s_long,
        "signal_short": s_short,
        "filters": {
            "long_ok": long_ok,
            "short_ok": short_ok,
            "vwap_dist": vwap_dist,
        },
        "thresholds": {"long": thresh_long, "short": thresh_short, "delta_margin": delta_margin},
        "risk": {"ttl_minutes": TTL_MINUTES, "tp_pct": TP_PCT, "sl_pct": SL_PCT},
    }


def vwap_distance(price: float, vwap: float) -> float:
    """Helper to compute |price - vwap| / vwap safely."""
    if vwap == 0:
        return 0.0
    return abs(price - vwap) / vwap


if __name__ == "__main__":
    # Example usage with dummy values:
    rsi = 55.0
    ema_diff_pct = 0.0025     # +0.25%
    volume_ratio = 0.9        # 90% of median
    atr = 0.0035              # 0.35%
    price = 100.0
    vwap = 99.8
    vdist = vwap_distance(price, vwap)

    decision = decide(
        rsi=rsi,
        ema_diff_pct=ema_diff_pct,
        volume_ratio=volume_ratio,
        atr=atr,
        vwap_dist=vdist,
    )
    print(decision)
