#!/usr/bin/env python3
"""
НАСТОЯЩАЯ симуляция на основе РЕАЛЬНЫХ исторических цен
Проверяет каждый сигнал: дошла ли цена до TP, SL или закрылась по TTL
"""

import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import os

COINALYZE_API_KEY = os.getenv('COINALYZE_API_KEY')

def get_historical_prices(symbol, start_time, end_time):
    """
    Получает минутные свечи от Coinalyze API
    """
    # Преобразуем символ BTCUSDT -> BTC
    coin = symbol.replace('USDT', '')
    
    # Coinalyze требует timestamps в секундах
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())
    
    url = f"https://api.coinalyze.net/v1/ohlcv-history"
    params = {
        'symbols': f'BINANCE:{coin}.P',
        'interval': '1',  # 1 минута
        'from': start_ts,
        'to': end_ts,
        'api_key': COINALYZE_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # Парсим данные
                df = pd.DataFrame(data[0]['history'])
                df['timestamp'] = pd.to_datetime(df['t'], unit='s')
                return df[['timestamp', 'o', 'h', 'l', 'c']].rename(columns={
                    'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close'
                })
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
    
    return None

def simulate_trade_with_real_prices(signal, config):
    """
    Симулирует трейд используя РЕАЛЬНЫЕ исторические цены
    
    Returns: (outcome, pnl_pct, exit_time, exit_price)
    """
    symbol = signal['symbol']
    entry_price = float(signal['entry_price'])
    signal_type = signal['verdict']
    ttl_minutes = int(signal['ttl_minutes'])
    
    # Парсим timestamp
    entry_time = pd.to_datetime(signal['timestamp'])
    exit_time_max = entry_time + timedelta(minutes=ttl_minutes)
    
    # Рассчитываем TP и SL уровни
    target_min = float(signal['target_min'])
    target_max = float(signal['target_max'])
    
    # TP target (используем hybrid стратегию)
    if signal_type == 'BUY':
        tp_price = target_min  # Консервативный для BUY
    else:
        tp_price = target_max  # Агрессивный для SELL
    
    # SL уровень
    sl_pct = config['stop_loss_pct'] / 100
    if signal_type == 'BUY':
        sl_price = entry_price * (1 - sl_pct)
    else:
        sl_price = entry_price * (1 + sl_pct)
    
    # Получаем исторические цены
    candles = get_historical_prices(symbol, entry_time, exit_time_max + timedelta(minutes=5))
    
    if candles is None or len(candles) == 0:
        # Нет данных - считаем TTL с нулевым результатом
        return 'TTL', -0.1 * config['leverage'], ttl_minutes, entry_price
    
    # Проходим по каждой свече и проверяем TP/SL
    for idx, candle in candles.iterrows():
        candle_time = candle['timestamp']
        
        # Если вышли за TTL
        if candle_time > exit_time_max:
            # Закрываем по последней цене
            final_price = float(candles[candles['timestamp'] <= exit_time_max].iloc[-1]['close'])
            
            if signal_type == 'BUY':
                price_change_pct = ((final_price - entry_price) / entry_price) * 100
            else:
                price_change_pct = ((entry_price - final_price) / entry_price) * 100
            
            gross_pnl = price_change_pct * config['leverage']
            fees = (0.0005 + 0.0005) * config['leverage']  # Entry + TTL exit
            net_pnl = gross_pnl - fees
            
            duration = int((exit_time_max - entry_time).total_seconds() / 60)
            return 'TTL', net_pnl, duration, final_price
        
        high = float(candle['high'])
        low = float(candle['low'])
        
        # Проверяем SL и TP в правильном порядке
        if signal_type == 'BUY':
            # Для BUY: сначала проверяем SL (снизу), потом TP (сверху)
            if low <= sl_price:
                # SL hit
                price_change_pct = ((sl_price - entry_price) / entry_price) * 100
                gross_loss = price_change_pct * config['leverage']
                fees = (0.0005 + 0.0005) * config['leverage']
                net_pnl = gross_loss - fees
                
                duration = int((candle_time - entry_time).total_seconds() / 60)
                return 'SL', net_pnl, duration, sl_price
            
            if high >= tp_price:
                # TP hit
                price_change_pct = ((tp_price - entry_price) / entry_price) * 100
                gross_profit = price_change_pct * config['leverage']
                fees = (0.0005 + 0.0002) * config['leverage']  # Entry + TP maker
                net_pnl = gross_profit - fees
                
                duration = int((candle_time - entry_time).total_seconds() / 60)
                return 'TP', net_pnl, duration, tp_price
        
        else:  # SELL
            # Для SELL: сначала проверяем SL (сверху), потом TP (снизу)
            if high >= sl_price:
                # SL hit
                price_change_pct = ((entry_price - sl_price) / entry_price) * 100
                gross_loss = price_change_pct * config['leverage']
                fees = (0.0005 + 0.0005) * config['leverage']
                net_pnl = gross_loss - fees
                
                duration = int((candle_time - entry_time).total_seconds() / 60)
                return 'SL', net_pnl, duration, sl_price
            
            if low <= tp_price:
                # TP hit
                price_change_pct = ((entry_price - tp_price) / entry_price) * 100
                gross_profit = price_change_pct * config['leverage']
                fees = (0.0005 + 0.0002) * config['leverage']
                net_pnl = gross_profit - fees
                
                duration = int((candle_time - entry_time).total_seconds() / 60)
                return 'TP', net_pnl, duration, tp_price
    
    # Если дошли сюда - закрываем по TTL
    final_price = float(candles.iloc[-1]['close'])
    
    if signal_type == 'BUY':
        price_change_pct = ((final_price - entry_price) / entry_price) * 100
    else:
        price_change_pct = ((entry_price - final_price) / entry_price) * 100
    
    gross_pnl = price_change_pct * config['leverage']
    fees = (0.0005 + 0.0005) * config['leverage']
    net_pnl = gross_pnl - fees
    
    duration = int((exit_time_max - entry_time).total_seconds() / 60)
    return 'TTL', net_pnl, duration, final_price

print("=" * 90)
print("🎯 СИМУЛЯЦИЯ НА РЕАЛЬНЫХ ИСТОРИЧЕСКИХ ЦЕНАХ")
print("=" * 90)

# Загружаем сигналы
signals_df = pd.read_csv('/tmp/signals_nov17_18_with_header.csv')
signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])
signals_df = signals_df.sort_values('timestamp').reset_index(drop=True)

print(f"\n📊 Загружено сигналов: {len(signals_df)}")
print(f"   Период: {signals_df['timestamp'].min()} → {signals_df['timestamp'].max()}")

# Текущая конфигурация
config = {
    'leverage': 20,
    'position_size_pct': 100,
    'stop_loss_pct': 10,
    'max_positions': 1
}

print(f"\n⚙️  Конфигурация:")
print(f"   Плечо: {config['leverage']}x")
print(f"   Размер позиции: {config['position_size_pct']}%")
print(f"   Stop-Loss: {config['stop_loss_pct']}%")
print(f"   Max позиций: {config['max_positions']}")

print(f"\n🔄 Симулирую торговлю с РЕАЛЬНЫМИ историческими ценами...")
print(f"   (это займёт несколько минут из-за API запросов)")

balance = 1000.0
trades = []
skipped = 0
current_position_end = None

for idx, signal in signals_df.iterrows():
    signal_time = signal['timestamp']
    
    # Проверяем перекрытие позиций
    if current_position_end is not None:
        if signal_time < current_position_end:
            skipped += 1
            continue
        else:
            current_position_end = None
    
    if balance <= 0:
        break
    
    position_size = balance * (config['position_size_pct'] / 100)
    
    if position_size < 10:
        break
    
    # Симулируем трейд на реальных ценах
    print(f"\n  [{idx+1}/{len(signals_df)}] {signal_time} | {signal['symbol']} {signal['verdict']}")
    
    outcome, pnl_pct, duration, exit_price = simulate_trade_with_real_prices(signal, config)
    
    pnl_dollars = position_size * (pnl_pct / 100)
    balance += pnl_dollars
    
    outcome_emoji = "✅" if outcome == 'TP' else "❌" if outcome == 'SL' else "⏱️"
    print(f"      → {outcome_emoji} {outcome} | PnL: {pnl_pct:+.2f}% (${pnl_dollars:+.2f}) | Duration: {duration}m")
    print(f"      → Entry: {signal['entry_price']} | Exit: {exit_price:.4f} | Balance: ${balance:.2f}")
    
    trades.append({
        'timestamp': signal_time,
        'symbol': signal['symbol'],
        'side': signal['verdict'],
        'entry_price': float(signal['entry_price']),
        'exit_price': exit_price,
        'outcome': outcome,
        'pnl_pct': pnl_pct,
        'pnl_dollars': pnl_dollars,
        'duration': duration,
        'balance_after': balance
    })
    
    # Обновляем время окончания позиции
    current_position_end = signal_time + timedelta(minutes=duration)
    
    # Rate limiting для API
    time.sleep(0.2)
    
    # Останавливаемся на первых 30 трейдах для демонстрации
    if len(trades) >= 30:
        print(f"\n⚠️  Остановлено на 30 трейдах для демонстрации (из {len(signals_df)})")
        break

# Анализ результатов
print("\n" + "=" * 90)
print("📊 РЕЗУЛЬТАТЫ СИМУЛЯЦИИ НА РЕАЛЬНЫХ ЦЕНАХ")
print("=" * 90)

tp_trades = [t for t in trades if t['outcome'] == 'TP']
sl_trades = [t for t in trades if t['outcome'] == 'SL']
ttl_trades = [t for t in trades if t['outcome'] == 'TTL']

win_trades = [t for t in trades if t['pnl_dollars'] > 0]
lose_trades = [t for t in trades if t['pnl_dollars'] <= 0]

print(f"\n💰 Финальный баланс: ${balance:.2f}")
print(f"   Начальный: $1,000.00")
print(f"   PnL: ${balance - 1000:.2f} ({(balance/1000 - 1)*100:+.1f}%)")

print(f"\n📊 Трейдов: {len(trades)}")
print(f"   Пропущено (позиция открыта): {skipped}")

print(f"\n🎯 Исходы:")
print(f"   ✅ TP: {len(tp_trades)} ({len(tp_trades)/len(trades)*100:.1f}%)")
print(f"   ❌ SL: {len(sl_trades)} ({len(sl_trades)/len(trades)*100:.1f}%)")
print(f"   ⏱️ TTL: {len(ttl_trades)} ({len(ttl_trades)/len(trades)*100:.1f}%)")

print(f"\n💵 Винрейт:")
print(f"   Wins: {len(win_trades)} ({len(win_trades)/len(trades)*100:.1f}%)")
print(f"   Losses: {len(lose_trades)} ({len(lose_trades)/len(trades)*100:.1f}%)")

print(f"\n📈 Средние показатели:")
print(f"   Avg PnL per trade: ${sum([t['pnl_dollars'] for t in trades])/len(trades):.2f}")
print(f"   Avg TP profit: ${sum([t['pnl_dollars'] for t in tp_trades])/len(tp_trades):.2f}" if tp_trades else "   Avg TP profit: N/A")
print(f"   Avg SL loss: ${sum([t['pnl_dollars'] for t in sl_trades])/len(sl_trades):.2f}" if sl_trades else "   Avg SL loss: N/A")
print(f"   Avg duration: {sum([t['duration'] for t in trades])/len(trades):.1f} minutes")

# Сохраняем детали
trades_df = pd.DataFrame(trades)
trades_df.to_csv('/tmp/real_price_backtest_trades.csv', index=False)

print(f"\n✅ Детальные результаты сохранены в /tmp/real_price_backtest_trades.csv")
print("=" * 90)
