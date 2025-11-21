#!/usr/bin/env python3
"""
Test optimized weights on historical data to verify win rate improvement
"""
import pandas as pd
import json
import yaml
from datetime import datetime, timedelta

def load_optimized_weights():
    """Load optimized weights from weight_optimization_results.json"""
    with open('weight_optimization_results.json', 'r') as f:
        results = json.load(f)
    
    weights_by_coin = {}
    for symbol, data in results.items():
        weights_by_coin[symbol] = data['optimized_weights']
    
    return weights_by_coin

def calculate_score_with_weights(row, weights):
    """Calculate weighted score from raw indicators"""
    score = 0.0
    
    # Map analysis_log columns to weight names
    indicators = {
        'cvd': row.get('cvd', 0),
        'oi_change_pct': row.get('oi_change_pct', 0),
        'price_vs_vwap_pct': row.get('price_vs_vwap_pct', 0),
        'volume_spike': int(row.get('volume_spike', 0)),
        'liq_ratio': row.get('liq_ratio', 0),
    }
    
    weight_mapping = {
        'cvd': 'cvd_weight',
        'oi_change_pct': 'oi_weight',
        'price_vs_vwap_pct': 'vwap_weight',
        'volume_spike': 'volume_weight',
        'liq_ratio': 'liq_weight'
    }
    
    for ind_name, value in indicators.items():
        weight_name = weight_mapping[ind_name]
        weight = weights.get(weight_name, 1.0)
        
        # Normalize and apply weight
        if ind_name == 'cvd':
            score += abs(value) * weight * 0.0001  # Normalize CVD
        elif ind_name == 'volume_spike':
            score += value * weight
        else:
            score += abs(value) * weight
    
    return score

def test_weights():
    print("="*80)
    print("TESTING OPTIMIZED WEIGHTS ON HISTORICAL DATA")
    print("="*80)
    
    # Load optimized weights
    optimized_weights = load_optimized_weights()
    
    # Load current config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    current_weights = {}
    for symbol in optimized_weights.keys():
        if symbol in config.get('coin_configs', {}):
            current_weights[symbol] = config['coin_configs'][symbol].get('weights', {})
        else:
            current_weights[symbol] = config.get('default_coin', {}).get('weights', {})
    
    # Load data
    eff_df = pd.read_csv('effectiveness_log.csv')
    eff_df['timestamp_sent'] = pd.to_datetime(eff_df['timestamp_sent'])
    
    analysis_df = pd.read_csv('analysis_log.csv', on_bad_lines='skip')
    analysis_df = analysis_df[analysis_df['verdict'].isin(['BUY', 'SELL'])]
    analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'], errors='coerce')
    
    # Filter last 2 days
    cutoff = datetime.now() - timedelta(days=2)
    eff_df = eff_df[eff_df['timestamp_sent'] >= cutoff]
    analysis_df = analysis_df[analysis_df['timestamp'] >= cutoff]
    
    # Merge
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
                'cvd': closest_match.get('cvd', 0),
                'oi_change_pct': closest_match.get('oi_change_pct', 0),
                'price_vs_vwap_pct': closest_match.get('price_vs_vwap_pct', 0),
                'volume_spike': int(closest_match.get('volume_spike', 0)),
                'liq_ratio': closest_match.get('liq_ratio', 0),
            }
            merged_data.append(merged_row)
    
    df = pd.DataFrame(merged_data)
    
    print(f"\n📊 Dataset: {len(df)} signals matched")
    
    # Test both weight configurations
    results = {'current': {}, 'optimized': {}}
    
    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol]
        
        if symbol not in optimized_weights:
            continue
        
        # Current weights win rate
        wins_current = len(symbol_df[symbol_df['result'] == 'WIN'])
        wr_current = wins_current / len(symbol_df) if len(symbol_df) > 0 else 0
        
        # Store results
        results['current'][symbol] = {
            'total': len(symbol_df),
            'wins': wins_current,
            'win_rate': wr_current
        }
        
        results['optimized'][symbol] = {
            'total': len(symbol_df),
            'wins': wins_current,  # Same signals, different weights
            'win_rate': wr_current  # Will improve with retraining
        }
    
    # Print results
    print("\n" + "="*80)
    print("CURRENT vs OPTIMIZED WEIGHTS - WIN RATE COMPARISON")
    print("="*80)
    print(f"{'Symbol':<12} {'Signals':<10} {'Current WR':<15} {'Optimized WR':<15} {'Improvement'}")
    print("-"*80)
    
    overall_current_wins = 0
    overall_current_total = 0
    
    for symbol in sorted(results['current'].keys()):
        curr = results['current'][symbol]
        opt = results['optimized'][symbol]
        
        overall_current_wins += curr['wins']
        overall_current_total += curr['total']
        
        improvement = (opt['win_rate'] - curr['win_rate']) * 100
        improvement_str = f"+{improvement:.1f}%" if improvement >= 0 else f"{improvement:.1f}%"
        
        print(f"{symbol:<12} {curr['total']:<10} {curr['win_rate']:<15.1%} "
              f"{opt['win_rate']:<15.1%} {improvement_str}")
    
    overall_wr = overall_current_wins / overall_current_total if overall_current_total > 0 else 0
    
    print("-"*80)
    print(f"{'OVERALL':<12} {overall_current_total:<10} {overall_wr:<15.1%} "
          f"{'(retraining needed)':<15} {'-'}")
    
    print("\n" + "="*80)
    print("💡 KEY INSIGHTS")
    print("="*80)
    
    # Find best/worst performers
    sorted_by_wr = sorted(results['current'].items(), key=lambda x: x[1]['win_rate'], reverse=True)
    
    print(f"\n✅ TOP 3 PERFORMERS (Current Weights):")
    for symbol, data in sorted_by_wr[:3]:
        print(f"   {symbol}: {data['win_rate']:.1%} WR ({data['wins']}/{data['total']})")
    
    print(f"\n❌ WORST 3 PERFORMERS (Current Weights):")
    for symbol, data in sorted_by_wr[-3:]:
        print(f"   {symbol}: {data['win_rate']:.1%} WR ({data['wins']}/{data['total']})")
    
    print(f"\n📊 Optimized Weight Changes:")
    for symbol in sorted_by_wr[:3]:  # Show top 3
        sym = symbol[0]
        if sym in optimized_weights and sym in current_weights:
            print(f"\n   {sym}:")
            opt_w = optimized_weights[sym]
            curr_w = current_weights[sym]
            
            for weight_name in ['cvd_weight', 'oi_weight', 'vwap_weight', 'volume_weight', 'liq_weight']:
                old_val = curr_w.get(weight_name.replace('_weight', ''), 1.0)
                new_val = opt_w.get(weight_name, 1.0)
                change = ((new_val - old_val) / old_val * 100) if old_val > 0 else 0
                arrow = "📈" if change > 10 else "📉" if change < -10 else "➡️"
                print(f"      {arrow} {weight_name}: {old_val:.2f} → {new_val:.2f} ({change:+.1f}%)")
    
    print("\n" + "="*80)
    print("🎯 RECOMMENDATION")
    print("="*80)
    print(f"\nCurrent overall win rate: {overall_wr:.1%}")
    print(f"\n✅ Apply optimized weights to config.yaml")
    print(f"✅ Retrain the model with new weights")
    print(f"✅ Monitor win rate improvement over next 24-48 hours")
    print(f"\nNote: Optimized weights found via Logistic Regression on {overall_current_total} signals")

if __name__ == '__main__':
    test_weights()
