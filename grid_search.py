#!/usr/bin/env python3
"""
Grid Search — Hyperparameter Optimization for Momentum Backtest

Performs independent 1D sweeps over 5 hyperparameters starting from the
aggressive.json baseline.  Fetches data once, reuses it across all runs,
and generates per-parameter return-vs-value charts.

Usage:
    python grid_search.py
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd

# ── Add project root to path (so script works from any cwd) ─────────────
PROJ_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ_ROOT)

from stock_selector.fetcher import auto_detect_proxy, fetch_v8_data
from stock_selector.tickers import get_tickers
from stock_selector.backtest import run_backtest
from stock_selector.screener import WINDOWS


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GridSearchConfig:
    """Container for grid search hyperparameter optimization configuration."""
    baseline: dict
    sweeps: List[Tuple[str, list]]
    param_labels: dict
    output_dir: str
    cache_path: str
    results_path: str


_OUTPUT_DIR = os.path.join(PROJ_ROOT, "results")

CONFIG = GridSearchConfig(
    baseline={
        "universe": "both",
        "bt_days": 365,
        "bt_capital": 50000,
        "bt_tp": 50,
        "bt_sl": 20,
        "bt_position_pct": 100,
        "bt_min_vol": 10,
        "bt_max_hold": 100,
        "bt_exec": "intraday",
    },
    sweeps=[
        ("bt_tp",           [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80]),
        ("bt_sl",           [5, 8, 10, 12, 15, 18, 20, 25, 30, 40]),
        ("bt_position_pct", [10, 25, 50, 75, 100]),
        ("bt_min_vol",      [0, 5, 10, 25, 50, 100]),
        ("bt_max_hold",     [5, 10, 15, 20, 30, 50, 75, 100, 150, 0]),
    ],
    param_labels={
        "bt_tp":           "Take-Profit (%)",
        "bt_sl":           "Stop-Loss (%)",
        "bt_position_pct": "Position Size (% of capital)",
        "bt_min_vol":      "Min Daily Dollar-Volume ($M, 0=disabled)",
        "bt_max_hold":     "Max Hold Days (0=disabled)",
    },
    output_dir=_OUTPUT_DIR,
    cache_path=os.path.join(_OUTPUT_DIR, "_grid_search_data.csv"),
    results_path=os.path.join(_OUTPUT_DIR, "grid_search_results.json"),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _param_slug(param: str, value) -> str:
    """Short label for a parameter value, e.g. 'tp50' or 'pos100'."""
    if param == "bt_tp":
        return f"tp{int(value)}"
    elif param == "bt_sl":
        return f"sl{int(value)}"
    elif param == "bt_position_pct":
        return f"pos{int(value)}"
    elif param == "bt_min_vol":
        return f"vol{int(value)}"
    elif param == "bt_max_hold":
        return f"hold{int(value)}"
    return f"{param}={value}"


def _build_config(param: str, value, base: dict) -> dict:
    """Return a backtest config dict with one parameter overridden."""
    cfg = dict(base)
    cfg[param] = value
    return cfg


def _run_one(param: str, value, df: pd.DataFrame, base: dict) -> dict:
    """Run a single backtest and return the summary dict."""
    cfg = _build_config(param, value, base)
    t0 = time.time()

    result = run_backtest(
        df,
        initial_capital=cfg["bt_capital"],
        take_profit_pct=cfg["bt_tp"],
        stop_loss_pct=cfg["bt_sl"],
        backtest_days=cfg["bt_days"],
        position_size_pct=cfg["bt_position_pct"],
        min_dollar_volume_m=cfg["bt_min_vol"],
        max_hold_days=cfg["bt_max_hold"],
        exec_mode=cfg["bt_exec"],
        windows={k: v for k, v in WINDOWS.items() if v <= 30},
    )

    elapsed = time.time() - t0
    s = result["summary"]

    # Per-strategy returns for deeper analysis
    strat_returns = {
        label: strat["return_pct"]
        for label, strat in result["strategies"].items()
    }

    return {
        "param": param,
        "value": value,
        "slug": _param_slug(param, value),
        "total_return_pct": s["total_return_pct"],
        "final_equity": s["final_equity"],
        "total_trades": s["total_trades"],
        "win_rate_pct": s["win_rate_pct"],
        "strategy_returns": strat_returns,
        "elapsed_sec": round(elapsed, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Chart generation
# ═══════════════════════════════════════════════════════════════════════════════

def _make_chart(param: str, results: List[dict], baseline_val,
                param_labels: dict, output_dir: str):
    """Generate a Return% vs parameter value chart."""
    values = [r["value"] for r in results]
    returns = [r["total_return_pct"] for r in results]

    # Re-sort by value for a clean line
    sorted_pairs = sorted(zip(values, returns))
    values_sorted = [p[0] for p in sorted_pairs]
    returns_sorted = [p[1] for p in sorted_pairs]

    fig, ax = plt.subplots(figsize=(10, 5.5))

    # Line + scatter
    ax.plot(values_sorted, returns_sorted, color="#58a6ff", linewidth=2, marker="o",
            markersize=8, markerfacecolor="#58a6ff", markeredgecolor="white", markeredgewidth=1.2)

    # Baseline marker
    baseline_ret = None
    for v, r in zip(values, returns):
        if v == baseline_val:
            baseline_ret = r
            break
    if baseline_ret is not None:
        ax.axvline(x=baseline_val, color="#f85149", linestyle="--", linewidth=1.5,
                   alpha=0.7, label=f"Aggressive default ({baseline_val})")
        ax.scatter([baseline_val], [baseline_ret], color="#f85149", s=120, zorder=5,
                   edgecolors="white", linewidth=1.2)

    # Best value marker
    best_idx = returns_sorted.index(max(returns_sorted))
    best_val = values_sorted[best_idx]
    best_ret = returns_sorted[best_idx]
    ax.scatter([best_val], [best_ret], color="#3fb950", s=150, zorder=5,
               edgecolors="white", linewidth=1.5, label=f"Best ({best_val} → {best_ret:+.2f}%)")

    ax.set_xlabel(param_labels.get(param, param), fontsize=12)
    ax.set_ylabel("Total Return (%)", fontsize=12)
    ax.set_title(f"Return vs {param_labels.get(param, param)}", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10, loc="best")
    ax.grid(True, alpha=0.25)
    ax.axhline(y=0, color="#8b949e", linewidth=0.8, alpha=0.5)

    # Dark theme
    fig.patch.set_facecolor("#0f1117")
    ax.set_facecolor("#0f1117")
    ax.tick_params(colors="#e1e4e8")
    ax.xaxis.label.set_color("#e1e4e8")
    ax.yaxis.label.set_color("#e1e4e8")
    ax.title.set_color("#e1e4e8")
    ax.spines["bottom"].set_color("#30363d")
    ax.spines["left"].set_color("#30363d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    path = os.path.join(output_dir, f"chart_{param}.png")
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  📈 Chart saved: {path}")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline steps (called by main)
# ═══════════════════════════════════════════════════════════════════════════════

def _print_header(config: GridSearchConfig) -> None:
    """Print the banner, baseline info, and start time."""
    print("=" * 72)
    print("  GRID SEARCH — Hyperparameter Optimization")
    print(f"  Baseline: config/aggressive.json")
    print(f"  Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)


def _load_or_fetch_data(config: GridSearchConfig) -> pd.DataFrame:
    """Load cached market data or download it fresh via v8 chart API."""
    print("\n⏳ Step 1/3: Loading market data...")
    if os.path.exists(config.cache_path):
        print(f"  Loading cached data from {config.cache_path}")
        df = pd.read_csv(config.cache_path)
        df["Date"] = pd.to_datetime(df["Date"])
        print(f"  Loaded {len(df)} rows, {df['Ticker'].nunique()} tickers")
        return df

    UNIVERSE = "nasdaq100"
    tickers = get_tickers(UNIVERSE)
    print(f"  Universe: {UNIVERSE.upper()} ({len(tickers)} tickers)")
    lookback = 30 + config.baseline["bt_days"] + 20  # max_window + bt_days + buffer
    print(f"  Lookback: {lookback} calendar days")
    print(f"  Downloading via v8 chart API (~{len(tickers) * 0.5:.0f}s)...")
    df = fetch_v8_data(tickers, lookback_days=lookback)
    if df is None or df.empty:
        print("ERROR: Could not fetch stock data.", file=sys.stderr)
        sys.exit(1)
    df.to_csv(config.cache_path, index=False)
    print(f"  Cached to {config.cache_path}")
    return df


def _run_all_sweeps(df: pd.DataFrame, config: GridSearchConfig) -> Dict[str, list]:
    """Run all parameter sweeps, save incremental results, return all_results."""
    total_runs = sum(len(vals) for _, vals in config.sweeps)
    print(f"\n⏳ Step 2/3: Running {total_runs} backtests...")
    print(f"  (each with 365d of data, ~550 tickers, intraday exec)")

    all_results: Dict[str, list] = {}
    run_count = 0

    for param, values in config.sweeps:
        print(f"\n  ── Sweeping {param} ({len(values)} values) ──")
        param_results = []
        for val in values:
            run_count += 1
            slug = _param_slug(param, val)
            result = _run_one(param, val, df, config.baseline)
            param_results.append(result)
            print(f"    [{run_count}/{total_runs}] {slug:12s} → "
                  f"return={result['total_return_pct']:+.2f}%  "
                  f"equity=${result['final_equity']:,.0f}  "
                  f"trades={result['total_trades']}  "
                  f"win={result['win_rate_pct']:.0f}%  "
                  f"({result['elapsed_sec']}s)")

        all_results[param] = param_results

        # Save incremental results
        with open(config.results_path, "w") as f:
            json.dump({"baseline": config.baseline, "results": all_results,
                       "generated_at": datetime.now().isoformat()}, f, indent=2)

    return all_results


def _analyze_and_report(all_results: dict, config: GridSearchConfig) -> dict:
    """Generate charts, terminal summary, markdown report, and optimized config."""
    print(f"\n⏳ Step 3/3: Generating charts and report...\n")

    best_config = dict(config.baseline)
    report_lines = []
    report_lines.append("# Grid Search Report — Hyperparameter Optimization\n")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append(f"Baseline: `config/aggressive.json` (universe=both, days=365, exec=intraday)\n")
    report_lines.append("---\n")

    for param, values in config.sweeps:
        results = all_results[param]
        baseline_val = config.baseline[param]
        _make_chart(param, results, baseline_val, config.param_labels, config.output_dir)

        # Find best
        best = max(results, key=lambda r: r["total_return_pct"])
        baseline_result = next((r for r in results if r["value"] == baseline_val), None)

        report_lines.append(f"## {config.param_labels.get(param, param)}\n")
        report_lines.append(f"| | Value | Return % | Equity | Trades | Win Rate |")
        report_lines.append(f"|---|---|---|---|---|---|")

        for r in sorted(results, key=lambda x: x["value"]):
            flag = ""
            if r["value"] == best["value"]:
                flag = " ⬅ BEST"
            elif r["value"] == baseline_val:
                flag = " (baseline)"
            report_lines.append(
                f"|{flag}| {r['value']} | {r['total_return_pct']:+.2f}% | "
                f"${r['final_equity']:,.0f} | {r['total_trades']} | "
                f"{r['win_rate_pct']:.1f}% |"
            )

        report_lines.append("")
        if baseline_result:
            delta = best["total_return_pct"] - baseline_result["total_return_pct"]
            report_lines.append(
                f"**Best:** `{param} = {best['value']}` → {best['total_return_pct']:+.2f}% "
                f"(Δ{delta:+.2f}% vs baseline {baseline_val})\n"
            )
        best_config[param] = best["value"]

    # ── Terminal summary ──────────────────────────────────────────────────
    print("=" * 72)
    print("  RESULTS SUMMARY")
    print("=" * 72)
    print(f"  {'Parameter':<22} {'Best Value':>10}  {'Return %':>10}  {'vs Baseline':>12}")
    print(f"  {'─'*22} {'─'*10} {'─'*10} {'─'*12}")

    for param, values in config.sweeps:
        results = all_results[param]
        best = max(results, key=lambda r: r["total_return_pct"])
        bl = next((r for r in results if r["value"] == config.baseline[param]), None)
        bl_ret = bl["total_return_pct"] if bl else 0
        delta = best["total_return_pct"] - bl_ret
        print(f"  {config.param_labels.get(param, param):<22} {best['value']:>10}  "
              f"{best['total_return_pct']:>+9.2f}%  {delta:>+11.2f}%")

    print()
    print(f"  Combined best config saved to: {config.results_path}")
    print(f"  Charts saved to: {config.output_dir}/chart_*.png")

    # ── Save optimized config ─────────────────────────────────────────────
    print()
    print("  ═══════════════════════════════════════════════════════════")
    print("  RECOMMENDED CONFIG (save as config/optimized.json)")
    print("  ═══════════════════════════════════════════════════════════")

    optimized = {
        "_description": "Optimized config from grid search hyperparameter sweep",
        "universe": best_config["universe"],
        "backtest": True,
        "bt_days": best_config["bt_days"],
        "bt_capital": best_config["bt_capital"],
        "bt_tp": best_config["bt_tp"],
        "bt_sl": best_config["bt_sl"],
        "bt_position_pct": best_config["bt_position_pct"],
        "bt_min_vol": best_config["bt_min_vol"],
        "bt_max_hold": best_config["bt_max_hold"],
        "bt_exec": best_config["bt_exec"],
        "html": True,
    }
    print(json.dumps(optimized, indent=4))

    config_path = os.path.join(PROJ_ROOT, "config", "optimized.json")
    with open(config_path, "w") as f:
        json.dump(optimized, f, indent=4)
    print(f"\n  ✅ Saved to: {config_path}")

    # ── Write markdown report ─────────────────────────────────────────────
    report_path = os.path.join(config.output_dir, "grid_search_report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"  ✅ Full report: {report_path}")

    return best_config


def _validate_optimized(df: pd.DataFrame, baseline: dict, best_config: dict) -> None:
    """Run baseline vs optimized config side-by-side and print comparison."""
    print("\n  ═══════════════════════════════════════════════════════════")
    print("  VALIDATION: Running combined best config...")
    print("  ═══════════════════════════════════════════════════════════")

    windows = {k: v for k, v in WINDOWS.items() if v <= 30}

    # Re-run baseline for side-by-side comparison
    print("  Running baseline (aggressive.json)...")
    bl_result = run_backtest(
        df, initial_capital=baseline["bt_capital"],
        take_profit_pct=baseline["bt_tp"], stop_loss_pct=baseline["bt_sl"],
        backtest_days=baseline["bt_days"], position_size_pct=baseline["bt_position_pct"],
        min_dollar_volume_m=baseline["bt_min_vol"], max_hold_days=baseline["bt_max_hold"],
        exec_mode=baseline["bt_exec"], windows=windows,
    )

    print("  Running optimized config...")
    opt_result = run_backtest(
        df, initial_capital=best_config["bt_capital"],
        take_profit_pct=best_config["bt_tp"], stop_loss_pct=best_config["bt_sl"],
        backtest_days=best_config["bt_days"], position_size_pct=best_config["bt_position_pct"],
        min_dollar_volume_m=best_config["bt_min_vol"], max_hold_days=best_config["bt_max_hold"],
        exec_mode=best_config["bt_exec"], windows=windows,
    )

    print()
    print(f"  {'Metric':<25} {'Baseline':>12} {'Optimized':>12} {'Delta':>12}")
    print(f"  {'─'*25} {'─'*12} {'─'*12} {'─'*12}")
    bl_s = bl_result["summary"]
    opt_s = opt_result["summary"]
    for metric, key in [
        ("Final Equity", "final_equity"),
        ("Total Return %", "total_return_pct"),
        ("Win Rate %", "win_rate_pct"),
        ("Total Trades", "total_trades"),
    ]:
        bl_v = bl_s[key]
        opt_v = opt_s[key]
        delta_v = opt_v - bl_v
        if isinstance(bl_v, float):
            print(f"  {metric:<25} {bl_v:>+11.2f} {opt_v:>+11.2f} {delta_v:>+11.2f}")
        else:
            print(f"  {metric:<25} {bl_v:>12} {opt_v:>12} {delta_v:>+12}")

    print()
    print("  ✅ Done! Check results/grid_search_report.md and results/chart_*.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    auto_detect_proxy()
    config = CONFIG
    os.makedirs(config.output_dir, exist_ok=True)

    _print_header(config)
    df = _load_or_fetch_data(config)
    all_results = _run_all_sweeps(df, config)
    best_config = _analyze_and_report(all_results, config)
    _validate_optimized(df, config.baseline, best_config)


if __name__ == "__main__":
    main()
