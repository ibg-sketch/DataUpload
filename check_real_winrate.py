"""
Проверка РЕАЛЬНОГО винрейта как показывают отчеты
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
print("СРАВНЕНИЕ ДВУХ МЕТОДОВ РАСЧЕТА ВИНРЕЙТА")
print("="*80)

wins = len(df_week[df_week['result'] == 'WIN'])
losses = len(df_week[df_week['result'] == 'LOSS'])
cancelled = len(df_week[df_week['result'] == 'CANCELLED'])
total = wins + losses + cancelled

print(f"\n📊 ДАННЫЕ ЗА НЕДЕЛЮ:")
print(f"   WIN: {wins}")
print(f"   LOSS: {losses}")
print(f"   CANCELLED: {cancelled}")
print(f"   TOTAL: {total}")

print(f"\n❌ МЕТОД 1 (НЕПРАВИЛЬНЫЙ) - как считает effectiveness_reporter.py:")
print(f"   Формула: wins / (wins + losses + cancelled)")
wrong_wr = (wins / total * 100) if total > 0 else 0
print(f"   Винрейт: {wrong_wr:.1f}%")
print(f"   ⚠️ Это включает CANCELLED сигналы в знаменатель!")

print(f"\n✅ МЕТОД 2 (ПРАВИЛЬНЫЙ) - как считают в трейдинге:")
print(f"   Формула: wins / (wins + losses)")
tradeable = wins + losses
correct_wr = (wins / tradeable * 100) if tradeable > 0 else 0
print(f"   Винрейт: {correct_wr:.1f}%")
print(f"   ✅ Считаются только закрытые сделки (WIN+LOSS)")

print(f"\n🔍 РАЗНИЦА:")
print(f"   {wrong_wr:.1f}% vs {correct_wr:.1f}%")
print(f"   Разница: {correct_wr - wrong_wr:.1f}%")

print(f"\n💡 ВЫВОД:")
print(f"   - effectiveness_reporter.py считает винрейт НЕПРАВИЛЬНО")
print(f"   - Реальный винрейт (как в трейдинге): {correct_wr:.1f}%")
print(f"   - В отчетах показывается: {wrong_wr:.1f}%")
print()
print("="*80)
