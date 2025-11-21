#!/usr/bin/env python3
"""
Formula Optimizer
Tests different weight combinations to find the best formula
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
import yaml
from datetime import datetime, timedelta

class FormulaOptimizer:
    def __init__(self):
        # Load current config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = list(self.config.get('coins', {}).keys())
        
        # Load processed data
        self.data = {}
        self.load_all_data()
    
    def load_all_data(self):
        """Load all processed CSV files"""
        data_dir = Path('backtesting/data')
        
        for symbol in self.symbols:
            filename = data_dir / f"{symbol}_processed.csv"
            
            if filename.exists():
                df = pd.read_csv(filename)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                self.data[symbol] = df
                print(f"✅ Loaded {symbol}: {len(df)} candles")
            else:
                print(f"⚠️ Missing {filename}")
    
    def calculate_score(self, row, weights, side):
        """
        Calculate signal score based on weights
        Simplified version of main bot logic
        """
        score = 0
        
        # VWAP contribution
        vwap_dist = abs(row['vwap_distance'])
        if side == 'BUY' and row['close'] < row['vwap']:
            score += weights['vwap'] * min(vwap_dist / 2.0, 1.0)
        elif side == 'SELL' and row['close'] > row['vwap']:
            score += weights['vwap'] * min(vwap_dist / 2.0, 1.0)
        
        # RSI contribution
        rsi = row['rsi']
        if side == 'BUY' and rsi < 45:
            score += weights['rsi'] * ((45 - rsi) / 15)
        elif side == 'SELL' and rsi > 55:
            score += weights['rsi'] * ((rsi - 55) / 15)
        
        # EMA contribution
        if row['ema_trend'] == 'bullish' and side == 'BUY':
            score += weights['ema']
        elif row['ema_trend'] == 'bearish' and side == 'SELL':
            score += weights['ema']
        
        # ADX contribution (trend strength)
        if row['adx'] > 25:
            score += weights['adx'] * (row['adx'] / 50)
        
        # Volume contribution
        if row['volume_spike']:
            score += weights['volume']
        
        return score
    
    def check_signal_outcome(self, df, idx, side, ttl_minutes):
        """
        Check if signal would be WIN or LOSS
        """
        entry_price = df.loc[idx, 'close']
        entry_time = df.loc[idx, 'timestamp']
        
        # Calculate target zone (simplified)
        if side == 'BUY':
            target_min = entry_price * 1.003  # +0.3%
            target_max = entry_price * 1.008  # +0.8%
        else:  # SELL
            target_min = entry_price * 0.992  # -0.8%
            target_max = entry_price * 0.997  # -0.3%
        
        # Look forward in time
        future_df = df[(df['timestamp'] > entry_time) & 
                       (df['timestamp'] <= entry_time + timedelta(minutes=ttl_minutes))]
        
        if len(future_df) == 0:
            return 'INCOMPLETE', 0
        
        # Check if target reached
        if side == 'BUY':
            if future_df['high'].max() >= target_min:
                profit = ((target_min - entry_price) / entry_price) * 100
                return 'WIN', profit
        else:  # SELL
            if future_df['low'].min() <= target_max:
                profit = ((entry_price - target_max) / entry_price) * 100
                return 'WIN', profit
        
        # TTL expired
        final_price = future_df.iloc[-1]['close']
        
        if side == 'BUY':
            profit = ((final_price - entry_price) / entry_price) * 100
        else:
            profit = ((entry_price - final_price) / entry_price) * 100
        
        result = 'WIN' if profit > 0 else 'LOSS'
        
        return result, profit
    
    def test_formula(self, weights, min_score=2.0, ttl_minutes=30):
        """
        Test a formula (weight combination) on all data
        """
        results = []
        
        for symbol, df in self.data.items():
            # Test every 50th candle to speed up (sample)
            for idx in range(50, len(df) - 100, 50):  # Skip first/last 100 candles
                row = df.iloc[idx]
                
                # Test BUY signal
                buy_score = self.calculate_score(row, weights, 'BUY')
                if buy_score >= min_score:
                    result, profit = self.check_signal_outcome(df, idx, 'BUY', ttl_minutes)
                    if result != 'INCOMPLETE':
                        results.append({
                            'symbol': symbol,
                            'side': 'BUY',
                            'score': buy_score,
                            'result': result,
                            'profit': profit
                        })
                
                # Test SELL signal
                sell_score = self.calculate_score(row, weights, 'SELL')
                if sell_score >= min_score:
                    result, profit = self.check_signal_outcome(df, idx, 'SELL', ttl_minutes)
                    if result != 'INCOMPLETE':
                        results.append({
                            'symbol': symbol,
                            'side': 'SELL',
                            'score': sell_score,
                            'result': result,
                            'profit': profit
                        })
        
        # Calculate metrics
        if not results:
            return {
                'win_rate': 0,
                'total_signals': 0,
                'avg_profit': 0,
                'total_profit': 0
            }
        
        wins = sum(1 for r in results if r['result'] == 'WIN')
        total = len(results)
        win_rate = (wins / total) * 100 if total > 0 else 0
        avg_profit = np.mean([r['profit'] for r in results])
        total_profit = sum([r['profit'] for r in results])
        
        return {
            'win_rate': win_rate,
            'total_signals': total,
            'avg_profit': avg_profit,
            'total_profit': total_profit,
            'results': results
        }
    
    def optimize(self):
        """
        Run optimization to find best weights
        """
        print("="*80)
        print("🔬 FORMULA OPTIMIZATION")
        print("="*80)
        
        # Define weight ranges to test
        weight_options = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        
        # TTL options
        ttl_options = [20, 25, 30, 35, 40]
        
        # Min score options
        min_score_options = [1.5, 2.0, 2.5, 3.0]
        
        best_result = None
        best_weights = None
        best_params = None
        
        total_tests = len(weight_options) ** 5 * len(ttl_options) * len(min_score_options)
        test_count = 0
        
        print(f"\nTesting {total_tests} combinations...")
        print("This will take some time...\n")
        
        # Grid search over weight combinations
        for vwap_w in weight_options:
            for rsi_w in weight_options:
                for ema_w in weight_options:
                    for adx_w in weight_options:
                        for vol_w in weight_options:
                            weights = {
                                'vwap': vwap_w,
                                'rsi': rsi_w,
                                'ema': ema_w,
                                'adx': adx_w,
                                'volume': vol_w
                            }
                            
                            # Test different TTL and min_score
                            for ttl in ttl_options:
                                for min_score in min_score_options:
                                    test_count += 1
                                    
                                    result = self.test_formula(weights, min_score, ttl)
                                    
                                    # Print progress every 100 tests
                                    if test_count % 100 == 0:
                                        print(f"Progress: {test_count}/{total_tests} ({test_count/total_tests*100:.1f}%)")
                                        if best_result:
                                            print(f"  Best so far: WR={best_result['win_rate']:.1f}% ({best_result['total_signals']} signals)")
                                    
                                    # Update best if this is better
                                    if result['total_signals'] >= 50:  # Minimum signal count
                                        if best_result is None or result['win_rate'] > best_result['win_rate']:
                                            best_result = result
                                            best_weights = weights.copy()
                                            best_params = {'ttl': ttl, 'min_score': min_score}
        
        # Print results
        print("\n" + "="*80)
        print("✅ OPTIMIZATION COMPLETE")
        print("="*80)
        
        if best_result:
            print(f"\n🏆 BEST FORMULA FOUND:")
            print(f"\nWeights:")
            for name, value in best_weights.items():
                print(f"  {name:10s}: {value:.1f}")
            
            print(f"\nParameters:")
            print(f"  Min Score: {best_params['min_score']:.1f}")
            print(f"  TTL:       {best_params['ttl']} minutes")
            
            print(f"\nPerformance:")
            print(f"  Win Rate:      {best_result['win_rate']:.1f}%")
            print(f"  Total Signals: {best_result['total_signals']}")
            print(f"  Avg Profit:    {best_result['avg_profit']:+.3f}%")
            print(f"  Total Profit:  {best_result['total_profit']:+.2f}%")
            
            # Save best weights to file
            output = {
                'weights': best_weights,
                'parameters': best_params,
                'performance': {
                    'win_rate': best_result['win_rate'],
                    'total_signals': best_result['total_signals'],
                    'avg_profit': best_result['avg_profit'],
                    'total_profit': best_result['total_profit']
                },
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            import json
            with open('backtesting/best_formula.json', 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✅ Saved to backtesting/best_formula.json")
        else:
            print("\n❌ No valid formula found")
        
        return best_weights, best_params, best_result

if __name__ == '__main__':
    optimizer = FormulaOptimizer()
    optimizer.optimize()
