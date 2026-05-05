import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Volume Surge Screener", page_icon="📊", layout="wide")

st.title("📊 Volume Surge Screener — Follow the Big Money")
st.caption("When big institutions buy, volume explodes. This screener catches them in the act.")

st.info("""
**How this works (plain English):**
Big mutual funds and FIIs cannot hide when they are buying — their trades show up as 
massive spikes in trading volume (3× or more the normal). When volume surges AND 
the price goes up on that day, it means smart money is accumulating. You follow them in.
""")

STOCKS_ALL = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","HINDUNILVR.NS",
    "SBIN.NS","BHARTIARTL.NS","BAJFINANCE.NS","LT.NS","KOTAKBANK.NS","AXISBANK.NS",
    "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TATAMOTORS.NS","WIPRO.NS","HCLTECH.NS",
    "TECHM.NS","DRREDDY.NS","DIVISLAB.NS","CIPLA.NS","ADANIPORTS.NS","ONGC.NS",
    "BPCL.NS","POWERGRID.NS","NTPC.NS","BAJAJ-AUTO.NS","M&M.NS","TITAN.NS",
    "ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS","BRITANNIA.NS",
]

with st.sidebar:
    st.header("Settings")
    capital      = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct     = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    vol_threshold= st.slider("Volume surge (× normal)", 1.5, 5.0, 2.5, 0.5)
    lookback     = st.slider("Look for surge in last N days", 1, 5, 2)
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown(f"- Volume {vol_threshold}× the 20-day average")
    st.markdown("- Price closed UP on the surge day")
    st.markdown("- Stock above EMA50 (uptrend)")
    st.markdown("- RSI not overbought (below 70)")
    st.markdown("- Enter next day on open")
    st.markdown("- Stop below surge day's low")
    st.caption("Not SEBI-registered advice.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker):
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
        if df.empty or len(df) < 30: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except: return None

def analyse(df, ticker):
    df = df.copy()
    df['EMA50']  = df['Close'].ewm(span=50).mean()
    df['EMA20']  = df['Close'].ewm(span=20).mean()
    df['VolMA20']= df['Volume'].rolling(20).mean()
    d = df['Close'].diff()
    g = d.clip(lower=0).rolling(14).mean()
    l = (-d.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100/(1 + g/l.replace(0,1e-9)))
    df['VolRatio'] = df['Volume'] / df['VolMA20']
    df['UpDay']    = df['Close'] > df['Close'].shift(1)

    # Check last N days for surge
    recent = df.iloc[-lookback:]
    surge_rows = recent[recent['VolRatio'] >= vol_threshold]

    if surge_rows.empty:
        return None

    surge_row   = surge_rows.iloc[-1]
    latest      = df.iloc[-1]
    price       = float(latest['Close'])
    rsi         = float(latest['RSI'])   if not pd.isna(latest['RSI'])   else 50
    ema50       = float(latest['EMA50']) if not pd.isna(latest['EMA50']) else price
    vol_ratio   = float(surge_row['VolRatio'])
    up_on_surge = bool(surge_row['UpDay'])
    above_ema   = price > ema50
    rsi_ok      = rsi < 70
    not_extended= price < float(latest['EMA20']) * 1.08 if not pd.isna(latest['EMA20']) else True

    score = sum([vol_ratio >= vol_threshold, up_on_surge, above_ema, rsi_ok, not_extended])

    # Stop below the low of surge day
    stop   = round(float(surge_row['Low']) * 0.99, 2)
    atr    = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])
    target = round(price + atr * 3, 2)
    qty    = max(1, int((capital * risk_pct/100) / max(price - stop, 1)))

    surge_date = surge_row.name.strftime('%d %b') if hasattr(surge_row.name, 'strftime') else "recent"

    return {
        "Ticker":        ticker.replace(".NS",""),
        "Price ₹":       round(price, 2),
        "Surge date":    surge_date,
        "Vol ratio":     f"{vol_ratio:.1f}×",
        "Up on surge":   "✅" if up_on_surge else "❌",
        "Above EMA50":   "✅" if above_ema   else "❌",
        "RSI ok":        "✅" if rsi_ok      else "❌",
        "Not extended":  "✅" if not_extended else "❌",
        "RSI":           round(rsi, 1),
        "Score /5":      score,
        "Signal":        "🟢 BUY" if score >= 4 and up_on_surge else "🟡 WATCH" if score >= 3 else "⚪ SKIP",
        "Stop ₹":        stop,
        "Target ₹":      target,
        "Qty":           qty,
    }

if st.button("🔍 Detect volume surges", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Detecting unusual volume…")
    for i, t in enumerate(STOCKS_ALL):
        bar.progress((i+1)/len(STOCKS_ALL), f"Checking {t.replace('.NS','')}…")
        df = fetch(t)
        if df is not None:
            r = analyse(df, t)
            if r: results.append(r)
    bar.empty()
    st.session_state["vol_results"] = sorted(results, key=lambda x: x["Score /5"], reverse=True)

if "vol_results" in st.session_state:
    res = st.session_state["vol_results"]
    if not res:
        st.warning("No volume surges detected today. Check back tomorrow or lower the threshold.")
    else:
        buys   = [r for r in res if "BUY"   in r["Signal"]]
        watchs = [r for r in res if "WATCH" in r["Signal"]]

        c1,c2,c3 = st.columns(3)
        c1.metric("Stocks with surges", len(res))
        c2.metric("Buy signals",        len(buys))
        c3.metric("Watch signals",      len(watchs))
        st.divider()

        if buys:
            st.subheader("🟢 Institutional buying detected")
            st.dataframe(pd.DataFrame(buys)[["Ticker","Price ₹","Surge date","Vol ratio",
                                              "RSI","Stop ₹","Target ₹","Qty"]],
                         use_container_width=True, hide_index=True)

        if watchs:
            st.subheader("🟡 Watch — surge detected but not all criteria met")
            st.dataframe(pd.DataFrame(watchs)[["Ticker","Price ₹","Vol ratio","Up on surge",
                                                "Above EMA50","RSI ok","Score /5"]],
                         use_container_width=True, hide_index=True)

        with st.expander("All stocks with recent volume surges"):
            st.dataframe(pd.DataFrame(res)[["Ticker","Price ₹","Vol ratio","Signal","Score /5"]],
                         use_container_width=True, hide_index=True)
else:
    st.info("Click the button above to scan for unusual volume.")
