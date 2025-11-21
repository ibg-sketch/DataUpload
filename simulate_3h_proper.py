"""
Proper trading simulation with position limits: max 20 positions simultaneously
Last 3 hours with 50x leverage + 25% SL + Far target TP
"""
import pandas as pd
from datetime import datetime, timedelta

# Load effectiveness data
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df['timestamp_checked'] = pd.to_datetime(df['timestamp_checked'])

# Last 3 hours
now = datetime.now()
three_hours_ago = now - timedelta(hours=3)
df_3h = df[df['timestamp_sent'] >= three_hours_ago].copy()

# Convert numeric columns
for col in ['entry_price', 'final_price', 'profit_pct', 'highest_reached', 'lowest_reached', 'target_min', 'target_max', 'duration_actual']:
    df_3h[col] = pd.to_numeric(df_3h[col], errors='coerce')

df_clean = df_3h.dropna(subset=['entry_price', 'final_price', 'profit_pct', 'timestamp_sent', 'timestamp_checked']).copy()
df_clean = df_clean.sort_values('timestamp_sent').reset_index(drop=True)

print(f"📊 Симуляция торговли за последние 3 часа")
print(f"   От: {three_hours_ago.strftime('%Y-%m-%d %H:%M')}")
print(f"   До: {now.strftime('%Y-%m-%d %H:%M')}")
print(f"   Сигналов получено: {len(df_clean)}")
print()

# Configuration
LEVERAGE = 50
SL_PCT = 25  # 25% of position = 0.50% price movement at 50x
INITIAL_BALANCE = 1000.0
POSITION_SIZE = 50.0
MAX_POSITIONS = 20

# Fees
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# Trading state
balance = INITIAL_BALANCE
active_positions = []  # List of open positions
closed_positions = []  # History of closed positions
signals_skipped = 0

def close_position(position, exit_type, exit_price=None):
    """Close a position and calculate PnL"""
    entry = position['entry']
    side = position['side']
    position_value = position['position_value']
    
    if exit_price is None:
        exit_price = position['final_price']
    
    # Calculate PnL
    if side == 'BUY':
        pnl_pct = (exit_price / entry - 1) * LEVERAGE
    else:
        pnl_pct = (1 - exit_price / entry) * LEVERAGE
    
    # Fees
    if exit_type == 'TP':
        fees = position_value * (TAKER_FEE + MAKER_FEE)
    else:
        fees = position_value * (TAKER_FEE + TAKER_FEE)
    
    pnl = position_value * pnl_pct - fees
    
    return {
        'symbol': position['symbol'],
        'side': side,
        'entry': entry,
        'exit': exit_price,
        'exit_type': exit_type,
        'pnl': pnl,
        'time_open': position['time_open'],
        'time_close': position['time_close']
    }

# Process signals chronologically
for idx, signal in df_clean.iterrows():
    signal_time = signal['timestamp_sent']
    close_time = signal['timestamp_checked']
    
    # Close any positions that finished before this signal started
    positions_to_remove = []
    for i, pos in enumerate(active_positions):
        if pos['time_close'] <= signal_time:
            # Position closed before this signal
            closed_pos = close_position(pos, pos['exit_type'], pos['exit_price'])
            closed_positions.append(closed_pos)
            balance += closed_pos['pnl']
            positions_to_remove.append(i)
    
    # Remove closed positions
    for i in reversed(positions_to_remove):
        active_positions.pop(i)
    
    # Check if we can open this position
    if len(active_positions) >= MAX_POSITIONS:
        signals_skipped += 1
        continue
    
    if balance <= 0:
        break
    
    # Open new position
    trade_size = min(POSITION_SIZE, balance)
    position_value = trade_size * LEVERAGE
    
    entry = signal['entry_price']
    side = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    target_min = signal['target_min']
    target_max = signal['target_max']
    final_price = signal['final_price']
    
    # Far target TP strategy
    if side == 'BUY':
        tp_price = target_max
    else:
        tp_price = target_min
    
    # Calculate SL price
    sl_price_change = (SL_PCT / 100) / LEVERAGE
    if side == 'BUY':
        sl_price = entry * (1 - sl_price_change)
    else:
        sl_price = entry * (1 + sl_price_change)
    
    # Check exit type
    exit_type = None
    exit_price = final_price
    
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
    
    if sl_hit:
        exit_type = 'SL'
        exit_price = sl_price
    elif tp_hit:
        exit_type = 'TP'
        exit_price = tp_price
    else:
        exit_type = 'TTL'
        exit_price = final_price
    
    # Create position
    position = {
        'symbol': signal['symbol'],
        'side': side,
        'entry': entry,
        'tp': tp_price,
        'sl': sl_price,
        'final_price': final_price,
        'position_value': position_value,
        'time_open': signal_time,
        'time_close': close_time,
        'exit_type': exit_type,
        'exit_price': exit_price
    }
    
    # Add to active positions (will be closed when time comes)
    active_positions.append(position)

# Close any remaining active positions at the end
for pos in active_positions:
    closed_pos = close_position(pos, pos['exit_type'], pos['exit_price'])
    closed_positions.append(closed_pos)
    balance += closed_pos['pnl']

# Calculate statistics
total_trades = len(closed_positions)
if total_trades == 0:
    print("⚠️ Нет закрытых позиций!")
    exit()

wins = sum(1 for p in closed_positions if p['pnl'] > 0)
losses = sum(1 for p in closed_positions if p['pnl'] <= 0)
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

tp_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TP')
sl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'SL')
ttl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TTL')

total_pnl = balance - INITIAL_BALANCE
roi = (total_pnl / INITIAL_BALANCE) * 100

# Average PnL per trade
avg_win = sum(p['pnl'] for p in closed_positions if p['pnl'] > 0) / wins if wins > 0 else 0
avg_loss = sum(p['pnl'] for p in closed_positions if p['pnl'] <= 0) / losses if losses > 0 else 0

print("=" * 100)
print("⚙️ КОНФИГУРАЦИЯ")
print("=" * 100)
print(f"   Депозит: ${INITIAL_BALANCE:.2f}")
print(f"   Размер позиции: ${POSITION_SIZE} (макс)")
print(f"   Макс одновременных позиций: {MAX_POSITIONS}")
print(f"   Плечо: {LEVERAGE}x")
print(f"   Stop-Loss: {SL_PCT}% позиции (= {(SL_PCT/100)/LEVERAGE*100:.2f}% движения цены)")
print(f"   Take-Profit: ДАЛЬНЯЯ ЦЕЛЬ (target_max для BUY, target_min для SELL)")
print()

print("=" * 100)
print("💰 РЕЗУЛЬТАТЫ")
print("=" * 100)
print(f"   Начальный баланс:  ${INITIAL_BALANCE:.2f}")
print(f"   Финальный баланс:  ${balance:.2f}")
print(f"   Прибыль/Убыток:    ${total_pnl:+.2f} ({roi:+.2f}%)")
print()

print("=" * 100)
print("📊 СТАТИСТИКА ПОЗИЦИЙ")
print("=" * 100)
print(f"   Сигналов получено:     {len(df_clean)}")
print(f"   Позиций открыто:       {total_trades}")
print(f"   Сигналов пропущено:    {signals_skipped} (лимит позиций)")
print()
print(f"   Win Rate:              {win_rate:.1f}% ({wins}/{total_trades})")
print(f"   Прибыльных:            {wins} | Средний профит: ${avg_win:.2f}")
print(f"   Убыточных:             {losses} | Средний убыток: ${avg_loss:.2f}")
print()
print(f"   TP exits:              {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
print(f"   SL exits:              {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
print(f"   TTL exits:             {ttl_exits} ({ttl_exits/total_trades*100:.1f}%)")
print()

# Top winning and losing trades
df_closed = pd.DataFrame(closed_positions)
df_closed = df_closed.sort_values('pnl', ascending=False)

print("=" * 100)
print("🏆 ТОП-5 ПРИБЫЛЬНЫХ СДЕЛОК")
print("=" * 100)
for i, (_, trade) in enumerate(df_closed.head(5).iterrows(), 1):
    print(f"{i}. {trade['time_open'].strftime('%H:%M')} | {trade['symbol']:8s} | {trade['side']:4s} | "
          f"{trade['exit_type']:3s} | PnL: ${trade['pnl']:+8.2f}")

print()
print("=" * 100)
print("💸 ТОП-5 УБЫТОЧНЫХ СДЕЛОК")
print("=" * 100)
for i, (_, trade) in enumerate(df_closed.tail(5).iterrows(), 1):
    print(f"{i}. {trade['time_open'].strftime('%H:%M')} | {trade['symbol']:8s} | {trade['side']:4s} | "
          f"{trade['exit_type']:3s} | PnL: ${trade['pnl']:+8.2f}")

# Breakdown by symbol
print()
print("=" * 100)
print("📈 СТАТИСТИКА ПО МОНЕТАМ")
print("=" * 100)
symbol_stats = {}
for pos in closed_positions:
    symbol = pos['symbol']
    if symbol not in symbol_stats:
        symbol_stats[symbol] = {'trades': 0, 'pnl': 0, 'wins': 0}
    symbol_stats[symbol]['trades'] += 1
    symbol_stats[symbol]['pnl'] += pos['pnl']
    if pos['pnl'] > 0:
        symbol_stats[symbol]['wins'] += 1

for symbol in sorted(symbol_stats.keys(), key=lambda x: symbol_stats[x]['pnl'], reverse=True):
    stats = symbol_stats[symbol]
    wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
    emoji = "✅" if stats['pnl'] > 0 else "❌"
    print(f"{emoji} {symbol:8s} | Сделок: {stats['trades']:3d} | WR: {wr:5.1f}% | PnL: ${stats['pnl']:+8.2f}")

# Compare with current config
print()
print("=" * 100)
print("📊 СРАВНЕНИЕ С ТЕКУЩЕЙ КОНФИГУРАЦИЕЙ (50x, 10% SL, Hybrid)")
print("=" * 100)

# Run simulation for current config
balance_current = INITIAL_BALANCE
closed_current = []
skipped_current = 0

for idx, signal in df_clean.iterrows():
    if len(closed_current) >= MAX_POSITIONS and skipped_current < len(df_clean) - MAX_POSITIONS:
        # This is simplified - we're assuming sequential processing
        pass
    
    if balance_current <= 0:
        break
    
    trade_size = min(POSITION_SIZE, balance_current)
    position_value = trade_size * LEVERAGE
    
    entry = signal['entry_price']
    side = signal['verdict']
    highest = signal['highest_reached']
    lowest = signal['lowest_reached']
    target_min = signal['target_min']
    target_max = signal['target_max']
    final_price = signal['final_price']
    
    # Hybrid TP (current)
    if side == 'BUY':
        tp_price = target_min
    else:
        tp_price = target_max
    
    # SL for 10%
    sl_price_change = (10 / 100) / LEVERAGE
    if side == 'BUY':
        sl_price = entry * (1 - sl_price_change)
    else:
        sl_price = entry * (1 + sl_price_change)
    
    # Check exits
    sl_hit = False
    if side == 'BUY' and not pd.isna(lowest):
        sl_hit = lowest <= sl_price
    elif side == 'SELL' and not pd.isna(highest):
        sl_hit = highest >= sl_price
    
    tp_hit = False
    if not sl_hit and not pd.isna(tp_price):
        if side == 'BUY' and not pd.isna(highest):
            tp_hit = highest >= tp_price
        elif side == 'SELL' and not pd.isna(lowest):
            tp_hit = lowest <= tp_price
    
    # Calculate PnL
    if sl_hit:
        exit_price = sl_price
        exit_type = 'SL'
    elif tp_hit:
        exit_price = tp_price
        exit_type = 'TP'
    else:
        exit_price = final_price
        exit_type = 'TTL'
    
    if side == 'BUY':
        pnl_pct = (exit_price / entry - 1) * LEVERAGE
    else:
        pnl_pct = (1 - exit_price / entry) * LEVERAGE
    
    if exit_type == 'TP':
        fees = position_value * (TAKER_FEE + MAKER_FEE)
    else:
        fees = position_value * (TAKER_FEE + TAKER_FEE)
    
    pnl = position_value * pnl_pct - fees
    balance_current += pnl
    closed_current.append(pnl)

pnl_current = balance_current - INITIAL_BALANCE
roi_current = (pnl_current / INITIAL_BALANCE) * 100
wins_current = sum(1 for p in closed_current if p > 0)
wr_current = (wins_current / len(closed_current) * 100) if len(closed_current) > 0 else 0

print(f"   Текущая (50x, 10% SL, Hybrid):      ${balance_current:.2f} | ROI {roi_current:+.1f}% | WR {wr_current:.1f}% | Сделок {len(closed_current)}")
print(f"   Новая (50x, 25% SL, Far target):    ${balance:.2f} | ROI {roi:+.1f}% | WR {win_rate:.1f}% | Сделок {total_trades}")
print()

improvement = balance - balance_current
improvement_pct = (improvement / INITIAL_BALANCE) * 100

if improvement > 0:
    print(f"   💡 Улучшение: ${improvement:+.2f} ({improvement_pct:+.1f}%)")
    print(f"   🎯 Рекомендация: ИСПОЛЬЗОВАТЬ НОВУЮ КОНФИГУРАЦИЮ")
else:
    print(f"   ⚠️ Ухудшение: ${improvement:+.2f} ({improvement_pct:+.1f}%)")
    print(f"   🎯 Рекомендация: ОСТАВИТЬ ТЕКУЩУЮ КОНФИГУРАЦИЮ")
