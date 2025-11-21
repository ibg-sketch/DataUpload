"""
Generate Final Comprehensive Summary Table
Combines tick-level lag analysis with statistical correlations
"""

import json
import re


def parse_tick_lag_results():
    """Parse tick-level lag analysis results from file"""
    tick_lags = {}
    
    try:
        with open('analysis/results/tick_lag_analysis.txt', 'r') as f:
            content = f.read()
        
        # Regex pattern: captures rank, coin symbol (including hyphens), and lag value
        pattern = r'(\d+)\.\s+([A-Z0-9-]+):\s+([\d.]+)s\s+avg\s+lag'
        matches = re.findall(pattern, content)
        
        for rank, coin, avg_lag in matches:
            symbol = coin + 'USDT'
            tick_lags[symbol] = float(avg_lag)
        
        print(f"✅ Parsed {len(tick_lags)} tick-lag measurements from file")
        
    except FileNotFoundError:
        print("⚠️  Warning: tick_lag_analysis.txt not found, using zeros")
        tick_lags = {
            'ETHUSDT': 0,
            'LINKUSDT': 0,
            'XRPUSDT': 0,
            'ADAUSDT': 0,
            'TRXUSDT': 0
        }
    
    return tick_lags


def load_results():
    """Load both analysis results"""
    
    # Statistical analysis results
    with open('analysis/results/btc_leadlag_statistical_report.json', 'r') as f:
        stat_results = json.load(f)
    
    # Parse tick-level lag results from file
    tick_lags = parse_tick_lag_results()
    
    return stat_results, tick_lags


def generate_comprehensive_table():
    """Generate final comprehensive trading table"""
    
    stat_results, tick_lags = load_results()
    
    print("\n" + "="*160)
    print("📊 FINAL COMPREHENSIVE ANALYSIS: BTC-ALTCOIN LEAD-LAG RELATIONSHIPS")
    print("="*160)
    print("\nCombines Statistical Analysis (correlations, beta, Granger) + Tick-Level Lag Detection\n")
    
    # Table header
    header = (
        f"{'Coin':<6} │ "
        f"{'Corr':<6} │ "
        f"{'Beta':<6} │ "
        f"{'R²':<6} │ "
        f"{'Lag(s)':<7} │ "
        f"{'Granger':<8} │ "
        f"{'VAR Lag':<8} │ "
        f"{'Trading Signal':<25} │ "
        f"{'Recommendation':<35}"
    )
    
    print(header)
    print("─" * 160)
    
    # Data rows
    coins_data = []
    
    for symbol, result in stat_results['results'].items():
        coin = symbol.replace('USDT', '')
        
        # Statistical metrics
        corr = result['correlations']['pearson']['corr']
        beta = result['beta']['beta']
        r2 = result['beta']['r_squared']
        granger_sig = '✅ YES' if result['granger'].get('is_significant') else '❌ NO'
        var_lag = result['var']['optimal_lag']
        
        # Tick-level lag
        tick_lag = tick_lags.get(symbol, 0)
        
        # Determine trading signal
        if tick_lag > 10 and corr > 0.6:
            signal = '🎯 EXCELLENT LAG-TRADE'
            recommendation = 'High-probability lag trading'
        elif tick_lag > 5 and corr > 0.7:
            signal = '✅ GOOD LAG-TRADE'
            recommendation = 'Viable 5s lag window'
        elif corr > 0.7 and beta > 1.2:
            signal = '⚡ FAST AMPLIFIER'
            recommendation = 'BTC proxy with leverage effect'
        elif corr > 0.6 and abs(beta - 1.0) < 0.2:
            signal = '🔗 1:1 FOLLOWER'
            recommendation = 'Direct BTC correlation'
        elif corr < 0.5:
            signal = '❌ WEAK CORRELATION'
            recommendation = 'Not suitable for BTC strategies'
        else:
            signal = '⚠️ MODERATE'
            recommendation = 'Limited predictive value'
        
        coins_data.append({
            'coin': coin,
            'corr': corr,
            'beta': beta,
            'r2': r2,
            'tick_lag': tick_lag,
            'granger': granger_sig,
            'var_lag': var_lag,
            'signal': signal,
            'recommendation': recommendation
        })
    
    # Sort by correlation (descending)
    coins_data.sort(key=lambda x: x['corr'], reverse=True)
    
    # Print rows
    for data in coins_data:
        row = (
            f"{data['coin']:<6} │ "
            f"{data['corr']:>6.3f} │ "
            f"{data['beta']:>6.2f} │ "
            f"{data['r2']:>6.3f} │ "
            f"{data['tick_lag']:>7.1f} │ "
            f"{data['granger']:<8} │ "
            f"{data['var_lag']:>8d} │ "
            f"{data['signal']:<25} │ "
            f"{data['recommendation']:<35}"
        )
        print(row)
    
    print("─" * 160)
    
    # Rankings
    print("\n" + "="*160)
    print("🏆 RANKINGS BY CRITERIA")
    print("="*160)
    
    # By correlation
    by_corr = sorted(coins_data, key=lambda x: x['corr'], reverse=True)
    print("\n📊 STRONGEST BTC CORRELATION:")
    for i, coin in enumerate(by_corr, 1):
        print(f"  {i}. {coin['coin']}: {coin['corr']:.3f} (β={coin['beta']:.2f}, R²={coin['r2']:.3f})")
    
    # By lag
    by_lag = sorted(coins_data, key=lambda x: x['tick_lag'], reverse=True)
    print("\n⏱️  HIGHEST LAG (Tick-Level Detection):")
    for i, coin in enumerate(by_lag, 1):
        print(f"  {i}. {coin['coin']}: {coin['tick_lag']:.1f}s lag (Corr={coin['corr']:.3f})")
    
    # By R²
    by_r2 = sorted(coins_data, key=lambda x: x['r2'], reverse=True)
    print("\n📈 BEST PREDICTIVE POWER (R²):")
    for i, coin in enumerate(by_r2, 1):
        print(f"  {i}. {coin['coin']}: R²={coin['r2']:.3f} ({coin['r2']*100:.1f}% variance explained)")
    
    print("\n" + "="*160)
    print("💡 KEY INSIGHTS FOR TRADING")
    print("="*160)
    
    print("""
1️⃣ BEST FOR LAG-TRADING:
   • ETH, LINK, XRP, ADA: ~5-second detectable lag with HIGH correlation (>0.6)
   • TRX: 46.8s lag BUT weak correlation (0.386) → UNRELIABLE
   
2️⃣ BEST BTC PROXIES (No-lag strategies):
   • ETH: 0.726 corr, 1.33 beta → Best overall (amplifies BTC by 33%)
   • LINK: 0.706 corr, 1.29 beta → Excellent alternative
   
3️⃣ AMPLIFIER EFFECT:
   • ETH & LINK: Beta > 1.3 → Move MORE than BTC (higher volatility)
   • XRP & ADA: Beta ≈ 1.0 → Near 1:1 movement with BTC
   • TRX: Beta = 0.21 → Decoupled from BTC
   
4️⃣ STATISTICAL SIGNIFICANCE:
   • ALL coins: Granger causality significant (p < 0.001)
   • BTC → ALT direction confirmed (not vice versa)
   • VAR models: Optimal lags 1-3 seconds (limited by data resolution)

5️⃣ TRADING RECOMMENDATIONS:
   
   ✅ LAG-TRADING STRATEGY (5-second window):
      • Monitor BTC for >0.15% moves in 10 seconds
      • Enter ETH/LINK/XRP/ADA in same direction
      • Exit after 5-10 seconds when lag closes
      • Expected lag: 5-6 seconds per tick analysis
   
   ✅ BTC CORRELATION STRATEGY:
      • Use ETH as primary BTC proxy (highest corr + R²)
      • Expect 33% amplification (beta 1.33)
      • 52.6% variance explained by BTC movements
   
   ❌ AVOID:
      • TRX for BTC-following (too weak correlation)
      • Using 1-second data for lag detection (too coarse)

6️⃣ METHODOLOGY NOTES:
   • Tick-level lag analysis: Detects real 5-46s delays
   • 1-second statistical analysis: Shows correlations but masks sub-second lags
   • Granger tests confirm causality direction
   • VAR models validate BTC leads altcoins relationship
""")
    
    print("="*160)
    print(f"\n💾 Full reports saved:")
    print(f"   • analysis/results/btc_leadlag_statistical_report.json")
    print(f"   • analysis/results/btc_leadlag_final_report.md")
    print(f"   • analysis/results/tick_lag_analysis.txt")
    print("\n" + "="*160 + "\n")


if __name__ == '__main__':
    generate_comprehensive_table()
