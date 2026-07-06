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
import subprocess
import time
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import requests
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
        elif cl == "open":
            col_map[c] = "Open"
        elif cl == "high":
            col_map[c] = "High"
        elif cl == "low":
            col_map[c] = "Low"
        elif cl == "close":
            col_map[c] = "Close"
        elif cl == "volume":
            col_map[c] = "Volume"
    df = df.rename(columns=col_map)

    keep = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
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


def auto_detect_proxy() -> bool:
    """
    Detect and configure HTTP/HTTPS proxy from environment variables or
    macOS system proxy settings.  Sets os.environ variables so that
    yfinance, requests, and curl_cffi pick them up transparently.

    Returns True if a proxy was configured, False otherwise.
    """
    # Check env vars first (explicit user configuration takes priority)
    if os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"):
        return True

    # Fall back to macOS system proxy (scutil)
    try:
        result = subprocess.run(
            ["scutil", "--proxy"], capture_output=True, text=True, timeout=5,
        )
        proxy_host = proxy_port = None
        for line in result.stdout.splitlines():
            if "HTTPProxy" in line and "HTTPEnable" not in line:
                proxy_host = line.split(":")[-1].strip()
            if "HTTPPort" in line:
                proxy_port = line.split(":")[-1].strip()
        if proxy_host and proxy_port:
            proxy_url = f"http://{proxy_host}:{proxy_port}"
            for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                os.environ[var] = proxy_url
            return True
    except Exception:
        pass
    return False


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


# ═══════════════════════════════════════════════════════════════════════════════
# Yahoo Finance v8 Chart API Fetcher (alternative to yfinance)
# ═══════════════════════════════════════════════════════════════════════════════

_V8_CHART_API = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"


def _make_v8_session() -> requests.Session:
    """Create a requests Session. Short UA avoids Yahoo's bot-detection 429."""
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s


def _fetch_one_v8(session: requests.Session, ticker: str,
                  lookback_days: int) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single ticker via Yahoo v8 chart API.
    Returns a DataFrame with [Date, Ticker, Open, High, Low, Close, Volume] or None.
    """
    if lookback_days < 1:
        lookback_days = 1
    range_str = f"{lookback_days}d"

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval=1d"

    for attempt in range(3):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 429:
                time.sleep(15)
                continue
            if resp.status_code == 403:
                # Proxy needed — should have been configured
                return None
            if resp.status_code != 200:
                return None

            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None

            r = result[0]
            timestamps = r.get("timestamp", [])
            quote = r.get("indicators", {}).get("quote", [{}])[0]

            if not timestamps or not quote:
                return None

            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            rows = []
            for i, ts in enumerate(timestamps):
                if closes[i] is not None:
                    rows.append({
                        "Date": pd.Timestamp.utcfromtimestamp(ts).tz_localize(None),
                        "Ticker": ticker,
                        "Open": float(opens[i]) if opens[i] is not None else None,
                        "High": float(highs[i]) if highs[i] is not None else None,
                        "Low": float(lows[i]) if lows[i] is not None else None,
                        "Close": float(closes[i]) if closes[i] is not None else None,
                        "Volume": int(volumes[i]) if volumes[i] is not None else 0,
                    })

            df = pd.DataFrame(rows)
            if df.empty:
                return None
            return df.dropna(subset=["Close", "Volume"])

        except Exception as e:
            msg = str(e).lower()
            if "ssl" in msg or "eof" in msg:
                # Transient proxy SSL issue — retry
                time.sleep(5)
                continue
            if attempt < 2:
                time.sleep(3)
            else:
                return None
    return None


def fetch_v8_data(
    tickers: List[str],
    lookback_days: int = 415,
    progress: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Download daily OHLCV data for `tickers` via Yahoo Finance v8 chart API.

    Alternative to fetch_historical_data() that avoids yfinance rate limits
    by fetching one ticker at a time with a short delay.

    Parameters
    ----------
    tickers : list[str]
        Stock ticker symbols.
    lookback_days : int
        How many calendar days of data to fetch.
    progress : bool
        Print progress to stdout.

    Returns
    -------
    pd.DataFrame with columns [Date, Ticker, Open, High, Low, Close, Volume] or None.
    """
    session = _make_v8_session()
    all_frames = []
    failed = 0
    delay = 0.5  # seconds between tickers
    consecutive_fails = 0

    # Pre-warm: make one request to verify connectivity
    if progress:
        print("  Pre-flight check...", end=" ", flush=True)
    test_df = _fetch_one_v8(session, tickers[0], lookback_days)
    if test_df is not None and not test_df.empty:
        all_frames.append(test_df)
        if progress:
            print(f"✓ {len(test_df)} rows")
    else:
        if progress:
            print("✗ (will retry)")

    for i, ticker in enumerate(tickers):
        if i == 0:
            continue  # already fetched in pre-flight

        # Adaptive cooldown on failures
        if consecutive_fails >= 3:
            wait = 30
            if progress:
                print(f"      (cooldown {wait}s after {consecutive_fails} failures)...",
                      end=" ", flush=True)
            time.sleep(wait)
            consecutive_fails = 0
        else:
            time.sleep(delay)

        if progress:
            pct = (i + 1) / len(tickers) * 100
            print(f"  [{i+1:3d}/{len(tickers)}] {ticker:5s} ({pct:.0f}%)...",
                  end=" ", flush=True)

        df = _fetch_one_v8(session, ticker, lookback_days)
        if df is not None and not df.empty:
            all_frames.append(df)
            consecutive_fails = 0
            if progress:
                print(f"✓ {len(df):4d} rows")
        else:
            failed += 1
            consecutive_fails += 1
            if progress:
                print("✗")

    if failed and progress:
        print(f"  ({failed} tickers skipped — delisted or no data)")

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.dropna(subset=["Close", "Volume"])
    result["Date"] = pd.to_datetime(result["Date"])
    return result
