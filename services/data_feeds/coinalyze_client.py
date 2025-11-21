"""
Coinalyze REST client for aggregated market data.
"""
import aiohttp
import os
from typing import Optional, List
from .schemas import OIData, FundingData


class CoinalyzeRESTClient:
    """Async REST client for Coinalyze API"""
    
    BASE_URL = "https://api.coinalyze.net/v1"
    
    def __init__(self, api_key: Optional[str] = None, session: Optional[aiohttp.ClientSession] = None):
        self.api_key = api_key or os.getenv('COINALYZE_API_KEY')
        self.session = session
        self._own_session = session is None
    
    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    def _symbol_to_coinalyze_format(self, symbol: str) -> str:
        """
        Convert Binance symbol to Coinalyze aggregated format.
        Example: BTCUSDT -> BTCUSDT_PERP.A (aggregated across exchanges)
        """
        return f"{symbol}_PERP.A"
    
    async def get_open_interest(self, symbol: str) -> Optional[OIData]:
        """
        Get current Open Interest from Coinalyze (aggregated across exchanges).
        
        Returns:
            OIData with sumOpenInterest (value) and timestamp (update)
        """
        if not self.api_key:
            return None
        
        endpoint = f"{self.BASE_URL}/open-interest"
        params = {
            "api_key": self.api_key,
            "symbols": self._symbol_to_coinalyze_format(symbol)
        }
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        item = data[0]
                        return OIData(
                            symbol=symbol,
                            sumOpenInterest=float(item.get('value', 0)),
                            sumOpenInterestValue=float(item.get('value', 0)),
                            timestamp=int(item.get('update', 0))
                        )
                else:
                    return None
        except Exception:
            return None
        return None
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingData]:
        """
        Get current Funding Rate from Coinalyze (aggregated across exchanges).
        
        Returns:
            FundingData with fundingRate (value) and fundingTime (update)
        """
        if not self.api_key:
            return None
        
        endpoint = f"{self.BASE_URL}/funding-rate"
        params = {
            "api_key": self.api_key,
            "symbols": self._symbol_to_coinalyze_format(symbol)
        }
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        item = data[0]
                        return FundingData(
                            symbol=symbol,
                            fundingRate=float(item.get('value', 0)),
                            fundingTime=int(item.get('update', 0))
                        )
                else:
                    return None
        except Exception:
            return None
        return None
