#!/usr/bin/env python3
"""
Simple Optimizer - Uses only basic indicators (no OI/CVD/Liquidations)
Works with processed data from indicator_calculator.py
"""

import pandas as pd
import yaml
import json
from pathlib import Path
from datetime import datetime
from itertools import product
import numpy as np

class SimpleOptimizer:
    def __init__(self):
        print("="*80)
        print("🔬 SIMPLE FORMULA OPTIMIZER")
        print("="*80)
        print("\nOptimizing: RSI, EMA, VWAP, ADX, Volume weights")
        print("(No OI/CVD/Liquidations - using basic indicators only)\n")
        
        # Load config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = self.config.get('symbols', [])
        
        # Load processed data
        self.load_data()
    
    def load_data(self):
        """Load processed indicator data"""
        self.data = {}
        data_dir = Path('backtesting/data')
        
        for symbol in self.symbols:
            file_path = data_dir / f"{symbol}_processed.csv"
            
            if file_path.exists():
                df = pd.read_csv(file_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                self.data[symbol] = df
                print(f"✅ Loaded {symbol}: {len(df)} candles")
        
        total_candles = sum(len(df) for df in self.data.values())
        print(f"\n📊 Total: {total_candles:,} candles across {len(self.data)} symbols")
        print("="*80)
    
    def calculate_score(self, row, weights):
        """
        Calculate signal score based on indicators
        
        Uses only: RSI, EMA, VWAP, ADX, Volume
        """
        score = 0
        
        # RSI component (0-100, normalize to -1 to +1)
        rsi = row.get('rsi', 50)
        if rsi < 30:
            rsi_score = (30 - rsi) / 30  # 0 to 1 (oversold, bullish)
        elif rsi > 70:
            rsi_score = (rsi - 70) / 30  # 0 to -1 (overbought, bearish)
        else:
            rsi_score = 0
        
        score += rsi_score * weights['rsi']
        
        # EMA trend (EMA_fast vs EMA_slow)
        ema_fast = row.get('ema_fast', 0)
        ema_slow = row.get('ema_slow', 0)
        
        if ema_fast > 0 and ema_slow > 0:
            ema_diff_pct = (ema_fast - ema_slow) / ema_slow * 100
            ema_score = np.clip(ema_diff_pct / 2, -1, 1)  # Normalize
            score += ema_score * weights['ema']
        
        # VWAP distance (price vs VWAP)
        close = row.get('close', 0)
        vwap = row.get('vwap', close)
        
        if vwap > 0:
            vwap_dist_pct = (close - vwap) / vwap * 100
            vwap_score = np.clip(vwap_dist_pct / 5, -1, 1)  # Normalize
            score += vwap_score * weights['vwap']
        
        # ADX trend strength (0-100)
        adx = row.get('adx', 0)
        adx_score = min(adx / 50, 1)  # Normalize to 0-1
        score += adx_score * weights['adx']
        
        # Volume ratio (current vs SMA)
        volume = row.get('volume', 0)
        volume_sma = row.get('volume_sma', volume)
        
        if volume_sma > 0:
            vol_ratio = volume / volume_sma
            vol_score = np.clip((vol_ratio - 1) / 2, -1, 1)  # Normalize
            score += vol_score * weights['volume']
        
        return score
    
    def backtest_weights(self, weights, min_score=2.0, ttl_minutes=30):
        """
        Backtest a weight combination
        """
        all_signals = []
        
        for symbol, df in self.data.items():
            for i in range(len(df)):
                row = df.iloc[i]
                
                # Calculate score
                score = self.calculate_score(row, weights)
                
                # Only consider if meets threshold
                if abs(score) < min_score:
                    continue
                
                # Determine direction
                side = 'BUY' if score > 0 else 'SELL'
                
                # Simulate signal tracking over TTL
                entry_price = row['close']
                entry_time = row['timestamp']
                
                # Find outcome within TTL
                ttl_end_idx = min(i + int(ttl_minutes / 5), len(df) - 1)
                
                max_price = df.iloc[i:ttl_end_idx+1]['high'].max()
                min_price = df.iloc[i:ttl_end_idx+1]['low'].min()
                
                # Calculate profit based on side
                if side == 'BUY':
                    profit_pct = (max_price - entry_price) / entry_price * 100
                    is_win = profit_pct >= 0.5  # 0.5% target
                else:  # SELL
                    profit_pct = (entry_price - min_price) / entry_price * 100
                    is_win = profit_pct >= 0.5
                
                all_signals.append({
                    'symbol': symbol,
                    'side': side,
                    'score': score,
                    'profit_pct': profit_pct,
                    'is_win': is_win
                })
        
        if not all_signals:
            return None
        
        # Calculate metrics
        total = len(all_signals)
        wins = sum(1 for s in all_signals if s['is_win'])
        win_rate = wins / total * 100
        avg_profit = np.mean([s['profit_pct'] for s in all_signals])
        total_profit = sum([s['profit_pct'] for s in all_signals])
        
        # BUY vs SELL breakdown
        buy_signals = [s for s in all_signals if s['side'] == 'BUY']
        sell_signals = [s for s in all_signals if s['side'] == 'SELL']
        
        buy_wr = sum(1 for s in buy_signals if s['is_win']) / len(buy_signals) * 100 if buy_signals else 0
        sell_wr = sum(1 for s in sell_signals if s['is_win']) / len(sell_signals) * 100 if sell_signals else 0
        
        return {
            'total_signals': total,
            'wins': wins,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_profit': total_profit,
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'buy_wr': buy_wr,
            'sell_wr': sell_wr
        }
    
    def optimize(self, quick_mode=False):
        """
        Find optimal weights
        """
        print("\n🔬 Starting optimization...")
        print(f"Mode: {'QUICK' if quick_mode else 'FULL'}\n")
        
        # Weight options
        if quick_mode:
            weight_options = [0.5, 1.0, 1.5, 2.0, 3.0]
            min_score_options = [1.5, 2.0, 2.5]
            ttl_options = [25, 30, 35]
        else:
            weight_options = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
            min_score_options = [1.5, 2.0, 2.5, 3.0]
            ttl_options = [20, 25, 30, 35, 40]
        
        best_result = None
        best_weights = None
        best_params = None
        test_count = 0
        
        total_tests = (len(weight_options) ** 5) * len(min_score_options) * len(ttl_options)
        print(f"Testing ~{total_tests:,} combinations...\n")
        
        # Test all combinations
        for rsi, ema, vwap, adx, vol in product(weight_options, repeat=5):
            weights = {
                'rsi': rsi,
                'ema': ema,
                'vwap': vwap,
                'adx': adx,
                'volume': vol
            }
            
            for min_score in min_score_options:
                for ttl in ttl_options:
                    test_count += 1
                    
                    result = self.backtest_weights(weights, min_score, ttl)
                    
                    if test_count % 5000 == 0:
                        print(f"Progress: {test_count:,}/{total_tests:,} ({test_count/total_tests*100:.1f}%)")
                        if best_result:
                            print(f"  Best: WR={best_result['win_rate']:.1f}% | Signals={best_result['total_signals']} | Avg={best_result['avg_profit']:+.3f}%\n")
                    
                    # Must have minimum signals
                    if result and result['total_signals'] >= 20:
                        # Score: win rate + avg profit * 50
                        current_score = result['win_rate'] + (result['avg_profit'] * 50)
                        
                        if best_result is None:
                            best_result = result
                            best_weights = weights.copy()
                            best_params = {'min_score': min_score, 'ttl': ttl}
                        else:
                            best_score = best_result['win_rate'] + (best_result['avg_profit'] * 50)
                            
                            if current_score > best_score:
                                best_result = result
                                best_weights = weights.copy()
                                best_params = {'min_score': min_score, 'ttl': ttl}
        
        # Print results
        self.print_results(best_weights, best_params, best_result, quick_mode)
        
        return best_weights, best_params, best_result
    
    def print_results(self, best_weights, best_params, best_result, quick_mode):
        """Print optimization results"""
        print("\n" + "="*80)
        print("✅ OPTIMIZATION COMPLETE")
        print("="*80)
        
        if best_result:
            print(f"\n🏆 BEST FORMULA FOUND:\n")
            print(f"{'Indicator':<15} {'Weight':<10}")
            print("-" * 25)
            for name, value in best_weights.items():
                print(f"{name:<15} {value:<10.1f}")
            
            print(f"\nParameters:")
            print(f"  Min Score: {best_params['min_score']:.1f}")
            print(f"  TTL: {best_params['ttl']} minutes")
            
            print(f"\nPerformance:")
            print(f"  Win Rate:      {best_result['win_rate']:.1f}%")
            print(f"  Total Signals: {best_result['total_signals']:,}")
            print(f"  Wins:          {best_result['wins']}")
            print(f"  Avg Profit:    {best_result['avg_profit']:+.4f}%")
            print(f"  Total Profit:  {best_result['total_profit']:+.2f}%")
            print(f"\n  BUY Signals:   {best_result['buy_count']} (WR: {best_result['buy_wr']:.1f}%)")
            print(f"  SELL Signals:  {best_result['sell_count']} (WR: {best_result['sell_wr']:.1f}%)")
            
            # Save results
            output_file = 'backtesting/best_formula_simple_quick.json' if quick_mode else 'backtesting/best_formula_simple_full.json'
            
            output = {
                'weights': best_weights,
                'parameters': best_params,
                'performance': best_result,
                'optimizer_type': 'simple_indicators_only',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✅ Saved to: {output_file}")
        else:
            print("\n❌ No valid formula found")
        
        print("\n" + "="*80)

if __name__ == '__main__':
    import sys
    
    quick_mode = '--quick' in sys.argv
    
    optimizer = SimpleOptimizer()
    optimizer.optimize(quick_mode=quick_mode)
