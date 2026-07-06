# Momentum Stock Selector — 20-Year Backtest Analysis (2006–2026)

## Strategy Overview

This repository implements a **multi-window momentum backtesting engine** for US stocks. The core idea is simple:

1. Every day, for each lookback window (3d to 80d), pick the **top-1 stock by price increase** over that window
2. Filter for liquidity (minimum daily dollar-volume)
3. Enter at the next day's open, deploying a configurable % of capital
4. Exit when: **take-profit (+80%)** triggers, **stop-loss (−40%)** triggers, **100-day time limit** expires, or the backtest period ends
5. Immediately re-enter with the new top gainer

The strategy runs **7 independent windows simultaneously** (3d, 7d, 14d, 21d, 30d, 50d, 80d), each managing its own capital allocation. This provides both diversification across timeframes and a natural comparison of which momentum horizons work best.

---

## 20-Year Backtest Results

| Metric | Value |
|--------|-------|
| **Period** | 2006-07-07 → 2026-07-02 (5,028 trading days) |
| **Universe** | NASDAQ-100 (~100 tickers) |
| **Initial Capital** | $50,000 ($7,143 per window × 7 windows) |
| **Final Equity** | **$36,921,056** |
| **Total Return** | **+73,742%** |
| **Total Trades** | 540 |
| **Win Rate** | 62.6% |
| **Execution** | Intraday (entry at next open, exit at TP/SL crossing) |
| **Rules** | TP +80%, SL −40%, Max Hold 100d, 100% position size |

### Benchmark Comparison

| | Strategy | QQQ Buy&Hold | SPY Buy&Hold |
|---|----------|-------------|-------------|
| **20-Year Return** | **+73,742%** | +2,111% | +750% |
| **Final Value (on $50K)** | $36,921,056 | $1,105,595 | $424,760 |
| **Alpha** | — | +71,631% | +72,993% |
| **Annualized Return** | ~39.1% | ~16.7% | ~11.3% |

Strategy outperformed QQQ by **35×** and SPY by **87×** over 20 years.

---

## Per-Window Performance

| Window | Final Equity | Return % | Trades | Wins | Losses | Time-Stops | Avg Return | Best | Worst |
|--------|-------------|----------|--------|------|--------|------------|------------|------|-------|
| **50D** | **$26,039,720** | +364,456% | 77 | 7 | 4 | 65 | +15.20% | +80% | −40% |
| **30D** | $6,109,599 | +85,434% | 80 | 6 | 8 | 65 | +13.27% | +80% | −40% |
| **80D** | $2,935,843 | +41,002% | 77 | 3 | 7 | 66 | +11.98% | +80% | −40% |
| **21D** | $1,523,504 | +21,229% | 78 | 8 | 6 | 63 | +11.42% | +80% | −40% |
| **14D** | $220,942 | +2,993% | 77 | 5 | 8 | 63 | +9.15% | +80% | −40% |
| 3D | $52,205 | +631% | 75 | 1 | 5 | 68 | +5.35% | +80% | −40% |
| 7D | $39,243 | +449% | 76 | 3 | 6 | 66 | +5.73% | +80% | −40% |

**Key insight:** Longer momentum windows dramatically outperform. The 50-day window alone generated **$26M** — 70% of total portfolio equity. The 3-day and 7-day windows barely beat SPY buy-and-hold and significantly underperformed QQQ.

**Why longer windows win:** A stock that's up strongly over 50+ days is in a sustained uptrend, not just a short-term bounce. These trends have more room to run toward the +80% profit target. Short windows chase noise — most 3d gainers reverse before reaching +80%.

---

## Notable Winning Trades

The strategy's edge comes from catching **massive momentum runs** in iconic growth stocks:

| Window | Ticker | Entry | Exit | Days | P&L |
|--------|--------|-------|------|------|-----|
| 50D | NFLX | 2010-03-19 | 2010-06-14 | 87 | +80% |
| 50D | NFLX | 2012-12-17 | 2013-01-25 | 39 | +80% |
| 50D | TSLA | 2013-05-09 | 2013-07-12 | 64 | +80% |
| 50D | TSLA | 2020-01-07 | 2020-02-04 | 28 | +80% |
| 21D | SMCI | 2023-02-22 | 2023-05-18 | 85 | +80% |
| 21D | SMCI | 2024-02-06 | 2024-03-08 | 31 | +80% |
| 30D | APP | 2024-10-01 | 2024-11-07 | 37 | +80% |
| 30D | APP | 2024-11-08 | 2025-02-13 | 97 | +80% |
| 14D | TSLA | 2013-05-24 | 2013-08-26 | 94 | +80% |
| 14D | TSLA | 2019-12-31 | 2020-02-03 | 34 | +80% |

Recurring winners: **TSLA** (4 take-profits), **SMCI** (4), **APP** (4), **NFLX** (2), **AMD** (2), **MU** (2), **INTC** (2). The strategy repeatedly catches the same high-momentum names across different windows and time periods.

---

## Investment Insights

### 1. Momentum works — but only at the right timeframe

The 3d and 7d windows generated only +449–631% over 20 years — barely keeping pace with SPY (+750%) and trailing QQQ (+2,111%) badly. Meanwhile, the 50d window returned +364,456%. The lesson: **very short-term "momentum" is mostly noise**. Meaningful trends develop over weeks to months, not days.

### 2. You don't need many winners to win big

The 50d window had only **7 take-profit wins out of 77 trades** (9% hit rate on TP), yet generated $26M. The +80% winners are so large that they overwhelm the many small time-stop exits (−5% to +20% range). This is the classic **asymmetric payoff** profile: cut losers slowly (time-stop at breakeven-ish), let winners compound fully to +80%.

### 3. The TP/SL ratio is critical

The optimized config uses **TP=80%, SL=40%** — a 2:1 reward-to-risk ratio. The wide 40% stop-loss is essential: with a tight stop, most trades get shaken out by normal volatility before reaching the +80% target. The 100-day time-stop acts as a secondary exit for trades that drift sideways.

### 4. Time-stop dominates exit reasons

Across all 540 trades, roughly **80% exit via time-stop or end-of-period**, not TP or SL. The 100-day hold limit means most positions close at whatever the market gives after ~3 months. The strategy is less "precision market timing" and more "ride the trend until it fades or explodes."

### 5. NASDAQ-100 is the ideal universe

The strategy thrives on high-volatility, high-growth tech names. The NASDAQ-100 provides exactly this — stocks like TSLA, SMCI, APP, and NFLX that can deliver massive runs in months. An S&P 500 universe would produce lower returns due to more stable, slower-moving constituents.

### 6. 50-day momentum is the sweet spot

The 50d window dominates all others. It's long enough to filter out noise and short-term reversals, but short enough to catch emerging trends early. The 80d window is slightly too slow (fewer take-profits: only 3), and the 14d/21d windows catch trends but with more noise.

---

## Caveats & Risks

### Survivorship Bias
The backtest uses **today's NASDAQ-100 constituents** for all historical periods. Stocks that were in the index in 2006 but later dropped out are missing. Meanwhile, stocks that only joined recently (APP in 2024, ARM in 2023) only contribute to recent years. Actual returns trading the true historical index composition would be **lower** than shown here.

### Survivorship Bias in Winners
The biggest winners (TSLA, SMCI, APP) are extreme survivors — they had to survive and thrive to appear in today's NASDAQ-100. The strategy's edge comes from catching these outliers, but in real time you wouldn't know which stocks would become outliers.

### Compounding at Scale
The backtest assumes you can deploy 100% of capital into a single stock position and exit at intraday TP/SL levels with no slippage. In reality, deploying millions into a single NASDAQ-100 stock would move the market. Position sizing would need to be capped at real-world liquidity limits.

### Drawdown Risk
With 40% stop-losses and 100% position sizing, individual positions can lose 40% of allocated capital. Across 7 windows, simultaneous drawdowns are possible. The 20-year equity curve likely contains several 30-50% portfolio drawdowns.

### Regime Dependence
The 2006–2026 period includes the longest bull market in history (2009–2020), near-zero interest rates, and tech dominance. A period with higher rates, value outperformance, or mean-reversion in tech would produce very different results.

---

## Practical Takeaways

1. **Focus on 30d–50d momentum.** These windows capture the sweet spot between noise-filtering and trend-timing.
2. **Let winners run.** The +80% take-profit is not too high — the biggest winners deliver the majority of returns.
3. **Give positions room.** A 40% stop-loss is wide but necessary. Tighter stops turn winning strategies into break-even ones.
4. **Diversify across windows.** Even though 50d dominates, running all 7 windows provides smoother equity curves and catches trends at different stages.
5. **Compare to benchmarks.** The strategy's +73,742% looks extraordinary, but QQQ itself returned +2,111% — tech was the place to be. Always measure alpha, not just absolute return.
6. **Don't over-optimize.** These results are in-sample optimized. Forward performance will almost certainly be lower. Use the config as a starting point, not a guarantee.

---

*Generated from `results/backtest_nasdaq100_7300d_tp80_sl40_pos100_max100d_intraday_20260706_175118.html`*
*Config: `config/optimized_20_years.json`*
