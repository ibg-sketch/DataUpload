import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load BingX trades log
df = pd.read_csv('bingx_trader/logs/trades_log.csv')
df['timestamp_open'] = pd.to_datetime(df['timestamp_open'])

# Filter last 7 days
cutoff_date = datetime.now() - timedelta(days=7)
df_week = df[df['timestamp_open'] >= cutoff_date].copy()

print(f"🔬 БЭКТЕСТ НА РЕАЛЬНЫХ ДАННЫХ BINGX AUTO-TRADER")
print(f"=" * 95)
print(f"Период: {df_week['timestamp_open'].min()} - {df_week['timestamp_open'].max()}")
print(f"Всего сделок: {len(df_week)}")
print()

# Trading parameters
POSITION_SIZE = 50  # USD
LEVERAGE = 50
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005

# Test different SL levels
SL_LEVELS = [2.0, 5.0, 10.0]

def calculate_pnl_from_trade(row, strategy, sl_percent):
    """
    Calculate PnL based on BingX trade data
    Strategy: 'start', 'mid', 'end'
    """
    
    entry_price = row['entry_price']
    side = row['side']
    highest = row['highest_during_trade']
    lowest = row['lowest_during_trade']
    
    # Get TP from column
    tp_price = row['tp_price_set']
    
    # Calculate targets from TP
    # For BUY: tp_price_set is target_min, calculate target_max
    # For SELL: tp_price_set is target_max, calculate target_min
    if side == 'BUY':
        target_min = tp_price
        # Estimate target_max (assuming ~0.5-1% zone)
        zone_size = abs(target_min - entry_price)
        target_max = target_min + zone_size
    else:  # SELL
        target_max = tp_price
        zone_size = abs(entry_price - target_max)
        target_min = target_max - zone_size
    
    target_mid = (target_min + target_max) / 2
    
    # Get final price
    final_price = row['exit_price']
    
    # SL calculation
    sl_price_move_pct = sl_percent / LEVERAGE
    
    # Track achievements
    reached_start = False
    reached_mid = False
    reached_end = False
    
    if side == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check SL
        if lowest <= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached_start': False,
                'reached_mid': False,
                'reached_end': False
            }
        
        # Check achievements
        if highest >= target_min:
            reached_start = True
        if highest >= target_mid:
            reached_mid = True
        if highest >= target_max:
            reached_end = True
        
        # Determine exit
        if strategy == 'start':
            exit_price = target_min if reached_start else final_price
            exit_type = 'TP_Start' if reached_start else 'TTL'
        elif strategy == 'mid':
            exit_price = target_mid if reached_mid else final_price
            exit_type = 'TP_Mid' if reached_mid else 'TTL'
        else:  # end
            exit_price = target_max if reached_end else final_price
            exit_type = 'TP_End' if reached_end else 'TTL'
        
        # Calculate PnL
        pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        
        return {
            'pnl_usd': POSITION_SIZE * pnl_pct / 100,
            'exit': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        # Check SL
        if highest >= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached_start': False,
                'reached_mid': False,
                'reached_end': False
            }
        
        # Check achievements
        if lowest <= target_max:
            reached_start = True
        if lowest <= target_mid:
            reached_mid = True
        if lowest <= target_min:
            reached_end = True
        
        # Determine exit
        if strategy == 'start':
            exit_price = target_max if reached_start else final_price
            exit_type = 'TP_Start' if reached_start else 'TTL'
        elif strategy == 'mid':
            exit_price = target_mid if reached_mid else final_price
            exit_type = 'TP_Mid' if reached_mid else 'TTL'
        else:  # end
            exit_price = target_min if reached_end else final_price
            exit_type = 'TP_End' if reached_end else 'TTL'
        
        # Calculate PnL
        pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        
        return {
            'pnl_usd': POSITION_SIZE * pnl_pct / 100,
            'exit': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }

# Test all combinations
strategies = {
    'start': 'НАЧАЛО зоны',
    'mid': 'СЕРЕДИНА зоны',
    'end': 'КОНЕЦ зоны'
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
        exit_counts = {'SL': 0, 'TTL': 0, 'TP_Start': 0, 'TP_Mid': 0, 'TP_End': 0}
        reached_stats = {'start': 0, 'mid': 0, 'end': 0}
        
        for _, row in df_week.iterrows():
            result = calculate_pnl_from_trade(row, strategy_key, sl_percent)
            results.append(result)
            
            exit_counts[result['exit']] += 1
            
            if result['reached_start']:
                reached_stats['start'] += 1
            if result['reached_mid']:
                reached_stats['mid'] += 1
            if result['reached_end']:
                reached_stats['end'] += 1
        
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
        tp_total = exit_counts['TP_Start'] + exit_counts['TP_Mid'] + exit_counts['TP_End']
        print(f"   🎯 TP:            {tp_total:4d} ({tp_total/total*100:5.1f}%)")
        if exit_counts['TP_Start'] > 0:
            print(f"      └─ Start:      {exit_counts['TP_Start']:4d}")
        if exit_counts['TP_Mid'] > 0:
            print(f"      └─ Mid:        {exit_counts['TP_Mid']:4d}")
        if exit_counts['TP_End'] > 0:
            print(f"      └─ End:        {exit_counts['TP_End']:4d}")
        print()
        print(f"🎯 ДОСТИЖЕНИЕ:")
        print(f"   Начало:           {reached_stats['start']:4d} ({reached_stats['start']/total*100:5.1f}%)")
        print(f"   Середина:         {reached_stats['mid']:4d} ({reached_stats['mid']/total*100:5.1f}%)")
        print(f"   Конец:            {reached_stats['end']:4d} ({reached_stats['end']/total*100:5.1f}%)")
        print()
        
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_combo = {
                'sl': sl_percent,
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
                'reached_stats': reached_stats.copy()
            }

# Print best
print(f"{'='*95}")
print(f"🏆 ЛУЧШАЯ КОМБИНАЦИЯ")
print(f"{'='*95}")
print(f"Стратегия:           {best_combo['strategy_name']}")
print(f"Stop-Loss:           {best_combo['sl']}% позиции = {best_combo['sl']/LEVERAGE:.2f}% цены")
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
print(f"📍 ВЫХОДЫ:")
print(f"   🛑 SL:            {ec['SL']:4d} ({ec['SL']/total*100:5.1f}%)")
print(f"   ⏱️  TTL:          {ec['TTL']:4d} ({ec['TTL']/total*100:5.1f}%)")
print(f"   🎯 TP:            {ec['TP_Start']+ec['TP_Mid']+ec['TP_End']:4d} ({(ec['TP_Start']+ec['TP_Mid']+ec['TP_End'])/total*100:5.1f}%)")
print()
rs = best_combo['reached_stats']
print(f"🎯 ДОСТИЖЕНИЕ:")
print(f"   Начало:           {rs['start']:4d} ({rs['start']/total*100:5.1f}%)")
print(f"   Середина:         {rs['mid']:4d} ({rs['mid']/total*100:5.1f}%)")
print(f"   Конец:            {rs['end']:4d} ({rs['end']/total*100:5.1f}%)")
print()
print(f"{'='*95}")
print(f"✅ Бэктест завершён на {len(df_week):,} реальных сделках BingX")
print(f"{'='*95}")

