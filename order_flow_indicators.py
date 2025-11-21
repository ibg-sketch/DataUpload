"""
Order Flow Indicators Module
=============================

Provides real-time order flow analysis for enhanced signal generation:
1. Bid-Ask Aggression Ratio - measures buying vs selling pressure
2. Psychological Level Proximity - detects stop-loss/take-profit clusters

These indicators help identify:
- Aggressive buying/selling (Order Flow Imbalance)
- Stop-hunt zones (round numbers, Fibonacci, recent extremes)
- Market microstructure signals

Author: Smart Money Signal Bot
Date: November 15, 2025
"""

import json
import time
from pathlib import Path
from typing import Dict, Tuple, Optional


def calculate_bid_ask_aggression(symbol: str, lookback_minutes: int = 5) -> Dict[str, float]:
    """
    Calculate Bid-Ask Aggression Ratio from CVD data.
    
    This measures the buying vs selling pressure over the last N minutes.
    A high ratio (>2.0) indicates aggressive buying, while low ratio (<0.5) 
    indicates aggressive selling.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        lookback_minutes: Time window for analysis (default: 5 minutes)
    
    Returns:
        Dict with:
        - 'ba_ratio': Bid-Ask ratio (buy_volume / sell_volume)
        - 'buy_pressure': Percentage of buy volume
        - 'sell_pressure': Percentage of sell volume
        - 'signal': 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        - 'strength': Signal strength 0-100
    """
    try:
        # Read CVD data from CVD Service
        cvd_file = Path('cvd_data.json')
        if not cvd_file.exists():
            return _empty_ba_result()
        
        with open(cvd_file, 'r') as f:
            data = json.load(f)
        
        # Check if data is fresh (< 5 minutes old)
        last_update = data.get('last_update', 0)
        data_age = time.time() - last_update
        if data_age > 300:  # 5 minutes
            return _empty_ba_result()
        
        # Get CVD history for this symbol
        cvd_history_raw = data.get('cvd_history', {}).get(symbol, [])
        
        if len(cvd_history_raw) < 2:
            return _empty_ba_result()
        
        # Calculate CVD change over lookback period
        # CVD = Cumulative(Buy Volume - Sell Volume)
        # Positive CVD change = more buying, Negative = more selling
        
        # Get recent CVD samples (last lookback_minutes worth)
        # Filter by timestamp (last N minutes)
        current_time = time.time()
        lookback_seconds = lookback_minutes * 60
        
        # Extract CVD values from history (format: [{'timestamp': ts, 'cvd': value}, ...])
        recent_cvd = [
            entry['cvd'] 
            for entry in cvd_history_raw 
            if (current_time - entry.get('timestamp', 0)) <= lookback_seconds
        ]
        
        if len(recent_cvd) < 2:
            return _empty_ba_result()
        
        # Calculate CVD delta (recent change)
        cvd_start = recent_cvd[0]
        cvd_end = recent_cvd[-1]
        cvd_delta = cvd_end - cvd_start
        
        # Estimate buy/sell volumes from CVD change
        # If CVD increased: more buying
        # If CVD decreased: more selling
        
        # We approximate volumes by looking at absolute CVD change
        # and directional bias
        abs_cvd_delta = abs(cvd_delta)
        
        if cvd_delta > 0:
            # Net buying
            buy_volume_estimate = abs_cvd_delta
            sell_volume_estimate = abs_cvd_delta * 0.3  # Assume some selling offset
        else:
            # Net selling
            sell_volume_estimate = abs_cvd_delta
            buy_volume_estimate = abs_cvd_delta * 0.3  # Assume some buying offset
        
        # Calculate BA ratio
        if sell_volume_estimate > 0:
            ba_ratio = buy_volume_estimate / sell_volume_estimate
        else:
            ba_ratio = 5.0 if buy_volume_estimate > 0 else 1.0
        
        # Calculate pressure percentages
        total_volume = buy_volume_estimate + sell_volume_estimate
        buy_pressure = (buy_volume_estimate / total_volume * 100) if total_volume > 0 else 50.0
        sell_pressure = (sell_volume_estimate / total_volume * 100) if total_volume > 0 else 50.0
        
        # Determine signal
        if ba_ratio > 2.0:
            signal = 'BULLISH'
            strength = min(100, int((ba_ratio - 2.0) * 20))  # Scale strength
        elif ba_ratio < 0.5:
            signal = 'BEARISH'
            strength = min(100, int((0.5 - ba_ratio) * 40))
        else:
            signal = 'NEUTRAL'
            strength = 0
        
        return {
            'ba_ratio': round(ba_ratio, 3),
            'buy_pressure': round(buy_pressure, 2),
            'sell_pressure': round(sell_pressure, 2),
            'signal': signal,
            'strength': strength,
            'cvd_delta': cvd_delta,
            'data_age_sec': int(data_age)
        }
    
    except Exception as e:
        print(f"[ORDER_FLOW] BA Aggression calculation error for {symbol}: {e}")
        return _empty_ba_result()


def detect_psychological_levels(
    symbol: str,
    current_price: float,
    recent_high: Optional[float] = None,
    recent_low: Optional[float] = None,
    proximity_threshold: float = 0.003  # 0.3%
) -> Dict[str, any]:
    """
    Detect proximity to psychological price levels (stop-loss/take-profit clusters).
    
    Identifies danger zones where stop-hunts are likely:
    - Round numbers ($96,000, $95,500, etc.)
    - Fibonacci retracement levels
    - Recent highs/lows (where traders place stops)
    
    Args:
        symbol: Trading pair
        current_price: Current market price
        recent_high: Recent high price (optional, for Fibonacci)
        recent_low: Recent low price (optional, for Fibonacci)
        proximity_threshold: Distance threshold (default 0.3% = 0.003)
    
    Returns:
        Dict with:
        - 'in_danger_zone': True if close to a cluster
        - 'nearest_level': Price of nearest psychological level
        - 'distance_pct': Distance to nearest level (%)
        - 'level_type': 'ROUND_1000' | 'ROUND_500' | 'ROUND_100' | 'FIBONACCI' | 'EXTREME'
        - 'risk_score': 0-100 (higher = more dangerous)
    """
    try:
        danger_zones = []
        
        # 1. ROUND NUMBERS
        # Round to nearest $1000 (e.g., $96,000)
        round_1k = round(current_price / 1000) * 1000
        danger_zones.append({
            'price': round_1k,
            'type': 'ROUND_1000',
            'importance': 100
        })
        
        # Round to nearest $500 (e.g., $96,500)
        round_500 = round(current_price / 500) * 500
        if round_500 != round_1k:  # Avoid duplicates
            danger_zones.append({
                'price': round_500,
                'type': 'ROUND_500',
                'importance': 70
            })
        
        # Round to nearest $100 (for altcoins)
        if current_price < 1000:  # Only for smaller prices
            round_100 = round(current_price / 100) * 100
            if round_100 not in [round_1k, round_500]:
                danger_zones.append({
                    'price': round_100,
                    'type': 'ROUND_100',
                    'importance': 50
                })
        
        # 2. FIBONACCI LEVELS (if highs/lows provided)
        if recent_high and recent_low and recent_high > recent_low:
            range_size = recent_high - recent_low
            fib_levels = {
                'FIB_0.236': recent_low + range_size * 0.236,
                'FIB_0.382': recent_low + range_size * 0.382,
                'FIB_0.500': recent_low + range_size * 0.500,
                'FIB_0.618': recent_low + range_size * 0.618,  # Golden ratio - most important
                'FIB_0.786': recent_low + range_size * 0.786
            }
            
            for fib_name, fib_price in fib_levels.items():
                # 0.618 is most important Fibonacci level
                importance = 90 if '0.618' in fib_name else 60
                danger_zones.append({
                    'price': fib_price,
                    'type': fib_name,
                    'importance': importance
                })
        
        # 3. RECENT EXTREMES (stop-loss magnets)
        if recent_high:
            danger_zones.append({
                'price': recent_high,
                'type': 'RECENT_HIGH',
                'importance': 80
            })
        
        if recent_low:
            danger_zones.append({
                'price': recent_low,
                'type': 'RECENT_LOW',
                'importance': 80
            })
        
        # Find nearest danger zone
        if not danger_zones:
            return _empty_level_result()
        
        # Calculate distances to all zones
        for zone in danger_zones:
            zone['distance_pct'] = abs(current_price - zone['price']) / current_price
        
        # Sort by proximity
        danger_zones.sort(key=lambda x: x['distance_pct'])
        
        # Get nearest zone
        nearest = danger_zones[0]
        distance_pct = nearest['distance_pct']
        
        # Determine if in danger zone
        in_danger_zone = distance_pct < proximity_threshold
        
        # Calculate risk score
        if in_danger_zone:
            # Closer = more dangerous
            # More important level = more dangerous
            proximity_risk = (1 - distance_pct / proximity_threshold) * 50  # 0-50 points
            importance_risk = nearest['importance'] * 0.5  # 0-50 points
            risk_score = int(proximity_risk + importance_risk)
        else:
            risk_score = 0
        
        return {
            'in_danger_zone': in_danger_zone,
            'nearest_level': round(nearest['price'], 2),
            'distance_pct': round(distance_pct * 100, 3),
            'level_type': nearest['type'],
            'risk_score': min(100, risk_score),
            'all_nearby_levels': [
                {
                    'price': round(z['price'], 2),
                    'type': z['type'],
                    'distance_pct': round(z['distance_pct'] * 100, 3)
                }
                for z in danger_zones[:5]  # Top 5 nearest
            ]
        }
    
    except Exception as e:
        print(f"[ORDER_FLOW] Psychological level detection error for {symbol}: {e}")
        return _empty_level_result()


def _empty_ba_result() -> Dict[str, float]:
    """Return empty Bid-Ask result when data unavailable"""
    return {
        'ba_ratio': 1.0,
        'buy_pressure': 50.0,
        'sell_pressure': 50.0,
        'signal': 'NEUTRAL',
        'strength': 0,
        'cvd_delta': 0.0,
        'data_age_sec': 999
    }


def _empty_level_result() -> Dict[str, any]:
    """Return empty psychological level result when data unavailable"""
    return {
        'in_danger_zone': False,
        'nearest_level': 0.0,
        'distance_pct': 100.0,
        'level_type': 'NONE',
        'risk_score': 0,
        'all_nearby_levels': []
    }


# Module test function
if __name__ == '__main__':
    print("=" * 70)
    print("ORDER FLOW INDICATORS - MODULE TEST")
    print("=" * 70)
    
    # Test 1: Bid-Ask Aggression
    print("\n[TEST 1] Bid-Ask Aggression Ratio")
    print("-" * 70)
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    for symbol in test_symbols:
        result = calculate_bid_ask_aggression(symbol, lookback_minutes=5)
        print(f"\n{symbol}:")
        print(f"  BA Ratio: {result['ba_ratio']}")
        print(f"  Buy Pressure: {result['buy_pressure']}%")
        print(f"  Sell Pressure: {result['sell_pressure']}%")
        print(f"  Signal: {result['signal']} (strength: {result['strength']})")
        print(f"  CVD Delta: {result['cvd_delta']:,.0f}")
        print(f"  Data Age: {result['data_age_sec']}s")
    
    # Test 2: Psychological Levels
    print("\n\n[TEST 2] Psychological Level Detection")
    print("-" * 70)
    test_prices = [
        ('BTCUSDT', 96050, 97500, 94800),
        ('ETHUSDT', 3213, 3400, 3100),
        ('SOLUSDT', 143.26, 150, 135)
    ]
    
    for symbol, price, high, low in test_prices:
        result = detect_psychological_levels(
            symbol=symbol,
            current_price=price,
            recent_high=high,
            recent_low=low,
            proximity_threshold=0.003
        )
        print(f"\n{symbol} @ ${price}:")
        print(f"  Danger Zone: {'⚠️ YES' if result['in_danger_zone'] else '✅ CLEAR'}")
        print(f"  Nearest Level: ${result['nearest_level']} ({result['level_type']})")
        print(f"  Distance: {result['distance_pct']}%")
        print(f"  Risk Score: {result['risk_score']}/100")
        if result['all_nearby_levels']:
            print(f"  Nearby Levels:")
            for lvl in result['all_nearby_levels'][:3]:
                print(f"    - ${lvl['price']} ({lvl['type']}) - {lvl['distance_pct']}% away")
    
    print("\n" + "=" * 70)
    print("MODULE TEST COMPLETE")
    print("=" * 70)
