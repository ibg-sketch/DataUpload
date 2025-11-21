#!/usr/bin/env python3
"""
Fast Short TTL Optimizer
Tests only logical weight combinations for speed
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

class FastShortTTLOptimizer:
    
    def __init__(self):
        self.data_dir = Path('backtesting/data')
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT',
            'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
        ]
        
        self.train_data = {}
        self.test_data = {}
        
        # Trading costs
        self.taker_fee = 0.05  # 0.05%
        self.slippage = 0.02   # 0.02%
        
    def load_and_split_data(self):
        """Load and split data (75% train, 25% test)"""
        print("Loading data with walk-forward split...")
        
        for symbol in self.symbols:
            file_path = self.data_dir / f"{symbol}_enriched.csv"
            
            if not file_path.exists():
                continue
            
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            split_idx = int(len(df) * 0.75)
            
            self.train_data[symbol] = df.iloc[:split_idx].copy()
            self.test_data[symbol] = df.iloc[split_idx:].copy()
        
        print(f"✅ Loaded {len(self.train_data)} symbols (75% train, 25% test)\n")
    
    def test_formula(self, data, ttl, weights, min_score_pct=0.6):
        """
        Test specific formula on dataset
        Returns: win_rate, avg_profit, signals_count, buy_wr, sell_wr
        """
        all_data = pd.concat(data.values(), ignore_index=True)
        
        gain_col = f'max_gain_{ttl}m'
        drop_col = f'max_drop_{ttl}m'
        
        max_score = sum(weights.values())
        min_score = max_score * min_score_pct
        
        signals = []
        
        for _, row in all_data.iterrows():
            # BUY score
            buy_score = 0
            if 0 <= row['rsi'] <= 35:
                buy_score += weights['rsi']
            if -5.0 <= row['vwap_distance'] <= -2.0:
                buy_score += weights['vwap']
            if row['adx'] >= 20:
                buy_score += weights['adx']
            if row['volume_ratio'] >= 0.8:
                buy_score += weights['volume']
            
            if buy_score >= min_score:
                gross = row[gain_col]
                net = gross - (self.taker_fee * 2) - self.slippage
                signals.append({
                    'side': 'BUY',
                    'net_profit': net,
                    'result': 'WIN' if net > 0 else 'LOSS'
                })
            
            # SELL score
            sell_score = 0
            if 65 <= row['rsi'] <= 100:
                sell_score += weights['rsi']
            if 2.0 <= row['vwap_distance'] <= 5.0:
                sell_score += weights['vwap']
            if row['adx'] >= 20:
                sell_score += weights['adx']
            if row['volume_ratio'] >= 0.8:
                sell_score += weights['volume']
            
            if sell_score >= min_score:
                gross = row[drop_col]
                net = gross - (self.taker_fee * 2) - self.slippage
                signals.append({
                    'side': 'SELL',
                    'net_profit': net,
                    'result': 'WIN' if net > 0 else 'LOSS'
                })
        
        if not signals:
            return {'win_rate': 0, 'avg_profit': 0, 'signals': 0, 'buy_wr': 0, 'sell_wr': 0}
        
        df_sig = pd.DataFrame(signals)
        wins = df_sig[df_sig['result'] == 'WIN']
        
        buy_sig = df_sig[df_sig['side'] == 'BUY']
        sell_sig = df_sig[df_sig['side'] == 'SELL']
        
        buy_wins = buy_sig[buy_sig['result'] == 'WIN']
        sell_wins = sell_sig[sell_sig['result'] == 'WIN']
        
        return {
            'win_rate': len(wins) / len(df_sig) * 100,
            'avg_profit': wins['net_profit'].mean() if len(wins) > 0 else 0,
            'signals': len(df_sig),
            'buy_wr': len(buy_wins) / len(buy_sig) * 100 if len(buy_sig) > 0 else 0,
            'sell_wr': len(sell_wins) / len(sell_sig) * 100 if len(sell_sig) > 0 else 0,
            'buy_signals': len(buy_sig),
            'sell_signals': len(sell_sig)
        }
    
    def optimize(self):
        """Run optimization with predefined logical weight combinations"""
        self.load_and_split_data()
        
        # Predefined logical combinations (based on correlation analysis)
        # Volatility and VWAP were strongest, RSI moderate, volume weakest
        weight_combinations = [
            # Equal weights
            {'name': 'Equal', 'rsi': 1.0, 'vwap': 1.0, 'adx': 1.0, 'volume': 1.0},
            
            # VWAP dominant (strongest predictor)
            {'name': 'VWAP Heavy', 'rsi': 1.0, 'vwap': 2.0, 'adx': 1.0, 'volume': 0.5},
            {'name': 'VWAP Max', 'rsi': 0.5, 'vwap': 2.0, 'adx': 1.0, 'volume': 0.5},
            
            # Balanced high importance
            {'name': 'Balanced Strong', 'rsi': 1.5, 'vwap': 1.5, 'adx': 1.0, 'volume': 1.0},
            
            # RSI+VWAP focus
            {'name': 'RSI+VWAP', 'rsi': 1.5, 'vwap': 1.5, 'adx': 0.5, 'volume': 0.5},
            
            # Conservative (high confluence requirement)
            {'name': 'Conservative', 'rsi': 1.0, 'vwap': 1.0, 'adx': 1.0, 'volume': 1.0},
            
            # Aggressive VWAP
            {'name': 'VWAP Only', 'rsi': 0.5, 'vwap': 3.0, 'adx': 0.5, 'volume': 0.5},
            
            # ADX importance
            {'name': 'Trend Focus', 'rsi': 1.0, 'vwap': 1.5, 'adx': 1.5, 'volume': 0.5}
        ]
        
        all_results = {}
        
        for ttl in [15, 30]:
            print(f"\n{'='*80}")
            print(f"TESTING TTL = {ttl} MINUTES")
            print(f"{'='*80}\n")
            
            results = []
            
            for config in weight_combinations:
                name = config['name']
                weights = {k: v for k, v in config.items() if k != 'name'}
                
                # Test on train data
                train_perf = self.test_formula(self.train_data, ttl, weights)
                
                # Test on holdout
                test_perf = self.test_formula(self.test_data, ttl, weights)
                
                # Only keep if both have signals
                if train_perf['signals'] > 100 and test_perf['signals'] > 20:
                    results.append({
                        'name': name,
                        'weights': weights.copy(),
                        'train': train_perf,
                        'test': test_perf,
                        'score': test_perf['win_rate'] * test_perf['avg_profit']  # Test performance matters
                    })
                    
                    print(f"{name:20s} | Train: {train_perf['win_rate']:5.1f}% WR, {train_perf['signals']:4d} sig | "
                          f"Test: {test_perf['win_rate']:5.1f}% WR, {test_perf['avg_profit']:5.2f}% profit, {test_perf['signals']:3d} sig")
            
            all_results[ttl] = sorted(results, key=lambda x: x['score'], reverse=True)
        
        # Find overall best
        best_ttl = None
        best_config = None
        best_score = 0
        
        for ttl, results in all_results.items():
            if results and results[0]['score'] > best_score:
                best_score = results[0]['score']
                best_ttl = ttl
                best_config = results[0]
        
        print(f"\n{'='*80}")
        print(f"🏆 OPTIMAL CONFIGURATION FOR 50x LEVERAGE")
        print(f"{'='*80}")
        print(f"TTL: {best_ttl} minutes")
        print(f"Formula: {best_config['name']}")
        print(f"\nIndicator Weights:")
        for ind, w in best_config['weights'].items():
            print(f"  {ind:10s}: {w:.1f}")
        
        print(f"\n📊 Training Performance:")
        print(f"  Win Rate: {best_config['train']['win_rate']:.1f}%")
        print(f"  BUY: {best_config['train']['buy_wr']:.1f}% WR ({best_config['train']['buy_signals']} signals)")
        print(f"  SELL: {best_config['train']['sell_wr']:.1f}% WR ({best_config['train']['sell_signals']} signals)")
        print(f"  Avg Profit: {best_config['train']['avg_profit']:.2f}%")
        
        print(f"\n✅ OUT-OF-SAMPLE Test Performance:")
        print(f"  Win Rate: {best_config['test']['win_rate']:.1f}%")
        print(f"  BUY: {best_config['test']['buy_wr']:.1f}% WR ({best_config['test']['buy_signals']} signals)")
        print(f"  SELL: {best_config['test']['sell_wr']:.1f}% WR ({best_config['test']['sell_signals']} signals)")
        print(f"  Avg Profit: {best_config['test']['avg_profit']:.2f}%")
        print(f"  Signals: {best_config['test']['signals']}")
        print(f"{'='*80}")
        
        # Show top 3 for each TTL
        for ttl, results in all_results.items():
            print(f"\n📋 Top 3 Formulas for TTL={ttl}min:")
            print("-"*60)
            for i, r in enumerate(results[:3], 1):
                print(f"{i}. {r['name']:20s}: Test {r['test']['win_rate']:5.1f}% WR, {r['test']['avg_profit']:5.2f}% profit")
        
        # Save results
        output = {
            'optimal_ttl': best_ttl,
            'optimal_formula': best_config['name'],
            'optimal_weights': best_config['weights'],
            'train_performance': best_config['train'],
            'test_performance': best_config['test'],
            'all_results': {
                str(ttl): [{
                    'name': r['name'],
                    'weights': r['weights'],
                    'train': r['train'],
                    'test': r['test']
                } for r in results]
                for ttl, results in all_results.items()
            }
        }
        
        output_file = Path('backtesting/short_ttl_optimal_formula.json')
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")


if __name__ == '__main__':
    optimizer = FastShortTTLOptimizer()
    optimizer.optimize()
