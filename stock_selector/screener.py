"""
Stock screening and ranking engine.

Given a DataFrame of historical daily bars (Close, Volume per Ticker),
compute top-N rankings by price-change % and by average volume over
several lookback windows (3 d, 7 d, 14 d, 21 d, 30 d).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd


# Lookback windows in calendar days
WINDOWS: Dict[str, int] = {
    "3d": 3,
    "7d": 7,
    "14d": 14,
    "21d": 21,
    "30d": 30,
    "50d": 50,
    "80d": 80,
}

# Ordered list for consistent display order
ORDERED_WINDOWS = ["3d", "7d", "14d", "21d", "30d", "50d", "80d"]


@dataclass
class StockRank:
    ticker: str
    metric_value: float
    extra_info: str = ""


@dataclass
class WindowResult:
    window_label: str
    top_by_gain: List[StockRank] = field(default_factory=list)
    top_by_volume: List[StockRank] = field(default_factory=list)


def _min_trading_days(calendar_days: int) -> int:
    """
    Require at least this many distinct trading days for a stock to be
    included in the ranking for a given window.
    """
    return max(2, int(calendar_days * 0.55))


def _price_change_pct(group: pd.DataFrame, cal_days: int, now: pd.Timestamp) -> Optional[float]:
    """Percentage price change over the last `cal_days` for one ticker."""
    cutoff = now - pd.Timedelta(days=cal_days)
    recent = group[group["Date"] >= cutoff]
    if recent.empty or len(recent["Date"].unique()) < _min_trading_days(cal_days):
        return None
    earliest = recent.loc[recent["Date"].idxmin()]
    latest = recent.loc[recent["Date"].idxmax()]
    if earliest["Close"] <= 0:
        return None
    return ((latest["Close"] - earliest["Close"]) / earliest["Close"]) * 100.0


def _avg_volume(group: pd.DataFrame, cal_days: int, now: pd.Timestamp) -> Optional[float]:
    """Average daily volume over the last `cal_days` for one ticker."""
    cutoff = now - pd.Timedelta(days=cal_days)
    recent = group[group["Date"] >= cutoff]
    if recent.empty or len(recent["Date"].unique()) < _min_trading_days(cal_days):
        return None
    return float(recent["Volume"].mean())


def compute_rankings(
    df: pd.DataFrame,
    top_n: int = 10,
    min_price: float = 1.0,
    windows: Optional[Dict[str, int]] = None,
) -> Dict[str, WindowResult]:
    """
    Compute top-N rankings.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: Date, Ticker, Close, Volume.
    top_n : int
        How many stocks to return per ranking.
    min_price : float
        Exclude stocks whose latest close is below this price.
    windows : dict | None
        Which windows to compute (label → calendar_days). Defaults to all.

    Returns
    -------
    dict  label → WindowResult
    """
    if windows is None:
        windows = WINDOWS

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    # Strip timezone info so comparisons with naive pd.Timestamp work reliably
    if df["Date"].dt.tz is not None:
        df["Date"] = df["Date"].dt.tz_localize(None)

    # "Now" for cutoff calculations — use the latest date in the data so
    # we aren't broken by weekends / holidays when markets are closed.
    now = df["Date"].max()

    # Drop penny / ultra-low-price stocks
    latest_close = df.groupby("Ticker")["Close"].last()
    valid_tickers = latest_close[latest_close >= min_price].index.tolist()
    df = df[df["Ticker"].isin(valid_tickers)]

    if df.empty:
        return {}

    # Skip windows that need more data than we have
    data_span_days = (df["Date"].max() - df["Date"].min()).days

    results: Dict[str, WindowResult] = {}

    for label, cal_days in windows.items():
        if cal_days > data_span_days + 3:  # +3 grace for weekends
            continue

        wr = WindowResult(window_label=label)

        gains = {}
        volumes = {}
        for ticker, group in df.groupby("Ticker"):
            pct = _price_change_pct(group, cal_days, now)
            vol = _avg_volume(group, cal_days, now)
            if pct is not None:
                gains[ticker] = pct
            if vol is not None:
                volumes[ticker] = vol

        # Top by price gain
        top_gainers = sorted(gains.items(), key=lambda x: x[1], reverse=True)[:top_n]
        for ticker, pct in top_gainers:
            vol_info = volumes.get(ticker, 0)
            wr.top_by_gain.append(
                StockRank(
                    ticker=ticker,
                    metric_value=round(pct, 2),
                    extra_info=f"avg_vol={vol_info:,.0f}",
                )
            )

        # Top by volume
        top_vol = sorted(volumes.items(), key=lambda x: x[1], reverse=True)[:top_n]
        for ticker, vol in top_vol:
            pct_info = gains.get(ticker, 0)
            wr.top_by_volume.append(
                StockRank(
                    ticker=ticker,
                    metric_value=round(vol, 2),
                    extra_info=f"gain={pct_info:.2f}%",
                )
            )

        results[label] = wr

    return results
