"""
Synthetic Basis Calculator

Computes basis_pct = (markPrice - spotMid) / spotMid * 100
using multi-provider fallback for spot mid-price.
"""
import asyncio
from typing import Optional, Dict
from collections import defaultdict


class SyntheticBasisCalculator:
    """
    Calculates synthetic basis using futures markPrice and spot mid-price.
    
    Spot mid-price provider fallback order:
    1. Binance Spot bookTicker (WebSocket, real-time)
    2. OKX Spot ticker (REST)
    3. Bybit Spot ticker (REST)
    4. Coinbase Spot ticker (REST)
    """
    
    def __init__(self, spot_ws_client, okx_client, bybit_client, coinbase_client):
        self.spot_ws_client = spot_ws_client
        self.okx_client = okx_client
        self.bybit_client = bybit_client
        self.coinbase_client = coinbase_client
        
        # Real-time caches
        self.mark_prices: Dict[str, float] = {}  # {symbol: markPrice}
        self.spot_mid_prices: Dict[str, float] = {}  # {symbol: spotMid}
        
        # Provider tracking
        self.spot_providers: Dict[str, str] = {}  # {symbol: provider_name}
    
    async def start_subscriptions(self, symbols: list[str]):
        """Start WebSocket subscriptions for mark price and spot mid price"""
        print(f"[SYNTH BASIS] Starting subscriptions for {len(symbols)} symbols")
        
        # Subscribe to Binance Spot bookTicker (primary spot provider)
        await self.spot_ws_client.subscribe_book_ticker(symbols, self._on_spot_ticker)
        
        print("[SYNTH BASIS] Subscriptions started")
    
    def update_mark_price(self, symbol: str, mark_price: float):
        """Update mark price from futures markPrice stream"""
        self.mark_prices[symbol] = mark_price
    
    async def _on_spot_ticker(self, data: dict):
        """Handle Binance Spot bookTicker WebSocket message"""
        try:
            symbol = data.get('s', '').upper()
            bid = float(data.get('b', 0))
            ask = float(data.get('a', 0))
            
            if bid > 0 and ask > 0:
                spot_mid = (bid + ask) / 2
                self.spot_mid_prices[symbol] = spot_mid
                self.spot_providers[symbol] = 'binance_spot_ws'
        except (KeyError, ValueError, TypeError):
            pass
    
    async def get_spot_mid(self, symbol: str) -> tuple[Optional[float], Optional[str]]:
        """
        Get spot mid price with fallback providers.
        
        Returns:
            (spot_mid_price, provider_name) or (None, None)
        """
        # Try Binance Spot WebSocket cache first
        if symbol in self.spot_mid_prices:
            return self.spot_mid_prices[symbol], 'binance_spot_ws'
        
        # Fallback to OKX REST
        try:
            spot_mid = await self.okx_client.get_ticker(symbol)
            if spot_mid:
                return spot_mid, 'okx_spot'
        except Exception as e:
            print(f"[SYNTH BASIS] OKX fallback failed for {symbol}: {e}")
        
        # Fallback to Bybit REST
        try:
            spot_mid = await self.bybit_client.get_ticker(symbol)
            if spot_mid:
                return spot_mid, 'bybit_spot'
        except Exception as e:
            print(f"[SYNTH BASIS] Bybit fallback failed for {symbol}: {e}")
        
        # Final fallback to Coinbase REST
        try:
            spot_mid = await self.coinbase_client.get_ticker(symbol)
            if spot_mid:
                return spot_mid, 'coinbase_spot'
        except Exception as e:
            print(f"[SYNTH BASIS] Coinbase fallback failed for {symbol}: {e}")
        
        return None, None
    
    async def calculate_basis(self, symbol: str) -> tuple[Optional[float], Optional[str]]:
        """
        Calculate synthetic basis percentage.
        
        Returns:
            (basis_pct, provider_name) or (None, None)
        
        Formula:
            basis_pct = (markPrice - spotMid) / spotMid * 100
        """
        # Get mark price from cache
        mark_price = self.mark_prices.get(symbol)
        if not mark_price:
            return None, None
        
        # Get spot mid price with fallback
        spot_mid, provider = await self.get_spot_mid(symbol)
        if not spot_mid:
            return None, None
        
        # Calculate basis percentage
        try:
            basis_pct = (mark_price - spot_mid) / spot_mid * 100
            return basis_pct, provider
        except (ZeroDivisionError, TypeError):
            return None, None
