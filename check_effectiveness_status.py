print("="*80)
print("ДИАГНОСТИКА: Почему нет отчетов эффективности")
print("="*80)

import os
import subprocess

# 1. Проверка переменных окружения
print("\n✅ 1. TELEGRAM CHANNELS:")
print(f"   Signal Bot ID: {os.getenv('TELEGRAM_CHAT_ID', 'NOT SET')}")
print(f"   Trading Bot ID: {os.getenv('TRADING_TELEGRAM_CHAT_ID', 'NOT SET')}")

# 2. Проверка процесса
print("\n❌ 2. EFFECTIVENESS_REPORTER ПРОЦЕСС:")
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
if 'effectiveness_reporter' in result.stdout:
    print("   ✅ Запущен")
else:
    print("   ❌ НЕ ЗАПУЩЕН!")

# 3. Проверка файла
print("\n✅ 3. ФАЙЛ EFFECTIVENESS_REPORTER.PY:")
if os.path.exists('effectiveness_reporter.py'):
    print("   ✅ Существует")
else:
    print("   ❌ Не найден")

# 4. Проверка данных
print("\n✅ 4. EFFECTIVENESS_LOG.CSV:")
if os.path.exists('effectiveness_log.csv'):
    import pandas as pd
    df = pd.read_csv('effectiveness_log.csv')
    print(f"   ✅ {len(df)} записей в логе")
else:
    print("   ❌ Файл не найден")

print("\n" + "="*80)
print("ВЫВОД:")
print("="*80)
print("❌ ПРОБЛЕМА: effectiveness_reporter.py НЕ ЗАПУЩЕН как workflow!")
print("   Отчеты не отправляются, потому что скрипт не работает.")
print("\n💡 РЕШЕНИЕ:")
print("   Нужно добавить workflow для effectiveness_reporter.py")
print("="*80)
