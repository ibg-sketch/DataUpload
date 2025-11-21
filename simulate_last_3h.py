"""
Simulate trading with 50x leverage + 25% SL + Far target TP for last 3 hours
"""
import pandas as pd
from datetime import datetime, timedelta

# Load data
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])

# Last 3 hours
now = datetime.now()
three_hours_ago = now - timedelta(hours=3)
df_3h = df[df['timestamp_sent'] >= three_hours_ago].copy()

# Convert numeric columns
for col in ['entry_price', 'final_price', 'profit_pct', 'highest_reached', 'lowest_reached', 'target_min', 'target_max']:
    df_3h[col] = pd.to_numeric(df_3h[col], errors='coerce')

df_clean = df_3h.dropna(subset=['entry_price', 'final_price', 'profit_pct']).copy()

print(f"📊 Симуляция торговли за последние 3 часа")
print(f"   От: {three_hours_ago.strftime('%Y-%m-%d %H:%M')}")
print(f"   До: {now.strftime('%Y-%m-%d %H:%M')}")
print(f"   Сигналов: {len(df_clean)}")
print()

# Configuration
LEVERAGE = 50
SL_PCT = 25  # 25% of position = 0.50% price movement at 50x
INITIAL_BALANCE = 1000.0
POSITION_SIZE = 50.0

# Fees
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# Trading simulation
balance = INITIAL_BALANCE
trades_log = []
tp_exits = 0
sl_exits = 0
ttl_exits = 0
total_wins = 0

for idx, row in df_clean.iterrows():
    if balance <= 0:
        print(f"⚠️ Баланс обнулился на сделке {len(trades_log) + 1}")
        break
    
    trade_size = min(POSITION_SIZE, balance)
    position_value = trade_size * LEVERAGE
    
    entry = row['entry_price']
    side = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    
    # Far target TP strategy
    if side == 'BUY':
        tp_price = target_max  # Far target for BUY
    else:
        tp_price = target_min  # Far target for SELL
    
    # Calculate SL price
    sl_price_change = (SL_PCT / 100) / LEVERAGE
    if side == 'BUY':
        sl_price = entry * (1 - sl_price_change)
    else:
        sl_price = entry * (1 + sl_price_change)
    
    # Check if SL was hit
    sl_hit = False
    if side == 'BUY' and not pd.isna(lowest):
        sl_hit = lowest <= sl_price
    elif side == 'SELL' and not pd.isna(highest):
        sl_hit = highest >= sl_price
    
    # Check if TP was hit
    tp_hit = False
    if not sl_hit and not pd.isna(tp_price):
        if side == 'BUY' and not pd.isna(highest):
            tp_hit = highest >= tp_price
        elif side == 'SELL' and not pd.isna(lowest):
            tp_hit = lowest <= tp_price
    
    # Calculate PnL
    exit_type = ''
    if sl_hit:
        # SL exit
        if side == 'BUY':
            pnl_pct = (sl_price / entry - 1) * LEVERAGE
        else:
            pnl_pct = (1 - sl_price / entry) * LEVERAGE
        
        fees = position_value * (TAKER_FEE + TAKER_FEE)
        pnl = position_value * pnl_pct - fees
        exit_type = 'SL'
        sl_exits += 1
    elif tp_hit:
        # TP exit
        if side == 'BUY':
            pnl_pct = (tp_price / entry - 1) * LEVERAGE
        else:
            pnl_pct = (1 - tp_price / entry) * LEVERAGE
        
        fees = position_value * (TAKER_FEE + MAKER_FEE)
        pnl = position_value * pnl_pct - fees
        exit_type = 'TP'
        tp_exits += 1
    else:
        # TTL exit at final price
        raw_pnl_pct = row['profit_pct'] / 100
        pnl_pct = raw_pnl_pct * LEVERAGE
        
        fees = position_value * (TAKER_FEE + TAKER_FEE)
        pnl = position_value * pnl_pct - fees
        exit_type = 'TTL'
        ttl_exits += 1
    
    balance += pnl
    
    if pnl > 0:
        total_wins += 1
    
    trades_log.append({
        'time': row['timestamp_sent'],
        'symbol': row['symbol'],
        'side': side,
        'entry': entry,
        'tp': tp_price,
        'sl': sl_price,
        'exit_type': exit_type,
        'pnl': pnl,
        'balance': balance
    })

# Results
total_trades = len(trades_log)
win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
total_pnl = balance - INITIAL_BALANCE
roi = (total_pnl / INITIAL_BALANCE) * 100

print("=" * 100)
print("⚙️ КОНФИГУРАЦИЯ")
print("=" * 100)
print(f"   Плечо: {LEVERAGE}x")
print(f"   Stop-Loss: {SL_PCT}% позиции (= {(SL_PCT/100)/LEVERAGE*100:.2f}% движения цены)")
print(f"   Take-Profit: ДАЛЬНЯЯ ЦЕЛЬ (target_max для BUY, target_min для SELL)")
print(f"   Размер позиции: ${POSITION_SIZE}")
print()

print("=" * 100)
print("💰 РЕЗУЛЬТАТЫ")
print("=" * 100)
print(f"   Начальный баланс:  ${INITIAL_BALANCE:.2f}")
print(f"   Финальный баланс:  ${balance:.2f}")
print(f"   Прибыль/Убыток:    ${total_pnl:+.2f} ({roi:+.2f}%)")
print()

print("=" * 100)
print("📊 СТАТИСТИКА")
print("=" * 100)
print(f"   Всего сделок:      {total_trades}")
print(f"   Win Rate:          {win_rate:.1f}% ({total_wins}/{total_trades})")
print()
print(f"   TP exits:          {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
print(f"   SL exits:          {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
print(f"   TTL exits:         {ttl_exits} ({ttl_exits/total_trades*100:.1f}%)")
print()

# Show last 10 trades
if len(trades_log) > 0:
    print("=" * 100)
    print("📋 ПОСЛЕДНИЕ 10 СДЕЛОК")
    print("=" * 100)
    df_trades = pd.DataFrame(trades_log)
    last_10 = df_trades.tail(10)
    
    for _, trade in last_10.iterrows():
        emoji = "✅" if trade['pnl'] > 0 else "❌"
        print(f"{emoji} {trade['time'].strftime('%H:%M')} | {trade['symbol']:8s} | {trade['side']:4s} | "
              f"{trade['exit_type']:3s} | PnL: ${trade['pnl']:+7.2f} | Balance: ${trade['balance']:.2f}")

# Comparison with current config
print()
print("=" * 100)
print("📊 СРАВНЕНИЕ С ТЕКУЩЕЙ КОНФИГУРАЦИЕЙ (50x, 10% SL, Hybrid)")
print("=" * 100)

# Run simulation for current config
balance_current = INITIAL_BALANCE
SL_PCT_CURRENT = 10
wins_current = 0
tp_current = 0
sl_current = 0
ttl_current = 0

for idx, row in df_clean.iterrows():
    if balance_current <= 0:
        break
    
    trade_size = min(POSITION_SIZE, balance_current)
    position_value = trade_size * LEVERAGE
    
    entry = row['entry_price']
    side = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    
    # Hybrid TP strategy (current)
    if side == 'BUY':
        tp_price = target_min
    else:
        tp_price = target_max
    
    # Calculate SL price
    sl_price_change = (SL_PCT_CURRENT / 100) / LEVERAGE
    if side == 'BUY':
        sl_price = entry * (1 - sl_price_change)
    else:
        sl_price = entry * (1 + sl_price_change)
    
    # Check if SL was hit
    sl_hit = False
    if side == 'BUY' and not pd.isna(lowest):
        sl_hit = lowest <= sl_price
    elif side == 'SELL' and not pd.isna(highest):
        sl_hit = highest >= sl_price
    
    # Check if TP was hit
    tp_hit = False
    if not sl_hit and not pd.isna(tp_price):
        if side == 'BUY' and not pd.isna(highest):
            tp_hit = highest >= tp_price
        elif side == 'SELL' and not pd.isna(lowest):
            tp_hit = lowest <= tp_price
    
    # Calculate PnL
    if sl_hit:
        if side == 'BUY':
            pnl_pct = (sl_price / entry - 1) * LEVERAGE
        else:
            pnl_pct = (1 - sl_price / entry) * LEVERAGE
        
        fees = position_value * (TAKER_FEE + TAKER_FEE)
        pnl = position_value * pnl_pct - fees
        sl_current += 1
    elif tp_hit:
        if side == 'BUY':
            pnl_pct = (tp_price / entry - 1) * LEVERAGE
        else:
            pnl_pct = (1 - tp_price / entry) * LEVERAGE
        
        fees = position_value * (TAKER_FEE + MAKER_FEE)
        pnl = position_value * pnl_pct - fees
        tp_current += 1
    else:
        raw_pnl_pct = row['profit_pct'] / 100
        pnl_pct = raw_pnl_pct * LEVERAGE
        
        fees = position_value * (TAKER_FEE + TAKER_FEE)
        pnl = position_value * pnl_pct - fees
        ttl_current += 1
    
    balance_current += pnl
    
    if pnl > 0:
        wins_current += 1

pnl_current = balance_current - INITIAL_BALANCE
roi_current = (pnl_current / INITIAL_BALANCE) * 100
wr_current = (wins_current / total_trades * 100) if total_trades > 0 else 0

print(f"   Текущая (50x, 10% SL, Hybrid):      ${balance_current:.2f} | ROI {roi_current:+.1f}% | WR {wr_current:.1f}%")
print(f"   Новая (50x, 25% SL, Far target):    ${balance:.2f} | ROI {roi:+.1f}% | WR {win_rate:.1f}%")
print()

improvement = balance - balance_current
improvement_pct = (improvement / INITIAL_BALANCE) * 100

if improvement > 0:
    print(f"   💡 Улучшение: ${improvement:+.2f} ({improvement_pct:+.1f}%)")
else:
    print(f"   ⚠️ Ухудшение: ${improvement:+.2f} ({improvement_pct:+.1f}%)")
