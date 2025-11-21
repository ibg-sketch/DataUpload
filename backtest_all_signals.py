import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')

# Filter last 7 days
cutoff_date = datetime.now() - timedelta(days=7)
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df_week = df[df['timestamp_sent'] >= cutoff_date].copy()

# Use ALL signals (including CANCELLED)
# Only exclude signals without targets
df_all = df_week[
    (df_week['target_min'] != 0) & 
    (df_week['target_max'] != 0)
].copy()

print(f"🔬 БЭКТЕСТ ВСЕХ СИГНАЛОВ (РЕАЛЬНАЯ МОДЕЛЬ)")
print(f"=" * 95)
print(f"Период: {df_all['timestamp_sent'].min()} - {df_all['timestamp_sent'].max()}")
print(f"Всего сигналов: {len(df_all)} (включая CANCELLED)")
print(f"  └─ Отменённых: {len(df_all[df_all['result'] == 'CANCELLED'])} ({len(df_all[df_all['result'] == 'CANCELLED'])/len(df_all)*100:.1f}%)")
print()

# Trading parameters
POSITION_SIZE = 50  # USD
LEVERAGE = 50
MAKER_FEE = 0.0002  # 0.02%
TAKER_FEE = 0.0005  # 0.05%

# Test different SL levels
SL_LEVELS = [2.0, 5.0, 10.0]

def calculate_pnl(row, strategy, sl_percent):
    """
    Calculate PnL for a position opened on signal
    Position does NOT close on CANCELLED, only on TP/SL/TTL
    
    Strategy:
    - 'start': Close at target_min (BUY) or target_max (SELL)
    - 'mid': Close at middle of target zone
    - 'end': Close at target_max (BUY) or target_min (SELL)
    """
    
    entry_price = row['entry_price']
    verdict = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    target_mid = (target_min + target_max) / 2
    final_price = row['final_price']
    
    # SL price movement
    sl_price_move_pct = sl_percent / LEVERAGE
    
    # Track achievements
    reached_start = False
    reached_mid = False
    reached_end = False
    
    if verdict == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check if SL hit
        if lowest <= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached_start': False,
                'reached_mid': False,
                'reached_end': False
            }
        
        # Check target achievements
        if highest >= target_min:
            reached_start = True
        if highest >= target_mid:
            reached_mid = True
        if highest >= target_max:
            reached_end = True
        
        # Determine exit based on strategy
        if strategy == 'start':
            if reached_start:
                exit_price = target_min
                exit_type = 'TP_Start'
            else:
                exit_price = final_price
                exit_type = 'TTL'
                
        elif strategy == 'mid':
            if reached_mid:
                exit_price = target_mid
                exit_type = 'TP_Mid'
            else:
                exit_price = final_price
                exit_type = 'TTL'
                
        else:  # end
            if reached_end:
                exit_price = target_max
                exit_type = 'TP_End'
            else:
                exit_price = final_price
                exit_type = 'TTL'
        
        # Calculate PnL
        pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        pnl_usd = POSITION_SIZE * pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'exit': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        # Check if SL hit
        if highest >= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-sl_percent / 100),
                'exit': 'SL',
                'reached_start': False,
                'reached_mid': False,
                'reached_end': False
            }
        
        # For SELL: target_max is start, target_min is end
        if lowest <= target_max:
            reached_start = True
        if lowest <= target_mid:
            reached_mid = True
        if lowest <= target_min:
            reached_end = True
        
        # Determine exit
        if strategy == 'start':
            if reached_start:
                exit_price = target_max
                exit_type = 'TP_Start'
            else:
                exit_price = final_price
                exit_type = 'TTL'
                
        elif strategy == 'mid':
            if reached_mid:
                exit_price = target_mid
                exit_type = 'TP_Mid'
            else:
                exit_price = final_price
                exit_type = 'TTL'
                
        else:  # end
            if reached_end:
                exit_price = target_min
                exit_type = 'TP_End'
            else:
                exit_price = final_price
                exit_type = 'TTL'
        
        # Calculate PnL
        pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        pnl_usd = POSITION_SIZE * pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'exit': exit_type,
            'reached_start': reached_start,
            'reached_mid': reached_mid,
            'reached_end': reached_end
        }

# Test all combinations
print(f"{'='*95}")
print(f"📊 РЕЗУЛЬТАТЫ БЭКТЕСТА")
print(f"{'='*95}")
print()

strategies = {
    'start': 'НАЧАЛО зоны (target_min/max)',
    'mid': 'СЕРЕДИНА зоны',
    'end': 'КОНЕЦ зоны (target_max/min)'
}

best_combo = None
best_pnl = float('-inf')

for sl_percent in SL_LEVELS:
    sl_price_move = sl_percent / LEVERAGE
    
    print(f"{'='*95}")
    print(f"🛑 Stop-Loss: {sl_percent}% позиции = {sl_price_move:.2f}% движения цены")
    print(f"{'='*95}")
    print()
    
    for strategy_key, strategy_name in strategies.items():
        results = []
        
        # Counters
        exit_counts = {'SL': 0, 'TTL': 0, 'TP_Start': 0, 'TP_Mid': 0, 'TP_End': 0}
        reached_stats = {'start': 0, 'mid': 0, 'end': 0}
        
        for _, row in df_all.iterrows():
            result = calculate_pnl(row, strategy_key, sl_percent)
            results.append(result)
            
            # Count exits
            exit_counts[result['exit']] += 1
            
            # Count achievements
            if result['reached_start']:
                reached_stats['start'] += 1
            if result['reached_mid']:
                reached_stats['mid'] += 1
            if result['reached_end']:
                reached_stats['end'] += 1
        
        total_pnl = sum(r['pnl_usd'] for r in results)
        wins = sum(1 for r in results if r['pnl_usd'] > 0)
        losses = sum(1 for r in results if r['pnl_usd'] < 0)
        win_rate = wins / len(results) * 100
        avg_pnl = total_pnl / len(results)
        
        pnl_week = total_pnl
        pnl_month = total_pnl * 4.33
        pnl_year = total_pnl * 52
        
        total = len(results)
        
        print(f"🎯 {strategy_name}")
        print(f"{'-'*95}")
        print(f"💰 PnL:  Неделя: ${pnl_week:+9.2f}  |  Месяц: ${pnl_month:+10.2f}  |  Год: ${pnl_year:+11.2f}")
        print(f"📊 Сделок: {total:4d}  |  Win Rate: {win_rate:5.1f}%  |  Avg PnL: ${avg_pnl:+.2f}")
        print()
        print(f"📍 ВЫХОДЫ:")
        print(f"   🛑 Stop-Loss:     {exit_counts['SL']:4d} ({exit_counts['SL']/total*100:5.1f}%)")
        print(f"   ⏱️  TTL Expired:   {exit_counts['TTL']:4d} ({exit_counts['TTL']/total*100:5.1f}%)")
        print(f"   🎯 Take-Profit:   {exit_counts['TP_Start'] + exit_counts['TP_Mid'] + exit_counts['TP_End']:4d} ({(exit_counts['TP_Start'] + exit_counts['TP_Mid'] + exit_counts['TP_End'])/total*100:5.1f}%)")
        if exit_counts['TP_Start'] > 0:
            print(f"      └─ TP Start:   {exit_counts['TP_Start']:4d} ({exit_counts['TP_Start']/total*100:5.1f}%)")
        if exit_counts['TP_Mid'] > 0:
            print(f"      └─ TP Mid:     {exit_counts['TP_Mid']:4d} ({exit_counts['TP_Mid']/total*100:5.1f}%)")
        if exit_counts['TP_End'] > 0:
            print(f"      └─ TP End:     {exit_counts['TP_End']:4d} ({exit_counts['TP_End']/total*100:5.1f}%)")
        print()
        print(f"🎯 ДОСТИЖЕНИЕ TARGET ЗОН (до SL/TTL):")
        print(f"   Начало:           {reached_stats['start']:4d} ({reached_stats['start']/total*100:5.1f}%)")
        print(f"   Середина:         {reached_stats['mid']:4d} ({reached_stats['mid']/total*100:5.1f}%)")
        print(f"   Конец:            {reached_stats['end']:4d} ({reached_stats['end']/total*100:5.1f}%)")
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
                'losses': losses,
                'total': total,
                'exit_counts': exit_counts.copy(),
                'reached_stats': reached_stats.copy()
            }

# Print best combo
print(f"{'='*95}")
print(f"🏆 ЛУЧШАЯ КОМБИНАЦИЯ")
print(f"{'='*95}")
print(f"Стратегия:           {best_combo['strategy_name']}")
print(f"Stop-Loss:           {best_combo['sl']}% позиции = {best_combo['sl_price_move']:.2f}% движения цены")
print()
print(f"💰 ДОХОДНОСТЬ:")
print(f"   Неделя:           ${best_combo['pnl_week']:+,.2f}")
print(f"   Месяц:            ${best_combo['pnl_month']:+,.2f}")
print(f"   Год:              ${best_combo['pnl_year']:+,.2f}")
print()
print(f"📊 СТАТИСТИКА:")
print(f"   Сделок:           {best_combo['total']:,}")
print(f"   Прибыльных:       {best_combo['wins']:,} ({best_combo['win_rate']:.1f}%)")
print(f"   Убыточных:        {best_combo['losses']:,} ({100-best_combo['win_rate']:.1f}%)")
print(f"   Avg PnL:          ${best_combo['avg_pnl']:+.2f}")
print()
print(f"📍 РАСПРЕДЕЛЕНИЕ ВЫХОДОВ:")
ec = best_combo['exit_counts']
total = best_combo['total']
print(f"   🛑 Stop-Loss:     {ec['SL']:4d} ({ec['SL']/total*100:5.1f}%)")
print(f"   ⏱️  TTL Expired:   {ec['TTL']:4d} ({ec['TTL']/total*100:5.1f}%)")
print(f"   🎯 Take-Profit:   {ec['TP_Start']+ec['TP_Mid']+ec['TP_End']:4d} ({(ec['TP_Start']+ec['TP_Mid']+ec['TP_End'])/total*100:5.1f}%)")
print()
print(f"🎯 ДОСТИЖЕНИЕ TARGET ЗОН:")
rs = best_combo['reached_stats']
print(f"   Начало:           {rs['start']:4d} ({rs['start']/total*100:5.1f}%)")
print(f"   Середина:         {rs['mid']:4d} ({rs['mid']/total*100:5.1f}%)")
print(f"   Конец:            {rs['end']:4d} ({rs['end']/total*100:5.1f}%)")
print()

# Risk metrics
print(f"📉 РИСК-МЕТРИКИ:")
pnls = [r['pnl_usd'] for r in results]
std_dev = np.std(pnls)
sharpe = (np.mean(pnls) / std_dev * np.sqrt(len(pnls))) if std_dev > 0 else 0

max_drawdown = 0
peak = 0
cumulative = 0
for pnl in pnls:
    cumulative += pnl
    if cumulative > peak:
        peak = cumulative
    drawdown = peak - cumulative
    if drawdown > max_drawdown:
        max_drawdown = drawdown

print(f"   Std Dev:          ${std_dev:.2f}")
print(f"   Sharpe Ratio:     {sharpe:.2f}")
print(f"   Max Drawdown:     ${max_drawdown:.2f}")
print()
print(f"{'='*95}")
print(f"✅ Бэктест завершён на {len(df_all):,} сигналах (включая CANCELLED)")
print(f"{'='*95}")

