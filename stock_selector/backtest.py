"""
Backtesting engine for momentum-based stock selection strategies.

Simulates paper trading over a historical period: each day, buys the
top-1 price-gainer over a given lookback window (filtered by minimum
daily dollar-volume for liquidity), and exits when the position hits
take-profit or stop-loss thresholds.

Supports three execution modes:
  - close    : signal & execute at daily closing price (default)
  - open     : signal at close, execute at NEXT day's open (no look-ahead)
  - intraday : signal at close, enter at next open, exit at intraday TP/SL
               crossing level when OHLC range confirms it was reachable

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
    capital_used: float
    entry_gain_pct: float = 0.0
    entry_avg_vol: float = 0.0
    exec_type: str = "close"             # close | open | intraday
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: str = "open"
    price_path: List = field(default_factory=list)


@dataclass
class StrategyState:
    """Mutable state for one window-strategy during the walk-forward."""
    cash: float
    position_ticker: Optional[str] = None
    entry_price: float = 0.0
    entry_date: Optional[pd.Timestamp] = None
    entry_gain_pct: float = 0.0
    entry_avg_vol: float = 0.0
    exec_type: str = "close"
    shares: float = 0.0
    invested_amount: float = 0.0
    # Delayed entry (open / intraday modes): signal computed at close T,
    # executed at open T+1.
    pending_ticker: Optional[str] = None
    pending_gain_pct: float = 0.0
    pending_avg_vol: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[pd.Timestamp, float]] = field(default_factory=list)


# ── Core helpers ───────────────────────────────────────────────────────────

def _dollar_volume(
    df: pd.DataFrame, ticker: str, today: pd.Timestamp, window_days: int,
) -> Optional[float]:
    cutoff = today - pd.Timedelta(days=window_days)
    mask = (df["Ticker"] == ticker) & (df["Date"] >= cutoff) & (df["Date"] <= today)
    recent = df.loc[mask]
    if len(recent) < 2:
        return None
    return float((recent["Close"] * recent["Volume"]).mean())


def _top_gainer(
    df: pd.DataFrame, today: pd.Timestamp, window_days: int,
    min_dollar_volume: float = 0.0,
) -> Optional[Tuple[str, float, float]]:
    cutoff = today - pd.Timedelta(days=window_days)
    window_data = df[(df["Date"] >= cutoff) & (df["Date"] <= today)]
    if window_data.empty:
        return None

    best_ticker, best_gain, best_vol = None, -float("inf"), 0.0
    for ticker, group in window_data.groupby("Ticker"):
        if len(group) < 2:
            continue
        earliest = group.loc[group["Date"].idxmin()]
        latest = group.loc[group["Date"].idxmax()]
        if earliest["Close"] <= 0:
            continue
        avg_dv = (group["Close"] * group["Volume"]).mean()
        if min_dollar_volume > 0 and avg_dv < min_dollar_volume:
            continue
        pct = (latest["Close"] - earliest["Close"]) / earliest["Close"] * 100.0
        if pct > best_gain:
            best_gain, best_ticker, best_vol = pct, ticker, avg_dv
    if best_ticker is None:
        return None
    return (best_ticker, best_gain, best_vol)


def _get_ohlc(df: pd.DataFrame, ticker: str, date: pd.Timestamp) -> Optional[dict]:
    """Return {open, high, low, close} dict for `ticker` on `date`, or None."""
    rows = df[(df["Ticker"] == ticker) & (df["Date"] == date)]
    if rows.empty:
        return None
    r = rows.iloc[0]
    return {"open": float(r["Open"]), "high": float(r["High"]),
            "low": float(r["Low"]), "close": float(r["Close"])}


def _next_trading_day(dates: List[pd.Timestamp], current: pd.Timestamp) -> Optional[pd.Timestamp]:
    """Return the next trading day after `current`, or None."""
    for d in dates:
        if d > current:
            return d
    return None


def _price_path(df: pd.DataFrame, ticker: str,
                entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> List:
    mask = ((df["Ticker"] == ticker) & (df["Date"] >= entry_date)
            & (df["Date"] <= exit_date))
    rows = df.loc[mask].sort_values("Date")
    result = []
    for _, r in rows.iterrows():
        result.append([str(r["Date"].date()), float(r["Open"]),
                       float(r["High"]), float(r["Low"]), float(r["Close"])])
    return result


# ── Exit check helpers (exec-mode aware) ────────────────────────────────────

def _check_exit_close(ohlc: dict, entry_price: float,
                      tp_pct: float, sl_pct: float) -> Optional[Tuple[float, str]]:
    """Check TP/SL at closing price. Returns (exit_price, reason) or None."""
    price = ohlc["close"]
    pnl = (price - entry_price) / entry_price * 100.0
    if pnl >= tp_pct:
        return (price, "take_profit")
    if pnl <= -sl_pct:
        return (price, "stop_loss")
    return None


def _check_exit_open(ohlc: dict, entry_price: float,
                     tp_pct: float, sl_pct: float) -> Optional[Tuple[float, str]]:
    """Check TP/SL at opening price. Returns (exit_price, reason) or None."""
    price = ohlc["open"]
    pnl = (price - entry_price) / entry_price * 100.0
    if pnl >= tp_pct:
        return (price, "take_profit")
    if pnl <= -sl_pct:
        return (price, "stop_loss")
    return None


def _check_exit_intraday(ohlc: dict, entry_price: float,
                         tp_pct: float, sl_pct: float) -> Optional[Tuple[float, str]]:
    """
    Check if TP or SL level was within the day's High-Low range.
    If so, assume execution at that level (intraday fill).

    Priority: TP first (optimistic — assume you took profit when available),
    then SL. Falls back to None if neither level was reachable.
    """
    tp_level = entry_price * (1 + tp_pct / 100.0)
    sl_level = entry_price * (1 - sl_pct / 100.0)

    if ohlc["high"] >= tp_level:
        return (tp_level, "take_profit")
    if ohlc["low"] <= sl_level:
        return (sl_level, "stop_loss")
    return None


# ── Main backtest loop ─────────────────────────────────────────────────────

def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    take_profit_pct: float = 10.0,
    stop_loss_pct: float = 5.0,
    backtest_days: int = 60,
    position_size_pct: float = 20.0,
    min_dollar_volume_m: float = 10.0,
    max_hold_days: int = 0,
    exec_mode: str = "close",
    windows: Optional[Dict[str, int]] = None,
) -> Dict:
    """
    Run a multi-strategy momentum backtest.

    Parameters
    ----------
    exec_mode : str
        'close'    — signal & execute at daily closing price.
        'open'     — signal at close, execute at NEXT day's open.
        'intraday' — signal at close, enter at next open, exit checks
                     intraday OHLC for TP/SL crossing first; falls back
                     to close-based check for time_stop / end_of_period.
    """
    if windows is None:
        windows = WINDOWS

    exec_mode = exec_mode.lower()
    if exec_mode not in ("close", "open", "intraday"):
        raise ValueError(f"Unknown exec_mode '{exec_mode}'. Choose: close, open, intraday")

    min_dollar_volume = min_dollar_volume_m * 1_000_000
    size_factor = max(0.01, min(1.0, position_size_pct / 100.0))

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    if df["Date"].dt.tz is not None:
        df["Date"] = df["Date"].dt.tz_localize(None)

    all_dates = sorted(df["Date"].unique())
    last_data_date = df["Date"].max()
    backtest_start = last_data_date - pd.Timedelta(days=backtest_days)

    trading_days = [d for d in all_dates if d >= backtest_start]
    if len(trading_days) < 5:
        raise ValueError(f"Not enough trading days (found {len(trading_days)})")

    capital_per_strat = initial_capital / len(windows)

    states: Dict[str, StrategyState] = {}
    for label in windows:
        states[label] = StrategyState(cash=capital_per_strat)

    # ── Walk forward day by day ─────────────────────────────────────────
    for day in trading_days:
        for label, window_days in windows.items():
            st = states[label]

            # ============================================================
            # 0. Process pending entry (open / intraday modes)
            # ============================================================
            if exec_mode in ("open", "intraday") and st.pending_ticker is not None:
                ohlc = _get_ohlc(df, st.pending_ticker, day)
                if ohlc is not None:
                    price = ohlc["open"]
                    invest = st.cash * size_factor
                    st.shares = invest / price
                    st.position_ticker = st.pending_ticker
                    st.entry_price = price
                    st.entry_date = day
                    st.invested_amount = invest
                    st.entry_gain_pct = round(st.pending_gain_pct, 2)
                    st.entry_avg_vol = st.pending_avg_vol
                    st.exec_type = exec_mode
                    st.cash -= invest
                st.pending_ticker = None
                st.pending_gain_pct = 0.0
                st.pending_avg_vol = 0.0

            # ============================================================
            # 1. Check existing position P&L
            # ============================================================
            if st.position_ticker is not None:
                ohlc = _get_ohlc(df, st.position_ticker, day)
                if ohlc is not None and st.entry_price > 0:
                    hold_days = (day - st.entry_date).days
                    exit_info = None
                    exit_price = ohlc["close"]
                    reason = "open"

                    if exec_mode == "close":
                        exit_info = _check_exit_close(ohlc, st.entry_price, take_profit_pct, stop_loss_pct)
                    elif exec_mode == "open":
                        exit_info = _check_exit_open(ohlc, st.entry_price, take_profit_pct, stop_loss_pct)
                    elif exec_mode == "intraday":
                        # Intraday exit: check if TP/SL was reachable during the day
                        exit_info = _check_exit_intraday(ohlc, st.entry_price, take_profit_pct, stop_loss_pct)
                        if exit_info is None:
                            # Not hit intraday — fall back to close check for TP/SL/time
                            exit_info = _check_exit_close(ohlc, st.entry_price, take_profit_pct, stop_loss_pct)

                    if exit_info is not None:
                        exit_price, reason = exit_info
                        should_sell = True
                    else:
                        should_sell = False

                    # Time-stop (always checked regardless of exec mode)
                    if not should_sell and max_hold_days > 0 and hold_days >= max_hold_days:
                        should_sell = True
                        reason = "time_stop"
                        exit_price = ohlc["close"]

                    if should_sell:
                        proceeds = st.shares * exit_price
                        trade = Trade(
                            strategy=label, ticker=st.position_ticker,
                            entry_date=st.entry_date, entry_price=st.entry_price,  # type: ignore[arg-type]
                            capital_used=round(st.invested_amount, 2),
                            entry_gain_pct=st.entry_gain_pct,
                            entry_avg_vol=st.entry_avg_vol,
                            exec_type=st.exec_type,
                            exit_date=day, exit_price=exit_price,
                            pnl_pct=round((exit_price - st.entry_price) / st.entry_price * 100, 2),
                            exit_reason=reason,
                            price_path=_price_path(df, st.position_ticker, st.entry_date, day),  # type: ignore[arg-type]
                        )
                        st.trades.append(trade)
                        st.cash += proceeds
                        st.position_ticker = None
                        st.entry_price = 0.0
                        st.entry_gain_pct = 0.0
                        st.entry_avg_vol = 0.0
                        st.exec_type = "close"
                        st.entry_date = None
                        st.shares = 0.0
                        st.invested_amount = 0.0

            # ============================================================
            # 2. Compute signal & try to enter
            # ============================================================
            if st.position_ticker is None and st.cash > 0:
                top_result = _top_gainer(df, day, window_days, min_dollar_volume)
                if top_result is not None:
                    top_ticker, entry_gain, entry_vol = top_result

                    if exec_mode == "close":
                        # Enter immediately at today's close
                        ohlc = _get_ohlc(df, top_ticker, day)
                        if ohlc is not None:
                            price = ohlc["close"]
                            invest = st.cash * size_factor
                            st.shares = invest / price
                            st.position_ticker = top_ticker
                            st.entry_price = price
                            st.entry_date = day
                            st.invested_amount = invest
                            st.entry_gain_pct = round(entry_gain, 2)
                            st.entry_avg_vol = entry_vol
                            st.exec_type = "close"
                            st.cash -= invest
                    else:
                        # open / intraday: queue entry at next day's open
                        st.pending_ticker = top_ticker
                        st.pending_gain_pct = entry_gain
                        st.pending_avg_vol = entry_vol

            # ============================================================
            # 3. Record equity (mark-to-market at close)
            # ============================================================
            if st.position_ticker is not None:
                ohlc = _get_ohlc(df, st.position_ticker, day)
                equity = st.cash + (st.shares * ohlc["close"] if ohlc else 0)
            else:
                equity = st.cash
            st.equity_curve.append((day, equity))

    # ── Close all open positions at last day ────────────────────────────
    last_day = trading_days[-1]
    for label in windows:
        st = states[label]
        # Flush any unexecuted pending entry
        st.pending_ticker = None

        if st.position_ticker is not None:
            ohlc = _get_ohlc(df, st.position_ticker, last_day)
            cur_price = ohlc["close"] if ohlc else st.entry_price
            pnl_pct = ((cur_price - st.entry_price) / st.entry_price * 100.0) if st.entry_price > 0 else 0.0
            proceeds = st.shares * cur_price
            trade = Trade(
                strategy=label, ticker=st.position_ticker,
                entry_date=st.entry_date, entry_price=st.entry_price,  # type: ignore[arg-type]
                capital_used=round(st.invested_amount, 2),
                entry_gain_pct=st.entry_gain_pct,
                entry_avg_vol=st.entry_avg_vol,
                exec_type=st.exec_type,
                exit_date=last_day, exit_price=cur_price,
                pnl_pct=round(pnl_pct, 2), exit_reason="end_of_period",
                price_path=_price_path(df, st.position_ticker, st.entry_date, last_day),  # type: ignore[arg-type]
            )
            st.trades.append(trade)
            st.cash += proceeds
            st.position_ticker = None

    # ── Build results ───────────────────────────────────────────────────
    strategy_results = {}
    total_final = 0.0
    total_trades = 0
    total_winners = 0

    for label in windows:
        st = states[label]
        final_eq = st.cash if st.cash > 0 else (
            st.equity_curve[-1][1] if st.equity_curve else capital_per_strat)
        total_final += final_eq

        wins = [t for t in st.trades if t.exit_reason == "take_profit"]
        losses = [t for t in st.trades if t.exit_reason == "stop_loss"]
        time_stops = [t for t in st.trades if t.exit_reason == "time_stop"]
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
            "take_profits": len(wins), "stop_losses": len(losses),
            "time_stops": len(time_stops), "end_of_period": len(eop),
            "avg_return_pct": round(avg_return, 2),
            "best_trade_pct": round(best_trade, 2),
            "worst_trade_pct": round(worst_trade, 2),
            "trades": st.trades, "equity_curve": st.equity_curve,
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
            "max_hold_days": max_hold_days,
            "backtest_days": backtest_days,
            "position_size_pct": position_size_pct,
            "min_dollar_volume_m": min_dollar_volume_m,
            "exec_mode": exec_mode,
            "windows": windows,
        },
    }
