import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')

# Filter last 7 days
cutoff_date = datetime.now() - timedelta(days=7)
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df_week = df[df['timestamp_sent'] >= cutoff_date].copy()

# Filter valid signals (exclude CANCELLED, only those with targets)
df_valid = df_week[
    (df_week['result'] != 'CANCELLED') & 
    (df_week['target_min'] != 0) & 
    (df_week['target_max'] != 0)
].copy()

print(f"🔬 ТОЧНЫЙ БЭКТЕСТ МОДЕЛИ (БЕЗ ОТМЕНЫ СИГНАЛОВ)")
print(f"=" * 90)
print(f"Период: {df_valid['timestamp_sent'].min()} - {df_valid['timestamp_sent'].max()}")
print(f"Сигналов: {len(df_valid)}")
print()

# Trading parameters
POSITION_SIZE = 50  # USD
LEVERAGE = 50
MAKER_FEE = 0.0002  # 0.02%
TAKER_FEE = 0.0005  # 0.05%

# Test different SL levels (percent of position)
SL_LEVELS = [2.0, 3.0, 5.0, 10.0]

def calculate_exit_detailed(row, strategy_type, sl_percent):
    """
    Calculate PnL with detailed exit tracking
    Returns: pnl_usd, pnl_pct, exit_type, reached_start, reached_mid, reached_end
    """
    
    entry_price = row['entry_price']
    verdict = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    target_mid = (target_min + target_max) / 2
    
    # SL price movement
    sl_price_move_pct = sl_percent / LEVERAGE
    
    # Track target zone achievements
    reached_start = False
    reached_mid = False
    reached_end = False
    
    if verdict == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check target achievements
        if highest >= target_min:
            reached_start = True
        if highest >= target_mid:
            reached_mid = True
        if highest >= target_max:
            reached_end = True
        
        # Determine exit
        if lowest <= sl_price:
            # SL hit
            exit_type = 'SL'
            loss_pct = -sl_percent
            pnl_usd = POSITION_SIZE * loss_pct / 100
            
        elif strategy_type == 'conservative':
            # Exit at target_min
            if reached_start:
                exit_price = target_min
                exit_type = 'TP_Start'
                pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + MAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
            else:
                exit_price = row['final_price']
                exit_type = 'TTL'
                pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
                
        elif strategy_type == 'balanced':
            # Mixed exit
            total_pnl_pct = 0
            
            if reached_start:
                pnl = (target_min - entry_price) / entry_price * 100 * LEVERAGE * 0.5
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.5
                total_pnl_pct += pnl
            else:
                pnl = (row['final_price'] - entry_price) / entry_price * 100 * LEVERAGE * 0.5
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.5
                total_pnl_pct += pnl
            
            if reached_mid:
                pnl = (target_mid - entry_price) / entry_price * 100 * LEVERAGE * 0.3
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.3
                total_pnl_pct += pnl
            else:
                pnl = (row['final_price'] - entry_price) / entry_price * 100 * LEVERAGE * 0.3
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.3
                total_pnl_pct += pnl
            
            if reached_end:
                pnl = (target_max - entry_price) / entry_price * 100 * LEVERAGE * 0.2
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.2
                total_pnl_pct += pnl
                exit_type = 'TP_Mixed'
            else:
                pnl = (row['final_price'] - entry_price) / entry_price * 100 * LEVERAGE * 0.2
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.2
                total_pnl_pct += pnl
                exit_type = 'TTL_Mixed' if not (reached_start or reached_mid) else 'TP_Mixed'
            
            pnl_usd = POSITION_SIZE * total_pnl_pct / 100
            
        else:  # aggressive
            # Exit at target_max or TTL
            if reached_end:
                exit_price = target_max
                exit_type = 'TP_End'
                pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + MAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
            else:
                exit_price = row['final_price']
                exit_type = 'TTL'
                pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'exit_type': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        # Check target achievements (for SELL: max=start, min=end)
        if lowest <= target_max:
            reached_start = True
        if lowest <= target_mid:
            reached_mid = True
        if lowest <= target_min:
            reached_end = True
        
        # Determine exit
        if highest >= sl_price:
            # SL hit
            exit_type = 'SL'
            loss_pct = -sl_percent
            pnl_usd = POSITION_SIZE * loss_pct / 100
            
        elif strategy_type == 'conservative':
            if reached_start:
                exit_price = target_max
                exit_type = 'TP_Start'
                pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + MAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
            else:
                exit_price = row['final_price']
                exit_type = 'TTL'
                pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
                
        elif strategy_type == 'balanced':
            total_pnl_pct = 0
            
            if reached_start:
                pnl = (entry_price - target_max) / entry_price * 100 * LEVERAGE * 0.5
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.5
                total_pnl_pct += pnl
            else:
                pnl = (entry_price - row['final_price']) / entry_price * 100 * LEVERAGE * 0.5
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.5
                total_pnl_pct += pnl
            
            if reached_mid:
                pnl = (entry_price - target_mid) / entry_price * 100 * LEVERAGE * 0.3
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.3
                total_pnl_pct += pnl
            else:
                pnl = (entry_price - row['final_price']) / entry_price * 100 * LEVERAGE * 0.3
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.3
                total_pnl_pct += pnl
            
            if reached_end:
                pnl = (entry_price - target_min) / entry_price * 100 * LEVERAGE * 0.2
                pnl -= (TAKER_FEE + MAKER_FEE) * 100 * 0.2
                total_pnl_pct += pnl
                exit_type = 'TP_Mixed'
            else:
                pnl = (entry_price - row['final_price']) / entry_price * 100 * LEVERAGE * 0.2
                pnl -= (TAKER_FEE + TAKER_FEE) * 100 * 0.2
                total_pnl_pct += pnl
                exit_type = 'TTL_Mixed' if not (reached_start or reached_mid) else 'TP_Mixed'
            
            pnl_usd = POSITION_SIZE * total_pnl_pct / 100
            
        else:  # aggressive
            if reached_end:
                exit_price = target_min
                exit_type = 'TP_End'
                pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + MAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
            else:
                exit_price = row['final_price']
                exit_type = 'TTL'
                pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
                pnl_pct -= (TAKER_FEE + TAKER_FEE) * 100
                pnl_usd = POSITION_SIZE * pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'exit_type': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }

# Test all combinations
print(f"{'='*90}")
print(f"📊 ДЕТАЛЬНАЯ СТАТИСТИКА ПО ВСЕМ КОМБИНАЦИЯМ")
print(f"{'='*90}")
print()

best_combo = None
best_pnl = float('-inf')

for sl_percent in SL_LEVELS:
    sl_price_move = sl_percent / LEVERAGE
    
    print(f"{'='*90}")
    print(f"🛑 SL: {sl_percent}% позиции = {sl_price_move:.2f}% движения цены")
    print(f"{'='*90}")
    
    for strategy in ['conservative', 'balanced', 'aggressive']:
        results = []
        
        # Counters
        exit_counts = {
            'SL': 0,
            'TTL': 0,
            'TP_Start': 0,
            'TP_Mid': 0,
            'TP_End': 0,
            'TP_Mixed': 0,
            'TTL_Mixed': 0
        }
        
        reached_stats = {
            'start': 0,
            'mid': 0,
            'end': 0
        }
        
        for _, row in df_valid.iterrows():
            result = calculate_exit_detailed(row, strategy, sl_percent)
            results.append(result)
            
            # Count exits
            exit_type = result['exit_type']
            if exit_type in exit_counts:
                exit_counts[exit_type] += 1
            
            # Count achievements
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
        
        pnl_year = total_pnl * 52
        
        print(f"\n🎯 {strategy.upper()}")
        print(f"{'-'*90}")
        print(f"💰 PnL/неделя: ${total_pnl:+,.2f}  |  PnL/год: ${pnl_year:+,.2f}")
        print(f"📊 Win Rate: {win_rate:.1f}%  |  Avg PnL: ${avg_pnl:+.2f}")
        print()
        print(f"📍 ВЫХОДЫ ИЗ ПОЗИЦИЙ:")
        
        total = len(results)
        print(f"   🛑 Stop-Loss:        {exit_counts['SL']:4d} ({exit_counts['SL']/total*100:5.1f}%)")
        print(f"   ⏱️  TTL Expired:      {exit_counts['TTL']:4d} ({exit_counts['TTL']/total*100:5.1f}%)")
        print(f"   🎯 TP Start:         {exit_counts['TP_Start']:4d} ({exit_counts['TP_Start']/total*100:5.1f}%)")
        print(f"   🎯 TP Mixed:         {exit_counts['TP_Mixed']:4d} ({exit_counts['TP_Mixed']/total*100:5.1f}%)")
        print(f"   🎯 TP End:           {exit_counts['TP_End']:4d} ({exit_counts['TP_End']/total*100:5.1f}%)")
        print(f"   ⏱️  TTL Mixed:        {exit_counts['TTL_Mixed']:4d} ({exit_counts['TTL_Mixed']/total*100:5.1f}%)")
        print()
        print(f"🎯 ДОСТИЖЕНИЕ TARGET ЗОН:")
        print(f"   Начало зоны:      {reached_stats['start']:4d} ({reached_stats['start']/total*100:5.1f}%)")
        print(f"   Середина зоны:    {reached_stats['mid']:4d} ({reached_stats['mid']/total*100:5.1f}%)")
        print(f"   Конец зоны:       {reached_stats['end']:4d} ({reached_stats['end']/total*100:5.1f}%)")
        
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_combo = {
                'sl': sl_percent,
                'sl_price_move': sl_price_move,
                'strategy': strategy,
                'pnl_week': total_pnl,
                'pnl_year': pnl_year,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'exit_counts': exit_counts.copy(),
                'reached_stats': reached_stats.copy(),
                'total': total
            }

print()
print(f"{'='*90}")
print(f"🏆 ЛУЧШАЯ КОМБИНАЦИЯ")
print(f"{'='*90}")
print(f"Стратегия:           {best_combo['strategy'].upper()}")
print(f"Stop-Loss:           {best_combo['sl']}% позиции = {best_combo['sl_price_move']:.2f}% движения цены")
print()
print(f"💰 ДОХОДНОСТЬ:")
print(f"   Неделя:           ${best_combo['pnl_week']:+,.2f}")
print(f"   Месяц:            ${best_combo['pnl_week']*4.33:+,.2f}")
print(f"   Год:              ${best_combo['pnl_year']:+,.2f}")
print()
print(f"📊 СТАТИСТИКА:")
print(f"   Win Rate:         {best_combo['win_rate']:.1f}%")
print(f"   Avg PnL:          ${best_combo['avg_pnl']:+.2f}")
print(f"   Всего сделок:     {best_combo['total']}")
print()
print(f"📍 ВЫХОДЫ:")
total = best_combo['total']
ec = best_combo['exit_counts']
print(f"   🛑 SL:            {ec['SL']:4d} ({ec['SL']/total*100:5.1f}%)")
print(f"   ⏱️  TTL:          {ec['TTL']:4d} ({ec['TTL']/total*100:5.1f}%)")
print(f"   🎯 TP Start:      {ec['TP_Start']:4d} ({ec['TP_Start']/total*100:5.1f}%)")
print(f"   🎯 TP End:        {ec['TP_End']:4d} ({ec['TP_End']/total*100:5.1f}%)")
print(f"   🎯 TP Mixed:      {ec['TP_Mixed']:4d} ({ec['TP_Mixed']/total*100:5.1f}%)")
print()
print(f"🎯 ДОСТИЖЕНИЕ TARGET:")
rs = best_combo['reached_stats']
print(f"   Начало:           {rs['start']:4d} ({rs['start']/total*100:5.1f}%)")
print(f"   Середина:         {rs['mid']:4d} ({rs['mid']/total*100:5.1f}%)")
print(f"   Конец:            {rs['end']:4d} ({rs['end']/total*100:5.1f}%)")
print()
print(f"{'='*90}")
print(f"✅ Анализ завершён")
print(f"{'='*90}")

