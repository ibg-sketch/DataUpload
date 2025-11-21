"""
BingX API Client
Handles authentication and trading operations
"""
import hmac
import hashlib
import time
import requests
from typing import Dict, Optional
from .config import TradingConfig

class BingXClient:
    def __init__(self):
        self.api_key = TradingConfig.API_KEY
        self.api_secret = TradingConfig.API_SECRET
        self.base_url = TradingConfig.API_URL
        self.session = requests.Session()
    
    def _generate_signature(self, params: str) -> str:
        if not self.api_secret:
            raise ValueError("API Secret not configured")
        return hmac.new(
            self.api_secret.encode('utf-8'),
            params.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _format_symbol_for_api(self, symbol: str) -> str:
        if '-' in symbol:
            return symbol
        return symbol.replace('USDT', '-USDT').replace('USDC', '-USDC')
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, signed: bool = True) -> Dict:
        from urllib.parse import urlencode
        
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
        
        if signed:
            timestamp = int(time.time() * 1000)
            params['timestamp'] = timestamp
            
            # Sort parameters alphabetically to create signature
            sorted_params = sorted(params.items())
            param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
            signature = self._generate_signature(param_str)
            
            # Add signature to sorted params list (maintains order)
            sorted_params.append(('signature', signature))
            
            # Build final query string from sorted params (BingX validates signature using received order)
            query_string = urlencode(sorted_params)
            
            
            # Construct full URL with query string
            full_url = f"{url}?{query_string}"
        else:
            full_url = url
            query_string = None
        
        headers = {
            'X-BX-APIKEY': self.api_key
        }
        
        # BingX API requires parameters in query string (not body) even for POST requests
        if method == 'GET':
            response = self.session.get(full_url if signed else url, 
                                       params=None if signed else params, 
                                       headers=headers, timeout=10)
        elif method == 'POST':
            # Use full URL with query string (params already in URL)
            response = self.session.post(full_url if signed else url, 
                                        params=None if signed else params, 
                                        headers=headers, timeout=10)
        elif method == 'DELETE':
            response = self.session.delete(full_url if signed else url, 
                                          params=None if signed else params, 
                                          headers=headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    def get_balance(self) -> Dict:
        return self._request('GET', '/openApi/swap/v2/user/balance')
    
    def get_current_price(self, symbol: str) -> float:
        formatted_symbol = self._format_symbol_for_api(symbol)
        params = {'symbol': formatted_symbol}
        result = self._request('GET', '/openApi/swap/v2/quote/price', params, signed=False)
        return float(result['data']['price'])
    
    def place_order(self, symbol: str, side: str, quantity: float, 
                   stop_loss: Optional[float] = None, 
                   take_profit: Optional[float] = None) -> Dict:
        formatted_symbol = self._format_symbol_for_api(symbol)
        position_side = 'LONG' if side == 'BUY' else 'SHORT'
        
        params = {
            'symbol': formatted_symbol,
            'side': side,
            'positionSide': position_side,
            'type': 'MARKET',
            'quantity': quantity
        }
        
        order_result = self._request('POST', '/openApi/swap/v2/trade/order', params)
        
        # CRITICAL FIX: Only set TP/SL if main order succeeded
        if order_result.get('code') != 0:
            # Main order failed - DO NOT attempt to set TP/SL
            print(f"❌ Main order failed with code {order_result.get('code')}: {order_result.get('msg')}")
            return order_result
        
        # Set TP/SL using separate TAKE_PROFIT_MARKET and STOP_MARKET orders
        if stop_loss or take_profit:
            print(f"📊 Setting TP/SL for {formatted_symbol} {position_side}...")
            print(f"   TP: {take_profit} | SL: {stop_loss}")
            
            # Take Profit order
            if take_profit:
                tp_params = {
                    'symbol': formatted_symbol,
                    'side': 'SELL' if position_side == 'LONG' else 'BUY',  # Opposite side to close position
                    'positionSide': position_side,
                    'type': 'TAKE_PROFIT_MARKET',
                    'stopPrice': str(take_profit),
                    'quantity': quantity,
                    'workingType': 'MARK_PRICE'
                }
                tp_result = self._request('POST', '/openApi/swap/v2/trade/order', tp_params)
                print(f"   TP order result: Code={tp_result.get('code')}, Msg={tp_result.get('msg')}")
                
                if tp_result.get('code') != 0:
                    print(f"   ❌ Failed to set TP: {tp_result.get('msg')}")
                else:
                    print(f"   ✅ TP order placed successfully")
            
            # Stop Loss order
            if stop_loss:
                sl_params = {
                    'symbol': formatted_symbol,
                    'side': 'SELL' if position_side == 'LONG' else 'BUY',  # Opposite side to close position
                    'positionSide': position_side,
                    'type': 'STOP_MARKET',
                    'stopPrice': str(stop_loss),
                    'quantity': quantity,
                    'workingType': 'MARK_PRICE'
                }
                sl_result = self._request('POST', '/openApi/swap/v2/trade/order', sl_params)
                print(f"   SL order result: Code={sl_result.get('code')}, Msg={sl_result.get('msg')}")
                
                if sl_result.get('code') != 0:
                    print(f"   ❌ Failed to set SL: {sl_result.get('msg')}")
                else:
                    print(f"   ✅ SL order placed successfully")
        
        return order_result
    
    def close_position(self, symbol: str, position_side: str, quantity: float) -> Dict:
        formatted_symbol = self._format_symbol_for_api(symbol)
        side = 'SELL' if position_side == 'LONG' else 'BUY'
        params = {
            'symbol': formatted_symbol,
            'side': side,
            'positionSide': position_side,
            'type': 'MARKET',
            'quantity': quantity
        }
        
        return self._request('POST', '/openApi/swap/v2/trade/order', params)
    
    def get_positions(self) -> Dict:
        return self._request('GET', '/openApi/swap/v2/user/positions')
    
    def get_order_status(self, symbol: str, order_id: str) -> Dict:
        formatted_symbol = self._format_symbol_for_api(symbol)
        params = {
            'symbol': formatted_symbol,
            'orderId': order_id
        }
        return self._request('GET', '/openApi/swap/v2/trade/order', params)
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        formatted_symbol = self._format_symbol_for_api(symbol)
        
        # BingX accounts in Hedge Mode require setting leverage separately for LONG and SHORT
        # Set leverage for LONG side
        params_long = {
            'symbol': formatted_symbol,
            'side': 'LONG',
            'leverage': leverage
        }
        result_long = self._request('POST', '/openApi/swap/v2/trade/leverage', params_long)
        
        # Set leverage for SHORT side
        params_short = {
            'symbol': formatted_symbol,
            'side': 'SHORT',
            'leverage': leverage
        }
        result_short = self._request('POST', '/openApi/swap/v2/trade/leverage', params_short)
        
        # Return combined result
        if result_long.get('code') == 0 and result_short.get('code') == 0:
            return {'code': 0, 'msg': 'success', 'data': {'long': result_long, 'short': result_short}}
        else:
            # Return first error encountered
            return result_long if result_long.get('code') != 0 else result_short
