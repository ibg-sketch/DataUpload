"""
Correlation Analysis Module for Smart Money Signal Bot

Analyzes historical signal effectiveness to identify which indicators
predict price movements best for each coin.

Uses multiple statistical methods:
- Pearson correlation (linear relationships)
- Mutual information (non-linear relationships)
- Logistic regression coefficients (predictive power)
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import mutual_info_classif
from scipy.stats import pearsonr
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class CorrelationAnalyzer:
    """
    Analyzes correlations between market indicators and signal success.
    """
    
    def __init__(self, effectiveness_file='effectiveness_log.csv', 
                 analysis_file='analysis_log.csv',
                 min_samples=20):
        """
        Initialize correlation analyzer.
        
        Args:
            effectiveness_file: Path to effectiveness log CSV
            analysis_file: Path to detailed analysis log CSV
            min_samples: Minimum signals required for reliable correlation (default 20)
        """
        self.effectiveness_file = effectiveness_file
        self.analysis_file = analysis_file
        self.min_samples = min_samples
        
    def load_data(self):
        """
        Load effectiveness data for analysis.
        
        Returns:
            DataFrame: Data with indicators and outcomes
        """
        try:
            # Load effectiveness log (only canonical file, not BROKEN versions)
            if '_BROKEN' in self.effectiveness_file or '_broken' in self.effectiveness_file:
                print(f"[CORRELATION] ERROR: Refusing to load from BROKEN file: {self.effectiveness_file}")
                return None
            
            eff_df = pd.read_csv(self.effectiveness_file)
            eff_df['timestamp_sent'] = pd.to_datetime(eff_df['timestamp_sent'])
            
            # Data integrity check: verify result column has only WIN/LOSS
            if 'result' not in eff_df.columns:
                print("[CORRELATION] ERROR: effectiveness_log missing 'result' column")
                return None
            
            valid_results = eff_df['result'].isin(['WIN', 'LOSS'])
            if not valid_results.all():
                invalid_count = (~valid_results).sum()
                print(f"[CORRELATION] WARNING: Found {invalid_count} invalid result values. Filtering out...")
                eff_df = eff_df[valid_results]
            
            if len(eff_df) == 0:
                print("[CORRELATION] ERROR: No valid WIN/LOSS entries found")
                return None
            
            # Create binary outcome (1 = WIN, 0 = LOSS)
            eff_df['outcome'] = (eff_df['result'] == 'WIN').astype(int)
            
            # Add verdict direction (1 for BUY, -1 for SELL)
            eff_df['verdict_direction'] = eff_df['verdict'].map({'BUY': 1, 'SELL': -1})
            
            # Try to load analysis log for enrichment
            try:
                analysis_df = pd.read_csv(self.analysis_file, on_bad_lines='skip')
                analysis_df['timestamp'] = pd.to_datetime(analysis_df['timestamp'])
                
                # Attempt to merge
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
                        
                        # Add analysis indicators to effectiveness data
                        eff_df.loc[idx, 'cvd'] = closest_match['cvd']
                        eff_df.loc[idx, 'oi_change_pct'] = closest_match['oi_change_pct']
                        eff_df.loc[idx, 'price_vs_vwap_pct'] = closest_match['price_vs_vwap_pct']
                        eff_df.loc[idx, 'volume_spike'] = int(closest_match['volume_spike'])
                
                if 'cvd' in eff_df.columns:
                    print(f"[CORRELATION] Enriched {eff_df['cvd'].notna().sum()} signals with analysis data")
            
            except Exception as e:
                print(f"[CORRELATION] Could not enrich with analysis data: {e}")
                print(f"[CORRELATION] Using effectiveness data only (confidence, market strength, targets)")
            
            print(f"[CORRELATION] Loaded {len(eff_df)} signals for analysis")
            return eff_df
            
        except Exception as e:
            print(f"[CORRELATION] Error loading data: {e}")
            return None
    
    def analyze_coin(self, df, symbol):
        """
        Analyze correlations for a specific coin.
        
        Args:
            df: DataFrame with merged data
            symbol: Trading pair symbol
            
        Returns:
            dict: Correlation results for this coin
        """
        # Filter data for this symbol
        coin_data = df[df['symbol'] == symbol].copy()
        
        if len(coin_data) < self.min_samples:
            return {
                'symbol': symbol,
                'sample_size': len(coin_data),
                'status': 'insufficient_data',
                'min_required': self.min_samples
            }
        
        # Calculate win rate
        win_rate = coin_data['outcome'].mean()
        
        # Prepare indicator features (use what's available)
        indicators = {}
        
        # Always available from effectiveness log
        indicators['confidence'] = coin_data['confidence']
        indicators['market_strength'] = coin_data.get('market_strength', pd.Series([1.0] * len(coin_data)))
        indicators['verdict_direction'] = coin_data['verdict_direction']
        indicators['target_range_pct'] = ((coin_data['target_max'] - coin_data['target_min']) / coin_data['entry_price']) * 100
        
        # Optional: enriched from analysis log
        if 'cvd' in coin_data.columns:
            cvd_max = coin_data['cvd'].abs().max()
            indicators['cvd_normalized'] = coin_data['cvd'] / cvd_max if cvd_max > 0 else pd.Series([0] * len(coin_data))
        
        if 'oi_change_pct' in coin_data.columns:
            indicators['oi_change_pct'] = coin_data['oi_change_pct']
        
        if 'price_vs_vwap_pct' in coin_data.columns:
            indicators['price_vs_vwap_pct'] = coin_data['price_vs_vwap_pct']
        
        if 'volume_spike' in coin_data.columns:
            indicators['volume_spike'] = coin_data['volume_spike']
        
        # Calculate Pearson correlations
        pearson_corr = {}
        for indicator_name, indicator_values in indicators.items():
            if indicator_values.std() > 0:  # Skip if no variance
                corr, pvalue = pearsonr(indicator_values, coin_data['outcome'])
                pearson_corr[indicator_name] = {
                    'correlation': float(corr),
                    'p_value': float(pvalue),
                    'significant': bool(pvalue < 0.05)
                }
            else:
                pearson_corr[indicator_name] = {
                    'correlation': 0.0,
                    'p_value': 1.0,
                    'significant': bool(False)
                }
        
        # Calculate mutual information (non-linear relationships)
        X = np.array([indicators[k].values for k in indicators.keys()]).T
        X = np.nan_to_num(X, 0)  # Replace NaN with 0
        y = coin_data['outcome'].values
        
        mi_scores = mutual_info_classif(X, y, random_state=42)
        mutual_info = {
            indicator_name: float(score)
            for indicator_name, score in zip(indicators.keys(), mi_scores)
        }
        
        # Logistic regression coefficients (predictive importance)
        try:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            lr = LogisticRegression(random_state=42, max_iter=1000, penalty='l2', C=1.0)
            lr.fit(X_scaled, y)
            
            logistic_coef = {
                indicator_name: float(coef)
                for indicator_name, coef in zip(indicators.keys(), lr.coef_[0])
            }
            
            # Model performance
            train_accuracy = lr.score(X_scaled, y)
            
        except Exception as e:
            print(f"[CORRELATION] Logistic regression failed for {symbol}: {e}")
            logistic_coef = {k: 0.0 for k in indicators.keys()}
            train_accuracy = 0.0
        
        # Rank indicators by importance
        # Combine Pearson (linear), MI (non-linear), and logistic (predictive)
        importance_scores = {}
        for indicator in indicators.keys():
            # Composite score: average of absolute values
            importance_scores[indicator] = (
                abs(pearson_corr[indicator]['correlation']) +
                mutual_info[indicator] +
                abs(logistic_coef[indicator])
            ) / 3.0
        
        # Sort by importance
        ranked_indicators = sorted(
            importance_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'symbol': symbol,
            'sample_size': len(coin_data),
            'win_rate': float(win_rate),
            'status': 'success',
            
            # Correlation results
            'pearson_correlation': pearson_corr,
            'mutual_information': mutual_info,
            'logistic_coefficients': logistic_coef,
            'logistic_accuracy': float(train_accuracy),
            
            # Ranked indicators
            'importance_scores': importance_scores,
            'ranked_indicators': ranked_indicators
        }
    
    def analyze_all_coins(self, symbols=None):
        """
        Analyze correlations for all coins.
        
        Args:
            symbols: List of symbols to analyze (default: all in data)
            
        Returns:
            dict: Correlation results for all coins
        """
        df = self.load_data()
        if df is None:
            return None
        
        if symbols is None:
            symbols = df['symbol'].unique()
        
        results = {}
        for symbol in symbols:
            print(f"[CORRELATION] Analyzing {symbol}...")
            results[symbol] = self.analyze_coin(df, symbol)
        
        # Overall statistics
        total_signals = len(df)
        overall_win_rate = df['outcome'].mean()
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_signals': total_signals,
            'overall_win_rate': float(overall_win_rate),
            'coins_analyzed': len(results),
            'results': results
        }
        
        return summary
    
    def save_results(self, results, filename='correlation_results.json'):
        """
        Save correlation analysis results to JSON file.
        
        Args:
            results: Results from analyze_all_coins()
            filename: Output filename
        """
        if results is None:
            print("[CORRELATION] No results to save")
            return
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"[CORRELATION] Results saved to {filename}")
    
    def generate_report(self, results):
        """
        Generate human-readable correlation report.
        
        Args:
            results: Results from analyze_all_coins()
            
        Returns:
            str: Formatted report
        """
        if results is None:
            return "No correlation data available"
        
        report = []
        report.append("=" * 80)
        report.append("CORRELATION ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {results['timestamp']}")
        report.append(f"Total Signals Analyzed: {results['total_signals']}")
        report.append(f"Overall Win Rate: {results['overall_win_rate']:.1%}")
        report.append("")
        
        for symbol, coin_result in results['results'].items():
            report.append("-" * 80)
            report.append(f"COIN: {symbol}")
            report.append("-" * 80)
            
            if coin_result['status'] != 'success':
                report.append(f"  Status: {coin_result['status']}")
                report.append(f"  Sample Size: {coin_result['sample_size']} (min required: {coin_result.get('min_required', 'N/A')})")
                report.append("")
                continue
            
            report.append(f"  Sample Size: {coin_result['sample_size']}")
            report.append(f"  Win Rate: {coin_result['win_rate']:.1%}")
            report.append(f"  Logistic Model Accuracy: {coin_result['logistic_accuracy']:.1%}")
            report.append("")
            
            report.append("  TOP 5 MOST PREDICTIVE INDICATORS:")
            for i, (indicator, score) in enumerate(coin_result['ranked_indicators'][:5], 1):
                pearson = coin_result['pearson_correlation'][indicator]['correlation']
                mi = coin_result['mutual_information'][indicator]
                lr_coef = coin_result['logistic_coefficients'][indicator]
                
                report.append(f"    {i}. {indicator}")
                report.append(f"       Importance Score: {score:.3f}")
                report.append(f"       Pearson Corr: {pearson:+.3f} {'*' if coin_result['pearson_correlation'][indicator]['significant'] else ''}")
                report.append(f"       Mutual Info: {mi:.3f}")
                report.append(f"       LR Coefficient: {lr_coef:+.3f}")
            
            report.append("")
        
        report.append("=" * 80)
        report.append("LEGEND:")
        report.append("  * = Statistically significant (p < 0.05)")
        report.append("  Importance Score = Average of |Pearson|, MI, and |LR Coef|")
        report.append("  Positive correlation = indicator predicts WIN")
        report.append("  Negative correlation = indicator predicts LOSS")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """
    Run correlation analysis and generate reports.
    """
    print("[CORRELATION] Starting correlation analysis...")
    
    analyzer = CorrelationAnalyzer(min_samples=10)  # Lower threshold for initial testing
    
    # Analyze all coins
    results = analyzer.analyze_all_coins()
    
    if results is None:
        print("[CORRELATION] Analysis failed - no data available")
        return
    
    # Save results
    analyzer.save_results(results, 'correlation_results.json')
    
    # Generate and save report
    report = analyzer.generate_report(results)
    with open('correlation_report.txt', 'w') as f:
        f.write(report)
    
    print("\n" + report)
    print(f"\n[CORRELATION] Analysis complete!")
    print(f"[CORRELATION] Results saved to: correlation_results.json")
    print(f"[CORRELATION] Report saved to: correlation_report.txt")


if __name__ == '__main__':
    main()
