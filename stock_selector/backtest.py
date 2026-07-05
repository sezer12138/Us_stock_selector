"""
Backtesting engine for momentum-based stock selection strategies.

Simulates paper trading over a historical period: each day, buys the
top-1 price-gainer over a given lookback window (filtered by minimum
daily dollar-volume for liquidity), and exits when the position hits
take-profit or stop-loss thresholds.

Each trade risks only a configurable percentage of available capital
(e.g. 20%), leaving the rest as cash reserve — realistic position sizing
rather than all-in bets.

Supports five independent window strategies: 3d, 7d, 14d, 21d, 30d.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .screener import WINDOWS

logging.getLogger("yfinance").setLevel(logging.ERROR)


# ── Data structures ────────────────────────────────────────────────────────

@dataclass
class Trade:
    strategy: str
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    capital_used: float          # how much cash was deployed for this trade
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: str = "open"
    # List of (date_str, close_price) for sparkline rendering
    price_path: List = field(default_factory=list)


@dataclass
class StrategyState:
    """Mutable state for one window-strategy during the walk-forward."""
    cash: float                   # total available buying power (invested + reserve)
    position_ticker: Optional[str] = None
    entry_price: float = 0.0
    entry_date: Optional[pd.Timestamp] = None
    shares: float = 0.0
    invested_amount: float = 0.0  # cash locked in current position
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[pd.Timestamp, float]] = field(default_factory=list)


# ── Core helpers ───────────────────────────────────────────────────────────

def _dollar_volume(
    df: pd.DataFrame,
    ticker: str,
    today: pd.Timestamp,
    window_days: int,
) -> Optional[float]:
    """Average daily dollar-volume (Close × Volume) for `ticker` over `window_days`."""
    cutoff = today - pd.Timedelta(days=window_days)
    mask = (df["Ticker"] == ticker) & (df["Date"] >= cutoff) & (df["Date"] <= today)
    recent = df.loc[mask]
    if len(recent) < 2:
        return None
    return float((recent["Close"] * recent["Volume"]).mean())


def _top_gainer(
    df: pd.DataFrame,
    today: pd.Timestamp,
    window_days: int,
    min_dollar_volume: float = 0.0,
) -> Optional[str]:
    """
    Return the ticker with the highest price-increase % over the last
    `window_days` calendar days, looking back from `today`.

    Stocks whose average daily dollar-volume falls below `min_dollar_volume`
    are excluded — ensuring picks are liquid enough to actually trade.

    Uses only data on or before `today` (no look-ahead).
    """
    cutoff = today - pd.Timedelta(days=window_days)
    window_data = df[(df["Date"] >= cutoff) & (df["Date"] <= today)]

    if window_data.empty:
        return None

    gains = {}
    for ticker, group in window_data.groupby("Ticker"):
        if len(group) < 2:
            continue
        earliest = group.loc[group["Date"].idxmin()]
        latest = group.loc[group["Date"].idxmax()]
        if earliest["Close"] <= 0:
            continue

        # Volume filter
        if min_dollar_volume > 0:
            avg_dv = (group["Close"] * group["Volume"]).mean()
            if avg_dv < min_dollar_volume:
                continue

        pct = (latest["Close"] - earliest["Close"]) / earliest["Close"] * 100.0
        gains[ticker] = pct

    if not gains:
        return None
    return max(gains, key=gains.get)


def _get_close(df: pd.DataFrame, ticker: str, date: pd.Timestamp) -> Optional[float]:
    rows = df[(df["Ticker"] == ticker) & (df["Date"] == date)]
    if rows.empty:
        return None
    return float(rows["Close"].iloc[0])


def _price_path(
    df: pd.DataFrame,
    ticker: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
) -> List:
    """
    Extract daily OHLC bars for `ticker` from `entry_date` to `exit_date`
    (inclusive). Returns a list of [date_str, open, high, low, close] per day.
    """
    mask = (
        (df["Ticker"] == ticker)
        & (df["Date"] >= entry_date)
        & (df["Date"] <= exit_date)
    )
    rows = df.loc[mask].sort_values("Date")
    result = []
    for _, r in rows.iterrows():
        result.append([
            str(r["Date"].date()),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
        ])
    return result


# ── Main backtest loop ─────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    take_profit_pct: float = 10.0,
    stop_loss_pct: float = 5.0,
    backtest_days: int = 60,
    position_size_pct: float = 20.0,
    min_dollar_volume_m: float = 10.0,
    windows: Optional[Dict[str, int]] = None,
) -> Dict:
    """
    Run a multi-strategy momentum backtest with liquidity filter and
    controlled position sizing.

    Parameters
    ----------
    df : pd.DataFrame
        Historical data with columns Date, Ticker, Close, Volume.
    initial_capital : float
        Total cash — split equally across window strategies.
    take_profit_pct : float
        Exit when unrealised gain ≥ this %.
    stop_loss_pct : float
        Exit when unrealised loss ≤ -this %.
    backtest_days : int
        Number of calendar days to simulate.
    position_size_pct : float
        Percentage of available cash to deploy per trade (e.g. 20).
        The rest stays as cash reserve.  100 = all-in (old behaviour).
    min_dollar_volume_m : float
        Minimum average daily dollar-volume in $M.  Stocks below this
        are excluded from the top-gainer selection.  Set to 0 to disable.
    windows : dict | None
        Window label → calendar days.

    Returns
    -------
    dict  strategies, summary, config
    """
    if windows is None:
        windows = WINDOWS

    min_dollar_volume = min_dollar_volume_m * 1_000_000

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    if df["Date"].dt.tz is not None:
        df["Date"] = df["Date"].dt.tz_localize(None)

    all_dates = sorted(df["Date"].unique())
    today = df["Date"].max()
    backtest_start = today - pd.Timedelta(days=backtest_days)

    trading_days = [d for d in all_dates if d >= backtest_start]
    if len(trading_days) < 5:
        raise ValueError(f"Not enough trading days in backtest window (found {len(trading_days)})")

    capital_per_strat = initial_capital / len(windows)

    # Position size factor: 1.0 = all-in, 0.2 = 20% per trade
    size_factor = max(0.01, min(1.0, position_size_pct / 100.0))

    states: Dict[str, StrategyState] = {}
    for label in windows:
        states[label] = StrategyState(cash=capital_per_strat)

    # ── Walk forward ────────────────────────────────────────────────────
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
                        proceeds = st.shares * cur_price
                        trade = Trade(
                            strategy=label,
                            ticker=st.position_ticker,
                            entry_date=st.entry_date,        # type: ignore[arg-type]
                            entry_price=st.entry_price,
                            capital_used=round(st.invested_amount, 2),
                            exit_date=day,
                            exit_price=cur_price,
                            pnl_pct=round(pnl_pct, 2),
                            exit_reason=reason,
                            price_path=_price_path(df, st.position_ticker, st.entry_date, day),  # type: ignore[arg-type]
                        )
                        st.trades.append(trade)
                        st.cash += proceeds                    # add back to reserve
                        st.position_ticker = None
                        st.entry_price = 0.0
                        st.entry_date = None
                        st.shares = 0.0
                        st.invested_amount = 0.0

            # --- 2. If no position, try to enter ---
            if st.position_ticker is None and st.cash > 0:
                top = _top_gainer(df, day, window_days, min_dollar_volume)
                if top is not None:
                    price = _get_close(df, top, day)
                    if price is not None and price > 0:
                        invest = st.cash * size_factor
                        st.shares = invest / price
                        st.position_ticker = top
                        st.entry_price = price
                        st.entry_date = day
                        st.invested_amount = invest
                        st.cash -= invest

            # --- 3. Record equity (mark-to-market) ---
            if st.position_ticker is not None:
                mark_price = _get_close(df, st.position_ticker, day)
                equity = st.cash + (st.shares * mark_price if mark_price else 0)
            else:
                equity = st.cash
            st.equity_curve.append((day, equity))

    # ── Close all open positions at last day ────────────────────────────
    last_day = trading_days[-1]
    for label in windows:
        st = states[label]
        if st.position_ticker is not None:
            cur_price = _get_close(df, st.position_ticker, last_day)
            if cur_price is None:
                cur_price = st.entry_price
            pnl_pct = ((cur_price - st.entry_price) / st.entry_price * 100.0) if st.entry_price > 0 else 0.0
            proceeds = st.shares * cur_price
            trade = Trade(
                strategy=label,
                ticker=st.position_ticker,
                entry_date=st.entry_date,        # type: ignore[arg-type]
                entry_price=st.entry_price,
                capital_used=round(st.invested_amount, 2),
                exit_date=last_day,
                exit_price=cur_price,
                pnl_pct=round(pnl_pct, 2),
                exit_reason="end_of_period",
                price_path=_price_path(df, st.position_ticker, st.entry_date, last_day),  # type: ignore[arg-type]
            )
            st.trades.append(trade)
            st.cash += proceeds
            st.position_ticker = None
            st.entry_price = 0.0
            st.entry_date = None
            st.shares = 0.0
            st.invested_amount = 0.0

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
            "position_size_pct": position_size_pct,
            "min_dollar_volume_m": min_dollar_volume_m,
            "windows": windows,
        },
    }
