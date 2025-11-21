#!/usr/bin/env python3
"""
Forward Opportunity Finder - using existing analysis_log.csv data
Find which indicator patterns precede >0.5% price movements within 30 minutes
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class OpportunityFinder:
    def __init__(self):
        self.data = None
        self.opportunities = None
        
    def load_analysis_data(self):
        """Load and prepare analysis_log.csv"""
        print("="*80)
        print("LOADING ANALYSIS DATA")
        print("="*80)
        
        df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values(['symbol', 'timestamp'])
        
        # Filter last 7 days
        cutoff = datetime.now() - timedelta(days=7)
        df = df[df['timestamp'] >= cutoff]
        
        print(f"\n📊 Loaded {len(df)} entries from last 7 days")
        print(f"📊 Symbols: {df['symbol'].nunique()}")
        print(f"📊 Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        self.data = df
        
    def label_forward_opportunities(self):
        """For each entry, check if price moved >0.5% in next 30min"""
        print("\n" + "="*80)
        print("LABELING FORWARD PRICE MOVEMENTS")
        print("="*80)
        
        opportunities = []
        
        for symbol in self.data['symbol'].unique():
            symbol_data = self.data[self.data['symbol'] == symbol].copy()
            symbol_data = symbol_data.reset_index(drop=True)
            
            for i in range(len(symbol_data)):
                current_row = symbol_data.iloc[i]
                current_price = current_row.get('price', 0)
                current_time = current_row['timestamp']
                
                if current_price == 0:
                    continue
                
                # Look ahead 30 minutes (6 candles at 5min intervals)
                future_time = current_time + timedelta(minutes=30)
                future_data = symbol_data[
                    (symbol_data['timestamp'] > current_time) &
                    (symbol_data['timestamp'] <= future_time)
                ]
                
                if len(future_data) < 3:  # Need at least some future data
                    continue
                
                # Find max and min prices in next 30min
                max_high = future_data['price'].max()
                min_low = future_data['price'].min()
                
                # Calculate movements
                max_gain_pct = (max_high - current_price) / current_price * 100
                max_drawdown_pct = (current_price - min_low) / current_price * 100
                
                # BUY opportunity: >0.5% gain, <=0.5% drawdown
                buy_opp = (max_gain_pct >= 0.5) and (max_drawdown_pct <= 0.5)
                
                # SELL opportunity: >0.5% drop, <=0.5% bounce
                sell_opp = (max_drawdown_pct >= 0.5) and (max_gain_pct <= 0.5)
                
                # Store result
                opp = {
                    'timestamp': current_time,
                    'symbol': symbol,
                    'price': current_price,
                    'buy_opportunity': buy_opp,
                    'sell_opportunity': sell_opp,
                    'max_gain_30min': max_gain_pct,
                    'max_drawdown_30min': max_drawdown_pct,
                    # Indicators
                    'cvd': current_row.get('cvd', 0),
                    'oi_change_pct': current_row.get('oi_change_pct', 0),
                    'price_vs_vwap_pct': current_row.get('price_vs_vwap_pct', 0),
                    'volume_spike': int(current_row.get('volume_spike', 0)),
                    'liq_ratio': current_row.get('liq_ratio', 0),
                    'rsi': current_row.get('rsi', 50),
                    'adx': current_row.get('adx', 0),
                    'funding_rate': current_row.get('funding_rate', 0),
                }
                opportunities.append(opp)
        
        if not opportunities:
            print("⚠️  No opportunities found!")
            self.opportunities = pd.DataFrame()
            return
        
        self.opportunities = pd.DataFrame(opportunities)
        
        # Statistics
        total = len(self.opportunities)
        buy_count = self.opportunities['buy_opportunity'].sum()
        sell_count = self.opportunities['sell_opportunity'].sum()
        
        print(f"\n📊 Total candles analyzed: {total:,}")
        print(f"🟢 BUY opportunities: {buy_count:,} ({buy_count/total*100:.1f}%)")
        print(f"🔴 SELL opportunities: {sell_count:,} ({sell_count/total*100:.1f}%)")
        
        # Show some stats
        print(f"\n📈 Average movements:")
        print(f"   Max gain in 30min: {self.opportunities['max_gain_30min'].mean():.2f}%")
        print(f"   Max drawdown in 30min: {self.opportunities['max_drawdown_30min'].mean():.2f}%")
        
    def find_predictive_patterns(self):
        """Find which indicator combinations predict opportunities"""
        print("\n" + "="*80)
        print("FINDING PREDICTIVE PATTERNS")
        print("="*80)
        
        indicators = ['cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'liq_ratio', 'rsi', 'adx']
        
        # === BUY OPPORTUNITIES ===
        print(f"\n{'='*80}")
        print("BUY OPPORTUNITY PREDICTORS")
        print(f"{'='*80}")
        print(f"Baseline: {self.opportunities['buy_opportunity'].mean():.1%}\n")
        print(f"{'Indicator':<20} {'Threshold':<15} {'Direction':<10} {'Success Rate':<15} {'Signals'}")
        print("-"*80)
        
        buy_patterns = []
        
        for indicator in indicators:
            # Try different thresholds
            for percentile in [10, 25, 50, 75, 90]:
                threshold = self.opportunities[indicator].quantile(percentile / 100)
                
                for direction in ['above', 'below']:
                    if direction == 'above':
                        mask = self.opportunities[indicator] > threshold
                    else:
                        mask = self.opportunities[indicator] < threshold
                    
                    filtered = self.opportunities[mask]
                    
                    if len(filtered) < 100:  # Need minimum sample size
                        continue
                    
                    success_rate = filtered['buy_opportunity'].mean()
                    
                    if success_rate > self.opportunities['buy_opportunity'].mean() * 1.2:  # At least 20% better
                        buy_patterns.append({
                            'indicator': indicator,
                            'threshold': threshold,
                            'direction': direction,
                            'success_rate': success_rate,
                            'signals': len(filtered)
                        })
        
        # Sort and display top patterns
        buy_patterns_sorted = sorted(buy_patterns, key=lambda x: x['success_rate'], reverse=True)
        
        for pattern in buy_patterns_sorted[:20]:
            print(f"{pattern['indicator']:<20} {pattern['threshold']:<15.2f} "
                  f"{pattern['direction']:<10} {pattern['success_rate']:<15.1%} {pattern['signals']}")
        
        # === SELL OPPORTUNITIES ===
        print(f"\n{'='*80}")
        print("SELL OPPORTUNITY PREDICTORS")
        print(f"{'='*80}")
        print(f"Baseline: {self.opportunities['sell_opportunity'].mean():.1%}\n")
        print(f"{'Indicator':<20} {'Threshold':<15} {'Direction':<10} {'Success Rate':<15} {'Signals'}")
        print("-"*80)
        
        sell_patterns = []
        
        for indicator in indicators:
            for percentile in [10, 25, 50, 75, 90]:
                threshold = self.opportunities[indicator].quantile(percentile / 100)
                
                for direction in ['above', 'below']:
                    if direction == 'above':
                        mask = self.opportunities[indicator] > threshold
                    else:
                        mask = self.opportunities[indicator] < threshold
                    
                    filtered = self.opportunities[mask]
                    
                    if len(filtered) < 100:
                        continue
                    
                    success_rate = filtered['sell_opportunity'].mean()
                    
                    if success_rate > self.opportunities['sell_opportunity'].mean() * 1.2:
                        sell_patterns.append({
                            'indicator': indicator,
                            'threshold': threshold,
                            'direction': direction,
                            'success_rate': success_rate,
                            'signals': len(filtered)
                        })
        
        sell_patterns_sorted = sorted(sell_patterns, key=lambda x: x['success_rate'], reverse=True)
        
        for pattern in sell_patterns_sorted[:20]:
            print(f"{pattern['indicator']:<20} {pattern['threshold']:<15.2f} "
                  f"{pattern['direction']:<10} {pattern['success_rate']:<15.1%} {pattern['signals']}")
        
        # Save results
        results = {
            'buy_patterns': buy_patterns_sorted[:30],
            'sell_patterns': sell_patterns_sorted[:30],
            'statistics': {
                'total_candles': len(self.opportunities),
                'buy_opportunities': int(self.opportunities['buy_opportunity'].sum()),
                'sell_opportunities': int(self.opportunities['sell_opportunity'].sum()),
                'buy_baseline': float(self.opportunities['buy_opportunity'].mean()),
                'sell_baseline': float(self.opportunities['sell_opportunity'].mean())
            }
        }
        
        with open('opportunity_patterns.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to opportunity_patterns.json")
        
        # Final summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        if buy_patterns_sorted:
            best_buy = buy_patterns_sorted[0]
            print(f"\n🏆 BEST BUY PREDICTOR:")
            print(f"   {best_buy['indicator']}: {best_buy['direction']} {best_buy['threshold']:.2f}")
            print(f"   Success rate: {best_buy['success_rate']:.1%} ({best_buy['signals']} signals)")
            print(f"   Baseline: {self.opportunities['buy_opportunity'].mean():.1%}")
            print(f"   Improvement: {(best_buy['success_rate'] / self.opportunities['buy_opportunity'].mean() - 1) * 100:.1f}%")
        
        if sell_patterns_sorted:
            best_sell = sell_patterns_sorted[0]
            print(f"\n🏆 BEST SELL PREDICTOR:")
            print(f"   {best_sell['indicator']}: {best_sell['direction']} {best_sell['threshold']:.2f}")
            print(f"   Success rate: {best_sell['success_rate']:.1%} ({best_sell['signals']} signals)")
            print(f"   Baseline: {self.opportunities['sell_opportunity'].mean():.1%}")
            print(f"   Improvement: {(best_sell['success_rate'] / self.opportunities['sell_opportunity'].mean() - 1) * 100:.1f}%")

def main():
    finder = OpportunityFinder()
    
    # Step 1: Load data
    finder.load_analysis_data()
    
    # Step 2: Label opportunities
    finder.label_forward_opportunities()
    
    # Step 3: Find patterns
    finder.find_predictive_patterns()
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
