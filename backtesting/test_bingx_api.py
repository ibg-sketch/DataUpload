#!/usr/bin/env python3
"""Test BingX API response"""

import requests
import json
from datetime import datetime, timedelta

# Test parameters
symbol = "BTC-USDT"
interval = "5m"

# Last 6 hours
end_dt = datetime.now()
start_dt = end_dt - timedelta(hours=6)

start_ms = int(start_dt.timestamp() * 1000)
end_ms = int(end_dt.timestamp() * 1000)

params = {
    'symbol': symbol,
    'interval': interval,
    'startTime': start_ms,
    'endTime': end_ms,
    'limit': 50
}

print("="*80)
print("🔍 TESTING BINGX API")
print("="*80)
print(f"Symbol: {symbol}")
print(f"Interval: {interval}")
print(f"Start: {start_dt}")
print(f"End: {end_dt}")
print(f"\nAPI Params:")
print(json.dumps(params, indent=2))
print("="*80)

try:
    response = requests.get(
        "https://open-api.bingx.com/openApi/swap/v2/quote/klines",
        params=params,
        timeout=10
    )
    
    response.raise_for_status()
    result = response.json()
    
    print(f"\n✅ Response received")
    print(f"Code: {result.get('code')}")
    print(f"Message: {result.get('msg')}")
    
    data = result.get('data', [])
    print(f"Data records: {len(data)}")
    
    if data:
        print(f"\n📋 First 3 records (raw):")
        for i, record in enumerate(data[:3]):
            print(f"\nRecord {i+1}:")
            print(f"  Type: {type(record)}")
            print(f"  Length: {len(record) if isinstance(record, (list, tuple)) else 'N/A'}")
            print(f"  Content: {record}")
            
            if isinstance(record, (list, tuple)) and len(record) >= 12:
                print(f"\n  Parsed:")
                print(f"    [0] Timestamp: {record[0]} (type: {type(record[0])})")
                print(f"    [1] Open: {record[1]}")
                print(f"    [2] High: {record[2]}")
                print(f"    [3] Low: {record[3]}")
                print(f"    [4] Close: {record[4]}")
                print(f"    [5] Volume: {record[5]}")
                print(f"    [6] Close time: {record[6]}")
                print(f"    [7] Quote volume: {record[7]}")
        
        # Try converting timestamp
        first_record = data[0]
        if isinstance(first_record, (list, tuple)) and len(first_record) > 0:
            timestamp = first_record[0]
            print(f"\n🕐 Timestamp conversion test:")
            print(f"  Raw: {timestamp}")
            print(f"  Type: {type(timestamp)}")
            
            try:
                import pandas as pd
                ts_converted = pd.to_datetime(int(timestamp), unit='ms')
                print(f"  Converted: {ts_converted}")
            except Exception as e:
                print(f"  ❌ Conversion failed: {e}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
