#!/usr/bin/env python3
"""
Pattern Mining: Поиск комбинаций индикаторов, предшествующих движениям цены.

Цель: Найти все случаи за среду-четверг, когда:
- В течение 30 минут цена изменилась на >= 1%
- Тренд был четким (без сильных откатов)
- Низкая волатильность в начале движения

Анализируем характеристики этих моментов.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_raw_data():
    """Загрузить сырые данные из analysis_log."""
    print("📥 Загрузка данных...")
    df = pd.read_csv('analysis_log_backup_20251031_051202.csv', on_bad_lines='skip', engine='python')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Фильтруем 30-31 октября
    start_date = '2025-10-30 00:00:00'
    end_date = '2025-11-01 00:00:00'
    
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    filtered = df[mask].copy()
    
    print(f"   Загружено: {len(filtered)} записей")
    print(f"   Период: {filtered['timestamp'].min()} - {filtered['timestamp'].max()}")
    
    return filtered

def check_clean_trend(prices, threshold_pct=1.0, max_drawdown_pct=0.5):
    """
    Проверить, является ли движение цены чистым трендом.
    
    Args:
        prices: список цен (по порядку времени)
        threshold_pct: минимальное изменение (в %)
        max_drawdown_pct: максимальный допустимый откат (в %)
    
    Returns:
        dict с информацией о тренде или None
    """
    if len(prices) < 2:
        return None
    
    start_price = prices[0]
    end_price = prices[-1]
    
    # Изменение цены в процентах
    price_change_pct = ((end_price - start_price) / start_price) * 100
    
    # Проверяем достижение порога
    if abs(price_change_pct) < threshold_pct:
        return None
    
    # Определяем направление
    direction = 'UP' if price_change_pct > 0 else 'DOWN'
    
    # Для восходящего тренда: проверяем максимальный откат вниз
    # Для нисходящего: проверяем максимальный откат вверх
    max_adverse_move = 0
    
    if direction == 'UP':
        # Ищем максимальное падение от начальной цены
        for price in prices:
            drawdown = ((price - start_price) / start_price) * 100
            if drawdown < max_adverse_move:
                max_adverse_move = drawdown
    else:
        # Ищем максимальное повышение от начальной цены
        for price in prices:
            rally = ((price - start_price) / start_price) * 100
            if rally > max_adverse_move:
                max_adverse_move = rally
    
    # Проверяем, не превышает ли откат допустимый
    if abs(max_adverse_move) > max_drawdown_pct:
        return None  # Слишком большой откат
    
    # Также проверяем, что тренд был относительно прямым
    # (конечная точка близка к максимальному/минимальному значению)
    if direction == 'UP':
        max_price = max(prices)
        # Конечная цена должна быть близка к максимуму (в пределах 0.3%)
        if ((max_price - end_price) / start_price) * 100 > 0.3:
            return None  # Откат от пика слишком большой
    else:
        min_price = min(prices)
        # Конечная цена должна быть близка к минимуму
        if ((end_price - min_price) / start_price) * 100 > 0.3:
            return None  # Отскок от дна слишком большой
    
    return {
        'direction': direction,
        'price_change_pct': price_change_pct,
        'max_adverse_move_pct': max_adverse_move,
        'start_price': start_price,
        'end_price': end_price,
        'max_price': max(prices),
        'min_price': min(prices)
    }

def find_price_movements(df, window_minutes=30, threshold_pct=1.0):
    """
    Найти все случаи четких движений цены.
    
    Args:
        df: DataFrame с данными
        window_minutes: окно для проверки (в минутах)
        threshold_pct: минимальное изменение цены (в %)
    
    Returns:
        список найденных паттернов
    """
    print(f"\n🔍 Поиск движений цены >= {threshold_pct}% за {window_minutes} минут...")
    
    patterns = []
    
    # Группируем по символам
    for symbol in df['symbol'].unique():
        symbol_data = df[df['symbol'] == symbol].sort_values('timestamp').reset_index(drop=True)
        
        # Для каждой записи смотрим вперед на window_minutes
        for idx in range(len(symbol_data)):
            current_row = symbol_data.iloc[idx]
            current_time = current_row['timestamp']
            current_price = current_row['price']
            
            # Находим все записи в течение следующих window_minutes
            future_mask = (
                (symbol_data['timestamp'] > current_time) &
                (symbol_data['timestamp'] <= current_time + timedelta(minutes=window_minutes))
            )
            future_data = symbol_data[future_mask]
            
            if len(future_data) < 3:  # Минимум 3 точки для тренда
                continue
            
            # Собираем цены включая текущую
            prices = [current_price] + future_data['price'].tolist()
            
            # Проверяем на чистый тренд
            trend_info = check_clean_trend(prices, threshold_pct=threshold_pct)
            
            if trend_info is not None:
                # Нашли паттерн!
                pattern = {
                    'timestamp': current_time,
                    'symbol': symbol,
                    'interval': current_row['interval'],
                    
                    # Характеристики движения
                    'direction': trend_info['direction'],
                    'price_change_pct': trend_info['price_change_pct'],
                    'max_adverse_move_pct': trend_info['max_adverse_move_pct'],
                    'duration_actual_min': (future_data.iloc[-1]['timestamp'] - current_time).total_seconds() / 60,
                    
                    # Входные индикаторы в момент начала
                    'price': current_price,
                    'vwap': current_row['vwap'],
                    'price_vs_vwap_pct': current_row['price_vs_vwap_pct'],
                    'dev_sigma': current_row.get('dev_sigma', np.nan),
                    'dev_sigma_blocked': current_row.get('dev_sigma_blocked', 0),
                    'dev_sigma_boost': current_row.get('dev_sigma_boost', 0),
                    
                    'cvd': current_row['cvd'],
                    'oi': current_row['oi'],
                    'oi_change': current_row['oi_change'],
                    'oi_change_pct': current_row['oi_change_pct'],
                    
                    'volume': current_row['volume'],
                    'volume_median': current_row['volume_median'],
                    'volume_ratio': current_row['volume'] / current_row['volume_median'] if current_row['volume_median'] > 0 else 0,
                    'volume_spike': current_row['volume_spike'],
                    
                    'liq_long_count': current_row['liq_long_count'],
                    'liq_short_count': current_row['liq_short_count'],
                    'liq_long_usd': current_row['liq_long_usd'],
                    'liq_short_usd': current_row['liq_short_usd'],
                    'liq_ratio': current_row['liq_ratio'],
                    
                    'rsi': current_row['rsi'],
                    'ema_short': current_row['ema_short'],
                    'ema_long': current_row['ema_long'],
                    'atr': current_row['atr'],
                    'adx': current_row['adx'],
                    'regime': current_row['regime'],
                    
                    'vwap_cross_up': current_row['vwap_cross_up'],
                    'vwap_cross_down': current_row['vwap_cross_down'],
                    'ema_cross_up': current_row['ema_cross_up'],
                    'ema_cross_down': current_row['ema_cross_down'],
                    
                    # Был ли это сигнал?
                    'verdict': current_row['verdict'],
                    'score': current_row['score'],
                    'min_score': current_row['min_score'],
                    'confidence': current_row['confidence'],
                }
                
                patterns.append(pattern)
    
    print(f"   Найдено паттернов: {len(patterns)}")
    return patterns

def analyze_patterns(patterns):
    """Анализ найденных паттернов."""
    if not patterns:
        print("\n⚠️ Паттерны не найдены")
        return
    
    df_patterns = pd.DataFrame(patterns)
    
    print(f"\n{'='*80}")
    print(f"📊 АНАЛИЗ НАЙДЕННЫХ ДВИЖЕНИЙ ЦЕНЫ")
    print(f"{'='*80}")
    
    # Общая статистика
    print(f"\n🔢 Общая статистика:")
    print(f"   Всего движений: {len(df_patterns)}")
    print(f"   UP движений: {len(df_patterns[df_patterns['direction'] == 'UP'])}")
    print(f"   DOWN движений: {len(df_patterns[df_patterns['direction'] == 'DOWN'])}")
    
    # По символам
    print(f"\n📈 По символам:")
    symbol_counts = df_patterns['symbol'].value_counts()
    for symbol, count in symbol_counts.items():
        print(f"   {symbol}: {count} движений")
    
    # По дням
    print(f"\n📅 По дням:")
    df_patterns['date'] = pd.to_datetime(df_patterns['timestamp']).dt.date
    date_counts = df_patterns['date'].value_counts().sort_index()
    for date, count in date_counts.items():
        print(f"   {date}: {count} движений")
    
    # Сколько были сигналами?
    signals = df_patterns[df_patterns['verdict'].isin(['BUY', 'SELL'])]
    no_signals = df_patterns[df_patterns['verdict'] == 'NO_TRADE']
    
    print(f"\n🎯 Было ли отправлено сигналов:")
    print(f"   ✅ Был сигнал: {len(signals)} ({len(signals)/len(df_patterns)*100:.1f}%)")
    print(f"   ❌ Не было сигнала: {len(no_signals)} ({len(no_signals)/len(df_patterns)*100:.1f}%)")
    
    if len(signals) > 0:
        print(f"\n   Сигналы по направлениям:")
        print(f"      BUY: {len(signals[signals['verdict'] == 'BUY'])}")
        print(f"      SELL: {len(signals[signals['verdict'] == 'SELL'])}")
    
    # КРИТИЧЕСКИЙ АНАЛИЗ: Пропущенные возможности
    print(f"\n{'='*80}")
    print(f"⚠️ ПРОПУЩЕННЫЕ ВОЗМОЖНОСТИ (не было сигнала)")
    print(f"{'='*80}")
    
    if len(no_signals) > 0:
        # UP движения без BUY сигнала
        missed_buys = no_signals[no_signals['direction'] == 'UP']
        print(f"\n📈 UP движения без BUY сигнала: {len(missed_buys)}")
        
        if len(missed_buys) > 0:
            print(f"\n   Почему не прошли фильтры:")
            
            # Анализ по причинам
            reasons = []
            
            for idx, row in missed_buys.iterrows():
                reason_parts = []
                
                # Score
                if row['score'] < row['min_score']:
                    reason_parts.append(f"score={row['score']:.1f}<{row['min_score']}")
                
                # Volume
                vol_ratio = row['volume_ratio']
                if vol_ratio < 0.5:
                    reason_parts.append(f"vol={vol_ratio:.2f}x (low)")
                
                # Dev sigma blocked
                if row['dev_sigma_blocked'] == 1:
                    reason_parts.append(f"dev_sigma={row['dev_sigma']:.2f} (blocked)")
                
                # Price vs VWAP (для BUY нужно price < VWAP или cross)
                if row['price_vs_vwap_pct'] > 0 and row['vwap_cross_up'] == 0:
                    reason_parts.append(f"price>{row['price_vs_vwap_pct']:.2f}% VWAP (no cross)")
                
                # OI
                if abs(row['oi_change_pct']) < 0.05:
                    reason_parts.append(f"OI Δ={row['oi_change_pct']:.3f}%")
                
                reason_str = "; ".join(reason_parts) if reason_parts else "unknown"
                reasons.append(reason_str)
            
            missed_buys['block_reason'] = reasons
            
            # Топ причин
            reason_counts = pd.Series(reasons).value_counts()
            print(f"\n   Топ-5 причин блокировки:")
            for i, (reason, count) in enumerate(reason_counts.head(5).items(), 1):
                print(f"      {i}. {reason}: {count} случаев")
            
            # Примеры
            print(f"\n   Примеры пропущенных UP движений:")
            print(f"   {'Время':<20} {'Символ':<10} {'Изм%':<8} {'Score':<10} {'Vol ratio':<10} {'OI Δ%':<10} {'Причина':<40}")
            print(f"   {'-'*120}")
            
            for idx, row in missed_buys.head(10).iterrows():
                print(f"   {str(row['timestamp']):<20} {row['symbol']:<10} "
                      f"{row['price_change_pct']:>6.2f}% "
                      f"{row['score']:>4.1f}/{row['min_score']:<3.1f} "
                      f"{row['volume_ratio']:>8.2f}x "
                      f"{row['oi_change_pct']:>8.3f}% "
                      f"{row['block_reason']:<40}")
        
        # DOWN движения без SELL сигнала
        missed_sells = no_signals[no_signals['direction'] == 'DOWN']
        print(f"\n📉 DOWN движения без SELL сигнала: {len(missed_sells)}")
        
        if len(missed_sells) > 0:
            print(f"\n   Примеры пропущенных DOWN движений:")
            print(f"   {'Время':<20} {'Символ':<10} {'Изм%':<8} {'Score':<10} {'Vol ratio':<10} {'Price vs VWAP':<15}")
            print(f"   {'-'*100}")
            
            for idx, row in missed_sells.head(10).iterrows():
                print(f"   {str(row['timestamp']):<20} {row['symbol']:<10} "
                      f"{row['price_change_pct']:>6.2f}% "
                      f"{row['score']:>4.1f}/{row['min_score']:<3.1f} "
                      f"{row['volume_ratio']:>8.2f}x "
                      f"{row['price_vs_vwap_pct']:>6.2f}%")
    
    # Характеристики успешных сигналов
    if len(signals) > 0:
        print(f"\n{'='*80}")
        print(f"✅ ХАРАКТЕРИСТИКИ УСПЕШНО ПОЙМАННЫХ ДВИЖЕНИЙ")
        print(f"{'='*80}")
        
        print(f"\n   Средние значения индикаторов:")
        print(f"   CVD: {signals['cvd'].mean():,.0f}")
        print(f"   OI change %: {signals['oi_change_pct'].mean():.3f}%")
        print(f"   Volume ratio: {signals['volume_ratio'].mean():.2f}x")
        print(f"   Dev sigma: {signals['dev_sigma'].mean():.2f}")
        print(f"   RSI: {signals['rsi'].mean():.1f}")
        print(f"   Price change: {signals['price_change_pct'].mean():.2f}%")
    
    # Сохранение в CSV для детального анализа
    csv_file = 'pattern_analysis_results.csv'
    df_patterns.to_csv(csv_file, index=False)
    print(f"\n💾 Результаты сохранены в: {csv_file}")
    
    return df_patterns

def main():
    print("🔍 PATTERN MINING: Поиск комбинаций индикаторов перед движениями цены")
    print("="*80)
    
    # Загружаем данные
    df = load_raw_data()
    
    # Находим движения цены
    patterns = find_price_movements(df, window_minutes=30, threshold_pct=1.0)
    
    # Анализируем
    if patterns:
        df_patterns = analyze_patterns(patterns)
        
        print(f"\n{'='*80}")
        print(f"✅ Анализ завершён")
        print(f"{'='*80}")
    else:
        print("\n⚠️ Не найдено движений цены, соответствующих критериям")

if __name__ == '__main__':
    main()
