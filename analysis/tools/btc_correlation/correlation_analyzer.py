"""
Correlation Analysis Module for BTC vs Altcoins
Computes lag correlations and directional similarity
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Tuple


def compute_returns(df: pd.DataFrame) -> pd.Series:
    """
    Compute log returns from close prices with zero-variance guard
    
    Args:
        df: DataFrame with 'close' column
    
    Returns:
        Series of log returns
    
    Note:
        Returns inf/-inf for zero/negative prices (filtered by dropna later)
        Guards against division by zero in correlation calculations
    """
    returns = np.log(df['close'] / df['close'].shift(1))
    
    # Replace inf/-inf with NaN (will be dropped in correlation calculations)
    returns = returns.replace([np.inf, -np.inf], np.nan)
    
    return returns


def compute_lag_correlation(
    btc_returns: pd.Series,
    alt_returns: pd.Series,
    max_lag: int = 12
) -> Tuple[float, int, float]:
    """
    Compute cross-correlation with time lags to find optimal lag
    
    Args:
        btc_returns: BTC log returns
        alt_returns: Altcoin log returns
        max_lag: Maximum lag to test (in 5-min periods, default ±60 minutes)
    
    Returns:
        Tuple of (best_correlation, optimal_lag_minutes, p_value)
        - best_correlation: Pearson correlation at optimal lag
        - optimal_lag_minutes: Lag in minutes (negative=leads BTC, positive=lags BTC)
        - p_value: Statistical significance
    """
    btc_clean = btc_returns.dropna()
    alt_clean = alt_returns.dropna()
    
    min_len = min(len(btc_clean), len(alt_clean))
    btc_clean = btc_clean.iloc[:min_len]
    alt_clean = alt_clean.iloc[:min_len]
    
    best_corr = 0
    best_lag = 0
    
    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            btc_slice = btc_clean
            alt_slice = alt_clean
        elif lag > 0:
            btc_slice = btc_clean.iloc[:-lag]
            alt_slice = alt_clean.iloc[lag:]
        else:
            abs_lag = abs(lag)
            btc_slice = btc_clean.iloc[abs_lag:]
            alt_slice = alt_clean.iloc[:-abs_lag]
        
        if len(btc_slice) < 10:
            continue
        
        btc_slice = btc_slice.reset_index(drop=True)
        alt_slice = alt_slice.reset_index(drop=True)
        
        corr = btc_slice.corr(alt_slice)
        
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag
    
    if best_lag == 0:
        correlation, p_value = stats.pearsonr(btc_clean, alt_clean)
    elif best_lag > 0:
        btc_slice = btc_clean.iloc[:-best_lag].reset_index(drop=True)
        alt_slice = alt_clean.iloc[best_lag:].reset_index(drop=True)
        correlation, p_value = stats.pearsonr(btc_slice, alt_slice)
    else:
        abs_lag = abs(best_lag)
        btc_slice = btc_clean.iloc[abs_lag:].reset_index(drop=True)
        alt_slice = alt_clean.iloc[:-abs_lag].reset_index(drop=True)
        correlation, p_value = stats.pearsonr(btc_slice, alt_slice)
    
    lag_minutes = best_lag * 5
    
    return correlation, lag_minutes, p_value


def compute_directional_similarity(
    btc_returns: pd.Series,
    alt_returns: pd.Series
) -> Tuple[float, int, int, int]:
    """
    Compute percentage of candles where both coins move in same direction
    
    Args:
        btc_returns: BTC log returns
        alt_returns: Altcoin log returns
    
    Returns:
        Tuple of (similarity_pct, same_direction_count, opposite_count, total_count)
        - similarity_pct: Percentage of candles moving in same direction
        - same_direction_count: Count of candles moving together
        - opposite_count: Count of candles moving opposite
        - total_count: Total candles analyzed
    """
    btc_clean = btc_returns.dropna()
    alt_clean = alt_returns.dropna()
    
    min_len = min(len(btc_clean), len(alt_clean))
    btc_clean = btc_clean.iloc[:min_len]
    alt_clean = alt_clean.iloc[:min_len]
    
    btc_direction = np.sign(btc_clean)
    alt_direction = np.sign(alt_clean)
    
    same_direction = (btc_direction == alt_direction).sum()
    total = len(btc_direction)
    opposite = total - same_direction
    
    similarity_pct = (same_direction / total * 100) if total > 0 else 0
    
    return similarity_pct, same_direction, opposite, total


def analyze_all_coins(data: Dict[str, pd.DataFrame], max_lag: int = 12) -> pd.DataFrame:
    """
    Analyze all altcoins vs BTC
    
    Args:
        data: Dictionary of aligned DataFrames (must include 'BTCUSDT')
        max_lag: Maximum lag for correlation analysis
    
    Returns:
        DataFrame with correlation metrics for each altcoin
    """
    if 'BTCUSDT' not in data:
        raise ValueError("BTCUSDT data required for correlation analysis")
    
    btc_df = data['BTCUSDT']
    btc_returns = compute_returns(btc_df)
    
    results = []
    
    print(f"\n📊 Analyzing correlation with BTC (max lag: ±{max_lag*5} minutes)...\n")
    
    for symbol in sorted(data.keys()):
        if symbol == 'BTCUSDT':
            continue
        
        alt_df = data[symbol]
        alt_returns = compute_returns(alt_df)
        
        correlation, lag_minutes, p_value = compute_lag_correlation(
            btc_returns, alt_returns, max_lag
        )
        
        similarity_pct, same_dir, opposite_dir, total_candles = compute_directional_similarity(
            btc_returns, alt_returns
        )
        
        lag_interpretation = "synchronous"
        if lag_minutes < 0:
            lag_interpretation = f"leads BTC by {abs(lag_minutes)} min"
        elif lag_minutes > 0:
            lag_interpretation = f"lags BTC by {lag_minutes} min"
        
        results.append({
            'symbol': symbol,
            'correlation': correlation,
            'optimal_lag_minutes': lag_minutes,
            'lag_interpretation': lag_interpretation,
            'p_value': p_value,
            'is_significant': p_value < 0.05,
            'directional_similarity_pct': similarity_pct,
            'same_direction_count': same_dir,
            'opposite_direction_count': opposite_dir,
            'total_candles': total_candles,
            'data_points': len(btc_returns.dropna())
        })
        
        significance = "✅ significant" if p_value < 0.05 else "⚠️ not significant"
        print(f"  {symbol:<12} | Corr: {correlation:+.3f} ({significance}) | "
              f"Lag: {lag_minutes:+4d} min | Similarity: {similarity_pct:.1f}%")
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('correlation', ascending=False)
    
    return results_df


def generate_summary_report(results_df: pd.DataFrame) -> str:
    """
    Generate human-readable summary report
    
    Args:
        results_df: Results DataFrame from analyze_all_coins
    
    Returns:
        Formatted text report
    """
    report = []
    report.append("\n" + "="*80)
    report.append("BTC PRICE CORRELATION ANALYSIS REPORT")
    report.append("="*80)
    report.append(f"\nAnalyzed {len(results_df)} altcoins vs BTCUSDT")
    report.append(f"Data points: {results_df['data_points'].iloc[0]} candles (5-minute)")
    
    report.append("\n" + "-"*80)
    report.append("CORRELATION RANKINGS (Highest to Lowest)")
    report.append("-"*80)
    
    for idx, row in results_df.iterrows():
        sig_marker = "✅" if row['is_significant'] else "⚠️"
        report.append(f"\n{row['symbol']}:")
        report.append(f"  Correlation:  {row['correlation']:+.4f} {sig_marker} (p={row['p_value']:.4f})")
        report.append(f"  Speed:        {row['lag_interpretation']}")
        report.append(f"  Similarity:   {row['directional_similarity_pct']:.1f}% "
                     f"({row['same_direction_count']} same, {row['opposite_direction_count']} opposite)")
    
    report.append("\n" + "-"*80)
    report.append("KEY INSIGHTS")
    report.append("-"*80)
    
    high_corr = results_df[results_df['correlation'] > 0.7]
    report.append(f"\n• High correlation (>0.7): {len(high_corr)} coins")
    if len(high_corr) > 0:
        report.append(f"  {', '.join(high_corr['symbol'].tolist())}")
    
    leads_btc = results_df[results_df['optimal_lag_minutes'] < 0]
    report.append(f"\n• Coins that LEAD BTC: {len(leads_btc)}")
    if len(leads_btc) > 0:
        for _, row in leads_btc.iterrows():
            report.append(f"  {row['symbol']}: {abs(row['optimal_lag_minutes'])} minutes ahead")
    
    lags_btc = results_df[results_df['optimal_lag_minutes'] > 0]
    report.append(f"\n• Coins that LAG BTC: {len(lags_btc)}")
    if len(lags_btc) > 0:
        for _, row in lags_btc.iterrows():
            report.append(f"  {row['symbol']}: {row['optimal_lag_minutes']} minutes behind")
    
    high_similarity = results_df[results_df['directional_similarity_pct'] > 75]
    report.append(f"\n• High directional similarity (>75%): {len(high_similarity)} coins")
    if len(high_similarity) > 0:
        report.append(f"  {', '.join(high_similarity['symbol'].tolist())}")
    
    report.append("\n" + "="*80)
    
    return "\n".join(report)
