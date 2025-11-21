#!/usr/bin/env python3
"""
CVD (Cumulative Volume Delta) Service
Connects to Binance Futures WebSocket to calculate real-time CVD for all trading pairs.
No API key required - uses public market data.
"""

import json
import time
from websocket._app import WebSocketApp
import threading
from datetime import datetime
from pathlib import Path
import pytz

# Timezone configuration - GMT+3
TZ = pytz.timezone('Etc/GMT-3')

# Configuration
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT']
CVD_DATA_FILE = 'cvd_data.json'
SAVE_INTERVAL = 5  # Save CVD data every 5 seconds
# LOOKBACK_HOURS removed - now storing full history without reset

# Global CVD storage
cvd_values = {}
cvd_history = {}  # Rolling history for each symbol (timestamp, cvd_value)
trade_counts = {}
last_save_time = time.time()
last_reset_time = time.time()

# History configuration
MAX_HISTORY_SIZE = 1000  # Keep last 1000 CVD snapshots (~16 minutes at 1 snapshot/sec)

def load_cvd_data():
    """Load existing CVD data from file if available"""
    global cvd_values, cvd_history, last_reset_time
    try:
        if Path(CVD_DATA_FILE).exists():
            with open(CVD_DATA_FILE, 'r') as f:
                data = json.load(f)
                cvd_values = data.get('cvd', {})
                cvd_history = data.get('cvd_history', {})
                last_reset_time = data.get('last_reset', time.time())
                print(f"[CVD] Loaded existing CVD data: {len(cvd_values)} symbols")
                for symbol, value in cvd_values.items():
                    history_len = len(cvd_history.get(symbol, []))
                    print(f"  {symbol}: {value:,.0f} (history: {history_len} points)")
    except Exception as e:
        print(f"[CVD] Could not load existing data: {e}")
        cvd_values = {s: 0.0 for s in SYMBOLS}
        cvd_history = {s: [] for s in SYMBOLS}
        last_reset_time = time.time()

def save_cvd_data():
    """Save CVD data to file including rolling history"""
    try:
        data = {
            'cvd': cvd_values,
            'cvd_history': cvd_history,
            'trade_counts': trade_counts,
            'last_reset': last_reset_time,
            'last_update': time.time(),
            'timestamp': datetime.now(TZ).isoformat()
        }
        with open(CVD_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[CVD] Error saving data: {e}")

# Reset function removed - CVD now accumulates indefinitely for full history

def on_message(ws, message):
    """Handle incoming trade messages from Binance WebSocket"""
    global cvd_values, cvd_history, trade_counts, last_save_time
    
    try:
        data = json.loads(message)
        
        # Handle combined stream format
        if 'data' in data:
            data = data['data']
        
        # Extract trade information
        symbol = data.get('s', '')
        if symbol not in SYMBOLS:
            return
        
        price = float(data.get('p', 0))
        quantity = float(data.get('q', 0))
        is_buyer_maker = data.get('m', False)
        
        # Initialize if needed
        if symbol not in cvd_values:
            cvd_values[symbol] = 0.0
        if symbol not in cvd_history:
            cvd_history[symbol] = []
        if symbol not in trade_counts:
            trade_counts[symbol] = 0
        
        # Calculate delta
        # m=false means buyer is taker (aggressive buy) -> positive delta
        # m=true means seller is taker (aggressive sell) -> negative delta
        usd_volume = price * quantity
        delta = -usd_volume if is_buyer_maker else usd_volume
        
        # Update CVD
        cvd_values[symbol] += delta
        trade_counts[symbol] += 1
        
        # Update rolling history (append current CVD value with timestamp)
        current_time = time.time()
        cvd_history[symbol].append({
            'timestamp': current_time,
            'cvd': cvd_values[symbol]
        })
        
        # Trim history to MAX_HISTORY_SIZE (keep last N points)
        if len(cvd_history[symbol]) > MAX_HISTORY_SIZE:
            cvd_history[symbol] = cvd_history[symbol][-MAX_HISTORY_SIZE:]
        
        # Log every 100 trades per symbol for monitoring
        if trade_counts[symbol] % 100 == 0:
            side = "SELL" if is_buyer_maker else "BUY "
            history_len = len(cvd_history[symbol])
            print(f"[{symbol}] {side} {quantity:.4f} @ ${price:,.2f} | CVD: {cvd_values[symbol]:+,.0f} USDT ({trade_counts[symbol]} trades, history: {history_len})")
        
        # Periodic save
        if time.time() - last_save_time >= SAVE_INTERVAL:
            save_cvd_data()
            last_save_time = time.time()
        
    except Exception as e:
        print(f"[CVD] Error processing message: {e}")

def on_error(ws, error):
    """Handle WebSocket errors"""
    print(f"[CVD] WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close"""
    print(f"[CVD] WebSocket connection closed: {close_status_code} - {close_msg}")
    print("[CVD] Will attempt to reconnect in 5 seconds...")
    save_cvd_data()

def on_open(ws):
    """Handle WebSocket connection open"""
    print(f"[CVD] ✅ Connected to Binance Futures WebSocket")
    print(f"[CVD] Monitoring {len(SYMBOLS)} symbols: {', '.join(SYMBOLS)}")
    print(f"[CVD] Storing full history (no automatic reset)")
    print(f"[CVD] Data saved to: {CVD_DATA_FILE}")
    print("-" * 70)

def create_websocket_url():
    """Create WebSocket URL for combined stream of all symbols"""
    # Convert symbols to lowercase and create stream names
    streams = [f"{symbol.lower()}@aggTrade" for symbol in SYMBOLS]
    combined_stream = "/".join(streams)
    
    # Combined stream endpoint
    url = f"wss://fstream.binance.com/stream?streams={combined_stream}"
    return url

def start_cvd_service():
    """Start the CVD WebSocket service"""
    print("=" * 70)
    print("CVD SERVICE - Cumulative Volume Delta Tracker")
    print("=" * 70)
    print(f"Started: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S GMT+3')}")
    print(f"Data source: Binance Futures (Public WebSocket)")
    print(f"Authentication: None required (public market data)")
    print("=" * 70)
    print()
    
    # Load existing data
    load_cvd_data()
    
    # Create WebSocket URL
    ws_url = create_websocket_url()
    print(f"[CVD] Connecting to: {ws_url[:80]}...")
    print()
    
    # Create WebSocket connection with auto-reconnect
    def run_with_reconnect():
        while True:
            try:
                ws = WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                
                # Run forever with ping/pong to keep connection alive
                ws.run_forever(ping_interval=60, ping_timeout=10)
                
            except Exception as e:
                print(f"[CVD] Connection failed: {e}")
            
            # Wait before reconnecting
            print("[CVD] Reconnecting in 5 seconds...")
            time.sleep(5)
    
    # Start in separate thread to handle reconnections
    reconnect_thread = threading.Thread(target=run_with_reconnect, daemon=True)
    reconnect_thread.start()
    
    # Main thread periodically prints status
    try:
        while True:
            time.sleep(60)  # Print status every minute
            print(f"\n[CVD] Status at {datetime.now(TZ).strftime('%H:%M:%S GMT+3')}:")
            for symbol in SYMBOLS:
                cvd = cvd_values.get(symbol, 0)
                trades = trade_counts.get(symbol, 0)
                print(f"  {symbol}: {cvd:+15,.0f} USDT ({trades:,} trades)")
            print()
    except KeyboardInterrupt:
        print("\n[CVD] Shutting down...")
        save_cvd_data()
        print("[CVD] Final CVD data saved. Goodbye!")

if __name__ == '__main__':
    start_cvd_service()
