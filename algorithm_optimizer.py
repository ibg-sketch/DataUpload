#!/usr/bin/env python3
"""
Algorithm Optimizer - Data-Driven Formula Design
Analyzes historical indicator data to design the best trading algorithm
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class AlgorithmOptimizer:
    def __init__(self):
        self.effectiveness_df = None
        self.analysis_df = None
        self.merged_df = None
        
    def load_data(self):
        """Load effectiveness and analysis logs"""
        print("=" * 80)
        print("LOADING DATA")
        print("=" * 80)
        
        try:
            self.effectiveness_df = pd.read_csv('effectiveness_log.csv')
            print(f"✅ Loaded {len(self.effectiveness_df)} signals from effectiveness_log.csv")
        except Exception as e:
            print(f"❌ Error loading effectiveness_log.csv: {e}")
            return False
            
        try:
            self.analysis_df = pd.read_csv('analysis_log.csv')
            print(f"✅ Loaded {len(self.analysis_df)} analyses from analysis_log.csv")
        except Exception as e:
            print(f"❌ Error loading analysis_log.csv: {e}")
            return False
            
        return True
    
    def merge_datasets(self):
        """Merge effectiveness and analysis data by timestamp (within 2-minute window)"""
        print("\n" + "=" * 80)
        print("MERGING DATASETS")
        print("=" * 80)
        
        # Convert timestamps
        self.effectiveness_df['timestamp_sent'] = pd.to_datetime(self.effectiveness_df['timestamp_sent'])
        self.analysis_df['timestamp'] = pd.to_datetime(self.analysis_df['timestamp'])
        
        merged = []
        for idx, eff_row in self.effectiveness_df.iterrows():
            # Find matching analysis within 2-minute window
            time_diff = (self.analysis_df['timestamp'] - eff_row['timestamp_sent']).abs()
            matches = self.analysis_df[
                (self.analysis_df['symbol'] == eff_row['symbol']) &
                (time_diff <= timedelta(minutes=2))
            ]
            
            if len(matches) > 0:
                # Take closest match
                closest = matches.loc[time_diff[matches.index].idxmin()]
                
                # Merge the rows
                merged_row = {
                    'timestamp': eff_row['timestamp_sent'],
                    'symbol': eff_row['symbol'],
                    'verdict': eff_row['verdict'],
                    'confidence': eff_row['confidence'],
                    'result': eff_row['result'],
                    'profit_pct': eff_row['profit_pct'],
                    'entry_price': eff_row['entry_price'],
                    'target_min': eff_row['target_min'],
                    'target_max': eff_row['target_max'],
                    'highest_reached': eff_row['highest_reached'],
                    'lowest_reached': eff_row['lowest_reached'],
                    'cvd': closest.get('cvd', 0),
                    'oi_change': closest.get('oi_change', 0),
                    'oi_change_pct': closest.get('oi_change_pct', 0),
                    'price_vs_vwap_pct': closest.get('price_vs_vwap_pct', 0),
                    'volume': closest.get('volume', 0),
                    'volume_median': closest.get('volume_median', 1),
                    'volume_spike': closest.get('volume_spike', False),
                    'rsi': closest.get('rsi', 50),
                    'atr': closest.get('atr', 0),
                }
                merged.append(merged_row)
        
        self.merged_df = pd.DataFrame(merged)
        print(f"✅ Merged {len(self.merged_df)} signals with indicator data")
        print(f"   Win rate in merged data: {(self.merged_df['result'] == 'WIN').mean() * 100:.1f}%")
        
        return len(self.merged_df) > 0
    
    def calculate_indicator_correlations(self):
        """Calculate correlation between indicators and winning outcomes"""
        print("\n" + "=" * 80)
        print("INDICATOR CORRELATION ANALYSIS")
        print("=" * 80)
        
        if self.merged_df is None or len(self.merged_df) == 0:
            print("❌ No merged data available")
            return
        
        # Binary outcome
        self.merged_df['win'] = (self.merged_df['result'] == 'WIN').astype(int)
        
        # Calculate volume ratio
        self.merged_df['volume_ratio'] = self.merged_df['volume'] / self.merged_df['volume_median']
        
        indicators = {
            'cvd': 'CVD (raw)',
            'oi_change_pct': 'OI Change %',
            'price_vs_vwap_pct': 'Price vs VWAP %',
            'volume_ratio': 'Volume Ratio',
            'rsi': 'RSI',
            'atr': 'ATR',
        }
        
        print("\nCorrelation with Winning Outcomes (Pearson):")
        print("-" * 60)
        
        correlations = []
        for col, label in indicators.items():
            if col in self.merged_df.columns:
                # Remove NaN/inf values
                valid_data = self.merged_df[[col, 'win']].replace([np.inf, -np.inf], np.nan).dropna()
                
                if len(valid_data) > 3:
                    corr, p_value = stats.pearsonr(valid_data[col], valid_data['win'])
                    correlations.append({
                        'indicator': label,
                        'correlation': corr,
                        'p_value': p_value,
                        'significant': '✓' if p_value < 0.05 else ''
                    })
                    print(f"{label:25} | r={corr:+.4f} | p={p_value:.4f} {('✓' if p_value < 0.05 else '')}")
        
        return correlations
    
    def analyze_by_symbol(self):
        """Analyze win rates and optimal thresholds by symbol"""
        print("\n" + "=" * 80)
        print("PER-SYMBOL ANALYSIS")
        print("=" * 80)
        
        if self.merged_df is None:
            return
        
        print(f"\n{'Symbol':<12} | {'Signals':<8} | {'Win Rate':<10} | {'Avg CVD':<15} | {'Avg OI%':<10}")
        print("-" * 70)
        
        symbol_stats = []
        for symbol in sorted(self.merged_df['symbol'].unique()):
            sym_data = self.merged_df[self.merged_df['symbol'] == symbol]
            
            if len(sym_data) > 0:
                win_rate = (sym_data['result'] == 'WIN').mean() * 100
                avg_cvd = sym_data['cvd'].mean()
                avg_oi = sym_data['oi_change_pct'].mean()
                
                symbol_stats.append({
                    'symbol': symbol,
                    'count': len(sym_data),
                    'win_rate': win_rate,
                    'avg_cvd': avg_cvd,
                    'avg_oi': avg_oi
                })
                
                print(f"{symbol:<12} | {len(sym_data):<8} | {win_rate:>6.1f}% | {avg_cvd:>13,.0f} | {avg_oi:>8.2f}%")
        
        return symbol_stats
    
    def find_optimal_thresholds(self):
        """Find optimal CVD and OI thresholds for maximum win rate"""
        print("\n" + "=" * 80)
        print("OPTIMAL THRESHOLD ANALYSIS")
        print("=" * 80)
        
        if self.merged_df is None or len(self.merged_df) < 20:
            print("❌ Insufficient data for threshold optimization")
            return
        
        # Test different CVD percentile thresholds
        print("\nTesting CVD Thresholds (by percentile):")
        print("-" * 60)
        
        cvd_abs = self.merged_df['cvd'].abs()
        for percentile in [50, 60, 70, 80, 90]:
            threshold = cvd_abs.quantile(percentile / 100)
            above_thresh = self.merged_df[cvd_abs >= threshold]
            
            if len(above_thresh) > 5:
                win_rate = (above_thresh['result'] == 'WIN').mean() * 100
                print(f"P{percentile} (CVD ≥ {threshold:>12,.0f}): {len(above_thresh):>3} signals | {win_rate:>5.1f}% win rate")
        
        # Test different OI change thresholds
        print("\nTesting OI Change % Thresholds:")
        print("-" * 60)
        
        oi_abs = self.merged_df['oi_change_pct'].abs()
        for threshold in [0.1, 0.3, 0.5, 1.0, 1.5]:
            above_thresh = self.merged_df[oi_abs >= threshold]
            
            if len(above_thresh) > 5:
                win_rate = (above_thresh['result'] == 'WIN').mean() * 100
                print(f"OI ≥ {threshold:>4.1f}%: {len(above_thresh):>3} signals | {win_rate:>5.1f}% win rate")
    
    def test_confluence_combinations(self):
        """Test different indicator combinations for best win rate"""
        print("\n" + "=" * 80)
        print("CONFLUENCE COMBINATION TESTING")
        print("=" * 80)
        
        if self.merged_df is None or len(self.merged_df) < 20:
            print("❌ Insufficient data")
            return
        
        # Define indicator conditions
        cvd_thresh = self.merged_df['cvd'].abs().quantile(0.70)
        oi_thresh = 0.3
        
        conditions = {
            'CVD_strong': self.merged_df['cvd'].abs() >= cvd_thresh,
            'OI_strong': self.merged_df['oi_change_pct'].abs() >= oi_thresh,
            'VWAP_aligned': self.merged_df['price_vs_vwap_pct'].abs() >= 0.1,
            'Volume_spike': self.merged_df['volume_ratio'] >= 1.5,
        }
        
        print("\nTesting 2-Indicator Combinations:")
        print("-" * 60)
        
        from itertools import combinations
        results = []
        
        for combo in combinations(conditions.keys(), 2):
            combined = conditions[combo[0]] & conditions[combo[1]]
            matches = self.merged_df[combined]
            
            if len(matches) >= 5:
                win_rate = (matches['result'] == 'WIN').mean() * 100
                results.append({
                    'combo': f"{combo[0]} + {combo[1]}",
                    'count': len(matches),
                    'win_rate': win_rate
                })
        
        # Sort by win rate
        results.sort(key=lambda x: x['win_rate'], reverse=True)
        
        for r in results[:5]:
            print(f"{r['combo']:<35} | {r['count']:>3} signals | {r['win_rate']:>5.1f}% win rate")
        
        print("\nTesting 3-Indicator Combinations:")
        print("-" * 60)
        
        results = []
        for combo in combinations(conditions.keys(), 3):
            combined = conditions[combo[0]] & conditions[combo[1]] & conditions[combo[2]]
            matches = self.merged_df[combined]
            
            if len(matches) >= 5:
                win_rate = (matches['result'] == 'WIN').mean() * 100
                results.append({
                    'combo': f"{combo[0]} + {combo[1]} + {combo[2]}",
                    'count': len(matches),
                    'win_rate': win_rate
                })
        
        results.sort(key=lambda x: x['win_rate'], reverse=True)
        
        for r in results[:5]:
            print(f"{r['combo']:<50} | {r['count']:>3} signals | {r['win_rate']:>5.1f}% win rate")
    
    def run_logistic_regression(self):
        """Use logistic regression to find optimal indicator weights"""
        print("\n" + "=" * 80)
        print("LOGISTIC REGRESSION - OPTIMAL WEIGHTS")
        print("=" * 80)
        
        if self.merged_df is None or len(self.merged_df) < 20:
            print("❌ Insufficient data for regression")
            return
        
        # Prepare features
        feature_cols = ['cvd', 'oi_change_pct', 'price_vs_vwap_pct', 'volume_ratio', 'rsi']
        
        # Filter valid data
        valid_data = self.merged_df[feature_cols + ['win']].replace([np.inf, -np.inf], np.nan).dropna()
        
        if len(valid_data) < 20:
            print("❌ Insufficient valid data after cleaning")
            return
        
        X = valid_data[feature_cols]
        y = valid_data['win']
        
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Fit logistic regression
        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X_scaled, y)
        
        print(f"\nModel trained on {len(valid_data)} signals")
        print(f"Training accuracy: {model.score(X_scaled, y) * 100:.1f}%")
        print(f"\nOptimal Indicator Weights:")
        print("-" * 60)
        
        coefficients = []
        for feature, coef in zip(feature_cols, model.coef_[0]):
            coefficients.append({
                'indicator': feature,
                'coefficient': coef,
                'importance': abs(coef)
            })
            print(f"{feature:20} | Coefficient: {coef:+.4f} | Importance: {abs(coef):.4f}")
        
        # Sort by importance
        coefficients.sort(key=lambda x: x['importance'], reverse=True)
        
        print("\nRanked by Importance:")
        print("-" * 60)
        for i, c in enumerate(coefficients, 1):
            print(f"{i}. {c['indicator']:20} | {c['importance']:.4f}")
        
        return coefficients
    
    def generate_recommendations(self):
        """Generate final algorithm recommendations"""
        print("\n" + "=" * 80)
        print("ALGORITHM RECOMMENDATIONS")
        print("=" * 80)
        
        recommendations = {
            'timestamp': datetime.now().isoformat(),
            'data_analyzed': {
                'total_signals': len(self.effectiveness_df) if self.effectiveness_df is not None else 0,
                'merged_signals': len(self.merged_df) if self.merged_df is not None else 0,
                'overall_win_rate': (self.merged_df['result'] == 'WIN').mean() * 100 if self.merged_df is not None else 0
            },
            'recommendations': []
        }
        
        print("\n📋 RECOMMENDED ALGORITHM IMPROVEMENTS:")
        print("-" * 60)
        
        if self.merged_df is not None and len(self.merged_df) > 20:
            # Recommendation 1: Optimal thresholds
            cvd_optimal = self.merged_df['cvd'].abs().quantile(0.70)
            oi_optimal = 0.3
            
            print(f"\n1. THRESHOLD OPTIMIZATION")
            print(f"   • CVD threshold: {cvd_optimal:,.0f} (P70)")
            print(f"   • OI threshold: {oi_optimal:.1f}%")
            
            recommendations['recommendations'].append({
                'type': 'thresholds',
                'cvd_threshold': float(cvd_optimal),
                'oi_threshold': float(oi_optimal)
            })
            
            # Recommendation 2: Best confluence
            print(f"\n2. CONFLUENCE STRATEGY")
            print(f"   • Require 3+ of: CVD + OI + VWAP + Volume")
            print(f"   • Volume ratio ≥ 1.5x median")
            print(f"   • Price ≥ 0.1% from VWAP")
            
            # Recommendation 3: Indicator weights (if regression ran)
            print(f"\n3. INDICATOR WEIGHTS")
            print(f"   • See logistic regression results above")
            print(f"   • Focus on top 3 most important indicators")
        
        # Save recommendations
        with open('algorithm_recommendations.json', 'w') as f:
            json.dump(recommendations, f, indent=2)
        
        print(f"\n✅ Recommendations saved to algorithm_recommendations.json")
    
    def run_full_analysis(self):
        """Run complete analysis pipeline"""
        print("\n" + "=" * 80)
        print("ALGORITHM OPTIMIZER - FULL ANALYSIS")
        print("=" * 80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not self.load_data():
            print("❌ Failed to load data")
            return
        
        if not self.merge_datasets():
            print("❌ Failed to merge datasets")
            return
        
        self.calculate_indicator_correlations()
        self.analyze_by_symbol()
        self.find_optimal_thresholds()
        self.test_confluence_combinations()
        self.run_logistic_regression()
        self.generate_recommendations()
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    optimizer = AlgorithmOptimizer()
    optimizer.run_full_analysis()
