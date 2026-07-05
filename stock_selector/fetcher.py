"""
Data-fetching layer for US stock historical data via Yahoo Finance.

Downloads daily OHLCV bars for a list of tickers and returns a clean
pandas DataFrame ready for screening.

Supports HTTP/HTTPS proxies via the standard environment variables
(HTTP_PROXY / HTTPS_PROXY) which are picked up by yfinance / curl_cffi
automatically.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf


# Silence yfinance's verbose "possibly delisted" warnings
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("peewee").setLevel(logging.ERROR)

# How many tickers to download in one batch
BATCH_SIZE = 50
# Seconds to wait between batches
BATCH_DELAY = 1.5
# Max retries per batch
MAX_RETRIES = 3


def _business_days_back(calendar_days: int) -> int:
    """Calendar days → approx trading days, plus buffer for holidays."""
    return int(calendar_days * 1.6) + 5


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise yfinance output into a consistent long-form DataFrame
    with columns: Date, Ticker, Close, Volume.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df = df.stack(level=0, future_stack=True).reset_index()
        df = df.rename(columns={"level_0": "Date"})
    else:
        df = df.reset_index()

    col_map = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl == "date" or cl.startswith("date"):
            col_map[c] = "Date"
        elif cl == "ticker" or cl.startswith("ticker"):
            col_map[c] = "Ticker"
        elif cl == "close":
            col_map[c] = "Close"
        elif cl == "volume":
            col_map[c] = "Volume"
    df = df.rename(columns=col_map)

    keep = ["Date", "Ticker", "Close", "Volume"]
    return df[[c for c in keep if c in df.columns]]


def _download_batch(tickers: List[str], start: str, end: str) -> Optional[pd.DataFrame]:
    """Download one batch with retries on rate-limit errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = yf.download(
                tickers,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                group_by="ticker",
                threads=False,
            )
            if data is None or data.empty:
                return None
            return _normalize_columns(data)

        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                wait = 5 * attempt
                print(f"  Rate-limited. Retrying in {wait}s... (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                else:
                    return None
    return None


def detect_proxy() -> dict | None:
    """
    Detect proxy settings from environment or macOS system config.
    """
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    if http_proxy or https_proxy:
        return {
            "http": http_proxy or https_proxy,
            "https": https_proxy or http_proxy,
        }
    return None


def fetch_historical_data(
    tickers: List[str],
    lookback_days: int = 30,
    progress: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Download daily OHLCV data for `tickers`.

    Parameters
    ----------
    tickers : list[str]
        Stock ticker symbols (e.g. ['AAPL', 'MSFT']).
    lookback_days : int
        How many calendar days of data to fetch.
    progress : bool
        Print batch progress to stdout.

    Returns
    -------
    pd.DataFrame with columns [Date, Ticker, Close, Volume] or None.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + _business_days_back(lookback_days))

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # Ensure proxy env vars are set for curl_cffi
    proxy = detect_proxy()
    if proxy and not os.environ.get("HTTP_PROXY"):
        os.environ["HTTP_PROXY"] = proxy["http"] or ""
        os.environ["HTTPS_PROXY"] = proxy["https"] or ""

    all_frames: List[pd.DataFrame] = []
    total_batches = (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE
    failed_count = 0

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        if progress:
            print(f"  Batch {batch_num}/{total_batches}: {len(batch)} tickers...", end=" ", flush=True)

        df = _download_batch(batch, start_str, end_str)

        if df is not None and not df.empty:
            got = df["Ticker"].nunique()
            missed = len(batch) - got
            failed_count += missed
            all_frames.append(df)
            if progress:
                tag = f" ({missed} skipped)" if missed else ""
                print(f"✓ {got} tickers, {len(df)} rows{tag}")
        else:
            failed_count += len(batch)
            if progress:
                print("✗ failed")

        if i + BATCH_SIZE < len(tickers):
            time.sleep(BATCH_DELAY)

    if failed_count and progress:
        print(f"  ({failed_count} tickers skipped — delisted or no data)")

    if not all_frames:
        return None

    result = pd.concat(all_frames, ignore_index=True)
    result = result.dropna(subset=["Close", "Volume"])
    result["Date"] = pd.to_datetime(result["Date"])
    return result
