#!/usr/bin/env python3
"""
Comprehensive Indicator Discovery Analysis
Goal: Find which indicators and combinations predict WIN signals
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from itertools import combinations
import json

class IndicatorDiscovery:
    def __init__(self):
        self.merged_data = None
        self.buy_data = None
        self.sell_data = None
        
    def load_and_merge_data(self):
        """Step 1: Load and merge effectiveness + analysis logs"""
        print("="*80)
        print("STEP 1: LOADING AND MERGING DATA")
        print("="*80)
        
        # Load effectiveness data
        eff_df = pd.read_csv('effectiveness_log.csv')
        eff_df['timestamp_sent'] = pd.to_datetime(eff_df['timestamp_sent'])
        
        # Load analysis data
        analysis_df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
        analysis_df = analysis_df[analysis_df['verdict'].isin(['BUY', 'SELL'])]
        analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'], errors='coerce')
        
        # Filter last 2 days
        cutoff = datetime.now() - timedelta(days=2)
        eff_df = eff_df[eff_df['timestamp_sent'] >= cutoff]
        analysis_df = analysis_df[analysis_df['timestamp'] >= cutoff]
        
        print(f"\n📊 Effectiveness log: {len(eff_df)} signals")
        print(f"📊 Analysis log: {len(analysis_df)} verdicts")
        
        # Merge on symbol, verdict, and close timestamp
        merged_data = []
        for idx, eff_row in eff_df.iterrows():
            time_diff = abs(analysis_df['timestamp'] - eff_row['timestamp_sent'])
            matches = analysis_df[
                (analysis_df['symbol'] == eff_row['symbol']) &
                (analysis_df['verdict'] == eff_row['verdict']) &
                (time_diff < timedelta(minutes=2))
            ]
            
            if len(matches) > 0:
                closest_match = matches.loc[time_diff[matches.index].idxmin()]
                
                merged_row = {
                    'symbol': eff_row['symbol'],
                    'verdict': eff_row['verdict'],
                    'result': eff_row['result'],
                    'confidence': eff_row['confidence'],
                    # Indicators
                    'cvd': closest_match.get('cvd', 0),
                    'oi_change_pct': closest_match.get('oi_change_pct', 0),
                    'price_vs_vwap_pct': closest_match.get('price_vs_vwap_pct', 0),
                    'volume_spike': int(closest_match.get('volume_spike', 0)),
                    'liq_ratio': closest_match.get('liq_ratio', 0),
                    'rsi': closest_match.get('rsi', 50),
                    'ema_trend': closest_match.get('ema_trend', 'neutral'),
                    'funding_rate': closest_match.get('funding_rate', 0),
                }
                merged_data.append(merged_row)
        
        self.merged_data = pd.DataFrame(merged_data)
        
        # Split into BUY and SELL
        self.buy_data = self.merged_data[self.merged_data['verdict'] == 'BUY'].copy()
        self.sell_data = self.merged_data[self.merged_data['verdict'] == 'SELL'].copy()
        
        print(f"\n✅ Merged {len(self.merged_data)} signals")
        print(f"   BUY:  {len(self.buy_data)} signals")
        print(f"   SELL: {len(self.sell_data)} signals")
        
        # Show win rates
        buy_wins = len(self.buy_data[self.buy_data['result'] == 'WIN'])
        sell_wins = len(self.sell_data[self.sell_data['result'] == 'WIN'])
        
        print(f"\n📊 Baseline Win Rates:")
        print(f"   BUY:  {buy_wins}/{len(self.buy_data)} = {buy_wins/len(self.buy_data):.1%}")
        print(f"   SELL: {sell_wins}/{len(self.sell_data)} = {sell_wins/len(self.sell_data):.1%}")
        
    def analyze_single_indicator(self, data, indicator_name, verdict_type):
        """Analyze single indicator performance"""
        if len(data) == 0:
            return None
        
        # Get indicator values
        values = data[indicator_name].values
        results = data['result'].values
        
        # Calculate correlation
        numeric_results = [1 if r == 'WIN' else 0 for r in results]
        
        # Handle different value types
        if indicator_name in ['volume_spike']:
            # Binary indicator
            spike_wr = np.mean([numeric_results[i] for i in range(len(values)) if values[i] == 1]) if np.sum(values) > 0 else 0
            no_spike_wr = np.mean([numeric_results[i] for i in range(len(values)) if values[i] == 0]) if np.sum(values == 0) > 0 else 0
            
            return {
                'name': indicator_name,
                'type': 'binary',
                'spike_wr': spike_wr,
                'no_spike_wr': no_spike_wr,
                'spike_count': int(np.sum(values)),
                'no_spike_count': int(np.sum(values == 0)),
                'improvement': spike_wr - no_spike_wr
            }
        
        elif indicator_name == 'ema_trend':
            # Categorical
            trends = data[indicator_name].unique()
            trend_stats = {}
            for trend in trends:
                mask = data[indicator_name] == trend
                trend_data = data[mask]
                wins = len(trend_data[trend_data['result'] == 'WIN'])
                total = len(trend_data)
                trend_stats[trend] = {
                    'wr': wins / total if total > 0 else 0,
                    'count': total
                }
            return {
                'name': indicator_name,
                'type': 'categorical',
                'trends': trend_stats
            }
        
        else:
            # Numeric indicator - find best threshold
            sorted_vals = np.sort(values)
            best_threshold = None
            best_wr = 0
            best_count = 0
            
            # Test various thresholds
            for percentile in [10, 25, 50, 75, 90]:
                threshold = np.percentile(sorted_vals, percentile)
                
                # Test both > and < threshold
                for direction in ['above', 'below']:
                    if direction == 'above':
                        mask = values > threshold
                    else:
                        mask = values < threshold
                    
                    if np.sum(mask) < 10:  # Need at least 10 samples
                        continue
                    
                    filtered_results = [numeric_results[i] for i in range(len(values)) if mask[i]]
                    wr = np.mean(filtered_results)
                    count = len(filtered_results)
                    
                    if wr > best_wr and count >= 10:
                        best_wr = wr
                        best_threshold = threshold
                        best_count = count
                        best_direction = direction
            
            # Correlation
            try:
                correlation = np.corrcoef(values, numeric_results)[0, 1]
            except:
                correlation = 0
            
            return {
                'name': indicator_name,
                'type': 'numeric',
                'correlation': correlation,
                'best_threshold': best_threshold,
                'best_direction': best_direction if best_threshold else None,
                'best_wr': best_wr,
                'best_count': best_count,
                'mean': np.mean(values),
                'std': np.std(values)
            }
    
    def univariate_analysis(self):
        """Step 2: Test each indicator individually"""
        print("\n" + "="*80)
        print("STEP 2: UNIVARIATE INDICATOR ANALYSIS")
        print("="*80)
        
        indicators = ['cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'volume_spike', 
                     'liq_ratio', 'rsi', 'ema_trend', 'funding_rate']
        
        # BUY analysis
        print(f"\n{'='*80}")
        print("BUY SIGNALS - Individual Indicator Performance")
        print(f"{'='*80}")
        print(f"Baseline WR: {len(self.buy_data[self.buy_data['result']=='WIN'])/len(self.buy_data):.1%}\n")
        
        buy_results = []
        for indicator in indicators:
            result = self.analyze_single_indicator(self.buy_data, indicator, 'BUY')
            if result:
                buy_results.append(result)
        
        # Sort by effectiveness
        buy_results_sorted = sorted(
            [r for r in buy_results if r['type'] == 'numeric'],
            key=lambda x: x.get('best_wr', 0),
            reverse=True
        )
        
        print(f"{'Indicator':<20} {'Correlation':<12} {'Best WR':<10} {'@ Threshold':<15} {'Direction':<10} {'Signals'}")
        print("-"*80)
        for r in buy_results_sorted:
            print(f"{r['name']:<20} {r['correlation']:>+.3f}       "
                  f"{r['best_wr']:<10.1%} {r['best_threshold']:>15.2f} {r['best_direction']:<10} {r['best_count']}")
        
        # Binary indicators
        binary_results = [r for r in buy_results if r['type'] == 'binary']
        if binary_results:
            print(f"\nBinary Indicators:")
            for r in binary_results:
                print(f"  {r['name']}: Spike WR={r['spike_wr']:.1%} ({r['spike_count']} sig) vs "
                      f"No-Spike WR={r['no_spike_wr']:.1%} ({r['no_spike_count']} sig)")
        
        # SELL analysis
        print(f"\n{'='*80}")
        print("SELL SIGNALS - Individual Indicator Performance")
        print(f"{'='*80}")
        print(f"Baseline WR: {len(self.sell_data[self.sell_data['result']=='WIN'])/len(self.sell_data):.1%}\n")
        
        sell_results = []
        for indicator in indicators:
            result = self.analyze_single_indicator(self.sell_data, indicator, 'SELL')
            if result:
                sell_results.append(result)
        
        sell_results_sorted = sorted(
            [r for r in sell_results if r['type'] == 'numeric'],
            key=lambda x: x.get('best_wr', 0),
            reverse=True
        )
        
        print(f"{'Indicator':<20} {'Correlation':<12} {'Best WR':<10} {'@ Threshold':<15} {'Direction':<10} {'Signals'}")
        print("-"*80)
        for r in sell_results_sorted:
            print(f"{r['name']:<20} {r['correlation']:>+.3f}       "
                  f"{r['best_wr']:<10.1%} {r['best_threshold']:>15.2f} {r['best_direction']:<10} {r['best_count']}")
        
        binary_results = [r for r in sell_results if r['type'] == 'binary']
        if binary_results:
            print(f"\nBinary Indicators:")
            for r in binary_results:
                print(f"  {r['name']}: Spike WR={r['spike_wr']:.1%} ({r['spike_count']} sig) vs "
                      f"No-Spike WR={r['no_spike_wr']:.1%} ({r['no_spike_count']} sig)")
        
        return {'buy': buy_results, 'sell': sell_results}
    
    def test_indicator_combination(self, data, indicators, thresholds):
        """Test a specific combination of indicators with thresholds"""
        if len(data) == 0:
            return None
        
        # Apply all filters
        mask = np.ones(len(data), dtype=bool)
        
        for indicator, threshold_info in zip(indicators, thresholds):
            values = data[indicator].values
            threshold = threshold_info['value']
            direction = threshold_info['direction']
            
            if direction == 'above':
                mask &= (values > threshold)
            elif direction == 'below':
                mask &= (values < threshold)
            elif direction == 'equals':
                mask &= (values == threshold)
        
        filtered_data = data[mask]
        
        if len(filtered_data) < 10:  # Need minimum samples
            return None
        
        wins = len(filtered_data[filtered_data['result'] == 'WIN'])
        total = len(filtered_data)
        wr = wins / total if total > 0 else 0
        
        return {
            'indicators': indicators,
            'thresholds': thresholds,
            'wr': wr,
            'signals': total,
            'wins': wins
        }
    
    def combination_search(self, max_combinations=3):
        """Step 3: Test indicator combinations"""
        print("\n" + "="*80)
        print(f"STEP 3: TESTING INDICATOR COMBINATIONS (up to {max_combinations})")
        print("="*80)
        
        indicators = ['cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'liq_ratio', 'rsi']
        
        # Simplified: test top combinations based on univariate analysis
        print("\nTesting 2-indicator combinations...")
        
        buy_combos = []
        sell_combos = []
        
        # For BUY signals
        for combo in combinations(indicators, 2):
            # Define simple thresholds (can be optimized)
            thresholds = []
            for ind in combo:
                if ind == 'cvd':
                    thresholds.append({'value': 50_000_000, 'direction': 'above'})
                elif ind == 'oi_change_pct':
                    thresholds.append({'value': 0, 'direction': 'above'})
                elif ind == 'price_vs_vwap_pct':
                    thresholds.append({'value': -0.5, 'direction': 'below'})
                elif ind == 'liq_ratio':
                    thresholds.append({'value': 1.0, 'direction': 'above'})
                elif ind == 'rsi':
                    thresholds.append({'value': 30, 'direction': 'above'})
            
            result = self.test_indicator_combination(self.buy_data, combo, thresholds)
            if result and result['signals'] >= 10:
                buy_combos.append(result)
        
        # For SELL signals
        for combo in combinations(indicators, 2):
            thresholds = []
            for ind in combo:
                if ind == 'cvd':
                    thresholds.append({'value': -50_000_000, 'direction': 'below'})
                elif ind == 'oi_change_pct':
                    thresholds.append({'value': 0, 'direction': 'above'})
                elif ind == 'price_vs_vwap_pct':
                    thresholds.append({'value': 0.5, 'direction': 'above'})
                elif ind == 'liq_ratio':
                    thresholds.append({'value': 1.0, 'direction': 'below'})
                elif ind == 'rsi':
                    thresholds.append({'value': 70, 'direction': 'below'})
            
            result = self.test_indicator_combination(self.sell_data, combo, thresholds)
            if result and result['signals'] >= 10:
                sell_combos.append(result)
        
        # Sort and display top results
        buy_combos_sorted = sorted(buy_combos, key=lambda x: x['wr'], reverse=True)
        sell_combos_sorted = sorted(sell_combos, key=lambda x: x['wr'], reverse=True)
        
        print(f"\n{'='*80}")
        print("TOP BUY COMBINATIONS")
        print(f"{'='*80}")
        print(f"{'Indicators':<40} {'Win Rate':<12} {'Signals':<10}")
        print("-"*80)
        for combo in buy_combos_sorted[:10]:
            indicators_str = " + ".join(combo['indicators'])
            print(f"{indicators_str:<40} {combo['wr']:<12.1%} {combo['signals']:<10}")
        
        print(f"\n{'='*80}")
        print("TOP SELL COMBINATIONS")
        print(f"{'='*80}")
        print(f"{'Indicators':<40} {'Win Rate':<12} {'Signals':<10}")
        print("-"*80)
        for combo in sell_combos_sorted[:10]:
            indicators_str = " + ".join(combo['indicators'])
            print(f"{indicators_str:<40} {combo['wr']:<12.1%} {combo['signals']:<10}")
        
        return {'buy': buy_combos_sorted, 'sell': sell_combos_sorted}
    
    def generate_report(self, univariate_results, combination_results):
        """Step 4: Generate final recommendations"""
        print("\n" + "="*80)
        print("FINAL RECOMMENDATIONS")
        print("="*80)
        
        # Best single indicators
        print("\n📊 BEST SINGLE INDICATORS:")
        
        buy_numeric = [r for r in univariate_results['buy'] if r['type'] == 'numeric']
        buy_best = sorted(buy_numeric, key=lambda x: x.get('best_wr', 0), reverse=True)[0]
        
        print(f"\nBUY:  {buy_best['name']}")
        print(f"      WR: {buy_best['best_wr']:.1%} ({buy_best['best_count']} signals)")
        print(f"      Threshold: {buy_best['best_direction']} {buy_best['best_threshold']:.2f}")
        
        sell_numeric = [r for r in univariate_results['sell'] if r['type'] == 'numeric']
        sell_best = sorted(sell_numeric, key=lambda x: x.get('best_wr', 0), reverse=True)[0]
        
        print(f"\nSELL: {sell_best['name']}")
        print(f"      WR: {sell_best['best_wr']:.1%} ({sell_best['best_count']} signals)")
        print(f"      Threshold: {sell_best['best_direction']} {sell_best['best_threshold']:.2f}")
        
        # Best combinations
        print(f"\n📊 BEST COMBINATIONS:")
        
        if len(combination_results['buy']) > 0:
            buy_combo = combination_results['buy'][0]
            print(f"\nBUY:  {' + '.join(buy_combo['indicators'])}")
            print(f"      WR: {buy_combo['wr']:.1%} ({buy_combo['signals']} signals)")
        
        if len(combination_results['sell']) > 0:
            sell_combo = combination_results['sell'][0]
            print(f"\nSELL: {' + '.join(sell_combo['indicators'])}")
            print(f"      WR: {sell_combo['wr']:.1%} ({sell_combo['signals']} signals)")
        
        # Save results
        results = {
            'univariate': univariate_results,
            'combinations': {
                'buy': [
                    {
                        'indicators': c['indicators'],
                        'wr': float(c['wr']),
                        'signals': int(c['signals'])
                    } for c in combination_results['buy'][:10]
                ],
                'sell': [
                    {
                        'indicators': c['indicators'],
                        'wr': float(c['wr']),
                        'signals': int(c['signals'])
                    } for c in combination_results['sell'][:10]
                ]
            }
        }
        
        with open('indicator_discovery_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to indicator_discovery_results.json")

def main():
    analyzer = IndicatorDiscovery()
    
    # Step 1: Load data
    analyzer.load_and_merge_data()
    
    # Step 2: Univariate analysis
    univariate_results = analyzer.univariate_analysis()
    
    # Step 3: Combination search
    combination_results = analyzer.combination_search()
    
    # Step 4: Generate report
    analyzer.generate_report(univariate_results, combination_results)
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
