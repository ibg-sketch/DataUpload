"""
Simulate trading for today (Nov 18, 2025) with $1000 deposit and max $50 per position
Find optimal leverage, SL, and TP combination
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

# Load signals
df_signals = pd.read_csv('signals_log.csv')

# Filter today's signals
today = '2025-11-18'
df_today = df_signals[df_signals['timestamp'].str.startswith(today)].copy()

print(f"📊 Симуляция торговли за {today}")
print(f"   💰 Начальный депозит: $1,000")
print(f"   📦 Максимум на позицию: $50")
print(f"   📈 Сигналов за день: {len(df_today)}")
print()

# Parse timestamps
df_today['start_time'] = pd.to_datetime(df_today['timestamp'])
df_today['entry_price'] = pd.to_numeric(df_today['entry_price'], errors='coerce')
df_today['target_min'] = pd.to_numeric(df_today['target_min'], errors='coerce')
df_today['target_max'] = pd.to_numeric(df_today['target_max'], errors='coerce')

# Load effectiveness log to get actual outcomes
df_eff = pd.read_csv('effectiveness_log.csv')
df_eff['timestamp_sent'] = pd.to_datetime(df_eff['timestamp_sent'])

# Merge with signals to get outcomes
df_today = df_today.merge(
    df_eff[['timestamp_sent', 'symbol', 'verdict', 'result', 'final_price', 'highest_reached', 'lowest_reached']],
    left_on=['start_time', 'symbol', 'verdict'],
    right_on=['timestamp_sent', 'symbol', 'verdict'],
    how='left'
)

# Filter only completed signals
df_completed = df_today[df_today['result'].notna()].copy()

print(f"   ✅ Завершённых сигналов: {len(df_completed)}")
print()

# Test configurations
configs = []

# Leverage options: 20x, 30x, 50x, 75x, 100x
# SL options: 5%, 10%, 15%, 20%
# TP strategies: target_min, hybrid, fixed_50, fixed_75

for leverage in [20, 30, 50, 75, 100]:
    for sl_pct in [5, 10, 15, 20]:
        for tp_strategy in ['target_min', 'hybrid', 'fixed_50', 'fixed_75']:
            configs.append({
                'leverage': leverage,
                'sl_pct': sl_pct,
                'tp_strategy': tp_strategy
            })

# Fee structure
TAKER_FEE = 0.0005  # 0.05%
MAKER_FEE = 0.0002  # 0.02%

def simulate_trade(row, leverage, sl_pct, tp_strategy, position_size):
    """Simulate a single trade"""
    entry_price = row['entry_price']
    final_price = row['final_price']
    side = row['verdict']
    result = row['result']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    
    if pd.isna(entry_price) or pd.isna(final_price):
        return 0, 0, None
    
    # Calculate TP price based on strategy
    if tp_strategy == 'target_min':
        tp_price = row['target_min'] if side == 'BUY' else row['target_max']
    elif tp_strategy == 'hybrid':
        tp_price = row['target_min'] if side == 'BUY' else row['target_max']
    elif tp_strategy == 'fixed_50':
        price_change = 0.01 / leverage
        tp_price = entry_price * (1 + price_change if side == 'BUY' else 1 - price_change)
    elif tp_strategy == 'fixed_75':
        price_change = 0.015 / leverage
        tp_price = entry_price * (1 + price_change if side == 'BUY' else 1 - price_change)
    else:
        tp_price = row['target_min']
    
    # Calculate SL price
    sl_price_change = (sl_pct / 100) / leverage
    if side == 'BUY':
        sl_price = entry_price * (1 - sl_price_change)
    else:
        sl_price = entry_price * (1 + sl_price_change)
    
    # Determine actual exit
    position_value = position_size * leverage
    
    # Check if price reached SL or TP during the trade using highest/lowest
    if side == 'BUY':
        # Check lowest price first (SL)
        if not pd.isna(lowest) and lowest <= sl_price:
            # SL hit
            pnl_pct = (sl_price / entry_price - 1) * leverage
            fees = position_value * (TAKER_FEE + TAKER_FEE)  # Both taker
            pnl = position_value * pnl_pct - fees
            return pnl, -1, 'SL'
        elif not pd.isna(highest) and highest >= tp_price:
            # TP hit
            pnl_pct = (tp_price / entry_price - 1) * leverage
            fees = position_value * (TAKER_FEE + MAKER_FEE)
            pnl = position_value * pnl_pct - fees
            return pnl, 1, 'TP'
        else:
            # TTL exit at final price
            pnl_pct = (final_price / entry_price - 1) * leverage
            fees = position_value * (TAKER_FEE + TAKER_FEE)
            pnl = position_value * pnl_pct - fees
            return pnl, 0, 'TTL'
    else:  # SELL
        # Check highest price first (SL for SELL)
        if not pd.isna(highest) and highest >= sl_price:
            # SL hit
            pnl_pct = (1 - sl_price / entry_price) * leverage
            fees = position_value * (TAKER_FEE + TAKER_FEE)
            pnl = position_value * pnl_pct - fees
            return pnl, -1, 'SL'
        elif not pd.isna(lowest) and lowest <= tp_price:
            # TP hit
            pnl_pct = (1 - tp_price / entry_price) * leverage
            fees = position_value * (TAKER_FEE + MAKER_FEE)
            pnl = position_value * pnl_pct - fees
            return pnl, 1, 'TP'
        else:
            # TTL exit at final price
            pnl_pct = (1 - final_price / entry_price) * leverage
            fees = position_value * (TAKER_FEE + TAKER_FEE)
            pnl = position_value * pnl_pct - fees
            return pnl, 0, 'TTL'

# Simulate all configurations
results = []

for config in configs:
    leverage = config['leverage']
    sl_pct = config['sl_pct']
    tp_strategy = config['tp_strategy']
    
    balance = 1000.0
    position_size = 50.0
    total_pnl = 0
    trades = 0
    wins = 0
    losses = 0
    tp_count = 0
    sl_count = 0
    ttl_count = 0
    
    for _, row in df_completed.iterrows():
        if balance <= 0:
            break
        
        # Use min of $50 or remaining balance
        trade_size = min(position_size, balance)
        
        pnl, result, exit_type = simulate_trade(row, leverage, sl_pct, tp_strategy, trade_size)
        
        balance += pnl
        total_pnl += pnl
        trades += 1
        
        if exit_type == 'TP':
            tp_count += 1
        elif exit_type == 'SL':
            sl_count += 1
        elif exit_type == 'TTL':
            ttl_count += 1
        
        if pnl > 0:
            wins += 1
        else:
            losses += 1
    
    win_rate = (wins / trades * 100) if trades > 0 else 0
    
    results.append({
        'leverage': leverage,
        'sl_pct': sl_pct,
        'tp_strategy': tp_strategy,
        'final_balance': balance,
        'total_pnl': total_pnl,
        'trades': trades,
        'win_rate': win_rate,
        'tp_count': tp_count,
        'sl_count': sl_count,
        'ttl_count': ttl_count,
        'roi': (total_pnl / 1000) * 100
    })

# Convert to DataFrame and sort by final balance
df_results = pd.DataFrame(results)
df_results = df_results.sort_values('final_balance', ascending=False)

# Show top 10 configurations
print("=" * 100)
print("🏆 ТОП-10 КОНФИГУРАЦИЙ")
print("=" * 100)

for i, row in df_results.head(10).iterrows():
    print(f"\n#{df_results.index.get_loc(i) + 1}. Плечо: {row['leverage']}x | SL: {row['sl_pct']}% | TP: {row['tp_strategy']}")
    print(f"   💰 Финальный баланс: ${row['final_balance']:.2f}")
    print(f"   📊 PnL: ${row['total_pnl']:+.2f} ({row['roi']:+.1f}%)")
    print(f"   🎯 Win Rate: {row['win_rate']:.1f}% ({int(row['win_rate'] * row['trades'] / 100)}/{int(row['trades'])})")
    print(f"   📈 Выходы: TP {row['tp_count']} | SL {row['sl_count']} | TTL {row['ttl_count']}")

print("\n" + "=" * 100)
print("⭐ ЛУЧШАЯ КОНФИГУРАЦИЯ")
print("=" * 100)

best = df_results.iloc[0]
print(f"\n🎯 Плечо: {int(best['leverage'])}x")
print(f"🛑 Stop-Loss: {int(best['sl_pct'])}%")
print(f"💎 TP Strategy: {best['tp_strategy']}")
print()
print(f"💰 Результаты:")
print(f"   Начальный депозит: $1,000.00")
print(f"   Финальный баланс:  ${best['final_balance']:.2f}")
print(f"   Прибыль/Убыток:    ${best['total_pnl']:+.2f} ({best['roi']:+.1f}%)")
print()
print(f"📊 Статистика:")
print(f"   Всего сделок:      {int(best['trades'])}")
print(f"   Win Rate:          {best['win_rate']:.1f}%")
print(f"   Прибыльных:        {int(best['win_rate'] * best['trades'] / 100)}")
print(f"   Убыточных:         {int(best['trades'] - best['win_rate'] * best['trades'] / 100)}")
print()
print(f"📈 Распределение выходов:")
print(f"   🎯 Take-Profit:    {int(best['tp_count'])} ({best['tp_count']/best['trades']*100:.1f}%)")
print(f"   🛑 Stop-Loss:      {int(best['sl_count'])} ({best['sl_count']/best['trades']*100:.1f}%)")
print(f"   ⏱️  TTL Expired:    {int(best['ttl_count'])} ({best['ttl_count']/best['trades']*100:.1f}%)")
print()

# Show comparison with current config (50x, 10% SL, hybrid)
current = df_results[(df_results['leverage'] == 50) & 
                     (df_results['sl_pct'] == 10) & 
                     (df_results['tp_strategy'] == 'hybrid')]

if not current.empty:
    current = current.iloc[0]
    print("=" * 100)
    print("📊 СРАВНЕНИЕ С ТЕКУЩЕЙ КОНФИГУРАЦИЕЙ (50x, 10% SL, hybrid)")
    print("=" * 100)
    print(f"   Финальный баланс:  ${current['final_balance']:.2f}")
    print(f"   PnL:               ${current['total_pnl']:+.2f} ({current['roi']:+.1f}%)")
    print(f"   Win Rate:          {current['win_rate']:.1f}%")
    print(f"   Выходы: TP {int(current['tp_count'])} | SL {int(current['sl_count'])} | TTL {int(current['ttl_count'])}")
    print()
    
    improvement = best['final_balance'] - current['final_balance']
    print(f"   💡 Улучшение: ${improvement:+.2f} ({improvement/10:.1f}%)")
