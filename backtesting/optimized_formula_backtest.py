#!/usr/bin/env python3
"""
Optimized Formula Backtester
Test new data-driven formula vs old broken baseline
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

class OptimizedFormulaBacktest:
    """
    Backtest using optimized formula from statistical analysis
    """
    
    def __init__(self):
        self.data_dir = Path('backtesting/data')
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT',
            'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
        ]
        
        # Optimized parameters from analysis
        self.ttl_minutes = 120  # 2 hours
        self.profit_threshold = 0.3  # 0.3% minimum profit
        
        # Optimized indicator thresholds
        self.thresholds = {
            'rsi': {
                'buy': (0, 35),      # Oversold
                'sell': (65, 100)    # Overbought
            },
            'vwap_distance': {
                'buy': (-5.0, -2.0),  # Price 2-5% below VWAP
                'sell': (2.0, 5.0)    # Price 2-5% above VWAP
            },
            'adx': {
                'min': 20  # Minimum trend strength
            },
            'volume_ratio': {
                'min': 0.8  # At least 80% of average volume
            }
        }
        
        # Results storage
        self.signals = []
        self.performance = {}
    
    def check_buy_signal(self, row):
        """
        Check if BUY conditions are met
        Based on optimized thresholds
        """
        conditions = []
        
        # RSI oversold
        if self.thresholds['rsi']['buy'][0] <= row['rsi'] <= self.thresholds['rsi']['buy'][1]:
            conditions.append('rsi')
        
        # Price below VWAP (institutional support zone)
        if self.thresholds['vwap_distance']['buy'][0] <= row['vwap_distance'] <= self.thresholds['vwap_distance']['buy'][1]:
            conditions.append('vwap')
        
        # Sufficient trend strength
        if row['adx'] >= self.thresholds['adx']['min']:
            conditions.append('adx')
        
        # Adequate volume
        if row['volume_ratio'] >= self.thresholds['volume_ratio']['min']:
            conditions.append('volume')
        
        # Confluence requirement: At least 3 out of 4 conditions
        if len(conditions) >= 3:
            return True, conditions
        
        return False, conditions
    
    def check_sell_signal(self, row):
        """
        Check if SELL conditions are met
        """
        conditions = []
        
        # RSI overbought
        if self.thresholds['rsi']['sell'][0] <= row['rsi'] <= self.thresholds['rsi']['sell'][1]:
            conditions.append('rsi')
        
        # Price above VWAP (institutional resistance zone)
        if self.thresholds['vwap_distance']['sell'][0] <= row['vwap_distance'] <= self.thresholds['vwap_distance']['sell'][1]:
            conditions.append('vwap')
        
        # Sufficient trend strength
        if row['adx'] >= self.thresholds['adx']['min']:
            conditions.append('adx')
        
        # Adequate volume
        if row['volume_ratio'] >= self.thresholds['volume_ratio']['min']:
            conditions.append('volume')
        
        # Confluence requirement: At least 3 out of 4 conditions
        if len(conditions) >= 3:
            return True, conditions
        
        return False, conditions
    
    def backtest_symbol(self, symbol):
        """
        Backtest a single symbol with optimized formula
        """
        file_path = self.data_dir / f"{symbol}_enriched.csv"
        
        if not file_path.exists():
            print(f"⚠️  {symbol}: No enriched data found")
            return None
        
        df = pd.read_csv(file_path)
        
        signals = []
        
        for idx, row in df.iterrows():
            # Check BUY signal
            is_buy, buy_conditions = self.check_buy_signal(row)
            
            if is_buy:
                # Calculate actual profit at TTL
                actual_gain = row[f'max_gain_{self.ttl_minutes}m']
                
                result = 'WIN' if actual_gain >= self.profit_threshold else 'LOSS'
                
                signals.append({
                    'symbol': symbol,
                    'timestamp': row['timestamp'],
                    'side': 'BUY',
                    'entry_price': row['close'],
                    'conditions_met': buy_conditions,
                    'conditions_count': len(buy_conditions),
                    'rsi': row['rsi'],
                    'vwap_distance': row['vwap_distance'],
                    'adx': row['adx'],
                    'volume_ratio': row['volume_ratio'],
                    'actual_profit': actual_gain,
                    'result': result
                })
            
            # Check SELL signal
            is_sell, sell_conditions = self.check_sell_signal(row)
            
            if is_sell:
                # Calculate actual profit at TTL
                actual_gain = row[f'max_drop_{self.ttl_minutes}m']
                
                result = 'WIN' if actual_gain >= self.profit_threshold else 'LOSS'
                
                signals.append({
                    'symbol': symbol,
                    'timestamp': row['timestamp'],
                    'side': 'SELL',
                    'entry_price': row['close'],
                    'conditions_met': sell_conditions,
                    'conditions_count': len(sell_conditions),
                    'rsi': row['rsi'],
                    'vwap_distance': row['vwap_distance'],
                    'adx': row['adx'],
                    'volume_ratio': row['volume_ratio'],
                    'actual_profit': actual_gain,
                    'result': result
                })
        
        return signals
    
    def run_backtest(self):
        """
        Run backtest on all symbols
        """
        print("="*80)
        print("OPTIMIZED FORMULA BACKTESTING")
        print("="*80)
        print(f"TTL: {self.ttl_minutes} minutes")
        print(f"Profit Threshold: {self.profit_threshold}%")
        print(f"Confluence: 3/4 conditions required")
        print("="*80)
        print()
        
        all_signals = []
        
        for symbol in self.symbols:
            print(f"Testing {symbol}...")
            signals = self.backtest_symbol(symbol)
            
            if signals:
                all_signals.extend(signals)
                buy_signals = [s for s in signals if s['side'] == 'BUY']
                sell_signals = [s for s in signals if s['side'] == 'SELL']
                
                buy_wins = sum(1 for s in buy_signals if s['result'] == 'WIN')
                sell_wins = sum(1 for s in sell_signals if s['result'] == 'WIN')
                
                buy_wr = buy_wins / len(buy_signals) * 100 if buy_signals else 0
                sell_wr = sell_wins / len(sell_signals) * 100 if sell_signals else 0
                
                print(f"  BUY: {len(buy_signals)} signals, {buy_wr:.1f}% WR")
                print(f"  SELL: {len(sell_signals)} signals, {sell_wr:.1f}% WR")
        
        self.signals = all_signals
        
        # Calculate overall performance
        self.calculate_performance()
    
    def calculate_performance(self):
        """
        Calculate overall performance metrics
        """
        if not self.signals:
            print("⚠️  No signals generated")
            return
        
        df = pd.DataFrame(self.signals)
        
        # Overall metrics
        total_signals = len(df)
        buy_signals = df[df['side'] == 'BUY']
        sell_signals = df[df['side'] == 'SELL']
        
        buy_wins = buy_signals[buy_signals['result'] == 'WIN']
        sell_wins = sell_signals[sell_signals['result'] == 'WIN']
        
        # Win rates
        buy_wr = len(buy_wins) / len(buy_signals) * 100 if len(buy_signals) > 0 else 0
        sell_wr = len(sell_wins) / len(sell_signals) * 100 if len(sell_signals) > 0 else 0
        overall_wr = (len(buy_wins) + len(sell_wins)) / total_signals * 100
        
        # Average profits
        buy_avg_profit = buy_wins['actual_profit'].mean() if len(buy_wins) > 0 else 0
        sell_avg_profit = sell_wins['actual_profit'].mean() if len(sell_wins) > 0 else 0
        
        # Signals per day
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        days = (df['timestamp'].max() - df['timestamp'].min()).days
        signals_per_day = total_signals / max(days, 1)
        signals_per_day_per_symbol = signals_per_day / len(self.symbols)
        
        self.performance = {
            'total_signals': total_signals,
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'buy_win_rate': buy_wr,
            'sell_win_rate': sell_wr,
            'overall_win_rate': overall_wr,
            'buy_avg_profit': buy_avg_profit,
            'sell_avg_profit': sell_avg_profit,
            'signals_per_day': signals_per_day,
            'signals_per_day_per_symbol': signals_per_day_per_symbol,
            'days_tested': days
        }
        
        print("\n" + "="*80)
        print("OPTIMIZED FORMULA PERFORMANCE")
        print("="*80)
        print(f"Total Signals: {total_signals}")
        print(f"BUY Signals: {len(buy_signals)} ({len(buy_signals)/total_signals*100:.1f}%)")
        print(f"SELL Signals: {len(sell_signals)} ({len(sell_signals)/total_signals*100:.1f}%)")
        print(f"\nBUY Win Rate: {buy_wr:.1f}%")
        print(f"SELL Win Rate: {sell_wr:.1f}%")
        print(f"Overall Win Rate: {overall_wr:.1f}%")
        print(f"\nBUY Avg Profit: {buy_avg_profit:.2f}%")
        print(f"SELL Avg Profit: {sell_avg_profit:.2f}%")
        print(f"\nSignals/Day/Symbol: {signals_per_day_per_symbol:.1f}")
        print(f"Days Tested: {days}")
        print("="*80)
    
    def compare_with_baseline(self):
        """
        Compare optimized formula with baseline (18% WR)
        """
        baseline_wr = 18.0  # From previous testing
        baseline_signals_per_day = 274  # Per symbol
        
        improvement_wr = self.performance['overall_win_rate'] - baseline_wr
        improvement_pct = (self.performance['overall_win_rate'] / baseline_wr - 1) * 100
        
        signal_reduction = baseline_signals_per_day - self.performance['signals_per_day_per_symbol']
        signal_reduction_pct = (signal_reduction / baseline_signals_per_day) * 100
        
        print("\n" + "="*80)
        print("COMPARISON WITH BASELINE")
        print("="*80)
        print(f"{'Metric':<30} {'Baseline':>15} {'Optimized':>15} {'Improvement':>15}")
        print("-"*80)
        print(f"{'Win Rate':<30} {baseline_wr:>14.1f}% {self.performance['overall_win_rate']:>14.1f}% {improvement_wr:>+14.1f}%")
        print(f"{'Signals/Day/Symbol':<30} {baseline_signals_per_day:>15.1f} {self.performance['signals_per_day_per_symbol']:>15.1f} {-signal_reduction:>+15.1f}")
        print(f"{'Signal Reduction':<30} {'':>15} {'':>15} {signal_reduction_pct:>14.1f}%")
        print(f"{'WR Improvement':<30} {'':>15} {'':>15} {improvement_pct:>14.1f}%")
        print("="*80)
        
        print("\n📊 Summary:")
        if improvement_wr > 0:
            print(f"✅ Win rate improved by {improvement_wr:.1f} percentage points ({improvement_pct:.0f}% relative improvement)")
        
        if signal_reduction > 0:
            print(f"✅ Signal noise reduced by {signal_reduction_pct:.0f}% (from {baseline_signals_per_day:.0f} to {self.performance['signals_per_day_per_symbol']:.1f} signals/day)")
    
    def save_results(self):
        """Save backtest results"""
        output_file = Path('backtesting/optimized_formula_results.json')
        
        results = {
            'parameters': {
                'ttl_minutes': self.ttl_minutes,
                'profit_threshold': self.profit_threshold,
                'thresholds': self.thresholds
            },
            'performance': self.performance,
            'baseline_comparison': {
                'baseline_win_rate': 18.0,
                'optimized_win_rate': self.performance['overall_win_rate'],
                'improvement': self.performance['overall_win_rate'] - 18.0
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
        
        # Save signals to CSV
        signals_file = Path('backtesting/optimized_formula_signals.csv')
        if self.signals:
            df = pd.DataFrame(self.signals)
            df.to_csv(signals_file, index=False)
            print(f"✅ Signals saved to {signals_file}")


if __name__ == '__main__':
    backtester = OptimizedFormulaBacktest()
    backtester.run_backtest()
    backtester.compare_with_baseline()
    backtester.save_results()
