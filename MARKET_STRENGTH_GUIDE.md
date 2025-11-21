# Market Strength Multiplier Guide

## What Does "1.20x" Mean?

The **multiplier shows how much stronger current market conditions are compared to baseline**.

### Simple Analogy:
Think of ATR (Average True Range) as your **baseline speed limit** (e.g., "expect 0.4% move").

The **multiplier** is like a **turbo boost** based on current traffic (market conditions):
- **1.0x** = No boost, drive at baseline speed
- **1.20x** = 20% turbo boost, drive faster
- **1.50x** = 50% turbo boost, race mode!

---

## How It's Calculated

We start at **1.0x** (baseline) and multiply based on these factors:

### 1. Volume Strength
- **Volume > 1.6x median:** Multiply by **1.3x** (big move expected)
- **Volume > 1.3x median:** Multiply by **1.15x** (moderate boost)

### 2. CVD Strength (Direction-Aware)
- **CVD supports signal + Very strong:** Multiply by **1.4x**
- **CVD supports signal + Strong:** Multiply by **1.2x**
- **CVD opposes signal:** No boost (1.0x)

### 3. Open Interest Change
- **Big OI change (>5M or >0.5%):** Multiply by **1.15x**
- **Moderate OI change (>2M):** Multiply by **1.08x**

---

## Real Example

**BNBUSDT BUY Signal:**
```
Starting: 1.0x (baseline)

Step 1 - Volume Check:
Volume: 1.5x median → ×1.15 = 1.15x

Step 2 - CVD Check:
CVD: +537,377 USDT (supports BUY) → ×1.2 = 1.38x

Step 3 - OI Check:
OI Change: +160,396 (moderate) → ×1.08 = 1.49x

FINAL: 1.49x → ⚡ Strong (up to 30min)
```

**VS. LINKUSDT SELL (Baseline):**
```
Starting: 1.0x

Step 1 - Volume Check:
Volume: 0.52x median (weak) → ×1.0 = 1.0x

Step 2 - CVD Check:
CVD: -410k USDT (supports SELL) → ×1.2 = 1.2x

Step 3 - OI Check:
OI Change: -19k (tiny) → ×1.0 = 1.2x

FINAL: 1.20x → ⏱ Baseline (up to 60min)
```

---

## What Each Level Means

| Multiplier | Label | Duration | What It Means |
|-----------|-------|----------|---------------|
| **1.0-1.24x** | ⏱ **Baseline** | up to 60min | Weak momentum, just barely passed threshold |
| **1.25-1.49x** | ⚡ **Strong** | up to 30min | Good indicators aligned, expect quick move |
| **≥1.50x** | 🔥 **Very Strong** | up to 15min | Explosive setup, fast move expected |
| **1.3x (fixed)** | 📊 **Intraday** | up to 12h | YFI/LUMIA/ANIME positional trades |

---

## Trading Implications

### 🔥 Very Strong (1.50x+)
- **High volume + Strong CVD + Big OI = Explosive**
- **Action:** Take profit quickly, tight stop-loss
- **Risk:** Fast moves can reverse just as quickly

### ⚡ Strong (1.25-1.49x)
- **Multiple indicators aligned well**
- **Action:** Standard scalp strategy, monitor closely
- **Risk:** Moderate - expect target within 30min

### ⏱ Baseline (1.0-1.24x)
- **Just barely passed 70% confidence**
- **Action:** Be patient, wider stop-loss
- **Risk:** Higher - may not reach target, could take full hour

---

## Example Signals

**Explosive Setup (1.52x):**
```
🟢 BTCUSDT — BUY (Conf: 75%)
🎯 Target: 0.6-1.2% ⏱ up to 15min
🔥 Market Strength: Very Strong (1.52x)

Why? Volume 2x median, CVD massive, OI spiking
Strategy: Quick in/out, take profit at 0.8-1.0%
```

**Baseline Setup (1.20x):**
```
🔴 LINKUSDT — SELL (Conf: 70%)
🎯 Target: 0.3-0.6% ⏱ up to 60min
⏱ Market Strength: Baseline (1.20x)

Why? Weak volume, moderate CVD, minimal OI change
Strategy: Be patient, may take 45-60 minutes
```

---

## Key Takeaway

**The multiplier tells you HOW CONFIDENT you should be about the SPEED of the move.**

- **High multiplier (1.5x+)** = Market is pumped, move fast!
- **Low multiplier (1.0-1.2x)** = Market is sluggish, be patient

It's comparing **current market energy** (volume/CVD/OI) to **baseline normal conditions**.
