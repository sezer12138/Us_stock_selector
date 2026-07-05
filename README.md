# US Stock Selector

Screen US stocks for the top 10 by **price increase %** and **average trading volume** across 5 lookback windows: 3, 7, 14, 21, and 30 calendar days.

Also supports **momentum backtesting**: paper-trade the top-1 gainer per window with configurable take-profit, stop-loss, and time-stop rules, plus liquidity filtering and position sizing.

Data sourced from Yahoo Finance (free, 15-min delayed). Screens the S&P 500 by default.

## Quick Start

```bash
pip install -r requirements.txt

# Screen: S&P 500, top 10, all windows
python main.py

# Backtest: 60-day momentum paper trade
python main.py --backtest
```

## Screening Usage

```
python main.py [OPTIONS]

Options:
  --top N, -n N         Show top N stocks per ranking (default: 10)
  --tickers SYM,SYM,..  Comma-separated ticker list (default: S&P 500)
  --min-price P, -p P   Minimum close price to include (default: 1.0)
  --export, -e          Also save results to CSV
  --html                Generate self-contained HTML report
  --output-dir DIR, -o  Export directory (default: current dir)
  --max-window D, -w D  Max lookback window: 3, 7, 14, 21, or 30 (default: 30)
```

### Examples

```bash
# Top 15 stocks from a custom watchlist
python main.py --top 15 --tickers AAPL,MSFT,NVDA,TSLA,GOOGL,META,AMZN

# Screen S&P 500, exclude stocks under $5, export CSV + HTML
python main.py --min-price 5 --export --html

# Only 3-day and 7-day windows (faster)
python main.py --max-window 7
```

## Backtest Usage

Runs a momentum paper-trade simulation over the last 60 calendar days.
For each window strategy (3d/7d/14d/21d/30d), it:

1. Each day, picks the **top-1 stock by price increase** over that window (filtered by minimum dollar-volume for liquidity)
2. Buys at the day's **closing price**, deploying a configurable % of available capital
3. Sells when any exit condition triggers:
   - **Take-profit**: profit ≥ +X% (default +10%)
   - **Stop-loss**: loss ≤ -Y% (default -5%)
   - **Time-stop**: held ≥ N days without hitting TP/SL (optional, disabled by default)
4. Immediately re-enters with the new top gainer

### Backtest Options

```
python main.py --backtest [OPTIONS]

  --bt-days N           Backtest period in calendar days (default: 60)
  --bt-capital N        Initial capital in dollars (default: 50000)
  --bt-tp N             Take-profit % threshold (default: 10)
  --bt-sl N             Stop-loss % threshold (default: 5)
  --bt-position-pct N   % of capital to deploy per trade (default: 20)
  --bt-min-vol N        Min avg daily dollar-volume in $M (default: 10, 0=disable)
  --bt-max-hold N       Max hold days before force-exit (default: 0=disabled)
  --html                Also generate HTML backtest report with K-line charts
```

### Exit Rules

| Rule | Flag | Default | Icon | Behavior |
|------|------|---------|------|----------|
| Take-profit | `--bt-tp` | +10% | 🟢 | Sell when profit ≥ threshold |
| Stop-loss | `--bt-sl` | -5% | 🔴 | Sell when loss ≤ threshold |
| Time-stop | `--bt-max-hold` | off (0) | ⏰ | Sell when held ≥ N days |
| End-of-period | — | — | ⚪ | Close any open position at backtest end |

Priority order: TP > SL > time-stop. All entries and exits execute at the daily **closing price**.

### Position Sizing

The `--bt-position-pct` flag controls how much of your available cash is deployed per trade:

- **20%** (default): Each trade risks only 1/5 of strategy capital. The remaining 80% stays as cash reserve. Reduces concentration risk.
- **100%**: All-in per trade (old behavior). Higher returns but higher drawdowns.
- **10%**: Conservative — spreads risk across more trades, smaller swings.

### Volume / Liquidity Filter

The `--bt-min-vol` flag excludes stocks with thin liquidity:

- **$10M/day** (default): Filters out stocks you couldn't realistically trade without slippage.
- **$50M/day**: Only highly liquid large-caps.
- **0**: Disable the filter — all stocks considered regardless of volume.

### Examples

```bash
# Default 60-day backtest
python main.py --backtest

# Conservative: 10% per trade, $50M min volume, max hold 15 days
python main.py --backtest --bt-position-pct 10 --bt-min-vol 50 --bt-max-hold 15

# Aggressive: 50% per trade, no volume filter, no time limit
python main.py --backtest --bt-position-pct 50 --bt-min-vol 0

# Custom TP/SL thresholds with time stop
python main.py --backtest --bt-tp 20 --bt-sl 10 --bt-max-hold 15

# Quick test on a watchlist
python main.py --tickers AAPL,MSFT,NVDA,TSLA --backtest --bt-days 30 --bt-capital 10000

# Full backtest with HTML report (includes K-line candlestick charts)
python main.py --backtest --html
```

## Project Structure

```
us_stock_selector/
├── main.py                      # CLI entry point
├── requirements.txt
├── README.md
└── stock_selector/
    ├── __init__.py
    ├── fetcher.py               # Yahoo Finance data download (OHLCV)
    ├── screener.py              # Ranking / screening engine
    ├── backtest.py              # Momentum backtesting engine
    ├── display.py               # Terminal tables, CSV & HTML export
    └── tickers.py               # S&P 500 constituent list
```

## Output

### Screening mode
For each window (3d / 7d / 14d / 21d / 30d), two tables are printed:

- **🟢 Top 10 by Price Increase %** — ranked by percentage gain over the window
- **📊 Top 10 by Average Volume** — ranked by mean daily volume over the window

### Backtest mode (terminal)
- **Summary card** — total return, win rate, trade count, rules in effect
- **Per-strategy table** — final equity, return %, trades, wins/losses/time-stops, avg/best/worst returns
- **Trade log per strategy** — buy/sell dates, close prices, holding days, P&L% and P&L$, capital deployed, exit reason

### Backtest mode (HTML report)
- **Summary cards** — initial capital, final equity, total return, win rate
- **Strategy summary table** — per-window performance breakdown
- **Trade log with K-line charts** — each trade has a 420×130px daily candlestick chart showing:
  - Open/High/Low/Close per day (green candles = up, red = down)
  - TP, Entry, and SL reference lines with labels
  - Date labels on x-axis, price labels on y-axis
  - Entry marker (blue triangle) and exit marker (colored circle)
