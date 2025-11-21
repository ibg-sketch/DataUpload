#!/usr/bin/env python3
"""
Enhanced Formula Integration Module
Loads trained 12-factor model and provides predictions for price targets
"""

import pickle
import json
import numpy as np
from pathlib import Path

# Global cache for loaded model
_MODEL_CACHE = None

def load_enhanced_model():
    """Load trained enhanced formula model"""
    global _MODEL_CACHE
    
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    
    model_path = Path('enhanced_formula_model.pkl')
    
    if not model_path.exists():
        print("[ENHANCED] Model not found. Using fallback formula.")
        return None
    
    try:
        with open(model_path, 'rb') as f:
            _MODEL_CACHE = pickle.load(f)
        
        print(f"[ENHANCED] ✅ Loaded model v{_MODEL_CACHE['version']}")
        print(f"[ENHANCED] R² score: {_MODEL_CACHE['r2_score']:.3f}")
        print(f"[ENHANCED] Features: {len(_MODEL_CACHE['feature_names'])}")
        
        return _MODEL_CACHE
    except Exception as e:
        print(f"[ENHANCED] ⚠️  Failed to load model: {e}")
        return None

def predict_price_movement(indicator_data):
    """
    Predict expected price movement using enhanced 12-factor model
    
    Args:
        indicator_data (dict): Dictionary with indicator values:
            {
                'rsi': float,
                'ema_short': float,
                'ema_long': float,
                'adx': float,
                'funding_rate': float,
                'market_strength': float,
                # ... derived factors calculated automatically
            }
    
    Returns:
        float: Predicted price movement percentage
        None: If model not available or missing data
    """
    model_data = load_enhanced_model()
    
    if model_data is None:
        return None
    
    try:
        # Extract model components
        model = model_data['model']
        scaler = model_data['scaler']
        feature_names = model_data['feature_names']
        
        # Calculate derived factors
        derived = calculate_derived_factors_from_indicators(indicator_data)
        
        # Build feature vector
        features = []
        for feat_name in feature_names:
            if feat_name in derived:
                features.append(derived[feat_name])
            else:
                print(f"[ENHANCED] ⚠️  Missing feature: {feat_name}")
                return None
        
        # Reshape for prediction
        X = np.array(features).reshape(1, -1)
        
        # Scale features
        X_scaled = scaler.transform(X)
        
        # Predict
        prediction = model.predict(X_scaled)[0]
        
        return prediction
        
    except Exception as e:
        print(f"[ENHANCED] ⚠️  Prediction failed: {e}")
        return None

def calculate_derived_factors_from_indicators(data):
    """Calculate derived factors from base indicators"""
    
    derived = {
        # Base indicators (passed directly)
        'rsi': data.get('rsi', 50),
        'ema_short': data.get('ema_short', 0),
        'ema_long': data.get('ema_long', 0),
        'adx': data.get('adx', 0),
        'funding_rate': data.get('funding_rate', 0),
        'market_strength': data.get('market_strength', 1.0),
    }
    
    # Derived factor: EMA cross magnitude
    if derived['ema_long'] != 0:
        derived['ema_cross'] = (derived['ema_short'] - derived['ema_long']) / derived['ema_long'] * 100
    else:
        derived['ema_cross'] = 0
    
    # Derived factor: Price momentum (from recent data if available)
    derived['price_momentum'] = data.get('price_momentum', 0)
    
    # Add more derived factors as needed
    # These will be calculated from analysis_log data in production
    
    return derived

def calculate_enhanced_targets(
    current_price,
    confidence,
    indicator_data,
    verdict,
    fallback_targets
):
    """
    Calculate price targets using enhanced 12-factor model
    
    Args:
        current_price (float): Current asset price
        confidence (float): Signal confidence (0-1)
        indicator_data (dict): All technical indicators
        verdict (str): 'BUY' or 'SELL'
        fallback_targets (tuple): (min_pct, max_pct) from old formula as fallback
    
    Returns:
        tuple: (target_min, target_max, predicted_movement_pct)
    """
    
    # Try enhanced model prediction
    predicted_movement = predict_price_movement(indicator_data)
    
    if predicted_movement is None:
        # Fallback to old formula
        print(f"[ENHANCED] Using fallback formula")
        min_pct, max_pct = fallback_targets
        return (
            current_price * (1 + min_pct/100) if verdict == 'BUY' else current_price * (1 - max_pct/100),
            current_price * (1 + max_pct/100) if verdict == 'BUY' else current_price * (1 - min_pct/100),
            (min_pct + max_pct) / 2
        )
    
    # Use enhanced model prediction
    # Adjust based on confidence
    base_movement = abs(predicted_movement)
    
    # Conservative minimum (80% of prediction)
    min_movement = base_movement * 0.8
    
    # Optimistic maximum (120% of prediction)
    max_movement = base_movement * 1.2
    
    # Apply confidence scaling
    min_movement *= confidence
    max_movement *= confidence
    
    # Calculate price targets
    if verdict == 'BUY':
        target_min = current_price * (1 + min_movement/100)
        target_max = current_price * (1 + max_movement/100)
    else:  # SELL
        target_min = current_price * (1 - max_movement/100)
        target_max = current_price * (1 - min_movement/100)
    
    print(f"[ENHANCED] Predicted movement: {base_movement:.2f}% (model)")
    print(f"[ENHANCED] Targets: {min_movement:.2f}% - {max_movement:.2f}%")
    
    return (target_min, target_max, base_movement)

def get_model_status():
    """Get current status of enhanced model"""
    model_data = load_enhanced_model()
    
    if model_data is None:
        return {
            'available': False,
            'message': 'Enhanced model not trained yet'
        }
    
    return {
        'available': True,
        'version': model_data['version'],
        'r2_score': model_data['r2_score'],
        'features': len(model_data['feature_names']),
        'trained_at': model_data['trained_at']
    }

# Example usage
if __name__ == '__main__':
    status = get_model_status()
    print("Enhanced Formula Status:")
    print(json.dumps(status, indent=2))
