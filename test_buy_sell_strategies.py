import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])

# Filter last 7 days
cutoff = datetime.now() - timedelta(days=7)
df_week = df[df['timestamp_sent'] >= cutoff].copy()

# Valid signals only
df_valid = df_week[
    (df_week['result'] != 'CANCELLED') & 
    (df_week['target_min'] != 0) & 
    (df_week['target_max'] != 0)
].copy()

print(f"🔬 ТЕСТ ГИБРИДНОЙ СТРАТЕГИИ: BUY vs SELL")
print(f"=" * 95)
print(f"Период: {df_valid['timestamp_sent'].min().date()} - {df_valid['timestamp_sent'].max().date()}")
print(f"Всего сигналов: {len(df_valid)}")
print()

# Analyze BUY vs SELL distribution
buy_signals = df_valid[df_valid['verdict'] == 'BUY']
sell_signals = df_valid[df_valid['verdict'] == 'SELL']

print(f"📊 РАСПРЕДЕЛЕНИЕ СИГНАЛОВ:")
print(f"   BUY:  {len(buy_signals):4d} ({len(buy_signals)/len(df_valid)*100:5.1f}%)")
print(f"   SELL: {len(sell_signals):4d} ({len(sell_signals)/len(df_valid)*100:5.1f}%)")
print()

# Parameters
POSITION_SIZE = 50
LEVERAGE = 50
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
SL_PERCENT = 10.0

def calculate_pnl(row, buy_strategy, sell_strategy):
    """
    Calculate PnL with different strategies for BUY and SELL
    buy_strategy/sell_strategy: 'start', 'mid', 'end'
    """
    
    entry_price = row['entry_price']
    verdict = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    target_mid = (target_min + target_max) / 2
    final_price = row['final_price']
    
    # Select strategy based on signal type
    strategy = buy_strategy if verdict == 'BUY' else sell_strategy
    
    # SL calculation
    sl_price_move_pct = SL_PERCENT / LEVERAGE
    
    if verdict == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check SL
        if lowest <= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-SL_PERCENT / 100),
                'exit': 'SL',
                'reached_target': False
            }
        
        # Determine exit based on strategy
        if strategy == 'start':
            if highest >= target_min:
                exit_price = target_min
                exit_type = 'TP_Start'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        elif strategy == 'mid':
            if highest >= target_mid:
                exit_price = target_mid
                exit_type = 'TP_Mid'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        else:  # end
            if highest >= target_max:
                exit_price = target_max
                exit_type = 'TP_End'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        
        # Calculate PnL
        pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        
        return {
            'pnl_usd': POSITION_SIZE * pnl_pct / 100,
            'exit': exit_type,
            'reached_target': reached
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        # Check SL
        if highest >= sl_price:
            return {
                'pnl_usd': POSITION_SIZE * (-SL_PERCENT / 100),
                'exit': 'SL',
                'reached_target': False
            }
        
        # For SELL: target_max is start, target_min is end
        if strategy == 'start':
            if lowest <= target_max:
                exit_price = target_max
                exit_type = 'TP_Start'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        elif strategy == 'mid':
            if lowest <= target_mid:
                exit_price = target_mid
                exit_type = 'TP_Mid'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        else:  # end
            if lowest <= target_min:
                exit_price = target_min
                exit_type = 'TP_End'
                reached = True
            else:
                exit_price = final_price
                exit_type = 'TTL'
                reached = False
        
        # Calculate PnL
        pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
        fee = (TAKER_FEE + (MAKER_FEE if 'TP' in exit_type else TAKER_FEE)) * 100
        pnl_pct -= fee
        
        return {
            'pnl_usd': POSITION_SIZE * pnl_pct / 100,
            'exit': exit_type,
            'reached_target': reached
        }

# Test different hybrid strategies
print(f"{'='*95}")
print(f"🎯 ТЕСТ ГИБРИДНЫХ СТРАТЕГИЙ (SL = 10% позиции = 0.20% цены)")
print(f"{'='*95}")
print()

strategies = [
    ('end', 'end', 'Обе на КОНЕЦ зоны (текущая оптимальная)'),
    ('start', 'start', 'Обе на НАЧАЛО зоны'),
    ('start', 'end', 'BUY→Начало, SELL→Конец (ТВОЯ ГИПОТЕЗА)'),
    ('end', 'start', 'BUY→Конец, SELL→Начало (обратная)'),
    ('mid', 'mid', 'Обе на СЕРЕДИНУ'),
    ('mid', 'end', 'BUY→Середина, SELL→Конец'),
]

results_summary = []

for buy_strat, sell_strat, description in strategies:
    results = {'BUY': [], 'SELL': [], 'TOTAL': []}
    
    for _, row in df_valid.iterrows():
        result = calculate_pnl(row, buy_strat, sell_strat)
        results['TOTAL'].append(result)
        results[row['verdict']].append(result)
    
    # Calculate totals
    total_pnl = sum(r['pnl_usd'] for r in results['TOTAL'])
    buy_pnl = sum(r['pnl_usd'] for r in results['BUY'])
    sell_pnl = sum(r['pnl_usd'] for r in results['SELL'])
    
    wins_total = sum(1 for r in results['TOTAL'] if r['pnl_usd'] > 0)
    wins_buy = sum(1 for r in results['BUY'] if r['pnl_usd'] > 0)
    wins_sell = sum(1 for r in results['SELL'] if r['pnl_usd'] > 0)
    
    wr_total = wins_total / len(results['TOTAL']) * 100
    wr_buy = wins_buy / len(results['BUY']) * 100 if len(results['BUY']) > 0 else 0
    wr_sell = wins_sell / len(results['SELL']) * 100 if len(results['SELL']) > 0 else 0
    
    reached_buy = sum(1 for r in results['BUY'] if r['reached_target'])
    reached_sell = sum(1 for r in results['SELL'] if r['reached_target'])
    
    print(f"📋 {description}")
    print(f"{'-'*95}")
    print(f"💰 ОБЩИЙ PnL:        ${total_pnl:+9.2f}/неделю  |  ${total_pnl*52:+11.2f}/год")
    print(f"   ├─ BUY PnL:       ${buy_pnl:+9.2f}  ({buy_pnl/total_pnl*100:+5.1f}%)" if total_pnl != 0 else f"   ├─ BUY PnL:       ${buy_pnl:+9.2f}")
    print(f"   └─ SELL PnL:      ${sell_pnl:+9.2f}  ({sell_pnl/total_pnl*100:+5.1f}%)" if total_pnl != 0 else f"   └─ SELL PnL:      ${sell_pnl:+9.2f}")
    print()
    print(f"📊 WIN RATE:         {wr_total:5.1f}%")
    print(f"   ├─ BUY:           {wr_buy:5.1f}%  ({wins_buy}/{len(results['BUY'])})")
    print(f"   └─ SELL:          {wr_sell:5.1f}%  ({wins_sell}/{len(results['SELL'])})")
    print()
    print(f"🎯 TP ДОСТИЖЕНИЕ:")
    print(f"   ├─ BUY:           {reached_buy:4d}/{len(results['BUY']):4d} ({reached_buy/len(results['BUY'])*100:5.1f}%)")
    print(f"   └─ SELL:          {reached_sell:4d}/{len(results['SELL']):4d} ({reached_sell/len(results['SELL'])*100:5.1f}%)")
    print()
    
    results_summary.append({
        'strategy': description,
        'buy_strat': buy_strat,
        'sell_strat': sell_strat,
        'total_pnl': total_pnl,
        'buy_pnl': buy_pnl,
        'sell_pnl': sell_pnl,
        'wr_total': wr_total,
        'wr_buy': wr_buy,
        'wr_sell': wr_sell
    })

# Find best strategy
print(f"{'='*95}")
print(f"🏆 РЕЙТИНГ СТРАТЕГИЙ")
print(f"{'='*95}")

results_df = pd.DataFrame(results_summary)
results_df = results_df.sort_values('total_pnl', ascending=False)

rank = 1
for _, row in results_df.iterrows():
    medal = '🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else '  '
    print(f"{medal} {rank}. {row['strategy']}")
    print(f"      PnL: ${row['total_pnl']:+.2f}/неделю = ${row['total_pnl']*52:+.2f}/год  |  WR: {row['wr_total']:.1f}%")
    rank += 1

print()
print(f"{'='*95}")
print(f"✅ ВЫВОД")
print(f"{'='*95}")

best = results_df.iloc[0]
hypothesis = results_df[results_df['strategy'].str.contains('ТВОЯ ГИПОТЕЗА')].iloc[0]

print(f"Лучшая стратегия:     {best['strategy']}")
print(f"PnL:                  ${best['total_pnl']:+.2f}/неделю")
print()
print(f"Твоя гипотеза:        {hypothesis['strategy']}")
print(f"PnL:                  ${hypothesis['total_pnl']:+.2f}/неделю")
print()

if hypothesis['total_pnl'] > best['total_pnl']:
    print(f"🎉 ГИПОТЕЗА ПОДТВЕРДИЛАСЬ! Гибридная стратегия на ${hypothesis['total_pnl'] - best['total_pnl']:+.2f}/неделю лучше!")
else:
    diff = best['total_pnl'] - hypothesis['total_pnl']
    print(f"❌ Гипотеза не подтвердилась. Разница: ${diff:+.2f}/неделю в пользу '{best['strategy']}'")

print()
print(f"{'='*95}")

