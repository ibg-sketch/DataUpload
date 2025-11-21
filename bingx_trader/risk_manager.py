"""
Risk Management
Validates trades against risk limits
"""
import json
import os
from typing import Dict, List
from .config import TradingConfig, PaperTradingConfig
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self):
        self.daily_losses = []
        self.max_positions = TradingConfig.MAX_CONCURRENT_POSITIONS
        self.daily_loss_limit = TradingConfig.DAILY_LOSS_LIMIT_USD
        self._ensure_balance_file()
    
    def can_open_position(self, active_positions: List[Dict]) -> tuple[bool, str]:
        if len(active_positions) >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"
        
        daily_loss = self._calculate_daily_loss()
        if abs(daily_loss) >= self.daily_loss_limit:
            return False, f"Daily loss limit reached (${abs(daily_loss):.2f})"
        
        return True, "OK"
    
    def is_valid_signal(self, signal: Dict) -> tuple[bool, str]:
        symbol = signal['symbol']
        
        if symbol not in TradingConfig.TRADING_PAIRS:
            return False, f"Symbol {symbol} not in trading pairs"
        
        confidence = float(signal.get('confidence', 0))
        if confidence < TradingConfig.MIN_CONFIDENCE / 100:
            return False, f"Confidence {confidence*100:.0f}% below minimum {TradingConfig.MIN_CONFIDENCE}%"
        
        return True, "OK"
    
    def record_loss(self, loss_amount: float):
        if loss_amount < 0:
            self.daily_losses.append({
                'amount': loss_amount,
                'timestamp': datetime.now()
            })
            self._cleanup_old_losses()
    
    def _calculate_daily_loss(self) -> float:
        self._cleanup_old_losses()
        return sum(loss['amount'] for loss in self.daily_losses)
    
    def _cleanup_old_losses(self):
        cutoff = datetime.now() - timedelta(hours=24)
        self.daily_losses = [
            loss for loss in self.daily_losses 
            if loss['timestamp'] > cutoff
        ]
    
    def calculate_position_quantity(self, entry_price: float, position_size_usd: float, leverage: int) -> float:
        notional_value = position_size_usd * leverage
        quantity = notional_value / entry_price
        return round(quantity, 4)
    
    def _ensure_balance_file(self):
        """
        Initialize balance tracking file for paper trading P&L calculation.
        Note: Balance is tracked for P&L reporting only - it does NOT limit position opening.
        """
        if TradingConfig.MODE != "PAPER":
            return
        
        os.makedirs(os.path.dirname(PaperTradingConfig.CURRENT_BALANCE_FILE), exist_ok=True)
        
        if not os.path.exists(PaperTradingConfig.CURRENT_BALANCE_FILE):
            self._save_balance(PaperTradingConfig.STARTING_BALANCE)
    
    def get_current_balance(self) -> float:
        """
        Get current paper trading balance for P&L tracking.
        This balance is informational only - it does NOT prevent opening new positions.
        """
        if TradingConfig.MODE != "PAPER":
            return 0.0
        
        try:
            with open(PaperTradingConfig.CURRENT_BALANCE_FILE, 'r') as f:
                data = json.load(f)
                return float(data.get('balance', PaperTradingConfig.STARTING_BALANCE))
        except:
            return PaperTradingConfig.STARTING_BALANCE
    
    def _save_balance(self, balance: float):
        if TradingConfig.MODE != "PAPER":
            return
        
        with open(PaperTradingConfig.CURRENT_BALANCE_FILE, 'w') as f:
            json.dump({
                'balance': balance,
                'updated_at': datetime.now().isoformat()
            }, f, indent=2)
    
    def update_balance(self, pnl: float):
        if TradingConfig.MODE != "PAPER":
            return
        
        current = self.get_current_balance()
        new_balance = current + pnl
        self._save_balance(new_balance)
        print(f"💰 Balance updated: ${current:.2f} → ${new_balance:.2f} (P&L: ${pnl:+.2f})")
