"""
Сравнение P&L по двум методам
"""
import pandas as pd
from datetime import datetime, timedelta

# Загрузка данных
df = pd.read_csv('effectiveness_log.csv')
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])

# За неделю
week_ago = datetime.now() - timedelta(days=7)
df_week = df[df['timestamp_sent'] >= week_ago]

print("="*80)
print("СРАВНЕНИЕ P&L ПО ДВУМ МЕТОДАМ")
print("="*80)

wins = df_week[df_week['result'] == 'WIN']
losses = df_week[df_week['result'] == 'LOSS']
cancelled = df_week[df_week['result'] == 'CANCELLED']

print(f"\n📊 ДАННЫЕ ЗА НЕДЕЛЮ:")
print(f"   WIN: {len(wins)}")
print(f"   LOSS: {len(losses)}")
print(f"   CANCELLED: {len(cancelled)}")

# P&L для каждой категории
pnl_wins = wins['profit_pct'].sum()
pnl_losses = losses['profit_pct'].sum()
pnl_cancelled = cancelled['profit_pct'].sum()

print(f"\n💰 P&L ПО КАТЕГОРИЯМ:")
print(f"   WIN P&L: {pnl_wins:+.2f}%")
print(f"   LOSS P&L: {pnl_losses:+.2f}%")
print(f"   CANCELLED P&L: {pnl_cancelled:+.2f}%")

print(f"\n" + "="*80)
print("МЕТОД 1: effectiveness_reporter.py")
print("="*80)
print("Формула: sum(ALL profit_pct)")
pnl_method1 = df_week['profit_pct'].sum()
print(f"P&L = {pnl_wins:+.2f}% + {pnl_losses:+.2f}% + {pnl_cancelled:+.2f}%")
print(f"P&L = {pnl_method1:+.2f}%")

print(f"\n" + "="*80)
print("МЕТОД 2: Мой анализ (только WIN + LOSS)")
print("="*80)
print("Формула: sum(WIN profit_pct) + sum(LOSS profit_pct)")
pnl_method2 = pnl_wins + pnl_losses
print(f"P&L = {pnl_wins:+.2f}% + {pnl_losses:+.2f}%")
print(f"P&L = {pnl_method2:+.2f}%")

print(f"\n" + "="*80)
print("РАЗНИЦА")
print("="*80)
print(f"Метод 1 (с CANCELLED): {pnl_method1:+.2f}%")
print(f"Метод 2 (без CANCELLED): {pnl_method2:+.2f}%")
print(f"Разница: {pnl_method1 - pnl_method2:+.2f}%")

if abs(pnl_method1 - pnl_method2) < 0.01:
    print(f"\n✅ P&L ОДИНАКОВЫЙ в обоих методах!")
else:
    print(f"\n⚠️ P&L РАЗНЫЙ!")
    print(f"   Разница из-за CANCELLED сигналов: {pnl_cancelled:+.2f}%")

# Средний P&L на CANCELLED сигнал
if len(cancelled) > 0:
    avg_cancelled_pnl = pnl_cancelled / len(cancelled)
    print(f"\n📉 Средний P&L на CANCELLED сигнал: {avg_cancelled_pnl:+.3f}%")

print(f"\n" + "="*80)
print("ВЫВОД")
print("="*80)

if abs(pnl_cancelled) > 1:
    print(f"⚠️ CANCELLED сигналы влияют на общий P&L:")
    print(f"   - Их вклад: {pnl_cancelled:+.2f}%")
    print(f"   - В отчетах показывается: {pnl_method1:+.2f}%")
    print(f"   - Реальный торговый P&L: {pnl_method2:+.2f}%")
else:
    print(f"✅ P&L практически одинаковый в обоих методах")
    print(f"   CANCELLED сигналы почти не влияют на общий P&L")

print()
