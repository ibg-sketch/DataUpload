"""
BTC 1-Minute Lag Analysis
Identifies which coins follow Bitcoin with the longest delay
Using 1-minute candles for precise lag detection (±60 minutes)
"""

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.btc_correlation.local_5m_fetcher import fetch_all_coins_from_log
from tools.btc_correlation.correlation_analyzer import analyze_all_coins, generate_summary_report


def main():
    print("\n" + "="*80)
    print("BTC 5-MINUTE LAG ANALYSIS (Local Data)")
    print("Finding coins that follow Bitcoin with the longest delay")
    print("="*80)
    
    symbols = [
        'BTCUSDT',
        'ETHUSDT',
        'BNBUSDT',
        'SOLUSDT',
        'XRPUSDT',
        'ADAUSDT',
        'AVAXUSDT',
        'DOGEUSDT',
        'LINKUSDT',
        'TRXUSDT',
        'HYPEUSDT'
    ]
    
    max_lag_periods = 36
    max_lag_minutes = max_lag_periods * 5
    
    print(f"\n⚙️  Configuration:")
    print(f"   Symbols: {len(symbols)} coins")
    print(f"   Data source: analysis_log_clean.csv (locally collected data)")
    print(f"   Resolution: 5-minute candles")
    print(f"   Lag range: ±{max_lag_minutes} minutes (±{max_lag_periods} periods)")
    
    data = fetch_all_coins_from_log(symbols, log_path='analysis_log_clean.csv')
    
    if 'BTCUSDT' not in data:
        print("\n❌ BTCUSDT data missing, cannot proceed")
        return
    
    if len(data) < 2:
        print(f"\n❌ Only {len(data)} symbols fetched, need at least 2")
        return
    
    print(f"\n📊 BTC data: {len(data['BTCUSDT'])} candles")
    print(f"   Time range: {data['BTCUSDT']['timestamp'].min()} to {data['BTCUSDT']['timestamp'].max()}")
    
    results_df = analyze_all_coins(data, max_lag=max_lag_periods)
    
    report = generate_summary_report(results_df)
    print(report)
    
    print("\n" + "="*80)
    print("🐌 COINS WITH LONGEST LAG (sorted by delay)")
    print("="*80)
    
    lagging_coins = results_df[results_df['optimal_lag_minutes'] > 0].sort_values(
        'optimal_lag_minutes', ascending=False
    )
    
    if len(lagging_coins) > 0:
        print("\n✅ Found coins that LAG behind Bitcoin:\n")
        for idx, row in lagging_coins.iterrows():
            symbol_clean = row['symbol'].replace('USDT', '')
            lag_min = row['optimal_lag_minutes']
            corr = row['correlation']
            similarity = row['directional_similarity_pct']
            
            lag_emoji = '🐌🐌🐌' if lag_min >= 5 else ('🐌🐌' if lag_min >= 3 else '🐌')
            
            print(f"  {lag_emoji} {symbol_clean:<8} → Lag: +{lag_min} min | "
                  f"Corr: {corr:+.3f} | Similarity: {similarity:.1f}%")
    else:
        print("\n⚠️  No coins lag behind Bitcoin (all synchronous or leading)")
    
    leading_coins = results_df[results_df['optimal_lag_minutes'] < 0].sort_values(
        'optimal_lag_minutes', ascending=True
    )
    
    if len(leading_coins) > 0:
        print("\n⚡ Coins that LEAD Bitcoin:\n")
        for idx, row in leading_coins.iterrows():
            symbol_clean = row['symbol'].replace('USDT', '')
            lag_min = abs(row['optimal_lag_minutes'])
            corr = row['correlation']
            similarity = row['directional_similarity_pct']
            
            print(f"  🚀 {symbol_clean:<8} → Leads by {lag_min} min | "
                  f"Corr: {corr:+.3f} | Similarity: {similarity:.1f}%")
    
    os.makedirs('analysis/results', exist_ok=True)
    
    csv_path = 'analysis/results/btc_5m_lag_analysis.csv'
    results_df.to_csv(csv_path, index=False)
    print(f"\n💾 Saved: {csv_path}")
    
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'analysis_config': {
            'data_source': 'analysis_log_clean.csv',
            'max_lag_periods': max_lag_periods,
            'max_lag_minutes': max_lag_minutes,
            'candle_interval': '5m'
        },
        'correlations': results_df.to_dict('records')
    }
    
    json_path = 'analysis/results/btc_5m_lag_analysis.json'
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"💾 Saved: {json_path}")
    
    txt_path = 'analysis/results/btc_5m_lag_analysis.txt'
    with open(txt_path, 'w') as f:
        f.write(report)
    print(f"💾 Saved: {txt_path}")
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)
    print(f"\n📌 Key Finding:")
    if len(lagging_coins) > 0:
        slowest = lagging_coins.iloc[0]
        print(f"   Slowest coin: {slowest['symbol'].replace('USDT', '')} "
              f"(lags BTC by {slowest['optimal_lag_minutes']} minutes)")
    else:
        print(f"   All coins move synchronously with BTC at 1-minute resolution")
    
    print(f"\n📊 Results saved to analysis/results/")


if __name__ == '__main__':
    main()
