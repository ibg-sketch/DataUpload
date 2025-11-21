#!/usr/bin/env python3
"""
BTC-Altcoin Lead-Lag Analysis for ALL 11 Coins
Uses 5-minute data from analysis_log.csv for statistical analysis
Combines with tick-level lag data where available (ETH, LINK, XRP, ADA, TRX)
"""

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# All 11 coins tracked in the system
ALL_COINS = [
    'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT', 'DOGEUSDT',
    'LINKUSDT', 'XRPUSDT', 'TRXUSDT', 'ADAUSDT', 'HYPEUSDT'
]

# Coins with tick-level lag data available
TICK_LAG_AVAILABLE = {
    'ETHUSDT': 5.1,
    'LINKUSDT': 5.3,
    'XRPUSDT': 5.3,
    'ADAUSDT': 5.5,
    'TRXUSDT': 46.8
}


def load_5min_data():
    """Load 5-minute candle data from analysis_log.csv"""
    print("📊 Loading 5-minute data from analysis_log.csv...")
    
    df = pd.read_csv('analysis_log.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter last 7 days for consistency
    df = df.sort_values('timestamp')
    cutoff = df['timestamp'].max() - pd.Timedelta(days=7)
    df = df[df['timestamp'] >= cutoff]
    
    print(f"   ✅ Loaded {len(df):,} records")
    print(f"   📅 Period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def calculate_returns(prices):
    """Calculate percentage returns"""
    return prices.pct_change().dropna()


def analyze_coin_vs_btc(btc_prices, alt_prices, symbol):
    """
    Comprehensive statistical analysis of ALT vs BTC relationship
    Returns correlation, beta, R², Granger p-value
    """
    
    # Merge prices on common timestamps
    combined = pd.DataFrame({
        'btc': btc_prices,
        'alt': alt_prices
    }).dropna()
    
    if len(combined) < 100:
        print(f"   ⚠️ {symbol}: Insufficient data ({len(combined)} points)")
        return None
    
    # Calculate returns
    btc_ret = calculate_returns(combined['btc'])
    alt_ret = calculate_returns(combined['alt'])
    
    if len(btc_ret) < 100:
        print(f"   ⚠️ {symbol}: Insufficient returns ({len(btc_ret)} points)")
        return None
    
    # 1. Correlations
    pearson_corr, _ = stats.pearsonr(btc_ret, alt_ret)
    spearman_corr, _ = stats.spearmanr(btc_ret, alt_ret)
    kendall_corr, _ = stats.kendalltau(btc_ret, alt_ret)
    
    # 2. Beta Regression (R²)
    X = btc_ret.values.reshape(-1, 1)
    y = alt_ret.values
    
    model = LinearRegression()
    model.fit(X, y)
    beta = model.coef_[0]
    r_squared = model.score(X, y)
    
    # 3. Granger Causality Test (BTC -> ALT)
    try:
        # Combine for Granger test
        data = pd.DataFrame({'btc': btc_ret.values, 'alt': alt_ret.values})
        
        # Test with lag=1 (5-minute intervals)
        gc_result = grangercausalitytests(data[['alt', 'btc']], maxlag=1, verbose=False)
        granger_pvalue = gc_result[1][0]['ssr_ftest'][1]
        granger_significant = granger_pvalue < 0.05
        
    except Exception as e:
        granger_pvalue = 1.0
        granger_significant = False
    
    # 4. VAR Model for lead-lag coefficients
    try:
        var_model = VAR(data)
        var_results = var_model.fit(maxlags=3, ic='aic')
        optimal_lag = var_results.k_ar
        
        # Extract BTC->ALT coefficient
        params_df = var_results.params
        btc_to_alt_coef = 0
        
        for lag_i in range(1, optimal_lag + 1):
            btc_lag_label = f'L{lag_i}.btc'
            if btc_lag_label in params_df.index:
                btc_to_alt_coef += params_df.loc[btc_lag_label, 'alt']
        
    except:
        optimal_lag = 0
        btc_to_alt_coef = 0
    
    return {
        'symbol': symbol,
        'pearson_corr': float(round(pearson_corr, 3)),
        'spearman_corr': float(round(spearman_corr, 3)),
        'kendall_corr': float(round(kendall_corr, 3)),
        'beta': float(round(beta, 2)),
        'r_squared': float(round(r_squared, 3)),
        'granger_pvalue': float(round(granger_pvalue, 4)),
        'granger_significant': bool(granger_significant),
        'var_optimal_lag': int(optimal_lag),
        'btc_to_alt_coef': float(round(btc_to_alt_coef, 4)),
        'tick_lag_sec': TICK_LAG_AVAILABLE.get(symbol, None),
        'data_points': int(len(btc_ret))
    }


def generate_trading_signal(result):
    """Generate trading recommendation based on analysis"""
    
    corr = result['pearson_corr']
    beta = result['beta']
    r2 = result['r_squared']
    tick_lag = result['tick_lag_sec']
    
    # Strong follower criteria
    if corr > 0.7 and r2 > 0.45 and tick_lag and tick_lag < 10:
        return "✅ EXCELLENT LAG-TRADE"
    elif corr > 0.65 and r2 > 0.4 and tick_lag and tick_lag < 10:
        return "✅ GOOD LAG-TRADE"
    elif corr > 0.7 and abs(beta - 1.0) < 0.15:
        return "🔗 1:1 FOLLOWER"
    elif corr > 0.6 and r2 > 0.35:
        return "⚠️ MODERATE"
    elif corr > 0.5:
        return "📊 WEAK POSITIVE"
    else:
        return "❌ POOR CORRELATION"


def generate_recommendation(result):
    """Generate human-readable trading recommendation"""
    
    corr = result['pearson_corr']
    r2 = result['r_squared']
    tick_lag = result['tick_lag_sec']
    
    if tick_lag and tick_lag < 10 and corr > 0.65:
        return f"Viable {int(tick_lag)}s lag window"
    elif corr > 0.7 and r2 > 0.45:
        return "Strong BTC correlation"
    elif corr > 0.6:
        return "Moderate correlation"
    elif tick_lag and tick_lag > 40:
        return "Long lag but weak correlation"
    else:
        return "Limited predictive value"


def main():
    """Main analysis routine"""
    
    print("="*100)
    print("📊 BTC-ALTCOIN LEAD-LAG ANALYSIS: ALL 11 COINS")
    print("="*100)
    print()
    
    # Load data
    df = load_5min_data()
    
    # Extract BTC prices and round timestamps to 5-minute intervals
    btc_df = df[df['symbol'] == 'BTCUSDT'][['timestamp', 'price']].copy()
    btc_df['timestamp_rounded'] = btc_df['timestamp'].dt.floor('5min')
    btc_df = btc_df.sort_values('timestamp_rounded').drop_duplicates('timestamp_rounded')
    btc_df = btc_df.set_index('timestamp_rounded')['price']
    
    print(f"\n📈 BTC data: {len(btc_df):,} 5-minute candles")
    
    # Analyze each altcoin
    results = []
    
    for symbol in sorted(ALL_COINS):
        print(f"\n{'='*100}")
        print(f"📊 Analyzing {symbol}")
        print('='*100)
        
        # Extract altcoin prices and round timestamps to 5-minute intervals
        alt_df = df[df['symbol'] == symbol][['timestamp', 'price']].copy()
        alt_df['timestamp_rounded'] = alt_df['timestamp'].dt.floor('5min')
        alt_df = alt_df.sort_values('timestamp_rounded').drop_duplicates('timestamp_rounded')
        alt_df = alt_df.set_index('timestamp_rounded')['price']
        
        if len(alt_df) < 100:
            print(f"   ⚠️ Skipping {symbol}: insufficient data ({len(alt_df)} points)")
            continue
        
        print(f"   ✅ Loaded {len(alt_df):,} 5-minute candles")
        
        # Perform analysis
        result = analyze_coin_vs_btc(btc_df, alt_df, symbol)
        
        if result:
            result['trading_signal'] = generate_trading_signal(result)
            result['recommendation'] = generate_recommendation(result)
            results.append(result)
            
            print(f"   📊 Correlation: {result['pearson_corr']:.3f}")
            print(f"   📈 Beta: {result['beta']:.2f}, R²: {result['r_squared']:.3f}")
            print(f"   🧪 Granger: {'✅ YES' if result['granger_significant'] else '❌ NO'} (p={result['granger_pvalue']:.4f})")
            if result['tick_lag_sec']:
                print(f"   ⏱️  Tick-lag: {result['tick_lag_sec']}s")
            print(f"   💡 Signal: {result['trading_signal']}")
    
    # Generate summary table
    print("\n" + "="*140)
    print("📋 COMPREHENSIVE SUMMARY TABLE: ALL 11 COINS")
    print("="*140)
    
    # Sort by correlation (descending)
    results_sorted = sorted(results, key=lambda x: x['pearson_corr'], reverse=True)
    
    print(f"{'Coin':<10} │ {'Corr':<6} │ {'Beta':<6} │ {'R²':<6} │ {'Lag(s)':<8} │ {'Granger':<9} │ {'Trading Signal':<25} │ {'Recommendation':<30}")
    print("─" * 140)
    
    for r in results_sorted:
        lag_str = f"{r['tick_lag_sec']:.1f}" if r['tick_lag_sec'] else "N/A"
        granger_str = "✅ YES" if r['granger_significant'] else "❌ NO"
        
        print(f"{r['symbol']:<10} │ {r['pearson_corr']:>6.3f} │ {r['beta']:>6.2f} │ {r['r_squared']:>6.3f} │ {lag_str:>8} │ {granger_str:<9} │ {r['trading_signal']:<25} │ {r['recommendation']:<30}")
    
    print("─" * 140)
    
    # Save results
    output = {
        'analysis_date': datetime.now().isoformat(),
        'data_source': 'analysis_log.csv (5-minute candles)',
        'coins_analyzed': len(results),
        'results': {r['symbol']: r for r in results}
    }
    
    with open('analysis/results/btc_leadlag_all_11_coins.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Full results saved: analysis/results/btc_leadlag_all_11_coins.json")
    print(f"🏁 Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == '__main__':
    main()
