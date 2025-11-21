#!/usr/bin/env python3
"""
Indicator Combination Tester
Test 2-way and 3-way indicator combinations to find patterns with 45-55% success rate
"""
import pandas as pd
import numpy as np
from itertools import combinations
import json
from datetime import datetime, timedelta

class CombinationTester:
    def __init__(self):
        self.data = None
        self.results_2way = []
        self.results_3way = []
        
    def load_labeled_data(self):
        """Load pre-labeled opportunity data from forward_opportunity_finder"""
        print("="*80)
        print("LOADING LABELED OPPORTUNITY DATA")
        print("="*80)
        
        # Load analysis log
        df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values(['symbol', 'timestamp'])
        
        # Filter last 7 days
        cutoff = datetime.now() - timedelta(days=7)
        df = df[df['timestamp'] >= cutoff]
        
        # Label opportunities (same logic as forward_opportunity_finder)
        opportunities = []
        
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].copy()
            symbol_data = symbol_data.reset_index(drop=True)
            
            for i in range(len(symbol_data)):
                current_row = symbol_data.iloc[i]
                current_price = current_row.get('price', 0)
                current_time = current_row['timestamp']
                
                if current_price == 0:
                    continue
                
                # Look ahead 30 minutes
                future_time = current_time + timedelta(minutes=30)
                future_data = symbol_data[
                    (symbol_data['timestamp'] > current_time) &
                    (symbol_data['timestamp'] <= future_time)
                ]
                
                if len(future_data) < 3:
                    continue
                
                max_high = future_data['price'].max()
                min_low = future_data['price'].min()
                
                max_gain_pct = (max_high - current_price) / current_price * 100
                max_drawdown_pct = (current_price - min_low) / current_price * 100
                
                buy_opp = (max_gain_pct >= 0.5) and (max_drawdown_pct <= 0.5)
                sell_opp = (max_drawdown_pct >= 0.5) and (max_gain_pct <= 0.5)
                
                opportunities.append({
                    'timestamp': current_time,
                    'symbol': symbol,
                    'buy_opportunity': buy_opp,
                    'sell_opportunity': sell_opp,
                    'cvd': current_row.get('cvd', 0),
                    'oi_change_pct': current_row.get('oi_change_pct', 0),
                    'price_vs_vwap_pct': current_row.get('price_vs_vwap_pct', 0),
                    'liq_ratio': current_row.get('liq_ratio', 0),
                    'rsi': current_row.get('rsi', 50),
                    'adx': current_row.get('adx', 0),
                })
        
        self.data = pd.DataFrame(opportunities)
        
        print(f"\n✅ Loaded {len(self.data):,} labeled candles")
        print(f"   BUY opportunities: {self.data['buy_opportunity'].sum():,} ({self.data['buy_opportunity'].mean():.1%})")
        print(f"   SELL opportunities: {self.data['sell_opportunity'].sum():,} ({self.data['sell_opportunity'].mean():.1%})")
        
    def test_2way_combinations(self):
        """Test all 2-indicator combinations with AND logic"""
        print("\n" + "="*80)
        print("TESTING 2-WAY INDICATOR COMBINATIONS (AND LOGIC)")
        print("="*80)
        
        indicators = ['price_vs_vwap_pct', 'oi_change_pct', 'rsi', 'adx', 'cvd', 'liq_ratio']
        
        # Priority pairs based on architect recommendations
        priority_pairs = [
            ('price_vs_vwap_pct', 'oi_change_pct'),  # VWAP + OI (highest priority)
            ('price_vs_vwap_pct', 'rsi'),             # VWAP + RSI
            ('oi_change_pct', 'rsi'),                 # OI + RSI
            ('price_vs_vwap_pct', 'adx'),             # VWAP + ADX
        ]
        
        # Test all unique pairs
        for ind1, ind2 in priority_pairs:
            print(f"\n{'─'*80}")
            print(f"Testing: {ind1} + {ind2}")
            print(f"{'─'*80}")
            
            # Grid search thresholds
            percentiles = [10, 25, 50, 75, 90]
            
            for p1 in percentiles:
                thresh1 = self.data[ind1].quantile(p1 / 100)
                
                for p2 in percentiles:
                    thresh2 = self.data[ind2].quantile(p2 / 100)
                    
                    # Test all 4 combinations of above/below
                    for dir1 in ['above', 'below']:
                        for dir2 in ['above', 'below']:
                            # BUY filter
                            if dir1 == 'above':
                                mask1_buy = self.data[ind1] > thresh1
                            else:
                                mask1_buy = self.data[ind1] < thresh1
                            
                            if dir2 == 'above':
                                mask2_buy = self.data[ind2] > thresh2
                            else:
                                mask2_buy = self.data[ind2] < thresh2
                            
                            filtered_buy = self.data[mask1_buy & mask2_buy]
                            
                            if len(filtered_buy) < 100:  # Minimum sample size
                                continue
                            
                            buy_wr = filtered_buy['buy_opportunity'].mean()
                            buy_baseline = self.data['buy_opportunity'].mean()
                            
                            # Only save if significantly better than baseline
                            if buy_wr >= buy_baseline * 1.5:  # 50% improvement
                                self.results_2way.append({
                                    'type': 'BUY',
                                    'ind1': ind1,
                                    'thresh1': thresh1,
                                    'dir1': dir1,
                                    'ind2': ind2,
                                    'thresh2': thresh2,
                                    'dir2': dir2,
                                    'success_rate': buy_wr,
                                    'signals': len(filtered_buy),
                                    'baseline': buy_baseline,
                                    'improvement': (buy_wr / buy_baseline - 1) * 100
                                })
                            
                            # SELL filter
                            sell_wr = filtered_buy['sell_opportunity'].mean()
                            sell_baseline = self.data['sell_opportunity'].mean()
                            
                            if sell_wr >= sell_baseline * 1.5:
                                self.results_2way.append({
                                    'type': 'SELL',
                                    'ind1': ind1,
                                    'thresh1': thresh1,
                                    'dir1': dir1,
                                    'ind2': ind2,
                                    'thresh2': thresh2,
                                    'dir2': dir2,
                                    'success_rate': sell_wr,
                                    'signals': len(filtered_buy),
                                    'baseline': sell_baseline,
                                    'improvement': (sell_wr / sell_baseline - 1) * 100
                                })
        
        print(f"\n✅ Found {len(self.results_2way)} promising 2-way combinations")
        
    def test_3way_combinations(self, min_2way_wr=0.45):
        """Test 3-indicator combinations if 2-way achieves target WR"""
        print("\n" + "="*80)
        print("TESTING 3-WAY INDICATOR COMBINATIONS")
        print("="*80)
        
        # Check if we should proceed
        best_2way_buy = max([r for r in self.results_2way if r['type'] == 'BUY'], 
                           key=lambda x: x['success_rate'], default=None)
        best_2way_sell = max([r for r in self.results_2way if r['type'] == 'SELL'], 
                            key=lambda x: x['success_rate'], default=None)
        
        if not best_2way_buy or best_2way_buy['success_rate'] < min_2way_wr:
            print(f"⚠️  2-way BUY max WR: {best_2way_buy['success_rate']:.1%} < {min_2way_wr:.0%}")
            print("   Skipping 3-way testing - need better 2-way results first")
            return
        
        print(f"✅ 2-way BUY max WR: {best_2way_buy['success_rate']:.1%} - proceeding with 3-way")
        
        # Take top 5 2-way combinations and add third indicator
        top_2way_buy = sorted([r for r in self.results_2way if r['type'] == 'BUY'], 
                             key=lambda x: x['success_rate'], reverse=True)[:5]
        
        third_indicators = ['adx', 'cvd', 'liq_ratio', 'rsi']
        
        for combo in top_2way_buy:
            ind1, ind2 = combo['ind1'], combo['ind2']
            
            # Build 2-way mask
            if combo['dir1'] == 'above':
                mask1 = self.data[ind1] > combo['thresh1']
            else:
                mask1 = self.data[ind1] < combo['thresh1']
            
            if combo['dir2'] == 'above':
                mask2 = self.data[ind2] > combo['thresh2']
            else:
                mask2 = self.data[ind2] < combo['thresh2']
            
            base_mask = mask1 & mask2
            
            # Test adding each third indicator
            for ind3 in third_indicators:
                if ind3 in [ind1, ind2]:
                    continue
                
                for percentile in [10, 25, 50, 75, 90]:
                    thresh3 = self.data[ind3].quantile(percentile / 100)
                    
                    for dir3 in ['above', 'below']:
                        if dir3 == 'above':
                            mask3 = self.data[ind3] > thresh3
                        else:
                            mask3 = self.data[ind3] < thresh3
                        
                        filtered = self.data[base_mask & mask3]
                        
                        if len(filtered) < 150:  # Need more samples for 3-way
                            continue
                        
                        buy_wr = filtered['buy_opportunity'].mean()
                        
                        # Only save if better than 2-way result
                        if buy_wr > combo['success_rate']:
                            self.results_3way.append({
                                'type': 'BUY',
                                'ind1': ind1,
                                'thresh1': combo['thresh1'],
                                'dir1': combo['dir1'],
                                'ind2': ind2,
                                'thresh2': combo['thresh2'],
                                'dir2': combo['dir2'],
                                'ind3': ind3,
                                'thresh3': thresh3,
                                'dir3': dir3,
                                'success_rate': buy_wr,
                                'signals': len(filtered),
                                'baseline': self.data['buy_opportunity'].mean(),
                                'improvement_vs_2way': (buy_wr / combo['success_rate'] - 1) * 100
                            })
        
        print(f"\n✅ Found {len(self.results_3way)} 3-way combinations better than 2-way")
        
    def display_results(self):
        """Display and save top combinations"""
        print("\n" + "="*80)
        print("TOP 2-WAY COMBINATIONS")
        print("="*80)
        
        # BUY combinations
        buy_2way = sorted([r for r in self.results_2way if r['type'] == 'BUY'], 
                         key=lambda x: x['success_rate'], reverse=True)[:10]
        
        print(f"\n🟢 TOP 10 BUY COMBINATIONS:")
        print(f"\n{'Ind1':<20} {'Op':<6} {'Thresh':<10} {'Ind2':<20} {'Op':<6} {'Thresh':<10} {'WR':<8} {'Signals':<10} {'Lift'}")
        print("─"*120)
        
        for r in buy_2way:
            print(f"{r['ind1']:<20} {r['dir1']:<6} {r['thresh1']:<10.2f} "
                  f"{r['ind2']:<20} {r['dir2']:<6} {r['thresh2']:<10.2f} "
                  f"{r['success_rate']:<8.1%} {r['signals']:<10} +{r['improvement']:.0f}%")
        
        # SELL combinations
        sell_2way = sorted([r for r in self.results_2way if r['type'] == 'SELL'], 
                          key=lambda x: x['success_rate'], reverse=True)[:10]
        
        print(f"\n🔴 TOP 10 SELL COMBINATIONS:")
        print(f"\n{'Ind1':<20} {'Op':<6} {'Thresh':<10} {'Ind2':<20} {'Op':<6} {'Thresh':<10} {'WR':<8} {'Signals':<10} {'Lift'}")
        print("─"*120)
        
        for r in sell_2way:
            print(f"{r['ind1']:<20} {r['dir1']:<6} {r['thresh1']:<10.2f} "
                  f"{r['ind2']:<20} {r['dir2']:<6} {r['thresh2']:<10.2f} "
                  f"{r['success_rate']:<8.1%} {r['signals']:<10} +{r['improvement']:.0f}%")
        
        # 3-way results
        if self.results_3way:
            print("\n" + "="*80)
            print("TOP 3-WAY COMBINATIONS")
            print("="*80)
            
            buy_3way = sorted([r for r in self.results_3way if r['type'] == 'BUY'], 
                             key=lambda x: x['success_rate'], reverse=True)[:5]
            
            print(f"\n🟢 TOP 5 BUY 3-WAY:")
            for i, r in enumerate(buy_3way, 1):
                print(f"\n{i}. WR: {r['success_rate']:.1%} ({r['signals']} signals)")
                print(f"   {r['ind1']} {r['dir1']} {r['thresh1']:.2f}")
                print(f"   AND {r['ind2']} {r['dir2']} {r['thresh2']:.2f}")
                print(f"   AND {r['ind3']} {r['dir3']} {r['thresh3']:.2f}")
                print(f"   Improvement vs 2-way: +{r['improvement_vs_2way']:.1f}%")
        
        # Save results
        results = {
            '2way_combinations': {
                'buy': buy_2way,
                'sell': sell_2way
            },
            '3way_combinations': {
                'buy': self.results_3way
            },
            'summary': {
                'best_2way_buy_wr': buy_2way[0]['success_rate'] if buy_2way else 0,
                'best_2way_sell_wr': sell_2way[0]['success_rate'] if sell_2way else 0,
                'best_3way_buy_wr': max([r['success_rate'] for r in self.results_3way], default=0),
                'target_wr': 0.45,
                'target_achieved': buy_2way[0]['success_rate'] >= 0.45 if buy_2way else False
            }
        }
        
        with open('combination_test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to combination_test_results.json")
        
        # Final summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if buy_2way:
            best = buy_2way[0]
            print(f"\n🏆 BEST BUY COMBINATION (2-way):")
            print(f"   {best['ind1']} {best['dir1']} {best['thresh1']:.2f}")
            print(f"   AND {best['ind2']} {best['dir2']} {best['thresh2']:.2f}")
            print(f"   Success Rate: {best['success_rate']:.1%}")
            print(f"   Signals: {best['signals']}")
            print(f"   Baseline: {best['baseline']:.1%}")
            print(f"   Improvement: +{best['improvement']:.0f}%")
            
            if best['success_rate'] >= 0.45:
                print(f"\n   ✅ TARGET ACHIEVED (45%+ WR)")
            else:
                print(f"\n   ⚠️  Below 45% target - may need to adjust strategy")

def main():
    tester = CombinationTester()
    
    # Step 1: Load labeled data
    tester.load_labeled_data()
    
    # Step 2: Test 2-way combinations
    tester.test_2way_combinations()
    
    # Step 3: Test 3-way if 2-way succeeds
    tester.test_3way_combinations(min_2way_wr=0.45)
    
    # Step 4: Display results
    tester.display_results()
    
    print("\n" + "="*80)
    print("✅ COMBINATION TESTING COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
