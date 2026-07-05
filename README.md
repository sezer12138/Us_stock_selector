# US Stock Selector

Screen US stocks for the top 10 by **price increase %** and **average trading volume** across 5 lookback windows: 3, 7, 14, 21, and 30 calendar days.

Also supports **momentum backtesting**: paper-trade the top-1 gainer per window with configurable take-profit / stop-loss rules.

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

1. Each day, picks the **top-1 stock by price increase** over that window
2. Buys at the day's closing price (allocates equal capital per strategy)
3. Sells when **profit ≥ +10%** (take-profit) or **loss ≤ -5%** (stop-loss)
4. Immediately re-enters with the new top gainer

```
python main.py --backtest [OPTIONS]

Backtest Options:
  --bt-days N           Backtest period in calendar days (default: 60)
  --bt-capital N        Initial capital in dollars (default: 50000)
  --bt-tp N             Take-profit % threshold (default: 10)
  --bt-sl N             Stop-loss % threshold (default: 5)
  --html                Also generate HTML backtest report
```

### Examples

```bash
# Default 60-day backtest with $50k capital
python main.py --backtest

# 90-day backtest, $100k capital, tighter stops
python main.py --backtest --bt-days 90 --bt-capital 100000 --bt-sl 3

# Small quick test on a watchlist
python main.py --tickers AAPL,MSFT,NVDA,TSLA --backtest --bt-days 30 --bt-capital 10000

# Backtest with HTML report
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
    ├── fetcher.py               # Yahoo Finance data download
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

### Backtest mode
- **Summary card** — total return, win rate, trade count
- **Per-strategy table** — final equity, return %, trades, avg/best/worst returns
- **Trade log per strategy** — entry/exit dates, prices, P&L, exit reason (🟢 take-profit, 🔴 stop-loss, ⚪ end-of-period)
- **HTML report** — dark-themed, self-contained, with summary cards and trade logs
