#!/usr/bin/env python3
"""
Real Data Optimizer
Uses actual signal logs and effectiveness data to find optimal formula weights
"""

import csv
import json
import yaml
from datetime import datetime
import statistics
import numpy as np

class RealDataOptimizer:
    def __init__(self):
        print("="*80)
        print("📊 REAL DATA FORMULA OPTIMIZER")
        print("="*80)
        print("\nUsing actual bot signals and outcomes")
        print("No need to download historical data!\n")
        
        # Load signals and effectiveness data
        self.load_data()
    
    def load_data(self):
        """Load signals and effectiveness logs"""
        # Load signals
        signals = []
        with open('signals_log.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                signals.append(row)
        
        # Load effectiveness
        effectiveness = {}
        with open('effectiveness_log.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Match by symbol + timestamp_sent
                verdict = row.get('verdict', '')
                side = verdict.split()[0] if verdict else ''
                key = f"{row['symbol']}_{side}_{row['timestamp_sent']}"
                effectiveness[key] = row
        
        # Match signals with results
        self.matched_data = []
        for sig in signals:
            verdict = sig.get('verdict', '')
            side = verdict.split()[0] if verdict else ''
            key = f"{sig['symbol']}_{side}_{sig['timestamp']}"
            
            if key in effectiveness:
                # Parse components JSON
                try:
                    components = json.loads(sig.get('components', '{}'))
                except:
                    components = {}
                
                self.matched_data.append({
                    'signal': sig,
                    'result': effectiveness[key]['result'],
                    'profit_pct': float(effectiveness[key].get('profit_pct', 0)),
                    'components': components
                })
        
        print(f"✅ Loaded {len(signals)} signals")
        print(f"✅ Matched {len(self.matched_data)} signals with outcomes")
        print(f"   WIN:       {sum(1 for d in self.matched_data if d['result'] == 'WIN')}")
        print(f"   LOSS:      {sum(1 for d in self.matched_data if d['result'] == 'LOSS')}")
        print(f"   CANCELLED: {sum(1 for d in self.matched_data if d['result'] == 'CANCELLED')}")
        print("="*80)
    
    def calculate_weighted_score(self, components, weights):
        """
        Calculate score using component scores and weights
        """
        score = 0
        
        for comp_name, comp_score in components.items():
            # Map component names to weight keys
            weight_map = {
                'cvd_score': 'cvd',
                'oi_score': 'oi',
                'vwap_score': 'vwap',
                'rsi_score': 'rsi',
                'ema_score': 'ema',
                'adx_score': 'adx',
                'volume_score': 'volume',
                'liquidation_score': 'liquidations',
                'funding_score': 'funding'
            }
            
            weight_key = weight_map.get(comp_name)
            if weight_key and weight_key in weights:
                score += float(comp_score) * weights[weight_key]
        
        return score
    
    def test_weights(self, weights, min_score_threshold=2.0):
        """
        Test a weight combination on real data
        """
        results = []
        
        for item in self.matched_data:
            # Calculate new score with these weights
            new_score = self.calculate_weighted_score(item['components'], weights)
            
            # Only consider if score meets threshold
            if new_score >= min_score_threshold:
                results.append({
                    'result': item['result'],
                    'profit': item['profit_pct'],
                    'score': new_score
                })
        
        if not results:
            return None
        
        # Calculate metrics
        wins = sum(1 for r in results if r['result'] == 'WIN')
        losses = sum(1 for r in results if r['result'] == 'LOSS')
        cancelled = sum(1 for r in results if r['result'] == 'CANCELLED')
        total = len(results)
        
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_profit = statistics.mean([r['profit'] for r in results])
        total_profit = sum([r['profit'] for r in results])
        
        return {
            'win_rate': win_rate,
            'total_signals': total,
            'wins': wins,
            'losses': losses,
            'cancelled': cancelled,
            'avg_profit': avg_profit,
            'total_profit': total_profit
        }
    
    def optimize(self, quick_mode=False):
        """
        Find optimal weights
        """
        print("\n🔬 Starting optimization...")
        print(f"Mode: {'QUICK' if quick_mode else 'FULL'}\n")
        
        # Weight options
        if quick_mode:
            weight_options = [0.5, 1.0, 2.0, 3.0]
            min_score_options = [2.0, 2.5]
        else:
            weight_options = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
            min_score_options = [1.5, 2.0, 2.5, 3.0]
        
        best_result = None
        best_weights = None
        best_threshold = None
        test_count = 0
        
        total_tests = (len(weight_options) ** 9) * len(min_score_options)
        print(f"Testing ~{total_tests:,} combinations...\n")
        
        # Test all weight combinations
        from itertools import product
        
        for cvd, oi, vwap, rsi, ema, adx, vol, liq, fund in product(weight_options, repeat=9):
            weights = {
                'cvd': cvd,
                'oi': oi,
                'vwap': vwap,
                'rsi': rsi,
                'ema': ema,
                'adx': adx,
                'volume': vol,
                'liquidations': liq,
                'funding': fund
            }
            
            for min_score in min_score_options:
                test_count += 1
                
                result = self.test_weights(weights, min_score)
                
                if test_count % 10000 == 0:
                    print(f"Progress: {test_count:,}/{total_tests:,} ({test_count/total_tests*100:.1f}%)")
                    if best_result:
                        print(f"  Best: WR={best_result['win_rate']:.1f}% | Signals={best_result['total_signals']} | Avg={best_result['avg_profit']:+.3f}%\n")
                
                # Must have minimum signals
                if result and result['total_signals'] >= 50:
                    # Score: prioritize win rate, then avg profit
                    current_score = result['win_rate'] + (result['avg_profit'] * 50)
                    
                    if best_result is None:
                        best_result = result
                        best_weights = weights.copy()
                        best_threshold = min_score
                    else:
                        best_score = best_result['win_rate'] + (best_result['avg_profit'] * 50)
                        
                        if current_score > best_score:
                            best_result = result
                            best_weights = weights.copy()
                            best_threshold = min_score
        
        # Print results
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
            print(f"  Min Score Threshold: {best_threshold:.1f}")
            
            print(f"\nPerformance on Real Data:")
            print(f"  Win Rate:      {best_result['win_rate']:.1f}%")
            print(f"  Total Signals: {best_result['total_signals']:,}")
            print(f"  Wins:          {best_result['wins']}")
            print(f"  Losses:        {best_result['losses']}")
            print(f"  Cancelled:     {best_result['cancelled']}")
            print(f"  Avg Profit:    {best_result['avg_profit']:+.4f}%")
            print(f"  Total Profit:  {best_result['total_profit']:+.2f}%")
            
            # Save results
            output = {
                'weights': best_weights,
                'parameters': {
                    'min_score_threshold': best_threshold
                },
                'performance': {
                    'win_rate': best_result['win_rate'],
                    'total_signals': best_result['total_signals'],
                    'wins': best_result['wins'],
                    'losses': best_result['losses'],
                    'cancelled': best_result['cancelled'],
                    'avg_profit': best_result['avg_profit'],
                    'total_profit': best_result['total_profit']
                },
                'data_source': 'real_bot_logs',
                'signals_analyzed': len(self.matched_data),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open('backtesting/best_formula_realdata.json', 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"\n✅ Saved to: backtesting/best_formula_realdata.json")
            
            # Compare with current weights
            with open('config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            
            current_weights = config.get('default_coin', {}).get('weights', {})
            
            print(f"\n" + "="*80)
            print("📊 COMPARISON: New vs Current Weights")
            print("="*80)
            print(f"\n{'Indicator':<15} {'Current':<10} {'New':<10} {'Change':<10}")
            print("-" * 50)
            
            for name in best_weights.keys():
                curr = current_weights.get(name, 1.0)
                new = best_weights[name]
                change = new - curr
                arrow = "↑" if change > 0 else "↓" if change < 0 else "="
                print(f"{name:<15} {curr:<10.1f} {new:<10.1f} {arrow} {abs(change):<8.1f}")
            
        else:
            print("\n❌ No valid formula found")
        
        print("\n" + "="*80)
        
        return best_weights, best_threshold, best_result

if __name__ == '__main__':
    import sys
    
    quick_mode = '--quick' in sys.argv
    
    optimizer = RealDataOptimizer()
    optimizer.optimize(quick_mode=quick_mode)
