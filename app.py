"""
Stock trend agent (mobile-friendly web page).

Run locally with:
    streamlit run app.py

Then open the "Network URL" it prints (e.g. http://192.168.x.x:8501) on your
phone's browser, as long as the phone is on the same WiFi as this PC.
"""

import matplotlib.pyplot as plt
import streamlit as st
import streamlit.components.v1 as components

from stock_core import analyze

st.set_page_config(page_title="Stock Trend", page_icon="📈", layout="centered")

components.html(
    """
    <script>
    const doc = window.parent.document;
    if (!doc.querySelector('link[rel="manifest"]')) {
        const link = doc.createElement('link');
        link.rel = 'manifest';
        link.href = 'app/static/manifest.json';
        doc.head.appendChild(link);
        const meta = doc.createElement('meta');
        meta.name = 'theme-color';
        meta.content = '#0e1117';
        doc.head.appendChild(meta);
        const icon = doc.createElement('link');
        icon.rel = 'apple-touch-icon';
        icon.href = 'app/static/icon-192.png';
        doc.head.appendChild(icon);
    }
    </script>
    """,
    height=0,
)

st.title("📈 Stock Trend Projection")
st.caption("1-year price history with a linear trend line extrapolated forward.")

ticker = st.text_input("Ticker symbol", value="AAPL",
                        help="US symbol (AAPL, MSFT) or NSE/BSE symbol (RELIANCE, TCS, INFY) "
                             "— NSE/BSE is tried automatically if no suffix is given.").strip()
months = st.slider("Months ahead to project", min_value=1, max_value=12, value=3)
run = st.button("Analyze", type="primary", use_container_width=True)

if run and ticker:
    with st.spinner(f"Fetching {ticker.upper()} and fitting trend..."):
        try:
            result = analyze(ticker, months)
        except Exception as e:
            st.error(f"Couldn't fetch data for '{ticker}': {e}")
            st.stop()

    data = result["data"]
    symbol = result["symbol"]
    currency = result["currency"]

    if result["resolved_ticker"] != ticker.upper():
        st.caption(f"Matched to **{result['resolved_ticker']}**")

    col1, col2, col3 = st.columns(3)
    col1.metric("Current price", f"{symbol}{result['current']:,.2f}")
    col2.metric(f"Projected (+{months} mo)", f"{symbol}{result['projected']:,.2f}",
                f"{result['change_pct']:+.2f}%")
    col3.metric("Trend slope", f"{symbol}{result['slope']:,.4f}/day")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(data.index, data["Close"], label="Actual close price", color="tab:blue")
    ax.plot(data.index, result["trend_hist"], label="Linear trend (fit)", color="tab:orange", linestyle="--")
    ax.plot(result["future_dates"], result["trend_future"], label=f"Projection (+{months} mo)",
            color="tab:red", linestyle="--")
    if result["future_dates"]:
        ax.scatter([result["future_dates"][-1]], [result["projected"]], color="tab:red", zorder=5)

    ax.plot(data.index, data["SMA50"], label="SMA 50", color="tab:green", linewidth=1.2)
    ax.plot(data.index, data["SMA200"], label="SMA 200", color="tab:purple", linewidth=1.2)
    for c in result["crosses"]:
        marker = "^" if c["kind"] == "golden" else "v"
        color = "gold" if c["kind"] == "golden" else "black"
        ax.scatter([c["date"]], [c["price"]], marker=marker, s=140, color=color,
                   edgecolor="black", zorder=6,
                   label=("Golden cross" if c["kind"] == "golden" else "Death cross"))

    ax.set_title(f"{result['resolved_ticker']} - 1yr price with trend, SMA50/SMA200")
    ax.set_xlabel("Date")
    ax.set_ylabel(f"Price ({currency})")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    st.pyplot(fig, use_container_width=True)

    if result["crosses"]:
        last = result["crosses"][-1]
        if last["kind"] == "golden":
            st.success(
                f"🟡 Golden Cross on {last['date'].date()}: SMA50 moved above SMA200 "
                f"at {symbol}{last['price']:,.2f} — traditionally read as bullish."
            )
        else:
            st.warning(
                f"⚫ Death Cross on {last['date'].date()}: SMA50 moved below SMA200 "
                f"at {symbol}{last['price']:,.2f} — traditionally read as bearish."
            )
    else:
        st.info("No Golden Cross / Death Cross occurred in the last 12 months.")

    st.caption(
        "Trend line is a naive linear extrapolation of the past year of prices. "
        "SMA50/SMA200 crosses are a lagging signal, not a prediction. Not investment advice."
    )
else:
    st.info("Enter a ticker and tap **Analyze** to see the trend and projection.")
