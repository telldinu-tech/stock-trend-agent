"""
Stock trend agent (CLI).

Downloads the last 1 year of daily closing prices for a ticker (via Yahoo
Finance, the practical stand-in for the now-defunct Google Finance API),
fits a linear regression ("line of best fit") through those prices, plots
the historical prices together with the fitted line extended N months into
the future, and prints the projected price.

Usage:
    python stock_trend.py AAPL
    python stock_trend.py MSFT --months 3 --no-show
    python stock_trend.py TSLA --out tsla_trend.png

For a mobile-friendly version, run: streamlit run app.py

Notes:
    - This is a simple linear extrapolation of the past year of prices.
      It is a naive trend estimate, not a forecast model, and should not
      be used as the sole basis for investment decisions.
"""

import argparse
import sys

import matplotlib
import matplotlib.pyplot as plt

from stock_core import analyze


def plot_trend(result: dict, months_ahead: float, ticker: str, out_path: str | None, show: bool) -> None:
    data = result["data"]
    symbol = result["symbol"]
    currency = result["currency"]
    future_dates = result["future_dates"]
    trend_hist = result["trend_hist"]
    trend_future = result["trend_future"]
    projected_price = result["projected"]

    plt.figure(figsize=(11, 6))
    plt.plot(data.index, data["Close"], label="Actual close price", color="tab:blue")
    plt.plot(data.index, trend_hist, label="Linear trend (fit)", color="tab:orange", linestyle="--")
    plt.plot(future_dates, trend_future, label=f"Trend projection (+{months_ahead:g} mo)",
              color="tab:red", linestyle="--")
    plt.scatter([future_dates[-1]] if future_dates else [data.index[-1]],
                [projected_price], color="tab:red", zorder=5)
    plt.annotate(f"{symbol}{projected_price:,.2f}",
                 (future_dates[-1] if future_dates else data.index[-1], projected_price),
                 textcoords="offset points", xytext=(8, 8), color="tab:red", fontweight="bold")

    plt.plot(data.index, data["SMA50"], label="SMA 50", color="tab:green", linewidth=1.2)
    plt.plot(data.index, data["SMA200"], label="SMA 200", color="tab:purple", linewidth=1.2)
    for c in result["crosses"]:
        marker = "^" if c["kind"] == "golden" else "v"
        color = "gold" if c["kind"] == "golden" else "black"
        plt.scatter([c["date"]], [c["price"]], marker=marker, s=140, color=color,
                    edgecolor="black", zorder=6,
                    label=("Golden cross" if c["kind"] == "golden" else "Death cross"))

    plt.title(f"{result['resolved_ticker']} - 1yr price with trend, SMA50/SMA200")
    plt.xlabel("Date")
    plt.ylabel(f"Price ({currency})")
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), fontsize=8)
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=150)
        print(f"Chart saved to {out_path}")
    if show:
        plt.show()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Project a stock's price N months out using a linear trend fit.")
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. AAPL, MSFT, TSLA, RELIANCE.NS")
    parser.add_argument("--months", type=float, default=3, help="Months ahead to project (default: 3)")
    parser.add_argument("--out", default=None, help="Path to save the chart PNG (default: <ticker>_trend.png)")
    parser.add_argument("--no-show", action="store_true", help="Don't open an interactive chart window")
    args = parser.parse_args()

    if args.no_show:
        matplotlib.use("Agg")

    try:
        result = analyze(args.ticker, args.months)
    except Exception as e:
        print(f"Error fetching data: {e}", file=sys.stderr)
        sys.exit(1)

    data = result["data"]
    symbol = result["symbol"]
    out_path = args.out or f"{result['resolved_ticker']}_trend.png"

    print(f"Ticker:                 {result['resolved_ticker']}")
    print(f"History window:         {data.index[0].date()} to {data.index[-1].date()} ({len(data)} trading days)")
    print(f"Current price:          {symbol}{result['current']:,.2f}")
    print(f"Linear trend slope:     {symbol}{result['slope']:,.4f} / trading day")
    print(f"Projected price (+{args.months:g} mo): {symbol}{result['projected']:,.2f}  ({result['change_pct']:+.2f}%)")

    if result["crosses"]:
        last = result["crosses"][-1]
        label = "Golden Cross (bullish)" if last["kind"] == "golden" else "Death Cross (bearish)"
        print(f"Latest SMA50/SMA200 signal: {label} on {last['date'].date()} at {symbol}{last['price']:,.2f}")
    else:
        print("Latest SMA50/SMA200 signal: none in the last 12 months")

    plot_trend(result, args.months, args.ticker, out_path, show=not args.no_show)


if __name__ == "__main__":
    main()
