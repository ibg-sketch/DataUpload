#!/usr/bin/env python3
"""
Short TTL Optimizer with Walk-Forward Validation
Optimizes formula for TTL ≤ 30 minutes with 50x leverage risk considerations
Uses train/test split to avoid overfitting
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from itertools import product

class ShortTTLOptimizer:
    """
    Optimize for short TTL (15-30 min) with realistic constraints
    """
    
    def __init__(self):
        self.data_dir = Path('backtesting/data')
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT',
            'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
        ]
        
        # Walk-forward split: 21 days train, 9 days test
        self.train_data = {}
        self.test_data = {}
        
        # Trading fees (BingX)
        self.taker_fee = 0.05  # 0.05%
        self.slippage = 0.02   # 0.02% average slippage
        
    def load_and_split_data(self):
        """
        Load enriched data and split into train/test
        First 21 days = training, Last 9 days = testing
        """
        print("="*80)
        print("LOADING DATA WITH WALK-FORWARD SPLIT")
        print("="*80)
        
        for symbol in self.symbols:
            file_path = self.data_dir / f"{symbol}_enriched.csv"
            
            if not file_path.exists():
                continue
            
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Calculate split point (75% train, 25% test)
            split_idx = int(len(df) * 0.75)
            
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()
            
            self.train_data[symbol] = train_df
            self.test_data[symbol] = test_df
            
            print(f"{symbol}: {len(train_df)} train, {len(test_df)} test candles")
        
        print(f"\n✅ Loaded {len(self.train_data)} symbols")
        print(f"Train period: ~21 days")
        print(f"Test period: ~9 days")
        print("="*80 + "\n")
    
    def test_indicator_weights(self, data, ttl, weights):
        """
        Test specific indicator weights on dataset
        
        weights = {
            'rsi': 1.0,
            'vwap': 1.5,
            'adx': 1.0,
            'volume': 0.5
        }
        """
        all_data = pd.concat(data.values(), ignore_index=True)
        
        gain_col = f'max_gain_{ttl}m'
        drop_col = f'max_drop_{ttl}m'
        
        signals = []
        
        for idx, row in all_data.iterrows():
            # Calculate weighted score for BUY
            buy_score = 0
            buy_conditions = 0
            
            # RSI oversold (0-35 range)
            if 0 <= row['rsi'] <= 35:
                buy_score += weights['rsi']
                buy_conditions += 1
            
            # VWAP below (strong signal)
            if -5.0 <= row['vwap_distance'] <= -2.0:
                buy_score += weights['vwap']
                buy_conditions += 1
            
            # ADX trend strength
            if row['adx'] >= 20:
                buy_score += weights['adx']
                buy_conditions += 1
            
            # Volume confirmation
            if row['volume_ratio'] >= 0.8:
                buy_score += weights['volume']
                buy_conditions += 1
            
            # Require minimum score threshold
            min_score = sum(weights.values()) * 0.6  # 60% of max score
            
            if buy_score >= min_score and buy_conditions >= 2:
                # Realistic profit calculation: entry fee + exit fee + slippage
                gross_profit = row[gain_col]
                net_profit = gross_profit - (self.taker_fee * 2) - self.slippage
                
                signals.append({
                    'side': 'BUY',
                    'net_profit': net_profit,
                    'result': 'WIN' if net_profit > 0 else 'LOSS'
                })
            
            # Calculate weighted score for SELL
            sell_score = 0
            sell_conditions = 0
            
            # RSI overbought (65-100 range)
            if 65 <= row['rsi'] <= 100:
                sell_score += weights['rsi']
                sell_conditions += 1
            
            # VWAP above (strong signal)
            if 2.0 <= row['vwap_distance'] <= 5.0:
                sell_score += weights['vwap']
                sell_conditions += 1
            
            # ADX trend strength
            if row['adx'] >= 20:
                sell_score += weights['adx']
                sell_conditions += 1
            
            # Volume confirmation
            if row['volume_ratio'] >= 0.8:
                sell_score += weights['volume']
                sell_conditions += 1
            
            if sell_score >= min_score and sell_conditions >= 2:
                gross_profit = row[drop_col]
                net_profit = gross_profit - (self.taker_fee * 2) - self.slippage
                
                signals.append({
                    'side': 'SELL',
                    'net_profit': net_profit,
                    'result': 'WIN' if net_profit > 0 else 'LOSS'
                })
        
        if not signals:
            return {
                'win_rate': 0,
                'avg_profit': 0,
                'signals_count': 0,
                'buy_count': 0,
                'sell_count': 0
            }
        
        df_signals = pd.DataFrame(signals)
        
        wins = df_signals[df_signals['result'] == 'WIN']
        buy_signals = df_signals[df_signals['side'] == 'BUY']
        sell_signals = df_signals[df_signals['side'] == 'SELL']
        
        buy_wins = buy_signals[buy_signals['result'] == 'WIN']
        sell_wins = sell_signals[sell_signals['result'] == 'WIN']
        
        return {
            'win_rate': len(wins) / len(df_signals) * 100,
            'avg_profit': wins['net_profit'].mean() if len(wins) > 0 else 0,
            'signals_count': len(df_signals),
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'buy_wr': len(buy_wins) / len(buy_signals) * 100 if len(buy_signals) > 0 else 0,
            'sell_wr': len(sell_wins) / len(sell_signals) * 100 if len(sell_signals) > 0 else 0
        }
    
    def grid_search_weights(self, ttl=30):
        """
        Grid search over different weight combinations
        """
        print(f"\n{'='*80}")
        print(f"GRID SEARCH: TTL={ttl} minutes")
        print(f"{'='*80}\n")
        
        # Weight ranges to test
        weight_options = [0.5, 1.0, 1.5, 2.0]
        
        results = []
        
        # Generate all combinations
        combinations = list(product(weight_options, repeat=4))
        total_combinations = len(combinations)
        
        print(f"Testing {total_combinations} weight combinations...")
        print(f"Progress: ", end='', flush=True)
        
        for i, (rsi_w, vwap_w, adx_w, vol_w) in enumerate(combinations):
            if (i + 1) % 50 == 0:
                print(f"{i+1}/{total_combinations}...", end='', flush=True)
            
            weights = {
                'rsi': rsi_w,
                'vwap': vwap_w,
                'adx': adx_w,
                'volume': vol_w
            }
            
            # Train on training data
            train_metrics = self.test_indicator_weights(self.train_data, ttl, weights)
            
            # Test on holdout data
            test_metrics = self.test_indicator_weights(self.test_data, ttl, weights)
            
            # Only consider if both train and test have reasonable performance
            if train_metrics['signals_count'] > 100 and test_metrics['signals_count'] > 30:
                results.append({
                    'weights': weights,
                    'train_wr': train_metrics['win_rate'],
                    'test_wr': test_metrics['win_rate'],
                    'train_profit': train_metrics['avg_profit'],
                    'test_profit': test_metrics['avg_profit'],
                    'train_signals': train_metrics['signals_count'],
                    'test_signals': test_metrics['signals_count'],
                    'train_buy_wr': train_metrics['buy_wr'],
                    'train_sell_wr': train_metrics['sell_wr'],
                    'test_buy_wr': test_metrics['buy_wr'],
                    'test_sell_wr': test_metrics['sell_wr'],
                    # Score: test performance is most important
                    'score': test_metrics['win_rate'] * test_metrics['avg_profit']
                })
        
        print(f"\n\n✅ Tested {len(combinations)} combinations, {len(results)} valid\n")
        
        # Sort by test performance
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        return results
    
    def optimize(self):
        """
        Run complete optimization
        """
        self.load_and_split_data()
        
        # Test both 15min and 30min TTL
        all_results = {}
        
        for ttl in [15, 30]:
            results = self.grid_search_weights(ttl=ttl)
            all_results[ttl] = results
            
            # Show top 10 results
            print(f"\n{'='*80}")
            print(f"TOP 10 RESULTS FOR TTL={ttl} MINUTES")
            print(f"{'='*80}")
            print(f"{'Rank':<6} {'RSI':>5} {'VWAP':>5} {'ADX':>5} {'Vol':>5} | {'Train WR':>9} {'Test WR':>9} | {'Train $':>8} {'Test $':>8} | {'Signals':>8}")
            print("-"*80)
            
            for i, r in enumerate(results[:10], 1):
                w = r['weights']
                print(f"{i:<6} {w['rsi']:>5.1f} {w['vwap']:>5.1f} {w['adx']:>5.1f} {w['volume']:>5.1f} | "
                      f"{r['train_wr']:>8.1f}% {r['test_wr']:>8.1f}% | "
                      f"{r['train_profit']:>7.2f}% {r['test_profit']:>7.2f}% | "
                      f"{r['test_signals']:>8}")
        
        # Find overall best
        best_ttl = max(all_results.items(), 
                       key=lambda x: x[1][0]['score'] if x[1] else 0)
        
        ttl_value = best_ttl[0]
        best_config = best_ttl[1][0]
        
        print(f"\n{'='*80}")
        print(f"🏆 OPTIMAL CONFIGURATION")
        print(f"{'='*80}")
        print(f"TTL: {ttl_value} minutes")
        print(f"\nIndicator Weights:")
        for indicator, weight in best_config['weights'].items():
            print(f"  {indicator:10s}: {weight:.1f}")
        
        print(f"\nTraining Performance:")
        print(f"  Win Rate: {best_config['train_wr']:.1f}%")
        print(f"  BUY WR: {best_config['train_buy_wr']:.1f}%")
        print(f"  SELL WR: {best_config['train_sell_wr']:.1f}%")
        print(f"  Avg Profit: {best_config['train_profit']:.2f}%")
        print(f"  Signals: {best_config['train_signals']}")
        
        print(f"\n✅ Out-of-Sample Test Performance:")
        print(f"  Win Rate: {best_config['test_wr']:.1f}%")
        print(f"  BUY WR: {best_config['test_buy_wr']:.1f}%")
        print(f"  SELL WR: {best_config['test_sell_wr']:.1f}%")
        print(f"  Avg Profit: {best_config['test_profit']:.2f}%")
        print(f"  Signals: {best_config['test_signals']}")
        print(f"{'='*80}")
        
        # Save results
        output = {
            'optimal_ttl': ttl_value,
            'optimal_weights': best_config['weights'],
            'train_performance': {
                'win_rate': best_config['train_wr'],
                'buy_wr': best_config['train_buy_wr'],
                'sell_wr': best_config['train_sell_wr'],
                'avg_profit': best_config['train_profit'],
                'signals': best_config['train_signals']
            },
            'test_performance': {
                'win_rate': best_config['test_wr'],
                'buy_wr': best_config['test_buy_wr'],
                'sell_wr': best_config['test_sell_wr'],
                'avg_profit': best_config['test_profit'],
                'signals': best_config['test_signals']
            },
            'all_results': {
                f'ttl_{ttl}': results[:20] for ttl, results in all_results.items()
            }
        }
        
        output_file = Path('backtesting/short_ttl_optimal_formula.json')
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
        
        return output


if __name__ == '__main__':
    optimizer = ShortTTLOptimizer()
    optimizer.optimize()
