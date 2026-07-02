"""
Shared core logic for the stock trend agent: fetch price history, fit a
linear trend, and project it forward. Used by both stock_trend.py (CLI)
and app.py (mobile-friendly web page).
"""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = TRADING_DAYS_PER_YEAR / 12
SMA_SHORT = 50
SMA_LONG = 200

CURRENCY_SYMBOLS = {
    "USD": "$", "INR": "₹", "EUR": "€", "GBP": "£",
    "JPY": "¥", "CNY": "¥", "HKD": "HK$", "AUD": "A$", "CAD": "C$",
}


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency + " ")


def resolve_ticker(ticker: str) -> str:
    """Try the symbol as given; if it has no exchange suffix and fails,
    fall back to NSE (.NS) then BSE (.BO) so Indian tickers like 'RELIANCE'
    or 'TCS' work without the user knowing the Yahoo suffix."""
    ticker = ticker.strip()
    if "." in ticker:
        return ticker

    candidates = [ticker, f"{ticker}.NS", f"{ticker}.BO"]
    for candidate in candidates:
        try:
            full = yf.Ticker(candidate).history(period="5d", interval="1d")
        except Exception:
            continue
        if not full.empty:
            return candidate
    return ticker


def fetch_last_year(ticker: str):
    """Fetch ~2y of history (so SMA200 is valid across the whole displayed
    1y window), compute SMA50/SMA200, then trim the display to the last 1y."""
    resolved = resolve_ticker(ticker)
    tk = yf.Ticker(resolved)
    full = tk.history(period="2y", interval="1d")
    if full.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check the symbol.")
    full = full[["Close"]].dropna()
    full["SMA50"] = full["Close"].rolling(SMA_SHORT).mean()
    full["SMA200"] = full["Close"].rolling(SMA_LONG).mean()

    cutoff = full.index[-1] - pd.Timedelta(days=365)
    data = full[full.index >= cutoff].copy()

    try:
        currency = tk.fast_info.get("currency") or "USD"
    except Exception:
        currency = "USD"
    return data, currency, resolved


def find_crosses(data: pd.DataFrame):
    """Detect points within the display window where SMA50 crosses SMA200.
    Returns a list of dicts: {date, price, kind: 'golden'|'death'}."""
    valid = data.dropna(subset=["SMA50", "SMA200"])
    crosses = []
    prev_diff = None
    for date, row in valid.iterrows():
        diff = row["SMA50"] - row["SMA200"]
        if prev_diff is not None and prev_diff != 0 and diff != 0:
            if prev_diff < 0 and diff > 0:
                crosses.append({"date": date, "price": row["Close"], "kind": "golden"})
            elif prev_diff > 0 and diff < 0:
                crosses.append({"date": date, "price": row["Close"], "kind": "death"})
        prev_diff = diff
    return crosses


def find_support_resistance(data: pd.DataFrame, window: int = 10, tolerance_pct: float = 0.02, max_levels: int = 3):
    """Find horizontal support/resistance levels by locating local price
    pivots (swing highs/lows over a +/-`window` day span) and clustering
    pivots that sit within `tolerance_pct` of each other into one level.
    Levels with more touches are considered stronger."""
    close = data["Close"].to_numpy()
    dates = data.index
    n = len(close)

    pivot_highs, pivot_lows = [], []
    for i in range(window, n - window):
        segment = close[i - window: i + window + 1]
        if close[i] == segment.max():
            pivot_highs.append((dates[i], close[i]))
        if close[i] == segment.min():
            pivot_lows.append((dates[i], close[i]))

    def cluster(pivots):
        if not pivots:
            return []
        pivots = sorted(pivots, key=lambda p: p[1])
        clusters, current = [], [pivots[0]]
        for p in pivots[1:]:
            if abs(p[1] - current[-1][1]) / current[-1][1] <= tolerance_pct:
                current.append(p)
            else:
                clusters.append(current)
                current = [p]
        clusters.append(current)
        return [
            {
                "price": sum(x[1] for x in c) / len(c),
                "touches": len(c),
                "last_date": max(x[0] for x in c),
            }
            for c in clusters
        ]

    current_price = close[-1]
    highs = cluster(pivot_highs)
    lows = cluster(pivot_lows)

    resistance = sorted(
        (h for h in highs if h["price"] > current_price),
        key=lambda h: (-h["touches"], h["price"]),
    )[:max_levels]
    support = sorted(
        (l for l in lows if l["price"] < current_price),
        key=lambda l: (-l["touches"], -l["price"]),
    )[:max_levels]

    return {"support": support, "resistance": resistance}


def fit_linear_trend(data: pd.DataFrame):
    x = np.arange(len(data))
    y = data["Close"].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept


def project_price(slope: float, intercept: float, n_points: int, months_ahead: float) -> float:
    future_x = n_points - 1 + months_ahead * TRADING_DAYS_PER_MONTH
    return slope * future_x + intercept


def build_trend_series(data: pd.DataFrame, slope: float, intercept: float, months_ahead: float):
    """Return (future_dates, trend_hist, trend_future, projected_price)."""
    n = len(data)
    future_days = int(round(months_ahead * TRADING_DAYS_PER_MONTH))
    last_date = data.index[-1]
    future_dates = [last_date + timedelta(days=int(d * 7 / 5)) for d in range(1, future_days + 1)]

    x_hist = np.arange(n)
    x_future = np.arange(n, n + future_days)
    trend_hist = slope * x_hist + intercept
    trend_future = slope * x_future + intercept
    projected_price = trend_future[-1] if future_days > 0 else trend_hist[-1]

    return future_dates, trend_hist, trend_future, projected_price


def analyze(ticker: str, months_ahead: float = 3):
    """Fetch, fit, and project in one call. Returns a dict of results."""
    data, currency, resolved = fetch_last_year(ticker)
    slope, intercept = fit_linear_trend(data)
    future_dates, trend_hist, trend_future, projected_price = build_trend_series(
        data, slope, intercept, months_ahead
    )
    current = data["Close"].iloc[-1]
    change_pct = (projected_price - current) / current * 100
    crosses = find_crosses(data)
    levels = find_support_resistance(data)

    return {
        "data": data,
        "resolved_ticker": resolved,
        "currency": currency,
        "symbol": currency_symbol(currency),
        "slope": slope,
        "intercept": intercept,
        "future_dates": future_dates,
        "trend_hist": trend_hist,
        "trend_future": trend_future,
        "current": current,
        "projected": projected_price,
        "change_pct": change_pct,
        "crosses": crosses,
        "support": levels["support"],
        "resistance": levels["resistance"],
    }
