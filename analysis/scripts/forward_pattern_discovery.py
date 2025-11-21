#!/usr/bin/env python3
"""
Forward-Looking Pattern Discovery
Find indicator combinations that predict >0.5% price movements within 30min
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import requests
import os
from itertools import combinations

class ForwardPatternDiscovery:
    def __init__(self):
        self.symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 
                       'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT']
        self.api_key = os.getenv('COINALYZE_API_KEY')
        self.price_data = {}
        self.labeled_data = None
        
    def fetch_ohlcv_binance(self, symbol, days=7):
        """Fetch OHLCV data from Binance Futures API"""
        print(f"📥 Fetching {days} days of 5m data for {symbol}...")
        
        url = "https://fapi.binance.com/fapi/v1/klines"
        
        # Calculate timestamps (milliseconds)
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        all_klines = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': symbol,
                'interval': '5m',
                'startTime': current_start,
                'endTime': end_time,
                'limit': 1500  # Max per request
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                klines = response.json()
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # Update start time to last candle + 1
                current_start = klines[-1][0] + 300000  # +5min in ms
                
                # Rate limit
                import time
                time.sleep(0.2)
                
            except Exception as e:
                print(f"❌ Error fetching {symbol}: {e}")
                break
        
        if not all_klines:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(all_klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convert types
        df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df = df.sort_values('timestamp')
        
        print(f"✅ {symbol}: {len(df)} candles")
        return df
    
    def load_all_price_data(self, days=7):
        """Load OHLCV for all symbols"""
        print("="*80)
        print(f"LOADING {days} DAYS OF PRICE DATA")
        print("="*80)
        
        for symbol in self.symbols:
            df = self.fetch_ohlcv_binance(symbol, days)
            if df is not None:
                self.price_data[symbol] = df
        
        print(f"\n✅ Loaded data for {len(self.price_data)} symbols")
    
    def label_opportunities(self):
        """
        Label each candle with forward-looking outcome:
        - BUY: price goes up >0.5% within 30min, no >0.5% drawdown
        - SELL: price goes down >0.5% within 30min, no >0.5% drawdown
        """
        print("\n" + "="*80)
        print("LABELING PRICE MOVEMENT OPPORTUNITIES")
        print("="*80)
        
        all_labeled = []
        
        for symbol in self.price_data.keys():
            df = self.price_data[symbol].copy()
            
            # Calculate forward-looking outcomes
            df['buy_opportunity'] = False
            df['sell_opportunity'] = False
            df['buy_hit_minutes'] = np.nan
            df['sell_hit_minutes'] = np.nan
            
            for i in range(len(df) - 6):  # Need 6 candles ahead (30 min)
                current_price = df.iloc[i]['close']
                
                # Look ahead 6 candles (30 minutes)
                future_candles = df.iloc[i+1:i+7]
                
                if len(future_candles) < 6:
                    continue
                
                # BUY opportunity: price goes up >0.5%
                max_high = future_candles['high'].max()
                min_low = future_candles['low'].min()
                
                max_gain = (max_high - current_price) / current_price * 100
                max_drawdown = (current_price - min_low) / current_price * 100
                
                # BUY: gain >0.5% and drawdown <=0.5%
                if max_gain >= 0.5 and max_drawdown <= 0.5:
                    df.loc[df.index[i], 'buy_opportunity'] = True
                    # Find when 0.5% was hit
                    for j, row in enumerate(future_candles.itertuples()):
                        if (row.high - current_price) / current_price * 100 >= 0.5:
                            df.loc[df.index[i], 'buy_hit_minutes'] = (j + 1) * 5
                            break
                
                # SELL opportunity: price goes down >0.5%
                max_loss = (current_price - min_low) / current_price * 100
                max_bounce = (max_high - current_price) / current_price * 100
                
                # SELL: loss >0.5% and bounce <=0.5%
                if max_loss >= 0.5 and max_bounce <= 0.5:
                    df.loc[df.index[i], 'sell_opportunity'] = True
                    # Find when 0.5% was hit
                    for j, row in enumerate(future_candles.itertuples()):
                        if (current_price - row.low) / current_price * 100 >= 0.5:
                            df.loc[df.index[i], 'sell_hit_minutes'] = (j + 1) * 5
                            break
            
            # Add symbol column
            df['symbol'] = symbol
            all_labeled.append(df)
        
        self.labeled_data = pd.concat(all_labeled, ignore_index=True)
        
        # Statistics
        total_candles = len(self.labeled_data)
        buy_opps = self.labeled_data['buy_opportunity'].sum()
        sell_opps = self.labeled_data['sell_opportunity'].sum()
        
        print(f"\n📊 Total candles analyzed: {total_candles:,}")
        print(f"🟢 BUY opportunities: {buy_opps:,} ({buy_opps/total_candles*100:.1f}%)")
        print(f"🔴 SELL opportunities: {sell_opps:,} ({sell_opps/total_candles*100:.1f}%)")
        
        # Average time to hit
        avg_buy_time = self.labeled_data[self.labeled_data['buy_opportunity']]['buy_hit_minutes'].mean()
        avg_sell_time = self.labeled_data[self.labeled_data['sell_opportunity']]['sell_hit_minutes'].mean()
        
        print(f"⏱  Avg time to BUY target: {avg_buy_time:.1f} min")
        print(f"⏱  Avg time to SELL target: {avg_sell_time:.1f} min")
    
    def merge_with_indicators(self):
        """Merge price opportunities with indicator data from analysis_log.csv"""
        print("\n" + "="*80)
        print("MERGING WITH INDICATOR DATA")
        print("="*80)
        
        # Load analysis log
        analysis_df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
        analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'], errors='coerce')
        
        print(f"📊 Analysis log: {len(analysis_df)} entries")
        
        # Merge based on symbol and timestamp (within 1 minute)
        merged_data = []
        
        for idx, row in self.labeled_data.iterrows():
            symbol = row['symbol']
            timestamp = row['timestamp']
            
            # Find matching analysis entry
            time_diff = abs(analysis_df['timestamp'] - timestamp)
            matches = analysis_df[
                (analysis_df['symbol'] == symbol) &
                (time_diff < timedelta(minutes=1))
            ]
            
            if len(matches) > 0:
                # Get closest match
                closest = matches.loc[time_diff[matches.index].idxmin()]
                
                merged_row = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'close': row['close'],
                    'buy_opportunity': row['buy_opportunity'],
                    'sell_opportunity': row['sell_opportunity'],
                    'buy_hit_minutes': row['buy_hit_minutes'],
                    'sell_hit_minutes': row['sell_hit_minutes'],
                    # Indicators
                    'cvd': closest.get('cvd', 0),
                    'oi_change_pct': closest.get('oi_change_pct', 0),
                    'price_vs_vwap_pct': closest.get('price_vs_vwap_pct', 0),
                    'volume_spike': int(closest.get('volume_spike', 0)),
                    'liq_ratio': closest.get('liq_ratio', 0),
                    'rsi': closest.get('rsi', 50),
                    'ema_trend': closest.get('ema_trend', 'neutral'),
                    'funding_rate': closest.get('funding_rate', 0),
                }
                merged_data.append(merged_row)
        
        self.labeled_data = pd.DataFrame(merged_data)
        
        print(f"✅ Merged {len(self.labeled_data)} candles with indicators")
        
        # Updated statistics
        buy_opps = self.labeled_data['buy_opportunity'].sum()
        sell_opps = self.labeled_data['sell_opportunity'].sum()
        
        print(f"🟢 BUY opportunities with indicators: {buy_opps:,}")
        print(f"🔴 SELL opportunities with indicators: {sell_opps:,}")
    
    def find_best_patterns(self):
        """Find indicator combinations that predict opportunities"""
        print("\n" + "="*80)
        print("PATTERN DISCOVERY")
        print("="*80)
        
        # Test single indicators first
        print("\n📊 SINGLE INDICATOR ANALYSIS:")
        
        indicators = ['cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'liq_ratio', 'rsi']
        
        buy_patterns = []
        sell_patterns = []
        
        # BUY patterns
        print(f"\n{'='*80}")
        print("BUY OPPORTUNITY PREDICTORS")
        print(f"{'='*80}")
        print(f"{'Indicator':<20} {'Success Rate':<15} {'Signals':<10} {'Avg Time'}")
        print("-"*80)
        
        for indicator in indicators:
            # Test various thresholds
            for percentile in [10, 25, 50, 75, 90]:
                threshold = self.labeled_data[indicator].quantile(percentile / 100)
                
                for direction in ['above', 'below']:
                    if direction == 'above':
                        mask = self.labeled_data[indicator] > threshold
                    else:
                        mask = self.labeled_data[indicator] < threshold
                    
                    filtered = self.labeled_data[mask]
                    
                    if len(filtered) < 50:  # Need minimum samples
                        continue
                    
                    success_rate = filtered['buy_opportunity'].mean()
                    avg_time = filtered[filtered['buy_opportunity']]['buy_hit_minutes'].mean()
                    
                    if success_rate >= 0.10:  # At least 10% success rate
                        pattern = {
                            'indicator': indicator,
                            'threshold': threshold,
                            'direction': direction,
                            'success_rate': success_rate,
                            'signals': len(filtered),
                            'avg_time': avg_time
                        }
                        buy_patterns.append(pattern)
        
        # Sort and display top BUY patterns
        buy_patterns_sorted = sorted(buy_patterns, key=lambda x: x['success_rate'], reverse=True)
        
        for pattern in buy_patterns_sorted[:15]:
            print(f"{pattern['indicator']:<20} {pattern['success_rate']:<15.1%} "
                  f"{pattern['signals']:<10} {pattern['avg_time']:.1f} min")
        
        # SELL patterns
        print(f"\n{'='*80}")
        print("SELL OPPORTUNITY PREDICTORS")
        print(f"{'='*80}")
        print(f"{'Indicator':<20} {'Success Rate':<15} {'Signals':<10} {'Avg Time'}")
        print("-"*80)
        
        for indicator in indicators:
            for percentile in [10, 25, 50, 75, 90]:
                threshold = self.labeled_data[indicator].quantile(percentile / 100)
                
                for direction in ['above', 'below']:
                    if direction == 'above':
                        mask = self.labeled_data[indicator] > threshold
                    else:
                        mask = self.labeled_data[indicator] < threshold
                    
                    filtered = self.labeled_data[mask]
                    
                    if len(filtered) < 50:
                        continue
                    
                    success_rate = filtered['sell_opportunity'].mean()
                    avg_time = filtered[filtered['sell_opportunity']]['sell_hit_minutes'].mean()
                    
                    if success_rate >= 0.10:
                        pattern = {
                            'indicator': indicator,
                            'threshold': threshold,
                            'direction': direction,
                            'success_rate': success_rate,
                            'signals': len(filtered),
                            'avg_time': avg_time
                        }
                        sell_patterns.append(pattern)
        
        sell_patterns_sorted = sorted(sell_patterns, key=lambda x: x['success_rate'], reverse=True)
        
        for pattern in sell_patterns_sorted[:15]:
            print(f"{pattern['indicator']:<20} {pattern['success_rate']:<15.1%} "
                  f"{pattern['signals']:<10} {pattern['avg_time']:.1f} min")
        
        # Save results
        results = {
            'buy_patterns': buy_patterns_sorted[:20],
            'sell_patterns': sell_patterns_sorted[:20]
        }
        
        with open('forward_pattern_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to forward_pattern_results.json")
        
        return results

def main():
    analyzer = ForwardPatternDiscovery()
    
    # Step 1: Load price data
    analyzer.load_all_price_data(days=7)
    
    # Step 2: Label opportunities
    analyzer.label_opportunities()
    
    # Step 3: Merge with indicators
    analyzer.merge_with_indicators()
    
    # Step 4: Find patterns
    results = analyzer.find_best_patterns()
    
    print("\n" + "="*80)
    print("✅ FORWARD PATTERN DISCOVERY COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
