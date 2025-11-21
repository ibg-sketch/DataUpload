import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load BingX trades
df = pd.read_csv('bingx_trader/logs/trades_log.csv')
df['timestamp_open'] = pd.to_datetime(df['timestamp_open'])

# Filter last 7 days
cutoff = datetime.now() - timedelta(days=7)
df_week = df[df['timestamp_open'] >= cutoff].copy()

print(f"🔬 БЭКТЕСТ НА ВСЕХ СИГНАЛАХ (2,599 СДЕЛОК BINGX)")
print(f"=" * 95)
print(f"Период: {df_week['timestamp_open'].min().date()} - {df_week['timestamp_open'].max().date()}")
print(f"Всего сделок: {len(df_week):,}")
print(f"Модель: БЕЗ отмены сигналов, закрытие только по TP/SL/TTL")
print()

# Parameters
POSITION_SIZE = 50
LEVERAGE = 50
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005

# SL levels to test
SL_LEVELS = [2.0, 5.0, 10.0]

# Strategies mapped to BingX columns
# 'start' = target_min (for BUY) or target_max (for SELL)
# 'mid' = fixed_50 (50% of zone)
# 'end' = fixed_75 (75% of zone, close to full target)

def calculate_pnl_with_bingx_data(row, strategy, sl_percent):
    """
    Use BingX pre-calculated data for target achievements
    """
    
    entry_price = row['entry_price']
    exit_price = row['exit_price']
    side = row['side']
    highest = row['highest_during_trade']
    lowest = row['lowest_during_trade']
    
    # SL calculation
    sl_price_move_pct = sl_percent / LEVERAGE
    
    if side == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check if SL was hit
        if lowest <= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached': False
            }
        
        # Check if target was reached based on strategy
        if strategy == 'start':
            reached = row['would_hit_target_min']
            profit_pct = row['profit_target_min'] if reached else None
        elif strategy == 'mid':
            reached = row['would_hit_fixed_50']
            profit_pct = row['profit_fixed_50'] if reached else None
        else:  # end
            reached = row['would_hit_fixed_75']
            profit_pct = row['profit_fixed_75'] if reached else None
        
        # Calculate PnL
        if reached:
            # Use BingX calculated profit
            pnl_usd = profit_pct  # Already in USD
            exit_type = 'TP'
        else:
            # Exit at TTL (final price)
            pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
            pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100  # Both market orders
            pnl_usd = POSITION_SIZE * pnl_pct / 100
            exit_type = 'TTL'
        
        return {
            'pnl_usd': pnl_usd,
            'exit': exit_type,
            'reached': reached
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        if highest >= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached': False
            }
        
        # Same logic for SELL
        if strategy == 'start':
            reached = row['would_hit_target_min']
            profit_pct = row['profit_target_min'] if reached else None
        elif strategy == 'mid':
            reached = row['would_hit_fixed_50']
            profit_pct = row['profit_fixed_50'] if reached else None
        else:  # end
            reached = row['would_hit_fixed_75']
            profit_pct = row['profit_fixed_75'] if reached else None
        
        if reached:
            pnl_usd = profit_pct
            exit_type = 'TP'
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
            pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100
            pnl_usd = POSITION_SIZE * pnl_pct / 100
            exit_type = 'TTL'
        
        return {
            'pnl_usd': pnl_usd,
            'exit': exit_type,
            'reached': reached
        }

# Test all combinations
strategies = {
    'start': 'НАЧАЛО зоны (target_min/max)',
    'mid': 'СЕРЕДИНА зоны (50%)',
    'end': 'ПОЧТИ КОНЕЦ зоны (75%)'
}

best_combo = None
best_pnl = float('-inf')

print(f"{'='*95}")
print(f"📊 РЕЗУЛЬТАТЫ БЭКТЕСТА")
print(f"{'='*95}")
print()

for sl_percent in SL_LEVELS:
    sl_price_move = sl_percent / LEVERAGE
    
    print(f"{'='*95}")
    print(f"🛑 Stop-Loss: {sl_percent}% позиции = {sl_price_move:.2f}% движения цены")
    print(f"{'='*95}")
    print()
    
    for strategy_key, strategy_name in strategies.items():
        results = []
        exit_counts = {'SL': 0, 'TTL': 0, 'TP': 0}
        reached_count = 0
        
        for _, row in df_week.iterrows():
            result = calculate_pnl_with_bingx_data(row, strategy_key, sl_percent)
            results.append(result)
            
            exit_counts[result['exit']] += 1
            if result['reached']:
                reached_count += 1
        
        total_pnl = sum(r['pnl_usd'] for r in results)
        wins = sum(1 for r in results if r['pnl_usd'] > 0)
        win_rate = wins / len(results) * 100
        avg_pnl = total_pnl / len(results)
        
        pnl_week = total_pnl
        pnl_month = total_pnl * 4.33
        pnl_year = total_pnl * 52
        
        total = len(results)
        
        print(f"🎯 {strategy_name}")
        print(f"{'-'*95}")
        print(f"💰 PnL:  Неделя: ${pnl_week:+9.2f}  |  Месяц: ${pnl_month:+10.2f}  |  Год: ${pnl_year:+11.2f}")
        print(f"📊 Win Rate: {win_rate:5.1f}%  |  Avg PnL: ${avg_pnl:+.2f}")
        print()
        print(f"📍 ВЫХОДЫ:")
        print(f"   🛑 SL:            {exit_counts['SL']:4d} ({exit_counts['SL']/total*100:5.1f}%)")
        print(f"   ⏱️  TTL:          {exit_counts['TTL']:4d} ({exit_counts['TTL']/total*100:5.1f}%)")
        print(f"   🎯 TP:            {exit_counts['TP']:4d} ({exit_counts['TP']/total*100:5.1f}%)")
        print()
        print(f"🎯 ДОСТИЖЕНИЕ TARGET: {reached_count:4d} ({reached_count/total*100:5.1f}%)")
        print()
        
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_combo = {
                'sl': sl_percent,
                'sl_price_move': sl_price_move,
                'strategy': strategy_key,
                'strategy_name': strategy_name,
                'pnl_week': pnl_week,
                'pnl_month': pnl_month,
                'pnl_year': pnl_year,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'wins': wins,
                'total': total,
                'exit_counts': exit_counts.copy(),
                'reached_count': reached_count
            }

# Print best combo
print(f"{'='*95}")
print(f"🏆 ЛУЧШАЯ КОМБИНАЦИЯ")
print(f"{'='*95}")
print(f"Стратегия:           {best_combo['strategy_name']}")
print(f"Stop-Loss:           {best_combo['sl']}% позиции = {best_combo['sl_price_move']:.2f}% цены")
print()
print(f"💰 ДОХОДНОСТЬ:")
print(f"   Неделя:           ${best_combo['pnl_week']:+,.2f}")
print(f"   Месяц:            ${best_combo['pnl_month']:+,.2f}")
print(f"   Год:              ${best_combo['pnl_year']:+,.2f}")
print()
print(f"📊 СТАТИСТИКА:")
print(f"   Сделок:           {best_combo['total']:,}")
print(f"   Win Rate:         {best_combo['win_rate']:.1f}%")
print(f"   Avg PnL:          ${best_combo['avg_pnl']:+.2f}")
print()
ec = best_combo['exit_counts']
total = best_combo['total']
print(f"📍 РАСПРЕДЕЛЕНИЕ ВЫХОДОВ:")
print(f"   🛑 SL:            {ec['SL']:4d} ({ec['SL']/total*100:5.1f}%)")
print(f"   ⏱️  TTL:          {ec['TTL']:4d} ({ec['TTL']/total*100:5.1f}%)")
print(f"   🎯 TP:            {ec['TP']:4d} ({ec['TP']/total*100:5.1f}%)")
print()
print(f"🎯 ДОСТИЖЕНИЕ TARGET: {best_combo['reached_count']:4d} ({best_combo['reached_count']/total*100:5.1f}%)")
print()

# Risk metrics
pnls = [r['pnl_usd'] for r in results]
std_dev = np.std(pnls)
sharpe = (np.mean(pnls) / std_dev * np.sqrt(len(pnls))) if std_dev > 0 else 0

max_dd = 0
peak = 0
cum = 0
for pnl in pnls:
    cum += pnl
    if cum > peak:
        peak = cum
    dd = peak - cum
    if dd > max_dd:
        max_dd = dd

print(f"📉 РИСК-МЕТРИКИ:")
print(f"   Std Dev:          ${std_dev:.2f}")
print(f"   Sharpe Ratio:     {sharpe:.2f}")
print(f"   Max Drawdown:     ${max_dd:.2f}")
print()
print(f"{'='*95}")
print(f"✅ Бэктест завершён на {len(df_week):,} сделках (ВСЕ сигналы включая CANCELLED)")
print(f"{'='*95}")

