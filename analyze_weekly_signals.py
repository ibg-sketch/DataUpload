"""
Анализ эффективности Smart Money Signal Bot за неделю
"""
import pandas as pd
from datetime import datetime, timedelta
import json

# Загрузка результатов
try:
    df = pd.read_csv('effectiveness_log.csv')
    print(f"✅ Загружено {len(df)} сигналов из effectiveness_log.csv")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    exit(1)

# Конвертация времени
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df['timestamp_checked'] = pd.to_datetime(df['timestamp_checked'])
df = df.sort_values('timestamp_sent')

# Временные рамки
now = datetime.now()
week_ago = now - timedelta(days=7)
last_3_days = now - timedelta(days=3)
last_24h = now - timedelta(hours=24)

# Фильтры
df_week = df[df['timestamp_sent'] >= week_ago].copy()
df_3days = df[df['timestamp_sent'] >= last_3_days].copy()
df_24h = df[df['timestamp_sent'] >= last_24h].copy()

print(f"\n{'='*80}")
print(f"АНАЛИЗ ЭФФЕКТИВНОСТИ SMART MONEY SIGNAL BOT")
print(f"{'='*80}")

print(f"\n📅 ДАННЫЕ:")
print(f"   Самый старый сигнал: {df['timestamp_sent'].min()}")
print(f"   Самый новый сигнал: {df['timestamp_sent'].max()}")
print(f"   Диапазон: {(df['timestamp_sent'].max() - df['timestamp_sent'].min()).days} дней")

print(f"\n📊 ПО ПЕРИОДАМ:")
print(f"   Всего в базе: {len(df)} сигналов")
print(f"   Последняя неделя: {len(df_week)} сигналов")
print(f"   Последние 3 дня: {len(df_3days)} сигналов")
print(f"   Последние 24 часа: {len(df_24h)} сигналов")

def analyze_period(data, period_name):
    """Детальный анализ периода"""
    if len(data) == 0:
        print(f"\n⚠️ Нет данных для: {period_name}")
        return None
    
    print(f"\n{'='*80}")
    print(f"{period_name}")
    print(f"{'='*80}")
    
    # Результаты
    wins = data[data['result'] == 'WIN']
    losses = data[data['result'] == 'LOSS']
    cancelled = data[data['result'] == 'CANCELLED']
    ttl_expired = data[data['result'] == 'TTL EXPIRED']
    
    total = len(data)
    win_rate = (len(wins) / total) * 100 if total > 0 else 0
    
    print(f"\n🎯 РЕЗУЛЬТАТЫ:")
    print(f"   Всего сигналов: {total}")
    print(f"   ✅ WIN: {len(wins)} ({len(wins)/total*100:.1f}%) - винрейт: {win_rate:.1f}%")
    print(f"   ❌ LOSS: {len(losses)} ({len(losses)/total*100:.1f}%)")
    print(f"   ⚪ CANCELLED: {len(cancelled)} ({len(cancelled)/total*100:.1f}%)")
    print(f"   ⏱️ TTL EXPIRED: {len(ttl_expired)} ({len(ttl_expired)/total*100:.1f}%)")
    
    # P&L анализ (только WIN и LOSS)
    tradeable = data[data['result'].isin(['WIN', 'LOSS'])].copy()
    
    if len(tradeable) > 0:
        total_pnl = tradeable['profit_pct'].sum()
        avg_pnl = tradeable['profit_pct'].mean()
        
        print(f"\n💰 PROFIT & LOSS (только WIN/LOSS):")
        print(f"   Торгуемых сигналов: {len(tradeable)}")
        print(f"   Общий P&L: {total_pnl:+.2f}%")
        print(f"   Средний P&L: {avg_pnl:+.3f}%")
        
        if len(wins) > 0:
            avg_win = wins['profit_pct'].mean()
            max_win = wins['profit_pct'].max()
            print(f"   Средний профит: +{avg_win:.3f}%")
            print(f"   Максимальный профит: +{max_win:.2f}%")
        
        if len(losses) > 0:
            avg_loss = losses['profit_pct'].mean()
            max_loss = losses['profit_pct'].min()
            print(f"   Средний убыток: {avg_loss:.3f}%")
            print(f"   Максимальный убыток: {max_loss:.2f}%")
        
        # Profit Factor
        if len(losses) > 0:
            total_profit = wins['profit_pct'].sum()
            total_loss = abs(losses['profit_pct'].sum())
            if total_loss > 0:
                pf = total_profit / total_loss
                print(f"   Profit Factor: {pf:.2f}")
    
    # По монетам
    print(f"\n💎 ПО МОНЕТАМ (ТОП-10):")
    print(f"   {'Монета':<12} {'Всего':<8} {'WIN':<7} {'LOSS':<7} {'Винрейт':<10} {'P&L'}")
    print(f"   {'-'*12} {'-'*8} {'-'*7} {'-'*7} {'-'*10} {'-'*10}")
    
    for symbol in data['symbol'].value_counts().head(10).index:
        sym_data = data[data['symbol'] == symbol]
        sym_tradeable = sym_data[sym_data['result'].isin(['WIN', 'LOSS'])]
        
        sym_wins = len(sym_data[sym_data['result'] == 'WIN'])
        sym_losses = len(sym_data[sym_data['result'] == 'LOSS'])
        sym_wr = (sym_wins / len(sym_tradeable) * 100) if len(sym_tradeable) > 0 else 0
        sym_pnl = sym_tradeable['profit_pct'].sum() if len(sym_tradeable) > 0 else 0
        
        print(f"   {symbol:<12} {len(sym_data):<8} {sym_wins:<7} {sym_losses:<7} {sym_wr:>6.1f}%    {sym_pnl:>+7.2f}%")
    
    # По направлению
    buy_data = data[data['verdict'] == 'BUY']
    sell_data = data[data['verdict'] == 'SELL']
    
    print(f"\n📈 ПО НАПРАВЛЕНИЯМ:")
    
    if len(buy_data) > 0:
        buy_tradeable = buy_data[buy_data['result'].isin(['WIN', 'LOSS'])]
        buy_wins = len(buy_data[buy_data['result'] == 'WIN'])
        buy_wr = (buy_wins / len(buy_tradeable) * 100) if len(buy_tradeable) > 0 else 0
        buy_pnl = buy_tradeable['profit_pct'].sum() if len(buy_tradeable) > 0 else 0
        print(f"   BUY: {len(buy_data)} сигналов, винрейт {buy_wr:.1f}%, P&L {buy_pnl:+.2f}%")
    
    if len(sell_data) > 0:
        sell_tradeable = sell_data[sell_data['result'].isin(['WIN', 'LOSS'])]
        sell_wins = len(sell_data[sell_data['result'] == 'WIN'])
        sell_wr = (sell_wins / len(sell_tradeable) * 100) if len(sell_tradeable) > 0 else 0
        sell_pnl = sell_tradeable['profit_pct'].sum() if len(sell_tradeable) > 0 else 0
        print(f"   SELL: {len(sell_data)} сигналов, винрейт {sell_wr:.1f}%, P&L {sell_pnl:+.2f}%")
    
    # По уровням confidence
    print(f"\n🎲 ПО УРОВНЯМ CONFIDENCE:")
    bins = [0, 60, 70, 80, 90, 100]
    labels = ['60-69%', '70-79%', '80-89%', '90-100%']
    
    data['conf_bin'] = pd.cut(data['confidence']*100, bins=bins, labels=labels, include_lowest=True)
    
    for conf_level in labels:
        conf_data = data[data['conf_bin'] == conf_level]
        if len(conf_data) > 0:
            conf_tradeable = conf_data[conf_data['result'].isin(['WIN', 'LOSS'])]
            conf_wins = len(conf_data[conf_data['result'] == 'WIN'])
            conf_wr = (conf_wins / len(conf_tradeable) * 100) if len(conf_tradeable) > 0 else 0
            conf_pnl = conf_tradeable['profit_pct'].sum() if len(conf_tradeable) > 0 else 0
            print(f"   {conf_level}: {len(conf_data)} сигналов, винрейт {conf_wr:.1f}%, P&L {conf_pnl:+.2f}%")
    
    # ТОП сделок
    tradeable_sorted = tradeable.copy() if len(tradeable) > 0 else pd.DataFrame()
    
    if len(tradeable_sorted) >= 5:
        print(f"\n🏆 ТОП-5 ЛУЧШИХ СДЕЛОК:")
        top_5 = tradeable_sorted.nlargest(5, 'profit_pct')
        for _, row in top_5.iterrows():
            ts = row['timestamp_sent'].strftime('%m-%d %H:%M')
            print(f"   {ts} | {row['symbol']:<10} {row['verdict']:<5} {row['confidence']*100:>3.0f}% | {row['profit_pct']:>+7.2f}% | {row['result']}")
        
        print(f"\n💔 ТОП-5 ХУДШИХ СДЕЛОК:")
        worst_5 = tradeable_sorted.nsmallest(5, 'profit_pct')
        for _, row in worst_5.iterrows():
            ts = row['timestamp_sent'].strftime('%m-%d %H:%M')
            print(f"   {ts} | {row['symbol']:<10} {row['verdict']:<5} {row['confidence']*100:>3.0f}% | {row['profit_pct']:>+7.2f}% | {row['result']}")
    
    return {
        'total': total,
        'win_rate': win_rate,
        'total_pnl': total_pnl if len(tradeable) > 0 else 0,
        'avg_pnl': avg_pnl if len(tradeable) > 0 else 0,
        'wins': len(wins),
        'losses': len(losses),
        'cancelled': len(cancelled)
    }

# Анализ по периодам
results = {}

if len(df_week) > 0:
    results['week'] = analyze_period(df_week, "📅 ПОСЛЕДНЯЯ НЕДЕЛЯ (7 ДНЕЙ)")

if len(df_3days) > 0:
    results['3days'] = analyze_period(df_3days, "📅 ПОСЛЕДНИЕ 3 ДНЯ")

if len(df_24h) > 0:
    results['24h'] = analyze_period(df_24h, "📅 ПОСЛЕДНИЕ 24 ЧАСА")

# Сравнительная таблица
print(f"\n{'='*80}")
print("СРАВНЕНИЕ ПЕРИОДОВ")
print(f"{'='*80}")
print(f"\n{'Период':<15} {'Сигналов':<10} {'WIN':<8} {'LOSS':<8} {'Винрейт':<10} {'P&L'}")
print(f"{'-'*15} {'-'*10} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")

for period_name, period_key in [('Неделя', 'week'), ('3 дня', '3days'), ('24 часа', '24h')]:
    if period_key in results and results[period_key]:
        r = results[period_key]
        print(f"{period_name:<15} {r['total']:<10} {r['wins']:<8} {r['losses']:<8} {r['win_rate']:>6.1f}%   {r['total_pnl']:>+7.2f}%")

# Сохранить
with open('weekly_analysis_results.json', 'w') as f:
    json.dump({
        'analysis_date': now.isoformat(),
        'results': results,
        'date_range': {
            'oldest': df['timestamp_sent'].min().isoformat(),
            'newest': df['timestamp_sent'].max().isoformat(),
            'days': (df['timestamp_sent'].max() - df['timestamp_sent'].min()).days
        }
    }, f, indent=2, default=str)

print(f"\n✅ Результаты сохранены в weekly_analysis_results.json")
