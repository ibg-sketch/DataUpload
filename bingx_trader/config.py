"""
Trading Configuration
All parameters optimized from backtesting analysis
"""
import os

class TradingConfig:
    MODE = "PAPER"
    
    EXCHANGE = "BingX"
    API_KEY = os.getenv('BINGX_API_KEY')
    API_SECRET = os.getenv('BINGX_API_SECRET')
    API_URL = "https://open-api.bingx.com"
    
    LEVERAGE = 100
    STOP_LOSS_PCT = 100  # 100% = 1% price movement at 100x leverage (effectively disabled)
    POSITION_SIZE_USD = 100
    
    TP_STRATEGY = "far"
    FIXED_TP_PCT = 75
    
    MAX_CONCURRENT_POSITIONS = 10
    DAILY_LOSS_LIMIT_USD = 999999
    MIN_CONFIDENCE = 0
    
    ALLOWED_SIGNAL_TYPES = ["BUY", "SELL"]
    
    TRADING_PAIRS = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "AVAXUSDT",
        "DOGEUSDT",
        "LINKUSDT",
        "XRPUSDT",
        "TRXUSDT",
        "ADAUSDT",
        "HYPEUSDT"
    ]
    
    TAKER_FEE = 0.0005
    MAKER_FEE = 0.0002
    
    SIGNAL_SOURCE = "signals_log.csv"
    TRADES_LOG = "bingx_trader/logs/trades_log.csv"
    POSITIONS_FILE = "bingx_trader/data/active_positions.json"
    
    TELEGRAM_BOT_TOKEN = os.getenv('TRADING_TELEGRAM_BOT_TOKEN')
    SIGNAL_CHANNEL_ID = os.getenv('TELEGRAM_CHAT_ID')
    TRADING_CHANNEL_ID = os.getenv('TRADING_TELEGRAM_CHAT_ID')
    
    POLL_INTERVAL_SECONDS = 1
    PRICE_UPDATE_INTERVAL = 2

class PaperTradingConfig:
    # Starting balance for P&L tracking only - does NOT limit position opening in paper mode
    STARTING_BALANCE = 1000
    CURRENT_BALANCE_FILE = "bingx_trader/data/paper_balance.json"
    ALL_IN_MODE = False
    LAST_POSITION_CLOSE_FILE = "bingx_trader/data/last_close_time.json"
