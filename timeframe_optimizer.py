#!/usr/bin/env python3
"""
Advanced Timeframe & Pattern Optimizer
Automatically finds the best analysis period by:
1. Testing multiple timeframes (5m, 15m, 30m, 1h, 4h)
2. Splitting data into training (past) and testing (future) periods
3. Validating patterns actually predict future outcomes
4. Finding optimal indicator combinations for each timeframe
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score
import warnings
warnings.filterwarnings('ignore')

class TimeframeOptimizer:
    def __init__(self):
        self.effectiveness_df = None
        self.analysis_df = None
        
    def load_data(self):
        """Load all historical data"""
        print("=" * 80)
        print("LOADING HISTORICAL DATA")
        print("=" * 80)
        
        try:
            self.effectiveness_df = pd.read_csv('effectiveness_log.csv')
            self.effectiveness_df['timestamp_sent'] = pd.to_datetime(self.effectiveness_df['timestamp_sent'])
            print(f"✅ Loaded {len(self.effectiveness_df)} signals")
            print(f"   Date range: {self.effectiveness_df['timestamp_sent'].min()} to {self.effectiveness_df['timestamp_sent'].max()}")
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
            
        try:
            self.analysis_df = pd.read_csv('analysis_log.csv')
            self.analysis_df['timestamp'] = pd.to_datetime(self.analysis_df['timestamp'])
            print(f"✅ Loaded {len(self.analysis_df)} analysis cycles")
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        
        return True
    
    def test_timeframe_effectiveness(self, timeframe_minutes, train_test_splits=3):
        """
        Test how well a timeframe predicts future signals using walk-forward validation
        
        Args:
            timeframe_minutes: Analysis timeframe to test
            train_test_splits: Number of train/test periods to validate
        """
        print(f"\n{'=' * 80}")
        print(f"TESTING {timeframe_minutes}-MINUTE TIMEFRAME")
        print(f"{'=' * 80}")
        
        # Merge with effectiveness data - NO DATA LEAKAGE
        # Only use analysis rows that occurred BEFORE the signal timestamp
        merged = []
        for idx, eff_row in self.effectiveness_df.iterrows():
            signal_time = eff_row['timestamp_sent']
            lookback_start = signal_time - timedelta(minutes=timeframe_minutes)
            
            # Get analysis rows in the lookback window, BEFORE signal time
            lookback_data = self.analysis_df[
                (self.analysis_df['symbol'] == eff_row['symbol']) &
                (self.analysis_df['timestamp'] > lookback_start) &
                (self.analysis_df['timestamp'] <= signal_time)
            ]
            
            if len(lookback_data) > 0:
                # Aggregate indicators only from data BEFORE the signal
                merged_row = {
                    'timestamp': signal_time,
                    'symbol': eff_row['symbol'],
                    'verdict': eff_row['verdict'],
                    'result': eff_row['result'],
                    'win': 1 if eff_row['result'] == 'WIN' else 0,
                    # Aggregated features from lookback window
                    'cvd_mean': lookback_data['cvd'].mean(),
                    'cvd_std': lookback_data['cvd'].std() if len(lookback_data) > 1 else 0,
                    'cvd_max': lookback_data['cvd'].max(),
                    'oi_pct_mean': lookback_data['oi_change_pct'].mean(),
                    'oi_pct_std': lookback_data['oi_change_pct'].std() if len(lookback_data) > 1 else 0,
                    'oi_pct_max': lookback_data['oi_change_pct'].max(),
                    'vwap_pct_mean': lookback_data['price_vs_vwap_pct'].mean(),
                    'vwap_pct_std': lookback_data['price_vs_vwap_pct'].std() if len(lookback_data) > 1 else 0,
                    'rsi_mean': lookback_data['rsi'].mean(),
                    'rsi_min': lookback_data['rsi'].min(),
                    'volume_sum': lookback_data['volume'].sum(),
                }
                merged.append(merged_row)
        
        if len(merged) < 30:
            print(f"❌ Insufficient data: only {len(merged)} signals matched")
            return None
        
        merged_df = pd.DataFrame(merged)
        print(f"✅ Merged {len(merged_df)} signals for {timeframe_minutes}m timeframe")
        
        # Walk-forward validation
        total_signals = len(merged_df)
        split_size = total_signals // (train_test_splits + 1)
        
        results = []
        
        for split_idx in range(train_test_splits):
            train_end = (split_idx + 1) * split_size
            test_end = min(train_end + split_size, total_signals)
            
            train_df = merged_df.iloc[:train_end]
            test_df = merged_df.iloc[train_end:test_end]
            
            if len(test_df) < 5:
                continue
            
            # Train model on past data
            feature_cols = ['cvd_mean', 'oi_pct_mean', 'vwap_pct_mean', 'rsi_mean', 'volume_sum']
            
            X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
            y_train = train_df['win']
            
            X_test = test_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
            y_test = test_df['win']
            
            try:
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                
                model = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
                model.fit(X_train_scaled, y_train)
                
                # Predict on future unseen data
                y_pred = model.predict(X_test_scaled)
                
                # Calculate metrics
                accuracy = accuracy_score(y_test, y_pred)
                baseline = y_test.mean()  # Just predicting majority class
                
                results.append({
                    'split': split_idx + 1,
                    'train_size': len(train_df),
                    'test_size': len(test_df),
                    'accuracy': accuracy,
                    'baseline': baseline,
                    'improvement': accuracy - baseline,
                    'actual_wins': y_test.sum(),
                    'predicted_wins': y_pred.sum()
                })
                
                print(f"\nSplit {split_idx + 1}: Train on {len(train_df)}, Test on {len(test_df)}")
                print(f"  Accuracy: {accuracy*100:.1f}% | Baseline: {baseline*100:.1f}% | Improvement: {(accuracy-baseline)*100:+.1f}%")
                print(f"  Actual wins: {y_test.sum()}/{len(y_test)} | Predicted wins: {y_pred.sum()}")
                
            except Exception as e:
                print(f"  ❌ Error in split {split_idx + 1}: {e}")
                continue
        
        if len(results) == 0:
            return None
        
        # Average results
        avg_accuracy = np.mean([r['accuracy'] for r in results])
        avg_improvement = np.mean([r['improvement'] for r in results])
        
        print(f"\n{'─' * 60}")
        print(f"AVERAGE PERFORMANCE FOR {timeframe_minutes}m TIMEFRAME:")
        print(f"  Accuracy: {avg_accuracy*100:.1f}%")
        print(f"  Improvement over baseline: {avg_improvement*100:+.1f}%")
        print(f"{'─' * 60}")
        
        return {
            'timeframe': timeframe_minutes,
            'avg_accuracy': avg_accuracy,
            'avg_improvement': avg_improvement,
            'splits': results,
            'total_signals': len(merged_df)
        }
    
    def find_optimal_patterns(self, timeframe_minutes):
        """
        Find specific patterns that predict wins for a given timeframe
        """
        print(f"\n{'=' * 80}")
        print(f"FINDING OPTIMAL PATTERNS FOR {timeframe_minutes}m TIMEFRAME")
        print(f"{'=' * 80}")
        
        # Merge with outcomes - NO DATA LEAKAGE
        merged = []
        for idx, eff_row in self.effectiveness_df.iterrows():
            signal_time = eff_row['timestamp_sent']
            lookback_start = signal_time - timedelta(minutes=timeframe_minutes)
            
            # Get analysis rows in the lookback window, BEFORE signal time
            lookback_data = self.analysis_df[
                (self.analysis_df['symbol'] == eff_row['symbol']) &
                (self.analysis_df['timestamp'] > lookback_start) &
                (self.analysis_df['timestamp'] <= signal_time)
            ]
            
            if len(lookback_data) > 0:
                rsi_mean = lookback_data['rsi'].mean()
                vwap_mean = lookback_data['price_vs_vwap_pct'].mean()
                
                merged_row = {
                    'result': eff_row['result'],
                    'win': 1 if eff_row['result'] == 'WIN' else 0,
                    'cvd_mean': lookback_data['cvd'].mean(),
                    'cvd_volatility': lookback_data['cvd'].std() if len(lookback_data) > 1 else 0,
                    'oi_momentum': lookback_data['oi_change_pct'].mean(),
                    'vwap_deviation': abs(vwap_mean),
                    'rsi': rsi_mean,
                    'rsi_extreme': abs(rsi_mean - 50),
                }
                merged.append(merged_row)
        
        if len(merged) < 20:
            print(f"❌ Insufficient data")
            return None
        
        df = pd.DataFrame(merged)
        
        # Test different pattern combinations
        print("\nTesting Pattern Combinations:")
        print("─" * 60)
        
        patterns = []
        
        # Pattern 1: Strong CVD
        cvd_thresh = df['cvd_mean'].abs().quantile(0.7)
        strong_cvd = df[df['cvd_mean'].abs() >= cvd_thresh]
        if len(strong_cvd) >= 5:
            win_rate = strong_cvd['win'].mean()
            patterns.append({
                'name': f'Strong CVD (≥{cvd_thresh:,.0f})',
                'count': len(strong_cvd),
                'win_rate': win_rate,
                'threshold': cvd_thresh
            })
            print(f"Strong CVD (≥{cvd_thresh:,.0f}): {len(strong_cvd)} signals, {win_rate*100:.1f}% win rate")
        
        # Pattern 2: Extreme RSI
        rsi_extreme_df = df[df['rsi_extreme'] >= 15]
        if len(rsi_extreme_df) >= 5:
            win_rate = rsi_extreme_df['win'].mean()
            patterns.append({
                'name': 'Extreme RSI (>15 from 50)',
                'count': len(rsi_extreme_df),
                'win_rate': win_rate,
                'threshold': 15
            })
            print(f"Extreme RSI (>15 from 50): {len(rsi_extreme_df)} signals, {win_rate*100:.1f}% win rate")
        
        # Pattern 3: High VWAP deviation
        vwap_thresh = df['vwap_deviation'].quantile(0.7)
        high_vwap = df[df['vwap_deviation'] >= vwap_thresh]
        if len(high_vwap) >= 5:
            win_rate = high_vwap['win'].mean()
            patterns.append({
                'name': f'High VWAP deviation (≥{vwap_thresh:.2f}%)',
                'count': len(high_vwap),
                'win_rate': win_rate,
                'threshold': vwap_thresh
            })
            print(f"High VWAP deviation (≥{vwap_thresh:.2f}%): {len(high_vwap)} signals, {win_rate*100:.1f}% win rate")
        
        # Pattern 4: Combination patterns
        combined = df[
            (df['cvd_mean'].abs() >= cvd_thresh) &
            (df['vwap_deviation'] >= vwap_thresh)
        ]
        if len(combined) >= 5:
            win_rate = combined['win'].mean()
            patterns.append({
                'name': 'CVD + VWAP combo',
                'count': len(combined),
                'win_rate': win_rate
            })
            print(f"CVD + VWAP combo: {len(combined)} signals, {win_rate*100:.1f}% win rate")
        
        # Sort by win rate
        patterns.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return patterns
    
    def run_comprehensive_analysis(self):
        """Run full timeframe optimization"""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE TIMEFRAME & PATTERN OPTIMIZATION")
        print("=" * 80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        if not self.load_data():
            return
        
        # Test different timeframes
        timeframes = [5, 15, 30, 60, 240]  # 5m, 15m, 30m, 1h, 4h
        
        timeframe_results = []
        
        for tf in timeframes:
            result = self.test_timeframe_effectiveness(tf, train_test_splits=3)
            if result:
                timeframe_results.append(result)
                
                # Find patterns for this timeframe
                patterns = self.find_optimal_patterns(tf)
                result['patterns'] = patterns
        
        # Find best timeframe
        if len(timeframe_results) > 0:
            print("\n" + "=" * 80)
            print("TIMEFRAME COMPARISON SUMMARY")
            print("=" * 80)
            
            print(f"\n{'Timeframe':<12} | {'Signals':<8} | {'Accuracy':<10} | {'Improvement':<12}")
            print("─" * 60)
            
            for r in timeframe_results:
                print(f"{r['timeframe']:>3} minutes | {r['total_signals']:<8} | {r['avg_accuracy']*100:>6.1f}% | {r['avg_improvement']*100:>+6.1f}%")
            
            # Best by improvement
            best = max(timeframe_results, key=lambda x: x['avg_improvement'])
            
            print(f"\n🏆 BEST TIMEFRAME: {best['timeframe']} minutes")
            print(f"   Accuracy: {best['avg_accuracy']*100:.1f}%")
            print(f"   Improvement: {best['avg_improvement']*100:+.1f}%")
            print(f"   Total signals: {best['total_signals']}")
            
            if best.get('patterns'):
                print(f"\n   Best Patterns for {best['timeframe']}m:")
                for i, p in enumerate(best['patterns'][:3], 1):
                    print(f"   {i}. {p['name']}: {p['win_rate']*100:.1f}% win rate ({p['count']} signals)")
            
            # Save recommendations
            recommendations = {
                'timestamp': datetime.now().isoformat(),
                'best_timeframe': best['timeframe'],
                'best_accuracy': best['avg_accuracy'],
                'best_improvement': best['avg_improvement'],
                'all_timeframes': timeframe_results
            }
            
            with open('timeframe_recommendations.json', 'w') as f:
                json.dump(recommendations, f, indent=2, default=str)
            
            print(f"\n✅ Recommendations saved to timeframe_recommendations.json")
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    optimizer = TimeframeOptimizer()
    optimizer.run_comprehensive_analysis()
