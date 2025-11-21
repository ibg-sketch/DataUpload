#!/usr/bin/env python3
"""
Анализ влияния изменений volume filter на количество сигналов.

Сравнивает три варианта:
- Вариант Б': window=15, threshold=0.3
- Вариант С: window=30, threshold=0.2
- Вариант D: без volume filter

Анализирует данные за 30-31 октября 2025.
"""

import pandas as pd
import numpy as np
from datetime import datetime

def load_data(start_date, end_date):
    """Загрузить данные из analysis_log за указанный период."""
    try:
        # Используем backup файл для данных за 30-31 октября
        df = pd.read_csv('analysis_log_backup_20251031_051202.csv', on_bad_lines='skip', engine='python')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Фильтруем по датам
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        filtered = df[mask].copy()
        
        print(f"\n📊 Загружено записей: {len(filtered)}")
        print(f"   Период: {filtered['timestamp'].min()} - {filtered['timestamp'].max()}")
        
        return filtered
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return None

def apply_volume_filter(row, window, threshold):
    """
    Применить volume filter к записи.
    
    Args:
        row: строка из DataFrame
        window: количество свечей для медианы (не используется, т.к. медиана уже рассчитана)
        threshold: порог (например, 0.5 = 50% медианы)
    
    Returns:
        True если проходит фильтр, False если блокируется
    """
    volume_last = row['volume']
    volume_median = row['volume_median']
    
    if volume_median == 0:
        return True  # Если медиана 0, пропускаем
    
    return volume_last >= volume_median * threshold

def simulate_signals(df, window, threshold, no_filter=False):
    """
    Симулировать генерацию сигналов с заданными параметрами.
    
    Args:
        df: DataFrame с данными
        window: окно для медианы (информационно, медиана уже рассчитана в логе)
        threshold: порог для фильтра
        no_filter: если True, игнорировать volume filter
    
    Returns:
        DataFrame только с записями, которые прошли бы фильтр
    """
    if no_filter:
        # Вариант D: все сигналы, где score >= min_score
        passed = df[df['score'] >= df['min_score']].copy()
        passed['filter_reason'] = 'no_filter'
    else:
        # Применяем volume filter
        df['passes_volume'] = df.apply(lambda row: apply_volume_filter(row, window, threshold), axis=1)
        
        # Сигналы проходят если: score >= min_score И passes_volume
        passed = df[(df['score'] >= df['min_score']) & df['passes_volume']].copy()
        passed['filter_reason'] = f'volume_ok (threshold={threshold})'
    
    return passed

def load_effectiveness_data():
    """Загрузить данные об эффективности сигналов."""
    try:
        eff = pd.read_csv('effectiveness_log.csv')
        eff['timestamp_sent'] = pd.to_datetime(eff['timestamp_sent'])
        return eff
    except Exception as e:
        print(f"⚠️ Не удалось загрузить effectiveness_log: {e}")
        return None

def match_signals_with_results(signals_df, effectiveness_df):
    """
    Сопоставить сигналы с результатами из effectiveness_log.
    
    Returns:
        dict с подсчетом результатов
    """
    if effectiveness_df is None:
        return {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0, 'UNKNOWN': len(signals_df)}
    
    results = {'WIN': 0, 'LOSS': 0, 'CANCELLED': 0, 'UNKNOWN': 0}
    
    for idx, signal in signals_df.iterrows():
        # Ищем совпадение по символу, времени (±2 минуты) и verdict
        time_window = pd.Timedelta(minutes=2)
        
        matches = effectiveness_df[
            (effectiveness_df['symbol'] == signal['symbol']) &
            (effectiveness_df['verdict'] == signal['verdict']) &
            (effectiveness_df['timestamp_sent'] >= signal['timestamp'] - time_window) &
            (effectiveness_df['timestamp_sent'] <= signal['timestamp'] + time_window)
        ]
        
        if len(matches) > 0:
            result = matches.iloc[0]['result']
            results[result] = results.get(result, 0) + 1
        else:
            results['UNKNOWN'] += 1
    
    return results

def analyze_variant(df, effectiveness_df, variant_name, window, threshold, no_filter=False, date_filter=None):
    """Анализировать один вариант параметров."""
    
    # Фильтруем по дате если указана
    if date_filter:
        df = df[df['timestamp'].dt.date == pd.to_datetime(date_filter).date()].copy()
    
    print(f"\n{'='*60}")
    print(f"📋 {variant_name}")
    print(f"{'='*60}")
    
    if no_filter:
        print(f"   Параметры: БЕЗ volume filter")
    else:
        print(f"   Параметры: окно={window} свечей, порог={threshold*100:.0f}% медианы")
    
    # Симулируем сигналы
    passed_signals = simulate_signals(df, window, threshold, no_filter)
    
    total_opportunities = len(df[df['score'] >= df['min_score']])
    total_signals = len(passed_signals)
    
    # Подсчет по verdict
    buy_signals = len(passed_signals[passed_signals['verdict'] == 'BUY'])
    sell_signals = len(passed_signals[passed_signals['verdict'] == 'SELL'])
    
    print(f"\n📊 Статистика сигналов:")
    print(f"   Всего возможностей (score >= min_score): {total_opportunities}")
    print(f"   Прошло volume filter: {total_signals}")
    print(f"   Заблокировано: {total_opportunities - total_signals}")
    print(f"   BUY сигналов: {buy_signals}")
    print(f"   SELL сигналов: {sell_signals}")
    
    # Сопоставляем с результатами
    results = match_signals_with_results(passed_signals, effectiveness_df)
    
    print(f"\n🎯 Результаты сигналов:")
    print(f"   ✅ WIN:       {results['WIN']} ({results['WIN']/total_signals*100 if total_signals > 0 else 0:.1f}%)")
    print(f"   ❌ LOSS:      {results['LOSS']} ({results['LOSS']/total_signals*100 if total_signals > 0 else 0:.1f}%)")
    print(f"   ⚠️ CANCELLED: {results['CANCELLED']} ({results['CANCELLED']/total_signals*100 if total_signals > 0 else 0:.1f}%)")
    print(f"   ❓ UNKNOWN:   {results['UNKNOWN']} ({results['UNKNOWN']/total_signals*100 if total_signals > 0 else 0:.1f}%)")
    
    # Win Rate
    total_completed = results['WIN'] + results['LOSS']
    win_rate = (results['WIN'] / total_completed * 100) if total_completed > 0 else 0
    
    print(f"\n📈 Метрики:")
    print(f"   Win Rate: {win_rate:.1f}% ({results['WIN']}/{total_completed})")
    print(f"   Cancellation Rate: {results['CANCELLED']/total_signals*100 if total_signals > 0 else 0:.1f}%")
    
    return {
        'variant': variant_name,
        'total_signals': total_signals,
        'buy': buy_signals,
        'sell': sell_signals,
        'win': results['WIN'],
        'loss': results['LOSS'],
        'cancelled': results['CANCELLED'],
        'win_rate': win_rate
    }

def main():
    print("🔍 Анализ влияния volume filter на генерацию сигналов")
    print("="*60)
    
    # Загружаем данные за 30-31 октября
    start_date = '2025-10-30 00:00:00'
    end_date = '2025-11-01 00:00:00'
    
    df = load_data(start_date, end_date)
    
    if df is None or len(df) == 0:
        print("❌ Нет данных для анализа")
        return
    
    # Загружаем effectiveness данные
    effectiveness_df = load_effectiveness_data()
    
    # Анализируем по дням
    dates = ['2025-10-30', '2025-10-31']
    
    for date in dates:
        print(f"\n\n{'#'*60}")
        print(f"# Дата: {date}")
        print(f"{'#'*60}")
        
        # Вариант Б': короткое окно + мягкий порог
        analyze_variant(df, effectiveness_df, 
                       "Вариант Б' (короткое окно + мягкий порог)", 
                       window=15, threshold=0.3, date_filter=date)
        
        # Вариант С: текущее окно + очень слабый порог
        analyze_variant(df, effectiveness_df,
                       "Вариант С (текущее окно + слабый порог)",
                       window=30, threshold=0.2, date_filter=date)
        
        # Вариант D: без фильтра
        analyze_variant(df, effectiveness_df,
                       "Вариант D (без volume filter)",
                       window=30, threshold=0.5, no_filter=True, date_filter=date)
        
        # Текущая система (для сравнения)
        analyze_variant(df, effectiveness_df,
                       "ТЕКУЩАЯ СИСТЕМА (baseline)",
                       window=30, threshold=0.5, date_filter=date)
    
    print("\n\n" + "="*60)
    print("✅ Анализ завершён")
    print("="*60)

if __name__ == '__main__':
    main()
