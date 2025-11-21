"""
Test different TP strategies with 50x leverage + 25% SL for last 12 hours
"""
import pandas as pd
from datetime import datetime, timedelta

# Load data
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])

# Last 12 hours
now = datetime.now()
twelve_hours_ago = now - timedelta(hours=12)
df_12h = df[df['timestamp_sent'] >= twelve_hours_ago].copy()

# Convert numeric columns
for col in ['entry_price', 'final_price', 'profit_pct', 'highest_reached', 'lowest_reached', 'target_min', 'target_max']:
    df_12h[col] = pd.to_numeric(df_12h[col], errors='coerce')

df_clean = df_12h.dropna(subset=['entry_price', 'final_price', 'profit_pct']).copy()

print(f"📊 Тест TP стратегий (50x leverage, 25% SL)")
print(f"   Последние 12 часов: {len(df_clean)} сигналов")
print()

# Fees
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

# Fixed leverage and SL
LEVERAGE = 50
SL_PCT = 25

# TP strategies to test
tp_strategies = {
    'target_min': 'Ближняя цель (консервативная)',
    'target_max': 'Дальняя цель (агрессивная)',
    'hybrid': 'Гибрид (BUY=min, SELL=max)',
    'fixed_50': 'Фиксированная 1% (50bp at 50x)',
    'fixed_75': 'Фиксированная 1.5% (75bp at 50x)',
}

results = []

for strategy_name, strategy_desc in tp_strategies.items():
    balance = 1000.0
    position_size = 50.0
    trades = 0
    total_pnl = 0
    wins = 0
    tp_exits = 0
    sl_exits = 0
    ttl_exits = 0
    
    for _, row in df_clean.iterrows():
        if balance <= 0:
            break
        
        trade_size = min(position_size, balance)
        position_value = trade_size * LEVERAGE
        
        entry = row['entry_price']
        final = row['final_price']
        highest = row['highest_reached']
        lowest = row['lowest_reached']
        side = row['verdict']
        target_min = row['target_min']
        target_max = row['target_max']
        
        # Calculate TP based on strategy
        if strategy_name == 'target_min':
            tp_price = target_min if side == 'BUY' else target_max
        elif strategy_name == 'target_max':
            tp_price = target_max if side == 'BUY' else target_min
        elif strategy_name == 'hybrid':
            tp_price = target_min if side == 'BUY' else target_max
        elif strategy_name == 'fixed_50':
            price_change = 0.01 / LEVERAGE
            tp_price = entry * (1 + price_change if side == 'BUY' else 1 - price_change)
        elif strategy_name == 'fixed_75':
            price_change = 0.015 / LEVERAGE
            tp_price = entry * (1 + price_change if side == 'BUY' else 1 - price_change)
        else:
            tp_price = target_min if side == 'BUY' else target_max
        
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
        if sl_hit:
            # SL exit
            if side == 'BUY':
                pnl_pct = (sl_price / entry - 1) * LEVERAGE
            else:
                pnl_pct = (1 - sl_price / entry) * LEVERAGE
            
            fees = position_value * (TAKER_FEE + TAKER_FEE)
            pnl = position_value * pnl_pct - fees
            sl_exits += 1
        elif tp_hit:
            # TP exit
            if side == 'BUY':
                pnl_pct = (tp_price / entry - 1) * LEVERAGE
            else:
                pnl_pct = (1 - tp_price / entry) * LEVERAGE
            
            fees = position_value * (TAKER_FEE + MAKER_FEE)
            pnl = position_value * pnl_pct - fees
            tp_exits += 1
        else:
            # TTL exit at final price
            raw_pnl_pct = row['profit_pct'] / 100
            pnl_pct = raw_pnl_pct * LEVERAGE
            
            fees = position_value * (TAKER_FEE + TAKER_FEE)
            pnl = position_value * pnl_pct - fees
            ttl_exits += 1
        
        balance += pnl
        total_pnl += pnl
        trades += 1
        
        if pnl > 0:
            wins += 1
    
    win_rate = (wins / trades * 100) if trades > 0 else 0
    roi = (total_pnl / 1000) * 100
    
    results.append({
        'strategy': strategy_name,
        'description': strategy_desc,
        'balance': balance,
        'pnl': total_pnl,
        'roi': roi,
        'trades': trades,
        'win_rate': win_rate,
        'tp': tp_exits,
        'sl': sl_exits,
        'ttl': ttl_exits,
        'tp_rate': (tp_exits / trades * 100) if trades > 0 else 0,
        'sl_rate': (sl_exits / trades * 100) if trades > 0 else 0
    })

# Sort by balance
df_results = pd.DataFrame(results).sort_values('balance', ascending=False)

print("=" * 100)
print("🏆 СРАВНЕНИЕ TP СТРАТЕГИЙ (50x leverage, 25% SL)")
print("=" * 100)

for i, row in df_results.iterrows():
    print(f"\n{'🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '  '} {row['description']}")
    print(f"   💰 Баланс: ${row['balance']:.2f}")
    print(f"   📊 PnL: ${row['pnl']:+.2f} ({row['roi']:+.1f}%)")
    print(f"   🎯 Win Rate: {row['win_rate']:.1f}% ({int(row['win_rate'] * row['trades'] / 100)}/{int(row['trades'])})")
    print(f"   📈 TP Hit Rate: {row['tp_rate']:.1f}% ({int(row['tp'])}/{int(row['trades'])})")
    print(f"   📉 SL Hit Rate: {row['sl_rate']:.1f}% ({int(row['sl'])}/{int(row['trades'])})")
    print(f"   ⏱️  TTL exits: {int(row['ttl'])} ({row['ttl']/row['trades']*100:.1f}%)")

# Best strategy
best = df_results.iloc[0]
print("\n" + "=" * 100)
print("⭐ ЛУЧШАЯ TP СТРАТЕГИЯ")
print("=" * 100)
print(f"\n🎯 Стратегия: {best['description']}")
print(f"⚙️  Leverage: 50x")
print(f"🛑 Stop-Loss: 25% (= 0.50% движения цены)")
print()
print(f"💰 Результаты:")
print(f"   Финальный баланс:  ${best['balance']:.2f}")
print(f"   Прибыль/Убыток:    ${best['pnl']:+.2f} ({best['roi']:+.2f}%)")
print()
print(f"📊 Статистика:")
print(f"   Сделок:            {int(best['trades'])}")
print(f"   Win Rate:          {best['win_rate']:.1f}%")
print(f"   TP Hit Rate:       {best['tp_rate']:.1f}%")
print(f"   SL Hit Rate:       {best['sl_rate']:.1f}%")

# Compare with hybrid
hybrid = df_results[df_results['strategy'] == 'hybrid'].iloc[0]
print()
print("=" * 100)
print(f"📊 СРАВНЕНИЕ С ТЕКУЩЕЙ (Hybrid)")
print("=" * 100)
print(f"   Hybrid:        ${hybrid['balance']:.2f} | ROI {hybrid['roi']:+.1f}% | TP {hybrid['tp_rate']:.0f}% | SL {hybrid['sl_rate']:.0f}%")
print(f"   {best['description']}: ${best['balance']:.2f} | ROI {best['roi']:+.1f}% | TP {best['tp_rate']:.0f}% | SL {best['sl_rate']:.0f}%")
print()
improvement = best['balance'] - hybrid['balance']
print(f"   💡 Улучшение: ${improvement:+.2f} ({improvement/10:.1f}%)")

# Show detailed comparison
print()
print("=" * 100)
print("📈 ДЕТАЛЬНОЕ СРАВНЕНИЕ ВСЕХ СТРАТЕГИЙ")
print("=" * 100)
print(f"{'Стратегия':<35} | {'Баланс':>10} | {'ROI':>8} | {'TP Rate':>8} | {'SL Rate':>8}")
print("-" * 100)
for _, row in df_results.iterrows():
    print(f"{row['description']:<35} | ${row['balance']:>9.2f} | {row['roi']:>7.1f}% | {row['tp_rate']:>7.1f}% | {row['sl_rate']:>7.1f}%")
