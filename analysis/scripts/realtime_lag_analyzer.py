"""
Real-Time Lag Analyzer
Analyzes tick-level aggTrades data to measure how quickly altcoins react to Bitcoin price movements
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import glob


def load_tick_data(symbol, date='2025-11-14', max_rows=None):
    """Load tick-level aggTrades data"""
    filepath = f"data/tick_data/{symbol}-aggTrades-{date}.csv"
    
    if not os.path.exists(filepath):
        print(f"  ❌ {symbol} data not found")
        return None
    
    print(f"  📥 Loading {symbol}...", end=" ")
    
    df = pd.read_csv(filepath, nrows=max_rows)
    df['timestamp'] = pd.to_datetime(df['transact_time'], unit='ms')
    df['price'] = df['price'].astype(float)
    
    df = df[['timestamp', 'price', 'quantity', 'is_buyer_maker']].sort_values('timestamp')
    
    print(f"✅ {len(df):,} trades")
    return df


def detect_btc_movements(btc_df, threshold_pct=0.1, window_seconds=10):
    """
    Detect significant BTC price movements
    
    Args:
        btc_df: DataFrame with BTC tick data
        threshold_pct: Minimum price change % to consider (default 0.1%)
        window_seconds: Time window to detect movement (default 10 sec)
    
    Returns:
        List of movement events: (timestamp, direction, magnitude_pct)
    """
    print(f"\n🔍 Detecting BTC movements (>{threshold_pct}% in {window_seconds}s windows)...")
    
    btc_df = btc_df.copy()
    btc_df = btc_df.set_index('timestamp')
    btc_df = btc_df.resample('1S').agg({'price': 'last'}).ffill()
    
    movements = []
    
    for i in range(len(btc_df) - window_seconds):
        start_price = btc_df['price'].iloc[i]
        end_price = btc_df['price'].iloc[i + window_seconds]
        
        if start_price == 0:
            continue
        
        change_pct = ((end_price - start_price) / start_price) * 100
        
        if abs(change_pct) >= threshold_pct:
            timestamp = btc_df.index[i]
            direction = 'UP' if change_pct > 0 else 'DOWN'
            movements.append((timestamp, direction, change_pct, start_price, end_price))
    
    print(f"  ✅ Found {len(movements)} significant BTC movements")
    return movements


def measure_altcoin_lag(btc_movements, alt_df, symbol, reaction_threshold_pct=0.05):
    """
    Measure how long it takes for altcoin to react to BTC movements
    
    Args:
        btc_movements: List of BTC movement events
        alt_df: DataFrame with altcoin tick data
        symbol: Altcoin symbol
        reaction_threshold_pct: Minimum altcoin change % to consider reaction
    
    Returns:
        List of lag measurements in seconds
    """
    print(f"\n⏱️  Measuring {symbol} lag...")
    
    alt_df = alt_df.copy()
    alt_df = alt_df.set_index('timestamp')
    alt_df = alt_df.resample('1S').agg({'price': 'last'}).ffill()
    
    lags = []
    matched = 0
    
    for btc_time, btc_dir, btc_mag, btc_start, btc_end in btc_movements[:100]:
        
        search_window_start = btc_time
        search_window_end = btc_time + pd.Timedelta(seconds=120)
        
        alt_window = alt_df[(alt_df.index >= search_window_start) & 
                            (alt_df.index <= search_window_end)]
        
        if len(alt_window) < 2:
            continue
        
        alt_start_price = alt_window['price'].iloc[0]
        
        for lag_sec in range(1, 121):
            try:
                alt_current_price = alt_window['price'].iloc[lag_sec]
                
                if alt_start_price == 0:
                    break
                
                alt_change_pct = ((alt_current_price - alt_start_price) / alt_start_price) * 100
                
                same_direction = (btc_dir == 'UP' and alt_change_pct > 0) or \
                                (btc_dir == 'DOWN' and alt_change_pct < 0)
                
                if same_direction and abs(alt_change_pct) >= reaction_threshold_pct:
                    lags.append(lag_sec)
                    matched += 1
                    break
                    
            except IndexError:
                break
    
    print(f"  ✅ Matched {matched}/{min(len(btc_movements), 100)} movements")
    return lags


def main():
    print("="*80)
    print("REAL-TIME LAG ANALYSIS - Tick-Level Data")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    date = '2025-11-14'
    
    print(f"📅 Analyzing date: {date}")
    print(f"📊 Data source: Binance Vision aggTrades (tick-level)\n")
    
    print("📥 Loading tick data...")
    btc_df = load_tick_data('BTCUSDT', date, max_rows=500000)
    
    if btc_df is None:
        print("\n❌ Cannot proceed without BTC data")
        return
    
    symbols_to_test = ['TRXUSDT', 'XRPUSDT', 'LINKUSDT', 'ADAUSDT', 'ETHUSDT']
    alt_data = {}
    
    for symbol in symbols_to_test:
        df = load_tick_data(symbol, date, max_rows=200000)
        if df is not None:
            alt_data[symbol] = df
    
    btc_movements = detect_btc_movements(btc_df, threshold_pct=0.15, window_seconds=10)
    
    if len(btc_movements) == 0:
        print("\n⚠️  No significant BTC movements detected")
        return
    
    print(f"\n📊 Sample BTC movements:")
    for i, (ts, direction, mag, start_p, end_p) in enumerate(btc_movements[:5]):
        print(f"  {i+1}. {ts.strftime('%H:%M:%S')} → {direction} {mag:+.2f}% "
              f"(${start_p:,.1f} → ${end_p:,.1f})")
    
    results = {}
    
    for symbol, alt_df in alt_data.items():
        lags = measure_altcoin_lag(btc_movements, alt_df, symbol, reaction_threshold_pct=0.08)
        
        if lags:
            results[symbol] = {
                'lags': lags,
                'mean_lag': np.mean(lags),
                'median_lag': np.median(lags),
                'std_lag': np.std(lags),
                'min_lag': np.min(lags),
                'max_lag': np.max(lags),
                'sample_size': len(lags)
            }
    
    print("\n" + "="*80)
    print("🐌 LAG ANALYSIS RESULTS (from slowest to fastest)")
    print("="*80)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['mean_lag'], reverse=True)
    
    for rank, (symbol, stats) in enumerate(sorted_results, 1):
        symbol_clean = symbol.replace('USDT', '')
        
        lag_emoji = '🐌🐌🐌' if stats['mean_lag'] >= 3 else ('🐌🐌' if stats['mean_lag'] >= 2 else '🐌')
        
        print(f"\n{rank}. {lag_emoji} {symbol_clean}")
        print(f"   └─ Средняя задержка: {stats['mean_lag']:.1f} секунд")
        print(f"   └─ Медиана: {stats['median_lag']:.1f}с | Разброс: {stats['min_lag']:.0f}-{stats['max_lag']:.0f}с")
        print(f"   └─ Образцов: {stats['sample_size']}")
    
    print("\n" + "="*80)
    print("💡 ИНТЕРПРЕТАЦИЯ:")
    print("="*80)
    print(f"""
• Анализ основан на {len(btc_movements)} крупных движений BTC (>0.15% за 10сек)
• Измерена задержка реакции каждой монеты на движение BTC
• Чем выше задержка → тем больше возможностей для lag-trading стратегии

📊 Данные: {date}, tick-level (миллисекунды)
""")
    
    if sorted_results:
        slowest = sorted_results[0]
        fastest = sorted_results[-1]
        print(f"🐌 Самая медленная: {slowest[0].replace('USDT', '')} ({slowest[1]['mean_lag']:.1f}с)")
        print(f"🐇 Самая быстрая: {fastest[0].replace('USDT', '')} ({fastest[1]['mean_lag']:.1f}с)")
        
        diff = slowest[1]['mean_lag'] - fastest[1]['mean_lag']
        print(f"\n⚡ Разница: {diff:.1f} секунд между самой медленной и быстрой")
    
    print("\n" + "="*80)
    
    os.makedirs('analysis/results', exist_ok=True)
    
    report_path = 'analysis/results/tick_lag_analysis.txt'
    with open(report_path, 'w') as f:
        f.write("TICK-LEVEL LAG ANALYSIS REPORT\n")
        f.write("="*80 + "\n\n")
        f.write(f"Date: {date}\n")
        f.write(f"BTC Movements Analyzed: {len(btc_movements)}\n\n")
        
        for rank, (symbol, stats) in enumerate(sorted_results, 1):
            f.write(f"{rank}. {symbol.replace('USDT', '')}: {stats['mean_lag']:.1f}s avg lag\n")
            f.write(f"   (median: {stats['median_lag']:.1f}s, range: {stats['min_lag']:.0f}-{stats['max_lag']:.0f}s, n={stats['sample_size']})\n\n")
    
    print(f"💾 Report saved: {report_path}\n")


if __name__ == '__main__':
    main()
