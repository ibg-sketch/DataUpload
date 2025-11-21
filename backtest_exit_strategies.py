import pandas as pd
from datetime import datetime, timedelta

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

print(f"🔬 БЭКТЕСТ СТРАТЕГИЙ ВЫХОДА ИЗ ПОЗИЦИЙ")
print(f"=" * 80)
print(f"Период: {df_valid['timestamp_sent'].min()} - {df_valid['timestamp_sent'].max()}")
print(f"Валидных сигналов: {len(df_valid)}")
print()

# Trading parameters
POSITION_SIZE = 50  # USD
LEVERAGE = 50
SL_PERCENT = 2.0  # 2% stop-loss
MAKER_FEE = 0.0002  # 0.02%
TAKER_FEE = 0.0005  # 0.05%

def calculate_strategy_pnl(row, strategy_type):
    """
    Calculate PnL for a given exit strategy
    
    Strategy types:
    - 'conservative': Exit at start of target zone (target_min for BUY, target_max for SELL)
    - 'balanced': 50% at start, 30% at middle, 20% at end
    - 'aggressive': Hold until end of zone (target_max for BUY, target_min for SELL)
    """
    
    entry_price = row['entry_price']
    verdict = row['verdict']
    highest = row['highest_reached']
    lowest = row['lowest_reached']
    target_min = row['target_min']
    target_max = row['target_max']
    target_mid = (target_min + target_max) / 2
    
    # Calculate SL price
    if verdict == 'BUY':
        sl_price = entry_price * (1 - SL_PERCENT / 100 / LEVERAGE)
        
        # Check if SL was hit
        if lowest <= sl_price:
            # Hit SL - full loss
            loss_pct = -SL_PERCENT / LEVERAGE * 100
            exit_price = sl_price
            reason = 'SL'
            return {
                'pnl_usd': POSITION_SIZE * loss_pct / 100,
                'pnl_pct': loss_pct,
                'exit_price': exit_price,
                'reason': reason,
                'fills': [(1.0, exit_price, reason)]
            }
        
        # Strategy-specific exits
        fills = []  # (portion, price, reason)
        
        if strategy_type == 'conservative':
            # Exit at target_min
            if highest >= target_min:
                exit_price = target_min
                reason = 'Target Start'
                fills.append((1.0, exit_price, reason))
            else:
                # TTL expired - exit at final price
                exit_price = row['final_price']
                reason = 'TTL'
                fills.append((1.0, exit_price, reason))
                
        elif strategy_type == 'balanced':
            # 50% at target_min, 30% at mid, 20% at target_max
            if highest >= target_min:
                fills.append((0.5, target_min, 'Start (50%)'))
            else:
                fills.append((0.5, row['final_price'], 'TTL (50%)'))
                
            if highest >= target_mid:
                fills.append((0.3, target_mid, 'Mid (30%)'))
            else:
                fills.append((0.3, row['final_price'], 'TTL (30%)'))
                
            if highest >= target_max:
                fills.append((0.2, target_max, 'End (20%)'))
            else:
                fills.append((0.2, row['final_price'], 'TTL (20%)'))
                
        else:  # aggressive
            # Hold until target_max
            if highest >= target_max:
                exit_price = target_max
                reason = 'Target End'
                fills.append((1.0, exit_price, reason))
            else:
                # TTL expired
                exit_price = row['final_price']
                reason = 'TTL'
                fills.append((1.0, exit_price, reason))
        
        # Calculate weighted average PnL
        total_pnl_pct = 0
        for portion, exit_price, reason in fills:
            pnl_pct = (exit_price - entry_price) / entry_price * 100 * LEVERAGE
            # Subtract fees (entry TAKER + exit depends on fill)
            if 'TTL' in reason:
                fee = (TAKER_FEE + TAKER_FEE) * 100  # Both market orders
            else:
                fee = (TAKER_FEE + MAKER_FEE) * 100  # Entry market, exit limit
            pnl_pct -= fee
            total_pnl_pct += portion * pnl_pct
            
        pnl_usd = POSITION_SIZE * total_pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'pnl_pct': total_pnl_pct,
            'exit_price': sum(p * px for p, px, _ in fills) / sum(p for p, _, _ in fills),
            'reason': 'Mixed' if len(fills) > 1 else fills[0][2],
            'fills': fills
        }
        
    else:  # SELL
        sl_price = entry_price * (1 + SL_PERCENT / 100 / LEVERAGE)
        
        # Check if SL was hit
        if highest >= sl_price:
            # Hit SL - full loss
            loss_pct = -SL_PERCENT / LEVERAGE * 100
            exit_price = sl_price
            reason = 'SL'
            return {
                'pnl_usd': POSITION_SIZE * loss_pct / 100,
                'pnl_pct': loss_pct,
                'exit_price': exit_price,
                'reason': reason,
                'fills': [(1.0, exit_price, reason)]
            }
        
        # For SELL: target_max is start, target_min is end
        fills = []
        
        if strategy_type == 'conservative':
            # Exit at target_max (start of zone)
            if lowest <= target_max:
                exit_price = target_max
                reason = 'Target Start'
                fills.append((1.0, exit_price, reason))
            else:
                # TTL expired
                exit_price = row['final_price']
                reason = 'TTL'
                fills.append((1.0, exit_price, reason))
                
        elif strategy_type == 'balanced':
            # 50% at target_max, 30% at mid, 20% at target_min
            if lowest <= target_max:
                fills.append((0.5, target_max, 'Start (50%)'))
            else:
                fills.append((0.5, row['final_price'], 'TTL (50%)'))
                
            if lowest <= target_mid:
                fills.append((0.3, target_mid, 'Mid (30%)'))
            else:
                fills.append((0.3, row['final_price'], 'TTL (30%)'))
                
            if lowest <= target_min:
                fills.append((0.2, target_min, 'End (20%)'))
            else:
                fills.append((0.2, row['final_price'], 'TTL (20%)'))
                
        else:  # aggressive
            # Hold until target_min (end)
            if lowest <= target_min:
                exit_price = target_min
                reason = 'Target End'
                fills.append((1.0, exit_price, reason))
            else:
                # TTL expired
                exit_price = row['final_price']
                reason = 'TTL'
                fills.append((1.0, exit_price, reason))
        
        # Calculate weighted average PnL
        total_pnl_pct = 0
        for portion, exit_price, reason in fills:
            pnl_pct = (entry_price - exit_price) / entry_price * 100 * LEVERAGE
            # Subtract fees
            if 'TTL' in reason:
                fee = (TAKER_FEE + TAKER_FEE) * 100
            else:
                fee = (TAKER_FEE + MAKER_FEE) * 100
            pnl_pct -= fee
            total_pnl_pct += portion * pnl_pct
            
        pnl_usd = POSITION_SIZE * total_pnl_pct / 100
        
        return {
            'pnl_usd': pnl_usd,
            'pnl_pct': total_pnl_pct,
            'exit_price': sum(p * px for p, px, _ in fills) / sum(p for p, _, _ in fills),
            'reason': 'Mixed' if len(fills) > 1 else fills[0][2],
            'fills': fills
        }

# Calculate PnL for each strategy
results = {
    'conservative': {'trades': [], 'total_pnl': 0, 'wins': 0, 'losses': 0, 'sl_hits': 0, 'ttl_exits': 0},
    'balanced': {'trades': [], 'total_pnl': 0, 'wins': 0, 'losses': 0, 'sl_hits': 0, 'ttl_exits': 0},
    'aggressive': {'trades': [], 'total_pnl': 0, 'wins': 0, 'losses': 0, 'sl_hits': 0, 'ttl_exits': 0}
}

for _, row in df_valid.iterrows():
    for strategy in ['conservative', 'balanced', 'aggressive']:
        trade_result = calculate_strategy_pnl(row, strategy)
        
        results[strategy]['trades'].append(trade_result)
        results[strategy]['total_pnl'] += trade_result['pnl_usd']
        
        if trade_result['pnl_usd'] > 0:
            results[strategy]['wins'] += 1
        else:
            results[strategy]['losses'] += 1
            
        if trade_result['reason'] == 'SL':
            results[strategy]['sl_hits'] += 1
        elif trade_result['reason'] == 'TTL' or 'TTL' in trade_result['reason']:
            results[strategy]['ttl_exits'] += 1

# Print results
print(f"{'='*80}")
print(f"💰 РЕЗУЛЬТАТЫ БЭКТЕСТА (Позиция: ${POSITION_SIZE}, Плечо: {LEVERAGE}x, SL: {SL_PERCENT}%)")
print(f"{'='*80}")
print()

strategies_display = {
    'conservative': '🛡️  КОНСЕРВАТИВНАЯ (выход на начале зоны)',
    'balanced': '⚖️  СБАЛАНСИРОВАННАЯ (50%/30%/20%)',
    'aggressive': '🚀 АГРЕССИВНАЯ (выход на конце зоны)'
}

for strategy_name, display_name in strategies_display.items():
    data = results[strategy_name]
    total_trades = len(data['trades'])
    total_pnl = data['total_pnl']
    wins = data['wins']
    losses = data['losses']
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0
    sl_hits = data['sl_hits']
    ttl_exits = data['ttl_exits']
    
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
    
    print(f"{display_name}")
    print(f"{'-'*80}")
    print(f"Всего сделок:        {total_trades:4d}")
    print(f"Прибыльных:          {wins:4d} ({win_rate:5.1f}%)")
    print(f"Убыточных:           {losses:4d} ({100-win_rate:5.1f}%)")
    print(f"SL срабатываний:     {sl_hits:4d} ({sl_hits/total_trades*100:5.1f}%)")
    print(f"TTL выходов:         {ttl_exits:4d} ({ttl_exits/total_trades*100:5.1f}%)")
    print(f"")
    print(f"💵 Общий PnL:        ${total_pnl:+8.2f}")
    print(f"📊 Средний PnL:      ${avg_pnl:+8.2f} на сделку")
    print(f"📈 PnL в неделю:     ${total_pnl:+8.2f}")
    print(f"📅 PnL в месяц:      ${total_pnl*4.33:+8.2f} (прогноз)")
    print(f"🎯 PnL в год:        ${total_pnl*52:+8.2f} (прогноз)")
    print()

# Compare strategies
print(f"{'='*80}")
print(f"📊 СРАВНЕНИЕ СТРАТЕГИЙ")
print(f"{'='*80}")

# Create comparison table
comparison_data = []
for strategy_name in ['conservative', 'balanced', 'aggressive']:
    data = results[strategy_name]
    comparison_data.append({
        'strategy': strategy_name,
        'pnl_week': data['total_pnl'],
        'pnl_month': data['total_pnl'] * 4.33,
        'pnl_year': data['total_pnl'] * 52,
        'win_rate': data['wins'] / len(data['trades']) * 100,
        'avg_pnl': data['total_pnl'] / len(data['trades'])
    })

comparison_df = pd.DataFrame(comparison_data)
comparison_df = comparison_df.sort_values('pnl_week', ascending=False)

print()
rank = 1
for _, row in comparison_df.iterrows():
    medal = '🥇' if rank == 1 else '🥈' if rank == 2 else '🥉'
    strategy_name = row['strategy'].upper()
    print(f"{medal} {rank}. {strategy_name:15s} | Неделя: ${row['pnl_week']:+8.2f} | "
          f"Месяц: ${row['pnl_month']:+9.2f} | Год: ${row['pnl_year']:+10.2f} | "
          f"WR: {row['win_rate']:5.1f}%")
    rank += 1

print()
print(f"{'='*80}")
print(f"✅ РЕКОМЕНДАЦИЯ")
print(f"{'='*80}")

best_strategy = comparison_df.iloc[0]
worst_strategy = comparison_df.iloc[-1]

improvement = best_strategy['pnl_week'] - worst_strategy['pnl_week']
improvement_pct = (improvement / abs(worst_strategy['pnl_week']) * 100) if worst_strategy['pnl_week'] != 0 else 0

print(f"Лучшая стратегия: {best_strategy['strategy'].upper()}")
print(f"PnL преимущество: ${improvement:+.2f} в неделю (+{improvement_pct:.1f}%)")
print(f"Годовая разница:  ${improvement * 52:+.2f}")
print()

# Risk-adjusted metrics
print(f"{'='*80}")
print(f"📉 РИСК-МЕТРИКИ")
print(f"{'='*80}")

for strategy_name in ['conservative', 'balanced', 'aggressive']:
    data = results[strategy_name]
    trades_pnl = [t['pnl_usd'] for t in data['trades']]
    
    import numpy as np
    std_dev = np.std(trades_pnl)
    sharpe = (np.mean(trades_pnl) / std_dev * np.sqrt(len(trades_pnl))) if std_dev > 0 else 0
    
    max_drawdown = 0
    peak = 0
    cumulative = 0
    for pnl in trades_pnl:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    print(f"{strategy_name.upper():15s} | Std Dev: ${std_dev:6.2f} | "
          f"Sharpe: {sharpe:6.2f} | Max DD: ${max_drawdown:7.2f}")

print()
print(f"{'='*80}")
print(f"✅ Бэктест завершён")
print(f"{'='*80}")

