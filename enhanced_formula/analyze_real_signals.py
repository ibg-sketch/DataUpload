#!/usr/bin/env python3
"""
АНАЛИЗ РЕАЛЬНЫХ СИГНАЛОВ БОТА

Анализирует эффективность формул на РЕАЛЬНЫХ сигналах из effectiveness_log.csv
- Достижимость target_min и target_max
- Win rates
- Корреляция multiplier с результатами
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Загрузить данные
df = pd.read_csv('effectiveness_log.csv')

print("="*80)
print("📊 АНАЛИЗ РЕАЛЬНЫХ СИГНАЛОВ БОТА")
print("="*80)

# Базовая информация
print(f"\n📁 Всего сигналов: {len(df):,}")
print(f"   Период: {df['timestamp_sent'].min()} → {df['timestamp_sent'].max()}")

# Фильтруем только последние 7 дней
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
cutoff_date = datetime.now() - timedelta(days=7)
df_recent = df[df['timestamp_sent'] >= cutoff_date].copy()

print(f"\n🕐 Последние 7 дней: {len(df_recent):,} сигналов")
print(f"   Период: {df_recent['timestamp_sent'].min()} → {df_recent['timestamp_sent'].max()}")

# Исключаем CANCELLED сигналы
df_active = df_recent[df_recent['result'] != 'CANCELLED'].copy()
print(f"   Активные (не CANCELLED): {len(df_active):,}")

# Рассчитываем достижимость целей
df_active['target_min_hit'] = False
df_active['target_max_hit'] = False

for idx, row in df_active.iterrows():
    entry = row['entry_price']
    target_min = row['target_min']
    target_max = row['target_max']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    
    if row['verdict'] == 'BUY':
        # Для BUY: проверяем highest
        if highest >= target_min:
            df_active.at[idx, 'target_min_hit'] = True
        if highest >= target_max:
            df_active.at[idx, 'target_max_hit'] = True
    else:  # SELL
        # Для SELL: проверяем lowest
        if lowest <= target_min:
            df_active.at[idx, 'target_min_hit'] = True
        if lowest <= target_max:
            df_active.at[idx, 'target_max_hit'] = True

# Разделяем на BUY и SELL
df_buy = df_active[df_active['verdict'] == 'BUY']
df_sell = df_active[df_active['verdict'] == 'SELL']

print("\n" + "="*80)
print("📊 ОБЩАЯ СТАТИСТИКА")
print("="*80)

# Общие показатели
total_win_rate = (df_active['result'] == 'WIN').mean() * 100
total_min_hit = df_active['target_min_hit'].mean() * 100
total_max_hit = df_active['target_max_hit'].mean() * 100
avg_profit = df_active['profit_pct'].mean()

print(f"\n💰 ОБЩИЕ ПОКАЗАТЕЛИ:")
print(f"   Win Rate: {total_win_rate:.1f}%")
print(f"   Target MIN достижимость: {total_min_hit:.1f}%")
print(f"   Target MAX достижимость: {total_max_hit:.1f}%")
print(f"   Средний PnL: {avg_profit:.2f}%")

# Статистика по BUY
print(f"\n🟢 BUY СИГНАЛЫ ({len(df_buy)} шт):")
if len(df_buy) > 0:
    buy_win_rate = (df_buy['result'] == 'WIN').mean() * 100
    buy_min_hit = df_buy['target_min_hit'].mean() * 100
    buy_max_hit = df_buy['target_max_hit'].mean() * 100
    buy_avg_profit = df_buy['profit_pct'].mean()
    buy_avg_multiplier = df_buy['market_strength'].mean()
    
    # Средние target значения
    buy_avg_target_min_pct = ((df_buy['target_min'] - df_buy['entry_price']) / df_buy['entry_price'] * 100).mean()
    buy_avg_target_max_pct = ((df_buy['target_max'] - df_buy['entry_price']) / df_buy['entry_price'] * 100).mean()
    
    print(f"   Win Rate: {buy_win_rate:.1f}%")
    print(f"   Target MIN hit rate: {buy_min_hit:.1f}%")
    print(f"   Target MAX hit rate: {buy_max_hit:.1f}%")
    print(f"   Средний PnL: {buy_avg_profit:.2f}%")
    print(f"   Средний multiplier: {buy_avg_multiplier:.2f}")
    print(f"   Средний target_min: {buy_avg_target_min_pct:.2f}%")
    print(f"   Средний target_max: {buy_avg_target_max_pct:.2f}%")

# Статистика по SELL
print(f"\n🔴 SELL СИГНАЛЫ ({len(df_sell)} шт):")
if len(df_sell) > 0:
    sell_win_rate = (df_sell['result'] == 'WIN').mean() * 100
    sell_min_hit = df_sell['target_min_hit'].mean() * 100
    sell_max_hit = df_sell['target_max_hit'].mean() * 100
    sell_avg_profit = df_sell['profit_pct'].mean()
    sell_avg_multiplier = df_sell['market_strength'].mean()
    
    # Средние target значения (для SELL это расстояние вниз)
    sell_avg_target_min_pct = ((df_sell['entry_price'] - df_sell['target_min']) / df_sell['entry_price'] * 100).mean()
    sell_avg_target_max_pct = ((df_sell['entry_price'] - df_sell['target_max']) / df_sell['entry_price'] * 100).mean()
    
    print(f"   Win Rate: {sell_win_rate:.1f}%")
    print(f"   Target MIN hit rate: {sell_min_hit:.1f}%")
    print(f"   Target MAX hit rate: {sell_max_hit:.1f}%")
    print(f"   Средний PnL: {sell_avg_profit:.2f}%")
    print(f"   Средний multiplier: {sell_avg_multiplier:.2f}")
    print(f"   Средний target_min: {sell_avg_target_min_pct:.2f}%")
    print(f"   Средний target_max: {sell_avg_target_max_pct:.2f}%")

# Анализ по квартилям multiplier
print("\n" + "="*80)
print("📊 АНАЛИЗ ПО MULTIPLIER (market_strength)")
print("="*80)

df_active['multiplier_quartile'] = pd.qcut(df_active['market_strength'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')

for quartile in ['Q1', 'Q2', 'Q3', 'Q4']:
    df_q = df_active[df_active['multiplier_quartile'] == quartile]
    if len(df_q) > 0:
        q_min = df_q['market_strength'].min()
        q_max = df_q['market_strength'].max()
        q_win_rate = (df_q['result'] == 'WIN').mean() * 100
        q_min_hit = df_q['target_min_hit'].mean() * 100
        q_max_hit = df_q['target_max_hit'].mean() * 100
        q_avg_profit = df_q['profit_pct'].mean()
        
        print(f"\n{quartile} (multiplier {q_min:.2f}-{q_max:.2f}): {len(df_q)} сигналов")
        print(f"   Win Rate: {q_win_rate:.1f}%")
        print(f"   Target MIN hit: {q_min_hit:.1f}%")
        print(f"   Target MAX hit: {q_max_hit:.1f}%")
        print(f"   Avg PnL: {q_avg_profit:.2f}%")

# Анализ по монетам
print("\n" + "="*80)
print("📊 СТАТИСТИКА ПО МОНЕТАМ (топ-10 по количеству)")
print("="*80)

symbol_stats = df_active.groupby('symbol').agg({
    'result': lambda x: (x == 'WIN').mean() * 100,
    'target_min_hit': lambda x: x.mean() * 100,
    'target_max_hit': lambda x: x.mean() * 100,
    'profit_pct': 'mean',
    'market_strength': 'mean',
    'verdict': 'count'
}).rename(columns={'verdict': 'count'})

symbol_stats = symbol_stats.sort_values('count', ascending=False).head(10)

print(f"\n{'Symbol':<12} {'Count':<8} {'WR%':<8} {'MinHit%':<10} {'MaxHit%':<10} {'AvgPnL%':<10} {'Mult':<6}")
print("-" * 80)
for symbol, row in symbol_stats.iterrows():
    print(f"{symbol:<12} {int(row['count']):<8} {row['result']:<8.1f} {row['target_min_hit']:<10.1f} {row['target_max_hit']:<10.1f} {row['profit_pct']:<10.2f} {row['market_strength']:<6.2f}")

# Анализ достижимости vs результат
print("\n" + "="*80)
print("🎯 КОРРЕЛЯЦИЯ: ДОСТИЖИМОСТЬ vs РЕЗУЛЬТАТ")
print("="*80)

# Сигналы которые достигли target_min
df_min_hit = df_active[df_active['target_min_hit'] == True]
df_min_miss = df_active[df_active['target_min_hit'] == False]

print(f"\n📈 Достигли target_min ({len(df_min_hit)} сигналов):")
print(f"   Win Rate: {(df_min_hit['result'] == 'WIN').mean() * 100:.1f}%")
print(f"   Avg PnL: {df_min_hit['profit_pct'].mean():.2f}%")

print(f"\n📉 НЕ достигли target_min ({len(df_min_miss)} сигналов):")
print(f"   Win Rate: {(df_min_miss['result'] == 'WIN').mean() * 100:.1f}%")
print(f"   Avg PnL: {df_min_miss['profit_pct'].mean():.2f}%")

# Проблемные сигналы
print("\n" + "="*80)
print("⚠️ ПРОБЛЕМНЫЕ СИГНАЛЫ")
print("="*80)

# 1. Win но не достиг target_min (странно!)
df_weird_win = df_active[(df_active['result'] == 'WIN') & (df_active['target_min_hit'] == False)]
print(f"\n🤔 WIN но НЕ достиг target_min: {len(df_weird_win)} сигналов")
if len(df_weird_win) > 0:
    print(f"   Средний PnL: {df_weird_win['profit_pct'].mean():.2f}%")
    print(f"   Это означает что логика WIN не синхронизирована с target_min!")

# 2. Достиг target_min но LOSS
df_weird_loss = df_active[(df_active['result'] == 'LOSS') & (df_active['target_min_hit'] == True)]
print(f"\n🤔 Достиг target_min но LOSS: {len(df_weird_loss)} сигналов")
if len(df_weird_loss) > 0:
    print(f"   Средний PnL: {df_weird_loss['profit_pct'].mean():.2f}%")
    print(f"   Возможно ранний выход или логика WIN требует target_max?")

# Временной анализ
print("\n" + "="*80)
print("📅 ДИНАМИКА ПО ДНЯМ")
print("="*80)

df_active['date'] = df_active['timestamp_sent'].dt.date
daily_stats = df_active.groupby('date').agg({
    'result': lambda x: (x == 'WIN').mean() * 100,
    'target_min_hit': lambda x: x.mean() * 100,
    'profit_pct': 'mean',
    'verdict': 'count'
}).rename(columns={'verdict': 'count'})

print(f"\n{'Date':<15} {'Signals':<10} {'WR%':<10} {'MinHit%':<12} {'AvgPnL%':<10}")
print("-" * 60)
for date, row in daily_stats.iterrows():
    print(f"{str(date):<15} {int(row['count']):<10} {row['result']:<10.1f} {row['target_min_hit']:<12.1f} {row['profit_pct']:<10.2f}")

# Финальные выводы
print("\n" + "="*80)
print("💡 КЛЮЧЕВЫЕ ВЫВОДЫ")
print("="*80)

print(f"\n1️⃣ ОБЩАЯ ЭФФЕКТИВНОСТЬ:")
print(f"   • Win Rate: {total_win_rate:.1f}% (цель: ≥70%)")
if total_win_rate < 70:
    print(f"   ⚠️ НИЖЕ ЦЕЛИ на {70 - total_win_rate:.1f}%")
else:
    print(f"   ✅ ВЫШЕ ЦЕЛИ")

print(f"\n2️⃣ ДОСТИЖИМОСТЬ ЦЕЛЕЙ:")
print(f"   • Target MIN hit: {total_min_hit:.1f}% (цель: ≥50%)")
if total_min_hit < 50:
    print(f"   ⚠️ ЦЕЛИ СЛИШКОМ АГРЕССИВНЫЕ! Не достигаются в {100-total_min_hit:.1f}% случаев")
else:
    print(f"   ✅ Цели достижимы")

print(f"\n3️⃣ BUY vs SELL:")
if len(df_buy) > 0 and len(df_sell) > 0:
    print(f"   • BUY: {buy_win_rate:.1f}% WR, {buy_min_hit:.1f}% достижимость MIN")
    print(f"   • SELL: {sell_win_rate:.1f}% WR, {sell_min_hit:.1f}% достижимость MIN")
    
    if abs(buy_win_rate - sell_win_rate) > 10:
        print(f"   ⚠️ ДИСБАЛАНС: разница {abs(buy_win_rate - sell_win_rate):.1f}%")

print(f"\n4️⃣ РЕКОМЕНДАЦИИ:")
if total_min_hit < 50:
    print(f"   🔧 СНИЗИТЬ target_min на ~{(50/total_min_hit - 1)*100:.0f}% для достижимости 50%")
if total_max_hit < 20:
    print(f"   🔧 target_max слишком агрессивный (hit rate {total_max_hit:.1f}%)")
if total_win_rate < 70:
    print(f"   🔧 Пересмотреть логику WIN или улучшить фильтрацию сигналов")

print("\n" + "="*80)
print("✅ Анализ завершён!")
print("="*80)
