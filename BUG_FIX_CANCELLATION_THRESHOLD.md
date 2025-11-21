# Bug Fix: Cancellation Threshold Mismatch

**Date:** October 19, 2025  
**Severity:** High  
**Status:** ✅ FIXED

---

## 🐛 **The Bug**

Signals with 65-66% confidence were being cancelled with the message "below 70% threshold" even though they were successfully generated.

### Root Cause

The `check_cancellation()` function in `main.py` was using the **global default threshold (70%)** instead of the **per-coin threshold** when checking whether to cancel signals.

**Buggy Code (Line 160):**
```python
min_confidence = cfg.get('min_score_pct', 0.70)  # Always used 70%!
```

### The Problem

1. **Signal Generation:** Uses per-coin `min_score_pct` from `coin_configs` in `config.yaml`
   - BTCUSDT: 50% (testing mode)
   - ETHUSDT: 50% (testing mode)
   - Others: 50% (testing mode)

2. **Signal Cancellation:** Used hardcoded global 70% threshold
   - ALL symbols checked against 70%
   - Ignored the per-coin configuration completely

### Impact

**Signals with 50-69% confidence were in "impossible limbo":**
- ✅ Passed generation threshold (50%) → Signal sent to Telegram
- ❌ Failed cancellation check (< 70%) → Immediately cancelled on next 5-min check

**Example:**
- SOLUSDT generates signal at 66% confidence (passes 50% threshold)
- 5 minutes later: 66% < 70% → CANCELLED!
- User receives signal + cancellation within minutes

---

## ✅ **The Fix**

Updated `check_cancellation()` to read the **same per-coin threshold** used for signal generation:

**Fixed Code (Lines 164-166):**
```python
# Get per-coin min_score_pct threshold (same as used for signal generation)
coin_config = cfg.get('coin_configs', {}).get(symbol, cfg.get('default_coin', {}))
min_confidence = coin_config.get('min_score_pct', cfg.get('min_score_pct', 0.70))
```

### What Changed

| Symbol | OLD Threshold | NEW Threshold | Change |
|--------|---------------|---------------|--------|
| BTCUSDT | 70% | 50% | ✅ Fixed |
| ETHUSDT | 70% | 50% | ✅ Fixed |
| SOLUSDT | 70% | 50% | ✅ Fixed |
| LINKUSDT | 70% | 50% | ✅ Fixed |
| BNBUSDT | 70% | 50% | ✅ Fixed |
| DOGEUSDT | 70% | 50% | ✅ Fixed |
| AVAXUSDT | 70% | 50% | ✅ Fixed |
| YFIUSDT | 70% | 50% | ✅ Fixed |

---

## 📊 **Before vs After**

### Before (Buggy Behavior)
```
1. Signal generated at 65% → Sent to Telegram ✅
2. Next check (5 min later): 65% < 70% → CANCELLED ❌
3. User sees: Signal + Cancellation (confusing!)
```

### After (Fixed Behavior)
```
1. Signal generated at 65% → Sent to Telegram ✅
2. Next check: 65% > 50% → Still valid ✅
3. Signal stays active unless confidence drops below 50%
4. Only cancelled if market conditions truly deteriorate
```

---

## 🎯 **Expected Impact**

1. **Fewer False Cancellations:** Signals at 50-69% confidence will no longer be cancelled immediately
2. **Consistent Logic:** Generation and cancellation now use the same threshold
3. **More Stable Signals:** Signals will stay active longer, allowing targets to be reached
4. **Better User Experience:** Fewer confusing "signal → immediate cancellation" sequences

---

## ✅ **Verification**

**Test Results:**
- All 8 symbols now correctly read their per-coin threshold (50% during testing)
- Cancellation logic matches signal generation logic
- Workflow restarted to apply fix

**Files Modified:**
- `main.py` (lines 164-166)
- `replit.md` (documented fix)

**Status:** ✅ FIXED & DEPLOYED
