import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Trend Strength Screener", page_icon="📈", layout="wide")

st.title("📈 Trend Strength Screener — Ride the Strongest Trends")
st.caption("Uses ADX to find stocks with the most powerful, consistent trends. Trade with the wind, not against it.")

st.info("""
**How this works (plain English):**
ADX (Average Directional Index) measures how STRONG a trend is — not just direction, but strength. 
An ADX above 25 means a strong trend. Above 40 means a very strong trend. 
This screener finds stocks in powerful uptrends so you are always trading with momentum behind you.
""")

STOCKS_ALL = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","HINDUNILVR.NS",
    "SBIN.NS","BHARTIARTL.NS","BAJFINANCE.NS","LT.NS","KOTAKBANK.NS","AXISBANK.NS",
    "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TATAMOTORS.NS","WIPRO.NS","HCLTECH.NS",
    "TECHM.NS","DRREDDY.NS","CIPLA.NS","ADANIPORTS.NS","ONGC.NS","POWERGRID.NS",
    "NTPC.NS","BAJAJ-AUTO.NS","M&M.NS","TITAN.NS","BRITANNIA.NS","HEROMOTOCO.NS",
    "NESTLEIND.NS","ULTRACEMCO.NS","JSWSTEEL.NS","HINDALCO.NS","EICHERMOT.NS",
]

with st.sidebar:
    st.header("Settings")
    capital    = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct   = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    adx_min    = st.slider("Minimum ADX (trend strength)", 20, 45, 25)
    st.divider()
    st.markdown("**What ADX means:**")
    st.markdown("- Below 20 = Weak/No trend (avoid)")
    st.markdown("- 20–25 = Developing trend")
    st.markdown("- 25–40 = **Strong trend ✅**")
    st.markdown("- Above 40 = **Very strong trend 🔥**")
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown(f"- ADX above {adx_min}")
    st.markdown("- +DI above -DI (uptrend not downtrend)")
    st.markdown("- Price above EMA20 and EMA50")
    st.markdown("- RSI between 45–70")
    st.caption("Not SEBI-registered advice.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker):
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
        if df.empty or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except: return None

def calc_adx(df, period=14):
    df = df.copy()
    df['H-L']   = df['High'] - df['Low']
    df['H-PC']  = (df['High'] - df['Close'].shift()).abs()
    df['L-PC']  = (df['Low']  - df['Close'].shift()).abs()
    df['TR']    = df[['H-L','H-PC','L-PC']].max(axis=1)
    df['DMp']   = np.where((df['High']-df['High'].shift()) > (df['Low'].shift()-df['Low']),
                            np.maximum(df['High']-df['High'].shift(), 0), 0)
    df['DMn']   = np.where((df['Low'].shift()-df['Low']) > (df['High']-df['High'].shift()),
                            np.maximum(df['Low'].shift()-df['Low'], 0), 0)
    df['ATR']   = df['TR'].ewm(span=period, adjust=False).mean()
    df['DIp']   = 100 * df['DMp'].ewm(span=period, adjust=False).mean() / df['ATR'].replace(0,1e-9)
    df['DIn']   = 100 * df['DMn'].ewm(span=period, adjust=False).mean() / df['ATR'].replace(0,1e-9)
    df['DX']    = 100 * (df['DIp'] - df['DIn']).abs() / (df['DIp'] + df['DIn']).replace(0,1e-9)
    df['ADX']   = df['DX'].ewm(span=period, adjust=False).mean()
    return df

def analyse(df, ticker):
    df  = calc_adx(df)
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    d = df['Close'].diff()
    g = d.clip(lower=0).rolling(14).mean()
    l = (-d.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100/(1 + g/l.replace(0,1e-9)))

    r     = df.iloc[-1]
    price = float(r['Close'])
    adx   = float(r['ADX']) if not pd.isna(r['ADX']) else 0
    dip   = float(r['DIp']) if not pd.isna(r['DIp']) else 0
    din   = float(r['DIn']) if not pd.isna(r['DIn']) else 0
    rsi   = float(r['RSI']) if not pd.isna(r['RSI']) else 50
    e20   = float(r['EMA20']) if not pd.isna(r['EMA20']) else price
    e50   = float(r['EMA50']) if not pd.isna(r['EMA50']) else price
    atr   = float(r['ATR'])  if not pd.isna(r['ATR'])  else price*0.02

    strong_adx = adx >= adx_min
    uptrend    = dip > din
    above_emas = price > e20 and price > e50
    rsi_ok     = 45 <= rsi <= 70
    adx_rising = adx > float(df['ADX'].iloc[-3]) if len(df) > 3 else True

    score = sum([strong_adx, uptrend, above_emas, rsi_ok, adx_rising])

    stop   = round(e20 - atr, 2)
    target = round(price + atr * 3, 2)
    qty    = max(1, int((capital * risk_pct/100) / max(price - stop, 1)))

    trend_str = "🔥 Very strong" if adx >= 40 else "✅ Strong" if adx >= 25 else "⚠️ Weak"

    return {
        "Ticker":        ticker.replace(".NS",""),
        "Price ₹":       round(price, 2),
        "ADX":           round(adx, 1),
        "Trend":         trend_str,
        "+DI":           round(dip, 1),
        "-DI":           round(din, 1),
        "RSI":           round(rsi, 1),
        "Strong trend":  "✅" if strong_adx  else "❌",
        "Uptrend":       "✅" if uptrend     else "❌",
        "Above EMAs":    "✅" if above_emas  else "❌",
        "RSI ok":        "✅" if rsi_ok      else "❌",
        "ADX rising":    "✅" if adx_rising  else "❌",
        "Score /5":      score,
        "Signal":        "🟢 BUY" if score >= 4 and uptrend else "🟡 WATCH" if score >= 3 else "⚪ SKIP",
        "Stop ₹":        stop,
        "Target ₹":      target,
        "Qty":           qty,
    }

if st.button("🔍 Find strongest trends", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Calculating trend strength…")
    for i, t in enumerate(STOCKS_ALL):
        bar.progress((i+1)/len(STOCKS_ALL), f"Analysing {t.replace('.NS','')}…")
        df = fetch(t)
        if df is not None:
            results.append(analyse(df, t))
    bar.empty()
    st.session_state["adx_results"] = sorted(results, key=lambda x: (x["Score /5"], float(x["ADX"])), reverse=True)

if "adx_results" in st.session_state:
    res = st.session_state["adx_results"]
    buys   = [r for r in res if "BUY"   in r["Signal"]]
    watchs = [r for r in res if "WATCH" in r["Signal"]]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Scanned",       len(res))
    c2.metric("Buy signals",   len(buys))
    c3.metric("Watch signals", len(watchs))
    c4.metric("Max risk/trade",f"₹{capital*risk_pct/100:,.0f}")
    st.divider()

    if buys:
        st.subheader("🟢 Strongest uptrends right now")
        st.dataframe(pd.DataFrame(buys)[["Ticker","Price ₹","ADX","Trend","+DI","-DI",
                                          "RSI","Stop ₹","Target ₹","Qty"]],
                     use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 Developing trends")
        st.dataframe(pd.DataFrame(watchs)[["Ticker","Price ₹","ADX","Trend","Score /5",
                                            "Strong trend","Uptrend","Above EMAs"]],
                     use_container_width=True, hide_index=True)

    with st.expander("All stocks — sorted by trend strength"):
        st.dataframe(pd.DataFrame(res)[["Ticker","Price ₹","ADX","Trend","Signal","Score /5"]],
                     use_container_width=True, hide_index=True)
else:
    st.info("Click the button above to scan for strong trends.")
