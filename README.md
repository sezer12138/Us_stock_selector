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
python main.py --backtest --html

# Load a preset config
python main.py --config config/conservative.json
```

## Config Presets

The `config/` folder contains JSON preset files that bundle all arguments together.
Use `--config` to load one — any CLI flags you add will override the preset.

| Preset | Description |
|--------|-------------|
| `config/default.json` | Balanced: 20% position, $10M min vol, close exec |
| `config/conservative.json` | Low risk: 10% position, $50M min vol, max hold 15d, intraday exec |
| `config/aggressive.json` | High risk: 50% position, no vol filter, TP+15%/SL-8%, close exec |
| `config/nasdaq100_quick.json` | Quick NASDAQ-100 test: 30d, open exec, max hold 7d |
| `config/screening.json` | Screening mode: top 15 S&P 500, export CSV + HTML |

Create your own by copying any preset and editing the JSON.

```bash
# Run with a preset
python main.py --config config/conservative.json

# Override specific settings
python main.py --config config/aggressive.json --bt-exec intraday --bt-days 90
```

## Screening Usage

```
python main.py [OPTIONS]

Options:
  --top N, -n N         Show top N stocks per ranking (default: 10)
  --tickers SYM,SYM,..  Comma-separated ticker list (overrides --universe)
  --universe U, -u U    Stock universe: sp500, nasdaq100, or both (default: sp500)
  --min-price P, -p P   Minimum close price to include (default: 1.0)
  --export, -e          Also save results to CSV
  --html                Generate self-contained HTML report
  --output-dir DIR, -o  Export directory (default: results/)
  --max-window D, -w D  Max lookback window: 3, 7, 14, 21, or 30 (default: 30)
```

### Examples

```bash
# Top 15 stocks from a custom watchlist
python main.py --top 15 --tickers AAPL,MSFT,NVDA,TSLA,GOOGL,META,AMZN

# Screen NASDAQ-100 instead of S&P 500
python main.py --universe nasdaq100

# Screen both S&P 500 + NASDAQ-100 combined (deduplicated)
python main.py --universe both

# Screen S&P 500, exclude stocks under $5, export CSV + HTML
python main.py --min-price 5 --export --html

# Only 3-day and 7-day windows (faster)
python main.py --max-window 7

# Backtest on NASDAQ-100 universe
python main.py --backtest --universe nasdaq100
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

## Grid Search (Hyperparameter Optimization)

`python grid_search.py` sweeps each of 5 hyperparameters independently over a
range of values, running a full 365-day momentum backtest for each value to
find the optimal settings for your backtest configuration.

### What It Does

Starting from the `config/aggressive.json` baseline, the script:

1. **Downloads** ~1 year of daily OHLCV data for the NASDAQ-100 universe
   (fetched once, cached to `results/_grid_search_data.csv`)
2. **Sweeps** each parameter over its range while keeping all other parameters
   at their baseline values (1D grid search)
3. **Generates** a return-vs-value chart per parameter (`results/chart_*.png`)
4. **Outputs** a markdown report (`results/grid_search_report.md`) and a JSON
   results file (`results/grid_search_results.json`)
5. **Recommends** an optimized config combining each parameter's best value,
   saved to `config/optimized.json`
6. **Validates** by running the baseline and optimized configs side-by-side

### Parameters Swept

| Parameter | Flag | Range Tested | Baseline |
|-----------|------|-------------|----------|
| Take-Profit | `bt_tp` | 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80 | 50 |
| Stop-Loss | `bt_sl` | 5, 8, 10, 12, 15, 18, 20, 25, 30, 40 | 20 |
| Position Size | `bt_position_pct` | 10, 25, 50, 75, 100 | 100 |
| Min Volume ($M) | `bt_min_vol` | 0, 5, 10, 25, 50, 100 | 10 |
| Max Hold Days | `bt_max_hold` | 5, 10, 15, 20, 30, 50, 75, 100, 150, 0 | 100 |

### How to Run

```bash
python grid_search.py
```

The script has no command-line arguments. To test different parameter ranges or
a different baseline, edit the `CONFIG` object inside `grid_search.py`.

### Output

- `config/optimized.json` — recommended config combining each parameter's best value
- `results/chart_*.png` — per-parameter return-vs-value line charts (dark theme)
- `results/grid_search_results.json` — full results in machine-readable format
- `results/grid_search_report.md` — human-readable markdown report with summary tables
- Terminal output — summary table comparing baseline vs optimized performance

## Project Structure

```
us_stock_selector/
├── main.py                      # CLI entry point
├── requirements.txt
├── README.md
├── config/                      # JSON preset configs
│   ├── default.json
│   ├── conservative.json
│   ├── aggressive.json
│   ├── nasdaq100_quick.json
│   └── screening.json
├── results/                     # Generated reports (HTML, CSV)
├── stock_selector/
│   ├── __init__.py
│   ├── fetcher.py               # Yahoo Finance data download (OHLCV)
│   ├── screener.py              # Ranking / screening engine
│   ├── backtest.py              # Momentum backtesting engine
│   ├── display.py               # Terminal tables, CSV & HTML export
│   └── tickers.py               # S&P 500 & NASDAQ-100 constituent lists
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
