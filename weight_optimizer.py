#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, TimeSeriesSplit

class WeightOptimizer:
    """
    Optimizes indicator weights by correlating raw indicator values  
    with actual WIN/LOSS outcomes from historical signals.
    """
    
    def __init__(self, effectiveness_file='effectiveness_log.csv',
                 analysis_file='analysis_log.csv',
                 config_file='config.yaml', 
                 min_samples=30):  # CRITICAL FIX: Raised from 15 to 30 for better statistical reliability
        self.effectiveness_file = effectiveness_file
        self.analysis_file = analysis_file
        self.config_file = config_file
        self.min_samples = min_samples
        self.weight_bounds = (0.5, 2.0)
        
    def load_config(self):
        """Load current config.yaml to get coin list and current weights."""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            print(f"[WEIGHT_OPT] Error loading config: {e}")
            return None
    
    def load_and_merge_data(self):
        """
        Load effectiveness and analysis logs, then merge them on timestamp/symbol/verdict.
        
        Returns:
            DataFrame with raw indicator values + WIN/LOSS outcomes
        """
        try:
            # Load effectiveness log
            if '_BROKEN' in self.effectiveness_file:
                print(f"[WEIGHT_OPT] ERROR: Refusing to load BROKEN file")
                return None
            
            eff_df = pd.read_csv(self.effectiveness_file)
            eff_df['timestamp_sent'] = pd.to_datetime(eff_df['timestamp_sent'])
            
            if 'result' not in eff_df.columns:
                print("[WEIGHT_OPT] ERROR: effectiveness_log missing 'result' column")
                return None
            
            # Filter valid results
            valid_results = eff_df['result'].isin(['WIN', 'LOSS'])
            if not valid_results.all():
                invalid_count = (~valid_results).sum()
                print(f"[WEIGHT_OPT] WARNING: Filtered {invalid_count} invalid results")
                eff_df = eff_df[valid_results]
            
            if len(eff_df) == 0:
                print("[WEIGHT_OPT] ERROR: No valid WIN/LOSS entries")
                return None
            
            eff_df['outcome'] = (eff_df['result'] == 'WIN').astype(int)
            
            # Load analysis log
            analysis_df = pd.read_csv(self.analysis_file, on_bad_lines='skip')
            
            # Filter only BUY/SELL verdicts BEFORE parsing timestamp (NO_TRADE has no indicators)
            analysis_df = analysis_df[analysis_df['verdict'].isin(['BUY', 'SELL'])]
            
            # Now parse timestamp only for BUY/SELL entries
            analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'], errors='coerce')
            
            if len(analysis_df) == 0:
                print("[WEIGHT_OPT] ERROR: No BUY/SELL entries in analysis_log")
                return None
            
            print(f"[WEIGHT_OPT] Loaded {len(eff_df)} effectiveness entries, {len(analysis_df)} analysis entries")
            
            # Merge on symbol + verdict + close timestamp (within 2 minutes)
            merged_data = []
            matched_count = 0
            
            for idx, eff_row in eff_df.iterrows():
                time_diff = abs(analysis_df['timestamp'] - eff_row['timestamp_sent'])
                matches = analysis_df[
                    (analysis_df['symbol'] == eff_row['symbol']) &
                    (analysis_df['verdict'] == eff_row['verdict']) &
                    (time_diff < timedelta(minutes=2))
                ]
                
                if len(matches) > 0:
                    # Take closest match
                    closest_match = matches.loc[time_diff[matches.index].idxmin()]
                    
                    # Extract raw indicator values
                    merged_row = {
                        'symbol': eff_row['symbol'],
                        'verdict': eff_row['verdict'],
                        'outcome': eff_row['outcome'],
                        'confidence': eff_row['confidence'],
                        
                        # Raw indicators from analysis log
                        'cvd': closest_match.get('cvd', 0),
                        'oi_change_pct': closest_match.get('oi_change_pct', 0),
                        'price_vs_vwap_pct': closest_match.get('price_vs_vwap_pct', 0),
                        'volume_spike': int(closest_match.get('volume_spike', 0)),
                        'liq_ratio': closest_match.get('liq_ratio', 0),
                    }
                    merged_data.append(merged_row)
                    matched_count += 1
            
            if len(merged_data) == 0:
                print("[WEIGHT_OPT] ERROR: No matching data between logs")
                return None
            
            df = pd.DataFrame(merged_data)
            print(f"[WEIGHT_OPT] Successfully matched {matched_count} signals with indicator data")
            return df
            
        except Exception as e:
            print(f"[WEIGHT_OPT] Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def prepare_features(self, coin_data):
        """
        Prepare feature matrix from raw indicator values.
        
        These map directly to config.yaml weights:
        - cvd -> cvd_weight
        - oi_change_pct -> oi_weight  
        - price_vs_vwap_pct -> vwap_weight
        - volume_spike -> volume_weight
        - liq_ratio -> liq_weight
        """
        # Normalize CVD by dividing by maximum absolute value
        cvd_max = coin_data['cvd'].abs().max()
        cvd_normalized = coin_data['cvd'] / cvd_max if cvd_max > 0 else pd.Series([0] * len(coin_data))
        
        # Create feature matrix
        features = {
            'cvd': cvd_normalized,
            'oi_change_pct': coin_data['oi_change_pct'],
            'price_vs_vwap_pct': coin_data['price_vs_vwap_pct'],
            'volume_spike': coin_data['volume_spike'].astype(float),
            'liq_ratio': coin_data['liq_ratio']
        }
        
        X = pd.DataFrame(features)
        X = X.fillna(0)
        
        return X
    
    def optimize_weights(self, X, y):
        """
        Optimize weights using L2-regularized Logistic Regression.
        
        CRITICAL: We preserve coefficient sign to maintain indicator directionality.
        Positive coefficient = indicator predicts WIN when value is positive
        Negative coefficient = indicator predicts WIN when value is negative
        
        Returns:
            dict: Optimized weights for each indicator
        """
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        lr = LogisticRegression(
            penalty='l2',
            C=1.0,
            max_iter=1000,
            random_state=42,
            solver='lbfgs'
        )
        
        lr.fit(X_scaled, y)
        
        # CRITICAL FIX: Use TimeSeriesSplit for proper time-series cross-validation
        # This prevents lookahead bias by always training on past data and testing on future data
        n_splits = min(5, max(2, len(y)//10))  # Fewer splits for time-series (need more data per fold)
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_scores = cross_val_score(lr, X_scaled, y, cv=tscv)
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        
        # Get coefficients (PRESERVE SIGN!)
        raw_coefficients = lr.coef_[0]
        
        # Scale coefficients to [0.5, 2.0] range while preserving sign
        # We use the magnitude for scaling but keep the original sign
        weights = {}
        for i, feature in enumerate(X.columns):
            coef = raw_coefficients[i]
            
            # Map coefficient to weight: abs(coef) determines magnitude
            # Sign determines whether we should use raw value or invert
            magnitude = abs(coef)
            
            # Scale to weight range (normalize across all coefficients)
            max_coef = abs(raw_coefficients).max()
            if max_coef > 0:
                # Scale to [0.5, 2.0] based on relative importance
                normalized = 0.5 + (magnitude / max_coef) * 1.5
            else:
                normalized = 1.0
            
            # Clip to bounds
            weight = float(np.clip(normalized, self.weight_bounds[0], self.weight_bounds[1]))
            
            weights[feature] = {
                'weight': weight,
                'coefficient': float(coef),
                'sign': '+' if coef > 0 else '-'
            }
        
        return weights, cv_mean, cv_std
    
    def analyze_coin(self, coin_data, symbol, current_weights):
        """Analyze and optimize weights for a specific coin."""
        print(f"[WEIGHT_OPT] Analyzing {symbol}...")
        
        if len(coin_data) < self.min_samples:
            print(f"  ⚠️  Only {len(coin_data)} signals (need {self.min_samples} minimum)")
            return None
        
        X = self.prepare_features(coin_data)
        y = coin_data['outcome'].values
        
        win_rate = y.mean()
        
        try:
            optimized_weights, cv_score, cv_std = self.optimize_weights(X, y)
            
            # Map indicator names to config.yaml weight names
            weight_mapping = {
                'cvd': 'cvd_weight',
                'oi_change_pct': 'oi_weight',
                'price_vs_vwap_pct': 'vwap_weight',
                'volume_spike': 'volume_weight',
                'liq_ratio': 'liq_weight'
            }
            
            result = {
                'symbol': symbol,
                'sample_size': len(coin_data),
                'current_win_rate': float(win_rate),
                'cv_accuracy': float(cv_score),
                'cv_std': float(cv_std),
                'current_weights': current_weights,
                'optimized_weights': {},
                'weight_changes': {}
            }
            
            for indicator_name, weight_info in optimized_weights.items():
                config_weight_name = weight_mapping.get(indicator_name, indicator_name)
                old_weight = current_weights.get(config_weight_name, 1.0)
                new_weight = weight_info['weight']
                
                result['optimized_weights'][config_weight_name] = new_weight
                result['weight_changes'][config_weight_name] = {
                    'old': float(old_weight),
                    'new': float(new_weight),
                    'change_pct': ((new_weight - old_weight) / old_weight) * 100 if old_weight > 0 else 0,
                    'coefficient': weight_info['coefficient'],
                    'sign': weight_info['sign']
                }
            
            return result
            
        except Exception as e:
            print(f"  ❌ Optimization failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze_all_coins(self, data, config):
        """Analyze and optimize weights for all coins."""
        symbols = data['symbol'].unique()
        results = {}
        
        for symbol in symbols:
            coin_data = data[data['symbol'] == symbol].copy()
            
            current_weights = {}
            if 'coins' in config and symbol in config['coins']:
                coin_config = config['coins'][symbol]
                if 'weights' in coin_config:
                    current_weights = coin_config['weights']
            
            analysis = self.analyze_coin(coin_data, symbol, current_weights)
            if analysis:
                results[symbol] = analysis
        
        return results
    
    def generate_report(self, results):
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 80)
        lines.append("WEIGHT OPTIMIZATION REPORT (RAW INDICATOR WEIGHTS)")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        lines.append("NOTE: This optimizer analyzes RAW indicator values (CVD, OI, VWAP, etc.)")
        lines.append("      and recommends optimal weights for config.yaml")
        lines.append("")
        
        lines.append("SUMMARY TABLE:")
        lines.append(f"{'Coin':<12} {'Signals':<10} {'Win Rate':<12} {'CV Accuracy':<15} {'Status':<15}")
        lines.append("-" * 80)
        for symbol, data in sorted(results.items()):
            status = "✅ Good" if data['current_win_rate'] >= 0.60 else "⚠️  Needs Improvement"
            lines.append(f"{symbol:<12} {data['sample_size']:<10} "
                        f"{data['current_win_rate']*100:>6.1f}%     "
                        f"{data['cv_accuracy']*100:>6.1f}% ±{data['cv_std']*100:.1f}%  "
                        f"{status}")
        lines.append("")
        lines.append("")
        
        for symbol, data in results.items():
            lines.append("-" * 80)
            lines.append(f"COIN: {symbol}")
            lines.append("-" * 80)
            lines.append(f"  Sample Size: {data['sample_size']}")
            lines.append(f"  Current Win Rate: {data['current_win_rate']*100:.1f}%")
            lines.append(f"  Cross-Validation Accuracy: {data['cv_accuracy']*100:.1f}% ± {data['cv_std']*100:.1f}%")
            lines.append("")
            lines.append("  WEIGHT RECOMMENDATIONS:")
            lines.append("")
            
            sorted_changes = sorted(data['weight_changes'].items(), 
                                   key=lambda x: abs(x[1]['change_pct']), 
                                   reverse=True)
            
            for weight_name, change_info in sorted_changes:
                change_indicator = "📈" if change_info['change_pct'] > 10 else "📉" if change_info['change_pct'] < -10 else "➡️ "
                sign_marker = change_info.get('sign', '?')
                coef = change_info.get('coefficient', 0)
                
                lines.append(f"  {change_indicator} {weight_name:<20} "
                           f"Old: {change_info['old']:.3f}  →  "
                           f"New: {change_info['new']:.3f}  "
                           f"({change_info['change_pct']:+.1f}%)  "
                           f"[Coef: {sign_marker}{abs(coef):.3f}]")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("LEGEND:")
        lines.append("  ✅ = Win rate >= 60% (performing well)")
        lines.append("  ⚠️  = Win rate < 60% (needs improvement)")
        lines.append("  📈 = Weight increased >10%")
        lines.append("  📉 = Weight decreased >10%")
        lines.append("  ➡️  = Weight changed <10%")
        lines.append("  [Coef] = Logistic regression coefficient (+ = bullish, - = bearish)")
        lines.append("  CV Accuracy = Cross-validated prediction accuracy")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save_results(self, results, output_file='weight_optimization_results.json'):
        """Save results to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"[WEIGHT_OPT] Results saved to {output_file}")
    
    def save_report(self, report, output_file='weight_optimization_report.txt'):
        """Save report to text file."""
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"[WEIGHT_OPT] Report saved to {output_file}")
    
    def generate_config_update(self, results):
        """Generate YAML snippet to update config.yaml."""
        lines = []
        lines.append("# Suggested weight updates for config.yaml")
        lines.append("# Generated by weight_optimizer.py on " + datetime.now().isoformat())
        lines.append("#")
        lines.append("# These weights are optimized based on historical signal performance")
        lines.append("# using raw indicator values (CVD, OI, VWAP, Volume, Liquidations)")
        lines.append("")
        lines.append("coins:")
        
        for symbol, data in sorted(results.items()):
            lines.append(f"  {symbol}:")
            lines.append(f"    # Current win rate: {data['current_win_rate']*100:.1f}%")
            lines.append(f"    # CV accuracy: {data['cv_accuracy']*100:.1f}%")
            lines.append(f"    weights:")
            
            for weight_name, weight_value in sorted(data['optimized_weights'].items()):
                change_info = data['weight_changes'].get(weight_name, {})
                sign = change_info.get('sign', '?')
                coef = change_info.get('coefficient', 0)
                lines.append(f"      {weight_name}: {weight_value:.3f}  # {sign}{abs(coef):.3f}")
            lines.append("")
        
        config_snippet = "\n".join(lines)
        
        with open('weight_update_snippet.yaml', 'w') as f:
            f.write(config_snippet)
        
        print(f"[WEIGHT_OPT] Config update snippet saved to: weight_update_snippet.yaml")
        return config_snippet

def main():
    print("[WEIGHT_OPT] Starting weight optimization analysis...")
    print("[WEIGHT_OPT] This will analyze RAW indicator values vs outcomes")
    print("")
    
    optimizer = WeightOptimizer()
    
    config = optimizer.load_config()
    if config is None:
        print("[WEIGHT_OPT] Failed to load config")
        return
    
    data = optimizer.load_and_merge_data()
    if data is None:
        print("[WEIGHT_OPT] Analysis failed - no overlapping data available")
        print("[WEIGHT_OPT] The bot needs to run longer to accumulate matching data")
        print("[WEIGHT_OPT] between effectiveness_log.csv and analysis_log.csv")
        return
    
    results = optimizer.analyze_all_coins(data, config)
    
    if not results:
        print("[WEIGHT_OPT] No results generated")
        return
    
    report = optimizer.generate_report(results)
    print("\n" + report)
    
    optimizer.save_results(results, 'weight_optimization_results.json')
    optimizer.save_report(report, 'weight_optimization_report.txt')
    optimizer.generate_config_update(results)
    
    print("\n[WEIGHT_OPT] Analysis complete!")
    print("[WEIGHT_OPT] Results saved to: weight_optimization_results.json")
    print("[WEIGHT_OPT] Report saved to: weight_optimization_report.txt")
    print("[WEIGHT_OPT] Config update saved to: weight_update_snippet.yaml")

if __name__ == '__main__':
    main()
