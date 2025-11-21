#!/usr/bin/env python3
"""
Full Formula Optimizer - Uses ALL indicators
Tests different weight combinations including CVD, OI, Liquidations, Funding Rate
"""

import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
import yaml
from datetime import datetime, timedelta
import json

class FullFormulaOptimizer:
    def __init__(self):
        # Load current config
        with open('config.yaml', 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.symbols = self.config.get('symbols', [])
        
        # Load complete merged data
        self.data = {}
        self.load_all_data()
    
    def load_all_data(self):
        """Load all complete CSV files with all indicators"""
        data_dir = Path('backtesting/data')
        
        print("="*80)
        print("LOADING COMPLETE DATA FILES")
        print("="*80)
        
        for symbol in self.symbols:
            filename = data_dir / f"{symbol}_complete.csv"
            
            if filename.exists():
                df = pd.read_csv(filename)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                self.data[symbol] = df
                
                period = f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}"
                print(f"✅ {symbol:12s}: {len(df):6d} candles ({period})")
            else:
                print(f"⚠️ {symbol:12s}: Missing complete data file")
        
        total_candles = sum(len(df) for df in self.data.values())
        print(f"\n📊 Total: {total_candles:,} candles across {len(self.data)} symbols")
        print("="*80)
    
    def calculate_score(self, row, weights, side):
        """
        Calculate signal score based on ALL indicators and weights
        Matches main bot logic but uses historical data
        """
        score = 0
        
        # 1. CVD Score
        cvd = row.get('cvd_delta', 0)
        if side == 'BUY' and cvd > 0:  # Positive CVD for BUY
            score += weights['cvd'] * min(abs(cvd) / 1000000, 1.0)
        elif side == 'SELL' and cvd < 0:  # Negative CVD for SELL
            score += weights['cvd'] * min(abs(cvd) / 1000000, 1.0)
        
        # 2. OI Change Score
        oi_change = row.get('oi_change', 0)
        if side == 'BUY' and oi_change < 0:  # OI falling = good for BUY
            score += weights['oi'] * min(abs(oi_change) / 1000000, 1.0)
        elif side == 'SELL' and oi_change < 0:  # OI falling = good for SELL
            score += weights['oi'] * min(abs(oi_change) / 1000000, 1.0)
        
        # 3. VWAP Score
        vwap_dist = abs(row.get('vwap_distance', 0))
        if side == 'BUY' and row['close'] < row.get('vwap', row['close']):
            score += weights['vwap'] * min(vwap_dist / 2.0, 1.0)
        elif side == 'SELL' and row['close'] > row.get('vwap', row['close']):
            score += weights['vwap'] * min(vwap_dist / 2.0, 1.0)
        
        # 4. RSI Score
        rsi = row.get('rsi', 50)
        if side == 'BUY' and rsi < 45:
            score += weights['rsi'] * ((45 - rsi) / 15)
        elif side == 'SELL' and rsi > 55:
            score += weights['rsi'] * ((rsi - 55) / 15)
        
        # 5. EMA Trend Score
        ema_trend = row.get('ema_trend', '')
        if ema_trend == 'bullish' and side == 'BUY':
            score += weights['ema']
        elif ema_trend == 'bearish' and side == 'SELL':
            score += weights['ema']
        
        # 6. ADX Score (trend strength)
        adx = row.get('adx', 0)
        if adx > 25:
            score += weights['adx'] * (min(adx, 50) / 50)
        
        # 7. Volume Spike Score
        if row.get('volume_spike', False):
            score += weights['volume']
        
        # 8. Liquidations Score
        liq_long = row.get('liq_long', 0)
        liq_short = row.get('liq_short', 0)
        
        if side == 'BUY' and liq_short > liq_long:  # Shorts getting liquidated = bullish
            score += weights['liquidations'] * min((liq_short - liq_long) / 100000, 1.0)
        elif side == 'SELL' and liq_long > liq_short:  # Longs getting liquidated = bearish
            score += weights['liquidations'] * min((liq_long - liq_short) / 100000, 1.0)
        
        # 9. Funding Rate Score
        funding = row.get('funding_rate', 0)
        if side == 'BUY' and funding < 0:  # Negative funding = bullish
            score += weights['funding'] * min(abs(funding) * 1000, 1.0)
        elif side == 'SELL' and funding > 0:  # Positive funding = bearish
            score += weights['funding'] * min(abs(funding) * 1000, 1.0)
        
        return score
    
    def check_signal_outcome(self, df, idx, side, ttl_minutes):
        """
        Check if signal would be WIN or LOSS
        Uses actual price movement to determine outcome
        """
        entry_price = df.loc[idx, 'close']
        entry_time = df.loc[idx, 'timestamp']
        
        # Calculate target zone (realistic targets)
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
        
        # TTL expired - check final profit
        final_price = future_df.iloc[-1]['close']
        
        if side == 'BUY':
            profit = ((final_price - entry_price) / entry_price) * 100
        else:
            profit = ((entry_price - final_price) / entry_price) * 100
        
        result = 'WIN' if profit > 0 else 'LOSS'
        
        return result, profit
    
    def test_formula(self, weights, min_score=2.0, ttl_minutes=30, sample_rate=25):
        """
        Test a formula (weight combination) on all data
        sample_rate: test every Nth candle (25 = faster, 1 = complete but slow)
        """
        results = []
        
        for symbol, df in self.data.items():
            # Test every Nth candle to speed up
            for idx in range(50, len(df) - 100, sample_rate):
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
            return None
        
        wins = sum(1 for r in results if r['result'] == 'WIN')
        losses = sum(1 for r in results if r['result'] == 'LOSS')
        total = len(results)
        
        win_rate = (wins / total) * 100 if total > 0 else 0
        avg_profit = np.mean([r['profit'] for r in results])
        total_profit = sum([r['profit'] for r in results])
        
        # Separate BUY and SELL stats
        buy_results = [r for r in results if r['side'] == 'BUY']
        sell_results = [r for r in results if r['side'] == 'SELL']
        
        buy_wr = (sum(1 for r in buy_results if r['result'] == 'WIN') / len(buy_results) * 100) if buy_results else 0
        sell_wr = (sum(1 for r in sell_results if r['result'] == 'WIN') / len(sell_results) * 100) if sell_results else 0
        
        return {
            'win_rate': win_rate,
            'total_signals': total,
            'wins': wins,
            'losses': losses,
            'avg_profit': avg_profit,
            'total_profit': total_profit,
            'buy_wr': buy_wr,
            'sell_wr': sell_wr,
            'buy_count': len(buy_results),
            'sell_count': len(sell_results),
            'results': results
        }
    
    def optimize(self, quick_mode=False):
        """
        Run optimization to find best weights
        quick_mode: fewer combinations, faster results
        """
        print("\n" + "="*80)
        print("🔬 FULL FORMULA OPTIMIZATION")
        print("="*80)
        
        # Define weight ranges to test
        if quick_mode:
            weight_options = [0.5, 1.0, 2.0, 3.0]  # 4 options
            ttl_options = [25, 30, 35]  # 3 options
            min_score_options = [2.0, 2.5]  # 2 options
            sample_rate = 50  # Test every 50th candle
        else:
            weight_options = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]  # 6 options
            ttl_options = [20, 25, 30, 35, 40]  # 5 options
            min_score_options = [1.5, 2.0, 2.5, 3.0]  # 4 options
            sample_rate = 25  # Test every 25th candle
        
        # Total combinations
        total_tests = (len(weight_options) ** 9) * len(ttl_options) * len(min_score_options)
        
        print(f"\nMode: {'QUICK' if quick_mode else 'FULL'}")
        print(f"Weight options: {weight_options}")
        print(f"TTL options: {ttl_options}")
        print(f"Min score options: {min_score_options}")
        print(f"Sample rate: Every {sample_rate}th candle")
        print(f"\nEstimated combinations: {total_tests:,}")
        print("\nThis will take some time...\n")
        
        best_result = None
        best_weights = None
        best_params = None
        test_count = 0
        
        # Grid search over weight combinations
        for cvd_w in weight_options:
            for oi_w in weight_options:
                for vwap_w in weight_options:
                    for rsi_w in weight_options:
                        for ema_w in weight_options:
                            for adx_w in weight_options:
                                for vol_w in weight_options:
                                    for liq_w in weight_options:
                                        for fund_w in weight_options:
                                            weights = {
                                                'cvd': cvd_w,
                                                'oi': oi_w,
                                                'vwap': vwap_w,
                                                'rsi': rsi_w,
                                                'ema': ema_w,
                                                'adx': adx_w,
                                                'volume': vol_w,
                                                'liquidations': liq_w,
                                                'funding': fund_w
                                            }
                                            
                                            # Test different TTL and min_score
                                            for ttl in ttl_options:
                                                for min_score in min_score_options:
                                                    test_count += 1
                                                    
                                                    result = self.test_formula(weights, min_score, ttl, sample_rate)
                                                    
                                                    # Print progress every 1000 tests
                                                    if test_count % 1000 == 0:
                                                        print(f"Progress: {test_count:,} tests completed")
                                                        if best_result:
                                                            print(f"  Best: WR={best_result['win_rate']:.1f}% | Signals={best_result['total_signals']} | Profit={best_result['avg_profit']:+.3f}%")
                                                    
                                                    # Update best if this is better
                                                    if result and result['total_signals'] >= 100:  # Minimum signal count
                                                        # Score based on win_rate and profit
                                                        current_score = result['win_rate'] + (result['avg_profit'] * 100)
                                                        
                                                        if best_result is None:
                                                            best_result = result
                                                            best_weights = weights.copy()
                                                            best_params = {'ttl': ttl, 'min_score': min_score}
                                                        else:
                                                            best_score = best_result['win_rate'] + (best_result['avg_profit'] * 100)
                                                            
                                                            if current_score > best_score:
                                                                best_result = result
                                                                best_weights = weights.copy()
                                                                best_params = {'ttl': ttl, 'min_score': min_score}
        
        # Print results
        print("\n" + "="*80)
        print("✅ OPTIMIZATION COMPLETE")
        print("="*80)
        
        if best_result:
            print(f"\n🏆 BEST FORMULA FOUND:")
            print(f"\n{'Indicator':<15} {'Weight':<10}")
            print("-" * 25)
            for name, value in best_weights.items():
                print(f"{name:<15} {value:<10.1f}")
            
            print(f"\nParameters:")
            print(f"  Min Score: {best_params['min_score']:.1f}")
            print(f"  TTL:       {best_params['ttl']} minutes")
            
            print(f"\nPerformance:")
            print(f"  Win Rate:      {best_result['win_rate']:.1f}%")
            print(f"  Total Signals: {best_result['total_signals']:,}")
            print(f"  Wins/Losses:   {best_result['wins']}/{best_result['losses']}")
            print(f"  Avg Profit:    {best_result['avg_profit']:+.4f}%")
            print(f"  Total Profit:  {best_result['total_profit']:+.2f}%")
            
            print(f"\nBUY vs SELL:")
            print(f"  BUY:  {best_result['buy_count']:4d} signals | WR: {best_result['buy_wr']:.1f}%")
            print(f"  SELL: {best_result['sell_count']:4d} signals | WR: {best_result['sell_wr']:.1f}%")
            
            # Save best weights to file
            output = {
                'weights': best_weights,
                'parameters': best_params,
                'performance': {
                    'win_rate': best_result['win_rate'],
                    'total_signals': best_result['total_signals'],
                    'wins': best_result['wins'],
                    'losses': best_result['losses'],
                    'avg_profit': best_result['avg_profit'],
                    'total_profit': best_result['total_profit'],
                    'buy_wr': best_result['buy_wr'],
                    'sell_wr': best_result['sell_wr'],
                    'buy_count': best_result['buy_count'],
                    'sell_count': best_result['sell_count']
                },
                'optimization': {
                    'mode': 'quick' if quick_mode else 'full',
                    'tests_run': test_count,
                    'sample_rate': sample_rate
                },
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('backtesting/best_formula_full.json', 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✅ Saved to backtesting/best_formula_full.json")
        else:
            print("\n❌ No valid formula found")
        
        return best_weights, best_params, best_result

if __name__ == '__main__':
    import sys
    
    # Check if quick mode requested
    quick_mode = '--quick' in sys.argv
    
    optimizer = FullFormulaOptimizer()
    optimizer.optimize(quick_mode=quick_mode)
