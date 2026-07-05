"""
Backtesting engine for momentum-based stock selection strategies.

Simulates paper trading over a historical period: each day, buys the
top-1 price-gainer over a given lookback window, and exits when the
position hits +10% take-profit or -5% stop-loss.

Supports five independent window strategies: 3d, 7d, 14d, 21d, 30d.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .screener import WINDOWS

# ── Suppress noise ────────────────────────────────────────────────────────
logging.getLogger("yfinance").setLevel(logging.ERROR)


# ── Data structures ────────────────────────────────────────────────────────

@dataclass
class Trade:
    strategy: str
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: str = "open"          # take_profit | stop_loss | end_of_period | open


@dataclass
class StrategyState:
    """Mutable state for one window-strategy during the backtest walk-forward."""
    cash: float
    position_ticker: Optional[str] = None
    entry_price: float = 0.0
    entry_date: Optional[pd.Timestamp] = None
    shares: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[pd.Timestamp, float]] = field(default_factory=list)


# ── Core helpers ───────────────────────────────────────────────────────────

def _top_gainer(
    df: pd.DataFrame,
    today: pd.Timestamp,
    window_days: int,
) -> Optional[str]:
    """
    Return the ticker with the highest price-increase % over the last
    `window_days` calendar days, looking back from `today`.  Uses only
    data available on or before `today` (no look-ahead).
    """
    cutoff = today - pd.Timedelta(days=window_days)
    window_data = df[(df["Date"] >= cutoff) & (df["Date"] <= today)]

    if window_data.empty:
        return None

    gains = {}
    for ticker, group in window_data.groupby("Ticker"):
        # Need at least 2 data points in the window
        if len(group) < 2:
            continue
        earliest = group.loc[group["Date"].idxmin()]
        latest = group.loc[group["Date"].idxmax()]
        if earliest["Close"] <= 0:
            continue
        pct = (latest["Close"] - earliest["Close"]) / earliest["Close"] * 100.0
        gains[ticker] = pct

    if not gains:
        return None
    return max(gains, key=gains.get)


def _get_close(df: pd.DataFrame, ticker: str, date: pd.Timestamp) -> Optional[float]:
    """Return the closing price of `ticker` on `date`, or None."""
    rows = df[(df["Ticker"] == ticker) & (df["Date"] == date)]
    if rows.empty:
        return None
    return float(rows["Close"].iloc[0])


# ── Main backtest loop ─────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    take_profit_pct: float = 10.0,
    stop_loss_pct: float = 5.0,
    backtest_days: int = 60,
    windows: Optional[Dict[str, int]] = None,
) -> Dict:
    """
    Run a multi-strategy momentum backtest.

    Parameters
    ----------
    df : pd.DataFrame
        Historical data with columns Date, Ticker, Close.  Must span
        (max_window + backtest_days + buffer) calendar days.
    initial_capital : float
        Total cash allocated — split equally across window strategies.
    take_profit_pct : float
        Exit when unrealised gain ≥ this percentage.
    stop_loss_pct : float
        Exit when unrealised loss ≤ -this percentage.
    backtest_days : int
        Number of calendar days to run the backtest over.
    windows : dict | None
        Window label → calendar days.  Defaults to 3d/7d/14d/21d/30d.

    Returns
    -------
    dict with keys:
        strategies  — per-window strategy results (trades, equity curve, final equity)
        summary     — combined P&L across all strategies
        config      — parameters used
    """
    if windows is None:
        windows = WINDOWS

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    if df["Date"].dt.tz is not None:
        df["Date"] = df["Date"].dt.tz_localize(None)

    # Determine backtest date range
    all_dates = sorted(df["Date"].unique())
    today = df["Date"].max()
    backtest_start = today - pd.Timedelta(days=backtest_days)

    # Filter to dates in the backtest window
    trading_days = [d for d in all_dates if d >= backtest_start]
    if len(trading_days) < 5:
        raise ValueError(f"Not enough trading days in backtest window (found {len(trading_days)})")

    # Per-strategy capital
    capital_per_strat = initial_capital / len(windows)

    # Initialise state for each strategy
    states: Dict[str, StrategyState] = {}
    for label in windows:
        states[label] = StrategyState(cash=capital_per_strat)

    # ── Walk forward day by day ─────────────────────────────────────────
    for day in trading_days:
        for label, window_days in windows.items():
            st = states[label]

            # --- 1. Check existing position P&L ---
            if st.position_ticker is not None:
                cur_price = _get_close(df, st.position_ticker, day)
                if cur_price is not None and st.entry_price > 0:
                    pnl_pct = (cur_price - st.entry_price) / st.entry_price * 100.0

                    should_sell = False
                    reason = "open"
                    if pnl_pct >= take_profit_pct:
                        should_sell = True
                        reason = "take_profit"
                    elif pnl_pct <= -stop_loss_pct:
                        should_sell = True
                        reason = "stop_loss"

                    if should_sell:
                        exit_value = st.shares * cur_price
                        trade = Trade(
                            strategy=label,
                            ticker=st.position_ticker,
                            entry_date=st.entry_date,       # type: ignore[arg-type]
                            entry_price=st.entry_price,
                            exit_date=day,
                            exit_price=cur_price,
                            pnl_pct=round(pnl_pct, 2),
                            exit_reason=reason,
                        )
                        st.trades.append(trade)
                        st.cash = exit_value
                        st.position_ticker = None
                        st.entry_price = 0.0
                        st.entry_date = None
                        st.shares = 0.0

            # --- 2. If no position, try to enter ---
            if st.position_ticker is None and st.cash > 0:
                top = _top_gainer(df, day, window_days)
                if top is not None:
                    price = _get_close(df, top, day)
                    if price is not None and price > 0:
                        st.shares = st.cash / price
                        st.position_ticker = top
                        st.entry_price = price
                        st.entry_date = day
                        st.cash = 0.0

            # --- 3. Record equity ---
            if st.position_ticker is not None:
                mark_price = _get_close(df, st.position_ticker, day)
                equity = st.shares * mark_price if mark_price else st.cash
            else:
                equity = st.cash
            st.equity_curve.append((day, equity))

    # ── Close all open positions at last day ────────────────────────────
    last_day = trading_days[-1]
    for label in windows:
        st = states[label]
        if st.position_ticker is not None:
            cur_price = _get_close(df, st.position_ticker, last_day)
            if cur_price is not None and st.entry_price > 0:
                pnl_pct = (cur_price - st.entry_price) / st.entry_price * 100.0
            else:
                pnl_pct = 0.0
                cur_price = st.entry_price
            trade = Trade(
                strategy=label,
                ticker=st.position_ticker,
                entry_date=st.entry_date,       # type: ignore[arg-type]
                entry_price=st.entry_price,
                exit_date=last_day,
                exit_price=cur_price,
                pnl_pct=round(pnl_pct, 2),
                exit_reason="end_of_period",
            )
            st.trades.append(trade)
            st.cash = st.shares * cur_price
            st.position_ticker = None
            st.entry_price = 0.0
            st.entry_date = None
            st.shares = 0.0

    # ── Build results ───────────────────────────────────────────────────
    strategy_results = {}
    total_final = 0.0
    total_trades = 0
    total_winners = 0

    for label in windows:
        st = states[label]
        final_eq = st.cash if st.cash > 0 else (st.equity_curve[-1][1] if st.equity_curve else capital_per_strat)
        total_final += final_eq

        wins = [t for t in st.trades if t.exit_reason == "take_profit"]
        losses = [t for t in st.trades if t.exit_reason == "stop_loss"]
        eop = [t for t in st.trades if t.exit_reason == "end_of_period"]

        returns = [t.pnl_pct for t in st.trades if t.pnl_pct is not None]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        best_trade = max(returns) if returns else 0.0
        worst_trade = min(returns) if returns else 0.0

        total_trades += len(st.trades)
        total_winners += len([t for t in st.trades if t.pnl_pct is not None and t.pnl_pct > 0])

        strategy_results[label] = {
            "final_equity": round(final_eq, 2),
            "return_pct": round((final_eq - capital_per_strat) / capital_per_strat * 100, 2),
            "total_trades": len(st.trades),
            "take_profits": len(wins),
            "stop_losses": len(losses),
            "end_of_period": len(eop),
            "avg_return_pct": round(avg_return, 2),
            "best_trade_pct": round(best_trade, 2),
            "worst_trade_pct": round(worst_trade, 2),
            "trades": st.trades,
            "equity_curve": st.equity_curve,
        }

    overall_return = round((total_final - initial_capital) / initial_capital * 100, 2)
    win_rate = round(total_winners / total_trades * 100, 2) if total_trades else 0.0

    return {
        "strategies": strategy_results,
        "summary": {
            "initial_capital": initial_capital,
            "final_equity": round(total_final, 2),
            "total_return_pct": overall_return,
            "total_trades": total_trades,
            "win_rate_pct": win_rate,
            "backtest_start": str(backtest_start.date()),
            "backtest_end": str(last_day.date()),
            "trading_days": len(trading_days),
        },
        "config": {
            "take_profit_pct": take_profit_pct,
            "stop_loss_pct": stop_loss_pct,
            "backtest_days": backtest_days,
            "windows": windows,
        },
    }
