#!/usr/bin/env python3
"""Analyze signal effectiveness for today (2025-11-03)"""

import csv
from datetime import datetime
from collections import defaultdict

def analyze_signals():
    # Read all signals generated today
    signals_generated = []
    with open('signals_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['timestamp'].startswith('2025-11-03'):
                signals_generated.append(row)
    
    # Read all effectiveness results for today
    effectiveness_results = []
    with open('effectiveness_log.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['timestamp_sent'].startswith('2025-11-03'):
                effectiveness_results.append(row)
    
    print("=" * 80)
    print(f"📊 АНАЛИЗ ЭФФЕКТИВНОСТИ ЗА СЕГОДНЯ (2025-11-03)")
    print("=" * 80)
    print()
    
    # Analysis of generated signals
    print(f"🔹 СГЕНЕРИРОВАНО СИГНАЛОВ: {len(signals_generated)}")
    print()
    
    # Count by direction
    buy_signals = [s for s in signals_generated if s['verdict'] == 'BUY']
    sell_signals = [s for s in signals_generated if s['verdict'] == 'SELL']
    
    print(f"   📈 BUY:  {len(buy_signals)} ({len(buy_signals)/len(signals_generated)*100:.1f}%)")
    print(f"   📉 SELL: {len(sell_signals)} ({len(sell_signals)/len(signals_generated)*100:.1f}%)")
    print()
    
    # Analysis of effectiveness results
    print(f"🔹 ЗАКРЫТО СИГНАЛОВ: {len(effectiveness_results)}")
    print()
    
    # Count outcomes
    win = [r for r in effectiveness_results if r['result'] == 'WIN']
    loss = [r for r in effectiveness_results if r['result'] == 'LOSS']
    cancelled = [r for r in effectiveness_results if r['result'] == 'CANCELLED']
    
    print(f"   ✅ WIN:       {len(win)} ({len(win)/len(effectiveness_results)*100:.1f}%)")
    print(f"   ❌ LOSS:      {len(loss)} ({len(loss)/len(effectiveness_results)*100:.1f}%)")
    print(f"   ⚪ CANCELLED: {len(cancelled)} ({len(cancelled)/len(effectiveness_results)*100:.1f}%)")
    print()
    
    # Win rate (excluding cancelled)
    traded = len(win) + len(loss)
    if traded > 0:
        win_rate = len(win) / traded * 100
        print(f"🎯 WIN RATE (без CANCELLED): {win_rate:.1f}% ({len(win)}W / {traded} trades)")
    print()
    
    # PnL analysis
    total_pnl = sum(float(r['profit_pct']) for r in effectiveness_results if r['profit_pct'])
    avg_pnl = total_pnl / len(effectiveness_results) if effectiveness_results else 0
    
    win_pnl = sum(float(r['profit_pct']) for r in win)
    loss_pnl = sum(float(r['profit_pct']) for r in loss)
    
    avg_win_pnl = win_pnl / len(win) if win else 0
    avg_loss_pnl = loss_pnl / len(loss) if loss else 0
    
    print(f"💰 PnL СТАТИСТИКА:")
    print(f"   Total PnL:     {total_pnl:+.2f}%")
    print(f"   Average PnL:   {avg_pnl:+.2f}%")
    print(f"   Avg WIN PnL:   {avg_win_pnl:+.2f}%")
    print(f"   Avg LOSS PnL:  {avg_loss_pnl:+.2f}%")
    print()
    
    # BUY vs SELL performance
    buy_results = [r for r in effectiveness_results if r['verdict'] == 'BUY']
    sell_results = [r for r in effectiveness_results if r['verdict'] == 'SELL']
    
    print(f"📊 ЭФФЕКТИВНОСТЬ ПО ТИПУ:")
    print()
    
    # BUY stats
    buy_win = [r for r in buy_results if r['result'] == 'WIN']
    buy_loss = [r for r in buy_results if r['result'] == 'LOSS']
    buy_traded = len(buy_win) + len(buy_loss)
    buy_wr = len(buy_win) / buy_traded * 100 if buy_traded > 0 else 0
    buy_pnl = sum(float(r['profit_pct']) for r in buy_results if r['profit_pct'])
    
    print(f"   📈 BUY:  {len(buy_results)} сигналов")
    print(f"      Win Rate: {buy_wr:.1f}% ({len(buy_win)}W-{len(buy_loss)}L)")
    print(f"      Total PnL: {buy_pnl:+.2f}%")
    print()
    
    # SELL stats
    sell_win = [r for r in sell_results if r['result'] == 'WIN']
    sell_loss = [r for r in sell_results if r['result'] == 'LOSS']
    sell_traded = len(sell_win) + len(sell_loss)
    sell_wr = len(sell_win) / sell_traded * 100 if sell_traded > 0 else 0
    sell_pnl = sum(float(r['profit_pct']) for r in sell_results if r['profit_pct'])
    
    print(f"   📉 SELL: {len(sell_results)} сигналов")
    print(f"      Win Rate: {sell_wr:.1f}% ({len(sell_win)}W-{len(sell_loss)}L)")
    print(f"      Total PnL: {sell_pnl:+.2f}%")
    print()
    
    # Top performers
    print(f"🏆 ТОП-5 ЛУЧШИХ СИГНАЛОВ:")
    top_wins = sorted(effectiveness_results, key=lambda x: float(x['profit_pct']), reverse=True)[:5]
    for i, sig in enumerate(top_wins, 1):
        print(f"   {i}. {sig['symbol']} {sig['verdict']}: {float(sig['profit_pct']):+.2f}% (conf: {float(sig['confidence'])*100:.0f}%)")
    print()
    
    # Worst performers
    print(f"💔 ТОП-5 ХУДШИХ СИГНАЛОВ:")
    worst_losses = sorted(effectiveness_results, key=lambda x: float(x['profit_pct']))[:5]
    for i, sig in enumerate(worst_losses, 1):
        print(f"   {i}. {sig['symbol']} {sig['verdict']}: {float(sig['profit_pct']):+.2f}% (conf: {float(sig['confidence'])*100:.0f}%)")
    print()
    
    # Symbol performance
    symbol_stats = defaultdict(lambda: {'win': 0, 'loss': 0, 'pnl': 0.0})
    for r in effectiveness_results:
        if r['result'] in ['WIN', 'LOSS']:
            symbol = r['symbol']
            symbol_stats[symbol]['pnl'] += float(r['profit_pct'])
            if r['result'] == 'WIN':
                symbol_stats[symbol]['win'] += 1
            else:
                symbol_stats[symbol]['loss'] += 1
    
    print(f"📈 СТАТИСТИКА ПО СИМВОЛАМ:")
    for symbol in sorted(symbol_stats.keys()):
        stats = symbol_stats[symbol]
        total = stats['win'] + stats['loss']
        wr = stats['win'] / total * 100 if total > 0 else 0
        print(f"   {symbol:12} {stats['win']:2}W-{stats['loss']:2}L ({wr:5.1f}%) PnL: {stats['pnl']:+6.2f}%")
    
    print()
    print("=" * 80)

if __name__ == '__main__':
    analyze_signals()
