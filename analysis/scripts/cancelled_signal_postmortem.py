#!/usr/bin/env python3
"""
Cancelled Signal Postmortem Analysis

Analyzes CANCELLED signals to check if price reached target zone
during the original TTL after cancellation, and maximum adverse deviation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv()

COINALYZE_API = 'https://api.coinalyze.net/v1'
COINALYZE_KEY = os.getenv('COINALYZE_API_KEY')


def _get(url, params=None, timeout=20, retries=5):
    """GET request with retry logic for 429 rate limit errors"""
    params = params or {}
    if COINALYZE_KEY:
        params['api_key'] = COINALYZE_KEY
    
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait_time = (2 ** attempt) * 1.5
                print(f"Rate limit hit, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise
    
    raise Exception(f"Failed after {retries} retries")


def _symbol_to_coinalyze(s):
    """Convert symbol to Coinalyze format"""
    symbol_map = {
        'BTCUSDT': 'BTCUSDT_PERP.A',
        'ETHUSDT': 'ETHUSDT_PERP.A',
        'BNBUSDT': 'BNBUSDT_PERP.A',
        'SOLUSDT': 'SOLUSDT_PERP.A',
        'AVAXUSDT': 'AVAXUSDT_PERP.A',
        'DOGEUSDT': 'DOGEUSDT_PERP.A',
        'LINKUSDT': 'LINKUSDT_PERP.A',
        'YFIUSDT': 'YFIUSDT_PERP.A',
        'LUMIAUSDT': 'LUMIAUSDT_PERP.A',
        'ANIMEUSDT': 'ANIMEUSDT_PERP.A',
        'HYPEUSDT': 'HYPEUSDT_PERP.A',
        'XRPUSDT': 'XRPUSDT_PERP.A',
        'ADAUSDT': 'ADAUSDT_PERP.A'
    }
    return symbol_map.get(s, f"{s}_PERP.A")


def fetch_historical_klines(symbol, start_time, end_time, interval='5m'):
    """
    Fetch historical klines for a specific time range.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        start_time: Start datetime
        end_time: End datetime
        interval: Candle interval (default '5m')
    
    Returns:
        List of klines: [[timestamp_ms, open, high, low, close, volume], ...]
    """
    interval_map = {
        '1m': '1min', '3m': '3min', '5m': '5min', 
        '15m': '15min', '30m': '30min', '1h': '1hour'
    }
    iv = interval_map.get(interval, '5min')
    
    from_ts = int(start_time.timestamp())
    to_ts = int(end_time.timestamp())
    
    sym = _symbol_to_coinalyze(symbol)
    
    try:
        data = _get(
            f"{COINALYZE_API}/ohlcv-history",
            {'symbols': sym, 'interval': iv, 'from': from_ts, 'to': to_ts}
        )
        
        if not data or not isinstance(data, list) or not data[0].get('history'):
            return []
        
        hist = data[0]['history']
        result = [
            [
                int(h['t']) * 1000,
                float(h['o']),
                float(h['h']),
                float(h['l']),
                float(h['c']),
                float(h.get('v', 0))
            ] 
            for h in hist
        ]
        
        return result
    except Exception as e:
        print(f"Error fetching klines for {symbol}: {e}")
        return []


def load_cancelled_signals():
    """Load CANCELLED signals from effectiveness_log.csv"""
    try:
        df = pd.read_csv('effectiveness_log.csv')
        cancelled = df[df['result'] == 'CANCELLED'].copy()
        
        # Convert timestamp strings to datetime
        cancelled['timestamp_sent'] = pd.to_datetime(cancelled['timestamp_sent'])
        cancelled['timestamp_checked'] = pd.to_datetime(cancelled['timestamp_checked'])
        
        print(f"Loaded {len(cancelled)} CANCELLED signals")
        return cancelled
    except Exception as e:
        print(f"Error loading effectiveness_log.csv: {e}")
        return pd.DataFrame()


def load_signals_metadata():
    """Load signals metadata from signals_log.csv"""
    try:
        df = pd.read_csv('signals_log.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"Loaded {len(df)} signals from signals_log.csv")
        return df
    except Exception as e:
        print(f"Error loading signals_log.csv: {e}")
        return pd.DataFrame()


def match_signal_metadata(cancelled_signal, signals_df):
    """
    Match a cancelled signal with its original metadata from signals_log.csv
    
    Returns: dict with target_min, target_max, ttl_minutes, or None if not found
    """
    symbol = cancelled_signal['symbol']
    verdict = cancelled_signal['verdict']
    timestamp_sent = cancelled_signal['timestamp_sent']
    entry_price = cancelled_signal['entry_price']
    
    # Find matching signal within ±5 seconds and same entry price (within 0.01%)
    time_tolerance = timedelta(seconds=5)
    price_tolerance = 0.0001  # 0.01% tolerance
    
    matches = signals_df[
        (signals_df['symbol'] == symbol) &
        (signals_df['verdict'] == verdict) &
        (abs(signals_df['timestamp'] - timestamp_sent) <= time_tolerance) &
        (abs(signals_df['entry_price'] - entry_price) / entry_price <= price_tolerance)
    ]
    
    if len(matches) == 0:
        return None
    
    # Take the closest match
    match = matches.iloc[0]
    
    return {
        'target_min': match['target_min'],
        'target_max': match['target_max'],
        'ttl_minutes': match['ttl_minutes']
    }


def analyze_post_cancellation_price(cancelled_signal, metadata, klines):
    """
    Analyze price movement after cancellation within original TTL.
    
    Returns: dict with analysis results
    """
    if not klines or len(klines) == 0:
        return None
    
    entry_price = cancelled_signal['entry_price']
    verdict = cancelled_signal['verdict']
    target_min = metadata['target_min']
    target_max = metadata['target_max']
    
    # Check if targets are valid
    if pd.isna(target_min) or pd.isna(target_max) or target_min == 0:
        return None
    
    # Extract highs and lows from klines
    highs = [k[2] for k in klines]
    lows = [k[3] for k in klines]
    
    max_high = max(highs) if highs else entry_price
    min_low = min(lows) if lows else entry_price
    
    # Check target zone hit
    target_hit = False
    
    if verdict == 'BUY':
        # For BUY: target zone is [target_min, target_max]
        # Price reaches target if high >= target_min
        target_hit = max_high >= target_min
        
        # Adverse deviation: maximum drop below entry
        adverse_deviation_pct = ((min_low - entry_price) / entry_price) * 100
        
    else:  # SELL
        # For SELL: target zone is [target_min, target_max]
        # target_max = near edge (less aggressive, higher price)
        # target_min = far edge (more aggressive, lower price)
        # Price reaches target zone if low <= target_max (enters the zone)
        target_hit = min_low <= target_max
        
        # Adverse deviation: maximum rise above entry
        adverse_deviation_pct = ((max_high - entry_price) / entry_price) * 100
    
    return {
        'target_hit': target_hit,
        'max_high': max_high,
        'min_low': min_low,
        'adverse_deviation_pct': adverse_deviation_pct
    }


def run_analysis(days_back=7, max_signals=None, output_csv='analysis/cancelled_postmortem_results.csv', 
                 output_md='analysis/CANCELLED_POSTMORTEM_REPORT.md'):
    """
    Run complete analysis on CANCELLED signals.
    
    Args:
        days_back: Number of days to analyze (default: 7)
        max_signals: Maximum number of signals to process (None = all)
        output_csv: Path for detailed CSV output
        output_md: Path for summary Markdown report
    """
    print("=" * 60)
    print("CANCELLED SIGNAL POSTMORTEM ANALYSIS")
    print("=" * 60)
    
    # Load data
    cancelled_df = load_cancelled_signals()
    if cancelled_df.empty:
        print("No CANCELLED signals found!")
        return
    
    signals_df = load_signals_metadata()
    if signals_df.empty:
        print("No signals metadata found!")
        return
    
    # Filter by date range
    cutoff_date = datetime.now() - timedelta(days=days_back)
    cancelled_df = cancelled_df[cancelled_df['timestamp_sent'] >= cutoff_date]
    
    # Limit number of signals if specified
    if max_signals and len(cancelled_df) > max_signals:
        cancelled_df = cancelled_df.head(max_signals)
        print(f"\nAnalyzing first {len(cancelled_df)} CANCELLED signals (limited from {len(cancelled_df)} total)")
    else:
        print(f"\nAnalyzing {len(cancelled_df)} CANCELLED signals from last {days_back} days")
    
    # Process each cancelled signal
    results = []
    processed_count = 0
    
    for idx, row in cancelled_df.iterrows():
        print(f"\nProcessing {idx + 1}/{len(cancelled_df)}: {row['symbol']} {row['verdict']} @ {row['timestamp_sent']}")
        
        # Match with original signal metadata
        metadata = match_signal_metadata(row, signals_df)
        if not metadata:
            print(f"  ⚠ No matching signal found in signals_log.csv")
            continue
        
        # Calculate original TTL expiry time
        original_ttl_expiry = row['timestamp_sent'] + timedelta(minutes=int(metadata['ttl_minutes']))
        cancellation_time = row['timestamp_checked']
        
        # Skip if already expired at cancellation
        if cancellation_time >= original_ttl_expiry:
            print(f"  ⚠ Signal already expired at cancellation")
            continue
        
        print(f"  Fetching klines from {cancellation_time} to {original_ttl_expiry}")
        
        # Fetch klines for post-cancellation period
        klines = fetch_historical_klines(
            row['symbol'],
            cancellation_time,
            original_ttl_expiry,
            interval='5m'
        )
        
        if not klines:
            print(f"  ⚠ No klines data available")
            continue
        
        print(f"  Analyzing {len(klines)} candles")
        
        # Analyze price movement
        analysis = analyze_post_cancellation_price(row, metadata, klines)
        if not analysis:
            print(f"  ⚠ Analysis failed (invalid targets)")
            continue
        
        # Store result
        result = {
            'timestamp_sent': row['timestamp_sent'],
            'timestamp_cancelled': cancellation_time,
            'original_ttl_expiry': original_ttl_expiry,
            'symbol': row['symbol'],
            'verdict': row['verdict'],
            'confidence': row['confidence'],
            'entry_price': row['entry_price'],
            'target_min': metadata['target_min'],
            'target_max': metadata['target_max'],
            'ttl_minutes': metadata['ttl_minutes'],
            'cancellation_profit_pct': row['profit_pct'],
            'target_hit_after_cancel': analysis['target_hit'],
            'max_high_after_cancel': analysis['max_high'],
            'min_low_after_cancel': analysis['min_low'],
            'adverse_deviation_pct': analysis['adverse_deviation_pct']
        }
        
        results.append(result)
        processed_count += 1
        
        print(f"  ✅ Target hit: {analysis['target_hit']}, Adverse deviation: {analysis['adverse_deviation_pct']:.2f}%")
        
        # Save intermediate results every 20 signals
        if processed_count % 20 == 0 and results:
            temp_df = pd.DataFrame(results)
            os.makedirs(os.path.dirname(output_csv), exist_ok=True)
            temp_df.to_csv(output_csv, index=False)
            print(f"\n💾 Intermediate save: {processed_count} signals processed, {len(results)} results saved")
        
        # Rate limiting: wait between requests
        time.sleep(1.5)
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    if results_df.empty:
        print("\n⚠ No valid results to report")
        return
    
    # Save detailed CSV
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    results_df.to_csv(output_csv, index=False)
    print(f"\n✅ Detailed results saved to {output_csv}")
    
    # Generate summary report
    generate_summary_report(results_df, output_md)
    print(f"✅ Summary report saved to {output_md}")


def generate_summary_report(df, output_path):
    """Generate Markdown summary report"""
    
    total_signals = len(df)
    target_hit_count = df['target_hit_after_cancel'].sum()
    target_hit_rate = (target_hit_count / total_signals) * 100
    
    # Split by verdict
    buy_df = df[df['verdict'] == 'BUY']
    sell_df = df[df['verdict'] == 'SELL']
    
    buy_target_hit = buy_df['target_hit_after_cancel'].sum() if not buy_df.empty else 0
    buy_total = len(buy_df)
    buy_hit_rate = (buy_target_hit / buy_total * 100) if buy_total > 0 else 0
    
    sell_target_hit = sell_df['target_hit_after_cancel'].sum() if not sell_df.empty else 0
    sell_total = len(sell_df)
    sell_hit_rate = (sell_target_hit / sell_total * 100) if sell_total > 0 else 0
    
    # Adverse deviation stats
    avg_adverse_dev = df['adverse_deviation_pct'].mean()
    max_adverse_dev = df['adverse_deviation_pct'].max()
    min_adverse_dev = df['adverse_deviation_pct'].min()
    
    # Generate report
    report = f"""# CANCELLED Signal Postmortem Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary

This analysis examines CANCELLED signals to determine:
1. **Did price reach target zone** after cancellation but within original TTL?
2. **Maximum adverse deviation** in the opposite direction after cancellation

---

## Key Findings

### Overall Results
- **Total CANCELLED signals analyzed:** {total_signals}
- **Signals that hit target after cancellation:** {target_hit_count} ({target_hit_rate:.1f}%)
- **Signals that did NOT hit target:** {total_signals - target_hit_count} ({100 - target_hit_rate:.1f}%)

### By Signal Type

#### BUY Signals
- **Total:** {buy_total}
- **Hit target zone after cancellation:** {buy_target_hit} ({buy_hit_rate:.1f}%)
- **Did NOT hit target:** {buy_total - buy_target_hit} ({100 - buy_hit_rate if buy_total > 0 else 0:.1f}%)

#### SELL Signals
- **Total:** {sell_total}
- **Hit target zone after cancellation:** {sell_target_hit} ({sell_hit_rate:.1f}%)
- **Did NOT hit target:** {sell_total - sell_target_hit} ({100 - sell_hit_rate if sell_total > 0 else 0:.1f}%)

---

## Adverse Deviation Analysis

**Adverse deviation** = Maximum price movement in the OPPOSITE direction of the signal:
- For BUY signals: maximum drop below entry price
- For SELL signals: maximum rise above entry price

### Statistics
- **Average adverse deviation:** {avg_adverse_dev:.2f}%
- **Maximum adverse deviation:** {max_adverse_dev:.2f}%
- **Minimum adverse deviation:** {min_adverse_dev:.2f}%

---

## Interpretation

### Target Hit Rate After Cancellation: {target_hit_rate:.1f}%

"""
    
    if target_hit_rate < 20:
        report += """**✅ EXCELLENT:** Very few cancelled signals reached target zone after cancellation.
This suggests the cancellation logic is working correctly - signals are being cancelled
when market conditions truly deteriorate, not prematurely.
"""
    elif target_hit_rate < 40:
        report += """**✅ GOOD:** Most cancelled signals did not reach target zone after cancellation.
The cancellation logic appears to be reasonably effective, though there may be room
for minor improvements to reduce false cancellations.
"""
    elif target_hit_rate < 60:
        report += """**⚠ MODERATE:** About half of cancelled signals reached target zone after cancellation.
This suggests the cancellation logic may be too aggressive, potentially cancelling
signals that would have been successful. Consider adjusting cancellation thresholds.
"""
    else:
        report += """**❌ CONCERNING:** Majority of cancelled signals reached target zone after cancellation.
The cancellation logic appears to be too aggressive, cancelling many potentially
profitable signals. Recommend reviewing and relaxing cancellation criteria.
"""
    
    report += f"""

### Adverse Deviation: {avg_adverse_dev:.2f}% average

"""
    
    if abs(avg_adverse_dev) < 0.5:
        report += """**✅ LOW RISK:** Minimal adverse price movement after cancellation.
Signals are being cancelled close to entry price, limiting potential losses.
"""
    elif abs(avg_adverse_dev) < 1.5:
        report += """**✅ MODERATE RISK:** Acceptable adverse price movement after cancellation.
Some drawdown occurs before cancellation, but within reasonable risk parameters.
"""
    else:
        report += """**⚠ HIGH RISK:** Significant adverse price movement after cancellation.
Signals are experiencing substantial drawdown before being cancelled.
Consider earlier cancellation triggers to reduce risk exposure.
"""
    
    report += f"""

---

## Detailed Statistics by Symbol

| Symbol | Total | Target Hit | Hit Rate | Avg Adverse Dev |
|--------|-------|------------|----------|-----------------|
"""
    
    for symbol in sorted(df['symbol'].unique()):
        sym_df = df[df['symbol'] == symbol]
        sym_total = len(sym_df)
        sym_hit = sym_df['target_hit_after_cancel'].sum()
        sym_hit_rate = (sym_hit / sym_total * 100)
        sym_avg_dev = sym_df['adverse_deviation_pct'].mean()
        
        report += f"| {symbol} | {sym_total} | {sym_hit} | {sym_hit_rate:.1f}% | {sym_avg_dev:+.2f}% |\n"
    
    report += f"""

---

## Methodology

1. **Data Source:** effectiveness_log.csv (CANCELLED signals) matched with signals_log.csv (original metadata)
2. **Time Window:** From cancellation timestamp to original TTL expiry time
3. **Target Zone Check:** 
   - BUY: Price high >= target_min
   - SELL: Price low <= target_min
4. **Adverse Deviation:**
   - BUY: Minimum price drop from entry
   - SELL: Maximum price rise from entry
5. **Price Data:** 5-minute candles from Coinalyze API

---

**Full results available in:** `cancelled_postmortem_results.csv`
"""
    
    # Write report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)


if __name__ == '__main__':
    # Default: analyze last 7 days, limit to 100 signals
    days = 7
    max_sigs = 100
    
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except:
            print("Usage: python cancelled_signal_postmortem.py [days_back] [max_signals]")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            max_sigs = int(sys.argv[2])
        except:
            print("Usage: python cancelled_signal_postmortem.py [days_back] [max_signals]")
            sys.exit(1)
    
    run_analysis(days_back=days, max_signals=max_sigs)
