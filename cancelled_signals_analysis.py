import pandas as pd

print("=" * 80)
print("CANCELLED SIGNALS ANALYSIS: BNB & SOL at 17:55")
print("=" * 80)

# WINNING signals from earlier analysis
winners = [
    {
        'symbol': 'LINKUSDT',
        'time': '17:35',
        'confidence': 0.74,
        'price': 17.459,
        'vwap': 17.305505,
        'price_vs_vwap_pct': 0.89,
        'cvd': -198101.25,
        'oi_change_pct': -0.02,
        'liq_ratio': 4.0,
        'rsi': 55.35,
        'ttl_minutes': 27,
        'market_strength': 1.0,
        'outcome': 'WIN',
    },
    {
        'symbol': 'LINKUSDT',
        'time': '17:40',
        'confidence': 0.74,
        'price': 17.422,
        'vwap': 17.305517,
        'price_vs_vwap_pct': 0.67,
        'cvd': -240548.67,
        'oi_change_pct': 0.0,
        'liq_ratio': 4.0,
        'rsi': 53.20,
        'ttl_minutes': 25,
        'market_strength': 1.0,
        'outcome': 'WIN',
    },
    {
        'symbol': 'SOLUSDT',
        'time': '17:50',
        'confidence': 0.66,
        'price': 190.27,
        'vwap': 190.11,
        'price_vs_vwap_pct': 0.08,
        'cvd': -6593614.50,
        'oi_change_pct': 0.0,
        'liq_ratio': 1.82,
        'rsi': 43.80,
        'ttl_minutes': 33,
        'market_strength': 1.4,
        'outcome': 'WIN',
    }
]

# LOSING signals
losers = [
    {
        'symbol': 'ETHUSDT',
        'time': '15:10',
        'confidence': 0.65,
        'price': 3979.85,
        'vwap': 3918.66,
        'price_vs_vwap_pct': 1.56,
        'cvd': -5254513.48,
        'oi_change_pct': -0.19,
        'liq_ratio': 5.69,
        'rsi': 72.50,
        'ttl_minutes': 20,
        'market_strength': 1.38,
        'outcome': 'LOSS',
    },
    {
        'symbol': 'ETHUSDT',
        'time': '16:10',
        'confidence': 0.65,
        'price': 3969.0,
        'vwap': 3936.29,
        'price_vs_vwap_pct': 0.83,
        'cvd': -15237758.39,
        'oi_change_pct': -0.30,
        'liq_ratio': 0.08,
        'rsi': 69.97,
        'ttl_minutes': 21,
        'market_strength': 1.61,
        'outcome': 'LOSS',
    },
    {
        'symbol': 'ETHUSDT',
        'time': '16:25',
        'confidence': 0.65,
        'price': 3969.64,
        'vwap': 3938.90,
        'price_vs_vwap_pct': 0.78,
        'cvd': -22239120.20,
        'oi_change_pct': -0.02,
        'liq_ratio': 0.04,
        'rsi': 68.35,
        'ttl_minutes': 16,
        'market_strength': 1.4,
        'outcome': 'LOSS',
    }
]

# CANCELLED signals at 17:55
cancelled = [
    {
        'symbol': 'BNBUSDT',
        'time': '17:55',
        'confidence': 0.65,
        'price': 1121.54,
        'vwap': 1111.17,
        'price_vs_vwap_pct': 0.93,
        'cvd': -2998673.55,
        'oi_change_pct': -0.03,
        'liq_ratio': 3.43,  # 24 short / 7 long
        'rsi': 54.20,
        'ttl_minutes': 34,
        'market_strength': 1.35,  # Estimated from similar patterns
        'outcome': 'CANCELLED',
        'reason': 'Confluence broke or filters failed'
    },
    {
        'symbol': 'SOLUSDT',
        'time': '17:55',
        'confidence': 0.81,
        'price': 189.98,
        'vwap': 190.10,
        'price_vs_vwap_pct': -0.06,  # BELOW VWAP!
        'cvd': -18531352.45,
        'oi_change_pct': 0.02,  # OI INCREASED!
        'liq_ratio': 1.11,  # 20 short / 18 long (almost balanced)
        'rsi': 42.27,
        'ttl_minutes': 26,
        'market_strength': 1.4,
        'outcome': 'CANCELLED',
        'reason': 'OI increased (wrong direction) AND extreme CVD'
    }
]

# Convert to DataFrames
winners_df = pd.DataFrame(winners)
losers_df = pd.DataFrame(losers)
cancelled_df = pd.DataFrame(cancelled)

print(f"\n📊 SAMPLE SIZE:")
print(f"  Winners: {len(winners)} signals")
print(f"  Losers: {len(losers)} signals")
print(f"  Cancelled: {len(cancelled)} signals")

print("\n" + "=" * 80)
print("CANCELLED SIGNALS DETAILS")
print("=" * 80)

print("\n🔶 CANCELLED #1: BNBUSDT 17:55 SELL")
print(f"  Entry: 1121.54 | VWAP: 1111.17 | Price vs VWAP: +0.93%")
print(f"  CVD: -2,998,674 | OI Change: -0.03% | Liq Ratio: 3.43")
print(f"  RSI: 54.20 | Confidence: 65% | Duration: 34 min")
print(f"  ⚠️ Reason: Moderate conditions, likely lost confluence soon after")

print("\n🔶 CANCELLED #2: SOLUSDT 17:55 SELL")
print(f"  Entry: 189.98 | VWAP: 190.10 | Price vs VWAP: -0.06% (BELOW!)")
print(f"  CVD: -18,531,352 (EXTREME!) | OI Change: +0.02% (INCREASED!)")
print(f"  Liq Ratio: 1.11 (balanced) | RSI: 42.27 | Confidence: 81%")
print(f"  Duration: 26 min")
print(f"  ⚠️ Reason: Price BELOW VWAP for SELL + OI increasing (wrong direction)")

print("\n" + "=" * 80)
print("COMPARISON TABLE: WINNERS vs LOSERS vs CANCELLED")
print("=" * 80)

# Calculate averages
print(f"\n{'Indicator':<25} {'Winners':<15} {'Losers':<15} {'Cancelled':<15}")
print("-" * 75)

indicators = [
    ('confidence', 'Confidence'),
    ('price_vs_vwap_pct', 'Price vs VWAP (%)'),
    ('cvd', 'CVD'),
    ('oi_change_pct', 'OI Change (%)'),
    ('liq_ratio', 'Liq Ratio'),
    ('rsi', 'RSI'),
    ('ttl_minutes', 'Duration (min)'),
    ('market_strength', 'Market Strength'),
]

for indicator, name in indicators:
    win_avg = winners_df[indicator].mean()
    lose_avg = losers_df[indicator].mean()
    canc_avg = cancelled_df[indicator].mean()
    
    print(f"{name:<25} {win_avg:>12.2f}   {lose_avg:>12.2f}   {canc_avg:>12.2f}")

print("\n" + "=" * 80)
print("🔍 KEY INSIGHTS - CANCELLED SIGNALS")
print("=" * 80)

print("""
1. ⚠️ **BNBUSDT CANCELLED - Moderate Setup (Similar to Winners)**:
   - RSI: 54.20 (✅ Neutral, like winners)
   - Price vs VWAP: +0.93% (✅ Moderate extension)
   - CVD: -3M (⚠️ Higher than LINK winners -200K, but less than ETH losers -14M)
   - Liq Ratio: 3.43 (✅ Good, shorts liquidating)
   - OI Change: -0.03% (✅ Slight decline)
   
   WHY CANCELLED? Likely lost 3/4 confluence soon after signal generation.
   This was a BORDERLINE signal - moderate indicators could go either way.

2. 🚨 **SOLUSDT CANCELLED - RED FLAGS (System Caught It!)**:
   - Price: 189.98 vs VWAP: 190.10 → BELOW VWAP for a SELL signal! ❌
   - OI Change: +0.02% → OI INCREASED instead of decreased! ❌
   - CVD: -18.5M → EXTREME selling pressure ❌
   - High Confidence: 81% → High confidence on wrong setup ❌
   
   WHY CANCELLED? Price below VWAP + OI increasing = conflicting signals!
   System correctly identified this as invalid setup and cancelled it.

3. 📊 **SOLUSDT at 17:50 WON, 17:55 CANCELLED - What Changed?**
   
   17:50 WINNER:
   - Price: 190.27 | VWAP: 190.11 → +0.08% ABOVE VWAP ✅
   - CVD: -6.6M (moderate for SOL)
   - OI Change: ~0% (stable)
   - RSI: 43.8
   
   17:55 CANCELLED (5 mins later):
   - Price: 189.98 | VWAP: 190.10 → -0.06% BELOW VWAP ❌
   - CVD: -18.5M (EXTREME, nearly 3x worse!)
   - OI Change: +0.02% (wrong direction!)
   - RSI: 42.3
   
   In just 5 minutes, price crossed BELOW VWAP and CVD became EXTREME!
   This invalidated the SELL setup → correct cancellation.

4. 📈 **Symbol Performance Context**:
   - LINKUSDT: 50% win rate (Good performer, winners show this)
   - BNBUSDT: 24% win rate (Poor performer, cancelled was right call)
   - SOLUSDT: 18% win rate (Worst performer, 17:50 win is rare, 17:55 correctly rejected)
   - ETHUSDT: 18% win rate (All losers in sample are ETHUSDT)
""")

print("\n" + "=" * 80)
print("✅ VALIDATION OF CANCELLATION LOGIC")
print("=" * 80)

print("""
The system's cancellation mechanism is working CORRECTLY:

✅ **BNBUSDT Cancellation:**
   - Moderate setup (not extreme)
   - Lost confluence shortly after generation
   - BNB has 24% win rate, so avoiding borderline signals is smart

✅ **SOLUSDT Cancellation:**
   - Price BELOW VWAP for a SELL (contradictory positioning)
   - OI INCREASED instead of decreased (wrong trend)
   - Extreme CVD (-18.5M vs -6.6M for winner 5 min earlier)
   - These are clear red flags that invalidate the setup

🎯 **Pattern Confirmation:**
   Winners: Moderate indicators, proper positioning vs VWAP, OI in right direction
   Losers: Extreme indicators, overbought RSI, extended from VWAP
   Cancelled: Either lost confluence OR had contradictory signals

The cancellation system is PROTECTING you from bad trades!
""")

print("\n" + "=" * 80)
print("🚀 OPTIMIZATION RECOMMENDATIONS - UPDATED")
print("=" * 80)

print("""
Based on Winners (3), Losers (3), Cancelled (2):

1. **VWAP Positioning is CRITICAL:**
   - For SELL signals, price MUST be ABOVE VWAP
   - Reject if price < VWAP (like cancelled SOLUSDT)
   - Winners: +0.08% to +0.89% above VWAP
   - Losers: +0.78% to +1.56% above VWAP
   - OPTIMAL: +0.0% to +1.0% above VWAP for SELL

2. **OI Direction Matters:**
   - For SELL signals, OI should decline or stay flat
   - Reject if OI increases (like cancelled SOLUSDT +0.02%)
   - Winners: -0.02% to 0.0% (flat/slight decline)
   - Losers: -0.02% to -0.30% (varied)

3. **CVD Thresholds by Symbol:**
   - LINKUSDT: -150K to -500K (winners were in this range)
   - SOLUSDT: -5M to -10M (winner was -6.6M, cancelled was -18.5M)
   - BNBUSDT: < -3M might be too aggressive
   - ETHUSDT: Avoid CVD < -15M (all extreme CVD failed)

4. **RSI Filter (CRITICAL):**
   - Winners: RSI 43.8-55.4 (neutral zone)
   - Losers: RSI 68.3-72.5 (overbought)
   - REJECT SELL when RSI > 65

5. **Symbol-Specific Weight Adjustment:**
   - LINKUSDT: Keep current weights (50% win rate)
   - BNBUSDT: Reduce weights or increase thresholds (24% win rate)
   - SOLUSDT: Tighten CVD limits (18% win rate)
   - ETHUSDT: Significantly reduce or pause (18% win rate)

6. **Confluence Validation:**
   - Current system correctly cancels when positioning is wrong
   - Strengthen VWAP positioning rules (price vs VWAP for direction)
   - Strengthen OI direction validation
""")
