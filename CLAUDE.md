# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Screen S&P 500 (top 10, all 5 windows)
python main.py

# Screen with custom settings
python main.py --top 15 --universe nasdaq100 --min-price 5 --export --html

# Backtest (60-day default)
python main.py --backtest --html

# Load a preset config (CLI flags override preset values)
python main.py --config config/conservative.json
python main.py --config config/aggressive.json --bt-exec intraday --bt-days 90

# Custom ticker list
python main.py --tickers AAPL,MSFT,NVDA,TSLA --backtest --bt-days 30
```

There is no test suite, linter, or type-checker configured for this project.

## Architecture

### Data Flow

```
tickers.py ──→ fetcher.py ──→ screener.py ──→ display.py   (screening mode)
                   │              │
                   └──────────────┴──→ backtest.py ──→ display.py   (backtest mode)
```

All paths start from `main.py`, which parses CLI args, loads optional JSON config, then dispatches to either the screening or backtest pipeline.

### Key Constants

- **Lookback windows** (`screener.py:WINDOWS`): `{"3d": 3, "7d": 7, "14d": 14, "21d": 21, "30d": 30}`. The `--max-window` flag filters which subset is computed.
- **Ticker universes** (`tickers.py`): Hard-coded S&P 500 (~500 tickers) and NASDAQ-100 (~90 tickers) constituent lists. `get_tickers("both")` returns a deduplicated union. Wikipedia fetching exists as a fallback (`fetch_sp500_tickers()`) but the hard-coded lists are the primary source.

### Modules

- **`main.py`** — CLI entry point. Owns argparse, JSON config loading (`_load_config` / `_apply_config`), macOS proxy auto-detection via `scutil`, and report filename generation. Config keys are mapped from both hyphenated and underscored variants to argparse dest names. CLI values always override config values.

- **`stock_selector/fetcher.py`** — Downloads daily OHLCV data from Yahoo Finance via `yfinance`. Downloads in batches of 50 tickers with 1.5s delays and up to 3 retries on rate-limit errors. Normalises yfinance's MultiIndex columns into a flat `[Date, Ticker, Open, High, Low, Close, Volume]` DataFrame. Accepts a `lookback_days` parameter and adds buffer for non-trading days.

- **`stock_selector/screener.py`** — Screening engine. For each window, computes two rankings per ticker: (1) price change % from earliest to latest close within the window, and (2) average daily volume. Filters out stocks below `min_price`. Returns a dict of `WindowResult` dataclasses containing `StockRank` lists.

- **`stock_selector/backtest.py`** — Walk-forward momentum backtesting engine. Runs 5 independent paper-trading strategies (one per window), each with its own capital allocation (`initial_capital / len(windows)`). Each day: picks the top-1 gainer by price increase (filtered by dollar-volume liquidity), enters a position, and exits on TP/SL/time-stop. Three execution modes:
  - `close`: signal and execute at same-day closing price
  - `open`: signal at close, enter at next day's open (avoids look-ahead bias)
  - `intraday`: signal at close, enter at next open, check if TP/SL levels were within day's OHLC range

  Returns a dict with per-strategy results and an overall summary. Each `Trade` record carries a `price_path` (list of `[date, O, H, L, C]`) for chart rendering.

- **`stock_selector/display.py`** — Terminal output via `tabulate`, CSV export, and self-contained HTML reports. The HTML backtest report includes inline SVG candlestick (K-line) charts for each trade, rendered by `_kline_svg()` with wick/body candles, TP/Entry/SL reference lines, and entry/exit markers.

### Config System

JSON preset files in `config/` bundle all CLI arguments. Any key in the JSON that matches an argparse dest (via the `key_map` in `_apply_config`) is applied to `args` — but only if the user didn't explicitly pass that flag on the CLI. Keys starting with `_` are ignored (used for descriptions). The `--config` flag can be combined with other CLI flags to override specific preset values.
