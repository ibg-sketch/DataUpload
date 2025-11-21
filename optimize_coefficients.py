#!/usr/bin/env python3
"""
Optimize multiplier coefficients using linear regression on historical data.
Finds data-driven values instead of heuristic 1.3, 1.2, 1.15, etc.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import train_test_split
import json

def load_and_prep_data():
    """Load effectiveness data and prepare features"""
    print("Loading data...")
    eff = pd.read_csv('effectiveness_log.csv')
    eff['timestamp_sent'] = pd.to_datetime(eff['timestamp_sent'])
    
    # Filter only traded signals
    traded = eff[eff['result'].isin(['WIN', 'LOSS'])].copy()
    
    print(f"Loaded {len(traded)} traded signals")
    print(f"Columns: {list(traded.columns)}")
    
    return traded

def analyze_current_coefficients(traded):
    """Analyze if current coefficient thresholds make sense"""
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ ТЕКУЩИХ ПОРОГОВЫХ ЗНАЧЕНИЙ")
    print("=" * 80)
    
    # We don't have raw CVD/OI/Volume ratios in effectiveness_log
    # But we can analyze market_strength if it exists
    if 'market_strength' in traded.columns:
        print("\n💪 Market Strength распределение:")
        print(traded['market_strength'].describe())
        
        # Binned analysis
        traded['ms_bin'] = pd.qcut(traded['market_strength'], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
        
        print("\n📈 Profit по квартилям Market Strength:")
        for bin_name in ['Q1', 'Q2', 'Q3', 'Q4']:
            bin_data = traded[traded['ms_bin'] == bin_name]
            if len(bin_data) > 0:
                avg_profit = bin_data['profit_pct'].mean()
                win_rate = (bin_data['result'] == 'WIN').mean() * 100
                print(f"   {bin_name}: {len(bin_data):4d} signals | Avg profit: {avg_profit:+.2f}% | WR: {win_rate:.1f}%")
    
    # Check if we have confidence
    if 'confidence' in traded.columns:
        print("\n💎 Confidence распределение:")
        print(traded['confidence'].describe())
        
        # Correlation with profit
        corr = traded['confidence'].corr(traded['profit_pct'])
        print(f"\n📈 Корреляция Confidence vs Profit: {corr:.4f}")

def recommend_coefficients(traded):
    """
    Since we don't have raw CVD/OI/Volume ratios in effectiveness_log,
    we'll provide recommendations based on what we CAN analyze.
    """
    print("\n" + "=" * 80)
    print("💡 РЕКОМЕНДАЦИИ")
    print("=" * 80)
    
    print("\n⚠️  ОГРАНИЧЕНИЕ:")
    print("   effectiveness_log.csv не содержит промежуточных значений")
    print("   (cvd_ratio, oi_change_pct, volume_ratio, vwap_dev_pct)")
    print("   Поэтому не можем точно оптимизировать коэффициенты регрессией.")
    
    print("\n✅ ЧТО МОЖЕМ СДЕЛАТЬ:")
    print("   1. Проанализировать текущий multiplier (market_strength)")
    print("   2. Найти оптимальный cap для multiplier")
    print("   3. Предложить стратегию для сбора данных")
    
    if 'market_strength' in traded.columns:
        # Find optimal cap
        traded_sorted = traded.sort_values('market_strength')
        
        # Test different caps
        print("\n🔧 Тестирование разных CAP значений для multiplier:")
        print(f"{'Cap Value':<12} {'Signals':>10} {'Avg Profit':>12} {'Win Rate':>10}")
        print("-" * 50)
        
        for cap in [1.2, 1.4, 1.6, 1.8, 2.0, 2.5]:
            capped_data = traded[traded['market_strength'] <= cap]
            if len(capped_data) > 0:
                avg_profit = capped_data['profit_pct'].mean()
                win_rate = (capped_data['result'] == 'WIN').mean() * 100
                print(f"{cap:<12.1f} {len(capped_data):>10} {avg_profit:>11.2f}% {win_rate:>9.1f}%")
        
        # Find best cap (maximize avg profit)
        best_cap = None
        best_profit = -999
        for cap in np.arange(1.0, 3.0, 0.1):
            capped_data = traded[traded['market_strength'] <= cap]
            if len(capped_data) >= 50:  # Need enough samples
                avg_profit = capped_data['profit_pct'].mean()
                if avg_profit > best_profit:
                    best_profit = avg_profit
                    best_cap = cap
        
        if best_cap:
            print(f"\n✅ РЕКОМЕНДУЕМЫЙ CAP: {best_cap:.1f}")
            print(f"   При этом cap средняя прибыль: {best_profit:+.2f}%")

def main():
    print("\n" + "=" * 80)
    print("🔬 ОПТИМИЗАЦИЯ КОЭФФИЦИЕНТОВ MULTIPLIER")
    print("=" * 80)
    
    try:
        traded = load_and_prep_data()
        
        if len(traded) == 0:
            print("❌ Нет данных для анализа")
            return
        
        analyze_current_coefficients(traded)
        recommend_coefficients(traded)
        
        print("\n" + "=" * 80)
        print("📌 NEXT STEPS:")
        print("=" * 80)
        print("1. Текущие исправления (двойной учёт, VWAP) уже внесены")
        print("2. Нужно собрать данные с новыми формулами (24-48ч)")
        print("3. Затем можем точно оптимизировать коэффициенты")
        print("4. Пока используем консервативные значения из кода")
        print("\n✅ Рекомендация: Оставить текущие коэффициенты до накопления новых данных")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
