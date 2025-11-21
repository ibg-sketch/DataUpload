#!/usr/bin/env python3
"""
Analyze which components of the score/confidence formula are creating the inverse correlation
"""

import pandas as pd
import numpy as np
from scipy import stats

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def load_data():
    """Load signals data with component flags"""
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_sig = pd.read_csv('signals_log.csv')
    
    # Filter to new data
    df_eff = df_eff[df_eff['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    
    # Merge
    df_eff['ts_key'] = pd.to_datetime(df_eff['timestamp_sent']).dt.strftime('%Y-%m-%d %H:%M')
    df_sig['ts_key'] = pd.to_datetime(df_sig['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    df = pd.merge(df_eff, df_sig, on=['ts_key', 'symbol'], how='left', suffixes=('', '_sig'))
    
    # Filter completed only
    df = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    return df

def analyze_score_components_correlation(df):
    """Analyze which score components correlate with profit"""
    print("="*80)
    print("АНАЛИЗ КОМПОНЕНТОВ SCORE - ЧТО ПОРТИТ ФОРМУЛУ?")
    print("="*80)
    
    # Component flags from signals_log.csv
    components = {
        'has_cvd_signal': 'CVD Signal',
        'has_oi_signal': 'OI Signal',
        'has_vwap_signal': 'VWAP Signal',
        'has_ema_signal': 'EMA Signal',
        'has_rsi_signal': 'RSI Signal'
    }
    
    print("\nКомпонент           | Частота | WIN когда есть | WIN когда нет | Влияние")
    print("-"*80)
    
    component_analysis = []
    
    for comp_col, comp_name in components.items():
        if comp_col in df.columns:
            # Convert to numeric
            df[comp_col] = pd.to_numeric(df[comp_col], errors='coerce')
            
            # Calculate stats
            with_comp = df[df[comp_col] == 1]
            without_comp = df[df[comp_col] == 0]
            
            if len(with_comp) > 0 and len(without_comp) > 0:
                freq = len(with_comp) / len(df) * 100
                
                wr_with = (with_comp['result'] == 'WIN').sum() / len(with_comp) * 100
                wr_without = (without_comp['result'] == 'WIN').sum() / len(without_comp) * 100
                
                profit_with = with_comp['profit_pct'].mean()
                profit_without = without_comp['profit_pct'].mean()
                
                impact = "✅ Положительное" if wr_with > wr_without else "❌ Отрицательное"
                
                component_analysis.append({
                    'component': comp_name,
                    'freq': freq,
                    'wr_with': wr_with,
                    'wr_without': wr_without,
                    'profit_with': profit_with,
                    'profit_without': profit_without,
                    'impact': wr_with - wr_without
                })
                
                print(f"{comp_name:18s} | {freq:5.1f}% | {wr_with:13.1f}% | {wr_without:12.1f}% | {impact}")
    
    return component_analysis

def analyze_score_vs_components(df):
    """Analyze how score relates to actual performance"""
    print("\n" + "="*80)
    print("РАЗБИВКА SCORE ПО КОМПОНЕНТАМ")
    print("="*80)
    
    # Group by number of active components
    component_cols = ['has_cvd_signal', 'has_oi_signal', 'has_vwap_signal', 
                      'has_ema_signal', 'has_rsi_signal']
    
    available_cols = [col for col in component_cols if col in df.columns]
    
    if len(available_cols) > 0:
        # Convert to numeric
        for col in available_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Count active components
        df['num_components'] = df[available_cols].sum(axis=1)
        
        print("\nКол-во компонентов | Сигналов | WIN Rate | Avg Profit | Avg Score | Avg Conf")
        print("-"*80)
        
        for num_comp in sorted(df['num_components'].unique()):
            subset = df[df['num_components'] == num_comp]
            if len(subset) > 0:
                wins = (subset['result'] == 'WIN').sum()
                wr = wins / len(subset) * 100
                avg_profit = subset['profit_pct'].mean()
                avg_score = subset['score'].mean() if 'score' in subset.columns else 0
                avg_conf = subset['confidence'].mean()
                
                print(f"{num_comp:18.0f} | {len(subset):8d} | {wr:8.1f}% | {avg_profit:+9.2f}% | {avg_score:9.2f} | {avg_conf:8.2%}")

def analyze_problematic_combinations(df):
    """Find which combinations of components lead to high confidence but low win rate"""
    print("\n" + "="*80)
    print("ПРОБЛЕМНЫЕ КОМБИНАЦИИ - Высокая Confidence, Низкий WR")
    print("="*80)
    
    # High confidence but lost
    high_conf_loss = df[(df['confidence'] >= 0.70) & (df['result'] == 'LOSS')]
    
    if len(high_conf_loss) > 0:
        print(f"\nВысокая confidence (≥70%) но LOSS: {len(high_conf_loss)} сигналов")
        print("\nХарактеристики этих сигналов:")
        
        component_cols = ['has_cvd_signal', 'has_oi_signal', 'has_vwap_signal', 
                          'has_ema_signal', 'has_rsi_signal']
        
        for col in component_cols:
            if col in high_conf_loss.columns:
                high_conf_loss[col] = pd.to_numeric(high_conf_loss[col], errors='coerce').fillna(0)
                freq = (high_conf_loss[col] == 1).sum() / len(high_conf_loss) * 100
                print(f"  {col:20s}: {freq:5.1f}% имеют этот компонент")
        
        print(f"\n  Средний score: {high_conf_loss['score'].mean():.2f}")
        print(f"  Средний OI change: {high_conf_loss['oi_change'].mean():.0f}")
        print(f"  Средний RSI: {high_conf_loss['rsi'].mean():.1f}")
    
    # Low confidence but won
    low_conf_win = df[(df['confidence'] < 0.70) & (df['result'] == 'WIN')]
    
    if len(low_conf_win) > 0:
        print(f"\n" + "="*80)
        print(f"Низкая confidence (<70%) но WIN: {len(low_conf_win)} сигналов")
        print("\nХарактеристики этих сигналов:")
        
        for col in component_cols:
            if col in low_conf_win.columns:
                low_conf_win[col] = pd.to_numeric(low_conf_win[col], errors='coerce').fillna(0)
                freq = (low_conf_win[col] == 1).sum() / len(low_conf_win) * 100
                print(f"  {col:20s}: {freq:5.1f}% имеют этот компонент")
        
        print(f"\n  Средний score: {low_conf_win['score'].mean():.2f}")
        print(f"  Средний OI change: {low_conf_win['oi_change'].mean():.0f}")
        print(f"  Средний RSI: {low_conf_win['rsi'].mean():.1f}")

def identify_root_cause(component_analysis, df):
    """Identify the root cause of inverse confidence correlation"""
    print("\n" + "="*80)
    print("КОРНЕВАЯ ПРИЧИНА ПРОБЛЕМЫ")
    print("="*80)
    
    # Sort components by impact
    sorted_comps = sorted(component_analysis, key=lambda x: x['impact'], reverse=True)
    
    print("\nКомпоненты отсортированные по влиянию на WR:")
    print("-"*80)
    for comp in sorted_comps:
        impact_str = f"{comp['impact']:+.1f}%"
        profit_str = f"{comp['profit_with']:+.2f}% vs {comp['profit_without']:+.2f}%"
        print(f"{comp['component']:18s}: WR Impact={impact_str:8s} | Profit: {profit_str}")
    
    # Find negative impact components
    negative_comps = [c for c in sorted_comps if c['impact'] < 0]
    
    if negative_comps:
        print("\n⚠️ НАЙДЕНЫ КОМПОНЕНТЫ С ОТРИЦАТЕЛЬНЫМ ВЛИЯНИЕМ:")
        for comp in negative_comps:
            print(f"  • {comp['component']}: Снижает WR на {abs(comp['impact']):.1f}%")
            print(f"    → Profit с компонентом: {comp['profit_with']:+.2f}%")
            print(f"    → Profit без компонента: {comp['profit_without']:+.2f}%")
            print(f"    → Частота: {comp['freq']:.1f}% сигналов")
    
    # Check score correlation
    if 'score' in df.columns:
        df['score_num'] = pd.to_numeric(df['score'], errors='coerce')
        df['profit_num'] = pd.to_numeric(df['profit_pct'], errors='coerce')
        valid = df[['score_num', 'profit_num']].dropna()
        
        if len(valid) > 5:
            corr, p_val = stats.pearsonr(valid['score_num'], valid['profit_num'])
            
            print(f"\n📊 Score ↔ Profit корреляция: {corr:+.3f} (p={p_val:.4f})")
            
            if corr < 0:
                print("   ⚠️ ПРОБЛЕМА: Чем выше score, тем ниже прибыль!")
                print("   Причина: В score входят компоненты с отрицательным влиянием")
    
    # Recommendation
    print("\n" + "="*80)
    print("РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("="*80)
    
    if negative_comps:
        print("\n1. УБРАТЬ ИЗ SCORE компоненты с отрицательным влиянием:")
        for comp in negative_comps:
            print(f"   • {comp['component']}")
    
    print("\n2. ПЕРЕСМОТРЕТЬ ВЕСА компонентов на основе корреляции с прибылью:")
    print("   • Компоненты с положительным влиянием → увеличить вес")
    print("   • Компоненты с отрицательным влиянием → убрать или инвертировать")
    
    print("\n3. АЛЬТЕРНАТИВНЫЙ ПОДХОД:")
    print("   • Использовать только OI change + RSI для расчета confidence")
    print("   • OI > 0: базовая confidence 60%")
    print("   • RSI оптимальный (40-50 для BUY, 50-60 для SELL): +10%")
    print("   • Прочие индикаторы: меньший вес или вообще убрать")

def main():
    print("="*80)
    print("АНАЛИЗ КОМПОНЕНТОВ ФОРМУЛЫ CONFIDENCE")
    print("="*80)
    print(f"Цель: Найти, какие компоненты score создают обратную корреляцию")
    print()
    
    df = load_data()
    print(f"Загружено завершенных сигналов: {len(df)}")
    print(f"  WIN: {(df['result'] == 'WIN').sum()}")
    print(f"  LOSS: {(df['result'] == 'LOSS').sum()}")
    print()
    
    component_analysis = analyze_score_components_correlation(df)
    analyze_score_vs_components(df)
    analyze_problematic_combinations(df)
    identify_root_cause(component_analysis, df)
    
    print("\n" + "="*80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*80)

if __name__ == '__main__':
    main()
