import pandas as pd
from datetime import datetime, timedelta

# Load effectiveness log
df = pd.read_csv('effectiveness_log.csv')

# Filter last 7 days
cutoff_date = datetime.now() - timedelta(days=7)
df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
df_week = df[df['timestamp_sent'] >= cutoff_date].copy()

print(f"📊 АНАЛИЗ TARGET ЗОН ЗА ПОСЛЕДНИЕ 7 ДНЕЙ")
print(f"=" * 70)
print(f"Всего сигналов за неделю: {len(df_week)}")
print(f"Период: {df_week['timestamp_sent'].min()} - {df_week['timestamp_sent'].max()}")
print()

# Filter out CANCELLED signals and signals with target_min/max = 0
df_valid = df_week[
    (df_week['result'] != 'CANCELLED') & 
    (df_week['target_min'] != 0) & 
    (df_week['target_max'] != 0)
].copy()

print(f"Сигналов с валидными target зонами (исключая CANCELLED): {len(df_valid)}")
print()

if len(df_valid) == 0:
    print("⚠️ Нет сигналов с валидными target зонами за последние 7 дней")
    exit()

# Calculate middle of target zone
df_valid['target_mid'] = (df_valid['target_min'] + df_valid['target_max']) / 2

# Analyze for BUY signals
buy_signals = df_valid[df_valid['verdict'] == 'BUY'].copy()
reached_start_buy = 0
reached_mid_buy = 0
reached_end_buy = 0

for _, row in buy_signals.iterrows():
    highest = row['highest_reached']
    target_min = row['target_min']
    target_mid = row['target_mid']
    target_max = row['target_max']
    
    if highest >= target_min:
        reached_start_buy += 1
    if highest >= target_mid:
        reached_mid_buy += 1
    if highest >= target_max:
        reached_end_buy += 1

# Analyze for SELL signals
sell_signals = df_valid[df_valid['verdict'] == 'SELL'].copy()
reached_start_sell = 0
reached_mid_sell = 0
reached_end_sell = 0

for _, row in sell_signals.iterrows():
    lowest = row['lowest_reached']
    target_max = row['target_max']  # For SELL, target_max is the entry point of zone
    target_mid = row['target_mid']
    target_min = row['target_min']  # For SELL, target_min is the end of zone
    
    if lowest <= target_max:
        reached_start_sell += 1
    if lowest <= target_mid:
        reached_mid_sell += 1
    if lowest <= target_min:
        reached_end_sell += 1

# Combined statistics
total_buy = len(buy_signals)
total_sell = len(sell_signals)
total_valid = total_buy + total_sell

reached_start_total = reached_start_buy + reached_start_sell
reached_mid_total = reached_mid_buy + reached_mid_sell
reached_end_total = reached_end_buy + reached_end_sell

print(f"{'='*70}")
print(f"📈 BUY СИГНАЛЫ (всего {total_buy})")
print(f"{'='*70}")
if total_buy > 0:
    print(f"🎯 Достигли НАЧАЛА target зоны (target_min):  {reached_start_buy:4d} ({reached_start_buy/total_buy*100:5.1f}%)")
    print(f"🎯 Достигли СЕРЕДИНЫ target зоны:             {reached_mid_buy:4d} ({reached_mid_buy/total_buy*100:5.1f}%)")
    print(f"🎯 Достигли КОНЦА target зоны (target_max):   {reached_end_buy:4d} ({reached_end_buy/total_buy*100:5.1f}%)")
else:
    print("Нет BUY сигналов")
print()

print(f"{'='*70}")
print(f"📉 SELL СИГНАЛЫ (всего {total_sell})")
print(f"{'='*70}")
if total_sell > 0:
    print(f"🎯 Достигли НАЧАЛА target зоны (target_max):  {reached_start_sell:4d} ({reached_start_sell/total_sell*100:5.1f}%)")
    print(f"🎯 Достигли СЕРЕДИНЫ target зоны:             {reached_mid_sell:4d} ({reached_mid_sell/total_sell*100:5.1f}%)")
    print(f"🎯 Достигли КОНЦА target зоны (target_min):   {reached_end_sell:4d} ({reached_end_sell/total_sell*100:5.1f}%)")
else:
    print("Нет SELL сигналов")
print()

print(f"{'='*70}")
print(f"🔄 ОБЩАЯ СТАТИСТИКА (BUY + SELL, всего {total_valid})")
print(f"{'='*70}")
print(f"🎯 Достигли НАЧАЛА target зоны:   {reached_start_total:4d} ({reached_start_total/total_valid*100:5.1f}%)")
print(f"🎯 Достигли СЕРЕДИНЫ target зоны: {reached_mid_total:4d} ({reached_mid_total/total_valid*100:5.1f}%)")
print(f"🎯 Достигли КОНЦА target зоны:    {reached_end_total:4d} ({reached_end_total/total_valid*100:5.1f}%)")
print()

# Breakdown by result type
print(f"{'='*70}")
print(f"📊 ДЕТАЛИЗАЦИЯ ПО РЕЗУЛЬТАТАМ")
print(f"{'='*70}")
result_counts = df_valid['result'].value_counts()
for result_type, count in result_counts.items():
    pct = count / len(df_valid) * 100
    print(f"{result_type:12s}: {count:4d} ({pct:5.1f}%)")
print()

# Symbol breakdown
print(f"{'='*70}")
print(f"💰 ТОП-5 МОНЕТ ПО КОЛИЧЕСТВУ СИГНАЛОВ")
print(f"{'='*70}")
symbol_counts = df_valid['symbol'].value_counts().head(5)
for symbol, count in symbol_counts.items():
    pct = count / len(df_valid) * 100
    print(f"{symbol:12s}: {count:4d} ({pct:5.1f}%)")
print()

# Average progress into target zone
print(f"{'='*70}")
print(f"📏 СРЕДНИЙ ПРОГРЕСС В TARGET ЗОНУ")
print(f"{'='*70}")

# Calculate penetration depth for each signal
def calculate_penetration(row):
    """Calculate how deep price penetrated into target zone (0-100%)"""
    if row['verdict'] == 'BUY':
        entry = row['entry_price']
        target_start = row['target_min']
        target_end = row['target_max']
        reached = row['highest_reached']
        
        if reached < target_start:
            return 0  # Didn't reach zone
        elif reached >= target_end:
            return 100  # Reached full target
        else:
            # Partial penetration
            zone_size = target_end - target_start
            penetration = reached - target_start
            return (penetration / zone_size * 100) if zone_size > 0 else 0
    else:  # SELL
        entry = row['entry_price']
        target_start = row['target_max']
        target_end = row['target_min']
        reached = row['lowest_reached']
        
        if reached > target_start:
            return 0  # Didn't reach zone
        elif reached <= target_end:
            return 100  # Reached full target
        else:
            # Partial penetration
            zone_size = target_start - target_end
            penetration = target_start - reached
            return (penetration / zone_size * 100) if zone_size > 0 else 0

df_valid['penetration_pct'] = df_valid.apply(calculate_penetration, axis=1)

# Filter only signals that entered target zone
in_zone = df_valid[df_valid['penetration_pct'] > 0]

if len(in_zone) > 0:
    avg_penetration = in_zone['penetration_pct'].mean()
    median_penetration = in_zone['penetration_pct'].median()
    
    print(f"Из {len(df_valid)} сигналов, {len(in_zone)} вошли в target зону ({len(in_zone)/len(df_valid)*100:.1f}%)")
    print(f"Средняя глубина проникновения: {avg_penetration:.1f}%")
    print(f"Медианная глубина проникновения: {median_penetration:.1f}%")
    print()
    
    # Distribution
    bins = [0, 25, 50, 75, 100]
    labels = ['0-25%', '25-50%', '50-75%', '75-100%']
    in_zone['depth_category'] = pd.cut(in_zone['penetration_pct'], bins=bins, labels=labels, include_lowest=True)
    
    print("Распределение глубины проникновения:")
    for category in labels:
        count = (in_zone['depth_category'] == category).sum()
        pct = count / len(in_zone) * 100
        print(f"  {category:10s}: {count:4d} ({pct:5.1f}%)")
else:
    print("Ни один сигнал не вошёл в target зону")

print()
print(f"{'='*70}")
print(f"✅ Анализ завершён")
print(f"{'='*70}")
