"""
Cancellation Monitor
Monitors effectiveness_log.csv for cancelled signals and triggers position closure
"""
import csv
import os
from typing import Optional, Dict, Set
from datetime import datetime, timedelta

class CancellationMonitor:
    def __init__(self, effectiveness_log_path: str = 'effectiveness_log.csv'):
        self.log_path = effectiveness_log_path
        self.processed_cancellations: Set[str] = set()
        self.last_check_line = 0
        
        # FIXED: Start from last 100 lines to catch recent cancellations after restart
        # This ensures we process CANCELLED signals that occurred shortly before service restart
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    total_lines = sum(1 for _ in f)
                
                # Start checking from last 100 lines (approx last 30-60 min)
                # This catches recent cancellations without reprocessing entire history
                self.last_check_line = max(0, total_lines - 100)
                
                print(f"[CANCELLATION MONITOR] Initialized: will scan from line {self.last_check_line}/{total_lines} "
                      f"to catch recent cancellations after service restart")
            
            except Exception as e:
                print(f"⚠️  Warning during cancellation monitor init: {e}")
                self.last_check_line = 0
    
    def get_new_cancellations(self) -> list[Dict]:
        """
        Check effectiveness_log.csv for completed signals (WIN, LOSS, CANCELLED).
        Returns list of completed signal data.
        """
        if not os.path.exists(self.log_path):
            return []
        
        new_cancellations = []
        
        try:
            with open(self.log_path, 'r') as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
            
            # Only process rows after last_check_line
            new_rows = all_rows[max(0, self.last_check_line - 1):]
            
            for row in new_rows:
                # Process all completed signals: WIN, LOSS, CANCELLED
                result = row.get('result')
                if result not in ['WIN', 'LOSS', 'CANCELLED']:
                    continue
                
                # Create unique ID for this cancellation
                cancellation_id = self._get_cancellation_id(row)
                
                # Skip if already processed
                if cancellation_id in self.processed_cancellations:
                    continue
                
                # Parse completed signal data
                cancellation_data = {
                    'timestamp_sent': row.get('timestamp_sent'),
                    'timestamp_cancelled': row.get('timestamp_checked'),
                    'symbol': row.get('symbol'),
                    'verdict': row.get('verdict'),
                    'confidence': float(row.get('confidence', 0)),
                    'entry_price': float(row.get('entry_price', 0)),
                    'final_price': float(row.get('final_price', 0)),
                    'profit_pct': float(row.get('profit_pct', 0)),
                    'duration_actual': int(row.get('duration_actual', 0)),
                    'result': result  # WIN, LOSS, or CANCELLED
                }
                
                new_cancellations.append(cancellation_data)
                self.processed_cancellations.add(cancellation_id)
            
            # Update last check line count
            self.last_check_line = len(all_rows) + 1  # +1 for header
            
        except Exception as e:
            print(f"⚠️  Error reading cancellations: {e}")
            return []
        
        return new_cancellations
    
    def _get_cancellation_id(self, row: Dict) -> str:
        """Create unique ID for cancellation tracking."""
        return f"{row.get('timestamp_sent')}_{row.get('symbol')}_{row.get('verdict')}"
    
    def match_position_to_cancellation(self, position: Dict, cancellation: Dict) -> bool:
        """
        Check if a position matches a cancelled signal.
        
        Matching criteria:
        - Same symbol
        - Same side (BUY/SELL)
        - Signal timestamp within position's signal_timestamp window
        """
        # Symbol must match
        if position['symbol'] != cancellation['symbol']:
            return False
        
        # Side must match
        if position['side'] != cancellation['verdict']:
            return False
        
        # Check if timestamps are close (within 1 minute)
        try:
            pos_signal_time = datetime.fromisoformat(
                position['signal_timestamp'].replace(' ', 'T')
            )
            cancel_time = datetime.fromisoformat(
                cancellation['timestamp_sent'].replace(' ', 'T')
            )
            
            time_diff = abs((pos_signal_time - cancel_time).total_seconds())
            
            # Match if timestamps within 60 seconds
            if time_diff <= 60:
                return True
        except Exception as e:
            print(f"⚠️  Error matching timestamps: {e}")
            return False
        
        return False
