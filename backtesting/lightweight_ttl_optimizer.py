#!/usr/bin/env python3
"""
Lightweight TTL & Formula Optimizer
Fast statistical approach to find optimal TTL and indicator weights
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

class LightweightOptimizer:
    """
    Efficient optimizer using statistical methods instead of heavy ML
    """
    
    def __init__(self):
        self.data_dir = Path('backtesting/data')
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT',
            'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
        ]
        self.all_data = None
        
    def load_enriched_data(self):
        """Load pre-enriched data"""
        print("Loading enriched data...")
        
        dfs = []
        for symbol in self.symbols:
            file_path = self.data_dir / f"{symbol}_enriched.csv"
            if file_path.exists():
                df = pd.read_csv(file_path)
                df['symbol'] = symbol
                dfs.append(df)
        
        self.all_data = pd.concat(dfs, ignore_index=True)
        print(f"✅ Loaded {len(self.all_data)} candles from {len(dfs)} symbols\n")
    
    def test_ttl_performance(self, ttl_minutes, profit_threshold=0.5):
        """
        Test a specific TTL value for win rate and profitability
        
        Args:
            ttl_minutes: TTL in minutes (15, 30, 60, 90, 120)
            profit_threshold: Minimum profit % to consider a win
        
        Returns:
            Dict with performance metrics
        """
        gain_col = f'max_gain_{ttl_minutes}m'
        drop_col = f'max_drop_{ttl_minutes}m'
        
        # Define profitable trades
        buy_wins = self.all_data[self.all_data[gain_col] > profit_threshold]
        sell_wins = self.all_data[self.all_data[drop_col] > profit_threshold]
        
        total_candles = len(self.all_data)
        
        # Calculate metrics
        buy_win_rate = len(buy_wins) / total_candles * 100
        sell_win_rate = len(sell_wins) / total_candles * 100
        
        buy_avg_profit = buy_wins[gain_col].mean() if len(buy_wins) > 0 else 0
        sell_avg_profit = sell_wins[drop_col].mean() if len(sell_wins) > 0 else 0
        
        return {
            'ttl': ttl_minutes,
            'buy_win_rate': buy_win_rate,
            'sell_win_rate': sell_win_rate,
            'buy_avg_profit': buy_avg_profit,
            'sell_avg_profit': sell_avg_profit,
            'buy_opportunity_count': len(buy_wins),
            'sell_opportunity_count': len(sell_wins)
        }
    
    def optimize_ttl(self, ttl_range=[15, 30, 60, 90, 120], thresholds=[0.3, 0.5, 0.7, 1.0]):
        """
        Test multiple TTL values and profit thresholds
        Find optimal combination
        """
        print("="*80)
        print("TTL OPTIMIZATION")
        print("="*80)
        
        results = []
        
        for threshold in thresholds:
            print(f"\n📊 Testing with profit threshold: {threshold}%")
            print("-"*80)
            print(f"{'TTL (min)':<12} {'BUY WR%':>10} {'SELL WR%':>10} {'BUY Avg':>10} {'SELL Avg':>10} {'BUY Opps':>10} {'SELL Opps':>10}")
            print("-"*80)
            
            for ttl in ttl_range:
                metrics = self.test_ttl_performance(ttl, threshold)
                results.append({**metrics, 'threshold': threshold})
                
                print(f"{ttl:<12} {metrics['buy_win_rate']:>9.1f}% {metrics['sell_win_rate']:>9.1f}% "
                      f"{metrics['buy_avg_profit']:>9.2f}% {metrics['sell_avg_profit']:>9.2f}% "
                      f"{metrics['buy_opportunity_count']:>10} {metrics['sell_opportunity_count']:>10}")
        
        # Find optimal TTL (maximize average profit while maintaining reasonable win rate)
        results_df = pd.DataFrame(results)
        
        # Score = avg_profit * win_rate (for both BUY and SELL)
        results_df['buy_score'] = results_df['buy_avg_profit'] * results_df['buy_win_rate']
        results_df['sell_score'] = results_df['sell_avg_profit'] * results_df['sell_win_rate']
        results_df['total_score'] = results_df['buy_score'] + results_df['sell_score']
        
        best = results_df.loc[results_df['total_score'].idxmax()]
        
        print("\n" + "="*80)
        print("🏆 OPTIMAL CONFIGURATION:")
        print("="*80)
        print(f"TTL: {best['ttl']} minutes")
        print(f"Profit Threshold: {best['threshold']}%")
        print(f"BUY Win Rate: {best['buy_win_rate']:.1f}%")
        print(f"SELL Win Rate: {best['sell_win_rate']:.1f}%")
        print(f"BUY Avg Profit: {best['buy_avg_profit']:.2f}%")
        print(f"SELL Avg Profit: {best['sell_avg_profit']:.2f}%")
        print(f"BUY Opportunities: {best['buy_opportunity_count']:.0f}")
        print(f"SELL Opportunities: {best['sell_opportunity_count']:.0f}")
        print("="*80)
        
        return results_df, best
    
    def analyze_indicator_thresholds(self, ttl=60):
        """
        Find optimal thresholds for each indicator
        Based on correlation with profitable trades
        """
        print("\n" + "="*80)
        print(f"INDICATOR THRESHOLD OPTIMIZATION (TTL={ttl}m)")
        print("="*80)
        
        gain_col = f'max_gain_{ttl}m'
        drop_col = f'max_drop_{ttl}m'
        
        # Test different thresholds for each indicator
        indicators = {
            'rsi': {
                'buy_ranges': [(0, 30), (0, 35), (0, 40), (0, 45)],
                'sell_ranges': [(70, 100), (65, 100), (60, 100), (55, 100)]
            },
            'vwap_distance': {
                'buy_ranges': [(-5, -2), (-4, -1), (-3, -0.5), (-2, 0)],
                'sell_ranges': [(0.5, 3), (1, 4), (2, 5), (0, 2)]
            },
            'adx': {
                'thresholds': [20, 25, 30, 35, 40]
            },
            'volume_ratio': {
                'thresholds': [0.8, 1.0, 1.2, 1.5, 2.0]
            }
        }
        
        optimal_thresholds = {}
        
        # RSI optimization
        print("\n📊 RSI Thresholds:")
        print("-"*80)
        print(f"{'Type':<8} {'Range':<15} {'Win Rate':>10} {'Avg Profit':>12} {'Opportunities':>15}")
        print("-"*80)
        
        best_buy_rsi = None
        best_sell_rsi = None
        best_buy_score = 0
        best_sell_score = 0
        
        for rng in indicators['rsi']['buy_ranges']:
            mask = (self.all_data['rsi'] >= rng[0]) & (self.all_data['rsi'] <= rng[1])
            subset = self.all_data[mask]
            wins = subset[subset[gain_col] > 0.5]
            
            win_rate = len(wins) / len(subset) * 100 if len(subset) > 0 else 0
            avg_profit = wins[gain_col].mean() if len(wins) > 0 else 0
            score = win_rate * avg_profit
            
            print(f"BUY      {str(rng):<15} {win_rate:>9.1f}% {avg_profit:>11.2f}% {len(subset):>15}")
            
            if score > best_buy_score:
                best_buy_score = score
                best_buy_rsi = rng
        
        for rng in indicators['rsi']['sell_ranges']:
            mask = (self.all_data['rsi'] >= rng[0]) & (self.all_data['rsi'] <= rng[1])
            subset = self.all_data[mask]
            wins = subset[subset[drop_col] > 0.5]
            
            win_rate = len(wins) / len(subset) * 100 if len(subset) > 0 else 0
            avg_profit = wins[drop_col].mean() if len(wins) > 0 else 0
            score = win_rate * avg_profit
            
            print(f"SELL     {str(rng):<15} {win_rate:>9.1f}% {avg_profit:>11.2f}% {len(subset):>15}")
            
            if score > best_sell_score:
                best_sell_score = score
                best_sell_rsi = rng
        
        optimal_thresholds['rsi'] = {
            'buy': best_buy_rsi,
            'sell': best_sell_rsi
        }
        
        print(f"\n✅ Optimal RSI: BUY {best_buy_rsi}, SELL {best_sell_rsi}")
        
        # VWAP Distance optimization
        print("\n📊 VWAP Distance Thresholds:")
        print("-"*80)
        
        best_buy_vwap = None
        best_sell_vwap = None
        best_buy_score = 0
        best_sell_score = 0
        
        for rng in indicators['vwap_distance']['buy_ranges']:
            mask = (self.all_data['vwap_distance'] >= rng[0]) & (self.all_data['vwap_distance'] <= rng[1])
            subset = self.all_data[mask]
            wins = subset[subset[gain_col] > 0.5]
            
            win_rate = len(wins) / len(subset) * 100 if len(subset) > 0 else 0
            avg_profit = wins[gain_col].mean() if len(wins) > 0 else 0
            score = win_rate * avg_profit
            
            print(f"BUY      {str(rng):<15} {win_rate:>9.1f}% {avg_profit:>11.2f}% {len(subset):>15}")
            
            if score > best_buy_score:
                best_buy_score = score
                best_buy_vwap = rng
        
        for rng in indicators['vwap_distance']['sell_ranges']:
            mask = (self.all_data['vwap_distance'] >= rng[0]) & (self.all_data['vwap_distance'] <= rng[1])
            subset = self.all_data[mask]
            wins = subset[subset[drop_col] > 0.5]
            
            win_rate = len(wins) / len(subset) * 100 if len(subset) > 0 else 0
            avg_profit = wins[drop_col].mean() if len(wins) > 0 else 0
            score = win_rate * avg_profit
            
            print(f"SELL     {str(rng):<15} {win_rate:>9.1f}% {avg_profit:>11.2f}% {len(subset):>15}")
            
            if score > best_sell_score:
                best_sell_score = score
                best_sell_vwap = rng
        
        optimal_thresholds['vwap_distance'] = {
            'buy': best_buy_vwap,
            'sell': best_sell_vwap
        }
        
        print(f"\n✅ Optimal VWAP Distance: BUY {best_buy_vwap}, SELL {best_sell_vwap}")
        
        # ADX minimum threshold
        print("\n📊 ADX Minimum Threshold:")
        print("-"*80)
        
        best_adx = None
        best_adx_score = 0
        
        for threshold in indicators['adx']['thresholds']:
            mask = self.all_data['adx'] >= threshold
            subset = self.all_data[mask]
            
            buy_wins = subset[subset[gain_col] > 0.5]
            sell_wins = subset[subset[drop_col] > 0.5]
            
            buy_wr = len(buy_wins) / len(subset) * 100 if len(subset) > 0 else 0
            sell_wr = len(sell_wins) / len(subset) * 100 if len(subset) > 0 else 0
            
            avg_wr = (buy_wr + sell_wr) / 2
            score = avg_wr * len(subset)
            
            print(f"ADX >= {threshold:>4} | BUY WR: {buy_wr:>5.1f}% | SELL WR: {sell_wr:>5.1f}% | Opps: {len(subset):>6}")
            
            if score > best_adx_score:
                best_adx_score = score
                best_adx = threshold
        
        optimal_thresholds['adx'] = {'min': best_adx}
        print(f"\n✅ Optimal ADX minimum: {best_adx}")
        
        return optimal_thresholds
    
    def save_results(self, ttl_results, best_ttl, thresholds):
        """Save optimization results"""
        output = {
            'ttl_optimization': ttl_results.to_dict('records'),
            'optimal_ttl': int(best_ttl['ttl']),
            'optimal_profit_threshold': float(best_ttl['threshold']),
            'optimal_thresholds': thresholds,
            'performance': {
                'buy_win_rate': float(best_ttl['buy_win_rate']),
                'sell_win_rate': float(best_ttl['sell_win_rate']),
                'buy_avg_profit': float(best_ttl['buy_avg_profit']),
                'sell_avg_profit': float(best_ttl['sell_avg_profit'])
            }
        }
        
        output_file = Path('backtesting/lightweight_optimization_results.json')
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
    
    def run(self):
        """Run complete optimization"""
        self.load_enriched_data()
        
        # Optimize TTL
        ttl_results, best_ttl = self.optimize_ttl()
        
        # Optimize indicator thresholds using best TTL
        optimal_ttl = int(best_ttl['ttl'])
        thresholds = self.analyze_indicator_thresholds(ttl=optimal_ttl)
        
        # Save results
        self.save_results(ttl_results, best_ttl, thresholds)
        
        print("\n" + "="*80)
        print("✅ OPTIMIZATION COMPLETE")
        print("="*80)


if __name__ == '__main__':
    optimizer = LightweightOptimizer()
    optimizer.run()
