#!/usr/bin/env python3
"""
Comprehensive Analysis of Collected Signals
Analyzes successful, unsuccessful, and cancelled signals
"""

import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def load_data():
    """Load and merge effectiveness and signals data"""
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_sig = pd.read_csv('signals_log.csv')
    
    # Filter to new data
    df_eff = df_eff[df_eff['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    
    # Prepare for merge - convert timestamps and create merge keys
    df_eff['ts_key'] = pd.to_datetime(df_eff['timestamp_sent']).dt.strftime('%Y-%m-%d %H:%M')
    df_sig['ts_key'] = pd.to_datetime(df_sig['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Merge datasets on timestamp (rounded to minute) and symbol
    df = pd.merge(df_eff, df_sig, on=['ts_key', 'symbol'], how='left', suffixes=('', '_sig'))
    
    return df

def analyze_win_factors(df):
    """Analyze what factors contribute to winning signals"""
    print("="*80)
    print("ФАКТОРЫ УСПЕХА - ЧТО ПРИВОДИТ К WIN?")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    df_completed['is_win'] = (df_completed['result'] == 'WIN').astype(int)
    
    # Correlation analysis
    numeric_cols = ['score', 'confidence', 'oi_change', 'cvd_strength', 'volume_ratio', 
                    'rsi', 'ttl_minutes', 'price_vs_vwap_pct']
    
    correlations = []
    for col in numeric_cols:
        if col in df_completed.columns and df_completed[col].notna().sum() > 5:
            corr = df_completed[['is_win', col]].corr().iloc[0, 1]
            correlations.append((col, corr))
    
    correlations.sort(key=lambda x: abs(x[1]), reverse=True)
    
    print("\nКорреляция параметров с успехом (WIN):")
    print("-"*80)
    for param, corr in correlations:
        direction = "📈 Положительная" if corr > 0 else "📉 Отрицательная"
        strength = "СИЛЬНАЯ" if abs(corr) > 0.3 else "Средняя" if abs(corr) > 0.15 else "Слабая"
        print(f"{param:20s}: {corr:+.3f} | {direction} | {strength}")
    
    return correlations

def analyze_confidence_performance(df):
    """Analyze performance by confidence levels"""
    print("\n" + "="*80)
    print("АНАЛИЗ ПО УРОВНЯМ CONFIDENCE")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    ranges = [
        (0.50, 0.60, '50-60%'),
        (0.60, 0.70, '60-70%'),
        (0.70, 0.80, '70-80%'),
        (0.80, 1.00, '80-100%')
    ]
    
    print("\nRange    | Count | WIN | LOSS | WR    | Avg Profit | Avg WIN | Avg LOSS")
    print("-"*80)
    
    for low, high, label in ranges:
        mask = (df_completed['confidence'] >= low) & (df_completed['confidence'] < high)
        subset = df_completed[mask]
        
        if len(subset) > 0:
            wins = (subset['result'] == 'WIN').sum()
            losses = (subset['result'] == 'LOSS').sum()
            wr = wins / len(subset) * 100
            avg_profit = subset['profit_pct'].mean()
            avg_win = subset[subset['result'] == 'WIN']['profit_pct'].mean() if wins > 0 else 0
            avg_loss = subset[subset['result'] == 'LOSS']['profit_pct'].mean() if losses > 0 else 0
            
            print(f"{label:8s} | {len(subset):5d} | {wins:3d} | {losses:4d} | {wr:5.1f}% | {avg_profit:+9.2f}% | {avg_win:+7.2f}% | {avg_loss:+8.2f}%")

def analyze_direction_performance(df):
    """Analyze BUY vs SELL performance"""
    print("\n" + "="*80)
    print("АНАЛИЗ BUY vs SELL")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    for direction in ['BUY', 'SELL']:
        subset = df_completed[df_completed['verdict'] == direction]
        if len(subset) > 0:
            wins = (subset['result'] == 'WIN').sum()
            wr = wins / len(subset) * 100
            avg_profit = subset['profit_pct'].mean()
            avg_win = subset[subset['result'] == 'WIN']['profit_pct'].mean() if wins > 0 else 0
            avg_loss = subset[subset['result'] == 'LOSS']['profit_pct'].mean() if (subset['result'] == 'LOSS').sum() > 0 else 0
            
            print(f"\n{direction}:")
            print(f"  Сигналов: {len(subset)}")
            print(f"  WIN Rate: {wr:.1f}%")
            print(f"  Avg Profit: {avg_profit:+.2f}%")
            print(f"  Avg WIN: {avg_win:+.2f}%")
            print(f"  Avg LOSS: {avg_loss:+.2f}%")

def analyze_symbol_performance(df):
    """Analyze performance by trading pair"""
    print("\n" + "="*80)
    print("АНАЛИЗ ПО ТОРГОВЫМ ПАРАМ")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    symbol_stats = []
    for symbol in df_completed['symbol'].unique():
        subset = df_completed[df_completed['symbol'] == symbol]
        if len(subset) >= 3:  # Минимум 3 сигнала для анализа
            wins = (subset['result'] == 'WIN').sum()
            wr = wins / len(subset) * 100
            avg_profit = subset['profit_pct'].mean()
            
            symbol_stats.append({
                'symbol': symbol,
                'count': len(subset),
                'wins': wins,
                'wr': wr,
                'avg_profit': avg_profit
            })
    
    symbol_stats.sort(key=lambda x: x['wr'], reverse=True)
    
    print("\nSymbol     | Count | WIN | WR    | Avg Profit")
    print("-"*80)
    for stat in symbol_stats:
        print(f"{stat['symbol']:10s} | {stat['count']:5d} | {stat['wins']:3d} | {stat['wr']:5.1f}% | {stat['avg_profit']:+9.2f}%")

def analyze_cancellation_reasons(df):
    """Analyze why signals get cancelled"""
    print("\n" + "="*80)
    print("АНАЛИЗ ОТМЕНЕННЫХ СИГНАЛОВ")
    print("="*80)
    
    df_cancelled = df[df['result'] == 'CANCELLED'].copy()
    
    print(f"\nВсего отменено: {len(df_cancelled)} сигналов")
    print(f"Процент отмены: {len(df_cancelled) / len(df) * 100:.1f}%")
    
    # Analyze PnL at cancellation
    if 'profit_pct' in df_cancelled.columns:
        valid_pnl = df_cancelled[df_cancelled['profit_pct'].notna()]
        if len(valid_pnl) > 0:
            avg_pnl = valid_pnl['profit_pct'].mean()
            positive_pnl = (valid_pnl['profit_pct'] > 0).sum()
            
            print(f"\nСредний PnL при отмене: {avg_pnl:+.2f}%")
            print(f"Отменено с прибылью: {positive_pnl} ({positive_pnl/len(valid_pnl)*100:.1f}%)")
            print(f"Отменено с убытком: {len(valid_pnl) - positive_pnl} ({(len(valid_pnl)-positive_pnl)/len(valid_pnl)*100:.1f}%)")
    
    # Analyze by confidence level
    print("\nОтмены по уровням confidence:")
    ranges = [(0.50, 0.60, '50-60%'), (0.60, 0.70, '60-70%'), 
              (0.70, 0.80, '70-80%'), (0.80, 1.00, '80-100%')]
    
    for low, high, label in ranges:
        mask = (df_cancelled['confidence'] >= low) & (df_cancelled['confidence'] < high)
        count = mask.sum()
        total_in_range = ((df['confidence'] >= low) & (df['confidence'] < high)).sum()
        cancel_rate = count / total_in_range * 100 if total_in_range > 0 else 0
        print(f"  {label:8s}: {count:3d} отмен ({cancel_rate:5.1f}% от всех в диапазоне)")

def analyze_ttl_performance(df):
    """Analyze performance by TTL duration"""
    print("\n" + "="*80)
    print("АНАЛИЗ ПО ДЛИТЕЛЬНОСТИ СИГНАЛА (TTL)")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    if 'ttl_minutes' in df_completed.columns:
        ranges = [
            (0, 15, 'Scalping (0-15m)'),
            (15, 60, 'Short (15-60m)'),
            (60, 120, 'Medium (60-120m)'),
            (120, 999, 'Long (120m+)')
        ]
        
        print("\nTTL Range         | Count | WIN | WR    | Avg Profit")
        print("-"*80)
        
        for low, high, label in ranges:
            mask = (df_completed['ttl_minutes'] >= low) & (df_completed['ttl_minutes'] < high)
            subset = df_completed[mask]
            
            if len(subset) > 0:
                wins = (subset['result'] == 'WIN').sum()
                wr = wins / len(subset) * 100
                avg_profit = subset['profit_pct'].mean()
                print(f"{label:17s} | {len(subset):5d} | {wins:3d} | {wr:5.1f}% | {avg_profit:+9.2f}%")

def analyze_indicator_combinations(df):
    """Analyze which indicator combinations work best"""
    print("\n" + "="*80)
    print("АНАЛИЗ КОМБИНАЦИЙ ИНДИКАТОРОВ")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    indicators = ['has_cvd_signal', 'has_oi_signal', 'has_vwap_signal', 
                  'has_ema_signal', 'has_rsi_signal']
    
    # Check which indicators are present
    available = [ind for ind in indicators if ind in df_completed.columns]
    
    if len(available) >= 3:
        print("\nЧастота индикаторов в WIN vs LOSS:")
        print("-"*80)
        
        for indicator in available:
            wins_with = ((df_completed['result'] == 'WIN') & (df_completed[indicator] == 1)).sum()
            total_wins = (df_completed['result'] == 'WIN').sum()
            losses_with = ((df_completed['result'] == 'LOSS') & (df_completed[indicator] == 1)).sum()
            total_losses = (df_completed['result'] == 'LOSS').sum()
            
            win_rate_with = wins_with / total_wins * 100 if total_wins > 0 else 0
            loss_rate_with = losses_with / total_losses * 100 if total_losses > 0 else 0
            
            print(f"{indicator:17s}: WIN {win_rate_with:5.1f}% | LOSS {loss_rate_with:5.1f}%")

def generate_recommendations(df, correlations):
    """Generate actionable recommendations based on analysis"""
    print("\n" + "="*80)
    print("РЕКОМЕНДАЦИИ ДЛЯ УЛУЧШЕНИЯ МОДЕЛИ")
    print("="*80)
    
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    recommendations = []
    
    # High cancellation rate
    cancel_rate = (df['result'] == 'CANCELLED').sum() / len(df) * 100
    if cancel_rate > 60:
        recommendations.append(f"⚠️  Высокий процент отмены ({cancel_rate:.1f}%)")
        recommendations.append("   → Пересмотреть пороги confidence для cancellation")
        recommendations.append("   → Возможно, сигналы слишком чувствительны к краткосрочным изменениям")
    
    # High confidence paradox
    high_conf = df_completed[df_completed['confidence'] >= 0.80]
    if len(high_conf) > 0:
        high_conf_wr = (high_conf['result'] == 'WIN').sum() / len(high_conf) * 100
        low_conf = df_completed[df_completed['confidence'] < 0.70]
        low_conf_wr = (low_conf['result'] == 'WIN').sum() / len(low_conf) * 100 if len(low_conf) > 0 else 0
        
        if high_conf_wr < low_conf_wr:
            recommendations.append(f"⚠️  Парадокс confidence: 80-100% WR={high_conf_wr:.1f}% < 50-70% WR={low_conf_wr:.1f}%")
            recommendations.append("   → Формула confidence требует рекалибровки")
            recommendations.append("   → Высокая confidence не коррелирует с успехом")
    
    # Strong correlations
    strong_positive = [c for c in correlations if c[1] > 0.2]
    strong_negative = [c for c in correlations if c[1] < -0.2]
    
    if strong_positive:
        recommendations.append(f"\n✅ Сильные положительные факторы:")
        for param, corr in strong_positive[:3]:
            recommendations.append(f"   → {param}: {corr:+.3f} - увеличить вес в модели")
    
    if strong_negative:
        recommendations.append(f"\n❌ Сильные отрицательные факторы:")
        for param, corr in strong_negative[:3]:
            recommendations.append(f"   → {param}: {corr:+.3f} - уменьшить вес или инвертировать")
    
    # Print recommendations
    for rec in recommendations:
        print(rec)
    
    # ML model recommendations
    print("\n📊 Рекомендации для ML модели:")
    print(f"   → Текущий датасет: {len(df_completed)} сигналов (минимум пройден)")
    if len(df_completed) < 100:
        print(f"   → Рекомендуется собрать еще {100 - len(df_completed)} для более точной модели")
    print("   → Использовать SimpleLinearRegression вместо RandomForest для малых данных")
    print("   → Добавить регуляризацию (L1/L2) для предотвращения переобучения")
    print("   → Применить кросс-валидацию с 5-10 фолдами")
    
def main():
    print("="*80)
    print("КОМПЛЕКСНЫЙ АНАЛИЗ СОБРАННЫХ ДАННЫХ")
    print("="*80)
    print(f"Дата тренировки модели: {TRAINING_CUTOFF}")
    print(f"Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    df = load_data()
    print(f"Загружено сигналов: {len(df)}")
    print(f"  WIN: {(df['result'] == 'WIN').sum()}")
    print(f"  LOSS: {(df['result'] == 'LOSS').sum()}")
    print(f"  CANCELLED: {(df['result'] == 'CANCELLED').sum()}")
    print()
    
    # Run analyses
    correlations = analyze_win_factors(df)
    analyze_confidence_performance(df)
    analyze_direction_performance(df)
    analyze_symbol_performance(df)
    analyze_ttl_performance(df)
    analyze_indicator_combinations(df)
    analyze_cancellation_reasons(df)
    generate_recommendations(df, correlations)
    
    print("\n" + "="*80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*80)
    print("\n📁 Исходные данные:")
    print("   - effectiveness_log.csv")
    print("   - signals_log.csv")
    print("\n💡 Следующие шаги:")
    print("   1. Применить рекомендации к формуле confidence")
    print("   2. Собрать еще данных (цель: 100-200 сигналов)")
    print("   3. Переобучить модель с улучшенными параметрами")

if __name__ == '__main__':
    main()
