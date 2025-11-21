"""
Comprehensive Statistical Analysis: BTC-Altcoin Lead-Lag Relationships
Econometric analysis using tick-level data from Binance Vision

Methodology:
1. Correlation Analysis (Pearson, Spearman, Kendall) + Rolling Windows
2. Beta Regression (sensitivity to BTC movements)
3. Cross-Correlation Function (CCF) for lag detection
4. Granger Causality Tests
5. VAR (Vector Autoregression) Model
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import correlate
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR
from sklearn.linear_model import LinearRegression
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class BTCLeadLagAnalyzer:
    """Comprehensive BTC-Altcoin Lead-Lag Statistical Analyzer"""
    
    def __init__(self, date='2025-11-14', max_rows=500000):
        self.date = date
        self.max_rows = max_rows
        self.results = {}
        
    def load_tick_data(self, symbol):
        """Load and preprocess tick-level data"""
        filepath = f"data/tick_data/{symbol}-aggTrades-{self.date}.csv"
        
        try:
            df = pd.read_csv(filepath, nrows=self.max_rows)
            df['timestamp'] = pd.to_datetime(df['transact_time'], unit='ms')
            df['price'] = df['price'].astype(float)
            
            # Resample to 1-second bars
            df = df.set_index('timestamp')
            df_1s = df['price'].resample('1s').last().ffill()
            
            # Calculate returns
            returns = df_1s.pct_change().dropna()
            
            return df_1s, returns
        except Exception as e:
            print(f"  ❌ Error loading {symbol}: {e}")
            return None, None
    
    def calculate_correlations(self, btc_returns, alt_returns, symbol):
        """
        1️⃣ Calculate instant correlations: Pearson, Spearman, Kendall
        """
        # Align timestamps
        aligned = pd.concat([btc_returns, alt_returns], axis=1, join='inner')
        aligned.columns = ['btc', 'alt']
        aligned = aligned.dropna()
        
        if len(aligned) < 100:
            return None
        
        # Calculate correlations
        pearson_corr, pearson_p = stats.pearsonr(aligned['btc'], aligned['alt'])
        spearman_corr, spearman_p = stats.spearmanr(aligned['btc'], aligned['alt'])
        kendall_corr, kendall_p = stats.kendalltau(aligned['btc'], aligned['alt'])
        
        # Rolling correlations
        windows = {'1m': 60, '5m': 300, '15m': 900}
        rolling_corr = {}
        
        for window_name, window_size in windows.items():
            if len(aligned) > window_size:
                roll = aligned['btc'].rolling(window_size).corr(aligned['alt'])
                rolling_corr[window_name] = {
                    'mean': roll.mean(),
                    'std': roll.std(),
                    'min': roll.min(),
                    'max': roll.max()
                }
        
        return {
            'pearson': {'corr': pearson_corr, 'p_value': pearson_p},
            'spearman': {'corr': spearman_corr, 'p_value': spearman_p},
            'kendall': {'corr': kendall_corr, 'p_value': kendall_p},
            'rolling': rolling_corr,
            'sample_size': len(aligned)
        }
    
    def calculate_beta(self, btc_returns, alt_returns, symbol):
        """
        2️⃣ Beta regression: r_ALT(t) = α + β·r_BTC(t) + ε
        """
        aligned = pd.concat([btc_returns, alt_returns], axis=1, join='inner')
        aligned.columns = ['btc', 'alt']
        aligned = aligned.dropna()
        
        if len(aligned) < 100:
            return None
        
        X = aligned['btc'].values.reshape(-1, 1)
        y = aligned['alt'].values
        
        # Linear regression
        model = LinearRegression()
        model.fit(X, y)
        
        beta = model.coef_[0]
        alpha = model.intercept_
        r_squared = model.score(X, y)
        
        # Calculate residuals
        y_pred = model.predict(X)
        residuals = y - y_pred
        mse = np.mean(residuals**2)
        
        # Rolling beta (5-minute windows)
        rolling_betas = []
        window = 300  # 5 minutes
        
        if len(aligned) > window:
            for i in range(window, len(aligned)):
                X_window = aligned['btc'].iloc[i-window:i].values.reshape(-1, 1)
                y_window = aligned['alt'].iloc[i-window:i].values
                
                temp_model = LinearRegression()
                temp_model.fit(X_window, y_window)
                rolling_betas.append(temp_model.coef_[0])
        
        beta_stability = {
            'mean': np.mean(rolling_betas) if rolling_betas else beta,
            'std': np.std(rolling_betas) if rolling_betas else 0,
            'min': np.min(rolling_betas) if rolling_betas else beta,
            'max': np.max(rolling_betas) if rolling_betas else beta
        }
        
        return {
            'beta': beta,
            'alpha': alpha,
            'r_squared': r_squared,
            'mse': mse,
            'beta_stability': beta_stability,
            'sample_size': len(aligned)
        }
    
    def calculate_ccf(self, btc_returns, alt_returns, max_lag=120):
        """
        3️⃣ Cross-Correlation Function: ρ(τ) = corr(r_ALT(t), r_BTC(t-τ))
        Find optimal lag where correlation is maximum
        """
        aligned = pd.concat([btc_returns, alt_returns], axis=1, join='inner')
        aligned.columns = ['btc', 'alt']
        aligned = aligned.dropna()
        
        if len(aligned) < max_lag * 2:
            return None
        
        btc_arr = aligned['btc'].values
        alt_arr = aligned['alt'].values
        
        # Normalize
        btc_norm = (btc_arr - np.mean(btc_arr)) / np.std(btc_arr)
        alt_norm = (alt_arr - np.mean(alt_arr)) / np.std(alt_arr)
        
        ccf_values = []
        lags = range(0, max_lag + 1)
        
        for lag in lags:
            if lag == 0:
                corr = np.corrcoef(btc_norm, alt_norm)[0, 1]
            else:
                # ALT(t) vs BTC(t-lag)
                corr = np.corrcoef(alt_norm[lag:], btc_norm[:-lag])[0, 1]
            
            ccf_values.append(corr)
        
        ccf_values = np.array(ccf_values)
        
        # Find maximum correlation and corresponding lag
        max_idx = np.argmax(np.abs(ccf_values))
        optimal_lag = lags[max_idx]
        max_corr = ccf_values[max_idx]
        
        # Correlation at 0 lag
        corr_0_lag = ccf_values[0]
        
        return {
            'ccf_values': ccf_values.tolist(),
            'lags': list(lags),
            'optimal_lag': optimal_lag,
            'max_corr': max_corr,
            'corr_0_lag': corr_0_lag,
            'improvement': max_corr - corr_0_lag
        }
    
    def granger_causality_test(self, btc_returns, alt_returns, max_lag=10):
        """
        4️⃣ Granger Causality Test: Does BTC predict future ALT returns?
        """
        aligned = pd.concat([btc_returns, alt_returns], axis=1, join='inner')
        aligned.columns = ['btc', 'alt']
        aligned = aligned.dropna()
        
        if len(aligned) < 200:
            return None
        
        # Prepare data for Granger test
        data = aligned[['alt', 'btc']].values
        
        try:
            # Test if BTC Granger-causes ALT
            gc_result = grangercausalitytests(data, maxlag=max_lag, verbose=False)
            
            # Extract p-values for each lag
            p_values = {}
            f_stats = {}
            
            for lag in range(1, max_lag + 1):
                ssr_ftest = gc_result[lag][0]['ssr_ftest']
                p_values[lag] = ssr_ftest[1]
                f_stats[lag] = ssr_ftest[0]
            
            # Find most significant lag
            min_p_lag = min(p_values, key=p_values.get)
            min_p_value = p_values[min_p_lag]
            
            # Determine if significant at 5% level
            is_significant = min_p_value < 0.05
            
            return {
                'p_values': p_values,
                'f_stats': f_stats,
                'best_lag': min_p_lag,
                'best_p_value': min_p_value,
                'is_significant': is_significant,
                'interpretation': 'BTC Granger-causes ALT' if is_significant else 'No Granger causality'
            }
        except Exception as e:
            return {'error': str(e)}
    
    def var_model_analysis(self, btc_returns, alt_returns, max_lag=10):
        """
        5️⃣ VAR Model: Vector Autoregression for bidirectional lead-lag
        """
        aligned = pd.concat([btc_returns, alt_returns], axis=1, join='inner')
        aligned.columns = ['btc', 'alt']
        aligned = aligned.dropna()
        
        if len(aligned) < 300:
            return None
        
        try:
            # Fit VAR model
            model = VAR(aligned)
            
            # Select optimal lag using AIC
            results = model.fit(maxlags=max_lag, ic='aic')
            optimal_lag = results.k_ar
            
            # Impulse Response Analysis
            irf = results.irf(10)
            
            # Extract coefficients correctly by selecting lagged BTC/ALT terms
            # BTC -> ALT: sum coefficients from 'alt' equation where BTC lags appear
            # ALT -> BTC: sum coefficients from 'btc' equation where ALT lags appear
            
            params_df = results.params
            btc_to_alt_coef = 0
            alt_to_btc_coef = 0
            
            for lag_i in range(1, optimal_lag + 1):
                btc_lag_label = f'L{lag_i}.btc'
                alt_lag_label = f'L{lag_i}.alt'
                
                # Check BTC lag independently
                if btc_lag_label in params_df.index:
                    btc_to_alt_coef += params_df.loc[btc_lag_label, 'alt']
                
                # Check ALT lag independently
                if alt_lag_label in params_df.index:
                    alt_to_btc_coef += params_df.loc[alt_lag_label, 'btc']
            
            # Determine lead-lag relationship based on magnitude
            if abs(btc_to_alt_coef) > abs(alt_to_btc_coef):
                relationship = 'BTC leads ALT'
            else:
                relationship = 'ALT leads BTC'
            
            return {
                'optimal_lag': optimal_lag,
                'btc_to_alt_coef': btc_to_alt_coef,
                'alt_to_btc_coef': alt_to_btc_coef,
                'relationship': relationship,
                'aic': results.aic,
                'bic': results.bic
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_coin(self, symbol, btc_price, btc_returns):
        """Run complete analysis for one altcoin"""
        print(f"\n{'='*80}")
        print(f"📊 Analyzing {symbol.replace('USDT', '')}")
        print(f"{'='*80}")
        
        # Load data
        alt_price, alt_returns = self.load_tick_data(symbol)
        
        if alt_returns is None:
            print(f"  ❌ Failed to load data")
            return None
        
        print(f"  ✅ Loaded {len(alt_returns):,} seconds of data")
        
        # 1. Correlations
        print(f"  🔄 Calculating correlations...")
        corr_results = self.calculate_correlations(btc_returns, alt_returns, symbol)
        
        # 2. Beta regression
        print(f"  📈 Running beta regression...")
        beta_results = self.calculate_beta(btc_returns, alt_returns, symbol)
        
        # 3. CCF
        print(f"  🔍 Computing Cross-Correlation Function...")
        ccf_results = self.calculate_ccf(btc_returns, alt_returns, max_lag=120)
        
        # 4. Granger causality
        print(f"  🧪 Testing Granger causality...")
        granger_results = self.granger_causality_test(btc_returns, alt_returns, max_lag=10)
        
        # 5. VAR model
        print(f"  🔬 Building VAR model...")
        var_results = self.var_model_analysis(btc_returns, alt_returns, max_lag=10)
        
        return {
            'symbol': symbol,
            'correlations': corr_results,
            'beta': beta_results,
            'ccf': ccf_results,
            'granger': granger_results,
            'var': var_results
        }
    
    def generate_summary_table(self, all_results):
        """Generate final summary table"""
        print("\n" + "="*120)
        print("📋 COMPREHENSIVE STATISTICAL SUMMARY TABLE")
        print("="*120)
        
        # Table header
        header = f"{'Coin':<8} {'Corr(0)':<9} {'MaxCorr':<9} {'Lag(s)':<8} {'Beta':<7} {'R²':<7} {'Granger':<10} {'Trading Signal':<20}"
        print(header)
        print("-" * 120)
        
        summary_data = []
        
        for result in all_results:
            if result is None:
                continue
            
            symbol = result['symbol'].replace('USDT', '')
            
            # Extract key metrics
            corr_0 = result['correlations']['pearson']['corr'] if result['correlations'] else 0
            max_corr = result['ccf']['max_corr'] if result['ccf'] else 0
            lag = result['ccf']['optimal_lag'] if result['ccf'] else 0
            beta = result['beta']['beta'] if result['beta'] else 0
            r2 = result['beta']['r_squared'] if result['beta'] else 0
            
            granger_sig = '✅ YES' if (result['granger'] and result['granger'].get('is_significant')) else '❌ NO'
            granger_p = result['granger']['best_p_value'] if (result['granger'] and 'best_p_value' in result['granger']) else 1.0
            
            # Trading signal interpretation
            if lag > 10 and max_corr > 0.7 and granger_sig == '✅ YES':
                signal = '🎯 EXCELLENT LAG'
            elif lag > 5 and max_corr > 0.6:
                signal = '✅ GOOD LAG'
            elif corr_0 > 0.7 and beta > 0.8:
                signal = '⚡ FAST FOLLOWER'
            elif corr_0 < 0.3:
                signal = '❌ WEAK CORRELATION'
            else:
                signal = '⚠️ MODERATE'
            
            # Print row
            row = f"{symbol:<8} {corr_0:>8.3f} {max_corr:>8.3f} {lag:>7d} {beta:>6.2f} {r2:>6.3f} {granger_sig:<10} {signal:<20}"
            print(row)
            
            summary_data.append({
                'symbol': symbol,
                'corr_0': corr_0,
                'max_corr': max_corr,
                'lag': lag,
                'beta': beta,
                'r2': r2,
                'granger_significant': granger_sig == '✅ YES',
                'granger_p': granger_p,
                'signal': signal,
                'result': result
            })
        
        print("-" * 120)
        
        return summary_data
    
    def trading_interpretation(self, summary_data):
        """Generate trading-focused interpretation"""
        print("\n" + "="*120)
        print("💡 TRADING INTERPRETATION & RECOMMENDATIONS")
        print("="*120)
        
        # Sort by different criteria
        by_lag = sorted(summary_data, key=lambda x: x['lag'], reverse=True)
        by_corr = sorted(summary_data, key=lambda x: x['corr_0'], reverse=True)
        by_beta = sorted(summary_data, key=lambda x: abs(x['beta'] - 1.0))
        
        print("\n🎯 BEST COINS FOR LAG-TRADING (Highest Lag):")
        for i, coin in enumerate(by_lag[:3], 1):
            print(f"  {i}. {coin['symbol']}: {coin['lag']}s lag, {coin['max_corr']:.3f} max corr, "
                  f"Granger: {'YES' if coin['granger_significant'] else 'NO'}")
        
        print("\n⚡ COINS THAT COPY BTC 1:1 (Beta ≈ 1.0):")
        for i, coin in enumerate(by_beta[:3], 1):
            print(f"  {i}. {coin['symbol']}: β={coin['beta']:.3f}, R²={coin['r2']:.3f}, "
                  f"Corr={coin['corr_0']:.3f}")
        
        print("\n🔗 STRONGEST BTC FOLLOWERS (Highest Correlation):")
        for i, coin in enumerate(by_corr[:3], 1):
            print(f"  {i}. {coin['symbol']}: {coin['corr_0']:.3f} corr, β={coin['beta']:.3f}")
        
        # Identify useless coins
        weak_coins = [c for c in summary_data if c['corr_0'] < 0.3 or not c['granger_significant']]
        
        if weak_coins:
            print("\n❌ WEAK/USELESS FOR BTC FOLLOWING:")
            for coin in weak_coins:
                print(f"  • {coin['symbol']}: Corr={coin['corr_0']:.3f}, "
                      f"Granger p={coin['granger_p']:.4f} (not significant)")
        
        print("\n📊 STATISTICAL SIGNIFICANCE NOTES:")
        print("  • Granger p-value < 0.05 = BTC significantly predicts ALT")
        print("  • Lag > 10s = Tradable delay window")
        print("  • R² > 0.5 = Strong predictive power")
        print("  • Beta ≈ 1.0 = Moves 1:1 with BTC")
        print("  • Corr > 0.7 = Strong positive relationship")
        
        print("\n" + "="*120)


def main():
    print("="*120)
    print("BTC-ALTCOIN LEAD-LAG STATISTICAL ANALYSIS")
    print("Econometric Analysis Using Tick-Level Data")
    print("="*120)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    analyzer = BTCLeadLagAnalyzer(date='2025-11-14', max_rows=500000)
    
    # Load BTC data
    print("📥 Loading BTC baseline...")
    btc_price, btc_returns = analyzer.load_tick_data('BTCUSDT')
    
    if btc_returns is None:
        print("❌ Failed to load BTC data")
        return
    
    print(f"  ✅ BTC: {len(btc_returns):,} seconds of returns data")
    
    # Analyze all altcoins
    symbols = ['ETHUSDT', 'TRXUSDT', 'XRPUSDT', 'LINKUSDT', 'ADAUSDT']
    all_results = []
    
    for symbol in symbols:
        result = analyzer.analyze_coin(symbol, btc_price, btc_returns)
        if result:
            all_results.append(result)
            analyzer.results[symbol] = result
    
    # Generate summary
    summary_data = analyzer.generate_summary_table(all_results)
    
    # Trading interpretation
    analyzer.trading_interpretation(summary_data)
    
    # Save detailed report
    import json
    with open('analysis/results/btc_leadlag_statistical_report.json', 'w') as f:
        json.dump({
            'date': analyzer.date,
            'timestamp': datetime.now().isoformat(),
            'results': analyzer.results
        }, f, indent=2, default=str)
    
    print(f"\n💾 Detailed report saved: analysis/results/btc_leadlag_statistical_report.json")
    print(f"🏁 Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == '__main__':
    main()
