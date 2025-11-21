"""
Analyze TTL exits in detail for optimal configuration
"""
import pandas as pd
from datetime import datetime, timedelta

# Load data
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df['timestamp_checked'] = pd.to_datetime(df['timestamp_checked'])

# Last 12 hours
now = datetime.now()
twelve_hours_ago = now - timedelta(hours=12)
df_12h = df[df['timestamp_sent'] >= twelve_hours_ago].copy()

# Convert numeric columns
for col in ['entry_price', 'final_price', 'profit_pct', 'highest_reached', 'lowest_reached', 'target_min', 'target_max']:
    df_12h[col] = pd.to_numeric(df_12h[col], errors='coerce')

df_clean = df_12h.dropna(subset=['entry_price', 'final_price', 'profit_pct', 'timestamp_sent', 'timestamp_checked']).copy()
df_clean = df_clean.sort_values('timestamp_sent').reset_index(drop=True)

# Optimal configuration
INITIAL_BALANCE = 1000.0
MAX_POSITIONS = 10
POSITION_SIZE = 100
LEVERAGE = 100
SL_PCT = 13
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

print(f"📊 Детальный анализ TTL exits для оптимальной конфигурации")
print(f"   Конфигурация: 10 позиций, $100, 100x, SL 13%")
print()

balance = INITIAL_BALANCE
active_positions = []
closed_positions = []
signals_skipped = 0

# Track TTL details
ttl_wins = []
ttl_losses = []

for idx, signal in df_clean.iterrows():
    signal_time = signal['timestamp_sent']
    close_time = signal['timestamp_checked']
    
    # Close finished positions
    positions_to_remove = []
    for i, pos in enumerate(active_positions):
        if pos['time_close'] <= signal_time:
            entry = pos['entry']
            side = pos['side']
            position_value = pos['position_value']
            exit_price = pos['exit_price']
            exit_type = pos['exit_type']
            
            if side == 'BUY':
                pnl_pct = (exit_price / entry - 1) * LEVERAGE
            else:
                pnl_pct = (1 - exit_price / entry) * LEVERAGE
            
            if exit_type == 'TP':
                fees = position_value * (TAKER_FEE + MAKER_FEE)
            else:
                fees = position_value * (TAKER_FEE + TAKER_FEE)
            
            pnl = position_value * pnl_pct - fees
            balance += pnl
            
            closed_positions.append({
                'symbol': pos['symbol'],
                'side': side,
                'pnl': pnl,
                'exit_type': exit_type,
                'time': pos['time_open']
            })
            
            # Track TTL
            if exit_type == 'TTL':
                ttl_data = {
                    'symbol': pos['symbol'],
                    'side': side,
                    'pnl': pnl,
                    'time': pos['time_open']
                }
                if pnl > 0:
                    ttl_wins.append(ttl_data)
                else:
                    ttl_losses.append(ttl_data)
            
            positions_to_remove.append(i)
    
    for i in reversed(positions_to_remove):
        active_positions.pop(i)
    
    # Check if can open new position
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
    
    # Far target TP
    if side == 'BUY':
        tp_price = target_max
    else:
        tp_price = target_min
    
    # Calculate SL
    sl_price_change = (SL_PCT / 100) / LEVERAGE
    if side == 'BUY':
        sl_price = entry * (1 - sl_price_change)
    else:
        sl_price = entry * (1 + sl_price_change)
    
    # Check exit
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
    
    if sl_hit:
        exit_type = 'SL'
        exit_price = sl_price
    elif tp_hit:
        exit_type = 'TP'
        exit_price = tp_price
    else:
        exit_type = 'TTL'
        exit_price = signal['final_price']
    
    position = {
        'symbol': signal['symbol'],
        'entry': entry,
        'side': side,
        'position_value': position_value,
        'time_open': signal_time,
        'time_close': close_time,
        'exit_type': exit_type,
        'exit_price': exit_price
    }
    
    active_positions.append(position)

# Close remaining positions
for pos in active_positions:
    entry = pos['entry']
    side = pos['side']
    position_value = pos['position_value']
    exit_price = pos['exit_price']
    exit_type = pos['exit_type']
    
    if side == 'BUY':
        pnl_pct = (exit_price / entry - 1) * LEVERAGE
    else:
        pnl_pct = (1 - exit_price / entry) * LEVERAGE
    
    if exit_type == 'TP':
        fees = position_value * (TAKER_FEE + MAKER_FEE)
    else:
        fees = position_value * (TAKER_FEE + TAKER_FEE)
    
    pnl = position_value * pnl_pct - fees
    balance += pnl
    
    closed_positions.append({
        'symbol': pos['symbol'],
        'side': side,
        'pnl': pnl,
        'exit_type': exit_type,
        'time': pos['time_open']
    })
    
    # Track TTL
    if exit_type == 'TTL':
        ttl_data = {
            'symbol': pos['symbol'],
            'side': side,
            'pnl': pnl,
            'time': pos['time_open']
        }
        if pnl > 0:
            ttl_wins.append(ttl_data)
        else:
            ttl_losses.append(ttl_data)

# Calculate overall stats
total_trades = len(closed_positions)
wins = sum(1 for p in closed_positions if p['pnl'] > 0)
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

tp_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TP')
sl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'SL')
ttl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TTL')

total_pnl = balance - INITIAL_BALANCE
roi = (total_pnl / INITIAL_BALANCE) * 100

print("=" * 100)
print("💰 ОБЩИЕ РЕЗУЛЬТАТЫ")
print("=" * 100)
print(f"   Финальный баланс:  ${balance:,.2f}")
print(f"   ROI:               {roi:+.1f}%")
print(f"   Сделок:            {total_trades}")
print(f"   Win Rate:          {win_rate:.1f}%")
print()
print(f"   TP exits:          {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
print(f"   SL exits:          {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
print(f"   TTL exits:         {ttl_exits} ({ttl_exits/total_trades*100:.1f}%)")
print()

# TTL analysis
ttl_total = len(ttl_wins) + len(ttl_losses)
ttl_win_count = len(ttl_wins)
ttl_loss_count = len(ttl_losses)
ttl_wr = (ttl_win_count / ttl_total * 100) if ttl_total > 0 else 0

ttl_total_pnl = sum(t['pnl'] for t in ttl_wins) + sum(t['pnl'] for t in ttl_losses)
ttl_wins_pnl = sum(t['pnl'] for t in ttl_wins)
ttl_losses_pnl = sum(t['pnl'] for t in ttl_losses)

ttl_avg_win = ttl_wins_pnl / ttl_win_count if ttl_win_count > 0 else 0
ttl_avg_loss = ttl_losses_pnl / ttl_loss_count if ttl_loss_count > 0 else 0

print("=" * 100)
print("⏱️  ДЕТАЛЬНАЯ СТАТИСТИКА TTL EXITS")
print("=" * 100)
print(f"   Всего TTL exits:       {ttl_total}")
print(f"   TTL в плюсе (WIN):     {ttl_win_count} ({ttl_wr:.1f}%)")
print(f"   TTL в минусе (LOSS):   {ttl_loss_count} ({100-ttl_wr:.1f}%)")
print()
print(f"   Общий PnL от TTL:      ${ttl_total_pnl:+,.2f}")
print(f"   PnL от TTL WIN:        ${ttl_wins_pnl:+,.2f}")
print(f"   PnL от TTL LOSS:       ${ttl_losses_pnl:+,.2f}")
print()
print(f"   Средний TTL WIN:       ${ttl_avg_win:+.2f}")
print(f"   Средний TTL LOSS:      ${ttl_avg_loss:+.2f}")
print()

# TTL contribution to total profit
ttl_contribution = (ttl_total_pnl / total_pnl * 100) if total_pnl != 0 else 0
print(f"   Вклад TTL в общую прибыль: {ttl_contribution:.1f}%")
print()

# Breakdown by exit type
print("=" * 100)
print("📊 ВКЛАД КАЖДОГО ТИПА ВЫХОДА В ОБЩУЮ ПРИБЫЛЬ")
print("=" * 100)

tp_pnl = sum(p['pnl'] for p in closed_positions if p['exit_type'] == 'TP')
sl_pnl = sum(p['pnl'] for p in closed_positions if p['exit_type'] == 'SL')

tp_contribution = (tp_pnl / total_pnl * 100) if total_pnl != 0 else 0
sl_contribution = (sl_pnl / total_pnl * 100) if total_pnl != 0 else 0

print(f"   TP exits ({tp_exits} сделок):   ${tp_pnl:+,.2f} ({tp_contribution:+.1f}%)")
print(f"   SL exits ({sl_exits} сделок):   ${sl_pnl:+,.2f} ({sl_contribution:+.1f}%)")
print(f"   TTL exits ({ttl_total} сделок): ${ttl_total_pnl:+,.2f} ({ttl_contribution:+.1f}%)")
print()
print(f"   ИТОГО: ${total_pnl:+,.2f} (100%)")
print()

# Show top TTL wins
print("=" * 100)
print("🏆 ТОП-10 ЛУЧШИХ TTL EXITS")
print("=" * 100)
ttl_wins_sorted = sorted(ttl_wins, key=lambda x: x['pnl'], reverse=True)
for i, trade in enumerate(ttl_wins_sorted[:10], 1):
    print(f"{i:2d}. {trade['time'].strftime('%H:%M')} | {trade['symbol']:8s} | {trade['side']:4s} | PnL: ${trade['pnl']:+8.2f}")

print()
print("=" * 100)
print("💸 ТОП-10 ХУДШИХ TTL EXITS")
print("=" * 100)
ttl_losses_sorted = sorted(ttl_losses, key=lambda x: x['pnl'])
for i, trade in enumerate(ttl_losses_sorted[:10], 1):
    print(f"{i:2d}. {trade['time'].strftime('%H:%M')} | {trade['symbol']:8s} | {trade['side']:4s} | PnL: ${trade['pnl']:+8.2f}")

# TTL by symbol
print()
print("=" * 100)
print("📈 TTL EXITS ПО МОНЕТАМ")
print("=" * 100)

ttl_by_symbol = {}
for t in ttl_wins + ttl_losses:
    symbol = t['symbol']
    if symbol not in ttl_by_symbol:
        ttl_by_symbol[symbol] = {'count': 0, 'wins': 0, 'pnl': 0}
    ttl_by_symbol[symbol]['count'] += 1
    ttl_by_symbol[symbol]['pnl'] += t['pnl']
    if t['pnl'] > 0:
        ttl_by_symbol[symbol]['wins'] += 1

for symbol in sorted(ttl_by_symbol.keys(), key=lambda x: ttl_by_symbol[x]['pnl'], reverse=True):
    stats = ttl_by_symbol[symbol]
    wr = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
    emoji = "✅" if stats['pnl'] > 0 else "❌"
    print(f"{emoji} {symbol:8s} | TTL: {stats['count']:3d} | WR: {wr:5.1f}% | PnL: ${stats['pnl']:+8.2f}")

print()
print("=" * 100)
print("✅ ВЫВОД: TTL EXITS ПОЛНОСТЬЮ УЧИТЫВАЛИСЬ В РАСЧЕТАХ")
print("=" * 100)
