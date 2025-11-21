#!/usr/bin/env python3
"""
Statistical validation of bot's predictive formulas.
Analyzes correlation between predicted parameters and actual outcomes.
"""
import pandas as pd
import numpy as np
from scipy import stats
import json

def load_data():
    """Load effectiveness and signals data"""
    # Load closed signals with results
    effectiveness = pd.read_csv('effectiveness_log.csv')
    effectiveness['timestamp_sent'] = pd.to_datetime(effectiveness['timestamp_sent'])
    
    # Load all generated signals with parameters
    signals = pd.read_csv('signals_log.csv')
    signals['timestamp'] = pd.to_datetime(signals['timestamp'])
    
    return effectiveness, signals

def analyze_magnitude_correlation(effectiveness):
    """
    Analyze if market_strength (magnitude) correlates with actual profit.
    Expected: Higher magnitude → Higher profit
    """
    print("=" * 80)
    print("📊 АНАЛИЗ 1: MAGNITUDE vs ACTUAL PROFIT")
    print("=" * 80)
    
    # Filter only WIN/LOSS (exclude CANCELLED)
    traded = effectiveness[effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    
    if 'market_strength' not in traded.columns:
        print("⚠️  market_strength column not found - magnitude not logged")
        return
    
    # Remove invalid values
    traded = traded[traded['market_strength'].notna()].copy()
    traded = traded[traded['profit_pct'].notna()].copy()
    
    if len(traded) == 0:
        print("⚠️  No data with market_strength available")
        return
    
    # Calculate correlation
    correlation = traded['market_strength'].corr(traded['profit_pct'])
    
    print(f"\n📈 Корреляция: {correlation:.4f}")
    
    if abs(correlation) < 0.1:
        print("❌ СЛАБАЯ корреляция - magnitude НЕ предсказывает прибыль!")
    elif abs(correlation) < 0.3:
        print("⚠️  УМЕРЕННАЯ корреляция - magnitude частично работает")
    else:
        print("✅ СИЛЬНАЯ корреляция - magnitude хорошо предсказывает!")
    
    # Statistical significance
    _, p_value = stats.pearsonr(traded['market_strength'], traded['profit_pct'])
    print(f"   p-value: {p_value:.6f} {'(статистически значимо)' if p_value < 0.05 else '(НЕ значимо)'}")
    
    # Binned analysis
    print("\n📊 Анализ по диапазонам magnitude:")
    traded['mag_bin'] = pd.cut(traded['market_strength'], bins=5, labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'])
    
    for bin_name in ['Very Low', 'Low', 'Medium', 'High', 'Very High']:
        bin_data = traded[traded['mag_bin'] == bin_name]
        if len(bin_data) > 0:
            avg_profit = bin_data['profit_pct'].mean()
            win_rate = (bin_data['result'] == 'WIN').mean() * 100
            print(f"   {bin_name:12s}: {len(bin_data):4d} signals | Avg profit: {avg_profit:+.2f}% | WR: {win_rate:.1f}%")

def analyze_ttl_accuracy(effectiveness):
    """
    Analyze if predicted TTL (duration_minutes) matches actual duration.
    Expected: Predicted ≈ Actual
    """
    print("\n" + "=" * 80)
    print("⏱️  АНАЛИЗ 2: TTL PREDICTION ACCURACY")
    print("=" * 80)
    
    # Filter valid data
    traded = effectiveness[effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    traded = traded[traded['duration_minutes'].notna()].copy()
    traded = traded[traded['duration_actual'].notna()].copy()
    
    if len(traded) == 0:
        print("⚠️  No duration data available")
        return
    
    # Calculate errors
    traded['duration_error'] = traded['duration_actual'] - traded['duration_minutes']
    traded['duration_error_pct'] = (traded['duration_error'] / traded['duration_minutes']) * 100
    
    mae = traded['duration_error'].abs().mean()
    mape = traded['duration_error_pct'].abs().mean()
    
    print(f"\n📊 Ошибка предсказания:")
    print(f"   MAE (средняя абсолютная): {mae:.1f} минут")
    print(f"   MAPE (средняя %): {mape:.1f}%")
    
    # How often we're close
    within_5min = (traded['duration_error'].abs() <= 5).mean() * 100
    within_10min = (traded['duration_error'].abs() <= 10).mean() * 100
    
    print(f"\n✅ Точность:")
    print(f"   В пределах ±5 мин: {within_5min:.1f}%")
    print(f"   В пределах ±10 мин: {within_10min:.1f}%")
    
    # Correlation
    correlation = traded['duration_minutes'].corr(traded['duration_actual'])
    print(f"\n📈 Корреляция predicted vs actual: {correlation:.4f}")
    
    if correlation > 0.5:
        print("✅ TTL формула работает хорошо!")
    elif correlation > 0.3:
        print("⚠️  TTL формула работает умеренно")
    else:
        print("❌ TTL формула работает плохо!")

def analyze_target_accuracy(effectiveness):
    """
    Analyze if price reaches predicted target zones.
    Expected: WIN signals should reach target_min/max
    """
    print("\n" + "=" * 80)
    print("🎯 АНАЛИЗ 3: TARGET ZONES ACCURACY")
    print("=" * 80)
    
    # Filter valid data
    valid = effectiveness[effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    valid = valid[valid['target_min'].notna()].copy()
    valid = valid[valid['highest_reached'].notna()].copy()
    
    if len(valid) == 0:
        print("⚠️  No target data available")
        return
    
    # For BUY signals (price should go UP)
    buy_signals = valid[valid['verdict'] == 'BUY'].copy()
    if len(buy_signals) > 0:
        # Calculate if highest reached target_min/max
        buy_signals['reached_min'] = buy_signals['highest_reached'] >= buy_signals['target_min']
        buy_signals['reached_max'] = buy_signals['highest_reached'] >= buy_signals['target_max']
        
        reached_min_pct = buy_signals['reached_min'].mean() * 100
        reached_max_pct = buy_signals['reached_max'].mean() * 100
        
        print(f"\n📈 BUY сигналы ({len(buy_signals)} шт):")
        print(f"   Достигли target_min: {reached_min_pct:.1f}%")
        print(f"   Достигли target_max: {reached_max_pct:.1f}%")
        
        # For wins vs losses
        buy_wins = buy_signals[buy_signals['result'] == 'WIN']
        buy_losses = buy_signals[buy_signals['result'] == 'LOSS']
        
        if len(buy_wins) > 0:
            win_min = buy_wins['reached_min'].mean() * 100
            win_max = buy_wins['reached_max'].mean() * 100
            print(f"   WIN сигналы: min={win_min:.1f}%, max={win_max:.1f}%")
        
        if len(buy_losses) > 0:
            loss_min = buy_losses['reached_min'].mean() * 100
            loss_max = buy_losses['reached_max'].mean() * 100
            print(f"   LOSS сигналы: min={loss_min:.1f}%, max={loss_max:.1f}%")
    
    # For SELL signals (price should go DOWN)
    sell_signals = valid[valid['verdict'] == 'SELL'].copy()
    if len(sell_signals) > 0:
        # For SELL, check if lowest reached target zones
        sell_signals['reached_min'] = sell_signals['lowest_reached'] <= sell_signals['target_min']
        sell_signals['reached_max'] = sell_signals['lowest_reached'] <= sell_signals['target_max']
        
        reached_min_pct = sell_signals['reached_min'].mean() * 100
        reached_max_pct = sell_signals['reached_max'].mean() * 100
        
        print(f"\n📉 SELL сигналы ({len(sell_signals)} шт):")
        print(f"   Достигли target_min: {reached_min_pct:.1f}%")
        print(f"   Достигли target_max: {reached_max_pct:.1f}%")
        
        # For wins vs losses
        sell_wins = sell_signals[sell_signals['result'] == 'WIN']
        sell_losses = sell_signals[sell_signals['result'] == 'LOSS']
        
        if len(sell_wins) > 0:
            win_min = sell_wins['reached_min'].mean() * 100
            win_max = sell_wins['reached_max'].mean() * 100
            print(f"   WIN сигналы: min={win_min:.1f}%, max={win_max:.1f}%")
        
        if len(sell_losses) > 0:
            loss_min = sell_losses['reached_min'].mean() * 100
            loss_max = sell_losses['reached_max'].mean() * 100
            print(f"   LOSS сигналы: min={loss_min:.1f}%, max={loss_max:.1f}%")

def analyze_indicator_strength(effectiveness):
    """
    Analyze correlation between indicator strength and Win Rate.
    Uses confidence as proxy for indicator strength.
    """
    print("\n" + "=" * 80)
    print("💪 АНАЛИЗ 4: INDICATOR STRENGTH vs WIN RATE")
    print("=" * 80)
    
    # Filter valid data
    traded = effectiveness[effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    traded = traded[traded['confidence'].notna()].copy()
    
    if len(traded) == 0:
        print("⚠️  No confidence data available")
        return
    
    # Bin by confidence level
    traded['conf_bin'] = pd.cut(traded['confidence'], 
                                 bins=[0, 0.3, 0.5, 0.7, 0.85, 1.0],
                                 labels=['Very Low (<30%)', 'Low (30-50%)', 'Medium (50-70%)', 'High (70-85%)', 'Very High (>85%)'])
    
    print("\n📊 Win Rate по уровню Confidence:")
    print(f"{'Confidence Range':<25} {'Count':>8} {'Win Rate':>12} {'Avg Profit':>12}")
    print("-" * 60)
    
    for bin_name in ['Very Low (<30%)', 'Low (30-50%)', 'Medium (50-70%)', 'High (70-85%)', 'Very High (>85%)']:
        bin_data = traded[traded['conf_bin'] == bin_name]
        if len(bin_data) > 0:
            win_rate = (bin_data['result'] == 'WIN').mean() * 100
            avg_profit = bin_data['profit_pct'].mean()
            print(f"{bin_name:<25} {len(bin_data):>8} {win_rate:>11.1f}% {avg_profit:>11.2f}%")
    
    # Correlation
    traded['is_win'] = (traded['result'] == 'WIN').astype(int)
    correlation = traded['confidence'].corr(traded['is_win'])
    
    print(f"\n📈 Корреляция Confidence vs Win: {correlation:.4f}")
    
    if correlation > 0.3:
        print("✅ Высокая confidence ДЕЙСТВИТЕЛЬНО означает больше побед!")
    elif correlation > 0.1:
        print("⚠️  Слабая корреляция - confidence частично работает")
    else:
        print("❌ Confidence НЕ коррелирует с победами!")

def analyze_verdict_asymmetry(effectiveness):
    """
    Analyze BUY vs SELL performance asymmetry.
    """
    print("\n" + "=" * 80)
    print("⚖️  АНАЛИЗ 5: BUY vs SELL ASYMMETRY")
    print("=" * 80)
    
    traded = effectiveness[effectiveness['result'].isin(['WIN', 'LOSS'])].copy()
    
    for verdict in ['BUY', 'SELL']:
        verdict_data = traded[traded['verdict'] == verdict]
        
        if len(verdict_data) == 0:
            continue
        
        win_rate = (verdict_data['result'] == 'WIN').mean() * 100
        avg_profit = verdict_data['profit_pct'].mean()
        avg_win_profit = verdict_data[verdict_data['result'] == 'WIN']['profit_pct'].mean()
        avg_loss_profit = verdict_data[verdict_data['result'] == 'LOSS']['profit_pct'].mean()
        
        print(f"\n{verdict} сигналы ({len(verdict_data)} шт):")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Средняя прибыль: {avg_profit:+.2f}%")
        print(f"   Средняя прибыль WIN: {avg_win_profit:+.2f}%")
        print(f"   Средний убыток LOSS: {avg_loss_profit:+.2f}%")
        
        # Confidence range
        if 'confidence' in verdict_data.columns:
            avg_conf = verdict_data['confidence'].mean() * 100
            print(f"   Средняя confidence: {avg_conf:.1f}%")

def main():
    print("\n" + "=" * 80)
    print("🔬 СТАТИСТИЧЕСКАЯ ВАЛИДАЦИЯ ФОРМУЛ БОТА")
    print("=" * 80)
    
    try:
        effectiveness, signals = load_data()
        
        print(f"\n📊 Загружено данных:")
        print(f"   Закрытые сигналы: {len(effectiveness)}")
        print(f"   Сгенерированные сигналы: {len(signals)}")
        
        # Run all analyses
        analyze_magnitude_correlation(effectiveness)
        analyze_ttl_accuracy(effectiveness)
        analyze_target_accuracy(effectiveness)
        analyze_indicator_strength(effectiveness)
        analyze_verdict_asymmetry(effectiveness)
        
        print("\n" + "=" * 80)
        print("✅ АНАЛИЗ ЗАВЕРШЁН")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
