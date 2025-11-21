"""
Trade Logger
Logs all trades with alternative TP tracking
"""
import csv
import os
from datetime import datetime
from typing import Optional

class TradeLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp_open', 'timestamp_close', 'symbol', 'side',
                    'entry_price', 'exit_price', 'exit_reason',
                    'tp_strategy_used', 'tp_price_set', 'sl_price_set',
                    'highest_during_trade', 'lowest_during_trade',
                    'would_hit_target_min', 'would_hit_fixed_50', 'would_hit_fixed_75',
                    'profit_target_min', 'profit_fixed_50', 'profit_fixed_75',
                    'actual_profit_usd', 'actual_profit_pct',
                    'best_strategy', 'missed_profit',
                    'duration_minutes', 'confidence', 'mode'
                ])
    
    def log_trade(self, trade_data: dict):
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade_data.get('timestamp_open', ''),
                trade_data.get('timestamp_close', ''),
                trade_data.get('symbol', ''),
                trade_data.get('side', ''),
                trade_data.get('entry_price', 0),
                trade_data.get('exit_price', 0),
                trade_data.get('exit_reason', ''),
                trade_data.get('tp_strategy_used', ''),
                trade_data.get('tp_price_set', 0),
                trade_data.get('sl_price_set', 0),
                trade_data.get('highest_during_trade', 0),
                trade_data.get('lowest_during_trade', 0),
                trade_data.get('would_hit_target_min', False),
                trade_data.get('would_hit_fixed_50', False),
                trade_data.get('would_hit_fixed_75', False),
                trade_data.get('profit_target_min', 0),
                trade_data.get('profit_fixed_50', 0),
                trade_data.get('profit_fixed_75', 0),
                trade_data.get('actual_profit_usd', 0),
                trade_data.get('actual_profit_pct', 0),
                trade_data.get('best_strategy', ''),
                trade_data.get('missed_profit', 0),
                trade_data.get('duration_minutes', 0),
                trade_data.get('confidence', 0),
                trade_data.get('mode', 'PAPER')
            ])
