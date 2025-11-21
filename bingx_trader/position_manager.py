"""
Position Manager
Manages opening, closing, and monitoring positions
"""
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from .config import TradingConfig, PaperTradingConfig
from .bingx_client import BingXClient
from .risk_manager import RiskManager

class PositionManager:
    def __init__(self, client: BingXClient, risk_manager: RiskManager):
        self.client = client
        self.risk_manager = risk_manager
        self.positions_file = TradingConfig.POSITIONS_FILE
        self._ensure_positions_file()
        self._ensure_last_close_file()
    
    def _ensure_positions_file(self):
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
        if not os.path.exists(self.positions_file):
            self._save_positions([])
    
    def _ensure_last_close_file(self):
        if TradingConfig.MODE != "PAPER" or not PaperTradingConfig.ALL_IN_MODE:
            return
        
        os.makedirs(os.path.dirname(PaperTradingConfig.LAST_POSITION_CLOSE_FILE), exist_ok=True)
        
        if not os.path.exists(PaperTradingConfig.LAST_POSITION_CLOSE_FILE):
            with open(PaperTradingConfig.LAST_POSITION_CLOSE_FILE, 'w') as f:
                json.dump({'last_close_time': None}, f)
    
    def _get_last_close_time(self) -> Optional[datetime]:
        if TradingConfig.MODE != "PAPER" or not PaperTradingConfig.ALL_IN_MODE:
            return None
        
        try:
            with open(PaperTradingConfig.LAST_POSITION_CLOSE_FILE, 'r') as f:
                data = json.load(f)
                close_time_str = data.get('last_close_time')
                if close_time_str:
                    return datetime.fromisoformat(close_time_str)
        except:
            pass
        return None
    
    def _save_last_close_time(self, close_time: datetime):
        if TradingConfig.MODE != "PAPER" or not PaperTradingConfig.ALL_IN_MODE:
            return
        
        with open(PaperTradingConfig.LAST_POSITION_CLOSE_FILE, 'w') as f:
            json.dump({
                'last_close_time': close_time.isoformat(),
                'updated_at': datetime.now().isoformat()
            }, f, indent=2)
    
    def _load_positions(self) -> List[Dict]:
        try:
            with open(self.positions_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _save_positions(self, positions: List[Dict]):
        with open(self.positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
    
    def get_active_positions(self) -> List[Dict]:
        return self._load_positions()
    
    def calculate_tp_sl(self, entry_price: float, side: str, signal: Dict) -> tuple[float, float]:
        leverage = TradingConfig.LEVERAGE
        sl_pct = TradingConfig.STOP_LOSS_PCT / 100
        
        price_change_for_sl = sl_pct / leverage
        
        if side == "BUY":
            sl_price = entry_price * (1 - price_change_for_sl)
            
            if TradingConfig.TP_STRATEGY == "hybrid":
                tp_price = self._calculate_hybrid_tp(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "far":
                tp_price = self._calculate_far_tp(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "target_min":
                tp_price = self._calculate_target_min(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "fixed_50":
                tp_price = entry_price * (1 + 0.01)
            elif TradingConfig.TP_STRATEGY == "fixed_75":
                tp_price = entry_price * (1 + 0.015)
            else:
                tp_pct = TradingConfig.FIXED_TP_PCT / 100
                price_change_for_tp = tp_pct / leverage
                tp_price = entry_price * (1 + price_change_for_tp)
        
        else:
            sl_price = entry_price * (1 + price_change_for_sl)
            
            if TradingConfig.TP_STRATEGY == "hybrid":
                tp_price = self._calculate_hybrid_tp(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "far":
                tp_price = self._calculate_far_tp(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "target_min":
                tp_price = self._calculate_target_min(signal, entry_price)
            elif TradingConfig.TP_STRATEGY == "fixed_50":
                tp_price = entry_price * (1 - 0.01)
            elif TradingConfig.TP_STRATEGY == "fixed_75":
                tp_price = entry_price * (1 - 0.015)
            else:
                tp_pct = TradingConfig.FIXED_TP_PCT / 100
                price_change_for_tp = tp_pct / leverage
                tp_price = entry_price * (1 - price_change_for_tp)
        
        return round(tp_price, 6), round(sl_price, 6)
    
    def _calculate_hybrid_tp(self, signal: Dict, entry_price: float) -> float:
        """
        Hybrid TP strategy optimized from backtesting (Nov 17, 2025):
        - BUY signals: target_min (closer to entry, conservative)
        - SELL signals: target_max (farther from entry, aggressive)
        
        This maximizes TP hit rate while maintaining good profit potential.
        """
        side = signal['verdict']
        
        if side == "BUY":
            target_price = signal.get('target_min')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        else:
            target_price = signal.get('target_max')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        
        # Fallback to legacy calculation if target not available
        leverage = TradingConfig.LEVERAGE
        confidence = float(signal.get('confidence', 0.5))
        
        base_target_pct = 1.5 if confidence >= 0.70 else 1.0
        
        tp_pct = base_target_pct / 100
        price_change = tp_pct / leverage
        
        if side == "BUY":
            return entry_price * (1 + price_change)
        else:
            return entry_price * (1 - price_change)
    
    def _calculate_far_tp(self, signal: Dict, entry_price: float) -> float:
        """
        Far target TP strategy optimized from backtesting (Nov 19, 2025):
        - BUY signals: target_max (farther from entry, aggressive)
        - SELL signals: target_min (farther from entry, aggressive)
        
        This strategy achieves higher profit per successful trade.
        Best results with 100x leverage and narrow SL (14%).
        """
        side = signal['verdict']
        
        if side == "BUY":
            target_price = signal.get('target_max')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        else:
            target_price = signal.get('target_min')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        
        # Fallback to legacy calculation if target not available
        leverage = TradingConfig.LEVERAGE
        confidence = float(signal.get('confidence', 0.5))
        
        base_target_pct = 1.5 if confidence >= 0.70 else 1.0
        
        tp_pct = base_target_pct / 100
        price_change = tp_pct / leverage
        
        if side == "BUY":
            return entry_price * (1 + price_change)
        else:
            return entry_price * (1 - price_change)
    
    def _calculate_target_min(self, signal: Dict, entry_price: float) -> float:
        # Use closest target to entry price (conservative approach):
        # - For BUY: target_min (lower target, closer to entry)
        # - For SELL: target_max (higher target, closer to entry)
        
        side = signal['verdict']
        
        if side == "BUY":
            target_price = signal.get('target_min')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        else:
            target_price = signal.get('target_max')
            if target_price:
                try:
                    target_float = float(target_price)
                    if target_float > 0:
                        return target_float
                except (ValueError, TypeError):
                    pass
        
        # Fallback to legacy calculation if target not available
        leverage = TradingConfig.LEVERAGE
        confidence = float(signal.get('confidence', 0.5))
        
        base_target_pct = 1.5 if confidence >= 0.70 else 1.0
        
        tp_pct = base_target_pct / 100
        price_change = tp_pct / leverage
        
        if side == "BUY":
            return entry_price * (1 + price_change)
        else:
            return entry_price * (1 - price_change)
    
    def open_position(self, signal: Dict) -> Optional[Dict]:
        positions = self.get_active_positions()
        
        if TradingConfig.MODE == "PAPER" and PaperTradingConfig.ALL_IN_MODE:
            if positions:
                print(f"⏸️  ALL-IN MODE: Position already open, skipping signal")
                return None
            
            last_close_time = self._get_last_close_time()
            if last_close_time:
                signal_time = datetime.fromisoformat(signal.get('timestamp', ''))
                if signal_time <= last_close_time:
                    time_diff = (last_close_time - signal_time).total_seconds()
                    print(f"⏩ ALL-IN MODE: Skipping old signal (sent {time_diff:.0f}s before last position close)")
                    return None
        
        can_open, reason = self.risk_manager.can_open_position(positions)
        if not can_open:
            print(f"Cannot open position: {reason}")
            return None
        
        is_valid, reason = self.risk_manager.is_valid_signal(signal)
        if not is_valid:
            print(f"Invalid signal: {reason}")
            return None
        
        symbol = signal['symbol']
        side = "BUY" if signal['verdict'] == "BUY" else "SELL"
        entry_price = float(signal['entry_price'])
        
        # Check for duplicate position (same symbol and side) opened within last 1 minute
        for pos in positions:
            if pos['symbol'] == symbol and pos['side'] == side:
                pos_time = datetime.fromisoformat(pos['timestamp_open'])
                time_diff = (datetime.now() - pos_time).total_seconds()
                
                if time_diff < 60:  # Block duplicates within 1 minute
                    print(f"⚠️  Position already exists: {symbol} {side} (opened {time_diff:.0f}s ago)")
                    return None
                else:
                    print(f"✅ Allowing new {symbol} {side} signal (previous position opened {time_diff/60:.1f}min ago)")
        
        tp_price, sl_price = self.calculate_tp_sl(entry_price, side, signal)
        
        if TradingConfig.MODE == "PAPER" and PaperTradingConfig.ALL_IN_MODE:
            position_size_usd = self.risk_manager.get_current_balance()
            print(f"💰 ALL-IN MODE: Using full balance ${position_size_usd:.2f}")
        else:
            position_size_usd = TradingConfig.POSITION_SIZE_USD
        
        quantity = self.risk_manager.calculate_position_quantity(
            entry_price,
            position_size_usd,
            TradingConfig.LEVERAGE
        )
        
        # LIVE MODE: Execute real trades on BingX
        if TradingConfig.MODE == "LIVE":
            try:
                # 1. Check balance first
                balance_result = self.client.get_balance()
                if balance_result.get('code') != 0:
                    print(f"❌ Failed to get balance: {balance_result}")
                    return None
                
                # Debug: Print full balance response
                print(f"📊 Balance API Response: {balance_result}")
                
                try:
                    available_margin_str = balance_result['data']['balance']['availableMargin']
                    if not available_margin_str or available_margin_str == '':
                        print(f"❌ CRITICAL: BingX returned empty availableMargin!")
                        print(f"   Full response: {balance_result}")
                        print(f"   Check: 1) API keys have correct permissions, 2) Funds in Perpetual Futures account")
                        return None
                    
                    available_balance = float(available_margin_str)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"❌ CRITICAL: Failed to parse balance from BingX response: {e}")
                    print(f"   Full response: {balance_result}")
                    return None
                
                required_margin = TradingConfig.POSITION_SIZE_USD / TradingConfig.LEVERAGE
                
                if available_balance < required_margin:
                    print(f"❌ Insufficient balance: ${available_balance:.2f} < ${required_margin:.2f} required")
                    return None
                
                print(f"✅ Balance check passed: ${available_balance:.2f} available")
                
                # 2. Set leverage for this symbol (CRITICAL - must succeed)
                print(f"📊 Setting leverage to {TradingConfig.LEVERAGE}x for {symbol}...")
                leverage_result = self.client.set_leverage(symbol, TradingConfig.LEVERAGE)
                if leverage_result.get('code') != 0:
                    print(f"❌ CRITICAL: Failed to set leverage to {TradingConfig.LEVERAGE}x: {leverage_result}")
                    print(f"   Cannot open position with unknown leverage - ABORTING order placement")
                    return None
                else:
                    print(f"✅ Leverage set to {TradingConfig.LEVERAGE}x")
                
                # 3. Place the market order on BingX
                print(f"🚀 Placing LIVE order: {symbol} {side} qty={quantity:.4f} @ ${entry_price:.4f}")
                order_result = self.client.place_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    stop_loss=sl_price,
                    take_profit=tp_price
                )
                
                if order_result.get('code') != 0:
                    error_code = order_result.get('code')
                    error_msg = order_result.get('msg', 'Unknown error')
                    
                    # Provide specific feedback for common errors
                    if error_code == 101204:  # Insufficient margin
                        print(f"❌ INSUFFICIENT MARGIN to open ${TradingConfig.POSITION_SIZE_USD} position")
                        print(f"   Available: ${available_balance:.2f} | Required: ${required_margin:.2f}")
                        print(f"   Used Margin: ${float(balance_result['data']['balance']['usedMargin']):.2f}")
                        print(f"   💡 Solution: Close existing positions or reduce position size")
                    else:
                        print(f"❌ Order failed: Code={error_code}, Msg={error_msg}")
                    
                    return None
                
                # Get actual entry price and order ID from BingX response
                order_data = order_result.get('data', {}).get('order', {})
                order_id = order_data.get('orderId', 'unknown')
                
                # Market orders execute at current price - get more accurate fill price
                try:
                    import time
                    time.sleep(0.5)  # Brief delay for order execution
                    actual_entry = self.client.get_current_price(symbol)
                    print(f"📈 Got actual execution price: ${actual_entry:.4f} (vs signal ${entry_price:.4f})")
                except Exception as e:
                    print(f"⚠️  Could not get execution price, using signal price: {e}")
                    actual_entry = entry_price
                
                print(f"✅ LIVE order placed successfully! Order ID: {order_id}")
                print(f"   Symbol: {symbol} | Side: {side}")
                print(f"   Entry: ${actual_entry:.4f} | TP: ${tp_price:.4f} | SL: ${sl_price:.4f}")
                
            except Exception as e:
                print(f"❌ Error placing LIVE order: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"📝 PAPER MODE: Simulating position for {symbol} {side}")
            order_id = None
            actual_entry = entry_price
        
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': actual_entry,  # Use actual fill price from BingX
            'signal_price': entry_price,  # Keep signal price for reference
            'tp_price': tp_price,
            'sl_price': sl_price,
            'quantity': quantity,
            'position_size_usd': position_size_usd,
            'confidence': float(signal.get('confidence', 0)),
            'tp_strategy': TradingConfig.TP_STRATEGY,
            'timestamp_open': datetime.now().isoformat(),
            'signal_timestamp': signal.get('timestamp', ''),
            'ttl_minutes': int(signal.get('ttl_minutes', 30)),
            'highest_price': actual_entry,
            'lowest_price': actual_entry,
            'mode': TradingConfig.MODE,
            'bingx_order_id': order_id if TradingConfig.MODE == "LIVE" else None,
            'telegram_msg_id': None  # Will be set after Telegram notification
        }
        
        positions.append(position)
        self._save_positions(positions)
        
        return position
    
    def close_position(self, position: Dict, exit_price: float, reason: str) -> Dict:
        # LIVE MODE: Close real position on BingX
        if TradingConfig.MODE == "LIVE" and position.get('mode') == "LIVE":
            symbol = position['symbol']
            quantity = position['quantity']
            position_side = 'LONG' if position['side'] == 'BUY' else 'SHORT'
            
            print(f"🔴 Closing LIVE position: {symbol} {position_side} qty={quantity:.4f}")
            print(f"   Reason: {reason} | Exit price: ${exit_price:.4f}")
            
            try:
                close_result = self.client.close_position(
                    symbol=symbol,
                    position_side=position_side,
                    quantity=quantity
                )
                
                if close_result.get('code') != 0:
                    error_code = close_result.get('code')
                    
                    # Special handling for "No position to close" error (101205)
                    # This means position was already closed on exchange (via TP/SL orders or manually)
                    if error_code == 101205:
                        print(f"⚠️  Position {symbol} already closed on BingX (likely via TP/SL)")
                        print(f"   Removing from local tracking and calculating results...")
                        # Continue to cleanup and PnL calculation below
                        # Use reason to determine exit price (SL or TP)
                        if "Stop-Loss" in reason:
                            exit_price = position['sl_price']
                            print(f"   Assuming SL exit price: ${exit_price:.4f}")
                        elif "Take-Profit" in reason:
                            exit_price = position['tp_price']
                            print(f"   Assuming TP exit price: ${exit_price:.4f}")
                        else:
                            # Use provided exit_price as best guess
                            print(f"   Using provided exit price: ${exit_price:.4f}")
                    else:
                        # Other errors are still critical
                        error_msg = f"BingX API returned error closing {symbol}: {close_result}"
                        print(f"❌ CRITICAL: {error_msg}")
                        print(f"   Position remains OPEN on exchange!")
                        raise RuntimeError(error_msg)
                
                order_id = close_result.get('data', {}).get('order', {}).get('orderId', 'unknown')
                print(f"✅ Position closed successfully on BingX! Order ID: {order_id}")
                    
            except RuntimeError:
                raise
            except Exception as e:
                error_msg = f"Exception closing LIVE position {symbol}: {str(e)}"
                print(f"❌ CRITICAL: {error_msg}")
                print(f"   Position may remain OPEN on exchange!")
                import traceback
                traceback.print_exc()
                raise RuntimeError(error_msg) from e
        else:
            print(f"📝 PAPER MODE: Simulating position close for {position['symbol']}")
        
        # Only remove from local storage after successful BingX close (or in PAPER mode)
        positions = self.get_active_positions()
        
        positions = [p for p in positions if not (
            p['symbol'] == position['symbol'] and 
            p['timestamp_open'] == position['timestamp_open']
        )]
        
        self._save_positions(positions)
        
        entry = position['entry_price']
        side = position['side']
        
        if side == "BUY":
            price_change_pct = (exit_price / entry - 1) * 100
        else:
            price_change_pct = (entry / exit_price - 1) * 100
        
        # Calculate profit with leverage
        profit_usd = position['position_size_usd'] * TradingConfig.LEVERAGE * (price_change_pct / 100)
        
        # Subtract fees (charged on leveraged notional value)
        fee = position['position_size_usd'] * TradingConfig.LEVERAGE * (TradingConfig.TAKER_FEE + TradingConfig.MAKER_FEE)
        profit_usd -= fee
        
        timestamp_open = datetime.fromisoformat(position['timestamp_open'])
        duration = (datetime.now() - timestamp_open).total_seconds() / 60
        
        trade_result = {
            'timestamp_open': position['timestamp_open'],
            'timestamp_close': datetime.now().isoformat(),
            'symbol': position['symbol'],
            'side': side,
            'entry_price': entry,
            'exit_price': exit_price,
            'exit_reason': reason,
            'tp_strategy_used': position['tp_strategy'],
            'tp_price_set': position['tp_price'],
            'sl_price_set': position['sl_price'],
            'highest_during_trade': position.get('highest_price', entry),
            'lowest_during_trade': position.get('lowest_price', entry),
            'actual_profit_usd': profit_usd,
            'actual_profit_pct': price_change_pct,
            'duration_minutes': int(duration),
            'confidence': position['confidence'],
            'mode': position['mode']
        }
        
        self._calculate_alternative_outcomes(trade_result, position)
        
        if profit_usd < 0:
            self.risk_manager.record_loss(profit_usd)
        
        if TradingConfig.MODE == "PAPER" and PaperTradingConfig.ALL_IN_MODE:
            self.risk_manager.update_balance(profit_usd)
            self._save_last_close_time(datetime.now())
        
        return trade_result
    
    def _calculate_alternative_outcomes(self, trade_result: Dict, position: Dict):
        entry = position['entry_price']
        side = position['side']
        highest = position.get('highest_price', entry)
        lowest = position.get('lowest_price', entry)
        
        if side == "BUY":
            target_min_price = position['tp_price']
            fixed_50_price = entry * 1.01
            fixed_75_price = entry * 1.015
            
            would_hit_target_min = highest >= target_min_price
            would_hit_50 = highest >= fixed_50_price
            would_hit_75 = highest >= fixed_75_price
        else:
            target_min_price = position['tp_price']
            fixed_50_price = entry * 0.99
            fixed_75_price = entry * 0.985
            
            would_hit_target_min = lowest <= target_min_price
            would_hit_50 = lowest <= fixed_50_price
            would_hit_75 = lowest <= fixed_75_price
        
        position_size = position['position_size_usd']
        
        profit_target_min = position_size * 0.30 if would_hit_target_min else 0
        profit_50 = position_size * 0.50 if would_hit_50 else 0
        profit_75 = position_size * 0.75 if would_hit_75 else 0
        
        best_profit = max(profit_target_min, profit_50, profit_75)
        if best_profit == profit_75:
            best_strategy = "fixed_75"
        elif best_profit == profit_50:
            best_strategy = "fixed_50"
        else:
            best_strategy = "target_min"
        
        missed = best_profit - trade_result['actual_profit_usd']
        
        trade_result.update({
            'would_hit_target_min': would_hit_target_min,
            'would_hit_fixed_50': would_hit_50,
            'would_hit_fixed_75': would_hit_75,
            'profit_target_min': profit_target_min,
            'profit_fixed_50': profit_50,
            'profit_fixed_75': profit_75,
            'best_strategy': best_strategy,
            'missed_profit': max(0, missed)
        })
    
    def update_position_extremes(self, position: Dict, current_price: float):
        positions = self.get_active_positions()
        
        for p in positions:
            if (p['symbol'] == position['symbol'] and 
                p['timestamp_open'] == position['timestamp_open']):
                
                p['highest_price'] = max(p.get('highest_price', current_price), current_price)
                p['lowest_price'] = min(p.get('lowest_price', current_price), current_price)
                break
        
        self._save_positions(positions)
    
    def update_telegram_msg_id(self, position: Dict, telegram_msg_id: Optional[int]):
        """Update telegram_msg_id for a position."""
        if not telegram_msg_id:
            return
        
        positions = self.get_active_positions()
        
        for p in positions:
            if (p['symbol'] == position['symbol'] and 
                p['timestamp_open'] == position['timestamp_open']):
                
                p['telegram_msg_id'] = telegram_msg_id
                break
        
        self._save_positions(positions)
