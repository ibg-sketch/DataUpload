#!/usr/bin/env python3
"""
МАТЕМАТИЧЕСКИЙ АНАЛИЗ ВЗАИМОСВЯЗИ ФОРМУЛ С ДВИЖЕНИЯМИ ЦЕН

Проверяет математическую предсказательную силу формул:
1. Корреляция ATR с реальными движениями
2. Корреляция multiplier с достижимостью целей
3. Точность предсказания направления и величины движения
"""

import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta

# Загрузить данные
df = pd.read_csv('effectiveness_log.csv')

print("="*80)
print("📐 МАТЕМАТИЧЕСКИЙ АНАЛИЗ ВЗАИМОСВЯЗИ ФОРМУЛ С ДВИЖЕНИЯМИ")
print("="*80)

# Фильтр последних 7 дней и только активные
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
cutoff_date = datetime.now() - timedelta(days=7)
df = df[df['timestamp_sent'] >= cutoff_date].copy()
df = df[df['result'] != 'CANCELLED'].copy()

print(f"\n📊 Анализируем {len(df)} активных сигналов за последние 7 дней")

# Рассчитываем реальные движения цены
df['real_move_pct'] = df.apply(lambda row: (
    ((row['highest_reached'] - row['entry_price']) / row['entry_price'] * 100)
    if row['verdict'] == 'BUY'
    else ((row['entry_price'] - row['lowest_reached']) / row['entry_price'] * 100)
), axis=1)

# Рассчитываем предсказанные цели (ИСПРАВЛЕННЫЕ для SELL!)
df['predicted_min_pct'] = df.apply(lambda row: (
    ((row['target_min'] - row['entry_price']) / row['entry_price'] * 100)
    if row['verdict'] == 'BUY'
    else ((row['entry_price'] - row['target_min']) / row['entry_price'] * 100)
), axis=1)

df['predicted_max_pct'] = df.apply(lambda row: (
    ((row['target_max'] - row['entry_price']) / row['entry_price'] * 100)
    if row['verdict'] == 'BUY'
    else ((row['entry_price'] - row['target_max']) / row['entry_price'] * 100)
), axis=1)

# Убедимся, что predicted_min < predicted_max (после исправления бага)
print("\n🔍 ПРОВЕРКА ПОСЛЕ ИСПРАВЛЕНИЯ БАГА:")
invalid_targets = df[df['predicted_min_pct'] > df['predicted_max_pct']]
print(f"   Сигналы с MIN > MAX: {len(invalid_targets)} из {len(df)}")
if len(invalid_targets) > 0:
    print(f"   ⚠️ ОШИБКА ВСЁ ЕЩЁ СУЩЕСТВУЕТ! (используются старые данные)")
    print(f"   Эти данные были созданы ДО исправления бага.")
else:
    print(f"   ✅ Все цели корректны (данные после исправления)")

print("\n" + "="*80)
print("1️⃣ КОРРЕЛЯЦИЯ: ФОРМУЛА vs РЕАЛЬНОЕ ДВИЖЕНИЕ")
print("="*80)

# 1.1 Корреляция predicted_min с real_move
corr_min, p_min = stats.pearsonr(df['predicted_min_pct'], df['real_move_pct'])
print(f"\n📊 Predicted MIN vs Real Move:")
print(f"   Корреляция (Pearson r): {corr_min:.3f}")
print(f"   P-value: {p_min:.6f}")
if p_min < 0.05:
    print(f"   ✅ СТАТИСТИЧЕСКИ ЗНАЧИМА!")
else:
    print(f"   ❌ НЕ значима (p > 0.05)")

if corr_min > 0.5:
    print(f"   💡 Сильная положительная связь - формула ПРЕДСКАЗЫВАЕТ!")
elif corr_min > 0.3:
    print(f"   💡 Умеренная связь - формула частично предсказывает")
else:
    print(f"   ⚠️ Слабая связь - формула плохо предсказывает")

# 1.2 Точность предсказания (насколько близко к реальности)
df['prediction_error'] = df['predicted_min_pct'] - df['real_move_pct']
mean_error = df['prediction_error'].mean()
median_error = df['prediction_error'].median()
mae = df['prediction_error'].abs().mean()  # Mean Absolute Error

print(f"\n📐 ТОЧНОСТЬ ПРЕДСКАЗАНИЯ:")
print(f"   Средняя ошибка: {mean_error:.3f}%")
print(f"   Медианная ошибка: {median_error:.3f}%")
print(f"   MAE (средняя абсолютная): {mae:.3f}%")

if abs(mean_error) < 0.1:
    print(f"   ✅ Формула ОЧЕНЬ ТОЧНАЯ (смещение <0.1%)")
elif abs(mean_error) < 0.2:
    print(f"   ✅ Формула ТОЧНАЯ (смещение <0.2%)")
else:
    if mean_error > 0:
        print(f"   ⚠️ Формула ПЕРЕОЦЕНИВАЕТ движение на {mean_error:.2f}%")
    else:
        print(f"   ⚠️ Формула НЕДООЦЕНИВАЕТ движение на {abs(mean_error):.2f}%")

# 1.3 Квартильный анализ: формула предсказывает сильнее в разных диапазонах?
df['predicted_quartile'] = pd.qcut(df['predicted_min_pct'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')

print(f"\n📊 ТОЧНОСТЬ ПО КВАРТИЛЯМ ПРЕДСКАЗАНИЙ:")
for q in ['Q1', 'Q2', 'Q3', 'Q4']:
    df_q = df[df['predicted_quartile'] == q]
    if len(df_q) > 0:
        q_min_pred = df_q['predicted_min_pct'].mean()
        q_real = df_q['real_move_pct'].mean()
        q_error = df_q['prediction_error'].mean()
        
        print(f"   {q}: Predicted={q_min_pred:.2f}%, Real={q_real:.2f}%, Error={q_error:.2f}%")

print("\n" + "="*80)
print("2️⃣ MULTIPLIER: МАТЕМАТИЧЕСКАЯ РОЛЬ")
print("="*80)

# 2.1 Корреляция multiplier с реальным движением
corr_mult_real, p_mult_real = stats.pearsonr(df['market_strength'], df['real_move_pct'])
print(f"\n📊 Multiplier vs Real Move:")
print(f"   Корреляция: {corr_mult_real:.3f} (p={p_mult_real:.4f})")

if corr_mult_real > 0:
    print(f"   {'✅' if p_mult_real < 0.05 else '⚠️'} Положительная связь: больший multiplier → большее движение")
else:
    print(f"   {'✅' if p_mult_real < 0.05 else '⚠️'} Отрицательная связь: больший multiplier → меньшее движение")

# 2.2 Multiplier vs достижимость target_min
df['target_min_hit'] = df.apply(lambda row: (
    row['highest_reached'] >= row['target_min']
    if row['verdict'] == 'BUY'
    else row['lowest_reached'] <= row['target_min']
), axis=1)

mult_bins = pd.cut(df['market_strength'], bins=5)
mult_hit_rate = df.groupby(mult_bins)['target_min_hit'].agg(['mean', 'count'])

print(f"\n📊 Достижимость TARGET_MIN по диапазонам Multiplier:")
print(f"   {'Multiplier Range':<25} {'Hit Rate':>10} {'Count':>8}")
print("-" * 50)
for idx, row in mult_hit_rate.iterrows():
    print(f"   {str(idx):<25} {row['mean']*100:>9.1f}% {int(row['count']):>8}")

print("\n" + "="*80)
print("3️⃣ НАПРАВЛЕННАЯ ТОЧНОСТЬ (BUY vs SELL)")
print("="*80)

for verdict in ['BUY', 'SELL']:
    df_v = df[df['verdict'] == verdict]
    if len(df_v) > 0:
        corr, p_val = stats.pearsonr(df_v['predicted_min_pct'], df_v['real_move_pct'])
        mean_pred = df_v['predicted_min_pct'].mean()
        mean_real = df_v['real_move_pct'].mean()
        error = df_v['prediction_error'].mean()
        
        print(f"\n🔹 {verdict} ({len(df_v)} сигналов):")
        print(f"   Корреляция: {corr:.3f} (p={p_val:.4f})")
        print(f"   Среднее predicted: {mean_pred:.3f}%")
        print(f"   Среднее реальное: {mean_real:.3f}%")
        print(f"   Ошибка: {error:.3f}%")
        
        if abs(error) < 0.15:
            print(f"   ✅ Отличная калибровка!")
        elif abs(error) < 0.30:
            print(f"   ⚠️ Приемлемая калибровка")
        else:
            print(f"   ❌ Плохая калибровка - требует корректировки")

print("\n" + "="*80)
print("4️⃣ ПРЕДСКАЗАТЕЛЬНАЯ СИЛА ФОРМУЛЫ")
print("="*80)

# R² (coefficient of determination) - насколько формула объясняет вариацию
slope, intercept, r_value, p_value, std_err = stats.linregress(df['predicted_min_pct'], df['real_move_pct'])
r_squared = r_value ** 2

print(f"\n📊 LINEAR REGRESSION: Real = a × Predicted + b")
print(f"   Slope (a): {slope:.3f}")
print(f"   Intercept (b): {intercept:.3f}")
print(f"   R² (коэффициент детерминации): {r_squared:.3f}")
print(f"   P-value: {p_value:.6f}")

print(f"\n💡 ИНТЕРПРЕТАЦИЯ R²:")
if r_squared > 0.7:
    print(f"   ✅ ОТЛИЧНАЯ предсказательная сила ({r_squared*100:.1f}% вариации объяснено)")
elif r_squared > 0.5:
    print(f"   ✅ ХОРОШАЯ предсказательная сила ({r_squared*100:.1f}% вариации объяснено)")
elif r_squared > 0.3:
    print(f"   ⚠️ УМЕРЕННАЯ предсказательная сила ({r_squared*100:.1f}% вариации объяснено)")
else:
    print(f"   ❌ СЛАБАЯ предсказательная сила ({r_squared*100:.1f}% вариации объяснено)")

print(f"\n💡 SLOPE АНАЛИЗ:")
if 0.9 <= slope <= 1.1:
    print(f"   ✅ Идеально откалиброванная формула (slope ≈ 1.0)")
elif slope > 1.1:
    print(f"   ⚠️ Формула НЕДООЦЕНИВАЕТ: реальное движение на {(slope-1)*100:.1f}% больше")
else:
    print(f"   ⚠️ Формула ПЕРЕОЦЕНИВАЕТ: реальное движение на {(1-slope)*100:.1f}% меньше")

print("\n" + "="*80)
print("5️⃣ ВЫБРОСЫ И АНОМАЛИИ")
print("="*80)

# Найти сигналы с экстремальными ошибками
extreme_threshold = df['prediction_error'].abs().quantile(0.90)  # Топ 10% по ошибке
df_extreme = df[df['prediction_error'].abs() >= extreme_threshold]

print(f"\n⚠️ Топ-10% ЭКСТРЕМАЛЬНЫХ ОШИБОК (>{extreme_threshold:.2f}%):")
print(f"   Количество: {len(df_extreme)}")
print(f"   Средняя ошибка: {df_extreme['prediction_error'].mean():.2f}%")
print(f"   Средний multiplier: {df_extreme['market_strength'].mean():.2f}")

# Проверка на систематические ошибки по монетам
print(f"\n📊 ОШИБКИ ПО МОНЕТАМ:")
symbol_errors = df.groupby('symbol').agg({
    'prediction_error': ['mean', 'std', 'count']
}).round(3)
symbol_errors.columns = ['Mean Error', 'Std Dev', 'Count']
symbol_errors = symbol_errors[symbol_errors['Count'] >= 5].sort_values('Mean Error', ascending=False)

print(f"\n{'Symbol':<12} {'Mean Error':>12} {'Std Dev':>10} {'Count':>8}")
print("-" * 50)
for symbol, row in symbol_errors.head(10).iterrows():
    print(f"{symbol:<12} {row['Mean Error']:>11.3f}% {row['Std Dev']:>9.3f}% {int(row['Count']):>8}")

print("\n" + "="*80)
print("💡 ФИНАЛЬНЫЕ ВЫВОДЫ")
print("="*80)

print(f"\n1️⃣ МАТЕМАТИЧЕСКАЯ СВЯЗЬ:")
print(f"   • Корреляция формулы с реальностью: {corr_min:.3f}")
if corr_min > 0.5 and p_min < 0.001:
    print(f"   ✅ СИЛЬНАЯ и СТАТИСТИЧЕСКИ ЗНАЧИМАЯ связь")
    print(f"   ✅ Формула ДЕЙСТВИТЕЛЬНО предсказывает движение цены!")
elif corr_min > 0.3:
    print(f"   ⚠️ УМЕРЕННАЯ связь - формула частично работает")
else:
    print(f"   ❌ СЛАБАЯ связь - формула не предсказывает надёжно")

print(f"\n2️⃣ ТОЧНОСТЬ КАЛИБРОВКИ:")
print(f"   • Средняя ошибка: {mean_error:.3f}%")
print(f"   • R² (объясненная вариация): {r_squared:.3f}")
if abs(mean_error) < 0.15 and r_squared > 0.5:
    print(f"   ✅ Формула ХОРОШО ОТКАЛИБРОВАНА")
else:
    print(f"   ⚠️ Требуется КОРРЕКТИРОВКА коэффициентов")

print(f"\n3️⃣ MULTIPLIER ЭФФЕКТ:")
print(f"   • Корреляция multiplier с движением: {corr_mult_real:.3f}")
if abs(corr_mult_real) > 0.2:
    print(f"   ✅ Multiplier ВЛИЯЕТ на реальное движение")
else:
    print(f"   ⚠️ Multiplier имеет СЛАБОЕ влияние")

print(f"\n4️⃣ РЕКОМЕНДАЦИИ:")
if abs(mean_error) > 0.2:
    correction = 1 - (mean_error / df['predicted_min_pct'].mean())
    print(f"   🔧 Применить корректировочный коэффициент: {correction:.3f}×")
if r_squared < 0.5:
    print(f"   🔧 Добавить дополнительные факторы в формулу (текущий R²={r_squared:.2f})")
if corr_mult_real < 0:
    print(f"   ⚠️ ПРОБЛЕМА: Multiplier имеет ОБРАТНУЮ связь с движением!")

print("\n" + "="*80)
print("✅ Математический анализ завершён!")
print("="*80)
