#!/usr/bin/env python3
"""
Download historical aggTrades data from Binance for missing dates
"""
import requests
import pandas as pd
import zipfile
import io
from datetime import datetime, timedelta
import time
import os

# Symbols to download
SYMBOLS = [
    'ADAUSDT', 'AVAXUSDT', 'BNBUSDT', 'BTCUSDT', 
    'DOGEUSDT', 'ETHUSDT', 'HYPEUSDT', 'LINKUSDT', 
    'SOLUSDT', 'TRXUSDT', 'XRPUSDT'
]

# Missing dates (05-12 Nov, 15-17 Nov)
DATES = [
    '2025-11-05', '2025-11-06', '2025-11-07', '2025-11-08',
    '2025-11-09', '2025-11-10', '2025-11-11', '2025-11-12',
    '2025-11-15', '2025-11-16', '2025-11-17'
]

OUTPUT_DIR = 'data/tick_data'

def download_aggtrades(symbol, date):
    """Download aggTrades from Binance data repository"""
    
    # Binance historical data URL format
    # https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-11-05.zip
    
    url = f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{symbol}-aggTrades-{date}.zip"
    
    print(f"📥 Downloading {symbol} {date}...")
    
    try:
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            # Save ZIP file
            zip_path = f"{OUTPUT_DIR}/{symbol}-aggTrades-{date}.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            # Extract CSV
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_name = f"{symbol}-aggTrades-{date}.csv"
                z.extractall(OUTPUT_DIR)
            
            csv_path = f"{OUTPUT_DIR}/{csv_name}"
            
            # Check file size
            csv_size = os.path.getsize(csv_path) / (1024 * 1024)  # MB
            zip_size = os.path.getsize(zip_path) / (1024 * 1024)  # MB
            
            print(f"   ✅ Success! CSV: {csv_size:.1f}MB, ZIP: {zip_size:.1f}MB")
            return True
            
        elif response.status_code == 404:
            print(f"   ⚠️  Not found (404) - data may not exist for this date")
            return False
        else:
            print(f"   ❌ Error {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def main():
    print("=" * 80)
    print("DOWNLOAD HISTORICAL AGGTRADES FROM BINANCE")
    print("=" * 80)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"\n📊 Symbols: {len(SYMBOLS)}")
    print(f"📅 Dates: {len(DATES)}")
    print(f"📁 Output: {OUTPUT_DIR}")
    print(f"🔢 Total downloads: {len(SYMBOLS) * len(DATES)}")
    
    # Track progress
    total = len(SYMBOLS) * len(DATES)
    completed = 0
    successful = 0
    failed = 0
    not_found = 0
    
    print("\n" + "=" * 80)
    print("STARTING DOWNLOADS...")
    print("=" * 80 + "\n")
    
    start_time = time.time()
    
    for date in DATES:
        print(f"\n📅 DATE: {date}")
        print("-" * 80)
        
        for symbol in SYMBOLS:
            # Check if already exists
            csv_path = f"{OUTPUT_DIR}/{symbol}-aggTrades-{date}.csv"
            zip_path = f"{OUTPUT_DIR}/{symbol}-aggTrades-{date}.zip"
            
            if os.path.exists(csv_path) and os.path.exists(zip_path):
                csv_size = os.path.getsize(csv_path) / (1024 * 1024)
                print(f"⏭️  {symbol} {date} - Already exists ({csv_size:.1f}MB), skipping")
                completed += 1
                successful += 1
                continue
            
            # Download
            result = download_aggtrades(symbol, date)
            
            completed += 1
            
            if result:
                successful += 1
            elif result is False:
                not_found += 1
            else:
                failed += 1
            
            # Progress
            progress = (completed / total) * 100
            print(f"   Progress: {completed}/{total} ({progress:.1f}%)")
            
            # Rate limit (be nice to Binance)
            time.sleep(0.5)
    
    elapsed = time.time() - start_time
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 DOWNLOAD SUMMARY")
    print("=" * 80)
    
    print(f"\n⏱️  Total time: {elapsed:.1f}s")
    print(f"✅ Successful: {successful}")
    print(f"⚠️  Not found: {not_found}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {completed}/{total}")
    
    # Check total size
    total_size = 0
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith('.csv'):
            total_size += os.path.getsize(f"{OUTPUT_DIR}/{filename}")
    
    total_size_gb = total_size / (1024 * 1024 * 1024)
    print(f"\n💾 Total data downloaded: {total_size_gb:.2f} GB")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
