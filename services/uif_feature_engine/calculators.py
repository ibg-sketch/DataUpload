"""
Local Technical Indicators Calculators

Implements 4 indicators from 5-minute OHLCV data:
- ADX14: Wilder's smoothing (14-period)
- PSAR State: +1 (price > PSAR) or -1 (price < PSAR)
- Momentum5: (close_t - close_t-5m) / close_t-5m
- VolAccel: d(volRatio)/dt, where volRatio = quoteVol / EWMA50 (capped at 3.0)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


def calculate_adx14(df: pd.DataFrame) -> Optional[float]:
    """
    Calculate ADX (Average Directional Index) using Wilder's smoothing.
    
    Args:
        df: DataFrame with columns ['high', 'low', 'close'] (min 30 rows recommended)
    
    Returns:
        ADX value (0-100) or None if insufficient data
    """
    if len(df) < 28:  # Need ~2x period for stable ADX
        return None
    
    try:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # True Range
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # Directional Movement
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Wilder's smoothing (period=14)
        period = 14
        alpha = 1.0 / period
        
        atr = pd.Series(tr).ewm(alpha=alpha, adjust=False).mean().values
        plus_di = 100 * pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean().values / atr
        minus_di = 100 * pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean().values / atr
        
        # ADX calculation
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = pd.Series(dx).ewm(alpha=alpha, adjust=False).mean().values[-1]
        
        return round(float(adx), 2)
    
    except Exception:
        return None


def calculate_psar_state(df: pd.DataFrame) -> Optional[int]:
    """
    Calculate Parabolic SAR state: +1 if price > PSAR, -1 if price < PSAR.
    
    Args:
        df: DataFrame with columns ['high', 'low', 'close'] (min 20 rows)
    
    Returns:
        +1 (bullish), -1 (bearish), or None if insufficient data
    """
    if len(df) < 20:
        return None
    
    try:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # PSAR parameters
        af = 0.02
        max_af = 0.2
        
        # Initialize
        is_bull = close[1] > close[0]
        sar = low[0] if is_bull else high[0]
        ep = high[0] if is_bull else low[0]
        current_af = af
        
        # Calculate PSAR
        for i in range(1, len(df)):
            sar = sar + current_af * (ep - sar)
            
            if is_bull:
                sar = min(sar, low[i-1])
                if i > 1:
                    sar = min(sar, low[i-2])
                
                if high[i] > ep:
                    ep = high[i]
                    current_af = min(current_af + af, max_af)
                
                if low[i] < sar:
                    is_bull = False
                    sar = ep
                    ep = low[i]
                    current_af = af
            else:
                sar = max(sar, high[i-1])
                if i > 1:
                    sar = max(sar, high[i-2])
                
                if low[i] < ep:
                    ep = low[i]
                    current_af = min(current_af + af, max_af)
                
                if high[i] > sar:
                    is_bull = True
                    sar = ep
                    ep = high[i]
                    current_af = af
        
        # Final state
        latest_close = close[-1]
        return +1 if latest_close > sar else -1
    
    except Exception:
        return None


def calculate_momentum5(df: pd.DataFrame) -> Optional[float]:
    """
    Calculate 5-minute momentum: (close_t - close_t-5m) / close_t-5m.
    
    Args:
        df: DataFrame with column ['close'] (min 2 rows)
    
    Returns:
        Momentum as decimal (e.g., 0.0012 = +0.12%) or None
    """
    if len(df) < 2:
        return None
    
    try:
        close_now = df['close'].iloc[-1]
        close_5m_ago = df['close'].iloc[-2]  # 1 candle ago = 5 minutes
        
        momentum = (close_now - close_5m_ago) / close_5m_ago
        return round(float(momentum), 6)
    
    except Exception:
        return None


def calculate_vol_accel(df: pd.DataFrame) -> Optional[float]:
    """
    Calculate volume acceleration: d(volRatio)/dt.
    volRatio = quoteVolume / EWMA50(quoteVolume), capped at 3.0
    
    Args:
        df: DataFrame with column ['quoteVolume'] (min 52 rows for stable EWMA50)
    
    Returns:
        Volume acceleration (rate of change) or None
    """
    if len(df) < 52:
        return None
    
    try:
        quote_vol = df['quoteVolume'].values
        
        # EWMA50 of quote volume
        ewma50 = pd.Series(quote_vol).ewm(span=50, adjust=False).mean().values
        
        # Volume ratio (capped at 3.0)
        vol_ratio = np.minimum(quote_vol / (ewma50 + 1e-10), 3.0)
        
        # Acceleration = d(volRatio)/dt (simple diff)
        if len(vol_ratio) < 2:
            return None
        
        accel = vol_ratio[-1] - vol_ratio[-2]
        return round(float(accel), 4)
    
    except Exception:
        return None


def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """
    Calculate all 4 UIF indicators from OHLCV dataframe.
    
    Args:
        df: DataFrame with columns ['high', 'low', 'close', 'quoteVolume']
    
    Returns:
        Dict with keys: adx14, psar_state, momentum5, vol_accel
    """
    return {
        'adx14': calculate_adx14(df),
        'psar_state': calculate_psar_state(df),
        'momentum5': calculate_momentum5(df),
        'vol_accel': calculate_vol_accel(df)
    }
