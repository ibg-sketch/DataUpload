"""
Better simulation using actual signal results with different position sizing
"""
import pandas as pd
import numpy as np

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')

# Filter today
today = '2025-11-18'
df_today = df[df['timestamp_sent'].str.startswith(today)].copy()

# Convert numeric columns
df_today['entry_price'] = pd.to_numeric(df_today['entry_price'], errors='coerce')
df_today['final_price'] = pd.to_numeric(df_today['final_price'], errors='coerce')
df_today['profit_pct'] = pd.to_numeric(df_today['profit_pct'], errors='coerce')
df_today['highest_reached'] = pd.to_numeric(df_today['highest_reached'], errors='coerce')
df_today['lowest_reached'] = pd.to_numeric(df_today['lowest_reached'], errors='coerce')

# Remove rows with missing data
df_clean = df_today.dropna(subset=['entry_price', 'final_price', 'profit_pct']).copy()

print(f"📊 Симуляция за {today}")
print(f"   💰 Депозит: $1,000")
print(f"   📦 Макс на позицию: $50")
print(f"   ✅ Чистых сигналов: {len(df_clean)}")
print()

# Test different leverage and SL combinations
configs = []

# Fees
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002

for leverage in [20, 30, 40, 50, 75, 100]:
    for sl_pct in [5, 10, 15, 20, 25]:
        
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
            position_value = trade_size * leverage
            
            entry = row['entry_price']
            final = row['final_price']
            highest = row['highest_reached']
            lowest = row['lowest_reached']
            side = row['verdict']
            
            # Calculate SL price
            sl_price_change = (sl_pct / 100) / leverage
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
            
            # Calculate PnL
            if sl_hit:
                # SL exit
                if side == 'BUY':
                    pnl_pct = (sl_price / entry - 1) * leverage
                else:
                    pnl_pct = (1 - sl_price / entry) * leverage
                
                fees = position_value * (TAKER_FEE + TAKER_FEE)
                pnl = position_value * pnl_pct - fees
                sl_exits += 1
            else:
                # Use actual result (TP or TTL)
                raw_pnl_pct = row['profit_pct'] / 100
                pnl_pct = raw_pnl_pct * leverage
                
                # Determine fee based on result
                if row['result'] == 'WIN' and abs(raw_pnl_pct) > 0.001:
                    fees = position_value * (TAKER_FEE + MAKER_FEE)  # TP
                    tp_exits += 1
                else:
                    fees = position_value * (TAKER_FEE + TAKER_FEE)  # TTL
                    ttl_exits += 1
                
                pnl = position_value * pnl_pct - fees
            
            balance += pnl
            total_pnl += pnl
            trades += 1
            
            if pnl > 0:
                wins += 1
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        roi = (total_pnl / 1000) * 100
        
        configs.append({
            'leverage': leverage,
            'sl_pct': sl_pct,
            'balance': balance,
            'pnl': total_pnl,
            'roi': roi,
            'trades': trades,
            'win_rate': win_rate,
            'tp': tp_exits,
            'sl': sl_exits,
            'ttl': ttl_exits
        })

# Convert to DataFrame
df_results = pd.DataFrame(configs)
df_results = df_results.sort_values('balance', ascending=False)

print("=" * 100)
print("🏆 ТОП-10 КОНФИГУРАЦИЙ")
print("=" * 100)

for i in range(min(10, len(df_results))):
    row = df_results.iloc[i]
    print(f"\n#{i+1}. Плечо: {int(row['leverage'])}x | SL: {int(row['sl_pct'])}%")
    print(f"   💰 Баланс: ${row['balance']:.2f}")
    print(f"   📊 PnL: ${row['pnl']:+.2f} ({row['roi']:+.1f}%)")
    print(f"   🎯 Win Rate: {row['win_rate']:.1f}% ({int(row['win_rate'] * row['trades'] / 100)}/{int(row['trades'])})")
    print(f"   📈 Выходы: TP {int(row['tp'])} ({row['tp']/row['trades']*100:.0f}%) | SL {int(row['sl'])} ({row['sl']/row['trades']*100:.0f}%) | TTL {int(row['ttl'])} ({row['ttl']/row['trades']*100:.0f}%)")

best = df_results.iloc[0]
print("\n" + "=" * 100)
print("⭐ ЛУЧШАЯ КОНФИГУРАЦИЯ")
print("=" * 100)
print(f"\n🎯 Плечо: {int(best['leverage'])}x")
print(f"🛑 Stop-Loss: {int(best['sl_pct'])}% (= {best['sl_pct']/best['leverage']:.3f}% движения цены)")
print()
print(f"💰 Результаты:")
print(f"   Начальный депозит:  $1,000.00")
print(f"   Финальный баланс:   ${best['balance']:.2f}")
print(f"   Прибыль/Убыток:     ${best['pnl']:+.2f} ({best['roi']:+.2f}%)")
print()
print(f"📊 Статистика:")
print(f"   Сделок:             {int(best['trades'])}")
print(f"   Win Rate:           {best['win_rate']:.1f}%")
print(f"   TP exits:           {int(best['tp'])} ({best['tp']/best['trades']*100:.1f}%)")
print(f"   SL exits:           {int(best['sl'])} ({best['sl']/best['trades']*100:.1f}%)")
print(f"   TTL exits:          {int(best['ttl'])} ({best['ttl']/best['trades']*100:.1f}%)")

# Current config
current = df_results[(df_results['leverage'] == 50) & (df_results['sl_pct'] == 10)]
if not current.empty:
    current = current.iloc[0]
    print()
    print("=" * 100)
    print("📊 ТЕКУЩАЯ КОНФИГУРАЦИЯ (50x, 10% SL)")
    print("=" * 100)
    print(f"   Финальный баланс:   ${current['balance']:.2f}")
    print(f"   PnL:                ${current['pnl']:+.2f} ({current['roi']:+.2f}%)")
    print(f"   Win Rate:           {current['win_rate']:.1f}%")
    print(f"   Выходы: TP {int(current['tp'])} | SL {int(current['sl'])} | TTL {int(current['ttl'])}")
    print()
    improvement = best['balance'] - current['balance']
    print(f"   💡 Улучшение: ${improvement:+.2f} ({improvement/10:.1f}%)")

# Show SL comparison for 50x leverage
print()
print("=" * 100)
print("📊 СРАВНЕНИЕ SL ДЛЯ 50x ПЛЕЧА")
print("=" * 100)
df_50x = df_results[df_results['leverage'] == 50].sort_values('sl_pct')
for _, row in df_50x.iterrows():
    sl_distance = row['sl_pct'] / row['leverage']
    print(f"SL {int(row['sl_pct']):2d}% ({sl_distance:.3f}% цены) → ${row['balance']:7.2f} | ROI {row['roi']:+6.1f}% | SL hits {int(row['sl'])}/{int(row['trades'])} ({row['sl']/row['trades']*100:.0f}%)")
