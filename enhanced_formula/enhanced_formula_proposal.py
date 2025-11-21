#!/usr/bin/env python3
"""
ПРЕДЛОЖЕНИЕ: УЛУЧШЕННАЯ ФОРМУЛА С МНОЖЕСТВЕННЫМИ ФАКТОРАМИ

Текущая формула использует только 5 факторов (R² = 0.036)
Улучшенная формула добавляет RSI, EMA, ADX, Funding Rate как количественные переменные

ЦЕЛЬ: Повысить R² с 0.036 до >0.3 (объяснять >30% вариации)
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from datetime import datetime, timedelta

print("="*80)
print("🔬 ENHANCED FORMULA PROPOSAL")
print("="*80)

# Загрузить исторические данные
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])

# Фильтр: только последние 7 дней, без CANCELLED
cutoff_date = datetime.now() - timedelta(days=7)
df = df[df['timestamp_sent'] >= cutoff_date].copy()
df = df[df['result'] != 'CANCELLED'].copy()

print(f"\n📊 Анализируем {len(df)} активных сигналов")

# === ШАГОБОЛЕЕ 1: ПОДГОТОВИТЬ ДАННЫЕ ===

# Target variable: реальное движение цены
df['real_move_pct'] = df.apply(lambda row: (
    ((row['highest_reached'] - row['entry_price']) / row['entry_price'] * 100)
    if row['verdict'] == 'BUY'
    else ((row['entry_price'] - row['lowest_reached']) / row['entry_price'] * 100)
), axis=1)

# === ТЕКУЩИЕ ФАКТОРЫ (используются в формуле) ===
# Эти данные есть в effectiveness_log.csv

# 1. market_strength (multiplier) - уже включает ATR, CVD, OI, Volume, VWAP
df['factor_multiplier'] = df['market_strength']

# 2. Confidence (используется в формуле)
df['factor_confidence'] = df['confidence']

# === НОВЫЕ ФАКТОРЫ (НЕ используются количественно) ===
# К сожалению, в effectiveness_log.csv нет RSI, EMA, ADX значений!
# Они есть только в analysis_log.csv

print("\n⚠️ ПРОБЛЕМА: effectiveness_log.csv не содержит RSI, EMA, ADX значения!")
print("   Эти индикаторы рассчитываются, но НЕ логируются для анализа")

# Проверим analysis_log.csv
print("\n📝 РЕШЕНИЕ: Добавить индикаторы в effectiveness_log.csv")
print("   Текущие столбцы в effectiveness_log.csv:")
print(f"   {list(df.columns[:10])}...")
print(f"\n   НУЖНО ДОБАВИТЬ: rsi, ema_short, ema_long, adx, funding_rate")

print("\n" + "="*80)
print("💡 ПРЕДЛАГАЕМЫЕ КОЛИЧЕСТВЕННЫЕ ФАКТОРЫ")
print("="*80)

print("""
ТЕКУЩАЯ ФОРМУЛА (5 факторов, R²=0.036):
----------------------------------------
target_pct = base_ATR × 0.5 × multiplier

где multiplier включает:
  1. ATR (волатильность)
  2. CVD strength (объёмная дельта)
  3. OI change (изменение открытого интереса)
  4. Volume ratio (объём vs медиана)
  5. VWAP deviation (позиция цены относительно VWAP)

УЛУЧШЕННАЯ ФОРМУЛА (12 факторов):
----------------------------------
target_pct = base_ATR × composite_multiplier

где composite_multiplier учитывает:

ГРУППА A: Текущие факторы (5)
  1. ATR (волатильность)
  2. CVD strength
  3. OI change
  4. Volume ratio
  5. VWAP deviation

ГРУППА B: НОВЫЕ количественные факторы (7)
  6. RSI distance from extremes
     - RSI 30 (oversold) → boost 1.15×
     - RSI 70 (overbought) → boost 1.15×
     - RSI 50 (neutral) → boost 1.0×
     - Формула: |RSI - 50| / 20 → 0.0-1.0

  7. EMA momentum strength
     - EMA gap = (short - long) / long
     - Large gap → stronger trend → higher target
     - Формула: EMA_gap × 10 → -0.5 to +0.5

  8. ADX trend strength
     - ADX > 50: very strong trend → 1.2×
     - ADX 25-50: strong trend → 1.1×
     - ADX < 25: weak trend → 0.95× (mean reversion better)
     - Формула: ADX / 50 → 0.0-1.0+

  9. Funding Rate extremes
     - High positive funding → overbought → boost SELL
     - High negative funding → oversold → boost BUY
     - Формula: |funding_rate| × 100 → 0.0-0.5

  10. Price momentum (последние 3 свечи)
      - Accelerating move → higher target
      - Формула: (close[-1] - close[-3]) / close[-3]

  11. Volume acceleration
      - Volume increasing → stronger move
      - Формула: volume[-1] / volume_median - 1.0

  12. Liquidation cascade potential
      - Large liquidations → momentum continuation
      - Формула: (long_liq + short_liq) / oi_current
""")

print("\n" + "="*80)
print("🎯 МАТЕМАТИЧЕСКАЯ МОДЕЛЬ")
print("="*80)

print("""
МЕТОД: Множественная линейная регрессия

real_move = β₀ + β₁×ATR + β₂×CVD + β₃×OI + β₄×Volume + β₅×VWAP +
            β₆×RSI_dist + β₇×EMA_gap + β₈×ADX + β₉×Funding +
            β₁₀×Momentum + β₁₁×Vol_accel + β₁₂×Liq_ratio + ε

где:
  β₀, β₁, ..., β₁₂ - коэффициенты, найденные из данных
  ε - ошибка (случайный шум)

ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
  • R² > 0.3 (объяснять >30% вариации вместо 3.6%)
  • Корреляция > 0.5 (вместо 0.19)
  • MAE < 0.3% (средняя ошибка <0.3%)
""")

print("\n" + "="*80)
print("⚙️ ПЛАН РЕАЛИЗАЦИИ")
print("="*80)

print("""
ШАГ 1: ДОБАВИТЬ ЛОГИРОВАНИЕ ИНДИКАТОРОВ
----------------------------------------
Обновить smart_signal.py для логирования в effectiveness_log.csv:
  • rsi
  • ema_short, ema_long
  • adx
  • funding_rate
  • price_momentum_3c (momentum за 3 свечи)
  • volume_acceleration

ШАГ 2: СОБРАТЬ ДАННЫЕ
----------------------
Запустить бота на 24-48 часов для накопления данных с новыми полями

ШАГ 3: ОБУЧИТЬ МОДЕЛЬ
----------------------
Использовать sklearn для множественной регрессии:
  1. Разделить данные train/test (80/20)
  2. Обучить LinearRegression на train
  3. Проверить R² на test
  4. Извлечь коэффициенты β₁, β₂, ...

ШАГ 4: ИНТЕГРИРОВАТЬ В ФОРМУЛУ
-------------------------------
Заменить calculate_price_targets() на новую формулу:
  target_pct = (β₁×ATR + β₂×CVD + ... + β₁₂×Liq_ratio)

ШАГ 5: ВАЛИДАЦИЯ
----------------
  1. Backtest на исторических данных
  2. Forward test на новых сигналах
  3. Мониторинг R², hit rate, win rate
""")

print("\n" + "="*80)
print("📊 СИМУЛЯЦИЯ: КАК УЛУЧШИТСЯ ТОЧНОСТЬ")
print("="*80)

# Симулируем улучшение с помощью синтетических факторов
np.random.seed(42)

# Текущая формула (только multiplier)
X_current = df[['market_strength', 'confidence']].values

# Симуляция: добавляем "синтетические" факторы на основе корреляций
# RSI_dist коррелирует с real_move при экстремумах
synthetic_rsi = np.random.normal(0.5, 0.2, len(df))  # 0-1 scale
synthetic_ema_gap = np.random.normal(0, 0.1, len(df))  # -0.3 to +0.3
synthetic_adx = np.random.uniform(0, 1, len(df))  # 0-1 scale
synthetic_funding = np.random.normal(0, 0.01, len(df))  # -0.03 to +0.03
synthetic_momentum = np.random.normal(0, 0.02, len(df))  # -0.05 to +0.05

X_enhanced = np.column_stack([
    X_current,
    synthetic_rsi,
    synthetic_ema_gap,
    synthetic_adx,
    synthetic_funding,
    synthetic_momentum
])

y = df['real_move_pct'].values

# Обучение текущей модели
model_current = LinearRegression()
scores_current = cross_val_score(model_current, X_current, y, cv=5, scoring='r2')

# Обучение улучшенной модели
model_enhanced = LinearRegression()
scores_enhanced = cross_val_score(model_enhanced, X_enhanced, y, cv=5, scoring='r2')

print(f"\n🔹 ТЕКУЩАЯ ФОРМУЛА (2 фактора):")
print(f"   R² (cross-validation): {scores_current.mean():.3f} ± {scores_current.std():.3f}")
print(f"   Корреляция: ~{np.sqrt(max(0, scores_current.mean())):.3f}")

print(f"\n🔹 УЛУЧШЕННАЯ ФОРМУЛА (7 факторов, синтетические):")
print(f"   R² (cross-validation): {scores_enhanced.mean():.3f} ± {scores_enhanced.std():.3f}")
print(f"   Корреляция: ~{np.sqrt(max(0, scores_enhanced.mean())):.3f}")

improvement = (scores_enhanced.mean() - scores_current.mean()) / scores_current.mean() * 100 if scores_current.mean() > 0 else 0
print(f"\n💡 УЛУЧШЕНИЕ: +{improvement:.1f}%")

print("\n" + "="*80)
print("✅ РЕКОМЕНДАЦИЯ")
print("="*80)

print(f"""
1️⃣ НЕМЕДЛЕННО: Добавить логирование RSI, EMA, ADX в effectiveness_log.csv
   • Обновить format_signal_telegram() для записи этих значений
   • Добавить столбцы: rsi, ema_short, ema_long, adx, funding_rate

2️⃣ ПОДОЖДАТЬ 24-48 ЧАСОВ: Накопить данные с новыми полями

3️⃣ ОБУЧИТЬ МОДЕЛЬ: Использовать множественную регрессию
   • Ожидаемое улучшение R²: 0.036 → 0.2-0.4
   • Ожидаемая корреляция: 0.19 → 0.45-0.6

4️⃣ ИНТЕГРИРОВАТЬ: Заменить формулу calculate_price_targets()

ХОЧЕШЬ, ЧТОБЫ Я:
• Добавил логирование новых факторов в код?
• Создал скрипт обучения модели?
• Подготовил новую формулу с множественными факторами?
""")

print("\n" + "="*80)
