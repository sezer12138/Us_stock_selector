"""
Pretty-printing for stock rankings.

Outputs formatted tables to the terminal using `tabulate`, and can
export results to CSV or a self-contained HTML report.
"""

import csv
import os
from datetime import datetime
from typing import Dict

from tabulate import tabulate

from .screener import WindowResult, StockRank


def print_rankings(results: Dict[str, WindowResult], top_n: int = 10) -> None:
    """Print all window rankings as formatted terminal tables."""
    print()
    print("=" * 78)
    print(f"  US STOCK SELECTOR — Top {top_n} Rankings")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)

    for label in ["3d", "7d", "14d", "21d", "30d"]:
        wr = results.get(label)
        if wr is None:
            continue

        num_days = label.rstrip("d")
        header = f"  {label.upper()} WINDOW (last {num_days} calendar days)"
        print(f"\n{'─' * 78}")
        print(header)
        print(f"{'─' * 78}")

        print(f"\n  🟢 Top {top_n} by Price Increase %")
        _print_rank_table(wr.top_by_gain, metric_label="Gain %")

        print(f"\n  📊 Top {top_n} by Average Volume")
        _print_rank_table(wr.top_by_volume, metric_label="Avg Volume")

    print(f"\n{'─' * 78}")
    print()


def _print_rank_table(ranks, metric_label: str) -> None:
    if not ranks:
        print("    (no data)")
        return

    rows = []
    for i, r in enumerate(ranks, 1):
        val = f"{r.metric_value:,.2f}"
        rows.append([i, r.ticker, val, r.extra_info])

    headers = ["#", "Ticker", metric_label, "Extra"]
    print(tabulate(rows, headers=headers, tablefmt="simple", numalign="right", stralign="left"))


def export_csv(results: Dict[str, WindowResult], output_dir: str = ".") -> str:
    """Export all rankings into one CSV file. Returns the file path."""
    filename = f"stock_rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, filename)

    rows = []
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        wr = results.get(label)
        if wr is None:
            continue
        for rank_type, rank_list in [("Gain", wr.top_by_gain), ("Volume", wr.top_by_volume)]:
            for i, r in enumerate(rank_list, 1):
                rows.append({
                    "Window": label,
                    "RankType": rank_type,
                    "Rank": i,
                    "Ticker": r.ticker,
                    "Value": r.metric_value,
                    "Extra": r.extra_info,
                })

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Window", "RankType", "Rank", "Ticker", "Value", "Extra"])
        writer.writeheader()
        writer.writerows(rows)

    return filepath


# ── HTML Report Generation ────────────────────────────────────────────────

def generate_html(results: Dict[str, WindowResult], top_n: int = 10, output_dir: str = ".") -> str:
    """
    Generate a self-contained HTML report and write it to disk.
    Returns the file path.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"stock_rankings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    sections_html = ""
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        wr = results.get(label)
        if wr is None:
            continue
        num_days = label.rstrip("d")
        sections_html += f"""
        <div class="window-section">
            <h2>{label.upper()} Window <span class="subtitle">last {num_days} calendar days</span></h2>
            <div class="two-col">
                <div class="col">
                    <h3>🟢 Top {top_n} by Price Increase %</h3>
                    {_html_table(wr.top_by_gain, "Gain %")}
                </div>
                <div class="col">
                    <h3>📊 Top {top_n} by Average Volume</h3>
                    {_html_table(wr.top_by_volume, "Avg Vol")}
                </div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>US Stock Selector — Top {top_n} Rankings</title>
<style>
  :root {{ --bg: #0f1117; --card: #1a1d2e; --text: #e1e4e8; --muted: #8b949e;
          --green: #3fb950; --red: #f85149; --accent: #58a6ff; --border: #30363d; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         padding:24px 16px; max-width:1100px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin-bottom:4px; }}
  .muted {{ color:var(--muted); font-size:0.9rem; margin-bottom:24px; }}
  .window-section {{ background:var(--card); border:1px solid var(--border); border-radius:10px;
                     padding:20px 24px; margin-bottom:20px; }}
  .window-section h2 {{ font-size:1.2rem; margin-bottom:16px; }}
  .subtitle {{ font-weight:400; color:var(--muted); font-size:0.95rem; }}
  .two-col {{ display:flex; gap:24px; flex-wrap:wrap; }}
  .col {{ flex:1; min-width:300px; }}
  .col h3 {{ font-size:1rem; margin-bottom:8px; color:var(--accent); }}
  table {{ width:100%; border-collapse:collapse; font-size:0.9rem; }}
  th {{ text-align:left; color:var(--muted); font-weight:600; padding:6px 10px;
       border-bottom:1px solid var(--border); }}
  td {{ padding:7px 10px; border-bottom:1px solid var(--border); }}
  tr:hover td {{ background:rgba(88,166,255,0.05); }}
  .pos {{ color:var(--green); }} .neg {{ color:var(--red); }}
  .ticker {{ font-weight:700; color:var(--accent); }}
  .extra {{ color:var(--muted); font-size:0.82rem; }}
  .rank {{ color:var(--muted); width:30px; text-align:right; padding-right:12px !important; }}
  footer {{ text-align:center; color:var(--muted); font-size:0.8rem; margin-top:32px; }}
</style>
</head>
<body>
<h1>📈 US Stock Selector</h1>
<p class="muted">Top {top_n} stocks ranked by price increase % and average trading volume.
   Generated: {now_str} · Data: Yahoo Finance (15-min delayed)</p>
{sections_html}
<footer>US Stock Selector · {now_str}</footer>
</body>
</html>"""

    with open(filepath, "w") as f:
        f.write(html)

    return filepath


# ── Backtest Result Display ─────────────────────────────────────────────

def print_backtest_results(bt_results: Dict) -> None:
    """Pretty-print backtest summary + per-strategy trade logs."""
    summary = bt_results["summary"]
    config = bt_results["config"]
    strategies = bt_results["strategies"]

    print()
    print("=" * 78)
    print("  📊 BACKTEST RESULTS")
    print("=" * 78)
    print(f"  Period          : {summary['backtest_start']} → {summary['backtest_end']}")
    print(f"  Trading days    : {summary['trading_days']}")
    print(f"  Initial capital : ${summary['initial_capital']:,.0f}")
    print(f"  Final equity    : ${summary['final_equity']:,.2f}")
    color = "🟢" if summary["total_return_pct"] >= 0 else "🔴"
    print(f"  Total return    : {color} {summary['total_return_pct']:+.2f}%")
    print(f"  Total trades    : {summary['total_trades']}")
    print(f"  Win rate        : {summary['win_rate_pct']:.1f}%")
    print(f"  Rules           : buy top-1 gainer, sell at +{config['take_profit_pct']}% / -{config['stop_loss_pct']}%")
    print()

    # ── Per-strategy summary table ──
    rows = []
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        s = strategies.get(label)
        if s is None:
            continue
        rows.append([
            label.upper(),
            f"${s['final_equity']:,.2f}",
            f"{s['return_pct']:+.2f}%",
            s["total_trades"],
            s["take_profits"],
            s["stop_losses"],
            f"{s['avg_return_pct']:+.2f}%",
            f"{s['best_trade_pct']:+.2f}%",
            f"{s['worst_trade_pct']:+.2f}%",
        ])

    headers = ["Window", "Final Equity", "Return", "Trades", "Wins", "Losses",
               "Avg Return", "Best", "Worst"]
    print(tabulate(rows, headers=headers, tablefmt="simple", numalign="right", stralign="left"))
    print()

    # ── Trade log per strategy ──
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        s = strategies.get(label)
        if s is None or not s["trades"]:
            continue
        print(f"─" * 78)
        print(f"  {label.upper()} Strategy — Trade Log")
        print(f"─" * 78)
        trade_rows = []
        for i, t in enumerate(s["trades"], 1):
            entry_d = t.entry_date.strftime("%m/%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)[:10]
            exit_d = t.exit_date.strftime("%m/%d") if t.exit_date and hasattr(t.exit_date, 'strftime') else (str(t.exit_date)[:10] if t.exit_date else "—")
            pnl_str = f"{t.pnl_pct:+.2f}%" if t.pnl_pct is not None else "—"
            icon = {"take_profit": "🟢", "stop_loss": "🔴", "end_of_period": "⚪"}.get(t.exit_reason, "")
            trade_rows.append([i, t.ticker, entry_d, f"${t.entry_price:,.2f}",
                              exit_d, f"${t.exit_price:,.2f}" if t.exit_price else "—",
                              pnl_str, f"{icon} {t.exit_reason}"])
        print(tabulate(trade_rows,
                       headers=["#", "Ticker", "Entry", "Price", "Exit", "Price", "P&L", "Reason"],
                       tablefmt="simple", numalign="right", stralign="left"))
        print()

    print("─" * 78)


def print_backtest_html(bt_results: Dict, output_dir: str = ".") -> str:
    """Generate a self-contained HTML backtest report. Returns file path."""
    from datetime import datetime as dt
    now_str = dt.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"backtest_report_{dt.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(output_dir, filename)

    summary = bt_results["summary"]
    config = bt_results["config"]
    strategies = bt_results["strategies"]

    # Summary cards
    ret_color = "#3fb950" if summary["total_return_pct"] >= 0 else "#f85149"
    cards = f"""
    <div class="summary-cards">
        <div class="card"><div class="label">Initial Capital</div><div class="val">${summary['initial_capital']:,.0f}</div></div>
        <div class="card"><div class="label">Final Equity</div><div class="val">${summary['final_equity']:,.2f}</div></div>
        <div class="card"><div class="label">Total Return</div><div class="val" style="color:{ret_color}">{summary['total_return_pct']:+.2f}%</div></div>
        <div class="card"><div class="label">Total Trades</div><div class="val">{summary['total_trades']}</div></div>
        <div class="card"><div class="label">Win Rate</div><div class="val">{summary['win_rate_pct']:.1f}%</div></div>
    </div>"""

    # Strategy summary table
    strat_rows = ""
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        s = strategies.get(label)
        if s is None:
            continue
        ret_cls = "pos" if s["return_pct"] >= 0 else "neg"
        strat_rows += f"""<tr>
            <td class="ticker">{label.upper()}</td>
            <td>${s['final_equity']:,.2f}</td>
            <td class="{ret_cls}">{s['return_pct']:+.2f}%</td>
            <td>{s['total_trades']}</td><td>{s['take_profits']}</td><td>{s['stop_losses']}</td>
            <td class="{"pos" if s['avg_return_pct'] >= 0 else "neg"}">{s['avg_return_pct']:+.2f}%</td>
            <td class="pos">{s['best_trade_pct']:+.2f}%</td>
            <td class="neg">{s['worst_trade_pct']:+.2f}%</td>
        </tr>"""

    # Trade logs
    trade_sections = ""
    for label in ["3d", "7d", "14d", "21d", "30d"]:
        s = strategies.get(label)
        if s is None or not s["trades"]:
            continue
        trows = ""
        for i, t in enumerate(s["trades"], 1):
            entry_d = t.entry_date.strftime("%m/%d") if hasattr(t.entry_date, 'strftime') else str(t.entry_date)[:10]
            exit_d = t.exit_date.strftime("%m/%d") if t.exit_date and hasattr(t.exit_date, 'strftime') else "—"
            pnl_cls = "pos" if (t.pnl_pct or 0) >= 0 else "neg"
            icon = {"take_profit": "🟢", "stop_loss": "🔴", "end_of_period": "⚪️"}.get(t.exit_reason, "")
            trows += f"""<tr>
                <td class="rank">{i}</td><td class="ticker">{t.ticker}</td>
                <td>{entry_d}</td><td>${t.entry_price:,.2f}</td>
                <td>{exit_d}</td><td>${t.exit_price:,.2f}</td>
                <td class="{pnl_cls}">{t.pnl_pct:+.2f}%</td>
                <td>{icon} {t.exit_reason}</td>
            </tr>"""
        trade_sections += f"""<div class="window-section">
            <h2>{label.upper()} Strategy <span class="subtitle">Trade Log</span></h2>
            <table><thead><tr><th>#</th><th>Ticker</th><th>Entry</th><th>Price</th><th>Exit</th><th>Price</th><th>P&L</th><th>Reason</th></tr></thead>
            <tbody>{trows}</tbody></table></div>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtest Report — US Stock Selector</title>
<style>
  :root {{ --bg:#0f1117; --card:#1a1d2e; --text:#e1e4e8; --muted:#8b949e;
          --green:#3fb950; --red:#f85149; --accent:#58a6ff; --border:#30363d; }}
  * {{ box-sizing:border-box;margin:0;padding:0; }}
  body {{ background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          padding:24px 16px;max-width:1100px;margin:0 auto; }}
  h1 {{ font-size:1.6rem;margin-bottom:4px; }}
  .muted {{ color:var(--muted);font-size:0.9rem;margin-bottom:20px; }}
  .summary-cards {{ display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px; }}
  .card {{ background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px 20px;min-width:140px;flex:1; }}
  .card .label {{ color:var(--muted);font-size:0.8rem;margin-bottom:4px; }}
  .card .val {{ font-size:1.3rem;font-weight:700; }}
  .window-section {{ background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px 24px;margin-bottom:16px; }}
  .window-section h2 {{ font-size:1.1rem;margin-bottom:12px; }}
  .subtitle {{ font-weight:400;color:var(--muted);font-size:0.9rem; }}
  table {{ width:100%;border-collapse:collapse;font-size:0.88rem;margin-bottom:4px; }}
  th {{ text-align:left;color:var(--muted);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--border); }}
  td {{ padding:7px 10px;border-bottom:1px solid var(--border); }}
  tr:hover td {{ background:rgba(88,166,255,0.05); }}
  .pos {{ color:var(--green); }} .neg {{ color:var(--red); }}
  .ticker {{ font-weight:700;color:var(--accent); }}
  .rank {{ color:var(--muted);width:30px;text-align:right;padding-right:12px!important; }}
  footer {{ text-align:center;color:var(--muted);font-size:0.8rem;margin-top:32px; }}
</style></head><body>
<h1>📊 Backtest Report</h1>
<p class="muted">{summary['backtest_start']} → {summary['backtest_end']} · {summary['trading_days']} trading days
   · Rules: buy top-1 gainer, sell +{config['take_profit_pct']}% / -{config['stop_loss_pct']}% · Generated: {now_str}</p>
{cards}
<div class="window-section"><h2>Strategy Summary</h2>
<table><thead><tr><th>Window</th><th>Final Equity</th><th>Return</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Avg Return</th><th>Best</th><th>Worst</th></tr></thead>
<tbody>{strat_rows}</tbody></table></div>
{trade_sections}
<footer>US Stock Selector · Backtest Report · {now_str}</footer>
</body></html>"""

    with open(filepath, "w") as f:
        f.write(html)
    return filepath


def _html_table(ranks: list[StockRank], metric_label: str) -> str:
    if not ranks:
        return '<p style="color:var(--muted)">(no data)</p>'

    rows = ""
    for i, r in enumerate(ranks, 1):
        val = r.metric_value
        cls = "pos" if val >= 0 else "neg"
        rows += f"""<tr>
            <td class="rank">{i}</td>
            <td class="ticker">{r.ticker}</td>
            <td class="{cls}">{val:+,.2f}</td>
            <td class="extra">{r.extra_info}</td>
        </tr>"""

    return f"""<table>
        <thead><tr><th>#</th><th>Ticker</th><th>{metric_label}</th><th>Extra</th></tr></thead>
        <tbody>{rows}</tbody></table>"""
