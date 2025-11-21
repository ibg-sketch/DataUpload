#!/usr/bin/env python3
"""
Self-Learning Controller with Statistical Guardrails
Monitors signal effectiveness and auto-suggests weight optimizations when performance drops.
Includes statistical validation to prevent overfitting.
"""

import pandas as pd
import numpy as np
import os
import json
import time
from datetime import datetime, timedelta
import yaml
from telegram_utils import send_telegram_message

# Statistical guardrails configuration
# CRITICAL FIX: Raised from 20 to 50 to prevent premature optimization on noisy data
MIN_SAMPLES_GLOBAL = 50  # Minimum total signals before any optimization
MIN_SAMPLES_PER_COMBO = 10  # Minimum per symbol+verdict combo (raised from 5)
TARGET_WIN_RATE = 0.80  # 80% target win rate
CONFIDENCE_LEVEL = 0.95  # 95% confidence intervals
CHECK_INTERVAL_HOURS = 1  # Run optimization check every 1 hour (changed from 6h)

def load_effectiveness_log():
    """Load effectiveness log with proper error handling."""
    log_file = 'effectiveness_log.csv'
    
    if not os.path.exists(log_file):
        return None
    
    try:
        df = pd.read_csv(log_file)
        
        # Ensure required columns exist
        required_cols = ['timestamp_sent', 'symbol', 'verdict', 'confidence', 'result']
        if not all(col in df.columns for col in required_cols):
            print(f"[ERROR] Missing required columns in {log_file}")
            return None
        
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load {log_file}: {e}")
        return None

def calculate_confidence_interval(wins, total, confidence=0.95):
    """
    Calculate Wilson score confidence interval for win rate.
    More accurate than normal approximation for small samples.
    
    Returns: (lower_bound, upper_bound, win_rate)
    """
    if total == 0:
        return (0.0, 0.0, 0.0)
    
    win_rate = wins / total
    
    # Wilson score interval
    from math import sqrt
    z = 1.96 if confidence == 0.95 else 2.576  # z-score for 95% or 99%
    
    denominator = 1 + z**2 / total
    centre_adjusted = win_rate + z**2 / (2 * total)
    adjusted_std = sqrt((win_rate * (1 - win_rate) + z**2 / (4 * total)) / total)
    
    lower = (centre_adjusted - z * adjusted_std) / denominator
    upper = (centre_adjusted + z * adjusted_std) / denominator
    
    return (max(0.0, lower), min(1.0, upper), win_rate)

def load_signals_log():
    """Load signals log for correlation analysis."""
    log_file = 'signals_log.csv'
    
    if not os.path.exists(log_file):
        return None
    
    try:
        df = pd.read_csv(log_file)
        return df
    except Exception as e:
        print(f"[ERROR] Failed to load {log_file}: {e}")
        return None

def analyze_indicator_correlations(start_date='2025-11-09'):
    """
    Analyze correlation between indicators and price movement (profit).
    Analyzes all signals starting from specified date.
    
    Returns dict with correlations for each indicator.
    """
    signals_df = load_signals_log()
    effectiveness_df = load_effectiveness_log()
    
    if signals_df is None or effectiveness_df is None:
        return None
    
    try:
        # Filter to signals from start_date onwards
        signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])
        effectiveness_df['timestamp_sent'] = pd.to_datetime(effectiveness_df['timestamp_sent'])
        
        cutoff = pd.to_datetime(start_date)
        signals_df = signals_df[signals_df['timestamp'] >= cutoff]
        effectiveness_df = effectiveness_df[effectiveness_df['timestamp_sent'] >= cutoff]
        
        # Merge signals with effectiveness results
        # Match by timestamp, symbol, verdict
        merged = pd.merge(
            signals_df,
            effectiveness_df[['timestamp_sent', 'symbol', 'verdict', 'result', 'profit_pct']],
            left_on=['timestamp', 'symbol', 'verdict'],
            right_on=['timestamp_sent', 'symbol', 'verdict'],
            how='inner'
        )
        
        if len(merged) == 0:
            return None
        
        # Calculate indicator values
        merged['vwap_deviation_pct'] = ((merged['entry_price'] - merged['vwap']) / merged['vwap'] * 100)
        merged['oi_change_pct'] = merged['oi_change'] / merged['oi'] * 100
        merged['is_win'] = (merged['result'] == 'WIN').astype(int)
        
        # Calculate correlations with profit_pct
        correlations = {}
        
        # Exclude 'confidence' - it's an artificial indicator, not a real market signal
        numeric_indicators = {
            'score': 'Total Score',
            'vwap_deviation_pct': 'VWAP Deviation %',
            'oi': 'Open Interest',
            'oi_change_pct': 'OI Change %',
            'volume_spike': 'Volume Spike',
            'liq_long': 'Long Liquidations',
            'liq_short': 'Short Liquidations'
        }
        
        for col, label in numeric_indicators.items():
            if col in merged.columns:
                valid_data = merged[[col, 'profit_pct', 'is_win']].dropna()
                if len(valid_data) > 10:
                    corr_profit = valid_data[col].corr(valid_data['profit_pct'])
                    corr_win = valid_data[col].corr(valid_data['is_win'])
                    correlations[label] = {
                        'profit_corr': corr_profit,
                        'win_corr': corr_win,
                        'samples': len(valid_data)
                    }
        
        # Analyze component flags (CVD_pos, OI_up, etc)
        component_correlations = {}
        if 'components' in merged.columns:
            all_components = set()
            for components_str in merged['components'].dropna():
                all_components.update(str(components_str).split('|'))
            
            for component in all_components:
                merged[f'has_{component}'] = merged['components'].str.contains(component, na=False).astype(int)
                valid_data = merged[[f'has_{component}', 'profit_pct', 'is_win']].dropna()
                
                if len(valid_data) > 10:
                    corr_profit = valid_data[f'has_{component}'].corr(valid_data['profit_pct'])
                    corr_win = valid_data[f'has_{component}'].corr(valid_data['is_win'])
                    component_correlations[component] = {
                        'profit_corr': corr_profit,
                        'win_corr': corr_win,
                        'samples': len(valid_data[valid_data[f'has_{component}'] == 1])
                    }
        
        return {
            'numeric_indicators': correlations,
            'components': component_correlations,
            'total_signals': len(merged),
            'win_rate': merged['is_win'].mean()
        }
        
    except Exception as e:
        print(f"[ERROR] Correlation analysis failed: {e}")
        return None

def analyze_effectiveness(start_date='2025-11-09'):
    """
    Analyze signal effectiveness with statistical validation.
    Analyzes all signals starting from 09.11.2025.
    
    Returns dict with:
    - overall_stats: Global win rate and sample size
    - per_symbol: Win rates per symbol
    - per_verdict: Win rates per verdict (BUY/SELL)
    - recommendations: List of actionable improvements
    - ready_for_optimization: Boolean indicating if we should optimize
    - indicator_correlations: Correlation analysis of indicators with price movement
    """
    df = load_effectiveness_log()
    
    if df is None or len(df) == 0:
        return {
            'overall_stats': {'total': 0, 'wins': 0, 'win_rate': 0.0, 'ready': False},
            'per_symbol': {},
            'per_verdict': {},
            'recommendations': ['Insufficient data - need at least 50 signals'],
            'ready_for_optimization': False
        }
    
    # Filter to signals from start_date onwards
    try:
        df['timestamp_sent'] = pd.to_datetime(df['timestamp_sent'])
        cutoff = pd.to_datetime(start_date)
        df = df[df['timestamp_sent'] >= cutoff]
    except:
        pass  # If timestamp parsing fails, use all data
    
    # Overall statistics
    total = len(df)
    wins = len(df[df['result'] == 'WIN'])
    lower, upper, win_rate = calculate_confidence_interval(wins, total, CONFIDENCE_LEVEL)
    
    overall_stats = {
        'total': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': win_rate,
        'ci_lower': lower,
        'ci_upper': upper,
        'ready': total >= MIN_SAMPLES_GLOBAL
    }
    
    # Per-symbol analysis
    per_symbol = {}
    for symbol in df['symbol'].unique():
        sym_df = df[df['symbol'] == symbol]
        sym_total = len(sym_df)
        sym_wins = len(sym_df[sym_df['result'] == 'WIN'])
        sym_lower, sym_upper, sym_wr = calculate_confidence_interval(sym_wins, sym_total)
        
        per_symbol[symbol] = {
            'total': sym_total,
            'wins': sym_wins,
            'win_rate': sym_wr,
            'ci_lower': sym_lower,
            'ci_upper': sym_upper,
            'sufficient_data': sym_total >= MIN_SAMPLES_PER_COMBO
        }
    
    # Per-verdict analysis
    per_verdict = {}
    for verdict in ['BUY', 'SELL']:
        verd_df = df[df['verdict'] == verdict]
        verd_total = len(verd_df)
        verd_wins = len(verd_df[verd_df['result'] == 'WIN'])
        verd_lower, verd_upper, verd_wr = calculate_confidence_interval(verd_wins, verd_total)
        
        per_verdict[verdict] = {
            'total': verd_total,
            'wins': verd_wins,
            'win_rate': verd_wr,
            'ci_lower': verd_lower,
            'ci_upper': verd_upper
        }
    
    # Generate recommendations
    recommendations = []
    ready_for_optimization = False
    
    if total < MIN_SAMPLES_GLOBAL:
        recommendations.append(f"Need {MIN_SAMPLES_GLOBAL - total} more signals before optimization (current: {total})")
    else:
        # Check if win rate is below target
        if upper < TARGET_WIN_RATE:
            recommendations.append(f"⚠️ Win rate {win_rate:.1%} below target {TARGET_WIN_RATE:.0%} (95% CI: {lower:.1%}-{upper:.1%})")
            recommendations.append("→ Weight optimization recommended")
            ready_for_optimization = True
        else:
            recommendations.append(f"✅ Win rate {win_rate:.1%} meets target (95% CI: {lower:.1%}-{upper:.1%})")
        
        # Identify underperforming symbols
        for symbol, stats in per_symbol.items():
            if stats['sufficient_data'] and stats['ci_upper'] < TARGET_WIN_RATE:
                recommendations.append(f"⚠️ {symbol}: {stats['win_rate']:.1%} win rate (n={stats['total']})")
        
        # Check verdict imbalance
        buy_wr = per_verdict.get('BUY', {}).get('win_rate', 0)
        sell_wr = per_verdict.get('SELL', {}).get('win_rate', 0)
        if abs(buy_wr - sell_wr) > 0.15 and min(per_verdict.get('BUY', {}).get('total', 0), per_verdict.get('SELL', {}).get('total', 0)) >= MIN_SAMPLES_PER_COMBO:
            recommendations.append(f"⚠️ Verdict imbalance: BUY {buy_wr:.1%} vs SELL {sell_wr:.1%}")
    
    # Run correlation analysis
    correlations = analyze_indicator_correlations(start_date)
    
    return {
        'overall_stats': overall_stats,
        'per_symbol': per_symbol,
        'per_verdict': per_verdict,
        'recommendations': recommendations,
        'ready_for_optimization': ready_for_optimization,
        'correlations': correlations
    }

def send_optimization_suggestion(analysis):
    """
    Send optimization suggestion to Telegram instead of auto-applying changes.
    """
    try:
        # Build detailed message
        stats = analysis['overall_stats']
        message_lines = [
            "🧠 <b>SELF-LEARNING CONTROLLER - Optimization Suggestion</b>",
            "",
            f"📊 <b>Current Performance:</b>",
            f"   Win Rate: {stats['win_rate']:.1%} (Target: {TARGET_WIN_RATE:.0%})",
            f"   95% CI: [{stats['ci_lower']:.1%}, {stats['ci_upper']:.1%}]",
            f"   Signals: {stats['wins']} wins / {stats['total']} total",
            ""
        ]
        
        # Top/worst performing symbols
        if analysis['per_symbol']:
            best_symbols = []
            worst_symbols = []
            
            for symbol, sym_stats in analysis['per_symbol'].items():
                if sym_stats['sufficient_data']:
                    if sym_stats['ci_upper'] >= TARGET_WIN_RATE:
                        best_symbols.append((symbol, sym_stats['win_rate'], sym_stats['total']))
                    elif sym_stats['ci_upper'] < TARGET_WIN_RATE:
                        worst_symbols.append((symbol, sym_stats['win_rate'], sym_stats['total']))
            
            if best_symbols:
                message_lines.append("✅ <b>Best Performing:</b>")
                for symbol, wr, total in sorted(best_symbols, key=lambda x: x[1], reverse=True)[:3]:
                    message_lines.append(f"   {symbol}: {wr:.1%} ({total} signals)")
                message_lines.append("")
            
            if worst_symbols:
                message_lines.append("⚠️ <b>Needs Improvement:</b>")
                for symbol, wr, total in sorted(worst_symbols, key=lambda x: x[1])[:3]:
                    message_lines.append(f"   {symbol}: {wr:.1%} ({total} signals)")
                message_lines.append("")
        
        # Indicator Correlations (NEW!)
        if analysis.get('correlations'):
            corr_data = analysis['correlations']
            message_lines.append(f"📊 <b>Indicator Correlations (from 09.11.2025, {corr_data['total_signals']} signals):</b>")
            message_lines.append("")
            
            # Top positive correlations with profit
            if corr_data.get('numeric_indicators'):
                sorted_corrs = sorted(
                    corr_data['numeric_indicators'].items(),
                    key=lambda x: abs(x[1]['profit_corr']),
                    reverse=True
                )
                
                message_lines.append("🔝 <b>Strongest Profit Predictors:</b>")
                for indicator, data in sorted_corrs[:5]:
                    corr_val = data['profit_corr']
                    win_corr = data['win_corr']
                    emoji = "📈" if corr_val > 0 else "📉"
                    message_lines.append(f"   {emoji} {indicator}: {corr_val:+.3f} profit | {win_corr:+.3f} win")
                message_lines.append("")
            
            # Top component flags
            if corr_data.get('components'):
                sorted_comps = sorted(
                    corr_data['components'].items(),
                    key=lambda x: x[1]['win_corr'],
                    reverse=True
                )
                
                message_lines.append("⭐️ <b>Best Component Flags:</b>")
                for component, data in sorted_comps[:5]:
                    win_corr = data['win_corr']
                    samples = data['samples']
                    emoji = "✅" if win_corr > 0 else "❌"
                    message_lines.append(f"   {emoji} {component}: {win_corr:+.3f} ({samples} occurrences)")
                message_lines.append("")
                
                # Worst component flags
                message_lines.append("⚠️ <b>Worst Component Flags:</b>")
                for component, data in sorted_comps[-5:]:
                    win_corr = data['win_corr']
                    samples = data['samples']
                    emoji = "❌" if win_corr < -0.05 else "⚪️"
                    message_lines.append(f"   {emoji} {component}: {win_corr:+.3f} ({samples} occurrences)")
                message_lines.append("")
        
        # Recommendations
        message_lines.append("💡 <b>Recommendations:</b>")
        for rec in analysis['recommendations'][:5]:  # Limit to 5
            message_lines.append(f"   • {rec}")
        
        message_lines.append("")
        message_lines.append("🔧 <b>Next Steps:</b>")
        if analysis['ready_for_optimization']:
            message_lines.append("   ⚙️ Review indicator correlations above")
            message_lines.append("   📝 Consider increasing weights for strong predictors")
            message_lines.append("   🎯 Decrease weights for negative correlations")
        else:
            message_lines.append("   ⏳ Continue collecting data")
            message_lines.append(f"   📊 Need {MIN_SAMPLES_GLOBAL - stats['total']} more signals")
        
        message = "\n".join(message_lines)
        
        # Send to Telegram
        success = send_telegram_message(message)
        
        if success:
            print(f"[CONTROLLER] ✅ Optimization suggestion sent to Telegram")
            return True
        else:
            print(f"[CONTROLLER] ❌ Failed to send Telegram message")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to send optimization suggestion: {e}")
        return False

def save_learning_state(state):
    """Save controller state to track optimization history."""
    state_file = 'learning_state.json'
    
    try:
        # Load existing state if available
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                history = json.load(f)
        else:
            history = {'optimizations': [], 'last_check': None}
        
        # Add new entry
        history['optimizations'].append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'win_rate_before': state.get('win_rate_before'),
            'win_rate_after': state.get('win_rate_after'),
            'samples': state.get('samples'),
            'action': state.get('action')
        })
        history['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save
        with open(state_file, 'w') as f:
            json.dump(history, indent=2, fp=f)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save learning state: {e}")
        return False

def generate_report(analysis):
    """Generate human-readable effectiveness report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SELF-LEARNING CONTROLLER - Effectiveness Report")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Overall stats
    stats = analysis['overall_stats']
    lines.append(f"📊 OVERALL PERFORMANCE (Last 30 days)")
    lines.append(f"   Total Signals: {stats['total']}")
    lines.append(f"   Wins: {stats['wins']} | Losses: {stats['losses']}")
    lines.append(f"   Win Rate: {stats['win_rate']:.1%}")
    if stats['total'] >= MIN_SAMPLES_GLOBAL:
        lines.append(f"   95% CI: [{stats['ci_lower']:.1%}, {stats['ci_upper']:.1%}]")
    lines.append("")
    
    # Per-symbol breakdown
    if analysis['per_symbol']:
        lines.append(f"📈 PER-SYMBOL BREAKDOWN")
        for symbol, sym_stats in sorted(analysis['per_symbol'].items()):
            status = "✅" if sym_stats['ci_upper'] >= TARGET_WIN_RATE else "⚠️"
            lines.append(f"   {status} {symbol}: {sym_stats['win_rate']:.1%} ({sym_stats['wins']}/{sym_stats['total']})")
        lines.append("")
    
    # Per-verdict breakdown
    if analysis['per_verdict']:
        lines.append(f"🎯 BUY vs SELL PERFORMANCE")
        for verdict, verd_stats in analysis['per_verdict'].items():
            if verd_stats['total'] > 0:
                lines.append(f"   {verdict}: {verd_stats['win_rate']:.1%} ({verd_stats['wins']}/{verd_stats['total']})")
        lines.append("")
    
    # Recommendations
    lines.append(f"💡 RECOMMENDATIONS")
    for rec in analysis['recommendations']:
        lines.append(f"   {rec}")
    lines.append("")
    
    # Optimization status
    if analysis['ready_for_optimization']:
        lines.append(f"🔧 ACTION REQUIRED: Run weight optimization")
        lines.append(f"   Command: python weight_optimizer.py")
    else:
        lines.append(f"⏳ Collecting more data before optimization")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)

def main():
    """Main controller loop."""
    print("[CONTROLLER] Self-Learning Controller started")
    print(f"[CONTROLLER] Target win rate: {TARGET_WIN_RATE:.0%}")
    print(f"[CONTROLLER] Minimum samples: {MIN_SAMPLES_GLOBAL}")
    print(f"[CONTROLLER] Check interval: {CHECK_INTERVAL_HOURS}h")
    print(f"[CONTROLLER] Heartbeat: 5min (keeps workflow alive)")
    print("")
    
    last_check_time = time.time()
    heartbeat_interval = 300  # 5 minutes to keep workflow alive
    check_interval_seconds = CHECK_INTERVAL_HOURS * 3600
    
    while True:
        try:
            elapsed = time.time() - last_check_time
            remaining = check_interval_seconds - elapsed
            
            if elapsed >= check_interval_seconds:
                # Time to run analysis
                print(f"\n[CONTROLLER] Running effectiveness analysis...")
                
                # Analyze current effectiveness
                analysis = analyze_effectiveness()
                
                # Generate and display report
                report = generate_report(analysis)
                print(report)
                
                # Send Telegram suggestion instead of auto-applying changes
                if analysis['ready_for_optimization']:
                    print("\n[CONTROLLER] Win rate below target - sending optimization suggestion to Telegram")
                    
                    # Send suggestion to Telegram
                    telegram_sent = send_optimization_suggestion(analysis)
                    
                    # Save state for tracking
                    save_learning_state({
                        'win_rate_before': analysis['overall_stats']['win_rate'],
                        'samples': analysis['overall_stats']['total'],
                        'action': 'suggestion_sent' if telegram_sent else 'suggestion_failed'
                    })
                else:
                    print(f"\n[CONTROLLER] Performance is good")
                    print(f"[CONTROLLER] Current win rate: {analysis['overall_stats']['win_rate']:.1%}")
                    print(f"[CONTROLLER] No optimization suggestions needed")
                
                last_check_time = time.time()
            else:
                # Heartbeat to keep workflow alive
                hours_left = int(remaining / 3600)
                mins_left = int((remaining % 3600) / 60)
                print(f"[HEARTBEAT] {datetime.now().strftime('%H:%M:%S')} - Next analysis in {hours_left}h {mins_left}m")
                time.sleep(heartbeat_interval)
            
        except KeyboardInterrupt:
            print("\n[CONTROLLER] Shutting down...")
            break
        except Exception as e:
            print(f"[ERROR] Controller error: {e}")
            time.sleep(60)  # Wait 1 minute on error before retrying

if __name__ == '__main__':
    main()
