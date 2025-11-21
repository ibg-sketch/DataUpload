#!/usr/bin/env python3
"""
Kline Cache Module - SQLite-backed persistent storage for historical klines

Stores klines from Coinalyze API to avoid redundant API calls and manage rate limits.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Tuple
import os


class KlineCache:
    """SQLite cache for historical klines"""
    
    def __init__(self, db_path='analysis/kline_cache.db'):
        """Initialize cache with SQLite database"""
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                start_ts INTEGER NOT NULL,
                end_ts INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, interval, start_ts, end_ts)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_symbol_interval 
            ON kline_cache(symbol, interval, start_ts, end_ts)
        ''')
        
        conn.commit()
        conn.close()
    
    def get_cached_klines(
        self, 
        symbol: str, 
        start_ts: int, 
        end_ts: int, 
        interval: str = '5m'
    ) -> Optional[List]:
        """
        Retrieve cached klines if available.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            start_ts: Start timestamp (unix seconds)
            end_ts: End timestamp (unix seconds)
            interval: Candle interval (default '5m')
        
        Returns:
            List of klines or None if not cached
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT payload_json FROM kline_cache
            WHERE symbol = ? AND interval = ?
            AND start_ts <= ? AND end_ts >= ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (symbol, interval, start_ts, end_ts))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            payload = json.loads(row[0])
            return self._filter_klines_by_time(payload, start_ts, end_ts)
        
        return None
    
    def _filter_klines_by_time(self, klines: List, start_ts: int, end_ts: int) -> List:
        """Filter klines to exact time range"""
        start_ms = start_ts * 1000
        end_ms = end_ts * 1000
        
        return [
            k for k in klines 
            if start_ms <= k[0] <= end_ms
        ]
    
    def cache_klines(
        self, 
        symbol: str, 
        start_ts: int, 
        end_ts: int, 
        klines: List, 
        interval: str = '5m'
    ):
        """
        Store klines in cache.
        
        Args:
            symbol: Trading symbol
            start_ts: Start timestamp (unix seconds)
            end_ts: End timestamp (unix seconds)
            klines: List of klines [[timestamp_ms, o, h, l, c, v], ...]
            interval: Candle interval (default '5m')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        payload_json = json.dumps(klines)
        
        cursor.execute('''
            INSERT OR REPLACE INTO kline_cache 
            (symbol, interval, start_ts, end_ts, payload_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (symbol, interval, start_ts, end_ts, payload_json))
        
        conn.commit()
        conn.close()
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM kline_cache')
        total_entries = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT symbol, COUNT(*) as cnt 
            FROM kline_cache 
            GROUP BY symbol
            ORDER BY cnt DESC
        ''')
        by_symbol = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_entries': total_entries,
            'by_symbol': dict(by_symbol)
        }
    
    def clear_cache(self, symbol: Optional[str] = None):
        """Clear cache (all or for specific symbol)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if symbol:
            cursor.execute('DELETE FROM kline_cache WHERE symbol = ?', (symbol,))
        else:
            cursor.execute('DELETE FROM kline_cache')
        
        conn.commit()
        conn.close()


if __name__ == '__main__':
    cache = KlineCache()
    stats = cache.get_stats()
    print(f"Kline Cache Stats:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  By symbol: {stats['by_symbol']}")
