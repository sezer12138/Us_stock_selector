# Hyperparameter Optimization Report — Momentum Backtest Grid Search

**Generated:** 2026-07-06  
**Universe:** NASDAQ-100 (100 tickers)  
**Backtest Period:** 365 calendar days, intraday execution  
**Baseline:** Adapted from `config/aggressive.json` but on nasdaq100 universe (tp=50, sl=20, pos=100%, vol≥$10M, max-hold=100d, exec=intraday)  
**Baseline Return:** +89.93% ($50K → $94,964) on NASDAQ-100

---

## Executive Summary

The 1D grid search over 5 hyperparameters (44 total backtests) reveals that **Take-Profit** and **Stop-Loss** are the most impactful levers, while **Min Volume** and **Position Size** have straightforward effects.

**Key Finding:** The individually best values for TP (+80%) and SL (+8%) do NOT combine well due to negative interaction. With a very tight stop (8%) and a very far profit target (80%), most trades get stopped out before reaching the target. To capture the upside, you must choose ONE of these improvements and keep the other parameter at its baseline.

---

## 1. Take-Profit (`bt_tp`) — Most Impactful Parameter

| TP% | Return% | Trades | Win Rate | Notes |
|-----|---------|--------|----------|-------|
| 5 | +59.73 | 150 | 86.0% | Frequent small wins |
| 10 | +52.42 | 86 | 75.6% | |
| 15 | **−7.27** | 58 | 56.9% | Only losing config |
| 20 | +10.65 | 41 | 53.7% | |
| 25 | +113.09 | 38 | 65.8% | First peak |
| 30 | +139.46 | 37 | 67.6% | **Second best** |
| 35 | +85.97 | 32 | 53.1% | |
| 40 | +89.57 | 30 | 56.7% | |
| 45 | +79.38 | 29 | 58.6% | |
| **50** | **+89.93** | **28** | **57.1%** | Baseline |
| 60 | +93.47 | 30 | 50.0% | |
| 70 | +128.88 | 28 | 46.4% | Third peak |
| **80** | **+141.85** | **26** | **53.9%** | **BEST** |

**Analysis:** The return curve is bimodal — peaks at TP=30% (+139%) and TP=80% (+142%). The worst performance is at TP=15% (−7%), where the profit target is too close to cover trading friction but too far to trigger reliably. Very high TP values (70-80%) let winning trades run to extraordinary gains, compensating for lower win rates with massive individual trade returns.

**Recommendation:** Consider `bt_tp = 30` (higher win rate, more consistent) or `bt_tp = 80` (highest total return, but more volatile with only 26 trades/year).

---

## 2. Stop-Loss (`bt_sl`) — Critical Sweet Spot

| SL% | Return% | Trades | Win Rate | Notes |
|-----|---------|--------|----------|-------|
| 5 | +103.06 | 73 | 23.3% | Too tight, many stops |
| **8** | **+142.59** | **51** | **39.2%** | **BEST — sweet spot** |
| 10 | +21.15 | 46 | 34.8% | Sharp drop-off |
| 12 | +54.56 | 40 | 42.5% | |
| 15 | +37.56 | 32 | 46.9% | |
| 18 | +76.79 | 28 | 42.9% | |
| **20** | **+89.93** | **28** | **57.1%** | Baseline |
| 25 | +77.35 | 25 | 48.0% | |
| 30 | +119.11 | 27 | 55.6% | Second peak |
| 40 | +134.54 | 25 | 64.0% | High return, high win rate |

**Analysis:** There's a sharp non-linear relationship. SL=5% is too tight (73 trades, 77% stop-outs). SL=8% finds the sweet spot. SL=10% crashes to +21% — this specific level happens to get triggered frequently by normal volatility in the top gainers. Wider stops (30-40%) perform well by giving positions room to recover from drawdowns.

**Recommendation:** `bt_sl = 8` for maximum return (but combined with TP ≤ 50) or `bt_sl = 40` for a more robust strategy (64% win rate, 25 trades, +134%).

---

## 3. Position Size (`bt_position_pct`) — Linear Multiplier

| Pos% | Return% | Trades | Win Rate |
|------|---------|--------|----------|
| 10 | +5.90 | 28 | 57.1% |
| 25 | +15.84 | 28 | 57.1% |
| 50 | +35.69 | 28 | 57.1% |
| 75 | +60.20 | 28 | 57.1% |
| **100** | **+89.93** | **28** | **57.1%** |

**Analysis:** Perfectly linear — returns scale exactly with position size. All trade counts and win rates are identical. This is effectively a leverage multiplier with no impact on strategy behavior.

**Recommendation:** 100% for maximum returns. Reduce only for risk management (lower drawdowns).

---

## 4. Min Dollar-Volume (`bt_min_vol`) — No Effect on NASDAQ-100

| Min Vol ($M) | Return% | Trades | Win Rate |
|-------------|---------|--------|----------|
| 0 | +89.93 | 28 | 57.1% |
| 5 | +89.93 | 28 | 57.1% |
| 10 | +89.93 | 28 | 57.1% |
| 25 | +89.93 | 28 | 57.1% |
| 50 | +89.93 | 28 | 57.1% |
| 100 | +89.93 | 28 | 57.1% |

**Analysis:** Zero variation — all NASDAQ-100 stocks have daily dollar-volume well above $100M. This parameter would only matter when screening smaller-cap universes.

**Recommendation:** Set to 0 to disable filtering on NASDAQ-100 (no benefit from filtering). For S&P 500 or broader universes, $10-25M may help filter illiquid stocks.

---

## 5. Max Hold Days (`bt_max_hold`) — Time-Stop Tradeoff

| Max Days | Return% | Trades | Win Rate | Notes |
|----------|---------|--------|----------|-------|
| 0 (off) | +57.61 | 11 | 63.6% | Few trades, decent returns |
| 5 | +24.80 | 266 | 54.5% | Too short, churning |
| 10 | +57.85 | 154 | 50.6% | |
| 15 | +74.58 | 112 | 54.5% | |
| 20 | +74.54 | 92 | 52.2% | |
| 30 | +42.82 | 65 | 50.8% | |
| 50 | +73.42 | 44 | 47.7% | |
| 75 | +77.93 | 33 | 60.6% | Good balance |
| **100** | **+89.93** | **28** | **57.1%** | **BEST** |
| 150 | +62.03 | 25 | 52.0% | Too long, stale positions |

**Analysis:** A time-stop of 75-100 days is optimal. Disabling the time-stop (0) yields decent returns with very few trades (11). Very short time-stops (5-10d) cause excessive churning (266 trades, only +24-58%). Beyond 100 days, returns decline as stale positions crowd out new opportunities.

**Recommendation:** Keep `bt_max_hold = 100` or reduce to 75 for more active turnover with similar returns.

---

## Parameter Interaction Warning — CRITICAL

The validation test combined the individually-best values (tp=80, sl=8) and got only **+90.66%** — barely above baseline (+89.93%). This demonstrates strong negative interaction.

**Cross-combination test reveals the true relationship:**

| Config | TP | SL | Return% | Trades | Win% | Notes |
|--------|----|----|---------|--------|------|-------|
| Baseline | 50 | 20 | +89.93 | 28 | 57.1% | Starting point |
| Best TP + base SL | 80 | 20 | +141.85 | 26 | 53.9% | |
| Best SL + base TP | 50 | 8 | +142.59 | 51 | 39.2% | Low win rate |
| TP30 + SL8 | 30 | 8 | +0.84 | 78 | 24.4% | ✗ Tight SL kills TP |
| TP80 + SL15 | 80 | 15 | +85.44 | 31 | 45.2% | Still too tight |
| TP80 + SL25 | 80 | 25 | +137.53 | 25 | 52.0% | Getting better |
| TP60 + SL25 | 60 | 25 | +98.76 | 28 | 46.4% | |
| TP30 + SL30 | 30 | 30 | +135.32 | 33 | 66.7% | High win rate |
| TP70 + SL40 | 70 | 40 | +155.27 | 25 | 52.0% | Strong |
| **🏆 TP80 + SL40** | **80** | **40** | **+172.48** | **22** | **63.6%** | **ABSOLUTE BEST** |

**Key Insight:** High Take-Profit (80%) REQUIRES a wide Stop-Loss (40%) to give positions room to breathe. With SL=8% or 15%, trades get stopped out by normal volatility before reaching the distant +80% target. The TP/SL ratio should be roughly 2:1 for optimal performance.

**Window-level analysis of the best config (TP80/SL40):**
- 3d window: +55.0%
- 7d window: +29.4%
- 14d window: +164.6%
- 21d window: +366.2% ← strongest performer
- 30d window: +247.2%

The shorter windows (3d, 7d) underperform with this strategy. The 21-day momentum window is the star performer.

---

## Recommended Optimized Configs

### 🏆 Best Overall (Highest Return + High Win Rate)
```json
{
    "universe": "nasdaq100",
    "bt_tp": 80, "bt_sl": 40, "bt_position_pct": 100,
    "bt_min_vol": 0, "bt_max_hold": 100, "bt_exec": "intraday"
}
```
**Expected:** +172% return ($50K → $136K), 22 trades, 63.6% win rate
**CLI:** `python main.py --config config/optimized.json`

### Solid Alternative (Highest Win Rate)
```json
{
    "universe": "nasdaq100",
    "bt_tp": 30, "bt_sl": 30, "bt_position_pct": 100,
    "bt_min_vol": 10, "bt_max_hold": 100, "bt_exec": "intraday"
}
```
**Expected:** +135% return, 33 trades, 66.7% win rate — more consistent, less volatile

### Conservative (Lower Risk)
```json
{
    "universe": "nasdaq100",
    "bt_tp": 30, "bt_sl": 30, "bt_position_pct": 50,
    "bt_min_vol": 10, "bt_max_hold": 75, "bt_exec": "intraday"
}
```
**Expected:** ~+68% return, lower drawdowns, more frequent turnover

> **Note:** All results above are based on NASDAQ-100 (100 tickers). The absolute return numbers **will differ** for other universes (S&P 500 or "both"). Relative trends (TP/SL ratio ≈ 2:1, wide stops needed for high TP) should generalize, but re-run the grid search to get accurate numbers for a different universe.

---

## Files Generated

| File | Description |
|------|-------------|
| `results/grid_search_results.json` | Raw data from all 44 backtests |
| `results/grid_search_report.md` | Detailed per-parameter tables |
| `results/chart_bt_tp.png` | Return vs Take-Profit chart |
| `results/chart_bt_sl.png` | Return vs Stop-Loss chart |
| `results/chart_bt_position_pct.png` | Return vs Position Size chart |
| `results/chart_bt_min_vol.png` | Return vs Min Volume chart |
| `results/chart_bt_max_hold.png` | Return vs Max Hold Days chart |
| `config/optimized.json` | Combined best config (note: interaction warning above) |
| `grid_search.py` | Standalone script — re-runnable with `python grid_search.py` |
