import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="RSI Reversal Screener", page_icon="📉", layout="wide")

st.title("📉 RSI Reversal Screener — Buy the Dip")
st.caption("Finds strong stocks that have dipped too far and are bouncing back. High win rate strategy.")

st.info("""
**How this works (plain English):**
Good stocks sometimes fall too much in a short time (RSI drops below 35). 
When they start recovering, it's a great low-risk buying opportunity. 
This screener catches that exact moment — when a quality stock is cheap and turning up.
""")

NIFTY50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","HINDUNILVR.NS",
    "SBIN.NS","BHARTIARTL.NS","BAJFINANCE.NS","LT.NS","KOTAKBANK.NS","AXISBANK.NS",
    "ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TATAMOTORS.NS","WIPRO.NS","HCLTECH.NS",
    "TECHM.NS","DRREDDY.NS","DIVISLAB.NS","CIPLA.NS","ADANIPORTS.NS","ONGC.NS",
    "BPCL.NS","POWERGRID.NS","NTPC.NS","BAJAJ-AUTO.NS","M&M.NS","NESTLEIND.NS",
    "TITAN.NS","ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS",
    "INDUSINDBK.NS","GRASIM.NS","BRITANNIA.NS","HEROMOTOCO.NS","EICHERMOT.NS",
]

with st.sidebar:
    st.header("Settings")
    capital     = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct    = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    rsi_entry   = st.slider("RSI entry level (oversold below)", 25, 45, 35)
    rsi_confirm = st.slider("RSI recovery confirm (above)", 30, 50, 40)
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown(f"- RSI dipped below {rsi_entry} recently")
    st.markdown(f"- RSI now recovering above {rsi_confirm}")
    st.markdown("- Stock still above 200-day SMA (quality filter)")
    st.markdown("- Price bouncing off support (today green candle)")
    st.markdown("- Volume picking up on bounce day")
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

def analyse(df, ticker):
    df = df.copy()
    df['SMA200'] = df['Close'].rolling(200).mean()
    df['EMA50']  = df['Close'].ewm(span=50).mean()
    df['EMA20']  = df['Close'].ewm(span=20).mean()
    df['VolMA']  = df['Volume'].rolling(20).mean()
    d  = df['Close'].diff()
    g  = d.clip(lower=0).rolling(14).mean()
    l  = (-d.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100/(1 + g/l.replace(0,1e-9)))

    r     = df.iloc[-1]
    r_prev= df.iloc[-2]
    price = float(r['Close'])
    rsi   = float(r['RSI'])   if not pd.isna(r['RSI'])   else 50
    rsi_p = float(r_prev['RSI']) if not pd.isna(r_prev['RSI']) else 50

    # Key conditions
    rsi_was_oversold  = df['RSI'].iloc[-10:].min() < rsi_entry
    rsi_recovering    = rsi > rsi_confirm and rsi > rsi_p
    above_sma200      = price > float(r['SMA200']) if not pd.isna(r['SMA200']) else False
    green_candle      = float(r['Close']) > float(r_prev['Close'])
    vol_pickup        = float(r['Volume']) > float(r['VolMA']) * 1.1 if not pd.isna(r['VolMA']) else False

    # Support level = recent 20-day low
    support = float(df['Low'].iloc[-20:].min())
    atr     = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])
    stop    = round(support - atr * 0.5, 2)
    target  = round(price + atr * 3, 2)
    qty     = max(1, int((capital * risk_pct/100) / max(price - stop, 1)))

    score = sum([rsi_was_oversold, rsi_recovering, above_sma200, green_candle, vol_pickup])

    # Pullback % from 20-day high
    hi20 = float(df['Close'].iloc[-20:].max())
    pullback = round((hi20 - price)/hi20 * 100, 1)

    return {
        "Ticker":          ticker.replace(".NS",""),
        "Price ₹":         round(price, 2),
        "RSI now":         round(rsi, 1),
        "RSI was low":     "✅" if rsi_was_oversold else "❌",
        "RSI recovering":  "✅" if rsi_recovering   else "❌",
        "Above SMA200":    "✅" if above_sma200      else "❌",
        "Green candle":    "✅" if green_candle       else "❌",
        "Volume up":       "✅" if vol_pickup         else "❌",
        "Pullback %":      f"{pullback}%",
        "Score /5":        score,
        "Signal":          "🟢 BUY" if score >= 4 and above_sma200 else "🟡 WATCH" if score >= 3 else "⚪ SKIP",
        "Stop ₹":          stop,
        "Target ₹":        target,
        "Qty":             qty,
        "Pot profit ₹":    round((target - price) * qty, 0),
        "Max loss ₹":      round((price - stop) * qty, 0),
    }

if st.button("🔍 Find oversold bounces", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Scanning…")
    for i, t in enumerate(NIFTY50):
        bar.progress((i+1)/len(NIFTY50), f"Checking {t.replace('.NS','')}…")
        df = fetch(t)
        if df is not None:
            results.append(analyse(df, t))
    bar.empty()
    st.session_state["rsi_results"] = sorted(results, key=lambda x: x["Score /5"], reverse=True)

if "rsi_results" in st.session_state:
    res = st.session_state["rsi_results"]
    buys   = [r for r in res if "BUY"   in r["Signal"]]
    watchs = [r for r in res if "WATCH" in r["Signal"]]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Scanned",       len(res))
    c2.metric("Buy signals",   len(buys))
    c3.metric("Watch signals", len(watchs))
    c4.metric("Max risk/trade",f"₹{capital*risk_pct/100:,.0f}")

    st.divider()

    if buys:
        st.subheader("🟢 Strong bounce setups")
        df_b = pd.DataFrame(buys)[["Ticker","Price ₹","RSI now","Pullback %",
                                    "Stop ₹","Target ₹","Qty","Pot profit ₹","Max loss ₹"]]
        st.dataframe(df_b, use_container_width=True, hide_index=True)

        st.subheader("Checklist for buy signals")
        df_c = pd.DataFrame(buys)[["Ticker","RSI was low","RSI recovering",
                                    "Above SMA200","Green candle","Volume up","Score /5"]]
        st.dataframe(df_c, use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 Developing setups — watch these")
        df_w = pd.DataFrame(watchs)[["Ticker","Price ₹","RSI now","Score /5",
                                      "RSI was low","RSI recovering","Above SMA200"]]
        st.dataframe(df_w, use_container_width=True, hide_index=True)

    with st.expander("Show all stocks"):
        st.dataframe(pd.DataFrame(res)[["Ticker","Price ₹","RSI now","Score /5","Signal"]],
                     use_container_width=True, hide_index=True)
else:
    st.info("Click the button above to start scanning.")
