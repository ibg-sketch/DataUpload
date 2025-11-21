"""
Find optimal trading configuration for last 12 hours
Test all combinations of:
- Position management: ALL-IN vs 10 max positions
- Position size: $50 vs $100
- Leverage: 25x, 50x, 100x
- SL: 25%, 50%, 100%
"""
import pandas as pd
from datetime import datetime, timedelta
from itertools import product

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

print(f"📊 Поиск оптимальной конфигурации для последних 12 часов")
print(f"   От: {twelve_hours_ago.strftime('%Y-%m-%d %H:%M')}")
print(f"   До: {now.strftime('%Y-%m-%d %H:%M')}")
print(f"   Сигналов: {len(df_clean)}")
print()

# Constants
INITIAL_BALANCE = 1000.0
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# Test parameters
position_modes = ['ALL-IN', '10-positions']
position_sizes = [50, 100]
leverages = [25, 50, 100]
sl_percentages = [25, 50, 100]

results = []

# Test all combinations
total_combos = len(position_modes) * len(position_sizes) * len(leverages) * len(sl_percentages)
print(f"Тестирование {total_combos} конфигураций...")
print()

for pos_mode, pos_size, leverage, sl_pct in product(position_modes, position_sizes, leverages, sl_percentages):
    max_positions = 1 if pos_mode == 'ALL-IN' else 10
    
    balance = INITIAL_BALANCE
    active_positions = []
    closed_positions = []
    signals_skipped = 0
    
    for idx, signal in df_clean.iterrows():
        signal_time = signal['timestamp_sent']
        close_time = signal['timestamp_checked']
        
        # Close finished positions
        positions_to_remove = []
        for i, pos in enumerate(active_positions):
            if pos['time_close'] <= signal_time:
                # Calculate PnL
                entry = pos['entry']
                side = pos['side']
                position_value = pos['position_value']
                exit_price = pos['exit_price']
                exit_type = pos['exit_type']
                
                if side == 'BUY':
                    pnl_pct = (exit_price / entry - 1) * leverage
                else:
                    pnl_pct = (1 - exit_price / entry) * leverage
                
                if exit_type == 'TP':
                    fees = position_value * (TAKER_FEE + MAKER_FEE)
                else:
                    fees = position_value * (TAKER_FEE + TAKER_FEE)
                
                pnl = position_value * pnl_pct - fees
                balance += pnl
                
                closed_positions.append({
                    'pnl': pnl,
                    'exit_type': exit_type
                })
                positions_to_remove.append(i)
        
        for i in reversed(positions_to_remove):
            active_positions.pop(i)
        
        # Check if can open new position
        if len(active_positions) >= max_positions:
            signals_skipped += 1
            continue
        
        if balance <= 0:
            break
        
        # Open new position
        trade_size = min(pos_size, balance)
        position_value = trade_size * leverage
        
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
        sl_price_change = (sl_pct / 100) / leverage
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
            'entry': entry,
            'side': side,
            'position_value': position_value,
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
            pnl_pct = (exit_price / entry - 1) * leverage
        else:
            pnl_pct = (1 - exit_price / entry) * leverage
        
        if exit_type == 'TP':
            fees = position_value * (TAKER_FEE + MAKER_FEE)
        else:
            fees = position_value * (TAKER_FEE + TAKER_FEE)
        
        pnl = position_value * pnl_pct - fees
        balance += pnl
        
        closed_positions.append({
            'pnl': pnl,
            'exit_type': exit_type
        })
    
    # Calculate stats
    total_trades = len(closed_positions)
    if total_trades == 0:
        continue
    
    wins = sum(1 for p in closed_positions if p['pnl'] > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    tp_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TP')
    sl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'SL')
    ttl_exits = sum(1 for p in closed_positions if p['exit_type'] == 'TTL')
    
    total_pnl = balance - INITIAL_BALANCE
    roi = (total_pnl / INITIAL_BALANCE) * 100
    
    results.append({
        'mode': pos_mode,
        'size': pos_size,
        'leverage': leverage,
        'sl': sl_pct,
        'balance': balance,
        'pnl': total_pnl,
        'roi': roi,
        'trades': total_trades,
        'win_rate': win_rate,
        'tp': tp_exits,
        'sl': sl_exits,
        'ttl': ttl_exits,
        'skipped': signals_skipped
    })

# Sort by balance
df_results = pd.DataFrame(results).sort_values('balance', ascending=False)

print("=" * 110)
print("🏆 ТОП-20 КОНФИГУРАЦИЙ")
print("=" * 110)
print(f"{'#':<3} {'Mode':<13} {'Size':<5} {'Lev':<4} {'SL%':<4} | {'Balance':>12} | {'ROI':>8} | {'WR':>6} | {'Trades':>6} | {'TP':>4} {'SL':>4} {'TTL':>4}")
print("-" * 110)

for i, (_, row) in enumerate(df_results.head(20).iterrows(), 1):
    sl_price_move = (row['sl'] / 100) / row['leverage'] * 100
    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
    print(f"{emoji}{i:<2} {row['mode']:<13} ${row['size']:<4.0f} {row['leverage']:<4.0f}x {row['sl']:<4.0f}% | "
          f"${row['balance']:>11,.2f} | {row['roi']:>7.1f}% | {row['win_rate']:>5.1f}% | "
          f"{row['trades']:>6.0f} | {row['tp']:>4.0f} {row['sl']:>4.0f} {row['ttl']:>4.0f}")

# Best configuration
best = df_results.iloc[0]
print()
print("=" * 110)
print("⭐ ОПТИМАЛЬНАЯ КОНФИГУРАЦИЯ")
print("=" * 110)
print(f"   Режим позиций:     {best['mode']}")
print(f"   Размер позиции:    ${best['size']:.0f}")
print(f"   Плечо:             {best['leverage']:.0f}x")
print(f"   Stop-Loss:         {best['sl']:.0f}% позиции = {(best['sl']/100)/best['leverage']*100:.2f}% движения цены")
print(f"   Take-Profit:       Дальняя цель (target_max для BUY, target_min для SELL)")
print()
print(f"💰 Результаты:")
print(f"   Начальный депозит: ${INITIAL_BALANCE:.2f}")
print(f"   Финальный баланс:  ${best['balance']:.2f}")
print(f"   Прибыль/Убыток:    ${best['pnl']:+,.2f} ({best['roi']:+.1f}%)")
print()
print(f"📊 Статистика:")
print(f"   Сделок:            {best['trades']:.0f}")
print(f"   Win Rate:          {best['win_rate']:.1f}%")
print(f"   TP exits:          {best['tp']:.0f} ({best['tp']/best['trades']*100:.1f}%)")
print(f"   SL exits:          {best['sl']:.0f} ({best['sl']/best['trades']*100:.1f}%)")
print(f"   TTL exits:         {best['ttl']:.0f} ({best['ttl']/best['trades']*100:.1f}%)")
print(f"   Сигналов пропущено: {best['skipped']:.0f}")

# Comparison by leverage
print()
print("=" * 110)
print("📊 СРАВНЕНИЕ ПО ПЛЕЧАМ (лучшие для каждого)")
print("=" * 110)
for lev in [25, 50, 100]:
    lev_best = df_results[df_results['leverage'] == lev].iloc[0] if len(df_results[df_results['leverage'] == lev]) > 0 else None
    if lev_best is not None:
        print(f"{lev:3.0f}x | Mode: {lev_best['mode']:<13} | Size: ${lev_best['size']:.0f} | SL: {lev_best['sl']:.0f}% | "
              f"Balance: ${lev_best['balance']:>10,.2f} | ROI: {lev_best['roi']:>7.1f}% | WR: {lev_best['win_rate']:>5.1f}%")

# Comparison by position mode
print()
print("=" * 110)
print("📊 СРАВНЕНИЕ ПО РЕЖИМАМ (лучшие для каждого)")
print("=" * 110)
for mode in ['ALL-IN', '10-positions']:
    mode_best = df_results[df_results['mode'] == mode].iloc[0] if len(df_results[df_results['mode'] == mode]) > 0 else None
    if mode_best is not None:
        print(f"{mode:<13} | Lev: {mode_best['leverage']:.0f}x | Size: ${mode_best['size']:.0f} | SL: {mode_best['sl']:.0f}% | "
              f"Balance: ${mode_best['balance']:>10,.2f} | ROI: {mode_best['roi']:>7.1f}% | WR: {mode_best['win_rate']:>5.1f}%")

print()
print("=" * 110)
print("✅ АНАЛИЗ ЗАВЕРШЕН")
print("=" * 110)
