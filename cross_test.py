#!/usr/bin/env python3
"""Quick cross-combination test to find the true optimal hyperparameter combo."""
import os, sys, time
sys.path.insert(0, '.')
import pandas as pd
from stock_selector.backtest import run_backtest
from stock_selector.screener import WINDOWS

df = pd.read_csv('results/_grid_search_data.csv')
df['Date'] = pd.to_datetime(df['Date'])
print(f'Loaded {len(df)} rows, {df["Ticker"].nunique()} tickers\n')

combos = [
    ("Baseline (aggressive)",  50, 20, 100, 10, 100),
    ("Best TP + base SL",      80, 20, 100, 10, 100),
    ("Best SL + base TP",      50,  8, 100, 10, 100),
    ("High TP + wide SL",      80, 40, 100,  0, 100),
    ("TP30 + SL30",            30, 30, 100, 10, 100),
    ("TP30 + SL8",             30,  8, 100, 10, 100),
    ("TP70 + SL40",            70, 40, 100,  0, 100),
    ("TP60 + SL25",            60, 25, 100,  0, 100),
    ("TP80 + SL25",            80, 25, 100,  0, 100),
    ("TP80 + SL15",            80, 15, 100,  0, 100),
]

header = f"{'Config':<28} {'Return%':>9} {'Equity':>11} {'Trades':>7} {'Win%':>7} | {'3d':>8} {'7d':>8} {'14d':>8} {'21d':>8} {'30d':>8}"
print(header)
print("-" * len(header))

best_name, best_ret = "", -float("inf")
for name, tp, sl, pos, vol, hold in combos:
    t0 = time.time()
    result = run_backtest(
        df, initial_capital=50000, take_profit_pct=tp, stop_loss_pct=sl,
        backtest_days=365, position_size_pct=pos, min_dollar_volume_m=vol,
        max_hold_days=hold, exec_mode="intraday",
        windows={k: v for k, v in WINDOWS.items() if v <= 30},
    )
    s = result["summary"]
    strats = result["strategies"]
    s3 = f"{strats['3d']['return_pct']:+.1f}%"
    s7 = f"{strats['7d']['return_pct']:+.1f}%"
    s14 = f"{strats['14d']['return_pct']:+.1f}%"
    s21 = f"{strats['21d']['return_pct']:+.1f}%"
    s30 = f"{strats['30d']['return_pct']:+.1f}%"
    elapsed = time.time() - t0
    print(f"{name:<28} {s['total_return_pct']:>+8.2f}% ${s['final_equity']:>9,.0f} {s['total_trades']:>6} {s['win_rate_pct']:>5.1f}% | {s3:>8} {s7:>8} {s14:>8} {s21:>8} {s30:>8}  ({elapsed:.1f}s)")

    if s["total_return_pct"] > best_ret:
        best_ret = s["total_return_pct"]
        best_name = name

print(f"\n  ** Best: {best_name} → {best_ret:+.2f}% **")
print(f"\n  Recommended config to use:")
print(f"  python main.py --config config/aggressive.json \\")
# Find the best combo again
for name, tp, sl, pos, vol, hold in combos:
    if name == best_name:
        print(f"    --bt-tp {tp} --bt-sl {sl} --bt-position-pct {pos} --bt-min-vol {vol} --bt-max-hold {hold}")
        break
