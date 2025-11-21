#!/usr/bin/env python3
"""
Backtest dev_sigma threshold sets to find optimal per-symbol thresholds.

Tests 3 threshold sets (A, B, C) on historical signal data:
- A: block<0.25, boost_start>1.8
- B: block<0.30, boost_start>2.0 (current)
- C: block<0.40, boost_start>2.2

Metrics: win_rate, profit_factor, avg_time_to_outcome, blocked_share
Selection: best profit_factor (tie-breaker: win_rate)
"""

import pandas as pd
import yaml
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Threshold sets to test
THRESHOLD_SETS = {
    'A': {'block': 0.25, 'boost_start': 1.8},
    'B': {'block': 0.30, 'boost_start': 2.0},  # Current
    'C': {'block': 0.40, 'boost_start': 2.2}
}

def smooth_boost(dev_sigma):
    """Calculate smooth confidence boost: max(0.0, min(0.20, (dev_sigma - 1.0) / 3.0))"""
    return max(0.0, min(0.20, (dev_sigma - 1.0) / 3.0))

def load_historical_data(days=30):
    """Load effectiveness log with dev_sigma from analysis log backup."""
    try:
        # Load effectiveness log (has outcomes)
        eff_df = pd.read_csv('effectiveness_log.csv', parse_dates=['timestamp_sent', 'timestamp_checked'])
        
        # Load analysis log backup (has dev_sigma values)
        # Try multiple backup files
        import glob
        backup_files = sorted(glob.glob('analysis_log_backup_*.csv'), reverse=True)
        
        if backup_files:
            analysis_df = pd.read_csv(backup_files[0], parse_dates=['timestamp'], low_memory=False, on_bad_lines='skip')
            print(f"[BACKTEST] Loaded analysis backup: {backup_files[0]}")
        else:
            print("[BACKTEST] No backup found, using current analysis_log.csv")
            analysis_df = pd.read_csv('analysis_log.csv', parse_dates=['timestamp'], low_memory=False)
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        eff_df = eff_df[eff_df['timestamp_sent'] >= cutoff_date]
        
        # Merge on symbol, timestamp (within 1 minute tolerance)
        merged = []
        for _, eff_row in eff_df.iterrows():
            # Find matching analysis entry
            symbol = eff_row['symbol']
            ts = eff_row['timestamp_sent']
            
            # Look for analysis within 1 minute of signal timestamp
            analysis_match = analysis_df[
                (analysis_df['symbol'] == symbol) &
                (analysis_df['timestamp'] >= ts - timedelta(minutes=1)) &
                (analysis_df['timestamp'] <= ts + timedelta(minutes=1))
            ]
            
            if not analysis_match.empty:
                # Take the closest match
                analysis_match = analysis_match.iloc[0]
                row_data = eff_row.to_dict()
                row_data['dev_sigma'] = analysis_match.get('dev_sigma', 0.0)
                row_data['vwap_sigma'] = analysis_match.get('vwap_sigma', 0.0)
                row_data['original_confidence'] = eff_row['confidence']
                merged.append(row_data)
        
        result_df = pd.DataFrame(merged)
        print(f"[BACKTEST] Loaded {len(result_df)} signals with dev_sigma from last {days} days")
        return result_df
    
    except Exception as e:
        print(f"[BACKTEST] Error loading data: {e}")
        return pd.DataFrame()

def simulate_threshold_set(df, threshold_set_name, block_threshold, boost_start):
    """Simulate a threshold set on the data."""
    results = defaultdict(lambda: {
        'total_signals': 0,
        'blocked': 0,
        'traded_signals': 0,
        'wins': 0,
        'losses': 0,
        'cancelled': 0,
        'total_profit': 0.0,
        'total_loss': 0.0,
        'durations': []
    })
    
    for _, row in df.iterrows():
        symbol = row['symbol']
        dev_sigma = row.get('dev_sigma', 0.0)
        result = row['result']
        profit_pct = row.get('profit_pct', 0.0)
        duration = row.get('duration_actual', 0)
        
        results[symbol]['total_signals'] += 1
        
        # Check if this signal would be blocked
        if dev_sigma < block_threshold:
            results[symbol]['blocked'] += 1
            continue  # This signal would not have been sent
        
        # Signal would be traded
        results[symbol]['traded_signals'] += 1
        
        # Calculate adjusted confidence with smooth boost
        boost = smooth_boost(dev_sigma)
        # Note: We don't re-evaluate if signal would pass threshold with boosted confidence
        # We only track if the ORIGINAL signal would have been blocked
        
        # Record outcome
        if result == 'WIN':
            results[symbol]['wins'] += 1
            results[symbol]['total_profit'] += profit_pct
        elif result == 'LOSS':
            results[symbol]['losses'] += 1
            results[symbol]['total_loss'] += abs(profit_pct)
        elif result == 'CANCELLED':
            results[symbol]['cancelled'] += 1
        
        results[symbol]['durations'].append(duration)
    
    # Calculate metrics per symbol
    metrics = {}
    for symbol, data in results.items():
        traded = data['traded_signals']
        wins = data['wins']
        losses = data['losses']
        total = data['total_signals']
        
        # Win rate (wins / traded_signals excluding cancelled)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
        
        # Profit factor (total_profit / total_loss)
        profit_factor = data['total_profit'] / data['total_loss'] if data['total_loss'] > 0 else (
            float('inf') if data['total_profit'] > 0 else 1.0
        )
        
        # Average time to outcome
        avg_duration = sum(data['durations']) / len(data['durations']) if data['durations'] else 0.0
        
        # Blocked share
        blocked_share = data['blocked'] / total if total > 0 else 0.0
        
        metrics[symbol] = {
            'threshold_set': threshold_set_name,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_time_to_outcome': avg_duration,
            'blocked_share': blocked_share,
            'total_signals': total,
            'traded_signals': traded,
            'blocked': data['blocked'],
            'wins': wins,
            'losses': losses,
            'cancelled': data['cancelled']
        }
    
    return metrics

def select_best_thresholds(all_metrics):
    """Select best threshold set per symbol based on profit_factor (tie: win_rate)."""
    best_per_symbol = {}
    
    # Get all symbols
    symbols = set()
    for metrics_dict in all_metrics.values():
        symbols.update(metrics_dict.keys())
    
    for symbol in symbols:
        candidates = []
        for set_name, metrics_dict in all_metrics.items():
            if symbol in metrics_dict:
                m = metrics_dict[symbol]
                candidates.append({
                    'set': set_name,
                    'profit_factor': m['profit_factor'],
                    'win_rate': m['win_rate'],
                    'metrics': m
                })
        
        if not candidates:
            continue
        
        # Sort by profit_factor DESC, then win_rate DESC
        # Handle inf profit_factor
        candidates.sort(key=lambda x: (
            x['profit_factor'] if x['profit_factor'] != float('inf') else 999999,
            x['win_rate']
        ), reverse=True)
        
        best = candidates[0]
        best_per_symbol[symbol] = {
            'set': best['set'],
            'thresholds': THRESHOLD_SETS[best['set']],
            'metrics': best['metrics']
        }
    
    return best_per_symbol

def update_config_with_thresholds(best_thresholds, config_file='config.yaml'):
    """Update config.yaml with optimized thresholds per symbol."""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    coin_configs = config.get('coin_configs', {})
    
    # Update each symbol's configuration
    for symbol_name, data in best_thresholds.items():
        if symbol_name not in coin_configs:
            coin_configs[symbol_name] = {}
        
        coin_configs[symbol_name]['dev_sigma_thresholds'] = {
            'block_below': data['thresholds']['block'],
            'boost_above': data['thresholds']['boost_start'],
            'optimized_set': data['set']
        }
    
    config['coin_configs'] = coin_configs
    
    # Write back to config
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"[BACKTEST] Updated {config_file} with optimized thresholds")

def main():
    """Run backtest and optimize thresholds."""
    print("="*70)
    print("DEV_SIGMA THRESHOLD OPTIMIZATION")
    print("="*70)
    
    # Load historical data
    df = load_historical_data(days=30)
    
    if df.empty:
        print("[BACKTEST] No data available for backtesting!")
        return
    
    # Check if dev_sigma is available
    if 'dev_sigma' not in df.columns or df['dev_sigma'].isna().all() or (df['dev_sigma'] == 0).all():
        print("[BACKTEST] WARNING: No dev_sigma data found in historical signals!")
        print("[BACKTEST] This is expected for newly implemented features.")
        print("[BACKTEST] Initializing all symbols with default Set B thresholds.")
        print("[BACKTEST] Re-run this script after collecting 30+ days of data.")
        
        # Initialize config with default Set B thresholds
        default_thresholds = THRESHOLD_SETS['B']
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Add default thresholds to all monitored symbols
        symbols = config.get('symbols', [])
        coin_configs = config.get('coin_configs', {})
        
        for symbol in symbols:
            if symbol not in coin_configs:
                coin_configs[symbol] = {}
            
            coin_configs[symbol]['dev_sigma_thresholds'] = {
                'block_below': default_thresholds['block'],
                'boost_above': default_thresholds['boost_start'],
                'optimized_set': 'B_default'
            }
        
        config['coin_configs'] = coin_configs
        
        # Write back
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"[BACKTEST] Initialized {len(symbols)} symbols with Set B defaults")
        print(f"[BACKTEST] block_below: {default_thresholds['block']}")
        print(f"[BACKTEST] boost_above: {default_thresholds['boost_start']}")
        return
    
    # Simulate each threshold set
    all_metrics = {}
    
    print("\n" + "="*70)
    print("SIMULATING THRESHOLD SETS")
    print("="*70)
    
    for set_name, thresholds in THRESHOLD_SETS.items():
        print(f"\n[{set_name}] Testing: block<{thresholds['block']}, boost>{thresholds['boost_start']}")
        metrics = simulate_threshold_set(
            df, 
            set_name, 
            thresholds['block'], 
            thresholds['boost_start']
        )
        all_metrics[set_name] = metrics
        
        # Print summary
        print(f"  Symbols tested: {len(metrics)}")
        for symbol, m in sorted(metrics.items()):
            pf = m['profit_factor']
            pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
            print(f"    {symbol}: WR={m['win_rate']:.1%} PF={pf_str} "
                  f"Blocked={m['blocked_share']:.1%} ({m['blocked']}/{m['total_signals']})")
    
    # Select best thresholds
    print("\n" + "="*70)
    print("OPTIMAL THRESHOLDS PER SYMBOL")
    print("="*70)
    
    best_thresholds = select_best_thresholds(all_metrics)
    
    for symbol, data in sorted(best_thresholds.items()):
        set_name = data['set']
        thresholds = data['thresholds']
        m = data['metrics']
        pf = m['profit_factor']
        pf_str = f"{pf:.2f}" if pf != float('inf') else "INF"
        
        print(f"\n{symbol}: Set {set_name} (block<{thresholds['block']}, boost>{thresholds['boost_start']})")
        print(f"  Win Rate: {m['win_rate']:.1%}")
        print(f"  Profit Factor: {pf_str}")
        print(f"  Avg Duration: {m['avg_time_to_outcome']:.1f} min")
        print(f"  Blocked: {m['blocked_share']:.1%} ({m['blocked']}/{m['total_signals']})")
        print(f"  Performance: {m['wins']}W / {m['losses']}L / {m['cancelled']}C")
    
    # Save results to JSON
    results = {
        'timestamp': datetime.now().isoformat(),
        'backtest_days': 30,
        'total_signals': len(df),
        'symbols_optimized': len(best_thresholds),
        'best_thresholds': {
            symbol: {
                'set': data['set'],
                'block_below': data['thresholds']['block'],
                'boost_above': data['thresholds']['boost_start'],
                'metrics': data['metrics']
            }
            for symbol, data in best_thresholds.items()
        }
    }
    
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n[BACKTEST] Results saved to backtest_results.json")
    
    # Update config.yaml
    update_config_with_thresholds(best_thresholds)
    
    print("\n" + "="*70)
    print("OPTIMIZATION COMPLETE")
    print("="*70)

if __name__ == '__main__':
    main()
