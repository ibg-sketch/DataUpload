#!/usr/bin/env python3
"""
Binance Futures Liquidation Service
Tracks real-time liquidations via WebSocket forceOrder stream
Stores aggregated liquidation data for the signal bot
"""

from websocket._app import WebSocketApp
from websocket._abnf import ABNF
import json
import time
from datetime import datetime
from pathlib import Path
import pytz

# Timezone configuration - GMT+3
TZ = pytz.timezone('Etc/GMT-3')

# Configuration
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT']
OUTPUT_FILE = 'liquidation_data.json'
# RESET_INTERVAL removed - now storing full history without reset
WEBSOCKET_URL = 'wss://fstream.binance.com/ws/!forceOrder@arr'

# Global state
liquidation_data = {symbol: {'long_count': 0, 'short_count': 0, 'long_usd': 0.0, 'short_usd': 0.0} for symbol in SYMBOLS}
message_count = 0

def save_data():
    """Save liquidation data to JSON file"""
    data = {
        'last_update': time.time(),
        'timestamp': datetime.now(TZ).isoformat(),
        'liquidations': liquidation_data
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Reset function removed - liquidation data now accumulates indefinitely for full history

def on_message(ws, message):
    """Process incoming liquidation messages"""
    global message_count
    
    try:
        data = json.loads(message)
        
        # Check if it's a liquidation order
        if 'o' not in data:
            return
        
        order = data['o']
        symbol = order['s']
        
        # Only track our symbols
        if symbol not in SYMBOLS:
            return
        
        side = order['S']  # BUY = shorts liquidated, SELL = longs liquidated
        quantity = float(order['q'])
        avg_price = float(order['ap'])
        total_usd = quantity * avg_price
        
        # Update counters
        if side == 'SELL':
            # Long position liquidated (price went down)
            liquidation_data[symbol]['long_count'] += 1
            liquidation_data[symbol]['long_usd'] += total_usd
        elif side == 'BUY':
            # Short position liquidated (price went up)
            liquidation_data[symbol]['short_count'] += 1
            liquidation_data[symbol]['short_usd'] += total_usd
        
        message_count += 1
        
        # Save data after every liquidation for real-time updates
        save_data()
        
        # Print summary
        liq_type = "Long" if side == 'SELL' else "Short"
        print(f"[{symbol}] {liq_type} liquidation: ${total_usd:,.2f} at ${avg_price:,.2f}")
            
    except Exception as e:
        print(f"[ERR] Error processing message: {e}")

def on_error(ws, error):
    """Handle WebSocket errors"""
    print(f"[ERR] WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket close"""
    print(f"[LIQ] WebSocket connection closed")
    save_data()

def on_open(ws):
    """Handle WebSocket open"""
    print("=" * 70)
    print("LIQUIDATION SERVICE - Binance Futures forceOrder Stream")
    print("=" * 70)
    print(f"Started: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S GMT+3')}")
    print(f"Data source: Binance Futures (Public WebSocket)")
    print(f"Stream: All market liquidations (!forceOrder@arr)")
    print(f"Authentication: None required (public market data)")
    print("=" * 70)
    
    # Load existing data if available
    if Path(OUTPUT_FILE).exists():
        try:
            with open(OUTPUT_FILE, 'r') as f:
                saved = json.load(f)
                global liquidation_data
                liquidation_data = saved.get('liquidations', liquidation_data)
                print(f"[LIQ] Loaded existing liquidation data from {OUTPUT_FILE}")
                print(f"[LIQ] Tracking {len(SYMBOLS)} symbols: {', '.join(SYMBOLS)}")
                
                # Show current counts
                for symbol in SYMBOLS:
                    liq = liquidation_data[symbol]
                    print(f"  {symbol}: Long {liq['long_count']} (${liq['long_usd']:,.0f}) | Short {liq['short_count']} (${liq['short_usd']:,.0f})")
        except Exception as e:
            print(f"[WARN] Could not load existing data: {e}")
    
    print(f"[LIQ] Storing full history (no automatic reset)")
    print(f"[LIQ] Data saved to: {OUTPUT_FILE}")
    print("-" * 70)
    print("[LIQ] ✅ Connected to Binance liquidation stream")
    print("[LIQ] Monitoring for liquidations...")
    print("-" * 70)

def on_ping(ws, message):
    """Handle ping from server"""
    ws.send(message, ABNF.OPCODE_PONG)

def main():
    """Main function to start the liquidation service"""
    print("\n[LIQ] Starting Binance Futures Liquidation Service...")
    
    # Create WebSocket connection
    ws = WebSocketApp(
        WEBSOCKET_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
        on_ping=on_ping
    )
    
    # Run forever with auto-reconnect
    while True:
        try:
            ws.run_forever(ping_interval=60, ping_timeout=10)
            print("[LIQ] Connection lost. Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[LIQ] Shutting down liquidation service...")
            save_data()
            break
        except Exception as e:
            print(f"[ERR] Unexpected error: {e}")
            print("[LIQ] Reconnecting in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
