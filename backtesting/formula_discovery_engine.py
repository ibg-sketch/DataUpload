#!/usr/bin/env python3
"""
Formula Discovery Engine
Data-driven analysis to find optimal trading formula from historical data
NO reliance on existing broken formula - pure statistical discovery
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
from scipy.stats import pearsonr, spearmanr
import warnings
warnings.filterwarnings('ignore')

class FormulaDiscoveryEngine:
    """
    Multi-phase engine for discovering optimal trading formula:
    Phase 2: Indicator enrichment (RSI, EMA, VWAP, ADX, Volume)
    Phase 3: Statistical analysis (correlation, feature importance, mutual info)
    Phase 4: ML modeling + TTL optimization
    Phase 5: Formula synthesis
    Phase 6: Validation & benchmarking
    """
    
    def __init__(self, data_dir='backtesting/data'):
        self.data_dir = Path(data_dir)
        self.symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT',
            'DOGEUSDT', 'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
        ]
        
        self.all_data = {}  # Will store enriched data per symbol
        self.analysis_results = {}  # Statistical findings
        
        print("="*80)
        print("🔬 FORMULA DISCOVERY ENGINE")
        print("="*80)
        print(f"Data Directory: {self.data_dir}")
        print(f"Symbols: {len(self.symbols)}")
        print("="*80)
        
    # ============================================================================
    # PHASE 2: INDICATOR ENRICHMENT
    # ============================================================================
    
    def calculate_indicators(self, df):
        """
        Calculate ALL indicators for a single symbol dataframe
        Returns enriched dataframe with indicator columns
        """
        df = df.copy()
        
        # RSI (14-period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # EMA (20, 50)
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_cross'] = df['ema_20'] - df['ema_50']  # Positive = bullish
        
        # VWAP (session-based approximation using 288 periods = 1 day)
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).rolling(288).sum() / df['volume'].rolling(288).sum()
        df['vwap_distance'] = ((df['close'] - df['vwap']) / df['vwap']) * 100
        
        # ADX (14-period)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        
        df['high_diff'] = df['high'] - df['high'].shift()
        df['low_diff'] = df['low'].shift() - df['low']
        
        df['+dm'] = np.where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), df['high_diff'], 0)
        df['-dm'] = np.where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), df['low_diff'], 0)
        
        df['+di'] = 100 * (df['+dm'].rolling(14).mean() / df['atr'])
        df['-di'] = 100 * (df['-dm'].rolling(14).mean() / df['atr'])
        
        df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
        df['adx'] = df['dx'].rolling(14).mean()
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price momentum
        df['price_change_1h'] = df['close'].pct_change(12) * 100  # 12 candles = 1 hour
        df['price_change_4h'] = df['close'].pct_change(48) * 100  # 48 candles = 4 hours
        
        # Volatility
        df['volatility'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean() * 100
        
        # Clean up temporary columns
        df = df.drop(columns=['tr1', 'tr2', 'tr3', 'tr', 'high_diff', 'low_diff', '+dm', '-dm', '+di', '-di', 'dx'], errors='ignore')
        
        return df
    
    def calculate_future_returns(self, df, ttl_minutes=[15, 30, 60, 90, 120]):
        """
        Calculate actual future returns at different TTL horizons
        This is our TARGET variable for ML models
        """
        df = df.copy()
        
        for ttl in ttl_minutes:
            periods = int(ttl / 5)  # 5-min candles
            
            # Future high/low within TTL window
            df[f'future_high_{ttl}m'] = df['high'].rolling(periods).max().shift(-periods)
            df[f'future_low_{ttl}m'] = df['low'].rolling(periods).min().shift(-periods)
            
            # Max potential gain (BUY signal)
            df[f'max_gain_{ttl}m'] = ((df[f'future_high_{ttl}m'] - df['close']) / df['close']) * 100
            
            # Max potential loss (SELL signal perspective)
            df[f'max_drop_{ttl}m'] = ((df['close'] - df[f'future_low_{ttl}m']) / df['close']) * 100
            
            # Net directional move (close-to-close)
            df[f'net_return_{ttl}m'] = ((df['close'].shift(-periods) - df['close']) / df['close']) * 100
        
        return df
    
    def load_and_enrich_all_symbols(self):
        """
        Phase 2: Load raw data and enrich with indicators + future returns
        """
        print("\n" + "="*80)
        print("PHASE 2: INDICATOR ENRICHMENT")
        print("="*80)
        
        for symbol in self.symbols:
            file_path = self.data_dir / f"{symbol}_5m.csv"
            
            if not file_path.exists():
                print(f"⚠️  {symbol}: File not found")
                continue
            
            print(f"\n📊 Processing {symbol}...")
            
            # Load raw data
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            print(f"  Raw data: {len(df)} candles")
            
            # Calculate indicators
            df = self.calculate_indicators(df)
            
            # Calculate future returns (our prediction targets)
            df = self.calculate_future_returns(df)
            
            # Drop rows with NaN (from rolling calculations)
            initial_len = len(df)
            df = df.dropna()
            print(f"  Enriched: {len(df)} candles ({initial_len - len(df)} dropped for warmup)")
            
            # Save enriched data
            self.all_data[symbol] = df
            
            output_file = self.data_dir / f"{symbol}_enriched.csv"
            df.to_csv(output_file, index=False)
            print(f"  ✅ Saved to {output_file}")
        
        print("\n" + "="*80)
        print(f"✅ PHASE 2 COMPLETE: {len(self.all_data)} symbols enriched")
        print("="*80)
    
    # ============================================================================
    # PHASE 3: STATISTICAL ANALYSIS
    # ============================================================================
    
    def analyze_indicator_correlations(self, ttl_target=60):
        """
        Analyze correlation between each indicator and future returns
        This shows which indicators are most predictive
        """
        print("\n" + "="*80)
        print(f"PHASE 3: CORRELATION ANALYSIS (TTL={ttl_target}m)")
        print("="*80)
        
        indicators = ['rsi', 'ema_cross', 'vwap_distance', 'adx', 'volume_ratio', 
                      'price_change_1h', 'price_change_4h', 'volatility']
        
        # Aggregate all symbols
        all_symbols_df = pd.concat(self.all_data.values(), ignore_index=True)
        
        target_col = f'net_return_{ttl_target}m'
        
        correlations = {}
        
        print(f"\nIndicator vs {target_col}:")
        print("-" * 60)
        
        for indicator in indicators:
            if indicator in all_symbols_df.columns:
                # Pearson correlation (linear relationship)
                corr, pvalue = pearsonr(
                    all_symbols_df[indicator].dropna(),
                    all_symbols_df[target_col].dropna()
                )
                
                correlations[indicator] = {
                    'pearson': corr,
                    'pvalue': pvalue,
                    'abs_corr': abs(corr)
                }
                
                print(f"  {indicator:20s}: {corr:+.4f} (p={pvalue:.2e})")
        
        # Rank by absolute correlation
        ranked = sorted(correlations.items(), key=lambda x: x[1]['abs_corr'], reverse=True)
        
        print("\n📊 Ranked by Predictive Power:")
        print("-" * 60)
        for i, (indicator, stats) in enumerate(ranked, 1):
            print(f"  {i}. {indicator:20s}: {stats['pearson']:+.4f}")
        
        self.analysis_results['correlations'] = correlations
        self.analysis_results['ranked_indicators'] = ranked
        
        return correlations
    
    def analyze_buy_sell_asymmetry(self, ttl_target=60):
        """
        Analyze BUY vs SELL signal asymmetry
        Do bullish and bearish moves have different characteristics?
        """
        print("\n" + "="*80)
        print("PHASE 3: BUY/SELL ASYMMETRY ANALYSIS")
        print("="*80)
        
        all_symbols_df = pd.concat(self.all_data.values(), ignore_index=True)
        
        # Define bullish vs bearish based on actual future returns
        gain_col = f'max_gain_{ttl_target}m'
        drop_col = f'max_drop_{ttl_target}m'
        
        # Profitable BUY opportunities (future gain > 1%)
        buy_opps = all_symbols_df[all_symbols_df[gain_col] > 1.0]
        
        # Profitable SELL opportunities (future drop > 1%)
        sell_opps = all_symbols_df[all_symbols_df[drop_col] > 1.0]
        
        print(f"\n📈 BUY Opportunities: {len(buy_opps)} ({len(buy_opps)/len(all_symbols_df)*100:.1f}%)")
        print(f"📉 SELL Opportunities: {len(sell_opps)} ({len(sell_opps)/len(all_symbols_df)*100:.1f}%)")
        print(f"Asymmetry Ratio: {len(sell_opps)/max(len(buy_opps), 1):.2f}x")
        
        # Analyze indicator distributions for each
        indicators = ['rsi', 'vwap_distance', 'adx', 'volume_ratio']
        
        print("\n" + "-"*80)
        print("Average Indicator Values:")
        print("-"*80)
        print(f"{'Indicator':<20} {'BUY Opps':>12} {'SELL Opps':>12} {'Difference':>12}")
        print("-"*80)
        
        for indicator in indicators:
            if indicator in all_symbols_df.columns:
                buy_mean = buy_opps[indicator].mean()
                sell_mean = sell_opps[indicator].mean()
                diff = buy_mean - sell_mean
                
                print(f"{indicator:<20} {buy_mean:>12.2f} {sell_mean:>12.2f} {diff:>+12.2f}")
        
        self.analysis_results['asymmetry'] = {
            'buy_count': len(buy_opps),
            'sell_count': len(sell_opps),
            'buy_pct': len(buy_opps)/len(all_symbols_df)*100,
            'sell_pct': len(sell_opps)/len(all_symbols_df)*100
        }
    
    def calculate_optimal_signal_frequency(self):
        """
        Determine how many signals per day per symbol is optimal
        Based on profit distribution analysis
        """
        print("\n" + "="*80)
        print("PHASE 3: OPTIMAL SIGNAL FREQUENCY")
        print("="*80)
        
        # We want to target only the TOP profitable opportunities
        # Analyze profit distribution to find optimal threshold
        
        all_symbols_df = pd.concat(self.all_data.values(), ignore_index=True)
        
        # Ensure timestamp is datetime
        all_symbols_df['timestamp'] = pd.to_datetime(all_symbols_df['timestamp'])
        
        # Days of data
        days = (all_symbols_df['timestamp'].max() - all_symbols_df['timestamp'].min()).days
        candles_per_day = 288  # 5-min intervals
        
        print(f"\nDataset: {days} days, {candles_per_day} candles/day")
        
        # Analyze profit distribution
        gains = all_symbols_df['max_gain_60m'].values
        
        percentiles = [50, 60, 70, 75, 80, 85, 90, 95, 99]
        
        print("\n" + "-"*80)
        print("Profit Percentile Analysis (max_gain_60m):")
        print("-"*80)
        print(f"{'Percentile':<15} {'Min Gain %':>12} {'Signals/Day':>15}")
        print("-"*80)
        
        for pct in percentiles:
            threshold = np.percentile(gains, pct)
            signals_above = (gains > threshold).sum()
            signals_per_day = signals_above / days
            
            print(f"{pct:>3}th percentile {threshold:>12.2f}% {signals_per_day:>15.1f}")
        
        # Target: 1-2 signals per day per symbol
        # Find percentile that gives ~1.5 signals/day
        target_signals_per_day = 1.5
        
        for pct in range(50, 100):
            threshold = np.percentile(gains, pct)
            signals_above = (gains > threshold).sum()
            signals_per_day = signals_above / days
            
            if signals_per_day <= target_signals_per_day:
                print(f"\n✅ Target achieved at {pct}th percentile: {threshold:.2f}% min gain")
                print(f"   Expected signals: {signals_per_day:.2f}/day per symbol")
                
                self.analysis_results['optimal_threshold'] = threshold
                self.analysis_results['target_percentile'] = pct
                break
    
    # ============================================================================
    # PHASE 4: ML MODELING + TTL OPTIMIZATION
    # ============================================================================
    
    def build_ml_models(self):
        """
        Build ML models to predict profitable trades
        Test multiple TTL values to find optimal
        """
        print("\n" + "="*80)
        print("PHASE 4: ML MODELING + TTL OPTIMIZATION")
        print("="*80)
        
        all_symbols_df = pd.concat(self.all_data.values(), ignore_index=True)
        
        # Feature columns (indicators)
        feature_cols = ['rsi', 'ema_cross', 'vwap_distance', 'adx', 'volume_ratio',
                        'price_change_1h', 'price_change_4h', 'volatility']
        
        # Test different TTL values
        ttl_values = [15, 30, 60, 90, 120]
        
        results = {}
        
        for ttl in ttl_values:
            print(f"\n{'='*80}")
            print(f"Testing TTL = {ttl} minutes")
            print('='*80)
            
            # Define profitable trade (binary classification)
            # BUY: future gain > 1%
            # SELL: future drop > 1%
            
            gain_col = f'max_gain_{ttl}m'
            drop_col = f'max_drop_{ttl}m'
            
            # Create binary targets
            all_symbols_df['buy_signal'] = (all_symbols_df[gain_col] > 1.0).astype(int)
            all_symbols_df['sell_signal'] = (all_symbols_df[drop_col] > 1.0).astype(int)
            
            # Prepare data
            X = all_symbols_df[feature_cols].fillna(0)
            
            # Time series split (no future data leakage)
            tscv = TimeSeriesSplit(n_splits=5)
            
            # Train BUY model
            buy_scores = []
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train = all_symbols_df['buy_signal'].iloc[train_idx]
                y_test = all_symbols_df['buy_signal'].iloc[test_idx]
                
                model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
                model.fit(X_train, y_train)
                
                # Predict probabilities
                y_pred = model.predict(X_test)
                
                # Calculate metrics
                # Only consider top 10% predictions as signals
                threshold = np.percentile(y_pred, 90)
                signals = y_pred > threshold
                
                if signals.sum() > 0:
                    precision = y_test[signals].mean()
                    buy_scores.append(precision)
            
            buy_precision = np.mean(buy_scores) if buy_scores else 0
            
            # Train SELL model
            sell_scores = []
            for train_idx, test_idx in tscv.split(X):
                X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
                y_train = all_symbols_df['sell_signal'].iloc[train_idx]
                y_test = all_symbols_df['sell_signal'].iloc[test_idx]
                
                model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
                model.fit(X_train, y_train)
                
                y_pred = model.predict(X_test)
                
                threshold = np.percentile(y_pred, 90)
                signals = y_pred > threshold
                
                if signals.sum() > 0:
                    precision = y_test[signals].mean()
                    sell_scores.append(precision)
            
            sell_precision = np.mean(sell_scores) if sell_scores else 0
            
            print(f"\n  BUY Model Precision: {buy_precision*100:.1f}%")
            print(f"  SELL Model Precision: {sell_precision*100:.1f}%")
            
            results[ttl] = {
                'buy_precision': buy_precision,
                'sell_precision': sell_precision,
                'avg_precision': (buy_precision + sell_precision) / 2
            }
        
        # Find best TTL
        best_ttl = max(results.items(), key=lambda x: x[1]['avg_precision'])
        
        print("\n" + "="*80)
        print("TTL OPTIMIZATION RESULTS:")
        print("="*80)
        print(f"{'TTL (min)':<12} {'BUY Precision':>15} {'SELL Precision':>15} {'Average':>15}")
        print("-"*80)
        
        for ttl, metrics in sorted(results.items()):
            print(f"{ttl:<12} {metrics['buy_precision']*100:>14.1f}% {metrics['sell_precision']*100:>14.1f}% {metrics['avg_precision']*100:>14.1f}%")
        
        print("\n" + "="*80)
        print(f"✅ OPTIMAL TTL: {best_ttl[0]} minutes")
        print(f"   Average Precision: {best_ttl[1]['avg_precision']*100:.1f}%")
        print("="*80)
        
        self.analysis_results['ml_results'] = results
        self.analysis_results['optimal_ttl'] = best_ttl[0]
        
        return results
    
    # ============================================================================
    # SAVE RESULTS
    # ============================================================================
    
    def save_analysis_results(self):
        """
        Save all analysis results to JSON for review
        """
        output_file = self.data_dir.parent / 'formula_discovery_results.json'
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(v) for v in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_types(v) for v in obj)
            return obj
        
        results_serializable = convert_types(self.analysis_results)
        
        with open(output_file, 'w') as f:
            json.dump(results_serializable, f, indent=2)
        
        print(f"\n✅ Results saved to {output_file}")
    
    def run_full_analysis(self):
        """
        Execute all phases of formula discovery
        """
        # Phase 2: Data enrichment
        self.load_and_enrich_all_symbols()
        
        # Phase 3: Statistical analysis
        self.analyze_indicator_correlations(ttl_target=60)
        self.analyze_buy_sell_asymmetry(ttl_target=60)
        self.calculate_optimal_signal_frequency()
        
        # Phase 4: ML modeling
        self.build_ml_models()
        
        # Save results
        self.save_analysis_results()
        
        print("\n" + "="*80)
        print("✅ FORMULA DISCOVERY COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("  1. Review formula_discovery_results.json")
        print("  2. Phase 5: Synthesize interpretable formula from ML insights")
        print("  3. Phase 6: Validate against broken baseline (18% WR)")
        print("="*80)


if __name__ == '__main__':
    engine = FormulaDiscoveryEngine()
    engine.run_full_analysis()
