#!/usr/bin/env python3
"""
US Stock Selector — Top 10 Stock Screener & Momentum Backtester

Ranks stocks by price increase % and average trading volume across
5 lookback windows: 3d, 7d, 14d, 21d, 30d.

Also supports a momentum backtest mode: paper-trade the top-1 gainer
per window with configurable take-profit / stop-loss / time-stop rules.

Usage:
    python main.py                                    # defaults
    python main.py --config config/conservative.json  # load preset
    python main.py --backtest                         # 60-day backtest
    python main.py --backtest --bt-exec intraday      # intraday execution
"""

import argparse
import json
import os
import sys
from datetime import datetime


# ── Config file support ────────────────────────────────────────────────────

def _load_config(path: str) -> dict:
    """Load a JSON config file.  Exits with a message on failure."""
    if not os.path.exists(path):
        print(f"ERROR: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path) as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)
    return cfg


def _apply_config(args: argparse.Namespace, cfg: dict, user_set: set) -> None:
    """
    Apply JSON config values to args for any key that matches an
    argparse dest name.  Skips keys the user explicitly set via CLI.
    """
    key_map = {
        "top": "top", "n": "top",
        "tickers": "tickers", "universe": "universe",
        "min_price": "min_price", "min-price": "min_price",
        "export": "export", "html": "html",
        "output_dir": "output_dir", "output-dir": "output_dir",
        "max_window": "max_window", "max-window": "max_window",
        "backtest": "backtest",
        "bt_days": "bt_days", "bt-days": "bt_days",
        "bt_capital": "bt_capital", "bt-capital": "bt_capital",
        "bt_tp": "bt_tp", "bt-tp": "bt_tp",
        "bt_sl": "bt_sl", "bt-sl": "bt_sl",
        "bt_position_pct": "bt_position_pct", "bt-position-pct": "bt_position_pct",
        "bt_min_vol": "bt_min_vol", "bt-min-vol": "bt_min_vol",
        "bt_max_hold": "bt_max_hold", "bt-max-hold": "bt_max_hold",
        "bt_exec": "bt_exec", "bt-exec": "bt_exec",
    }

    for json_key, value in cfg.items():
        if json_key.startswith("_"):
            continue
        dest = key_map.get(json_key)
        if dest is None or dest in user_set:
            continue

        # Apply config value with correct type
        current = getattr(args, dest)
        if isinstance(current, bool):
            setattr(args, dest, bool(value))
        elif isinstance(current, int):
            setattr(args, dest, int(value))
        elif isinstance(current, float):
            setattr(args, dest, float(value))
        else:
            setattr(args, dest, value)


# ── Argument parsing ───────────────────────────────────────────────────────

def parse_args(argv: list = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="US Stock Selector — Top N stocks by price gain & volume",
    )
    # Config
    parser.add_argument("--config", "-c", type=str, default=None,
                        help="Path to JSON config file (preset)")
    # Screening
    parser.add_argument("--top", "-n", type=int, default=10)
    parser.add_argument("--tickers", "-t", type=str, default=None)
    parser.add_argument("--universe", "-u", type=str, default="sp500",
                        choices=["sp500", "nasdaq100", "both"])
    parser.add_argument("--min-price", "-p", type=float, default=1.0)
    parser.add_argument("--export", "-e", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--output-dir", "-o", type=str, default="results")
    parser.add_argument("--max-window", "-w", type=int, default=80,
                        choices=[3, 7, 14, 21, 30, 50, 80])
    # Backtest
    parser.add_argument("--backtest", "-b", action="store_true")
    parser.add_argument("--bt-days", type=int, default=60)
    parser.add_argument("--bt-capital", type=float, default=50000.0)
    parser.add_argument("--bt-tp", type=float, default=10.0)
    parser.add_argument("--bt-sl", type=float, default=5.0)
    parser.add_argument("--bt-position-pct", type=float, default=20.0)
    parser.add_argument("--bt-min-vol", type=float, default=10.0)
    parser.add_argument("--bt-max-hold", type=int, default=0)
    parser.add_argument("--bt-exec", type=str, default="close",
                        choices=["close", "open", "intraday"])

    # Determine which args were explicitly passed on the command line
    # by scanning sys.argv for flag names.  This is more reliable than
    # comparing with defaults (which fails when user passes the default value).
    import re
    cli_tokens = set()
    cli_args = argv if argv is not None else sys.argv[1:]
    for i, tok in enumerate(cli_args):
        if tok.startswith("--"):
            dest = tok.lstrip("-").replace("-", "_")
            cli_tokens.add(dest)
        elif tok.startswith("-") and len(tok) == 2:
            # Short flags — map to dest names
            short_map = {"n": "top", "t": "tickers", "u": "universe",
                         "p": "min_price", "e": "export", "o": "output_dir",
                         "w": "max_window", "b": "backtest", "c": "config"}
            cli_tokens.add(short_map.get(tok[1], ""))

    # Parse actual args
    args = parser.parse_args(argv)

    # Build set of dest names the user explicitly set
    user_set = cli_tokens & set(vars(args).keys())

    # Load config file (CLI values override config)
    if args.config:
        cfg = _load_config(args.config)
        _apply_config(args, cfg, user_set)
        cfg_name = os.path.splitext(os.path.basename(args.config))[0]
        print(f"Loaded config: {cfg_name}")

    return args


# ── Report filename builder ────────────────────────────────────────────────

def _report_basename(args: argparse.Namespace) -> str:
    """Build a descriptive base filename like 'backtest_sp500_60d_tp10_sl5_pos20'."""
    mode = "backtest" if args.backtest else "screen"
    universe = args.universe
    if args.tickers:
        universe = "custom"

    if args.backtest:
        parts = [
            mode, universe,
            f"{args.bt_days}d",
            f"tp{args.bt_tp:.0f}", f"sl{args.bt_sl:.0f}",
            f"pos{args.bt_position_pct:.0f}",
        ]
        if args.bt_max_hold > 0:
            parts.append(f"max{args.bt_max_hold}d")
        if args.bt_min_vol:
            parts.append(f"vol{args.bt_min_vol:.0f}M")
        parts.append(args.bt_exec)
    else:
        parts = [mode, universe, f"top{args.top}", f"w{args.max_window}"]

    return "_".join(parts)


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    from stock_selector.fetcher import auto_detect_proxy
    auto_detect_proxy()

    from stock_selector.fetcher import fetch_historical_data
    from stock_selector.screener import compute_rankings, ORDERED_WINDOWS, WINDOWS
    from stock_selector.display import (
        print_rankings, export_csv, generate_html,
        print_backtest_results, print_backtest_html,
    )
    from stock_selector.tickers import get_tickers

    args = parse_args()

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # ── Ticker list ─────────────────────────────────────────────────────
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = get_tickers(args.universe)
        tag = args.universe.upper() if args.universe != "both" else "S&P 500 + NASDAQ-100"
        print(f"Universe: {tag} ({len(tickers)} tickers)")

    # Always include QQQ and SPY for benchmark comparison in backtest mode
    benchmark_tickers = ["QQQ", "SPY"]
    all_tickers = tickers + [t for t in benchmark_tickers if t not in tickers]

    # ── Data fetch ──────────────────────────────────────────────────────
    if args.backtest:
        lookback = args.max_window + args.bt_days + 20
    else:
        lookback = args.max_window

    print(f"\nDownloading data for {len(all_tickers)} tickers ({lookback}d lookback)...")
    print("This may take a minute or two.\n")

    df = fetch_historical_data(all_tickers, lookback_days=lookback, progress=True)

    if df is None or df.empty:
        print("ERROR: Could not fetch stock data.", file=sys.stderr)
        sys.exit(1)

    # Separate benchmark data from stock data
    benchmark_df = df[df["Ticker"].isin(benchmark_tickers)].copy()
    df = df[~df["Ticker"].isin(benchmark_tickers)].copy()

    stock_count = df["Ticker"].nunique()
    print(f"\nDownloaded {len(df)} rows across {stock_count} tickers "
          f"(+ {benchmark_df['Ticker'].nunique()} benchmarks: QQQ, SPY).")

    # ── Survivorship bias detection ──────────────────────────────────────
    if args.backtest and not args.tickers:
        total_dates = df["Date"].nunique()
        if total_dates > 0:
            coverage = df.groupby("Ticker")["Date"].nunique()
            full_coverage = len(coverage[coverage >= total_dates * 0.8])
            partial = stock_count - full_coverage
            if partial > 0:
                pct = partial / stock_count * 100
                print(f"  ⚠  Survivorship bias: {partial}/{stock_count} tickers ({pct:.0f}%) "
                      f"have <80% data coverage in this period.")
                print(f"     These may be recently listed or historically absent from the index.")
                print(f"     Backtest returns may be OVERSTATED vs a true historical simulation.")

    # Build base filename for reports
    base = _report_basename(args)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Backtest path ───────────────────────────────────────────────────
    if args.backtest:
        from stock_selector.backtest import run_backtest

        print(f"Running backtest ({args.bt_days}d, ${args.bt_capital:,.0f} capital, "
              f"exec={args.bt_exec})...")

        bt_results = run_backtest(
            df,
            initial_capital=args.bt_capital,
            take_profit_pct=args.bt_tp,
            stop_loss_pct=args.bt_sl,
            backtest_days=args.bt_days,
            position_size_pct=args.bt_position_pct,
            min_dollar_volume_m=args.bt_min_vol,
            max_hold_days=args.bt_max_hold,
            exec_mode=args.bt_exec,
            windows={k: v for k, v in WINDOWS.items() if v <= args.max_window},
            benchmark_df=benchmark_df,
        )

        print_backtest_results(bt_results)

        if args.html:
            path = print_backtest_html(bt_results, output_dir=args.output_dir,
                                       filename=f"{base}_{ts}.html")
            print(f"🌐 HTML report: {path}")
        return

    # ── Screening path ──────────────────────────────────────────────────
    effective_windows = {k: v for k, v in WINDOWS.items() if v <= args.max_window}
    results = compute_rankings(df, top_n=args.top, min_price=args.min_price,
                               windows=effective_windows)

    if not results:
        print("No rankings could be computed (insufficient data).", file=sys.stderr)
        sys.exit(1)

    print_rankings(results, top_n=args.top)

    if args.export:
        path = export_csv(results, output_dir=args.output_dir)
        print(f"📁 CSV: {path}")

    if args.html:
        path = generate_html(results, top_n=args.top, output_dir=args.output_dir,
                             filename=f"{base}_{ts}.html")
        print(f"🌐 HTML report: {path}")


if __name__ == "__main__":
    main()
