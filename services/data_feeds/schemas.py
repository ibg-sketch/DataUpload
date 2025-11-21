"""
Pydantic schemas for data feeds.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class FeedRow(BaseModel):
    """Single row in feeds_log.csv"""
    timestamp: datetime
    symbol: str
    oi: Optional[float] = None
    oi_pct: Optional[float] = None
    funding: Optional[float] = None
    basis: Optional[float] = None
    liq_long_usd: Optional[float] = 0.0
    liq_short_usd: Optional[float] = 0.0
    liq_ratio: Optional[float] = None
    obi_top: Optional[float] = None
    basis_pct: Optional[float] = None
    basis_provider: Optional[str] = None
    latency_ms: Optional[int] = None
    source_errors: int = 0
    provider_oi: Optional[str] = None
    provider_funding: Optional[str] = None
    provider_basis: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S')
        }


class OIData(BaseModel):
    """Open Interest data from Binance"""
    symbol: str
    sumOpenInterest: float
    sumOpenInterestValue: float
    timestamp: int


class FundingData(BaseModel):
    """Funding rate data"""
    symbol: str
    fundingRate: float
    fundingTime: int


class BasisData(BaseModel):
    """Premium Index (Basis) data"""
    symbol: str
    markPrice: float
    indexPrice: float
    estimatedSettlePrice: Optional[float] = None
    lastFundingRate: float
    time: int


class LiquidationEvent(BaseModel):
    """Single liquidation event from WebSocket"""
    symbol: str
    side: str  # BUY or SELL
    order_type: str
    time_in_force: str
    original_qty: float
    price: float
    avg_price: float
    order_status: str
    order_last_filled_qty: float
    order_filled_accumulated_qty: float
    order_trade_time: int


class DepthSnapshot(BaseModel):
    """Order book depth snapshot"""
    symbol: str
    bids: list[list[float]]  # [[price, qty], ...]
    asks: list[list[float]]
    timestamp: int


class BookTickerData(BaseModel):
    """Book ticker data from combined stream"""
    symbol: str
    best_bid_price: float = Field(alias='b')
    best_bid_qty: float = Field(alias='B')
    best_ask_price: float = Field(alias='a')
    best_ask_qty: float = Field(alias='A')
    
    class Config:
        populate_by_name = True
