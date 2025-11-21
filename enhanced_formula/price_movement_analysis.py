#!/usr/bin/env python3
"""
Deep Price Movement Analysis
Analyzes correlation between signal parameters and actual price movements
"""

import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def load_and_merge_data():
    """Load and merge all data sources"""
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_sig = pd.read_csv('signals_log.csv')
    
    # Filter to new data
    df_eff = df_eff[df_eff['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    
    # Prepare for merge
    df_eff['ts_key'] = pd.to_datetime(df_eff['timestamp_sent']).dt.strftime('%Y-%m-%d %H:%M')
    df_sig['ts_key'] = pd.to_datetime(df_sig['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Merge datasets
    df = pd.merge(df_eff, df_sig, on=['ts_key', 'symbol'], how='left', suffixes=('', '_sig'))
    
    return df

def calculate_price_metrics(df):
    """Calculate additional price movement metrics"""
    df_completed = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    # Max favorable movement (how far price went in our direction)
    df_completed['max_favorable_pct'] = np.where(
        df_completed['verdict'] == 'BUY',
        (df_completed['highest_reached'] - df_completed['entry_price']) / df_completed['entry_price'] * 100,
        (df_completed['entry_price'] - df_completed['lowest_reached']) / df_completed['entry_price'] * 100
    )
    
    # Max adverse movement (how far price went against us)
    df_completed['max_adverse_pct'] = np.where(
        df_completed['verdict'] == 'BUY',
        (df_completed['entry_price'] - df_completed['lowest_reached']) / df_completed['entry_price'] * 100,
        (df_completed['highest_reached'] - df_completed['entry_price']) / df_completed['entry_price'] * 100
    )
    
    # Price volatility during signal
    df_completed['price_volatility'] = df_completed['max_favorable_pct'] + df_completed['max_adverse_pct']
    
    # Target achievement rate
    df_completed['target_min_achieved'] = np.where(
        df_completed['target_min'] > 0,
        df_completed['max_favorable_pct'] >= (df_completed['target_min'] - df_completed['entry_price']).abs() / df_completed['entry_price'] * 100,
        np.nan
    )
    
    return df_completed

def analyze_profit_correlations(df):
    """Analyze correlation between parameters and profit size"""
    print("="*80)
    print("КОРРЕЛЯЦИЯ ПАРАМЕТРОВ С РАЗМЕРОМ ПРОФИТА (profit_pct)")
    print("="*80)
    
    # Parameters to analyze
    params = {
        'score': 'Общий Score',
        'confidence': 'Confidence',
        'oi_change': 'OI Change',
        'rsi': 'RSI',
        'cvd_strength': 'CVD Strength',
        'volume_ratio': 'Volume Ratio',
        'ttl_minutes': 'TTL Duration',
        'volume_spike': 'Volume Spike',
        'liq_long': 'Long Liquidations',
        'liq_short': 'Short Liquidations'
    }
    
    correlations = []
    
    print("\nПараметр              | Корр. | P-value | Значимость | Направление")
    print("-"*80)
    
    for param, label in params.items():
        if param in df.columns:
            # Filter out NaN values and convert to numeric
            valid_data = df[[param, 'profit_pct']].copy()
            valid_data[param] = pd.to_numeric(valid_data[param], errors='coerce')
            valid_data['profit_pct'] = pd.to_numeric(valid_data['profit_pct'], errors='coerce')
            valid_data = valid_data.dropna()
            
            if len(valid_data) > 5:
                corr, p_value = stats.pearsonr(valid_data[param].astype(float), valid_data['profit_pct'].astype(float))
                
                # Significance
                if p_value < 0.01:
                    significance = "***"
                elif p_value < 0.05:
                    significance = "**"
                elif p_value < 0.10:
                    significance = "*"
                else:
                    significance = "n.s."
                
                # Strength
                if abs(corr) > 0.3:
                    strength = "СИЛЬНАЯ"
                elif abs(corr) > 0.15:
                    strength = "Средняя"
                else:
                    strength = "Слабая"
                
                # Direction
                direction = "↑ Больше=Выше прибыль" if corr > 0 else "↓ Больше=Ниже прибыль"
                
                correlations.append((param, label, corr, p_value))
                print(f"{label:20s} | {corr:+.3f} | {p_value:.4f} | {significance:10s} | {direction}")
    
    print("\nЛегенда значимости: *** p<0.01 (высокая), ** p<0.05 (средняя), * p<0.10 (низкая), n.s. (не значима)")
    
    return correlations

def analyze_movement_strength(df):
    """Analyze correlation with maximum favorable movement"""
    print("\n" + "="*80)
    print("КОРРЕЛЯЦИЯ С МАКСИМАЛЬНЫМ ДВИЖЕНИЕМ В НАШУ СТОРОНУ")
    print("="*80)
    
    params = ['score', 'confidence', 'oi_change', 'rsi', 'cvd_strength', 'volume_ratio', 'ttl_minutes']
    
    print("\nПараметр              | Корр. | P-value | Интерпретация")
    print("-"*80)
    
    for param in params:
        if param in df.columns:
            valid_data = df[[param, 'max_favorable_pct']].copy()
            valid_data[param] = pd.to_numeric(valid_data[param], errors='coerce')
            valid_data['max_favorable_pct'] = pd.to_numeric(valid_data['max_favorable_pct'], errors='coerce')
            valid_data = valid_data.dropna()
            
            if len(valid_data) > 5:
                corr, p_value = stats.pearsonr(valid_data[param].astype(float), valid_data['max_favorable_pct'].astype(float))
                
                if abs(corr) > 0.2 and p_value < 0.1:
                    interpretation = "✅ Предсказывает силу движения"
                elif abs(corr) < 0.1:
                    interpretation = "➖ Не влияет на движение"
                else:
                    interpretation = "⚠️ Слабое влияние"
                
                print(f"{param:20s} | {corr:+.3f} | {p_value:.4f} | {interpretation}")

def analyze_volatility_patterns(df):
    """Analyze which parameters predict high volatility"""
    print("\n" + "="*80)
    print("ПРЕДИКТОРЫ ВОЛАТИЛЬНОСТИ")
    print("="*80)
    
    params = ['score', 'confidence', 'oi_change', 'cvd_strength', 'volume_ratio']
    
    print("\nПараметр              | Корр. | Интерпретация")
    print("-"*80)
    
    for param in params:
        if param in df.columns:
            valid_data = df[[param, 'price_volatility']].copy()
            valid_data[param] = pd.to_numeric(valid_data[param], errors='coerce')
            valid_data['price_volatility'] = pd.to_numeric(valid_data['price_volatility'], errors='coerce')
            valid_data = valid_data.dropna()
            
            if len(valid_data) > 5:
                corr, p_value = stats.pearsonr(valid_data[param].astype(float), valid_data['price_volatility'].astype(float))
                
                if corr > 0.2 and p_value < 0.1:
                    interpretation = "📊 Высокое значение → Высокая волатильность"
                elif corr < -0.2 and p_value < 0.1:
                    interpretation = "📉 Высокое значение → Низкая волатильность"
                else:
                    interpretation = "➖ Не влияет на волатильность"
                
                print(f"{param:20s} | {corr:+.3f} | {interpretation}")

def analyze_by_profit_quartiles(df):
    """Analyze parameter distributions across profit quartiles"""
    print("\n" + "="*80)
    print("АНАЛИЗ ПО КВАРТИЛЯМ ПРИБЫЛИ")
    print("="*80)
    
    # Create profit quartiles
    df['profit_quartile'] = pd.qcut(df['profit_pct'], q=4, labels=['Q1_Worst', 'Q2_Below_Avg', 'Q3_Above_Avg', 'Q4_Best'])
    
    params = ['score', 'confidence', 'oi_change', 'rsi']
    
    print("\nСредние значения параметров по квартилям прибыли:")
    print("-"*80)
    
    for param in params:
        if param in df.columns:
            print(f"\n{param}:")
            quartile_means = df.groupby('profit_quartile')[param].agg(['mean', 'median', 'count'])
            
            for quartile in ['Q1_Worst', 'Q2_Below_Avg', 'Q3_Above_Avg', 'Q4_Best']:
                if quartile in quartile_means.index:
                    mean = quartile_means.loc[quartile, 'mean']
                    median = quartile_means.loc[quartile, 'median']
                    count = quartile_means.loc[quartile, 'count']
                    print(f"  {quartile:15s}: mean={mean:7.2f}, median={median:7.2f}, n={count}")

def analyze_target_achievement(df):
    """Analyze what predicts target achievement"""
    print("\n" + "="*80)
    print("ДОСТИЖЕНИЕ ЦЕЛЕВЫХ УРОВНЕЙ")
    print("="*80)
    
    # Filter signals with valid targets
    df_with_targets = df[df['target_min_achieved'].notna()].copy()
    
    if len(df_with_targets) > 0:
        achieved = df_with_targets['target_min_achieved'].sum()
        total = len(df_with_targets)
        
        print(f"\nЦель достигнута: {achieved}/{total} ({achieved/total*100:.1f}%)")
        
        # Compare parameters between achieved and not achieved
        params = ['score', 'confidence', 'oi_change', 'cvd_strength']
        
        print("\nСравнение параметров (Достигли vs Не достигли):")
        print("-"*80)
        
        for param in params:
            if param in df_with_targets.columns:
                achieved_mean = df_with_targets[df_with_targets['target_min_achieved'] == True][param].mean()
                not_achieved_mean = df_with_targets[df_with_targets['target_min_achieved'] == False][param].mean()
                diff_pct = (achieved_mean - not_achieved_mean) / not_achieved_mean * 100 if not_achieved_mean != 0 else 0
                
                print(f"{param:20s}: Достигли={achieved_mean:7.2f} | Не достигли={not_achieved_mean:7.2f} | Разница={diff_pct:+6.1f}%")

def analyze_direction_specific_correlations(df):
    """Analyze correlations separately for BUY and SELL"""
    print("\n" + "="*80)
    print("КОРРЕЛЯЦИИ ОТДЕЛЬНО ДЛЯ BUY И SELL")
    print("="*80)
    
    params = ['score', 'confidence', 'oi_change', 'rsi']
    
    for direction in ['BUY', 'SELL']:
        df_dir = df[df['verdict'] == direction]
        
        if len(df_dir) > 5:
            print(f"\n{direction} сигналы (n={len(df_dir)}):")
            print("-"*80)
            
            for param in params:
                if param in df_dir.columns:
                    valid_data = df_dir[[param, 'profit_pct']].copy()
                    valid_data[param] = pd.to_numeric(valid_data[param], errors='coerce')
                    valid_data['profit_pct'] = pd.to_numeric(valid_data['profit_pct'], errors='coerce')
                    valid_data = valid_data.dropna()
                    
                    if len(valid_data) > 3:
                        corr, p_value = stats.pearsonr(valid_data[param].astype(float), valid_data['profit_pct'].astype(float))
                        sig = "✅" if p_value < 0.1 else "➖"
                        print(f"  {param:20s}: {corr:+.3f} (p={p_value:.3f}) {sig}")

def find_best_combinations(df):
    """Find parameter combinations that predict highest profits"""
    print("\n" + "="*80)
    print("ОПТИМАЛЬНЫЕ КОМБИНАЦИИ ПАРАМЕТРОВ")
    print("="*80)
    
    # High OI change combinations
    print("\nВысокий OI Change (>0) комбинации:")
    print("-"*80)
    
    high_oi = df[df['oi_change'] > 0]
    
    conditions = [
        ('RSI < 40 (Oversold)', high_oi[high_oi['rsi'] < 40]),
        ('RSI > 60 (Overbought)', high_oi[high_oi['rsi'] > 60]),
        ('Confidence < 70%', high_oi[high_oi['confidence'] < 0.70]),
        ('Confidence > 70%', high_oi[high_oi['confidence'] >= 0.70]),
    ]
    
    for label, subset in conditions:
        if len(subset) > 2:
            avg_profit = subset['profit_pct'].mean()
            win_rate = (subset['result'] == 'WIN').sum() / len(subset) * 100
            print(f"{label:25s}: n={len(subset):2d}, WR={win_rate:5.1f}%, Avg Profit={avg_profit:+6.2f}%")
    
    # Low confidence but high OI
    print("\nНизкая Confidence (<70%) + Высокий OI:")
    low_conf_high_oi = df[(df['confidence'] < 0.70) & (df['oi_change'] > 0)]
    if len(low_conf_high_oi) > 0:
        avg_profit = low_conf_high_oi['profit_pct'].mean()
        win_rate = (low_conf_high_oi['result'] == 'WIN').sum() / len(low_conf_high_oi) * 100
        print(f"  Сигналов: {len(low_conf_high_oi)}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg Profit: {avg_profit:+.2f}%")

def generate_actionable_insights(correlations, df):
    """Generate specific actionable recommendations"""
    print("\n" + "="*80)
    print("КОНКРЕТНЫЕ РЕКОМЕНДАЦИИ НА ОСНОВЕ ДАННЫХ")
    print("="*80)
    
    # Sort correlations by absolute value
    sorted_corr = sorted(correlations, key=lambda x: abs(x[2]), reverse=True)
    
    print("\n1. ПРИОРИТЕТНЫЕ ПАРАМЕТРЫ ДЛЯ МОДЕЛИ:")
    print("-"*80)
    for param, label, corr, p_value in sorted_corr[:5]:
        if p_value < 0.1:
            if corr > 0:
                action = f"Увеличить вес - коррелирует с прибылью ({corr:+.3f})"
            else:
                action = f"Пересмотреть использование - отрицательная корреляция ({corr:+.3f})"
            print(f"  • {label:20s}: {action}")
    
    # Confidence paradox analysis
    print("\n2. ПРОБЛЕМА CONFIDENCE:")
    print("-"*80)
    high_conf = df[df['confidence'] >= 0.80]
    low_conf = df[(df['confidence'] >= 0.50) & (df['confidence'] < 0.70)]
    
    if len(high_conf) > 0 and len(low_conf) > 0:
        high_conf_profit = high_conf['profit_pct'].mean()
        low_conf_profit = low_conf['profit_pct'].mean()
        
        print(f"  Высокая confidence (80-100%): {high_conf_profit:+.2f}% средний профит")
        print(f"  Низкая confidence (50-70%):   {low_conf_profit:+.2f}% средний профит")
        
        if low_conf_profit > high_conf_profit:
            print("  ⚠️  КРИТИЧЕСКАЯ ПРОБЛЕМА: Низкая confidence дает лучшие результаты!")
            print("  → Формула confidence работает НАОБОРОТ")
            print("  → Рекомендация: Инвертировать или полностью пересчитать")
    
    # Best parameter ranges
    print("\n3. ОПТИМАЛЬНЫЕ ДИАПАЗОНЫ ПАРАМЕТРОВ:")
    print("-"*80)
    
    # OI Change optimal range
    if 'oi_change' in df.columns:
        oi_positive = df[df['oi_change'] > 0]
        oi_negative = df[df['oi_change'] <= 0]
        
        if len(oi_positive) > 0 and len(oi_negative) > 0:
            pos_profit = oi_positive['profit_pct'].mean()
            neg_profit = oi_negative['profit_pct'].mean()
            
            print(f"  OI Change > 0: {pos_profit:+.2f}% (n={len(oi_positive)})")
            print(f"  OI Change ≤ 0: {neg_profit:+.2f}% (n={len(oi_negative)})")
            
            if pos_profit > neg_profit:
                print("  → Рекомендация: Требовать OI Change > 0 для всех сигналов")
    
    # RSI optimal ranges
    if 'rsi' in df.columns:
        rsi_oversold = df[df['rsi'] < 40]
        rsi_neutral = df[(df['rsi'] >= 40) & (df['rsi'] <= 60)]
        rsi_overbought = df[df['rsi'] > 60]
        
        print(f"\n  RSI < 40 (Oversold):   {rsi_oversold['profit_pct'].mean():+.2f}% (n={len(rsi_oversold)})")
        print(f"  RSI 40-60 (Neutral):   {rsi_neutral['profit_pct'].mean():+.2f}% (n={len(rsi_neutral)})")
        print(f"  RSI > 60 (Overbought): {rsi_overbought['profit_pct'].mean():+.2f}% (n={len(rsi_overbought)})")

def main():
    print("="*80)
    print("ГЛУБОКИЙ АНАЛИЗ ДВИЖЕНИЯ ЦЕН И КОРРЕЛЯЦИЙ")
    print("="*80)
    print(f"Дата среза: {TRAINING_CUTOFF}")
    print(f"Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    print("Загрузка данных...")
    df = load_and_merge_data()
    df_completed = calculate_price_metrics(df)
    
    print(f"Завершенных сигналов для анализа: {len(df_completed)}")
    print(f"  WIN: {(df_completed['result'] == 'WIN').sum()}")
    print(f"  LOSS: {(df_completed['result'] == 'LOSS').sum()}")
    print()
    
    # Run analyses
    correlations = analyze_profit_correlations(df_completed)
    analyze_movement_strength(df_completed)
    analyze_volatility_patterns(df_completed)
    analyze_by_profit_quartiles(df_completed)
    analyze_target_achievement(df_completed)
    analyze_direction_specific_correlations(df_completed)
    find_best_combinations(df_completed)
    generate_actionable_insights(correlations, df_completed)
    
    print("\n" + "="*80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*80)
    print("\nСледующие шаги:")
    print("  1. Применить найденные оптимальные диапазоны параметров")
    print("  2. Пересчитать формулу confidence на основе корреляций")
    print("  3. Увеличить вес параметров с высокой корреляцией")
    print("  4. Собрать больше данных для валидации (цель: 100+ сигналов)")

if __name__ == '__main__':
    main()
