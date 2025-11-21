#!/usr/bin/env python3
"""
Indicator Calculator
Calculates all indicators on historical data (VWAP, RSI, EMA, etc)
"""

import pandas as pd
import numpy as np
from pathlib import Path

class IndicatorCalculator:
    def __init__(self):
        pass
    
    def calculate_vwap(self, df):
        """Calculate VWAP with quote volume"""
        # Typical price
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Cumulative volume-weighted price
        df['cum_vol_price'] = (df['typical_price'] * df['quote_volume']).cumsum()
        df['cum_vol'] = df['quote_volume'].cumsum()
        
        # VWAP
        df['vwap'] = df['cum_vol_price'] / df['cum_vol']
        
        # VWAP deviation
        df['vwap_distance'] = ((df['close'] - df['vwap']) / df['vwap'] * 100)
        
        return df
    
    def calculate_rsi(self, df, period=14):
        """Calculate RSI"""
        delta = df['close'].diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def calculate_ema(self, df, short_period=9, long_period=21):
        """Calculate EMA"""
        df['ema_short'] = df['close'].ewm(span=short_period, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=long_period, adjust=False).mean()
        
        # EMA trend
        df['ema_trend'] = np.where(df['ema_short'] > df['ema_long'], 'bullish', 'bearish')
        
        return df
    
    def calculate_adx(self, df, period=14):
        """Calculate ADX"""
        # True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        
        # Directional Movement
        df['up_move'] = df['high'] - df['high'].shift()
        df['down_move'] = df['low'].shift() - df['low']
        
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
        # Smoothed indicators
        df['atr'] = df['tr'].rolling(window=period).mean()
        df['plus_di'] = 100 * (df['plus_dm'].rolling(window=period).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].rolling(window=period).mean() / df['atr'])
        
        # ADX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].rolling(window=period).mean()
        
        return df
    
    def calculate_volume_change(self, df, lookback=20):
        """Calculate volume change percentage"""
        df['volume_ma'] = df['volume'].rolling(window=lookback).mean()
        df['volume_change'] = ((df['volume'] - df['volume_ma']) / df['volume_ma'] * 100)
        df['volume_spike'] = df['volume_change'] > 50  # 50% above average
        
        return df
    
    def calculate_all_indicators(self, df):
        """Calculate all indicators"""
        print(f"  Calculating indicators on {len(df)} candles...")
        
        # Make copy to avoid warnings
        df = df.copy()
        
        # Calculate all
        df = self.calculate_vwap(df)
        df = self.calculate_rsi(df)
        df = self.calculate_ema(df)
        df = self.calculate_adx(df)
        df = self.calculate_volume_change(df)
        
        # Drop NaN rows from indicators
        df = df.dropna()
        
        print(f"  ✅ {len(df)} candles with indicators")
        
        return df
    
    def process_all_files(self):
        """Process all downloaded CSV files"""
        data_dir = Path('backtesting/data')
        
        if not data_dir.exists():
            print("❌ No data directory found. Run data_downloader.py first.")
            return
        
        csv_files = list(data_dir.glob('*_5m.csv'))
        
        if not csv_files:
            print("⚠️ No 5m.csv files found in backtesting/data/")
            print("   Make sure data_downloader.py completed successfully.")
            return
        
        print(f"Found {len(csv_files)} files to process")
        
        for csv_file in csv_files:
            print(f"\n{'='*60}")
            print(f"Processing {csv_file.name}...")
            print(f"{'='*60}")
            
            # Load data
            df = pd.read_csv(csv_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Calculate indicators
            df = self.calculate_all_indicators(df)
            
            # Save processed data
            output_file = data_dir / csv_file.name.replace('_5m.csv', '_processed.csv')
            df.to_csv(output_file, index=False)
            
            print(f"✅ Saved to {output_file}")
        
        print(f"\n{'='*60}")
        print("✅ All files processed!")
        print(f"{'='*60}")

if __name__ == '__main__':
    calculator = IndicatorCalculator()
    calculator.process_all_files()
