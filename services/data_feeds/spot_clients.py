"""
Spot market clients for synthetic basis calculation.
"""
import aiohttp
import asyncio
import websockets
import json
from typing import Optional, Dict, Callable


class BinanceSpotWebSocket:
    """WebSocket client for Binance Spot bookTicker"""
    
    WS_BASE = "wss://stream2.binance.com:9443"
    
    def __init__(self):
        self.ws = None
        self.running = False
        self.callback = None
    
    async def subscribe_book_ticker(self, symbols: list[str], callback: Callable):
        """
        Subscribe to combined bookTicker stream for spot symbols.
        Stream: wss://stream.binance.com:9443/stream?streams=symbol1@bookTicker/symbol2@bookTicker/...
        """
        streams = '/'.join([f"{symbol.lower()}@bookTicker" for symbol in symbols])
        stream_url = f"{self.WS_BASE}/stream?streams={streams}"
        
        self.callback = callback
        asyncio.create_task(self._ws_loop(stream_url))
    
    async def _ws_loop(self, url: str):
        """WebSocket connection loop with auto-reconnect"""
        retry_delay = 1
        max_retry_delay = 60
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    print(f"[SPOT WS] Connected: Binance Spot bookTicker")
                    retry_delay = 1
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if self.callback and 'data' in data:
                                await self.callback(data['data'])
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            print(f"[SPOT WS ERROR] Processing: {e}")
            
            except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
                print(f"[SPOT WS ERROR] Connection: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            
            except Exception as e:
                print(f"[SPOT WS FATAL] {e}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)


class OKXSpotClient:
    """REST client for OKX Spot tickers"""
    
    BASE_URL = "https://www.okx.com"
    
    # Symbol mapping: USDT futures -> OKX spot
    SYMBOL_MAP = {
        'BTCUSDT': 'BTC-USDT',
        'ETHUSDT': 'ETH-USDT',
        'BNBUSDT': 'BNB-USDT',
        'SOLUSDT': 'SOL-USDT',
        'AVAXUSDT': 'AVAX-USDT',
        'DOGEUSDT': 'DOGE-USDT',
        'LINKUSDT': 'LINK-USDT',
        'XRPUSDT': 'XRP-USDT',
        'TRXUSDT': 'TRX-USDT',
        'ADAUSDT': 'ADA-USDT',
        'HYPEUSDT': 'HYPE-USDT',
    }
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
    
    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get spot mid price from OKX ticker"""
        okx_symbol = self.SYMBOL_MAP.get(symbol)
        if not okx_symbol:
            return None
        
        endpoint = f"{self.BASE_URL}/api/v5/market/ticker"
        params = {"instId": okx_symbol}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('code') == '0' and data.get('data'):
                        ticker = data['data'][0]
                        bid = float(ticker.get('bidPx', 0))
                        ask = float(ticker.get('askPx', 0))
                        if bid > 0 and ask > 0:
                            return (bid + ask) / 2
        except Exception as e:
            print(f"[OKX ERROR] {symbol}: {e}")
        return None


class BybitSpotClient:
    """REST client for Bybit Spot tickers"""
    
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
    
    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get spot mid price from Bybit ticker"""
        endpoint = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "spot", "symbol": symbol}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        ticker = data['result']['list'][0]
                        bid = float(ticker.get('bid1Price', 0))
                        ask = float(ticker.get('ask1Price', 0))
                        if bid > 0 and ask > 0:
                            return (bid + ask) / 2
        except Exception as e:
            print(f"[BYBIT ERROR] {symbol}: {e}")
        return None


class CoinbaseSpotClient:
    """REST client for Coinbase Spot tickers"""
    
    BASE_URL = "https://api.coinbase.com"
    
    # Symbol mapping: USDT -> USD for Coinbase
    SYMBOL_MAP = {
        'BTCUSDT': 'BTC-USD',
        'ETHUSDT': 'ETH-USD',
        'SOLUSDT': 'SOL-USD',
        'AVAXUSDT': 'AVAX-USD',
        'DOGEUSDT': 'DOGE-USD',
        'LINKUSDT': 'LINK-USD',
        'XRPUSDT': 'XRP-USD',
        'TRXUSDT': 'TRX-USD',
        'ADAUSDT': 'ADA-USD',
    }
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self._own_session = session is None
    
    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            await self.session.close()
    
    async def get_ticker(self, symbol: str) -> Optional[float]:
        """Get spot mid price from Coinbase ticker"""
        cb_symbol = self.SYMBOL_MAP.get(symbol)
        if not cb_symbol:
            return None
        
        endpoint = f"{self.BASE_URL}/api/v3/brokerage/products/{cb_symbol}/ticker"
        
        try:
            async with self.session.get(endpoint, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'price' in data:
                        return float(data['price'])
        except Exception as e:
            print(f"[COINBASE ERROR] {symbol}: {e}")
        return None
