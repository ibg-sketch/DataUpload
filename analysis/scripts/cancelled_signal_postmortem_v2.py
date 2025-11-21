#!/usr/bin/env python3
"""
Cancelled Signal Postmortem Analysis V2 - Optimized with caching and batching

Analyzes CANCELLED signals with SQLite caching and symbol-grouped batching
to efficiently process hundreds of signals within API rate limits.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests
import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path for kline_cache import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from analysis.kline_cache import KlineCache

load_dotenv()

COINALYZE_API = 'https://api.coinalyze.net/v1'
COINALYZE_KEY = os.getenv('COINALYZE_API_KEY')
CHECKPOINT_FILE = 'analysis/tmp_cancelled_progress.json'


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
                wait_time = (2 ** attempt) * 2.0
                print(f"  ⏳ Rate limit hit, waiting {wait_time}s...")
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


def fetch_klines_with_cache(cache, symbol, start_time, end_time, interval='5m'):
    """Fetch klines from cache first, API if needed"""
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())
    
    # Try cache first
    cached = cache.get_cached_klines(symbol, start_ts, end_ts, interval)
    if cached:
        print(f"    ✅ Cache hit for {symbol} ({len(cached)} candles)")
        return cached
    
    # Fetch from API
    print(f"    🌐 Fetching from API for {symbol}")
    interval_map = {'1m': '1min', '3m': '3min', '5m': '5min', '15m': '15min', '30m': '30min', '1h': '1hour'}
    iv = interval_map.get(interval, '5min')
    
    sym = _symbol_to_coinalyze(symbol)
    
    try:
        data = _get(
            f"{COINALYZE_API}/ohlcv-history",
            {'symbols': sym, 'interval': iv, 'from': start_ts, 'to': end_ts}
        )
        
        if not data or not isinstance(data, list) or not data[0].get('history'):
            return []
        
        hist = data[0]['history']
        result = [
            [int(h['t']) * 1000, float(h['o']), float(h['h']), float(h['l']), float(h['c']), float(h.get('v', 0))] 
            for h in hist
        ]
        
        # Cache the result
        cache.cache_klines(symbol, start_ts, end_ts, result, interval)
        print(f"    💾 Cached {len(result)} candles for {symbol}")
        
        # Adaptive delay to avoid rate limits
        time.sleep(1.5)
        
        return result
    except Exception as e:
        print(f"    ❌ Error fetching klines for {symbol}: {e}")
        return []


def load_cancelled_signals(date_filter=None):
    """Load CANCELLED signals, optionally filtered by date range"""
    try:
        df = pd.read_csv('effectiveness_log.csv')
        cancelled = df[df['result'] == 'CANCELLED'].copy()
        
        cancelled['timestamp_sent'] = pd.to_datetime(cancelled['timestamp_sent'])
        cancelled['timestamp_checked'] = pd.to_datetime(cancelled['timestamp_checked'])
        
        if date_filter:
            cancelled = cancelled[cancelled['timestamp_sent'] >= date_filter]
        
        print(f"✅ Loaded {len(cancelled)} CANCELLED signals")
        return cancelled
    except Exception as e:
        print(f"❌ Error loading effectiveness_log.csv: {e}")
        return pd.DataFrame()


def load_signals_metadata():
    """Load signals metadata from signals_log.csv"""
    try:
        df = pd.read_csv('signals_log.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        print(f"✅ Loaded {len(df)} signals metadata")
        return df
    except Exception as e:
        print(f"❌ Error loading signals_log.csv: {e}")
        return pd.DataFrame()


def match_signal_metadata(cancelled_signal, signals_df):
    """Match cancelled signal with original metadata"""
    symbol = cancelled_signal['symbol']
    verdict = cancelled_signal['verdict']
    timestamp_sent = cancelled_signal['timestamp_sent']
    entry_price = cancelled_signal['entry_price']
    
    time_tolerance = timedelta(seconds=5)
    price_tolerance = 0.0001
    
    matches = signals_df[
        (signals_df['symbol'] == symbol) &
        (signals_df['verdict'] == verdict) &
        (abs(signals_df['timestamp'] - timestamp_sent) <= time_tolerance) &
        (abs(signals_df['entry_price'] - entry_price) / entry_price <= price_tolerance)
    ]
    
    if len(matches) == 0:
        return None
    
    match = matches.iloc[0]
    
    return {
        'target_min': match['target_min'],
        'target_max': match['target_max'],
        'ttl_minutes': match['ttl_minutes']
    }


def analyze_post_cancellation_price(cancelled_signal, metadata, klines):
    """Analyze price movement after cancellation"""
    if not klines or len(klines) == 0:
        return None
    
    entry_price = cancelled_signal['entry_price']
    verdict = cancelled_signal['verdict']
    target_min = metadata['target_min']
    target_max = metadata['target_max']
    
    if pd.isna(target_min) or pd.isna(target_max) or target_min == 0:
        return None
    
    highs = [k[2] for k in klines]
    lows = [k[3] for k in klines]
    
    max_high = max(highs) if highs else entry_price
    min_low = min(lows) if lows else entry_price
    
    target_hit = False
    
    if verdict == 'BUY':
        target_hit = max_high >= target_min
        adverse_deviation_pct = ((min_low - entry_price) / entry_price) * 100
    else:
        target_hit = min_low <= target_max
        adverse_deviation_pct = ((max_high - entry_price) / entry_price) * 100
    
    return {
        'target_hit': target_hit,
        'max_high': max_high,
        'min_low': min_low,
        'adverse_deviation_pct': adverse_deviation_pct
    }


def group_signals_by_symbol(cancelled_df):
    """Group signals by symbol for batch processing"""
    grouped = {}
    for idx, row in cancelled_df.iterrows():
        symbol = row['symbol']
        if symbol not in grouped:
            grouped[symbol] = []
        grouped[symbol].append((idx, row))
    return grouped


def load_checkpoint():
    """Load processing checkpoint"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {'processed_indices': [], 'completed_symbols': []}


def save_checkpoint(processed_indices, completed_symbols):
    """Save processing checkpoint"""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({
            'processed_indices': processed_indices,
            'completed_symbols': completed_symbols,
            'last_update': datetime.now().isoformat()
        }, f, indent=2)


def save_partial_results(results, output_csv):
    """Save partial results during processing"""
    if results:
        pd.DataFrame(results).to_csv(output_csv, index=False)
        print(f"  💾 Saved {len(results)} results to {output_csv}")


def run_analysis_v2(yesterday_today=True, output_csv='analysis/cancelled_postmortem_results_v2.csv'):
    """Run optimized analysis with caching and batching"""
    print("=" * 70)
    print("CANCELLED SIGNAL POSTMORTEM ANALYSIS V2 (Optimized)")
    print("=" * 70)
    
    # Initialize cache
    cache = KlineCache()
    cache_stats = cache.get_stats()
    print(f"\n📦 Cache initialized: {cache_stats['total_entries']} entries")
    
    # Load data
    if yesterday_today:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        date_filter = yesterday
        print(f"\n📅 Analyzing CANCELLED signals from {yesterday.strftime('%Y-%m-%d')} to now")
    else:
        date_filter = None
        print(f"\n📅 Analyzing ALL CANCELLED signals")
    
    cancelled_df = load_cancelled_signals(date_filter)
    if cancelled_df.empty:
        print("❌ No CANCELLED signals found!")
        return
    
    signals_df = load_signals_metadata()
    if signals_df.empty:
        print("❌ No signals metadata found!")
        return
    
    # Load checkpoint
    checkpoint = load_checkpoint()
    processed_indices = set(checkpoint.get('processed_indices', []))
    
    # Group by symbol for efficient processing
    grouped = group_signals_by_symbol(cancelled_df)
    print(f"\n📊 Processing {len(cancelled_df)} signals across {len(grouped)} symbols")
    
    for symbol, count in sorted([(s, len(sigs)) for s, sigs in grouped.items()], key=lambda x: -x[1]):
        print(f"   {symbol}: {count} signals")
    
    results = []
    total_signals = len(cancelled_df)
    processed_count = len(processed_indices)
    
    # Process each symbol group
    for symbol_idx, (symbol, signals_list) in enumerate(grouped.items(), 1):
        print(f"\n{'='*70}")
        print(f"Symbol {symbol_idx}/{len(grouped)}: {symbol} ({len(signals_list)} signals)")
        print(f"{'='*70}")
        
        for signal_idx, (idx, row) in enumerate(signals_list, 1):
            # Skip if already processed
            if idx in processed_indices:
                print(f"  ⏩ Skipping {signal_idx}/{len(signals_list)}: already processed")
                continue
            
            print(f"\n  [{processed_count + 1}/{total_signals}] {symbol} {row['verdict']} @ {row['timestamp_sent']}")
            
            # Match metadata
            metadata = match_signal_metadata(row, signals_df)
            if not metadata:
                print(f"    ⚠ No matching signal in signals_log.csv")
                processed_indices.add(idx)
                continue
            
            # Calculate time ranges
            original_ttl_expiry = row['timestamp_sent'] + timedelta(minutes=int(metadata['ttl_minutes']))
            cancellation_time = row['timestamp_checked']
            
            if cancellation_time >= original_ttl_expiry:
                print(f"    ⚠ Already expired at cancellation")
                processed_indices.add(idx)
                continue
            
            # Fetch klines with caching
            klines = fetch_klines_with_cache(
                cache,
                row['symbol'],
                cancellation_time,
                original_ttl_expiry,
                interval='5m'
            )
            
            if not klines:
                print(f"    ⚠ No klines data available")
                processed_indices.add(idx)
                continue
            
            # Analyze
            analysis = analyze_post_cancellation_price(row, metadata, klines)
            if not analysis:
                print(f"    ⚠ Analysis failed (invalid targets)")
                processed_indices.add(idx)
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
            processed_indices.add(idx)
            processed_count += 1
            
            hit_status = "✅ HIT" if analysis['target_hit'] else "❌ MISS"
            print(f"    {hit_status} | Adverse dev: {analysis['adverse_deviation_pct']:+.2f}%")
        
        # Save checkpoint and partial results after each symbol
        save_checkpoint(list(processed_indices), [])
        save_partial_results(results, output_csv)
    
    # Final save
    if results:
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_csv, index=False)
        
        print(f"\n{'='*70}")
        print(f"✅ Analysis complete!")
        print(f"   Total processed: {len(results)}/{total_signals}")
        print(f"   Results saved to: {output_csv}")
        print(f"{'='*70}")
        
        # Summary stats
        total_hit = df_results['target_hit_after_cancel'].sum()
        hit_rate = (total_hit / len(df_results)) * 100 if len(df_results) > 0 else 0
        
        buy_df = df_results[df_results['verdict'] == 'BUY']
        sell_df = df_results[df_results['verdict'] == 'SELL']
        
        buy_hit = buy_df['target_hit_after_cancel'].sum() if len(buy_df) > 0 else 0
        buy_rate = (buy_hit / len(buy_df) * 100) if len(buy_df) > 0 else 0
        
        sell_hit = sell_df['target_hit_after_cancel'].sum() if len(sell_df) > 0 else 0
        sell_rate = (sell_hit / len(sell_df) * 100) if len(sell_df) > 0 else 0
        
        avg_adverse = df_results['adverse_deviation_pct'].mean()
        
        print(f"\n📊 Quick Summary:")
        print(f"   Overall target hit rate: {hit_rate:.1f}% ({int(total_hit)}/{len(df_results)})")
        print(f"   BUY hit rate: {buy_rate:.1f}% ({int(buy_hit)}/{len(buy_df)})")
        print(f"   SELL hit rate: {sell_rate:.1f}% ({int(sell_hit)}/{len(sell_df)})")
        print(f"   Avg adverse deviation: {avg_adverse:+.2f}%")
        
        # Cache stats
        final_cache_stats = cache.get_stats()
        print(f"\n📦 Cache stats:")
        print(f"   Total cached entries: {final_cache_stats['total_entries']}")
        
        return df_results
    else:
        print("\n⚠ No results generated")
        return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze cancelled signals with caching')
    parser.add_argument('--all', action='store_true', help='Analyze all signals (not just yesterday+today)')
    parser.add_argument('--output', default='analysis/cancelled_postmortem_results_v2.csv', help='Output CSV path')
    
    args = parser.parse_args()
    
    run_analysis_v2(yesterday_today=not args.all, output_csv=args.output)
