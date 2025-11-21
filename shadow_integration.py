"""
Shadow Mode Integration for Smart Signal Bot
Integrates dual-formula evaluation alongside existing signal system for A/B comparison.

This module provides a clean wrapper around the existing decide_signal function
to log dual-formula predictions without disrupting current operations.
"""

import time
from typing import Dict, Optional
from shadow_mode import should_send_signal, SHADOW_MODE_ENABLED, ROLLBACK_ENABLED
from shadow_logger import get_shadow_logger

class ShadowIntegration:
    """Manages shadow mode integration with the existing signal system."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize shadow integration.
        
        Args:
            enabled: Whether shadow mode is active (default: True)
        """
        self.enabled = enabled and SHADOW_MODE_ENABLED
        self.logger = get_shadow_logger() if self.enabled else None
    
    def evaluate_and_log(
        self,
        signal_result: Dict,
        start_time: float = None
    ) -> Dict:
        """
        Evaluate signal using dual-formula and log for comparison.
        
        Args:
            signal_result: Output from decide_signal()
            start_time: When processing started (for latency calculation)
        
        Returns:
            Enhanced signal_result with shadow mode data added
        """
        if not self.enabled:
            return signal_result
        
        # Extract required data from signal result
        symbol = signal_result.get('symbol')
        verdict = signal_result.get('verdict')
        
        # Only evaluate if verdict is BUY or SELL (skip NO_TRADE)
        if verdict not in ['BUY', 'SELL']:
            return signal_result
        
        # Extract indicator values
        rsi = signal_result.get('rsi')
        ema_short = signal_result.get('ema_short')
        ema_long = signal_result.get('ema_long')
        price = signal_result.get('last_close')
        vwap = signal_result.get('vwap_ref')
        atr = signal_result.get('atr')
        regime = signal_result.get('regime', 'neutral')  # Extract market regime for adaptive filtering
        
        volume_info = signal_result.get('volume', {})
        volume = volume_info.get('last', 0)
        volume_median = volume_info.get('median', 0)
        
        cvd = signal_result.get('cvd', 0)
        oi_change = signal_result.get('oi_change', 0)
        
        # Old system decision
        old_decision = verdict
        old_score = signal_result.get('confidence', 0)
        
        # Calculate latency
        latency_ms = None
        if start_time is not None:
            latency_ms = (time.time() - start_time) * 1000
        
        # Validate required data
        if None in [rsi, ema_short, ema_long, price, vwap, atr]:
            # Missing required indicators - skip shadow evaluation
            return signal_result
        
        if volume_median == 0:
            volume_median = 1  # Prevent division by zero
        
        try:
            # Evaluate with dual-formula system (with regime-adaptive VWAP filtering)
            send_signal, probability, details = should_send_signal(
                rsi=rsi,
                ema_short=ema_short,
                ema_long=ema_long,
                price=price,
                volume=volume,
                volume_median=volume_median,
                vwap=vwap,
                atr=atr,
                verdict=verdict,
                regime=regime  # Pass regime for adaptive VWAP threshold
            )
            
            # Calculate CVD 5m aggregate if available
            # For now, use instant CVD (can be enhanced later with analysis_log)
            cvd_5m = cvd
            
            # Log the evaluation
            self.logger.log_signal_evaluation(
                symbol=symbol,
                verdict=verdict,
                logit=details['logit'],
                prob=details['probability'],
                should_send=send_signal,
                rsi=rsi,
                ema_short=ema_short,
                ema_long=ema_long,
                price=price,
                vwap=vwap,
                volume=volume,
                volume_median=volume_median,
                atr=atr,
                cvd=cvd,
                cvd_5m=cvd_5m,
                oi_change=oi_change,
                old_decision=old_decision,
                old_score=old_score,
                passed_filters=details['passed_filters'],
                filter_reason=details['filter_reason'],
                latency_ms=latency_ms
            )
            
            # Add shadow mode data to result for potential inspection
            signal_result['shadow_mode'] = {
                'enabled': True,
                'probability': details['probability'],
                'would_send': send_signal,
                'passed_threshold': details['passed_threshold'],
                'passed_filters': details['passed_filters'],
                'filter_reason': details['filter_reason'],
                'threshold_used': details['threshold_used'],
                'regime': regime  # Include regime for transparency
            }
            
        except Exception as e:
            # Log error but don't disrupt main system
            print(f"Shadow mode error for {symbol}: {e}")
            signal_result['shadow_mode'] = {
                'enabled': True,
                'error': str(e)
            }
        
        return signal_result


# Global instance
_shadow_integration = None

def get_shadow_integration(enabled: bool = True) -> ShadowIntegration:
    """
    Get or create the global shadow integration instance.
    
    Args:
        enabled: Whether shadow mode is active
    
    Returns:
        ShadowIntegration instance
    """
    global _shadow_integration
    if _shadow_integration is None:
        _shadow_integration = ShadowIntegration(enabled)
    return _shadow_integration


def evaluate_with_shadow_mode(signal_result: Dict, start_time: float = None) -> Dict:
    """
    Convenience function to evaluate signal with shadow mode.
    
    Args:
        signal_result: Output from decide_signal()
        start_time: When processing started
    
    Returns:
        Enhanced signal_result
    """
    integration = get_shadow_integration()
    return integration.evaluate_and_log(signal_result, start_time)


if __name__ == "__main__":
    # Test shadow integration with mock signal result
    print("Testing shadow integration...")
    
    mock_result = {
        'symbol': 'BTCUSDT',
        'verdict': 'BUY',
        'confidence': 78.5,
        'score': 3.2,
        'last_close': 50000.0,
        'vwap_ref': 49900.0,
        'rsi': 55.0,
        'ema_short': 50100.0,
        'ema_long': 50000.0,
        'atr': 200.0,
        'volume': {'last': 40_000_000, 'median': 40_000_000},
        'cvd': 2_500_000,
        'oi_change': 15_000_000
    }
    
    start = time.time()
    enhanced = evaluate_with_shadow_mode(mock_result, start)
    
    if 'shadow_mode' in enhanced:
        print("\n✅ Shadow mode data added:")
        for key, value in enhanced['shadow_mode'].items():
            print(f"  {key}: {value}")
    else:
        print("\n❌ Shadow mode not added to result")
    
    print(f"\n📊 Check shadow_predictions.csv for logged data")
