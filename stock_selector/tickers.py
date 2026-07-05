"""
Stock ticker lists for screening and backtesting.

Provides S&P 500 and NASDAQ-100 constituents.  Use --universe to
choose: sp500 (default), nasdaq100, or both (deduplicated union).

NOTE: yfinance uses hyphens for share-class tickers (BRK-B not BRK.B).
"""

from typing import List, Optional

import pandas as pd
import requests


# ═══════════════════════════════════════════════════════════════════════════
# S&P 500 constituents
# ═══════════════════════════════════════════════════════════════════════════

SP500_TICKERS: List[str] = [
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM",
    "ADP", "ADSK", "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM",
    "ALB", "ALGN", "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP",
    "AMT", "AMZN", "ANET", "AON", "AOS", "APA", "APD", "APH", "APTV",
    "ARE", "ATO", "AVB", "AVGO", "AVY", "AWK", "AXON", "AXP", "AZO", "BA",
    "BAC", "BALL", "BAX", "BBY", "BDX", "BEN", "BG", "BIIB", "BIO",
    "BK", "BKNG", "BKR", "BLDR", "BLK", "BMY", "BR", "BRK-B", "BRO", "BSX",
    "BWA", "BXP", "C", "CAG", "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE",
    "CCI", "CCL", "CDNS", "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW",
    "CHTR", "CI", "CINF", "CL", "CLX", "CMCSA", "CME", "CMG", "CMI",
    "CMS", "CNC", "CNP", "COF", "COO", "COP", "COR", "COST", "CPAY", "CPB",
    "CPRT", "CPT", "CRL", "CRM", "CSCO", "CSGP", "CSX", "CTAS", "CTRA",
    "CTSH", "CTVA", "CVS", "CVX", "CZR", "D", "DAL", "DD", "DE", "DECK",
    "DG", "DGX", "DHI", "DHR", "DIS", "DLR", "DLTR", "DOV", "DOW",
    "DPZ", "DRI", "DTE", "DUK", "DVA", "DVN", "DXCM", "EA", "EBAY", "ECL",
    "ED", "EFX", "EG", "EIX", "EL", "ELV", "EMN", "EMR", "ENPH", "EOG",
    "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS", "ETN", "ETR", "ETSY", "EVRG",
    "EW", "EXC", "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS",
    "FDX", "FE", "FFIV", "FICO", "FIS", "FITB", "FMC", "FOX", "FOXA",
    "FRT", "FSLR", "FTNT", "FTV", "GD", "GE", "GEHC", "GEN", "GEV", "GILD",
    "GIS", "GL", "GLW", "GM", "GNRC", "GOOG", "GOOGL", "GPC", "GPN", "GRMN",
    "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD", "HIG", "HII",
    "HLT", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUBB",
    "HUM", "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "INCY", "INTC", "INTU",
    "INVH", "IP", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ",
    "J", "JBHT", "JBL", "JCI", "JKHY", "JNJ", "JPM", "KDP",
    "KEY", "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI", "KMX", "KO",
    "KR", "KVUE", "L", "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY",
    "LMT", "LNT", "LOW", "LRCX", "LULU", "LUV", "LVS", "LW", "LYB", "LYV",
    "MA", "MAA", "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT",
    "MET", "META", "MGM", "MHK", "MKC", "MLM", "MMM", "MNST", "MO",
    "MOH", "MOS", "MPC", "MPWR", "MRK", "MRNA", "MS", "MSCI", "MSFT", "MSI",
    "MTB", "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NEE", "NEM", "NFLX", "NI",
    "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA", "NVR",
    "NWL", "NWS", "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC", "ON", "ORCL",
    "ORLY", "OTIS", "OXY", "PANW", "PAYC", "PAYX", "PCAR", "PCG",
    "PEG", "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD",
    "PLTR", "PM", "PNC", "PNR", "PNW", "PODD", "POOL", "PPG", "PPL", "PRU",
    "PSA", "PSX", "PTC", "PWR", "QCOM", "QRVO", "RCL", "REG", "REGN", "RF",
    "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG", "RTX", "RVTY",
    "SBAC", "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA", "SNPS", "SO",
    "SOLV", "SPG", "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ", "SWK",
    "SWKS", "SYF", "SYK", "SYY", "T", "TAP", "TDG", "TDY", "TECH", "TEL",
    "TER", "TFC", "TFX", "TGT", "TJX", "TMO", "TMUS", "TPR", "TRGP", "TRMB",
    "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT", "TTWO", "TXN", "TXT", "TYL",
    "UA", "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI",
    "USB", "V", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRTX", "VST",
    "VTR", "VTRS", "VZ", "WAB", "WAT", "WBD", "WDC", "WEC", "WELL",
    "WFC", "WHR", "WM", "WMB", "WMT", "WRB", "WST", "WTW", "WY", "WYNN",
    "XEL", "XOM", "XYL", "YUM", "ZBH", "ZBRA", "ZION", "ZTS",
]


# ═══════════════════════════════════════════════════════════════════════════
# NASDAQ-100 constituents
# ═══════════════════════════════════════════════════════════════════════════
#
# The NASDAQ-100 includes the 100 largest non-financial companies listed
# on the NASDAQ exchange.  There is substantial overlap with the S&P 500.

NASDAQ100_TICKERS: List[str] = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD",
    "AMGN", "AMZN", "APP", "ARM", "ASML", "AVGO", "AXON",
    "BIIB", "BKNG", "BKR", "CCEP", "CDNS", "CDW", "CEG", "CHTR",
    "CMCSA", "COST", "CPRT", "CRWD", "CSCO", "CSGP", "CSX", "CTAS",
    "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "EA", "EXC", "FANG",
    "FAST", "FTNT", "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON",
    "IDXX", "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC", "LIN",
    "LRCX", "LULU", "MAR", "MCHP", "MDB", "MDLZ", "MELI", "META",
    "MNST", "MPWR", "MRVL", "MSFT", "MU", "NFLX", "NVDA", "NXPI",
    "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP",
    "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SMCI", "SNPS",
    "TEAM", "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX",
    "WBD", "WDAY", "XEL", "ZS",
]

# ── Universe helpers ─────────────────────────────────────────────────────

# Valid universe keys and their ticker lists
UNIVERSES = {
    "sp500": SP500_TICKERS,
    "nasdaq100": NASDAQ100_TICKERS,
}


def get_tickers(universe: str = "sp500") -> List[str]:
    """
    Return a deduplicated ticker list for the given universe.

    Parameters
    ----------
    universe : str
        One of 'sp500', 'nasdaq100', or 'both'.

    Returns
    -------
    list[str] of uppercase ticker symbols.
    """
    universe = universe.lower().strip()

    if universe == "both":
        # Deduplicate while preserving order: S&P first, then NASDAQ-only
        sp_set = set(SP500_TICKERS)
        combined = list(SP500_TICKERS)
        for t in NASDAQ100_TICKERS:
            if t not in sp_set:
                combined.append(t)
        return combined

    tickers = UNIVERSES.get(universe)
    if tickers is None:
        raise ValueError(f"Unknown universe '{universe}'. Choose: sp500, nasdaq100, both")
    return list(tickers)


def fetch_sp500_tickers() -> List[str]:
    """
    Fetch the current S&P 500 constituents from Wikipedia.

    Returns the hard-coded list on failure.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        tables = pd.read_html(url)
        tickers = tables[0]["Symbol"].tolist()
        tickers = [t.replace(".", "-") for t in tickers]
        return tickers
    except Exception:
        return SP500_TICKERS
