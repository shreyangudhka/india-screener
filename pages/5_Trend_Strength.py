import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Trend Strength — All NSE+BSE", page_icon="📈", layout="wide")

st.markdown("""
<style>
    :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--green:#3fb950;
          --red:#f85149;--blue:#58a6ff;--gold:#ffa657;--text:#c9d1d9;--muted:#8b949e;}
    .stApp{background-color:var(--bg);color:var(--text);}
    div[data-testid="stSidebarContent"]{background:#0d1117;}
    .stButton>button{background:linear-gradient(135deg,#1a6b3c,#0f4028);color:white;
        border:1px solid var(--green);border-radius:8px;font-weight:700;
        font-size:1rem;padding:10px 24px;width:100%;}
    .stButton>button:hover{background:linear-gradient(135deg,#26a641,#1a6b3c);}
    .metric-card{background:var(--card);border:1px solid var(--border);
        border-radius:10px;padding:14px 18px;text-align:center;margin-bottom:8px;}
    .metric-val{font-size:1.8rem;font-weight:800;}
    .metric-lbl{font-size:0.75rem;color:var(--muted);margin-top:2px;}
</style>""", unsafe_allow_html=True)

st.title("📈 Trend Strength Screener — ADX Rankings | All NSE + BSE")
st.caption("Scans all ~5,500+ stocks. Finds the strongest, most powerful uptrends using ADX.")

st.markdown("""
<div style='background:#161b22;border-left:4px solid #bc8cff;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0;font-size:0.88rem;color:#c9d1d9'>
<b>How this works:</b> ADX (Average Directional Index) measures how STRONG a trend is.
ADX above 25 = strong trend. Above 40 = very strong. This screener ranks all stocks by trend strength
so you always trade with momentum behind you. <b>Best combined with VCP screener.</b>
</div>""", unsafe_allow_html=True)

# ── Load universe ─────────────────────────────────────────────────────────────
try:
    from stocks_universe import get_all_stocks
    @st.cache_data(ttl=86400, show_spinner=False)
    def load_universe():
        return get_all_stocks()
    ALL_STOCKS_DATA = load_universe()
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)
except Exception:
    _FALLBACK = [
        "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN","BAJFINANCE",
        "BHARTIARTL","ITC","KOTAKBANK","LT","HCLTECH","ASIANPAINT","AXISBANK","MARUTI",
        "SUNPHARMA","TITAN","ULTRACEMCO","NTPC","ONGC","POWERGRID","WIPRO","NESTLEIND",
        "TATAMOTORS","TECHM","DIVISLAB","ADANIENT","ADANIPORTS","JSWSTEEL","TATASTEEL",
        "CIPLA","BRITANNIA","HINDALCO","EICHERMOT","DRREDDY","BPCL","INDUSINDBK",
        "HEROMOTOCO","BAJAJ-AUTO","M&M","KPITTECH","PERSISTENT","COFORGE","MPHASIS",
        "TANLA","DEEPAKNITRI","NAVINFLUOR","FINEORG","IRCTC","TATAPOWER","DMART",
        "SIEMENS","HAVELLS","PIDILITIND","BERGEPAINT","MUTHOOTFIN","LUPIN","BIOCON",
        "GLAND","ALKEM","AMBUJACEM","SHRIRAMFIN","CHOLAFIN","BANDHANBNK","FEDERALBNK",
        "IDFCFIRSTB","GREENPANEL","CENTURYPLY","POLYCAB","DIXON","AMBER","VGUARD",
        "ASTRAL","BEL","HAL","GODREJPROP","MANAPPURAM","UJJIVAN","CREDITACC",
        "TATAELXSI","BALKRISIND","ENDURANCE","COLPAL","DABUR","MARICO","EMAMILTD",
        "LAURUSLABS","GRANULES","INTELLECT","MASTEK","NEWGEN","GALAXYSURF","NOCIL",
        "AAVAS","HOMEFIRST","EQUITASBNK","SUPREMEIND","RATNAMANI","PCBL","PAGEIND",
    ]
    ALL_STOCKS_DATA = [{"symbol":s,"name":s,"exchange":"NSE","yf_ticker":f"{s}.NS"} for s in _FALLBACK]
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    capital     = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct    = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    adx_min     = st.slider("Minimum ADX (trend strength)", 20, 45, 25)
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    max_workers = st.slider("Parallel workers", 1, 10, 5)
    min_price   = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price   = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.markdown("**What ADX means:**")
    st.markdown("- Below 20 = Weak/No trend (avoid)")
    st.markdown("- 20–25 = Developing trend")
    st.markdown("- 25–40 = **Strong trend ✅**")
    st.markdown("- Above 40 = **Very strong trend 🔥**")
    st.caption("Not SEBI-registered advice.")

# ── ADX CALCULATION ───────────────────────────────────────────────────────────
def calc_adx(df, period=14):
    df = df.copy()
    df['H-L']  = df['High'] - df['Low']
    df['H-PC'] = (df['High'] - df['Close'].shift()).abs()
    df['L-PC'] = (df['Low']  - df['Close'].shift()).abs()
    df['TR']   = df[['H-L','H-PC','L-PC']].max(axis=1)
    df['DMp']  = np.where((df['High']-df['High'].shift()) > (df['Low'].shift()-df['Low']),
                           np.maximum(df['High']-df['High'].shift(), 0), 0)
    df['DMn']  = np.where((df['Low'].shift()-df['Low']) > (df['High']-df['High'].shift()),
                           np.maximum(df['Low'].shift()-df['Low'], 0), 0)
    df['ATR']  = df['TR'].ewm(span=period, adjust=False).mean()
    df['DIp']  = 100 * df['DMp'].ewm(span=period, adjust=False).mean() / df['ATR'].replace(0,1e-9)
    df['DIn']  = 100 * df['DMn'].ewm(span=period, adjust=False).mean() / df['ATR'].replace(0,1e-9)
    df['DX']   = 100 * (df['DIp']-df['DIn']).abs() / (df['DIp']+df['DIn']).replace(0,1e-9)
    df['ADX']  = df['DX'].ewm(span=period, adjust=False).mean()
    return df

def fetch_and_score(stock_info: dict) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, timeout=15)
        if df is None or len(df) < 60:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        df  = calc_adx(df)
        df['EMA20'] = df['Close'].ewm(span=20).mean()
        df['EMA50'] = df['Close'].ewm(span=50).mean()
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + g / l.replace(0, 1e-9)))

        r     = df.iloc[-1]
        price = float(r['Close'])
        if not (min_price <= price <= max_price):
            return None

        adx   = float(r['ADX']) if not pd.isna(r['ADX']) else 0
        dip   = float(r['DIp']) if not pd.isna(r['DIp']) else 0
        din   = float(r['DIn']) if not pd.isna(r['DIn']) else 0
        rsi   = float(r['RSI']) if not pd.isna(r['RSI']) else 50
        e20   = float(r['EMA20']) if not pd.isna(r['EMA20']) else price
        e50   = float(r['EMA50']) if not pd.isna(r['EMA50']) else price
        atr   = float(r['ATR'])   if not pd.isna(r['ATR'])   else price * 0.02

        if adx < adx_min:
            return None

        strong_adx  = adx >= adx_min
        uptrend     = dip > din
        above_emas  = price > e20 and price > e50
        rsi_ok      = 45 <= rsi <= 70
        adx_rising  = adx > float(df['ADX'].iloc[-3]) if len(df) > 3 else True

        score = sum([strong_adx, uptrend, above_emas, rsi_ok, adx_rising])
        if score < 3:
            return None

        signal = "BUY" if score >= 4 and uptrend else "WATCH" if score >= 3 else "SKIP"
        if signal == "SKIP":
            return None

        trend_str = "🔥 Very strong" if adx >= 40 else "✅ Strong" if adx >= 25 else "⚠️ Weak"
        stop      = round(e20 - atr, 2)
        target    = round(price + atr * 3, 2)
        qty       = max(1, int((capital * risk_pct / 100) / max(price - stop, 0.01)))

        return {
            "Ticker":       stock_info["symbol"],
            "Name":         stock_info.get("name", stock_info["symbol"])[:28],
            "Exchange":     stock_info.get("exchange","NSE"),
            "Price ₹":      round(price, 2),
            "ADX":          round(adx, 1),
            "Trend":        trend_str,
            "+DI":          round(dip, 1),
            "-DI":          round(din, 1),
            "RSI":          round(rsi, 1),
            "Strong trend": "✅" if strong_adx  else "❌",
            "Uptrend":      "✅" if uptrend     else "❌",
            "Above EMAs":   "✅" if above_emas  else "❌",
            "RSI ok":       "✅" if rsi_ok      else "❌",
            "ADX rising":   "✅" if adx_rising  else "❌",
            "Score /5":     score,
            "Signal":       signal,
            "Stop ₹":       stop,
            "Target ₹":     target,
            "Qty":          qty,
            "PotProfit ₹":  round((target - price) * qty, 0),
            "MaxLoss ₹":    round((price - stop) * qty, 0),
        }
    except Exception:
        return None

# ── MAIN ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, color in [
    (c1, f"{UNIVERSE_SIZE:,}", "Stocks Universe", "#58a6ff"),
    (c2, f"ADX ≥ {adx_min}", "Trend Filter", "#3fb950"),
    (c3, "ADX + DI", "Indicators", "#ffa657"),
    (c4, "Combine with VCP", "Pro Tip", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
st.markdown("---")

if st.button("🔍 Find strongest trends across ALL stocks", use_container_width=True):
    stocks_to_scan = [s for s in ALL_STOCKS_DATA if s.get("exchange","NSE") in exchange_filter]
    total = len(stocks_to_scan)
    st.info(f"Scanning **{total:,} stocks** | Minimum ADX: {adx_min}")

    prog, prog_txt = st.progress(0), st.empty()
    results, scanned = [], 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_and_score, s): s for s in stocks_to_scan}
        for fut in as_completed(futures):
            scanned += 1
            try:
                r = fut.result()
                if r: results.append(r)
            except Exception: pass
            if scanned % 20 == 0 or scanned == total:
                prog.progress(scanned / total)
                prog_txt.markdown(f"Scanned **{scanned:,}/{total:,}** | Found: **{len(results)}** strong trends")

    prog.progress(1.0)
    results.sort(key=lambda x: (x["Score /5"], x["ADX"]), reverse=True)
    st.session_state["adx_results"] = results
    st.success(f"✅ Done! Found **{len(results)}** strong trend stocks from {total:,} scanned.")

if "adx_results" in st.session_state:
    res    = st.session_state["adx_results"]
    buys   = [r for r in res if r["Signal"] == "BUY"]
    watchs = [r for r in res if r["Signal"] == "WATCH"]
    v_strong = [r for r in buys if r["ADX"] >= 40]

    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in [(c1,len(res),"Total found"),(c2,len(v_strong),"🔥 Very strong (ADX≥40)"),
                           (c3,len(buys),"BUY signals"),(c4,len(watchs),"WATCH signals")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    cols_show  = ["Ticker","Name","Exchange","Price ₹","ADX","Trend","+DI","-DI","RSI","Stop ₹","Target ₹","Qty","PotProfit ₹"]
    cols_check = ["Ticker","Name","ADX","Strong trend","Uptrend","Above EMAs","RSI ok","ADX rising","Score /5"]

    if v_strong:
        st.subheader("🔥 Very strong trends (ADX ≥ 40) — highest conviction")
        st.dataframe(pd.DataFrame(v_strong)[cols_show], use_container_width=True, hide_index=True)

    if buys:
        st.subheader("🟢 Strong uptrends — BUY signals")
        st.dataframe(pd.DataFrame(buys)[cols_show], use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame(buys)[cols_check], use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 Developing trends — WATCH")
        st.dataframe(pd.DataFrame(watchs)[cols_check], use_container_width=True, hide_index=True)

    with st.expander("📋 Full ranked results"):
        st.dataframe(pd.DataFrame(res)[cols_show], use_container_width=True, hide_index=True)
else:
    st.info(f"👆 Click the scan button to rank all {UNIVERSE_SIZE:,} stocks by trend strength.")
    st.markdown("""
    **Pro tip:** Use this screener alongside the VCP Screener.
    If a stock has a VCP Score 6-7 AND ADX above 30, it's a very high conviction setup —
    strong trend + contraction pattern = explosive breakout potential.
    """)
