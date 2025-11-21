"""
Calculators for derived metrics.
"""
import math
from typing import Optional


class FeedCalculators:
    """Stateless calculators for feed metrics"""
    
    @staticmethod
    def calculate_oi_pct(current_oi: float, previous_oi: Optional[float]) -> Optional[float]:
        """
        Calculate OI percentage change using log difference.
        oi_pct = 100 * (log(OI_t) - log(OI_{t-1}))
        """
        if previous_oi is None or previous_oi <= 0 or current_oi <= 0:
            return None
        
        try:
            return 100 * (math.log(current_oi) - math.log(previous_oi))
        except (ValueError, ZeroDivisionError):
            return None
    
    @staticmethod
    def calculate_liq_ratio(liq_short_usd: float, liq_long_usd: float) -> Optional[float]:
        """
        Calculate liquidation ratio.
        liq_ratio = (Short - Long) / (Short + Long)
        
        Returns:
            float between -1 and 1
            Positive = more shorts liquidated (bullish)
            Negative = more longs liquidated (bearish)
        """
        total = liq_short_usd + liq_long_usd
        if total <= 0:
            return None
        
        return (liq_short_usd - liq_long_usd) / total
    
    @staticmethod
    def calculate_obi_top(bids: list[list[float]], asks: list[list[float]], 
                         depth_levels: int = 3) -> Optional[float]:
        """
        Calculate Order Book Imbalance for top N levels.
        obi_top = total_bid_volume / (total_bid_volume + total_ask_volume)
        
        Args:
            bids: [[price, qty], ...]
            asks: [[price, qty], ...]
            depth_levels: Number of levels to consider
            
        Returns:
            float between 0 and 1
            >0.5 = more bids (buying pressure)
            <0.5 = more asks (selling pressure)
        """
        if not bids or not asks:
            return None
        
        try:
            total_bid_vol = sum(float(bid[1]) for bid in bids[:depth_levels])
            total_ask_vol = sum(float(ask[1]) for ask in asks[:depth_levels])
            
            total = total_bid_vol + total_ask_vol
            if total <= 0:
                return None
            
            return total_bid_vol / total
        except (IndexError, ValueError, TypeError):
            return None
    
    @staticmethod
    def smooth_ema(current_value: float, previous_ema: Optional[float], 
                   periods: int = 5) -> float:
        """
        Exponential Moving Average smoothing.
        EMA_t = value_t * k + EMA_{t-1} * (1-k), where k = 2/(periods+1)
        """
        if previous_ema is None:
            return current_value
        
        k = 2.0 / (periods + 1)
        return current_value * k + previous_ema * (1 - k)
    
    @staticmethod
    def calculate_basis(mark_price: float, index_price: float) -> float:
        """
        Calculate basis (premium/discount).
        basis = mark_price - index_price
        
        Positive = futures trading at premium
        Negative = futures trading at discount
        """
        return mark_price - index_price
