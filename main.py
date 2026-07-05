#!/usr/bin/env python3
"""
US Stock Selector — Top 10 Stock Screener & Momentum Backtester

Ranks stocks by price increase % and average trading volume across
5 lookback windows: 3d, 7d, 14d, 21d, 30d.

Also supports a momentum backtest mode: paper-trade the top-1 gainer
per window with +10% take-profit and -5% stop-loss.

Usage:
    python main.py                          # default: S&P 500, top 10
    python main.py --top 15                # top 15 instead of 10
    python main.py --tickers AAPL,MSFT,NVDA,TSLA,GOOGL
    python main.py --min-price 5           # exclude stocks below $5
    python main.py --html --export         # HTML + CSV reports

    python main.py --backtest              # run 60-day momentum backtest
    python main.py --backtest --bt-days 90 # 90-day backtest
    python main.py --backtest --bt-capital 100000  # $100k starting capital
"""

import argparse
import os
import subprocess
import sys


def _auto_detect_proxy() -> None:
    """Detect macOS system proxy and set env vars for yfinance/curl_cffi."""
    if os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"):
        return

    try:
        result = subprocess.run(
            ["scutil", "--proxy"],
            capture_output=True, text=True, timeout=5,
        )
        proxy_host = None
        proxy_port = None
        for line in result.stdout.splitlines():
            if "HTTPProxy" in line and "HTTPEnable" not in line:
                proxy_host = line.split(":")[-1].strip()
            if "HTTPPort" in line:
                proxy_port = line.split(":")[-1].strip()
        if proxy_host and proxy_port:
            proxy_url = f"http://{proxy_host}:{proxy_port}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="US Stock Selector — Top N stocks by price gain & volume",
    )
    # Screening
    parser.add_argument("--top", "-n", type=int, default=10,
                        help="Number of top stocks per ranking (default: 10)")
    parser.add_argument("--tickers", "-t", type=str, default=None,
                        help="Comma-separated ticker list (overrides --universe)")
    parser.add_argument("--universe", "-u", type=str, default="sp500",
                        choices=["sp500", "nasdaq100", "both"],
                        help="Stock universe: sp500, nasdaq100, or both (default: sp500)")
    parser.add_argument("--min-price", "-p", type=float, default=1.0,
                        help="Minimum close price to include (default: 1.0)")
    parser.add_argument("--export", "-e", action="store_true",
                        help="Export results to CSV")
    parser.add_argument("--html", action="store_true",
                        help="Generate a self-contained HTML report")
    parser.add_argument("--output-dir", "-o", type=str, default=".",
                        help="Directory for CSV/HTML export (default: .)")
    parser.add_argument("--max-window", "-w", type=int, default=30,
                        choices=[3, 7, 14, 21, 30],
                        help="Max lookback window (default: 30)")

    # Backtest
    parser.add_argument("--backtest", "-b", action="store_true",
                        help="Run 60-day momentum backtest (paper trade)")
    parser.add_argument("--bt-days", type=int, default=60,
                        help="Backtest period in calendar days (default: 60)")
    parser.add_argument("--bt-capital", type=float, default=50000.0,
                        help="Initial capital for backtest (default: 50000)")
    parser.add_argument("--bt-tp", type=float, default=10.0,
                        help="Take-profit %% (default: 10)")
    parser.add_argument("--bt-sl", type=float, default=5.0,
                        help="Stop-loss %% (default: 5)")
    parser.add_argument("--bt-position-pct", type=float, default=20.0,
                        help="%% of capital to deploy per trade (default: 20)")
    parser.add_argument("--bt-min-vol", type=float, default=10.0,
                        help="Min avg daily dollar-volume in $M (default: 10, 0=disable)")
    parser.add_argument("--bt-max-hold", type=int, default=0,
                        help="Max hold days before force-exit (default: 0=disabled)")
    return parser.parse_args()


def main() -> None:
    _auto_detect_proxy()

    from stock_selector.fetcher import fetch_historical_data
    from stock_selector.screener import compute_rankings, WINDOWS
    from stock_selector.display import (
        print_rankings, export_csv, generate_html,
        print_backtest_results, print_backtest_html,
    )
    from stock_selector.tickers import get_tickers

    args = parse_args()

    # ── Ticker list ─────────────────────────────────────────────────────
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = get_tickers(args.universe)
        tag = args.universe.upper() if args.universe != "both" else "S&P 500 + NASDAQ-100"
        print(f"Universe: {tag} ({len(tickers)} tickers)")

    # ── Determine how far back to fetch ─────────────────────────────────
    if args.backtest:
        # Need: max_window + backtest_days + buffer
        lookback = args.max_window + args.bt_days + 20
    else:
        lookback = args.max_window

    # ── Fetch data ──────────────────────────────────────────────────────
    print(f"\nDownloading data for {len(tickers)} tickers ({lookback}d lookback)...")
    print("This may take a minute or two.\n")

    df = fetch_historical_data(tickers, lookback_days=lookback, progress=True)

    if df is None or df.empty:
        print("ERROR: Could not fetch stock data. Check your internet connection.", file=sys.stderr)
        print("If you are behind a proxy, set HTTP_PROXY / HTTPS_PROXY and retry.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDownloaded {len(df)} rows across {df['Ticker'].nunique()} tickers.")

    # ── Backtest path ───────────────────────────────────────────────────
    if args.backtest:
        from stock_selector.backtest import run_backtest

        print(f"Running backtest ({args.bt_days}d, ${args.bt_capital:,.0f} capital)...")

        bt_results = run_backtest(
            df,
            initial_capital=args.bt_capital,
            take_profit_pct=args.bt_tp,
            stop_loss_pct=args.bt_sl,
            backtest_days=args.bt_days,
            position_size_pct=args.bt_position_pct,
            min_dollar_volume_m=args.bt_min_vol,
            max_hold_days=args.bt_max_hold,
            windows={k: v for k, v in WINDOWS.items() if v <= args.max_window},
        )

        print_backtest_results(bt_results)

        if args.html:
            path = print_backtest_html(bt_results, output_dir=args.output_dir)
            print(f"🌐 Backtest HTML report: {path}")
        return

    # ── Screening path (default) ────────────────────────────────────────
    effective_windows = {k: v for k, v in WINDOWS.items() if v <= args.max_window}
    results = compute_rankings(df, top_n=args.top, min_price=args.min_price, windows=effective_windows)

    if not results:
        print("No rankings could be computed (insufficient data).", file=sys.stderr)
        sys.exit(1)

    print_rankings(results, top_n=args.top)

    if args.export:
        path = export_csv(results, output_dir=args.output_dir)
        print(f"📁 CSV exported to: {path}")

    if args.html:
        path = generate_html(results, top_n=args.top, output_dir=args.output_dir)
        print(f"🌐 HTML report: {path}")


if __name__ == "__main__":
    main()
