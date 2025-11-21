#!/usr/bin/env python3
"""
Test three approaches to fix the inverse confidence correlation
Compare results on actual signal data
"""

import pandas as pd
import numpy as np
from datetime import datetime

TRAINING_CUTOFF = "2025-11-04 12:21:00"

def load_data():
    """Load and merge data"""
    df_eff = pd.read_csv('effectiveness_log.csv')
    df_sig = pd.read_csv('signals_log.csv')
    
    df_eff = df_eff[df_eff['timestamp_sent'] >= TRAINING_CUTOFF].copy()
    
    df_eff['ts_key'] = pd.to_datetime(df_eff['timestamp_sent']).dt.strftime('%Y-%m-%d %H:%M')
    df_sig['ts_key'] = pd.to_datetime(df_sig['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    
    df = pd.merge(df_eff, df_sig, on=['ts_key', 'symbol'], how='left', suffixes=('', '_sig'))
    df = df[df['result'].isin(['WIN', 'LOSS'])].copy()
    
    # Convert to numeric
    df['oi_change'] = pd.to_numeric(df['oi_change'], errors='coerce')
    df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df['profit_pct'] = pd.to_numeric(df['profit_pct'], errors='coerce')
    
    return df

def test_variant_1_oi_required(df):
    """Variant 1: Require OI > 0 for all signals"""
    print("="*80)
    print("ВАРИАНТ 1: ТРЕБОВАТЬ OI > 0")
    print("="*80)
    
    # Filter signals with positive OI
    df_filtered = df[df['oi_change'] > 0].copy()
    
    print(f"\nИсходных сигналов: {len(df)}")
    print(f"После фильтра OI > 0: {len(df_filtered)} ({len(df_filtered)/len(df)*100:.1f}%)")
    print(f"Отфильтровано: {len(df) - len(df_filtered)} сигналов")
    
    # Stats before filter
    wins_before = (df['result'] == 'WIN').sum()
    wr_before = wins_before / len(df) * 100
    profit_before = df['profit_pct'].mean()
    
    # Stats after filter
    if len(df_filtered) > 0:
        wins_after = (df_filtered['result'] == 'WIN').sum()
        wr_after = wins_after / len(df_filtered) * 100
        profit_after = df_filtered['profit_pct'].mean()
        
        print(f"\nПЕРФОРМАНС:")
        print(f"  До фильтра:    WR={wr_before:5.1f}% | Profit={profit_before:+.2f}%")
        print(f"  После фильтра: WR={wr_after:5.1f}% | Profit={profit_after:+.2f}%")
        print(f"  Улучшение WR:  {wr_after - wr_before:+.1f}%")
        print(f"  Улучшение Profit: {profit_after - profit_before:+.2f}%")
        
        # Check confidence correlation after filter
        from scipy import stats
        valid = df_filtered[['confidence', 'profit_pct']].dropna()
        if len(valid) > 5:
            corr, p_val = stats.pearsonr(valid['confidence'], valid['profit_pct'])
            print(f"\n  Корреляция Confidence ↔ Profit: {corr:+.3f} (p={p_val:.4f})")
            if corr > 0:
                print(f"  ✅ Корреляция стала ПОЛОЖИТЕЛЬНОЙ!")
            else:
                print(f"  ⚠️  Корреляция всё ещё отрицательная")
        
        return {
            'name': 'Вариант 1: OI > 0 обязателен',
            'signals_kept': len(df_filtered),
            'signals_pct': len(df_filtered)/len(df)*100,
            'win_rate': wr_after,
            'avg_profit': profit_after,
            'wr_improvement': wr_after - wr_before,
            'profit_improvement': profit_after - profit_before,
            'conf_corr': corr if len(valid) > 5 else None
        }
    
    return None

def test_variant_2_increase_oi_weight(df):
    """Variant 2: Increase OI weight in score calculation"""
    print("\n" + "="*80)
    print("ВАРИАНТ 2: УВЕЛИЧИТЬ ВЕС OI В 2 РАЗА")
    print("="*80)
    
    # Simulate recalculation of score with 2x OI weight
    # Current formula: score includes OI with weight 1.0
    # New formula: OI with weight 2.0
    
    # Estimate new score (rough approximation)
    # If OI was positive: score += 1.0 extra
    # If OI was negative: score -= 1.0 extra
    
    df_variant2 = df.copy()
    
    # Adjust score based on OI direction
    oi_adjustment = np.where(df_variant2['oi_change'] > 0, 1.0, -1.0)
    df_variant2['score_new'] = df_variant2['score'] + oi_adjustment
    
    # Recalculate confidence using same formula
    # confidence = 0.40 + (score_margin * 0.40) for SELL
    # confidence = 0.25 + (score_margin * 0.40) for BUY
    
    # Estimate min_score and max_score
    # Typical: min_score = 60% of max, max = sum of all weights
    # Old: ~4.0 max (if 4 indicators), min = 2.4
    # New: ~5.0 max (OI weight doubled), min = 3.0
    
    def recalc_confidence(row):
        score = row['score_new']
        verdict = row['verdict']
        
        # Estimated thresholds
        min_score = 3.0  # ~60% of 5.0
        max_score = 5.0
        
        if score < min_score:
            return 0.0
        
        score_margin = (score - min_score) / (max_score - min_score)
        
        if verdict == 'SELL':
            conf = 0.40 + (score_margin * 0.40)
            return max(0.40, min(0.80, conf))
        else:
            conf = 0.25 + (score_margin * 0.40)
            return max(0.25, min(0.65, conf))
    
    df_variant2['confidence_new'] = df_variant2.apply(recalc_confidence, axis=1)
    
    # Filter signals that still pass threshold
    df_filtered = df_variant2[df_variant2['confidence_new'] > 0].copy()
    
    print(f"\nИсходных сигналов: {len(df)}")
    print(f"После пересчета с OI×2: {len(df_filtered)} ({len(df_filtered)/len(df)*100:.1f}%)")
    
    # Stats
    wins_before = (df['result'] == 'WIN').sum()
    wr_before = wins_before / len(df) * 100
    profit_before = df['profit_pct'].mean()
    
    if len(df_filtered) > 0:
        wins_after = (df_filtered['result'] == 'WIN').sum()
        wr_after = wins_after / len(df_filtered) * 100
        profit_after = df_filtered['profit_pct'].mean()
        
        print(f"\nПЕРФОРМАНС:")
        print(f"  До изменений:  WR={wr_before:5.1f}% | Profit={profit_before:+.2f}%")
        print(f"  После OI×2:    WR={wr_after:5.1f}% | Profit={profit_after:+.2f}%")
        print(f"  Улучшение WR:  {wr_after - wr_before:+.1f}%")
        print(f"  Улучшение Profit: {profit_after - profit_before:+.2f}%")
        
        # Check new confidence correlation
        from scipy import stats
        valid = df_filtered[['confidence_new', 'profit_pct']].dropna()
        if len(valid) > 5:
            corr, p_val = stats.pearsonr(valid['confidence_new'], valid['profit_pct'])
            print(f"\n  Корреляция Confidence ↔ Profit: {corr:+.3f} (p={p_val:.4f})")
            if corr > 0:
                print(f"  ✅ Корреляция стала ПОЛОЖИТЕЛЬНОЙ!")
            else:
                print(f"  ⚠️  Корреляция всё ещё отрицательная")
        
        return {
            'name': 'Вариант 2: OI вес ×2',
            'signals_kept': len(df_filtered),
            'signals_pct': len(df_filtered)/len(df)*100,
            'win_rate': wr_after,
            'avg_profit': profit_after,
            'wr_improvement': wr_after - wr_before,
            'profit_improvement': profit_after - profit_before,
            'conf_corr': corr if len(valid) > 5 else None
        }
    
    return None

def test_variant_3_oi_multiplier(df):
    """Variant 3: Add OI multiplier to confidence"""
    print("\n" + "="*80)
    print("ВАРИАНТ 3: OI КАК МНОЖИТЕЛЬ CONFIDENCE")
    print("="*80)
    
    df_variant3 = df.copy()
    
    # Calculate OI multiplier
    def calc_oi_multiplier(oi_change):
        if pd.isna(oi_change):
            return 1.0
        
        if oi_change > 0:
            # Positive OI: boost up to 1.2x
            # Scale: 0 → 1.0, 10M → 1.2
            multiplier = 1.0 + min(0.2, oi_change / 50_000_000)
            return multiplier
        else:
            # Negative OI: penalty to 0.7x
            return 0.7
    
    df_variant3['oi_multiplier'] = df_variant3['oi_change'].apply(calc_oi_multiplier)
    df_variant3['confidence_new'] = df_variant3['confidence'] * df_variant3['oi_multiplier']
    
    # Clamp to valid ranges
    def clamp_confidence(row):
        conf = row['confidence_new']
        verdict = row['verdict']
        
        if verdict == 'SELL':
            return max(0.40, min(0.80, conf))
        else:
            return max(0.25, min(0.65, conf))
    
    df_variant3['confidence_new'] = df_variant3.apply(clamp_confidence, axis=1)
    
    # Filter signals that still meet minimum threshold
    # Use 50% as threshold
    df_filtered = df_variant3[df_variant3['confidence_new'] >= 0.50].copy()
    
    print(f"\nИсходных сигналов: {len(df)}")
    print(f"После OI-множителя: {len(df_filtered)} ({len(df_filtered)/len(df)*100:.1f}%)")
    
    # Stats
    wins_before = (df['result'] == 'WIN').sum()
    wr_before = wins_before / len(df) * 100
    profit_before = df['profit_pct'].mean()
    
    if len(df_filtered) > 0:
        wins_after = (df_filtered['result'] == 'WIN').sum()
        wr_after = wins_after / len(df_filtered) * 100
        profit_after = df_filtered['profit_pct'].mean()
        
        print(f"\nПЕРФОРМАНС:")
        print(f"  До изменений:       WR={wr_before:5.1f}% | Profit={profit_before:+.2f}%")
        print(f"  После OI-множителя: WR={wr_after:5.1f}% | Profit={profit_after:+.2f}%")
        print(f"  Улучшение WR:  {wr_after - wr_before:+.1f}%")
        print(f"  Улучшение Profit: {profit_after - profit_before:+.2f}%")
        
        # Distribution of multipliers
        print(f"\nРаспределение OI множителей:")
        print(f"  0.70 (штраф):   {(df_variant3['oi_multiplier'] == 0.7).sum()} сигналов")
        print(f"  1.00-1.10:      {((df_variant3['oi_multiplier'] >= 1.0) & (df_variant3['oi_multiplier'] < 1.1)).sum()} сигналов")
        print(f"  1.10-1.20:      {(df_variant3['oi_multiplier'] >= 1.1).sum()} сигналов")
        
        # Check new confidence correlation
        from scipy import stats
        valid = df_filtered[['confidence_new', 'profit_pct']].dropna()
        if len(valid) > 5:
            corr, p_val = stats.pearsonr(valid['confidence_new'], valid['profit_pct'])
            print(f"\n  Корреляция Confidence ↔ Profit: {corr:+.3f} (p={p_val:.4f})")
            if corr > 0:
                print(f"  ✅ Корреляция стала ПОЛОЖИТЕЛЬНОЙ!")
            else:
                print(f"  ⚠️  Корреляция всё ещё отрицательная")
        
        return {
            'name': 'Вариант 3: OI-множитель',
            'signals_kept': len(df_filtered),
            'signals_pct': len(df_filtered)/len(df)*100,
            'win_rate': wr_after,
            'avg_profit': profit_after,
            'wr_improvement': wr_after - wr_before,
            'profit_improvement': profit_after - profit_before,
            'conf_corr': corr if len(valid) > 5 else None
        }
    
    return None

def compare_variants(results):
    """Compare all variants and recommend the best"""
    print("\n" + "="*80)
    print("СРАВНЕНИЕ ВСЕХ ВАРИАНТОВ")
    print("="*80)
    
    # Create comparison table
    print("\nВариант                    | Сигналов | WR      | Profit  | Улучш.WR | Улучш.Profit | Корр.Conf")
    print("-"*100)
    
    for r in results:
        if r:
            corr_str = f"{r['conf_corr']:+.3f}" if r['conf_corr'] is not None else "N/A"
            print(f"{r['name']:25s} | {r['signals_kept']:8d} | {r['win_rate']:6.1f}% | {r['avg_profit']:+6.2f}% | {r['wr_improvement']:+8.1f}% | {r['profit_improvement']:+12.2f}% | {corr_str}")
    
    # Determine best variant
    print("\n" + "="*80)
    print("РЕКОМЕНДАЦИЯ")
    print("="*80)
    
    # Score each variant
    scores = []
    for r in results:
        if r:
            score = 0
            # Win rate improvement (most important)
            score += r['wr_improvement'] * 3
            # Profit improvement
            score += r['profit_improvement'] * 10
            # Positive correlation
            if r['conf_corr'] and r['conf_corr'] > 0:
                score += 10
            # Penalty for losing too many signals
            if r['signals_pct'] < 30:
                score -= 20
            
            scores.append((r['name'], score, r))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    
    if scores:
        best = scores[0]
        print(f"\n🏆 ЛУЧШИЙ ВАРИАНТ: {best[0]}")
        print(f"   Общий скор: {best[1]:.1f}")
        print(f"\n   Преимущества:")
        print(f"   • Win Rate: {best[2]['win_rate']:.1f}% (улучшение на {best[2]['wr_improvement']:+.1f}%)")
        print(f"   • Profit: {best[2]['avg_profit']:+.2f}% (улучшение на {best[2]['profit_improvement']:+.2f}%)")
        print(f"   • Сохранено сигналов: {best[2]['signals_pct']:.1f}%")
        if best[2]['conf_corr']:
            corr_status = "положительная ✅" if best[2]['conf_corr'] > 0 else "отрицательная ⚠️"
            print(f"   • Корреляция confidence: {best[2]['conf_corr']:+.3f} ({corr_status})")
        
        print(f"\n   Недостатки:")
        if best[2]['signals_pct'] < 50:
            print(f"   ⚠️  Отфильтровывает {100 - best[2]['signals_pct']:.1f}% сигналов")
        
        # Show other variants
        if len(scores) > 1:
            print(f"\n   Альтернативы:")
            for i, (name, score, data) in enumerate(scores[1:], 2):
                print(f"   {i}. {name} (скор: {score:.1f})")
                print(f"      WR: {data['win_rate']:.1f}%, Profit: {data['avg_profit']:+.2f}%")

def main():
    print("="*80)
    print("ТЕСТИРОВАНИЕ ВАРИАНТОВ ИСПРАВЛЕНИЯ CONFIDENCE")
    print("="*80)
    print(f"Дата среза: {TRAINING_CUTOFF}")
    print(f"Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    df = load_data()
    print(f"Загружено сигналов: {len(df)}")
    print(f"  WIN: {(df['result'] == 'WIN').sum()}")
    print(f"  LOSS: {(df['result'] == 'LOSS').sum()}")
    
    # Original stats
    wins = (df['result'] == 'WIN').sum()
    wr = wins / len(df) * 100
    profit = df['profit_pct'].mean()
    print(f"\nИсходная производительность:")
    print(f"  Win Rate: {wr:.1f}%")
    print(f"  Avg Profit: {profit:+.2f}%")
    print()
    
    # Test all variants
    results = []
    results.append(test_variant_1_oi_required(df))
    results.append(test_variant_2_increase_oi_weight(df))
    results.append(test_variant_3_oi_multiplier(df))
    
    # Compare
    compare_variants(results)
    
    print("\n" + "="*80)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*80)

if __name__ == '__main__':
    main()
