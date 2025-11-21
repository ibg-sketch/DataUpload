#!/usr/bin/env python3
"""
Signal Tracker Service - Real-time Effectiveness Monitoring
Tracks sent signals, monitors price movements, and logs results
"""

import json
import time
import csv
import requests
from datetime import datetime, timedelta
from pathlib import Path
import os
import fcntl
from dotenv import load_dotenv
from alert_manager import enqueue_alert, process_alert_queue, get_queue_status, update_alert_extremes
from telegram_utils import send_telegram_message, send_to_trading_channel

load_dotenv()

TRACKING_FILE = 'active_signals.json'
SIGNALS_LOG = 'signals_log.csv'
EFFECTIVENESS_LOG = 'effectiveness_log.csv'
CHECK_INTERVAL = 30  # Optimized to reduce Coinalyze API load (Binance blocked in region)

COINALYZE_API = 'https://api.coinalyze.net/v1'
COINALYZE_KEY = os.getenv('COINALYZE_API_KEY')

def _symbol_to_coinalyze(s):
    """Convert symbol to Coinalyze format (e.g., BTCUSDT -> BTCUSDT_PERP.A)"""
    symbol_map = {
        'BTCUSDT': 'BTCUSDT_PERP.A',
        'ETHUSDT': 'ETHUSDT_PERP.A',
        'BNBUSDT': 'BNBUSDT_PERP.A',
        'SOLUSDT': 'SOLUSDT_PERP.A',
        'AVAXUSDT': 'AVAXUSDT_PERP.A',
        'DOGEUSDT': 'DOGEUSDT_PERP.A',
        'LINKUSDT': 'LINKUSDT_PERP.A',
        'XRPUSDT': 'XRPUSDT_PERP.A',
        'TRXUSDT': 'TRXUSDT_PERP.A',
        'ADAUSDT': 'ADAUSDT_PERP.A',
        'HYPEUSDT': 'HYPEUSDT_PERP.A',
        'YFIUSDT': 'YFIUSDT_PERP.A',
        'LUMIAUSDT': 'LUMIAUSDT_PERP.A',
        'ANIMEUSDT': 'ANIMEUSDT_PERP.A'
    }
    return symbol_map.get(s, s)

class ActiveSignalsManager:
    """
    Context manager for safe read-modify-write of active_signals.json.
    Ensures entire operation is protected by exclusive lock to prevent race conditions.
    """
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock_path = file_path + '.lock'
        self.lock_file = None
        self.signals = []
        
    def __enter__(self):
        """Acquire exclusive lock and load signals"""
        import tempfile
        
        # Create lock file if it doesn't exist
        Path(self.lock_path).touch(exist_ok=True)
        
        # Acquire exclusive lock for entire read-modify-write
        self.lock_file = open(self.lock_path, 'r')
        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
        
        # Now safely read the data
        if Path(self.file_path).exists():
            try:
                with open(self.file_path, 'r') as f:
                    self.signals = json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[TRACKER WARN] JSON decode error: {e}, using empty list")
                self.signals = []
            except Exception as e:
                print(f"[TRACKER WARN] Read error: {e}, using empty list")
                self.signals = []
        
        return self.signals
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Save signals and release lock"""
        import tempfile
        
        try:
            # Write to temp file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.file_path) or '.',
                prefix='.active_signals_tmp_',
                suffix='.json'
            )
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(self.signals, f, indent=2)
                
                # Atomic rename
                os.replace(temp_path, self.file_path)
            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
        except Exception as e:
            print(f"[TRACKER ERROR] Failed to save: {e}")
        finally:
            # Always release lock
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
        
        return False  # Don't suppress exceptions

def load_active_signals():
    """
    Load currently tracked signals.
    DEPRECATED: Use ActiveSignalsManager context manager for read-modify-write.
    """
    if not Path(TRACKING_FILE).exists():
        return []
    
    try:
        with open(TRACKING_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[TRACKER WARN] JSON decode error: {e}, returning empty list")
        return []
    except Exception as e:
        print(f"[TRACKER WARN] Unexpected error loading signals: {e}")
        return []

def save_active_signals(signals):
    """
    Save active signals.
    DEPRECATED: Use ActiveSignalsManager context manager for read-modify-write.
    """
    import tempfile
    
    lock_file_path = TRACKING_FILE + '.lock'
    Path(lock_file_path).touch(exist_ok=True)
    
    try:
        with open(lock_file_path, 'r') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                temp_fd, temp_path = tempfile.mkstemp(
                    dir=os.path.dirname(TRACKING_FILE) or '.', 
                    prefix='.active_signals_tmp_', 
                    suffix='.json'
                )
                try:
                    with os.fdopen(temp_fd, 'w') as f:
                        json.dump(signals, f, indent=2)
                    
                    os.replace(temp_path, TRACKING_FILE)
                except Exception as e:
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    raise e
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        print(f"[TRACKER ERROR] Failed to save signals: {e}")

def get_current_price(symbol):
    """
    Fetch current price from Binance Futures API (no rate limits, faster).
    Falls back to Coinalyze if Binance fails.
    """
    try:
        # Try Binance Futures API first (unlimited, free, fast)
        binance_url = "https://fapi.binance.com/fapi/v1/ticker/price"
        response = requests.get(binance_url, params={'symbol': symbol}, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        print(f"[TRACKER] Binance API failed for {symbol}, trying Coinalyze: {e}")
    
    # Fallback to Coinalyze if Binance fails
    try:
        coin_symbol = _symbol_to_coinalyze(symbol)
        params = {
            'symbols': coin_symbol,
            'interval': '1min',
            'from': int(time.time()) - 300,
            'to': int(time.time())
        }
        if COINALYZE_KEY:
            params['api_key'] = COINALYZE_KEY
        
        url = f"{COINALYZE_API}/ohlcv-history"
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and data[0].get('history'):
                history = data[0]['history']
                if history:
                    return float(history[-1]['c'])
    except Exception as e:
        print(f"[TRACKER] Coinalyze fallback also failed for {symbol}: {e}")
    
    return None

def get_ohlcv_since(symbol, since_timestamp):
    """
    Fetch OHLCV candles since a given timestamp to track true high/low.
    This prevents missing price movements between spot price checks.
    Returns list of candles with 'h' (high), 'l' (low), 'c' (close), 't' (timestamp)
    """
    try:
        # Try Binance Futures klines API first
        binance_url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            'symbol': symbol,
            'interval': '1m',
            'startTime': int(since_timestamp * 1000),  # Binance uses milliseconds
            'limit': 1000
        }
        response = requests.get(binance_url, params=params, timeout=10)
        
        if response.status_code == 200:
            klines = response.json()
            candles = []
            for k in klines:
                candles.append({
                    't': k[0] / 1000,  # Convert ms to seconds
                    'h': float(k[2]),  # High
                    'l': float(k[3]),  # Low
                    'c': float(k[4])   # Close
                })
            return candles
    except Exception as e:
        print(f"[TRACKER] Binance klines failed for {symbol}, trying Coinalyze: {e}")
    
    # Fallback to Coinalyze
    try:
        coin_symbol = _symbol_to_coinalyze(symbol)
        params = {
            'symbols': coin_symbol,
            'interval': '1min',
            'from': int(since_timestamp),
            'to': int(time.time())
        }
        if COINALYZE_KEY:
            params['api_key'] = COINALYZE_KEY
        
        url = f"{COINALYZE_API}/ohlcv-history"
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and data[0].get('history'):
                return data[0]['history']
    except Exception as e:
        print(f"[TRACKER] Coinalyze OHLCV fallback also failed for {symbol}: {e}")
    
    return []

def initialize_effectiveness_log():
    """Create effectiveness log CSV if it doesn't exist"""
    if not Path(EFFECTIVENESS_LOG).exists():
        with open(EFFECTIVENESS_LOG, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp_sent',
                'timestamp_checked',
                'symbol',
                'verdict',
                'confidence',
                'entry_price',
                'target_min',
                'target_max',
                'duration_minutes',
                'result',
                'highest_reached',
                'lowest_reached',
                'final_price',
                'profit_pct',
                'duration_actual',
                'market_strength',
                'rsi',
                'ema_short',
                'ema_long',
                'adx',
                'funding_rate'
            ])

def log_effectiveness(signal_data, result_data):
    """Log signal effectiveness result"""
    with open(EFFECTIVENESS_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            signal_data['timestamp'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            signal_data['symbol'],
            signal_data['verdict'],
            signal_data['confidence'],
            signal_data['entry_price'],
            signal_data['target_min'],
            signal_data['target_max'],
            signal_data['duration_minutes'],
            result_data['result'],
            result_data['highest_reached'],
            result_data['lowest_reached'],
            result_data['final_price'],
            result_data['profit_pct'],
            result_data['duration_actual'],
            signal_data.get('market_strength', 1.0),
            signal_data.get('rsi', None),
            signal_data.get('ema_short', None),
            signal_data.get('ema_long', None),
            signal_data.get('adx', None),
            signal_data.get('funding_rate', None)
        ])

def reconcile_active_signals_on_startup():
    """
    STARTUP RECONCILIATION: Filter active_signals.json to only include signals that:
    1. Have telegram_msg_id > 0
    2. Exist in sent_signals.json (successfully delivered to Telegram)
    
    This prevents orphaned signals with telegram_msg_id=0 from breaking reply-to chains.
    Called once at startup before normal tracking begins.
    """
    print("[RECONCILE] Starting startup reconciliation...")
    
    # Load sent_signals.json to build valid signal_id set
    valid_signal_ids = set()
    sent_signals_file = 'sent_signals.json'
    if Path(sent_signals_file).exists():
        try:
            with open(sent_signals_file, 'r') as f:
                sent_data = json.load(f)
                if isinstance(sent_data, list):
                    for sig in sent_data:
                        if sig.get('message_id', 0) > 0 and sig.get('signal_id'):
                            valid_signal_ids.add(sig['signal_id'])
        except Exception as e:
            print(f"[RECONCILE WARN] Error reading sent_signals.json: {e}")
    
    # Filter active_signals.json
    removed_count = 0
    kept_count = 0
    
    with ActiveSignalsManager(TRACKING_FILE) as active_signals:
        original_count = len(active_signals)
        filtered_signals = []
        
        for sig in active_signals:
            # Keep only if: (1) telegram_msg_id > 0 AND (2) signal_id in sent_signals.json
            signal_id = sig.get('signal_id', '')
            telegram_msg_id = sig.get('telegram_msg_id', 0)
            
            if telegram_msg_id > 0 and signal_id in valid_signal_ids:
                filtered_signals.append(sig)
                kept_count += 1
            else:
                removed_count += 1
                print(f"[RECONCILE] Removed orphaned signal: {sig['symbol']} {sig['verdict']} @ {sig['timestamp']} (msg_id={telegram_msg_id}, signal_id={signal_id[:8]}...)")
        
        # Replace with filtered list
        active_signals.clear()
        active_signals.extend(filtered_signals)
    
    print(f"[RECONCILE] Complete: {kept_count} kept, {removed_count} removed (original: {original_count})")
    return removed_count

def load_new_signals_from_log():
    """
    Load new signals from signals_log.csv that are not yet in effectiveness_log.csv.
    Returns list of signal dictionaries ready to be added to active tracking.
    """
    if not Path(SIGNALS_LOG).exists():
        return []
    
    # Load sent_signals.json to get telegram_msg_id for signals
    # CRITICAL FIX: Use signal_id for reliable lookup (timestamp mismatch between CSV and JSON)
    sent_signals_map = {}
    sent_signals_file = 'sent_signals.json'  # List format: [{symbol, message_id, timestamp, verdict, signal_id, ...}, ...]
    if Path(sent_signals_file).exists():
        try:
            with open(sent_signals_file, 'r') as f:
                sent_data = json.load(f)
                # Handle both old dict format and new list format
                if isinstance(sent_data, dict):
                    # Old format: {symbol: {message_id, timestamp, verdict, ...}}
                    for symbol, sig_data in sent_data.items():
                        # Try signal_id first, fallback to timestamp key for old data
                        if 'signal_id' in sig_data and sig_data['signal_id']:
                            key = sig_data['signal_id']
                            sent_signals_map[key] = sig_data.get('message_id', 0)
                        # Legacy timestamp-based key
                        key_legacy = f"{sig_data['timestamp']}_{symbol}_{sig_data['verdict']}"
                        sent_signals_map[key_legacy] = sig_data.get('message_id', 0)
                else:
                    # New list format: [{symbol, message_id, timestamp, verdict, signal_id, ...}, ...]
                    for sig_data in sent_data:
                        # Try signal_id first, fallback to timestamp key for old data
                        if 'signal_id' in sig_data and sig_data['signal_id']:
                            key = sig_data['signal_id']
                            sent_signals_map[key] = sig_data.get('message_id', 0)
                        # Legacy timestamp-based key
                        key_legacy = f"{sig_data['timestamp']}_{sig_data['symbol']}_{sig_data['verdict']}"
                        sent_signals_map[key_legacy] = sig_data.get('message_id', 0)
        except Exception as e:
            print(f"[TRACKER WARN] Error reading sent_signals.json: {e}")
    
    # Load all tracked signals from effectiveness_log
    tracked_signals = set()
    if Path(EFFECTIVENESS_LOG).exists():
        try:
            with open(EFFECTIVENESS_LOG, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Create unique key: timestamp + symbol + verdict
                    key = f"{row['timestamp_sent']}_{row['symbol']}_{row['verdict']}"
                    tracked_signals.add(key)
        except Exception as e:
            print(f"[TRACKER WARN] Error reading effectiveness log: {e}")
    
    # Load signals from signals_log.csv
    new_signals = []
    try:
        with open(SIGNALS_LOG, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Create same unique key
                key = f"{row['timestamp']}_{row['symbol']}_{row['verdict']}"
                
                # Skip if already tracked
                if key in tracked_signals:
                    continue
                
                # FIXED: Don't skip expired signals - let check_signal_completion handle them
                # This ensures ALL signals are tracked and get a result (WIN/LOSS/CANCELLED)
                try:
                    signal_time = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    duration_minutes = int(row.get('ttl_minutes', row.get('duration_minutes', 30)))
                except Exception as e:
                    print(f"[TRACKER WARN] Error parsing signal timestamp: {e}")
                    continue
                
                # Convert CSV row to signal format
                try:
                    # Get telegram_msg_id from sent_signals.json if available
                    # CRITICAL FIX: Try signal_id first, fallback to timestamp-based key for old data
                    telegram_msg_id = 0
                    signal_id = row.get('signal_id', '')
                    if signal_id:
                        # New signal_id-based lookup (reliable)
                        telegram_msg_id = sent_signals_map.get(signal_id, 0)
                    
                    if telegram_msg_id == 0:
                        # Fallback to legacy timestamp-based lookup for old data
                        lookup_key = f"{row['timestamp']}_{row['symbol']}_{row['verdict']}"
                        telegram_msg_id = sent_signals_map.get(lookup_key, 0)
                    
                    # CRITICAL FILTER: Skip signals without valid telegram_msg_id
                    # These are signals where Telegram send failed - they should NOT be tracked
                    if telegram_msg_id == 0:
                        print(f"[TRACKER FILTER] Skipping signal without Telegram msg_id: {row['symbol']} {row['verdict']} @ {row['timestamp']}")
                        continue
                    
                    signal = {
                        'timestamp': row['timestamp'],
                        'symbol': row['symbol'],
                        'verdict': row['verdict'],
                        'confidence': float(row['confidence']),
                        'entry_price': float(row['entry_price']),
                        'target_min': float(row['target_min']),
                        'target_max': float(row['target_max']),
                        'duration_minutes': duration_minutes,  # Use parsed duration_minutes
                        'highest_reached': float(row['entry_price']),
                        'lowest_reached': float(row['entry_price']),
                        'last_check_time': time.time(),
                        'market_strength': 1.0,  # Default value, not in signals_log.csv
                        'rsi': None,
                        'ema_short': None,
                        'ema_long': None,
                        'adx': None,
                        'funding_rate': None,
                        'telegram_msg_id': telegram_msg_id,  # Get from sent_signals.json
                        'signal_id': signal_id,  # Store signal_id for future tracking
                        'regime': 'neutral'  # Default regime for old signals (for cancellation logic)
                    }
                    new_signals.append(signal)
                except Exception as e:
                    print(f"[TRACKER WARN] Error converting signal: {e}")
                    continue
    
    except Exception as e:
        print(f"[TRACKER ERROR] Error reading signals_log: {e}")
        return []
    
    return new_signals

def log_cancelled_signal(signal_data):
    """
    Log a cancelled signal with its PnL at the time of cancellation.
    
    Args:
        signal_data: Signal dictionary from sent_signals.json or active_signals.json
                    Must contain: timestamp, symbol, verdict, confidence, entry_price
                    Optional: target_min, target_max, duration_minutes, market_strength
    
    Returns:
        dict: Result data with cancellation details (for reference)
    """
    # Get current price at cancellation time
    current_price = get_current_price(signal_data['symbol'])
    
    # If we can't get price, use entry price (0% PnL)
    if current_price is None:
        print(f"[CANCEL LOG WARN] Cannot fetch price for {signal_data['symbol']}, using entry price (0% PnL)")
        current_price = signal_data['entry_price']
    
    # Find signal in active_signals to get highest/lowest reached
    highest_reached = signal_data['entry_price']
    lowest_reached = signal_data['entry_price']
    
    try:
        with ActiveSignalsManager(TRACKING_FILE.replace('sent_signals', 'active_signals')) as active_signals:
            for sig in active_signals:
                if (sig['symbol'] == signal_data['symbol'] and 
                    sig.get('telegram_msg_id') == signal_data.get('message_id')):
                    highest_reached = sig.get('highest_reached', signal_data['entry_price'])
                    lowest_reached = sig.get('lowest_reached', signal_data['entry_price'])
                    break
    except Exception as e:
        print(f"[CANCEL LOG WARN] Could not fetch extremes from active_signals: {e}")
    
    # NEW METHODOLOGY: Calculate PnL at cancellation time using current_price
    # CANCELLED: Use current_price (price at moment of cancellation)
    verdict = signal_data['verdict']
    entry_price = signal_data['entry_price']
    
    if verdict == 'BUY':
        # For BUY: profit if current price > entry
        profit_pct = ((current_price - entry_price) / entry_price) * 100
    else:  # SELL
        # For SELL: profit if current price < entry
        profit_pct = ((entry_price - current_price) / entry_price) * 100
    
    # Calculate how long the signal was active before cancellation
    signal_timestamp = datetime.strptime(signal_data['timestamp'], '%Y-%m-%d %H:%M:%S')
    duration_actual = int((datetime.now() - signal_timestamp).total_seconds() / 60)
    
    result_data = {
        'result': 'CANCELLED',
        'highest_reached': highest_reached,
        'lowest_reached': lowest_reached,
        'final_price': current_price,
        'profit_pct': round(profit_pct, 2),
        'duration_actual': duration_actual
    }
    
    # Log to effectiveness_log.csv
    with open(EFFECTIVENESS_LOG, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            signal_data['timestamp'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            signal_data['symbol'],
            signal_data['verdict'],
            signal_data.get('confidence', 0.0),
            signal_data['entry_price'],
            signal_data.get('target_min', 0.0),
            signal_data.get('target_max', 0.0),
            signal_data.get('duration_minutes', 0),
            'CANCELLED',
            highest_reached,
            lowest_reached,
            current_price,
            result_data['profit_pct'],
            duration_actual,
            signal_data.get('market_strength', 1.0),
            signal_data.get('rsi', None),
            signal_data.get('ema_short', None),
            signal_data.get('ema_long', None),
            signal_data.get('adx', None),
            signal_data.get('funding_rate', None)
        ])
    
    print(f"[CANCEL LOG] {signal_data['symbol']} {verdict}: Cancelled at {current_price:.4f} with {profit_pct:+.2f}% PnL (Entry: {entry_price:.4f})")
    
    return result_data

def check_signal_completion(signal):
    """
    Check if a signal has completed and determine result.
    Sends TTL EXPIRED message with reply-to when signal expires.
    Returns: (is_complete, result_data or None)
    """
    timestamp = datetime.strptime(signal['timestamp'], '%Y-%m-%d %H:%M:%S')
    duration_minutes = signal['duration_minutes']
    expiry_time = timestamp + timedelta(minutes=duration_minutes)
    now = datetime.now()
    
    if now < expiry_time:
        return False, None
    
    current_price = get_current_price(signal['symbol'])
    if current_price is None:
        # Use last known price (highest or lowest) if current price unavailable
        print(f"[TRACKER WARN] Cannot fetch price for {signal['symbol']}, using last known price")
        if signal['verdict'] == 'BUY':
            current_price = signal.get('highest_reached', signal['entry_price'])
        else:
            current_price = signal.get('lowest_reached', signal['entry_price'])
    
    verdict = signal['verdict']
    entry_price = signal['entry_price']
    target_min = signal['target_min']
    target_max = signal['target_max']
    highest = signal.get('highest_reached', entry_price)
    lowest = signal.get('lowest_reached', entry_price)
    
    # Check if target was hit
    if verdict == 'BUY':
        target_hit = highest >= target_min
    else:
        target_hit = lowest <= target_max
    
    # TTL EXPIRED METHODOLOGY: Always use actual price at expiry moment
    # Calculate PnL from current_price (actual market price when TTL expired)
    # This gives real profit/loss regardless of whether target was hit or not
    exit_price = current_price
    
    if verdict == 'BUY':
        profit_pct = ((current_price - entry_price) / entry_price) * 100
    else:  # SELL
        profit_pct = ((entry_price - current_price) / entry_price) * 100
    
    # Determine result based on target hit
    result = 'WIN' if target_hit else 'LOSS'
    
    # Send TTL EXPIRED notification with reply-to
    telegram_msg_id = signal.get('telegram_msg_id', 0)
    if telegram_msg_id > 0:
        try:
            from telegram_utils import send_ttl_expired_message
            msg_id = send_ttl_expired_message(
                symbol=signal['symbol'],
                verdict=verdict,
                original_message_id=telegram_msg_id,
                result=result,
                profit_pct=round(profit_pct, 2),
                duration_minutes=duration_minutes
            )
            if msg_id:
                print(f"[TTL EXPIRED] {signal['symbol']} {verdict}: Sent notification (msg_id={msg_id}, reply_to={telegram_msg_id})")
            else:
                print(f"[TTL EXPIRED WARN] {signal['symbol']} {verdict}: Failed to send notification")
        except Exception as e:
            print(f"[TTL EXPIRED ERROR] Failed to send notification: {e}")
    else:
        print(f"[TTL EXPIRED SKIP] {signal['symbol']} {verdict}: No telegram_msg_id, skipping notification")
    
    result_data = {
        'result': result,
        'highest_reached': highest,
        'lowest_reached': lowest,
        'final_price': exit_price,  # Actual price at TTL expiry moment
        'profit_pct': round(profit_pct, 2),
        'duration_actual': int((now - timestamp).total_seconds() / 60)
    }
    
    return True, result_data

def update_signal_extremes(signal):
    """
    Update highest/lowest prices reached during signal lifetime using OHLCV data.
    This prevents missing price movements between checks.
    Also checks and sends alerts for target zone entry and final goal.
    """
    from telegram_utils import send_telegram_message
    
    # Get the last check time (or signal start time if first check)
    last_check = signal.get('last_ohlcv_check')
    if not last_check:
        # First check - use signal timestamp, but floor to previous minute
        # to ensure we capture the candle where the signal was created
        signal_start = datetime.strptime(signal['timestamp'], '%Y-%m-%d %H:%M:%S')
        # Subtract 60 seconds to ensure we get the current candle
        last_check = signal_start.timestamp() - 60
    
    # Fetch all OHLCV candles since last check
    candles = get_ohlcv_since(signal['symbol'], last_check)
    
    # If no candles, fall back to current price
    if not candles:
        current_price = get_current_price(signal['symbol'])
        if current_price is None:
            return signal
        candles = [{'h': current_price, 'l': current_price, 'c': current_price}]
    
    entry_price = signal['entry_price']
    target_min = signal['target_min']
    target_max = signal['target_max']
    verdict = signal['verdict']
    
    # Update extremes by examining ALL candles since last check
    current_highest = signal.get('highest_reached', entry_price)
    current_lowest = signal.get('lowest_reached', entry_price)
    
    for candle in candles:
        current_highest = max(current_highest, float(candle['h']))
        current_lowest = min(current_lowest, float(candle['l']))
    
    signal['highest_reached'] = current_highest
    signal['lowest_reached'] = current_lowest
    
    # Update the last check time to now (AFTER processing candles)
    signal['last_ohlcv_check'] = time.time()
    
    # CRITICAL: Update any pending/failed alerts with latest extremes
    # This ensures alert payloads stay fresh even if signal completes before alert is sent
    if signal.get('signal_id'):
        update_alert_extremes(signal['signal_id'], current_highest, current_lowest)
    
    # Check for target zone alerts using EXTREMES, not current price
    # This ensures we alert even if price hit target intra-candle and rebounded
    # Alerts are QUEUED (not sent immediately) for persistence and retry capability
    if verdict == 'BUY':
        # BUY: target_min is beginning of zone, target_max is final goal
        if current_highest >= target_min and not signal.get('target_zone_alerted'):
            # Entered target zone - enqueue alert
            enqueue_alert(
                symbol=signal['symbol'],
                verdict='BUY',
                alert_type='target_zone',
                signal_data=signal,
                signal_id=signal.get('signal_id')
            )
            signal['target_zone_alerted'] = True
            print(f"[ALERT QUEUED] {signal['symbol']} BUY - Target zone reached @ ${current_highest:.4f}")
        
        if current_highest >= target_max and not signal.get('final_goal_alerted'):
            # Hit final goal - enqueue alert
            enqueue_alert(
                symbol=signal['symbol'],
                verdict='BUY',
                alert_type='final_goal',
                signal_data=signal,
                signal_id=signal.get('signal_id')
            )
            signal['final_goal_alerted'] = True
            print(f"[ALERT QUEUED] {signal['symbol']} BUY - Final goal reached @ ${current_highest:.4f}")
    
    else:  # SELL
        # SELL: target_max is beginning of zone, target_min is final goal
        if current_lowest <= target_max and not signal.get('target_zone_alerted'):
            # Entered target zone - enqueue alert
            enqueue_alert(
                symbol=signal['symbol'],
                verdict='SELL',
                alert_type='target_zone',
                signal_data=signal,
                signal_id=signal.get('signal_id')
            )
            signal['target_zone_alerted'] = True
            print(f"[ALERT QUEUED] {signal['symbol']} SELL - Target zone reached @ ${current_lowest:.4f}")
        
        if current_lowest <= target_min and not signal.get('final_goal_alerted'):
            # Hit final goal - enqueue alert
            enqueue_alert(
                symbol=signal['symbol'],
                verdict='SELL',
                alert_type='final_goal',
                signal_data=signal,
                signal_id=signal.get('signal_id')
            )
            signal['final_goal_alerted'] = True
            print(f"[ALERT QUEUED] {signal['symbol']} SELL - Final goal reached @ ${current_lowest:.4f}")
    
    return signal

def print_status(active_count, completed_count):
    """Print tracker status"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S GMT+3')
    
    # Get alert queue status
    queue_status = get_queue_status()
    
    print(f"\n[TRACKER] {timestamp}")
    print(f"  Active signals: {active_count}")
    print(f"  Completed this session: {completed_count}")
    print(f"  Alert queue: {queue_status['pending']} pending, {queue_status['failed']} failed")

def parse_timestamp(ts_str):
    """Parse timestamp from log"""
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None

def get_effectiveness_stats(hours=None):
    """
    Calculate win/loss/cancelled stats for a time period.
    If hours=None, returns all-time stats.
    Returns (wins, losses, cancelled, win_rate, total_signals, total_pnl)
    
    FIXED: Win rate now excludes CANCELLED signals from denominator
    """
    if not Path(EFFECTIVENESS_LOG).exists():
        return (0, 0, 0, 0.0, 0, 0.0)
    
    now = datetime.now()
    cutoff = now - timedelta(hours=hours) if hours else None
    
    wins = 0
    losses = 0
    cancelled = 0
    total_pnl = 0.0
    
    with open(EFFECTIVENESS_LOG, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if cutoff:
                ts = parse_timestamp(row.get('timestamp_sent', row.get('timestamp_checked', '')))
                if not ts or ts < cutoff:
                    continue
            
            if row['result'] == 'WIN':
                wins += 1
            elif row['result'] == 'LOSS':
                losses += 1
            elif row['result'] == 'CANCELLED':
                cancelled += 1
            
            try:
                total_pnl += float(row.get('profit_pct', 0))
            except (ValueError, TypeError):
                pass
    
    total = wins + losses + cancelled
    # FIXED: Win rate excludes CANCELLED from denominator
    decided = wins + losses
    win_rate = (wins / decided * 100) if decided > 0 else 0
    
    return (wins, losses, cancelled, win_rate, total, total_pnl)

def format_effectiveness_report():
    """Generate effectiveness report with FIXED win rate calculation"""
    periods = [
        (1, '1h'),
        (6, '6h'),
        (12, '12h'),
        (24, '24h'),
        (72, '3d'),
        (168, '7d'),
        (336, '14d'),
        (720, '30d'),
        (2160, '3mo'),
        (4320, '6mo'),
        (8760, '1yr')
    ]
    
    lines = ["📊 <b>EFFECTIVENESS REPORT</b>\n"]
    has_any_data = False
    
    for hours, label in periods:
        wins, losses, cancelled, win_rate, total, total_pnl = get_effectiveness_stats(hours)
        
        if total == 0:
            if hours <= 6:
                lines.append(f"⚪️ <b>{label:>4}:</b> No signals")
            continue
        
        has_any_data = True
        
        if win_rate >= 60:
            icon = "🟢"
        elif win_rate >= 50:
            icon = "🟡"
        else:
            icon = "🔴"
        
        stats = f"{wins}W-{losses}L-{cancelled}C | {total_pnl:+.2f}%"
        
        lines.append(f"{icon} <b>{label:>4}:</b> {win_rate:.0f}% ({stats})")
    
    if not has_any_data:
        return None
    
    return '\n'.join(lines)

def calculate_next_report_time(target_minute=2):
    """Calculate next scheduled report time (at :02 of next hour)"""
    now = datetime.now()
    
    if now.minute >= target_minute:
        next_hour = now.replace(minute=target_minute, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_hour = now.replace(minute=target_minute, second=0, microsecond=0)
    
    # BUGFIX: If calculated time is in the past (service restarted close to target time),
    # skip to next hour to avoid missing reports
    if next_hour <= now:
        next_hour += timedelta(hours=1)
    
    return next_hour

def main():
    """Main tracking loop with integrated hourly reporting"""
    REPORT_MINUTE = 2  # Send reports at :02 of each hour
    
    print("="*70)
    print("SIGNAL TRACKER + EFFECTIVENESS REPORTER")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S GMT+3')}")
    print(f"Tracking file: {TRACKING_FILE}")
    print(f"Signals source: {SIGNALS_LOG}")
    print(f"Results log: {EFFECTIVENESS_LOG}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print(f"Hourly reports: Every hour at :{REPORT_MINUTE:02d} minutes")
    print("="*70)
    
    initialize_effectiveness_log()
    
    # CRITICAL: Startup reconciliation - remove orphaned signals with telegram_msg_id=0
    # This ensures reply-to chains work correctly by filtering out failed Telegram sends
    reconcile_active_signals_on_startup()
    
    # Load any untracked signals from signals_log.csv at startup
    print("[TRACKER] Loading untracked signals from signals_log.csv...")
    new_signals = load_new_signals_from_log()
    if new_signals:
        with ActiveSignalsManager(TRACKING_FILE) as active_signals:
            for sig in new_signals:
                # CRITICAL: Use signal_id for deduplication to preserve enriched data from main.py
                # Avoids overwriting signals with 'regime' field by checking signal_id first
                signal_id = sig.get('signal_id', '')
                if signal_id:
                    # If signal_id exists, check by ID (reliable)
                    exists = any(s.get('signal_id') == signal_id for s in active_signals)
                else:
                    # Fallback to timestamp-based check for old signals without signal_id
                    exists = any(
                        s['timestamp'] == sig['timestamp'] and 
                        s['symbol'] == sig['symbol'] and 
                        s['verdict'] == sig['verdict']
                        for s in active_signals
                    )
                if not exists:
                    active_signals.append(sig)
        print(f"[TRACKER] ✅ Added {len(new_signals)} untracked signals to monitoring")
    else:
        print("[TRACKER] No new signals to track")
    
    completed_count = 0
    check_count = 0  # Counter for periodic signal reload
    
    # Initialize hourly reporting schedule
    next_report_time = calculate_next_report_time(REPORT_MINUTE)
    print(f"[REPORT] Next effectiveness report: {next_report_time.strftime('%H:%M:%S')}")
    
    while True:
        try:
            # Periodically check for new signals from signals_log.csv (every 10 iterations)
            check_count += 1
            if check_count % 10 == 0:
                new_signals = load_new_signals_from_log()
                if new_signals:
                    with ActiveSignalsManager(TRACKING_FILE) as active_signals:
                        added_count = 0
                        for sig in new_signals:
                            # CRITICAL: Use signal_id for deduplication to preserve enriched data from main.py
                            # Avoids overwriting signals with 'regime' field by checking signal_id first
                            signal_id = sig.get('signal_id', '')
                            if signal_id:
                                # If signal_id exists, check by ID (reliable)
                                exists = any(s.get('signal_id') == signal_id for s in active_signals)
                            else:
                                # Fallback to timestamp-based check for old signals without signal_id
                                exists = any(
                                    s['timestamp'] == sig['timestamp'] and 
                                    s['symbol'] == sig['symbol'] and 
                                    s['verdict'] == sig['verdict']
                                    for s in active_signals
                                )
                            if not exists:
                                active_signals.append(sig)
                                added_count += 1
                    if added_count > 0:
                        print(f"[TRACKER] ✅ Added {added_count} new signals from signals_log.csv")
            
            # Use context manager for atomic read-modify-write
            with ActiveSignalsManager(TRACKING_FILE) as active_signals:
                if not active_signals:
                    print(f"\n[TRACKER] {datetime.now().strftime('%H:%M:%S')} - No active signals to track")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # Save original list, clear, then rebuild with only non-completed signals
                original_signals = list(active_signals)
                active_signals.clear()
                
                for signal in original_signals:
                    signal = update_signal_extremes(signal)
                    
                    is_complete, result_data = check_signal_completion(signal)
                    
                    if is_complete and result_data is not None:
                        log_effectiveness(signal, result_data)
                        completed_count += 1
                        
                        result_icon = "✅" if result_data['result'] == 'WIN' else "❌"
                        print(f"\n{result_icon} {signal['symbol']} {signal['verdict']} @ {signal['confidence']:.0%}")
                        print(f"   Entry: ${signal['entry_price']:,.2f}")
                        print(f"   Target: ${signal['target_min']:,.2f} - ${signal['target_max']:,.2f}")
                        print(f"   Result: {result_data['result']} | Profit: {result_data['profit_pct']:+.2f}%")
                        print(f"   Duration: {result_data['duration_actual']} minutes")
                    else:
                        active_signals.append(signal)
                        
                        time_left = signal['duration_minutes'] - ((datetime.now() - datetime.strptime(signal['timestamp'], '%Y-%m-%d %H:%M:%S')).total_seconds() / 60)
                        current_price = signal.get('highest_reached', signal['entry_price']) if signal['verdict'] == 'BUY' else signal.get('lowest_reached', signal['entry_price'])
                        
                        if signal['verdict'] == 'BUY':
                            progress_pct = ((current_price - signal['entry_price']) / (signal['target_min'] - signal['entry_price'])) * 100
                        else:
                            progress_pct = ((signal['entry_price'] - current_price) / (signal['entry_price'] - signal['target_max'])) * 100
                        
                        print(f"⏳ {signal['symbol']} {signal['verdict']} @ {signal['confidence']:.0%} | {time_left:.0f}min left | Progress: {progress_pct:.0f}%")
                
                # Context manager will save automatically on exit
                print_status(len(active_signals), completed_count)
            
            # Process alert queue - send any pending alerts with retry logic
            # This runs outside the ActiveSignalsManager context to avoid lock conflicts
            sent_count = process_alert_queue()
            if sent_count > 0:
                print(f"[ALERT] Successfully sent {sent_count} queued alert(s)")
            
            # Check if it's time to send hourly effectiveness report
            now = datetime.now()
            if now >= next_report_time:
                print(f"\n[REPORT] {now.strftime('%H:%M:%S')} - Sending scheduled effectiveness report", flush=True)
                report = format_effectiveness_report()
                
                if report:
                    # Send to Signal Bot channel (main channel)
                    send_telegram_message(report)
                    print(f"[REPORT] ✅ Report sent to Signal Bot channel", flush=True)
                    
                    # Send to Trading Bot channel if configured
                    trading_channel_id = os.getenv('TRADING_TELEGRAM_CHAT_ID')
                    if trading_channel_id:
                        send_to_trading_channel(report, trading_channel_id)
                        print(f"[REPORT] ✅ Report sent to Trading Bot channel", flush=True)
                    else:
                        print(f"[REPORT] ⚠️ Trading channel not configured, skipping", flush=True)
                else:
                    print(f"[REPORT] ⚪️ No data yet, skipping report", flush=True)
                
                # Schedule next report
                next_report_time = calculate_next_report_time(REPORT_MINUTE)
                print(f"[REPORT] Next report scheduled: {next_report_time.strftime('%H:%M:%S')}", flush=True)
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n[TRACKER] Shutting down...")
            break
        except Exception as e:
            print(f"\n[TRACKER ERROR] {e}")
            import traceback
            traceback.print_exc()
            time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
