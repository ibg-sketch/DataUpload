"""
Signal Reader
Monitors signals_log.csv for new trading signals
"""
import csv
import os
from typing import Optional, Dict, Set
from datetime import datetime, timedelta

class SignalReader:
    def __init__(self, signal_file: str):
        self.signal_file = signal_file
        self.processed_signals: Set[str] = set()
        self.last_check_time = datetime.now() - timedelta(minutes=10)
    
    def get_latest_signal(self) -> Optional[Dict]:
        if not os.path.exists(self.signal_file):
            return None
        
        try:
            with open(self.signal_file, 'r') as f:
                reader = csv.DictReader(f)
                signals = list(reader)
            
            if not signals:
                return None
            
            valid_signals = []
            for signal in reversed(signals):
                signal_id = self._get_signal_id(signal)
                
                if signal_id in self.processed_signals:
                    continue
                
                signal_time = datetime.fromisoformat(signal['timestamp'].replace(' ', 'T'))
                
                if signal_time < self.last_check_time:
                    continue
                
                ttl_minutes = int(signal.get('ttl_minutes', 0))
                expiry_time = signal_time + timedelta(minutes=ttl_minutes)
                
                if datetime.now() > expiry_time:
                    self.processed_signals.add(signal_id)
                    continue
                
                valid_signals.append(signal)
            
            if not valid_signals:
                return None
            
            latest = valid_signals[0]
            signal_id = self._get_signal_id(latest)
            self.processed_signals.add(signal_id)
            
            return latest
        
        except Exception as e:
            print(f"Error reading signals: {e}")
            return None
    
    def _get_signal_id(self, signal: Dict) -> str:
        return f"{signal['timestamp']}_{signal['symbol']}_{signal['verdict']}"
    
    def mark_as_processed(self, signal: Dict):
        signal_id = self._get_signal_id(signal)
        self.processed_signals.add(signal_id)
