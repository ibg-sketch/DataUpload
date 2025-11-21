#!/usr/bin/env python3
"""
Data Merger
Merges OHLCV, indicators, OI, liquidations, CVD, funding rate into single files
"""

import pandas as pd
from pathlib import Path

class DataMerger:
    def __init__(self):
        self.data_dir = Path('backtesting/data')
    
    def merge_symbol_data(self, symbol):
        """
        Merge all data sources for a symbol into one DataFrame
        """
        print(f"\n{'='*60}")
        print(f"Merging data for {symbol}...")
        print(f"{'='*60}")
        
        # Load base OHLCV with indicators
        base_file = self.data_dir / f"{symbol}_processed.csv"
        
        if not base_file.exists():
            print(f"  ⚠️ No processed data found for {symbol}")
            return None
        
        df = pd.read_csv(base_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"  ✅ Loaded {len(df)} candles with indicators")
        
        # Merge OI
        oi_file = self.data_dir / f"{symbol}_oi.csv"
        if oi_file.exists():
            oi_df = pd.read_csv(oi_file)
            oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'])
            
            # Round to 5-min buckets for merging
            oi_df['timestamp'] = oi_df['timestamp'].dt.floor('5min')
            df['timestamp_floor'] = df['timestamp'].dt.floor('5min')
            
            df = df.merge(oi_df, left_on='timestamp_floor', right_on='timestamp', 
                         how='left', suffixes=('', '_oi'))
            df = df.drop(columns=['timestamp_floor', 'timestamp_oi'])
            
            print(f"  ✅ Merged OI data")
        else:
            print(f"  ⚠️ No OI data found")
            df['oi'] = 0
            df['oi_change'] = 0
        
        # Merge Liquidations
        liq_file = self.data_dir / f"{symbol}_liquidations.csv"
        if liq_file.exists():
            liq_df = pd.read_csv(liq_file)
            liq_df['timestamp'] = pd.to_datetime(liq_df['timestamp'])
            liq_df['timestamp'] = liq_df['timestamp'].dt.floor('5min')
            df['timestamp_floor'] = df['timestamp'].dt.floor('5min')
            
            df = df.merge(liq_df, left_on='timestamp_floor', right_on='timestamp',
                         how='left', suffixes=('', '_liq'))
            df = df.drop(columns=['timestamp_floor', 'timestamp_liq'])
            
            print(f"  ✅ Merged liquidation data")
        else:
            print(f"  ⚠️ No liquidation data found")
            df['liq_long'] = 0
            df['liq_short'] = 0
        
        # Merge CVD
        cvd_file = self.data_dir / f"{symbol}_cvd.csv"
        if cvd_file.exists():
            cvd_df = pd.read_csv(cvd_file)
            cvd_df['timestamp'] = pd.to_datetime(cvd_df['timestamp'])
            cvd_df['timestamp'] = cvd_df['timestamp'].dt.floor('5min')
            df['timestamp_floor'] = df['timestamp'].dt.floor('5min')
            
            df = df.merge(cvd_df, left_on='timestamp_floor', right_on='timestamp',
                         how='left', suffixes=('', '_cvd'))
            df = df.drop(columns=['timestamp_floor', 'timestamp_cvd'])
            
            # Forward fill CVD (it's cumulative)
            df['cvd'] = df['cvd'].fillna(method='ffill')
            df['cvd_delta'] = df['cvd_delta'].fillna(0)
            
            print(f"  ✅ Merged CVD data")
        else:
            print(f"  ⚠️ No CVD data found")
            df['cvd'] = 0
            df['cvd_delta'] = 0
        
        # Merge Funding Rate
        funding_file = self.data_dir / f"{symbol}_funding.csv"
        if funding_file.exists():
            funding_df = pd.read_csv(funding_file)
            funding_df['timestamp'] = pd.to_datetime(funding_df['timestamp'])
            funding_df['timestamp'] = funding_df['timestamp'].dt.floor('5min')
            df['timestamp_floor'] = df['timestamp'].dt.floor('5min')
            
            df = df.merge(funding_df, left_on='timestamp_floor', right_on='timestamp',
                         how='left', suffixes=('', '_funding'))
            df = df.drop(columns=['timestamp_floor', 'timestamp_funding'])
            
            # Forward fill funding rate (updates every 8h)
            df['funding_rate'] = df['funding_rate'].fillna(method='ffill')
            
            print(f"  ✅ Merged funding rate data")
        else:
            print(f"  ⚠️ No funding rate data found")
            df['funding_rate'] = 0
        
        # Fill remaining NaN with 0
        df = df.fillna(0)
        
        # Save merged data
        output_file = self.data_dir / f"{symbol}_complete.csv"
        df.to_csv(output_file, index=False)
        
        print(f"\n  ✅ Saved complete data to {output_file}")
        print(f"  📊 Total columns: {len(df.columns)}")
        print(f"  📊 Total rows: {len(df)}")
        
        # Show columns
        print(f"\n  Columns included:")
        for col in df.columns:
            print(f"    - {col}")
        
        return df
    
    def merge_all_symbols(self):
        """
        Merge all symbols
        """
        print("="*80)
        print("DATA MERGER - Combining all data sources")
        print("="*80)
        
        import yaml
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        symbols = config.get('symbols', [])
        
        for symbol in symbols:
            self.merge_symbol_data(symbol)
        
        print(f"\n{'='*80}")
        print("✅ ALL DATA MERGED")
        print(f"{'='*80}")

if __name__ == '__main__':
    merger = DataMerger()
    merger.merge_all_symbols()
