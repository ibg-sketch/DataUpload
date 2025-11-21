"""
Анализ недельной эффективности Smart Money Signal Bot
"""
import pandas as pd
from datetime import datetime, timedelta
import json

# Загрузка логов
try:
    df = pd.read_csv('analysis_log.csv')
    print(f"✅ Загружено {len(df)} сигналов из analysis_log.csv")
except Exception as e:
    print(f"❌ Ошибка загрузки: {e}")
    exit(1)

# Конвертация времени
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

# Определение временных рамок
now = datetime.now()
week_ago = now - timedelta(days=7)
last_3_days = now - timedelta(days=3)
last_24h = now - timedelta(hours=24)

# Фильтрация данных
df_week = df[df['timestamp'] >= week_ago].copy()
df_3days = df[df['timestamp'] >= last_3_days].copy()
df_24h = df[df['timestamp'] >= last_24h].copy()

print(f"\n{'='*80}")
print(f"АНАЛИЗ ЭФФЕКТИВНОСТИ SMART MONEY SIGNAL BOT")
print(f"{'='*80}")

print(f"\n📅 ВРЕМЕННЫЕ РАМКИ:")
print(f"   Всего в базе: {len(df)} сигналов")
print(f"   Последняя неделя (7 дней): {len(df_week)} сигналов")
print(f"   Последние 3 дня: {len(df_3days)} сигналов")
print(f"   Последние 24 часа: {len(df_24h)} сигналов")

if len(df_week) == 0:
    print("\n⚠️ Нет данных за последнюю неделю")
    # Покажем что есть
    print(f"\nСамый старый сигнал: {df['timestamp'].min()}")
    print(f"Самый новый сигнал: {df['timestamp'].max()}")
    df_week = df.copy()
    print(f"\nИспользуем ВСЕ доступные данные: {len(df_week)} сигналов")

def analyze_period(data, period_name):
    """Анализ данных за период"""
    if len(data) == 0:
        print(f"\n⚠️ Нет данных для периода: {period_name}")
        return None
    
    print(f"\n{'='*80}")
    print(f"{period_name}")
    print(f"{'='*80}")
    
    # Фильтр только закрытых сигналов
    closed = data[data['status'].isin(['target_hit', 'stop_loss', 'cancelled', 'ttl_expired'])].copy()
    
    print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего сигналов: {len(data)}")
    print(f"   Закрытых: {len(closed)}")
    print(f"   Активных: {len(data) - len(closed)}")
    
    if len(closed) == 0:
        print("   ⚠️ Нет закрытых сигналов для анализа")
        return None
    
    # Статистика по монетам
    print(f"\n💰 ПО МОНЕТАМ:")
    print(f"   {'Монета':<12} {'Сигналов':<10} {'BUY':<8} {'SELL':<8} {'Закрыто':<10}")
    print(f"   {'-'*12} {'-'*10} {'-'*8} {'-'*8} {'-'*10}")
    
    for symbol in sorted(data['symbol'].unique()):
        sym_data = data[data['symbol'] == symbol]
        sym_closed = closed[closed['symbol'] == symbol]
        buy_count = len(sym_data[sym_data['direction'] == 'BUY'])
        sell_count = len(sym_data[sym_data['direction'] == 'SELL'])
        print(f"   {symbol:<12} {len(sym_data):<10} {buy_count:<8} {sell_count:<8} {len(sym_closed):<10}")
    
    # Винрейт и PnL
    wins = closed[closed['pnl_pct'] > 0]
    losses = closed[closed['pnl_pct'] < 0]
    breakeven = closed[closed['pnl_pct'] == 0]
    
    win_rate = (len(wins) / len(closed)) * 100 if len(closed) > 0 else 0
    
    print(f"\n🎯 РЕЗУЛЬТАТЫ ТОРГОВЛИ:")
    print(f"   Прибыльных: {len(wins)} ({win_rate:.1f}%)")
    print(f"   Убыточных: {len(losses)} ({len(losses)/len(closed)*100:.1f}%)")
    print(f"   Безубыточных: {len(breakeven)}")
    
    # PnL статистика
    total_pnl = closed['pnl_pct'].sum()
    avg_pnl = closed['pnl_pct'].mean()
    
    print(f"\n💵 PROFIT & LOSS:")
    print(f"   Общий P&L: {total_pnl:+.2f}%")
    print(f"   Средний P&L: {avg_pnl:+.3f}%")
    
    if len(wins) > 0:
        avg_win = wins['pnl_pct'].mean()
        max_win = wins['pnl_pct'].max()
        print(f"   Средний профит: +{avg_win:.3f}%")
        print(f"   Максимальный профит: +{max_win:.2f}%")
    
    if len(losses) > 0:
        avg_loss = losses['pnl_pct'].mean()
        max_loss = losses['pnl_pct'].min()
        print(f"   Средний убыток: {avg_loss:.3f}%")
        print(f"   Максимальный убыток: {max_loss:.2f}%")
    
    # Profit Factor
    if len(losses) > 0 and losses['pnl_pct'].sum() != 0:
        profit_factor = abs(wins['pnl_pct'].sum() / losses['pnl_pct'].sum())
        print(f"   Profit Factor: {profit_factor:.2f}")
    
    # Статус закрытия
    print(f"\n🔔 ПРИЧИНЫ ЗАКРЫТИЯ:")
    for status in closed['status'].value_counts().items():
        print(f"   {status[0]}: {status[1]} ({status[1]/len(closed)*100:.1f}%)")
    
    # Направление
    buy_signals = closed[closed['direction'] == 'BUY']
    sell_signals = closed[closed['direction'] == 'SELL']
    
    print(f"\n📈 ПО НАПРАВЛЕНИЯМ:")
    if len(buy_signals) > 0:
        buy_wr = (len(buy_signals[buy_signals['pnl_pct'] > 0]) / len(buy_signals)) * 100
        print(f"   BUY: {len(buy_signals)} сигналов, винрейт {buy_wr:.1f}%, avg P&L {buy_signals['pnl_pct'].mean():+.3f}%")
    
    if len(sell_signals) > 0:
        sell_wr = (len(sell_signals[sell_signals['pnl_pct'] > 0]) / len(sell_signals)) * 100
        print(f"   SELL: {len(sell_signals)} сигналов, винрейт {sell_wr:.1f}%, avg P&L {sell_signals['pnl_pct'].mean():+.3f}%")
    
    # Confidence analysis
    print(f"\n🎲 ПО УРОВНЯМ CONFIDENCE:")
    bins = [0, 60, 70, 80, 90, 100]
    labels = ['60-69%', '70-79%', '80-89%', '90-100%']
    
    closed['conf_bin'] = pd.cut(closed['confidence'], bins=bins, labels=labels, include_lowest=True)
    
    for conf_level in labels:
        conf_data = closed[closed['conf_bin'] == conf_level]
        if len(conf_data) > 0:
            conf_wr = (len(conf_data[conf_data['pnl_pct'] > 0]) / len(conf_data)) * 100
            conf_avg_pnl = conf_data['pnl_pct'].mean()
            print(f"   {conf_level}: {len(conf_data)} сигналов, винрейт {conf_wr:.1f}%, avg P&L {conf_avg_pnl:+.3f}%")
    
    # ТОП-5 лучших и худших сделок
    print(f"\n🏆 ТОП-5 ЛУЧШИХ СДЕЛОК:")
    top_5 = closed.nlargest(5, 'pnl_pct')[['timestamp', 'symbol', 'direction', 'confidence', 'pnl_pct', 'status']]
    for idx, row in top_5.iterrows():
        print(f"   {row['timestamp'].strftime('%m-%d %H:%M')} | {row['symbol']:<10} {row['direction']:<5} {row['confidence']:>3}% | {row['pnl_pct']:>+7.2f}% | {row['status']}")
    
    print(f"\n💔 ТОП-5 ХУДШИХ СДЕЛОК:")
    worst_5 = closed.nsmallest(5, 'pnl_pct')[['timestamp', 'symbol', 'direction', 'confidence', 'pnl_pct', 'status']]
    for idx, row in worst_5.iterrows():
        print(f"   {row['timestamp'].strftime('%m-%d %H:%M')} | {row['symbol']:<10} {row['direction']:<5} {row['confidence']:>3}% | {row['pnl_pct']:>+7.2f}% | {row['status']}")
    
    return {
        'total_signals': len(data),
        'closed_signals': len(closed),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'profit_factor': profit_factor if len(losses) > 0 and losses['pnl_pct'].sum() != 0 else 0
    }

# Анализ по периодам
results = {}
results['week'] = analyze_period(df_week, "📅 ПОСЛЕДНЯЯ НЕДЕЛЯ (7 ДНЕЙ)")

if len(df_3days) > 0:
    results['3days'] = analyze_period(df_3days, "📅 ПОСЛЕДНИЕ 3 ДНЯ")

if len(df_24h) > 0:
    results['24h'] = analyze_period(df_24h, "📅 ПОСЛЕДНИЕ 24 ЧАСА")

# Сравнительная таблица
print(f"\n{'='*80}")
print("СРАВНЕНИЕ ПЕРИОДОВ")
print(f"{'='*80}")
print(f"\n{'Период':<20} {'Сигналов':<12} {'Закрыто':<10} {'Винрейт':<10} {'P&L':<10}")
print(f"{'-'*20} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")

for period_name, period_key in [('Неделя', 'week'), ('3 дня', '3days'), ('24 часа', '24h')]:
    if period_key in results and results[period_key]:
        r = results[period_key]
        print(f"{period_name:<20} {r['total_signals']:<12} {r['closed_signals']:<10} {r['win_rate']:>6.1f}%   {r['total_pnl']:>+7.2f}%")

# Сохранить результаты
with open('weekly_analysis_results.json', 'w') as f:
    json.dump({
        'analysis_date': now.isoformat(),
        'results': results,
        'total_signals_in_db': len(df),
        'date_range': {
            'oldest': df['timestamp'].min().isoformat(),
            'newest': df['timestamp'].max().isoformat()
        }
    }, f, indent=2, default=str)

print(f"\n✅ Результаты сохранены в weekly_analysis_results.json")
