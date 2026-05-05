import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Momentum Screener", page_icon="🚀", layout="wide")

st.markdown("""
<style>
.win  { color: #155724; font-weight: 700; }
.lose { color: #721c24; font-weight: 700; }
.card { background:#f8f9fa; border-radius:10px; padding:14px; margin-bottom:8px; }
</style>""", unsafe_allow_html=True)

st.title("🚀 Momentum Screener — 52-Week High Breakouts")
st.caption("Finds stocks making new highs with strong volume. Simple, proven, powerful.")

st.info("""
**How this works (plain English):**
Stocks that make new 52-week highs tend to keep going up. This screener finds them early — 
when they just broke out on high volume. You buy, set a stop 5% below, target 10-15% above.
""")

STOCKS = {
    "Large Cap": ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
                  "HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS","BAJFINANCE.NS","LT.NS",
                  "KOTAKBANK.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS"],
    "Mid Cap":   ["TATAMOTORS.NS","WIPRO.NS","TECHM.NS","HCLTECH.NS","DRREDDY.NS",
                  "DIVISLAB.NS","CIPLA.NS","ADANIPORTS.NS","ONGC.NS","BPCL.NS",
                  "POWERGRID.NS","NTPC.NS","BAJAJ-AUTO.NS","M&M.NS","NESTLEIND.NS"],
}

with st.sidebar:
    st.header("Settings")
    capital    = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct   = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    stop_pct   = st.slider("Stop loss % below entry", 3, 8, 5)
    target_mul = st.slider("Target (× stop distance)", 1.5, 4.0, 2.5, 0.5)
    sel_cap    = st.multiselect("Universe", list(STOCKS.keys()), default=list(STOCKS.keys()))
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown("- Price within 3% of 52W high")
    st.markdown("- Volume 1.5× 20-day average")
    st.markdown("- RSI above 55 (momentum)")
    st.markdown("- Above 50-day EMA")
    st.caption("Not SEBI-registered advice.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except: return None

def analyse(df, ticker):
    df = df.copy()
    df['EMA50']  = df['Close'].ewm(span=50).mean()
    df['VolMA20']= df['Volume'].rolling(20).mean()
    d = df['Close'].diff()
    g = d.clip(lower=0).rolling(14).mean()
    l = (-d.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100/(1 + g/l.replace(0,1e-9)))
    r = df.iloc[-1]
    price  = float(r['Close'])
    hi52   = float(df['Close'].rolling(252).max().iloc[-1])
    near52 = (price / hi52) >= 0.97
    vol_ok = float(r['Volume']) > float(r['VolMA20']) * 1.5 if not pd.isna(r['VolMA20']) else False
    rsi    = float(r['RSI']) if not pd.isna(r['RSI']) else 50
    rsi_ok = rsi > 55
    ema_ok = price > float(r['EMA50']) if not pd.isna(r['EMA50']) else False
    score  = sum([near52, vol_ok, rsi_ok, ema_ok])
    pct_from_hi = round((price/hi52 - 1)*100, 1)
    vol_ratio   = round(float(r['Volume'])/float(r['VolMA20']), 1) if not pd.isna(r['VolMA20']) else 0
    stop   = round(price * (1 - stop_pct/100), 2)
    target = round(price + (price - stop) * target_mul, 2)
    qty    = max(1, int((capital * risk_pct/100) / (price - stop)))
    return {
        "Ticker": ticker.replace(".NS",""),
        "Price ₹": round(price,2),
        "52W High ₹": round(hi52,2),
        "From high %": f"{pct_from_hi}%",
        "Volume ratio": f"{vol_ratio}×",
        "RSI": round(rsi,1),
        "Score /4": score,
        "Signal": "🟢 BUY" if score==4 else "🟡 WATCH" if score>=3 else "⚪ SKIP",
        "Stop ₹": stop,
        "Target ₹": target,
        "Qty": qty,
        "Near 52W high": "✅" if near52 else "❌",
        "Volume surge": "✅" if vol_ok else "❌",
        "RSI > 55": "✅" if rsi_ok else "❌",
        "Above EMA50": "✅" if ema_ok else "❌",
    }

tickers = [s for cap, lst in STOCKS.items() for s in lst if cap in sel_cap]

if st.button("🔍 Scan for momentum breakouts", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Fetching data…")
    for i, t in enumerate(tickers):
        bar.progress((i+1)/len(tickers), f"Scanning {t.replace('.NS','')}…")
        df = fetch(t)
        if df is not None:
            results.append(analyse(df, t))
    bar.empty()
    st.session_state["mom_results"] = results

if "mom_results" in st.session_state:
    res = st.session_state["mom_results"]
    buys   = [r for r in res if "BUY"   in r["Signal"]]
    watchs = [r for r in res if "WATCH" in r["Signal"]]

    c1,c2,c3 = st.columns(3)
    c1.metric("Scanned", len(res))
    c2.metric("Buy signals", len(buys))
    c3.metric("Watch signals", len(watchs))

    st.divider()

    if buys:
        st.subheader("🟢 Buy signals — all 4 criteria met")
        df_buy = pd.DataFrame(buys)[["Ticker","Price ₹","52W High ₹","From high %",
                                      "Volume ratio","RSI","Stop ₹","Target ₹","Qty"]]
        st.dataframe(df_buy, use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 Watch list — 3 of 4 criteria met")
        df_w = pd.DataFrame(watchs)[["Ticker","Price ₹","Near 52W high","Volume surge","RSI > 55","Above EMA50","Score /4"]]
        st.dataframe(df_w, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Full results")
    df_all = pd.DataFrame(res).sort_values("Score /4", ascending=False)
    st.dataframe(df_all[["Ticker","Price ₹","Score /4","Signal","Near 52W high",
                           "Volume surge","RSI > 55","Above EMA50"]],
                 use_container_width=True, hide_index=True)
else:
    st.info("Click the button above to scan stocks.")
