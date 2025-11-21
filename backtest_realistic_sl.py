import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')

# Filter last 7 days
cutoff_date = datetime.now() - timedelta(days=7)
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df_week = df[df['timestamp_sent'] >= cutoff_date].copy()

# Filter valid signals
df_valid = df_week[
    (df_week['result'] != 'CANCELLED') & 
    (df_week['target_min'] != 0) & 
    (df_week['target_max'] != 0)
].copy()

print(f"🔬 БЭКТЕСТ С РЕАЛИСТИЧНЫМИ ПАРАМЕТРАМИ SL")
print(f"=" * 90)
print(f"Сигналов: {len(df_valid)}")
print()

# Trading parameters
POSITION_SIZE = 50  # USD
LEVERAGE = 50
MAKER_FEE = 0.0002  # 0.02%
TAKER_FEE = 0.0005  # 0.05%

# Test multiple SL levels
SL_LEVELS = [1.0, 1.5, 2.0, 3.0, 5.0]  # Percent of position (not price!)

def calculate_strategy_pnl_v2(row, strategy_type, sl_percent):
    """Enhanced version with configurable SL"""
    
    entry_price = row['entry_price']
    verdict = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    target_mid = (target_min + target_max) / 2
    
    # Calculate SL price based on position loss tolerance
    # SL percent is % of position value, not price movement
    sl_price_move_pct = sl_percent / LEVERAGE
    
    if verdict == 'BUY':
        sl_price = entry_price * (1 - sl_price_move_pct / 100)
        
        # Check if SL was hit
        if lowest <= sl_price:
            loss_pct = -sl_percent
            return {
                'pnl_usd': POSITION_SIZE * loss_pct / 100,
                'pnl_pct': loss_pct,
                'reason': 'SL',
                'sl_hit': True
            }
        
        # Strategy-specific exits
        fills = []
        
        if strategy_type == 'conservative':
            if highest >= target_min:
                fills.append((1.0, target_min, 'Target Start'))
            else:
                fills.append((1.0, row['final_price'], 'TTL'))
                
        elif strategy_type == 'balanced':
            if highest >= target_min:
                fills.append((0.5, target_min, 'Start'))
            else:
                fills.append((0.5, row['final_price'], 'TTL'))
                
            if highest >= target_mid:
                fills.append((0.3, target_mid, 'Mid'))
            else:
                fills.append((0.3, row['final_price'], 'TTL'))
                
            if highest >= target_max:
                fills.append((0.2, target_max, 'End'))
            else:
                fills.append((0.2, row['final_price'], 'TTL'))
                
        else:  # aggressive
            if highest >= target_max:
                fills.append((1.0, target_max, 'Target End'))
            else:
                fills.append((1.0, row['final_price'], 'TTL'))
        
        total_pnl_pct = 0
        for portion, exit_price, reason in fills:
            pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
            fee = (TAKER_FEE + (TAKER_FEE if 'TTL' in reason else MAKER_FEE)) * 100
            pnl_pct -= fee
            total_pnl_pct += portion * pnl_pct
            
        return {
            'pnl_usd': POSITION_SIZE * total_pnl_pct / 100,
            'pnl_pct': total_pnl_pct,
            'reason': 'Mixed' if len(fills) > 1 else fills[0][2],
            'sl_hit': False
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + sl_price_move_pct / 100)
        
        if highest >= sl_price:
            loss_pct = -sl_percent
            return {
                'pnl_usd': POSITION_SIZE * loss_pct / 100,
                'pnl_pct': loss_pct,
                'reason': 'SL',
                'sl_hit': True
            }
        
        fills = []
        
        if strategy_type == 'conservative':
            if lowest <= target_max:
                fills.append((1.0, target_max, 'Target Start'))
            else:
                fills.append((1.0, row['final_price'], 'TTL'))
                
        elif strategy_type == 'balanced':
            if lowest <= target_max:
                fills.append((0.5, target_max, 'Start'))
            else:
                fills.append((0.5, row['final_price'], 'TTL'))
                
            if lowest <= target_mid:
                fills.append((0.3, target_mid, 'Mid'))
            else:
                fills.append((0.3, row['final_price'], 'TTL'))
                
            if lowest <= target_min:
                fills.append((0.2, target_min, 'End'))
            else:
                fills.append((0.2, row['final_price'], 'TTL'))
                
        else:  # aggressive
            if lowest <= target_min:
                fills.append((1.0, target_min, 'Target End'))
            else:
                fills.append((1.0, row['final_price'], 'TTL'))
        
        total_pnl_pct = 0
        for portion, exit_price, reason in fills:
            pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
            fee = (TAKER_FEE + (TAKER_FEE if 'TTL' in reason else MAKER_FEE)) * 100
            pnl_pct -= fee
            total_pnl_pct += portion * pnl_pct
            
        return {
            'pnl_usd': POSITION_SIZE * total_pnl_pct / 100,
            'pnl_pct': total_pnl_pct,
            'reason': 'Mixed' if len(fills) > 1 else fills[0][2],
            'sl_hit': False
        }

# Test all combinations
print(f"{'SL %':<8} {'Strategy':<15} {'PnL/Week':<12} {'PnL/Year':<14} {'WR%':<8} {'SL Hits%':<10} {'Avg PnL':<10}")
print(f"=" * 90)

best_combo = None
best_pnl = float('-inf')

for sl_percent in SL_LEVELS:
    for strategy in ['conservative', 'balanced', 'aggressive']:
        results = []
        sl_hits = 0
        
        for _, row in df_valid.iterrows():
            result = calculate_strategy_pnl_v2(row, strategy, sl_percent)
            results.append(result)
            if result['sl_hit']:
                sl_hits += 1
        
        total_pnl = sum(r['pnl_usd'] for r in results)
        wins = sum(1 for r in results if r['pnl_usd'] > 0)
        win_rate = wins / len(results) * 100
        sl_hit_rate = sl_hits / len(results) * 100
        avg_pnl = total_pnl / len(results)
        
        pnl_year = total_pnl * 52
        
        print(f"{sl_percent:<8.1f} {strategy:<15} ${total_pnl:<11.2f} ${pnl_year:<13.2f} "
              f"{win_rate:<7.1f} {sl_hit_rate:<9.1f} ${avg_pnl:<9.2f}")
        
        if total_pnl > best_pnl:
            best_pnl = total_pnl
            best_combo = {
                'sl': sl_percent,
                'strategy': strategy,
                'pnl_week': total_pnl,
                'pnl_year': pnl_year,
                'win_rate': win_rate,
                'sl_hit_rate': sl_hit_rate,
                'avg_pnl': avg_pnl,
                'results': results
            }

print()
print(f"=" * 90)
print(f"🏆 ЛУЧШАЯ КОМБИНАЦИЯ")
print(f"=" * 90)
print(f"Стратегия:       {best_combo['strategy'].upper()}")
print(f"Stop-Loss:       {best_combo['sl']}% от позиции")
print(f"")
print(f"💰 PnL/неделя:   ${best_combo['pnl_week']:+,.2f}")
print(f"📅 PnL/месяц:    ${best_combo['pnl_week']*4.33:+,.2f}")
print(f"🎯 PnL/год:      ${best_combo['pnl_year']:+,.2f}")
print(f"")
print(f"📊 Win Rate:     {best_combo['win_rate']:.1f}%")
print(f"🛑 SL Hit Rate:  {best_combo['sl_hit_rate']:.1f}%")
print(f"💵 Avg PnL:      ${best_combo['avg_pnl']:+.2f} на сделку")
print()

# Risk metrics for best combo
pnls = [r['pnl_usd'] for r in best_combo['results']]
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

print(f"📉 Риск-метрики:")
print(f"   Std Dev:      ${std_dev:.2f}")
print(f"   Sharpe Ratio: {sharpe:.2f}")
print(f"   Max Drawdown: ${max_drawdown:.2f}")
print()

print(f"=" * 90)
print(f"✅ Анализ завершён")
print(f"=" * 90)

