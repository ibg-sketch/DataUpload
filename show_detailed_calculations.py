#!/usr/bin/env python3
"""
Show detailed trade-by-trade calculations with full breakdown
"""
import pandas as pd

# Configuration
LEVERAGE = 50
TAKER_FEE = 0.0005  # 0.05%
CSV_FILE = 'analysis/results/scenario1_oldest_signal.csv'

def show_detailed_trade_calculations(num_trades=20):
    """Show detailed calculations for each trade"""
    
    # Load trades
    df = pd.read_csv(CSV_FILE)
    
    print("=" * 100)
    print("DETAILED TRADE-BY-TRADE CALCULATIONS")
    print("=" * 100)
    print(f"\nShowing first {num_trades} trades with full calculation breakdown\n")
    
    for idx, trade in df.head(num_trades).iterrows():
        trade_num = idx + 1
        
        print(f"\n{'='*100}")
        print(f"TRADE #{trade_num}: {trade['symbol']} {trade['direction']} @ {trade['entry_time']}")
        print(f"{'='*100}")
        
        # Extract data
        balance_before = trade['balance_before']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        direction = trade['direction']
        exit_reason = trade['exit_reason']
        outcome = trade['outcome']
        
        print(f"\n📊 POSITION DETAILS:")
        print(f"   Balance Before:      ${balance_before:,.2f}")
        print(f"   Leverage:            {LEVERAGE}x")
        print(f"   Direction:           {direction}")
        print(f"   Entry Price:         ${entry_price:,.8f}")
        print(f"   Exit Price:          ${exit_price:,.8f}")
        print(f"   Exit Reason:         {exit_reason}")
        print(f"   Outcome:             {outcome}")
        
        # Step 1: Calculate quantity
        position_notional = balance_before * LEVERAGE
        quantity = position_notional / entry_price
        
        print(f"\n🔢 STEP 1: CALCULATE QUANTITY")
        print(f"   Position Notional = Balance × Leverage")
        print(f"   Position Notional = ${balance_before:,.2f} × {LEVERAGE}")
        print(f"   Position Notional = ${position_notional:,.2f}")
        print(f"   ")
        print(f"   Quantity = Position Notional / Entry Price")
        print(f"   Quantity = ${position_notional:,.2f} / ${entry_price:,.8f}")
        print(f"   Quantity = {quantity:,.8f} {trade['symbol'].replace('USDT', '')}")
        
        # Step 2: Calculate entry fee
        entry_notional = quantity * entry_price
        entry_fee = entry_notional * TAKER_FEE
        
        print(f"\n💵 STEP 2: CALCULATE ENTRY FEE")
        print(f"   Entry Notional = Quantity × Entry Price")
        print(f"   Entry Notional = {quantity:,.8f} × ${entry_price:,.8f}")
        print(f"   Entry Notional = ${entry_notional:,.2f}")
        print(f"   ")
        print(f"   Entry Fee = Entry Notional × Taker Fee")
        print(f"   Entry Fee = ${entry_notional:,.2f} × {TAKER_FEE}")
        print(f"   Entry Fee = ${entry_fee:,.2f}")
        
        # Step 3: Calculate exit fee
        exit_notional = quantity * exit_price
        exit_fee = exit_notional * TAKER_FEE
        
        print(f"\n💵 STEP 3: CALCULATE EXIT FEE")
        print(f"   Exit Notional = Quantity × Exit Price")
        print(f"   Exit Notional = {quantity:,.8f} × ${exit_price:,.8f}")
        print(f"   Exit Notional = ${exit_notional:,.2f}")
        print(f"   ")
        print(f"   Exit Fee = Exit Notional × Taker Fee")
        print(f"   Exit Fee = ${exit_notional:,.2f} × {TAKER_FEE}")
        print(f"   Exit Fee = ${exit_fee:,.2f}")
        
        # Step 4: Calculate raw P&L
        if direction == 'SELL':
            raw_pnl = entry_notional - exit_notional
            price_change = entry_price - exit_price
        else:
            raw_pnl = exit_notional - entry_notional
            price_change = exit_price - entry_price
        
        print(f"\n📈 STEP 4: CALCULATE RAW P&L")
        if direction == 'SELL':
            print(f"   Raw P&L = Entry Notional - Exit Notional (SHORT)")
            print(f"   Raw P&L = ${entry_notional:,.2f} - ${exit_notional:,.2f}")
        else:
            print(f"   Raw P&L = Exit Notional - Entry Notional (LONG)")
            print(f"   Raw P&L = ${exit_notional:,.2f} - ${entry_notional:,.2f}")
        print(f"   Raw P&L = ${raw_pnl:,.2f}")
        print(f"   ")
        print(f"   Price Change: ${price_change:,.8f} ({(price_change/entry_price)*100:+.4f}%)")
        
        # Step 5: Calculate net P&L
        net_pnl = raw_pnl - entry_fee - exit_fee
        
        print(f"\n💰 STEP 5: CALCULATE NET P&L")
        print(f"   Net P&L = Raw P&L - Entry Fee - Exit Fee")
        print(f"   Net P&L = ${raw_pnl:,.2f} - ${entry_fee:,.2f} - ${exit_fee:,.2f}")
        print(f"   Net P&L = ${net_pnl:,.2f}")
        
        # Step 6: Calculate new balance
        balance_after = balance_before + net_pnl
        roi_pct = (net_pnl / balance_before) * 100
        
        print(f"\n🏦 STEP 6: UPDATE BALANCE")
        print(f"   New Balance = Old Balance + Net P&L")
        print(f"   New Balance = ${balance_before:,.2f} + ${net_pnl:,.2f}")
        print(f"   New Balance = ${balance_after:,.2f}")
        print(f"   ")
        print(f"   ROI: {roi_pct:+.2f}%")
        
        # Verification
        expected_balance = trade['balance_after']
        if abs(balance_after - expected_balance) > 0.01:
            print(f"\n⚠️  WARNING: Calculated balance ${balance_after:,.2f} != Expected ${expected_balance:,.2f}")
        else:
            print(f"\n✅ VERIFIED: Calculation matches CSV data")
        
        print(f"\n{'─'*100}\n")

if __name__ == '__main__':
    show_detailed_trade_calculations(num_trades=20)
