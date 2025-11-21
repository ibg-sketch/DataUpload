#!/usr/bin/env python3
"""
Advanced Data Downloader
Downloads historical data for CVD, OI, Liquidations, Funding Rate
"""

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import yaml
import json
from pathlib import Path

class AdvancedDataDownloader:
    def __init__(self):
        self.coinalyze_key = os.getenv('COINALYZE_API_KEY')
        self.coinalyze_base = "https://api.coinalyze.net/v1"
        
        # Load config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = self.config.get('symbols', [])
        
    def download_oi_history(self, symbol, start_ts, end_ts):
        """
        Download Open Interest history from Coinalyze
        """
        base_symbol = symbol.replace('USDT', '')
        
        url = f"{self.coinalyze_base}/open-interest-history"
        params = {
            'api_key': self.coinalyze_key,
            'symbols': base_symbol,
            'interval': '5m',
            'from': int(start_ts),
            'to': int(end_ts),
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"  Error downloading OI for {symbol}: {response.status_code}")
                if response.status_code == 429:
                    print(f"  Rate limit hit, waiting 60s...")
                    time.sleep(60)
                return None
        except Exception as e:
            print(f"  Exception downloading OI: {e}")
            return None
    
    def download_liquidations_history(self, symbol, start_ts, end_ts):
        """
        Download Liquidations history from Coinalyze
        """
        base_symbol = symbol.replace('USDT', '')
        
        url = f"{self.coinalyze_base}/liquidation-history"
        params = {
            'api_key': self.coinalyze_key,
            'symbols': base_symbol,
            'interval': '5m',
            'from': int(start_ts),
            'to': int(end_ts),
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"  Error downloading liquidations for {symbol}: {response.status_code}")
                if response.status_code == 429:
                    print(f"  Rate limit hit, waiting 60s...")
                    time.sleep(60)
                return None
        except Exception as e:
            print(f"  Exception downloading liquidations: {e}")
            return None
    
    def download_funding_rate(self, symbol, start_ts, end_ts):
        """
        Download Funding Rate history from Coinalyze
        """
        base_symbol = symbol.replace('USDT', '')
        
        url = f"{self.coinalyze_base}/funding-rate-history"
        params = {
            'api_key': self.coinalyze_key,
            'symbols': base_symbol,
            'from': int(start_ts),
            'to': int(end_ts),
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"  Error downloading funding rate for {symbol}: {response.status_code}")
                if response.status_code == 429:
                    print(f"  Rate limit hit, waiting 60s...")
                    time.sleep(60)
                return None
        except Exception as e:
            print(f"  Exception downloading funding rate: {e}")
            return None
    
    def download_trades_for_cvd(self, symbol, start_time, end_time):
        """
        Download aggregated trades from Binance to calculate CVD
        We'll download trades and aggregate them into 5-minute buckets
        """
        url = "https://fapi.binance.com/fapi/v1/aggTrades"
        
        all_trades = []
        current_start = int(start_time * 1000)
        end_ms = int(end_time * 1000)
        
        print(f"  Downloading trades for CVD calculation...")
        
        while current_start < end_ms:
            params = {
                'symbol': symbol,
                'startTime': current_start,
                'endTime': end_ms,
                'limit': 1000
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    trades = response.json()
                    
                    if not trades:
                        break
                    
                    all_trades.extend(trades)
                    
                    # Update to last trade time
                    current_start = trades[-1]['T'] + 1
                    
                    print(f"    Downloaded {len(trades)} trades, total: {len(all_trades)}")
                    
                    time.sleep(0.2)  # Rate limit
                else:
                    print(f"  Error: {response.status_code}")
                    break
                    
            except Exception as e:
                print(f"  Exception: {e}")
                break
        
        return all_trades
    
    def calculate_cvd_from_trades(self, trades):
        """
        Calculate CVD from raw trades
        Aggregate into 5-minute buckets
        """
        if not trades:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['T'], unit='ms')
        df['price'] = df['p'].astype(float)
        df['qty'] = df['q'].astype(float)
        df['is_buyer_maker'] = df['m']  # True if buyer is maker (sell)
        
        # Calculate signed volume (buy = positive, sell = negative)
        df['signed_volume'] = df.apply(
            lambda row: row['qty'] if not row['is_buyer_maker'] else -row['qty'],
            axis=1
        )
        
        # Round timestamp to 5-minute buckets
        df['time_bucket'] = df['timestamp'].dt.floor('5min')
        
        # Aggregate by 5-minute buckets
        cvd_df = df.groupby('time_bucket').agg({
            'signed_volume': 'sum',  # CVD delta
            'qty': 'sum',  # Total volume
            'T': 'count'  # Trade count
        }).reset_index()
        
        cvd_df.columns = ['timestamp', 'cvd_delta', 'total_volume', 'trade_count']
        
        # Calculate cumulative CVD
        cvd_df['cvd'] = cvd_df['cvd_delta'].cumsum()
        
        return cvd_df
    
    def download_all_advanced_data(self, days=None, start_date=None):
        """
        Download all advanced data (OI, Liquidations, Funding, CVD)
        days: number of days back
        start_date: specific start date (overrides days) e.g., '2025-01-01'
        """
        end_time = datetime.now()
        
        if start_date:
            start_time = datetime.strptime(start_date, '%Y-%m-%d')
        elif days:
            start_time = end_time - timedelta(days=days)
        else:
            start_time = end_time - timedelta(days=30)
        
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        print(f"="*80)
        print(f"ADVANCED DATA DOWNLOAD")
        print(f"="*80)
        print(f"Period: {start_time} to {end_time}")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"="*80)
        
        os.makedirs('backtesting/data', exist_ok=True)
        
        for symbol in self.symbols:
            print(f"\n{'='*60}")
            print(f"📊 {symbol}")
            print(f"{'='*60}")
            
            # 1. Open Interest
            print(f"\n1️⃣ Downloading Open Interest...")
            oi_data = self.download_oi_history(symbol, start_ts, end_ts)
            
            if oi_data:
                # Parse and save
                oi_records = []
                for exchange, data_points in oi_data.items():
                    if isinstance(data_points, list):
                        for point in data_points:
                            oi_records.append({
                                'timestamp': pd.to_datetime(point['t'], unit='s'),
                                'oi': point.get('v', 0),
                                'exchange': exchange
                            })
                
                if oi_records:
                    oi_df = pd.DataFrame(oi_records)
                    # Aggregate by timestamp (sum across exchanges)
                    oi_df = oi_df.groupby('timestamp')['oi'].sum().reset_index()
                    # Calculate OI change
                    oi_df['oi_change'] = oi_df['oi'].diff()
                    
                    filename = f"backtesting/data/{symbol}_oi.csv"
                    oi_df.to_csv(filename, index=False)
                    print(f"  ✅ Saved {len(oi_df)} OI data points to {filename}")
                else:
                    print(f"  ⚠️ No OI data received")
            else:
                print(f"  ❌ Failed to download OI")
            
            time.sleep(2)  # Rate limit
            
            # 2. Liquidations
            print(f"\n2️⃣ Downloading Liquidations...")
            liq_data = self.download_liquidations_history(symbol, start_ts, end_ts)
            
            if liq_data:
                liq_records = []
                for exchange, data_points in liq_data.items():
                    if isinstance(data_points, list):
                        for point in data_points:
                            liq_records.append({
                                'timestamp': pd.to_datetime(point['t'], unit='s'),
                                'liq_long': point.get('l', 0),  # Long liquidations
                                'liq_short': point.get('s', 0),  # Short liquidations
                                'exchange': exchange
                            })
                
                if liq_records:
                    liq_df = pd.DataFrame(liq_records)
                    # Aggregate by timestamp
                    liq_df = liq_df.groupby('timestamp').agg({
                        'liq_long': 'sum',
                        'liq_short': 'sum'
                    }).reset_index()
                    
                    filename = f"backtesting/data/{symbol}_liquidations.csv"
                    liq_df.to_csv(filename, index=False)
                    print(f"  ✅ Saved {len(liq_df)} liquidation data points to {filename}")
                else:
                    print(f"  ⚠️ No liquidation data received")
            else:
                print(f"  ❌ Failed to download liquidations")
            
            time.sleep(2)  # Rate limit
            
            # 3. Funding Rate
            print(f"\n3️⃣ Downloading Funding Rate...")
            funding_data = self.download_funding_rate(symbol, start_ts, end_ts)
            
            if funding_data:
                funding_records = []
                for exchange, data_points in funding_data.items():
                    if isinstance(data_points, list):
                        for point in data_points:
                            funding_records.append({
                                'timestamp': pd.to_datetime(point['t'], unit='s'),
                                'funding_rate': point.get('v', 0),
                                'exchange': exchange
                            })
                
                if funding_records:
                    funding_df = pd.DataFrame(funding_records)
                    # Average across exchanges
                    funding_df = funding_df.groupby('timestamp')['funding_rate'].mean().reset_index()
                    
                    filename = f"backtesting/data/{symbol}_funding.csv"
                    funding_df.to_csv(filename, index=False)
                    print(f"  ✅ Saved {len(funding_df)} funding rate data points to {filename}")
                else:
                    print(f"  ⚠️ No funding data received")
            else:
                print(f"  ❌ Failed to download funding rate")
            
            time.sleep(2)  # Rate limit
            
            # 4. CVD (from trades)
            print(f"\n4️⃣ Calculating CVD from trades...")
            trades = self.download_trades_for_cvd(symbol, start_ts, end_ts)
            
            if trades:
                cvd_df = self.calculate_cvd_from_trades(trades)
                
                if len(cvd_df) > 0:
                    filename = f"backtesting/data/{symbol}_cvd.csv"
                    cvd_df.to_csv(filename, index=False)
                    print(f"  ✅ Saved {len(cvd_df)} CVD data points to {filename}")
                else:
                    print(f"  ⚠️ No CVD data calculated")
            else:
                print(f"  ❌ Failed to download trades for CVD")
            
            time.sleep(2)  # Rate limit between symbols
        
        print(f"\n{'='*80}")
        print("✅ ADVANCED DATA DOWNLOAD COMPLETE")
        print(f"{'='*80}")

if __name__ == '__main__':
    import sys
    
    downloader = AdvancedDataDownloader()
    
    # Check for start_date argument
    if len(sys.argv) > 1 and sys.argv[1].startswith('--start='):
        start_date = sys.argv[1].replace('--start=', '')
        print(f"Using custom start date: {start_date}")
        downloader.download_all_advanced_data(start_date=start_date)
    else:
        # Default: from January 1, 2025
        downloader.download_all_advanced_data(start_date='2025-01-01')
