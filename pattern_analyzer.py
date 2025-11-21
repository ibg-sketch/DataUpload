#!/usr/bin/env python3
"""
Detailed Pattern Analyzer
Deep analysis of winning patterns - specifically CVD+VWAP combination
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from scipy import stats

class PatternAnalyzer:
    def __init__(self):
        self.effectiveness_df = None
        self.analysis_df = None
        
    def load_data(self):
        """Load historical data"""
        print("=" * 80)
        print("PATTERN ANALYZER - CVD+VWAP DEEP DIVE")
        print("=" * 80)
        
        try:
            self.effectiveness_df = pd.read_csv('effectiveness_log.csv')
            self.effectiveness_df['timestamp_sent'] = pd.to_datetime(self.effectiveness_df['timestamp_sent'])
            print(f"✅ Loaded {len(self.effectiveness_df)} signals")
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
    
    def analyze_cvd_vwap_pattern(self, timeframe_minutes=60):
        """
        Detailed analysis of CVD+VWAP winning pattern
        Args:
            timeframe_minutes: Lookback window (default 60 from optimizer results)
        """
        print(f"\n{'=' * 80}")
        print(f"ANALYZING CVD+VWAP PATTERN ({timeframe_minutes}m LOOKBACK)")
        print(f"{'=' * 80}")
        
        # Merge signals with indicator data
        merged = []
        for idx, eff_row in self.effectiveness_df.iterrows():
            signal_time = eff_row['timestamp_sent']
            lookback_start = signal_time - timedelta(minutes=timeframe_minutes)
            
            lookback_data = self.analysis_df[
                (self.analysis_df['symbol'] == eff_row['symbol']) &
                (self.analysis_df['timestamp'] > lookback_start) &
                (self.analysis_df['timestamp'] <= signal_time)
            ]
            
            if len(lookback_data) > 0:
                cvd_mean = lookback_data['cvd'].mean()
                cvd_std = lookback_data['cvd'].std() if len(lookback_data) > 1 else 0
                vwap_mean = lookback_data['price_vs_vwap_pct'].mean()
                vwap_std = lookback_data['price_vs_vwap_pct'].std() if len(lookback_data) > 1 else 0
                
                merged_row = {
                    'timestamp': signal_time,
                    'symbol': eff_row['symbol'],
                    'verdict': eff_row['verdict'],
                    'result': eff_row['result'],
                    'profit_pct': eff_row['profit_pct'],
                    'duration_minutes': eff_row.get('duration_minutes', 0),
                    'win': 1 if eff_row['result'] == 'WIN' else 0,
                    'cvd_mean': cvd_mean,
                    'cvd_std': cvd_std,
                    'cvd_abs': abs(cvd_mean),
                    'vwap_deviation': abs(vwap_mean),
                    'vwap_std': vwap_std,
                    'oi_mean': lookback_data['oi_change_pct'].mean(),
                    'volume_sum': lookback_data['volume'].sum(),
                    'rsi_mean': lookback_data['rsi'].mean(),
                }
                merged.append(merged_row)
        
        df = pd.DataFrame(merged)
        
        # Define thresholds from optimizer results
        cvd_threshold = df['cvd_abs'].quantile(0.70)
        vwap_threshold = df['vwap_deviation'].quantile(0.70)
        
        # Identify CVD+VWAP combo signals
        cvd_vwap_combo = df[
            (df['cvd_abs'] >= cvd_threshold) &
            (df['vwap_deviation'] >= vwap_threshold)
        ]
        
        print(f"\n📊 COMBO PATTERN STATISTICS:")
        print(f"   CVD threshold: {cvd_threshold:,.0f}")
        print(f"   VWAP deviation threshold: {vwap_threshold:.2f}%")
        print(f"   Signals matching pattern: {len(cvd_vwap_combo)}/{len(df)} ({len(cvd_vwap_combo)/len(df)*100:.1f}%)")
        
        if len(cvd_vwap_combo) == 0:
            print("❌ No signals match the combo pattern")
            return None
        
        # Win rate analysis
        combo_win_rate = cvd_vwap_combo['win'].mean()
        overall_win_rate = df['win'].mean()
        
        print(f"\n🎯 WIN RATE COMPARISON:")
        print(f"   CVD+VWAP combo: {combo_win_rate*100:.1f}%")
        print(f"   Overall: {overall_win_rate*100:.1f}%")
        print(f"   Improvement: {(combo_win_rate - overall_win_rate)*100:+.1f} percentage points")
        
        # Analyze winning vs losing combos
        combo_wins = cvd_vwap_combo[cvd_vwap_combo['win'] == 1]
        combo_losses = cvd_vwap_combo[cvd_vwap_combo['win'] == 0]
        
        print(f"\n🔍 WINNING PATTERN CHARACTERISTICS:")
        if len(combo_wins) > 0:
            print(f"   Avg CVD: {combo_wins['cvd_mean'].mean():,.0f}")
            print(f"   Avg VWAP deviation: {combo_wins['vwap_deviation'].mean():.2f}%")
            print(f"   Avg OI change: {combo_wins['oi_mean'].mean():.2f}%")
            print(f"   Avg RSI: {combo_wins['rsi_mean'].mean():.1f}")
            print(f"   Avg profit: {combo_wins['profit_pct'].mean():+.2f}%")
        
        print(f"\n❌ LOSING PATTERN CHARACTERISTICS:")
        if len(combo_losses) > 0:
            print(f"   Avg CVD: {combo_losses['cvd_mean'].mean():,.0f}")
            print(f"   Avg VWAP deviation: {combo_losses['vwap_deviation'].mean():.2f}%")
            print(f"   Avg OI change: {combo_losses['oi_mean'].mean():.2f}%")
            print(f"   Avg RSI: {combo_losses['rsi_mean'].mean():.1f}")
            print(f"   Avg loss: {combo_losses['profit_pct'].mean():+.2f}%")
        
        # Per-symbol analysis
        print(f"\n📈 PER-SYMBOL BREAKDOWN:")
        print(f"{'Symbol':<12} | {'Combo Signals':<15} | {'Win Rate':<10} | {'Avg Profit':<12}")
        print("-" * 60)
        
        symbol_results = []
        for symbol in sorted(cvd_vwap_combo['symbol'].unique()):
            sym_combo = cvd_vwap_combo[cvd_vwap_combo['symbol'] == symbol]
            if len(sym_combo) > 0:
                sym_win_rate = sym_combo['win'].mean()
                sym_avg_profit = sym_combo['profit_pct'].mean()
                symbol_results.append({
                    'symbol': symbol,
                    'count': len(sym_combo),
                    'win_rate': sym_win_rate,
                    'avg_profit': sym_avg_profit
                })
                print(f"{symbol:<12} | {len(sym_combo):<15} | {sym_win_rate*100:>6.1f}% | {sym_avg_profit:>+8.2f}%")
        
        # Verdict analysis
        print(f"\n📊 BY VERDICT:")
        for verdict in ['BUY', 'SELL']:
            verdict_combo = cvd_vwap_combo[cvd_vwap_combo['verdict'] == verdict]
            if len(verdict_combo) > 0:
                verdict_win_rate = verdict_combo['win'].mean()
                print(f"   {verdict}: {len(verdict_combo)} signals, {verdict_win_rate*100:.1f}% win rate")
        
        # Find the "sweet spot" ranges
        print(f"\n🎯 OPTIMAL RANGES (for wins):")
        if len(combo_wins) > 0:
            print(f"   CVD range: {combo_wins['cvd_abs'].min():,.0f} to {combo_wins['cvd_abs'].max():,.0f}")
            print(f"   CVD median (winners): {combo_wins['cvd_abs'].median():,.0f}")
            print(f"   VWAP deviation range: {combo_wins['vwap_deviation'].min():.2f}% to {combo_wins['vwap_deviation'].max():.2f}%")
            print(f"   VWAP median (winners): {combo_wins['vwap_deviation'].median():.2f}%")
            print(f"   RSI range: {combo_wins['rsi_mean'].min():.1f} to {combo_wins['rsi_mean'].max():.1f}")
            print(f"   RSI median (winners): {combo_wins['rsi_mean'].median():.1f}")
        
        # Duration analysis
        if 'duration_minutes' in cvd_vwap_combo.columns:
            print(f"\n⏱️  SIGNAL DURATION ANALYSIS:")
            print(f"   Winners avg duration: {combo_wins['duration_minutes'].mean():.0f} min")
            print(f"   Losers avg duration: {combo_losses['duration_minutes'].mean():.0f} min")
        
        # Save detailed results
        results = {
            'timestamp': datetime.now().isoformat(),
            'timeframe_minutes': timeframe_minutes,
            'cvd_threshold': float(cvd_threshold),
            'vwap_threshold': float(vwap_threshold),
            'total_combo_signals': len(cvd_vwap_combo),
            'combo_win_rate': float(combo_win_rate),
            'overall_win_rate': float(overall_win_rate),
            'improvement': float(combo_win_rate - overall_win_rate),
            'symbol_breakdown': symbol_results,
            'winning_ranges': {
                'cvd_min': float(combo_wins['cvd_abs'].min()) if len(combo_wins) > 0 else 0,
                'cvd_max': float(combo_wins['cvd_abs'].max()) if len(combo_wins) > 0 else 0,
                'cvd_median': float(combo_wins['cvd_abs'].median()) if len(combo_wins) > 0 else 0,
                'vwap_min': float(combo_wins['vwap_deviation'].min()) if len(combo_wins) > 0 else 0,
                'vwap_max': float(combo_wins['vwap_deviation'].max()) if len(combo_wins) > 0 else 0,
                'vwap_median': float(combo_wins['vwap_deviation'].median()) if len(combo_wins) > 0 else 0,
                'rsi_min': float(combo_wins['rsi_mean'].min()) if len(combo_wins) > 0 else 0,
                'rsi_max': float(combo_wins['rsi_mean'].max()) if len(combo_wins) > 0 else 0,
                'rsi_median': float(combo_wins['rsi_mean'].median()) if len(combo_wins) > 0 else 0,
            }
        }
        
        with open('pattern_analysis_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Detailed results saved to pattern_analysis_results.json")
        
        return results
    
    def compare_timeframes(self):
        """Compare pattern across different timeframes"""
        print(f"\n{'=' * 80}")
        print(f"TIMEFRAME COMPARISON FOR CVD+VWAP PATTERN")
        print(f"{'=' * 80}")
        
        timeframes = [5, 15, 30, 60, 240]
        comparison = []
        
        for tf in timeframes:
            result = self.analyze_cvd_vwap_pattern(tf)
            if result:
                comparison.append({
                    'timeframe': tf,
                    'win_rate': result['combo_win_rate'],
                    'signals': result['total_combo_signals'],
                    'improvement': result['improvement']
                })
        
        if len(comparison) > 0:
            print(f"\n{'Timeframe':<12} | {'Signals':<10} | {'Win Rate':<12} | {'Improvement':<15}")
            print("-" * 60)
            for c in comparison:
                print(f"{c['timeframe']:>3} minutes | {c['signals']:<10} | {c['win_rate']*100:>8.1f}% | {c['improvement']*100:>+8.1f} pp")
        
        return comparison

if __name__ == "__main__":
    analyzer = PatternAnalyzer()
    
    if not analyzer.load_data():
        print("❌ Failed to load data")
        exit(1)
    
    # Analyze the 60-minute pattern (best from optimizer)
    print("\n" + "=" * 80)
    print("MAIN ANALYSIS: 60-MINUTE LOOKBACK (BEST FROM OPTIMIZER)")
    print("=" * 80)
    analyzer.analyze_cvd_vwap_pattern(60)
    
    # Compare across timeframes
    analyzer.compare_timeframes()
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
