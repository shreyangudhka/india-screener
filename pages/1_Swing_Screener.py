import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Swing Screener — All NSE+BSE", page_icon="🔄", layout="wide")

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
    .cap-large{background:#0f2a1a;color:#3fb950;padding:2px 8px;border-radius:4px;
               font-size:11px;font-weight:600;border:1px solid #3fb950;}
    .cap-mid  {background:#0f1a2a;color:#58a6ff;padding:2px 8px;border-radius:4px;
               font-size:11px;font-weight:600;border:1px solid #58a6ff;}
    .cap-small{background:#1a1500;color:#ffa657;padding:2px 8px;border-radius:4px;
               font-size:11px;font-weight:600;border:1px solid #ffa657;}
    .metric-card{background:var(--card);border:1px solid var(--border);
        border-radius:10px;padding:14px 18px;text-align:center;margin-bottom:8px;}
    .metric-val{font-size:1.8rem;font-weight:800;}
    .metric-lbl{font-size:0.75rem;color:var(--muted);margin-top:2px;}
</style>""", unsafe_allow_html=True)

st.title("🔄 Swing Trading Screener — All NSE + BSE Stocks")
st.caption("Scans all ~5,500+ listed stocks. Pullback and Breakout setups. Large + Mid + Small cap.")

# ── Load universal stock universe ─────────────────────────────────────────────
try:
    from stocks_universe import get_all_stocks
    @st.cache_data(ttl=86400, show_spinner=False)
    def load_universe():
        return get_all_stocks()
    ALL_STOCKS_DATA = load_universe()
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)
except Exception:
    # Fallback: large hardcoded list
    _FALLBACK = [
        "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN","BAJFINANCE",
        "BHARTIARTL","ITC","KOTAKBANK","LT","HCLTECH","ASIANPAINT","AXISBANK","MARUTI",
        "SUNPHARMA","TITAN","ULTRACEMCO","NTPC","ONGC","POWERGRID","BAJAJFINSV","WIPRO",
        "NESTLEIND","TATAMOTORS","TECHM","DIVISLAB","ADANIENT","ADANIPORTS","JSWSTEEL",
        "TATASTEEL","COALINDIA","CIPLA","GRASIM","BRITANNIA","HINDALCO","APOLLOHOSP",
        "EICHERMOT","DRREDDY","BPCL","INDUSINDBK","HEROMOTOCO","SHREECEM","SBILIFE",
        "HDFCLIFE","BAJAJ-AUTO","UPL","TATACONSUM","M&M","KPITTECH","PERSISTENT","LTTS",
        "COFORGE","MPHASIS","HAPPSTMNDS","TANLA","DEEPAKNITRI","NAVINFLUOR","FINEORG",
        "IRCTC","RVNL","TATAPOWER","ADANIGREEN","ZOMATO","DMART","SIEMENS","HAVELLS",
        "PIDILITIND","BERGEPAINT","MUTHOOTFIN","TORNTPHARM","LUPIN","BIOCON","GLAND",
        "ALKEM","APOLLOTYRE","AMBUJACEM","SHRIRAMFIN","CHOLAFIN","HDFCAMC","ICICIGI",
        "SBICARD","BANDHANBNK","FEDERALBNK","IDFCFIRSTB","RBLBANK","GREENPANEL",
        "CENTURYPLY","POLYCAB","DIXON","AMBER","VGUARD","ASTRAL","FINOLEX","SUPREMEIND",
        "BEL","HAL","BHEL","THERMAX","GODREJPROP","OBEROIRLTY","PRESTIGE","PHOENIXLTD",
        "MANAPPURAM","IIFL","UJJIVAN","CREDITACC","TATAELXSI","HEXAWARE","SONATASOFT",
        "CYIENT","ZENSAR","BALKRISIND","ENDURANCE","TIINDIA","SUNDRMFAST","MOTHERSON",
        "COLPAL","DABUR","MARICO","EMAMILTD","JYOTHY","RADICO","CESC","NHPC","SJVN",
        "SUZLON","INOXWIND","LAURUSLABS","GRANULES","ALKEM","IPCALAB","TORNTPOWER",
        "INTELLECT","MASTEK","NEWGEN","DATAMATICS","GALAXYSURF","NOCIL","SUDARSCHEM",
        "AAVAS","HOMEFIRST","EQUITASBNK","GABRIEL","SUBROS","LUMAXTECH","ROUTE",
        "APLAPOLLO","NILKAMAL","RATNAMANI","PCBL","ELGI","GRINDWELL","PAGEIND","KITEX",
    ]
    ALL_STOCKS_DATA = [{"symbol":s,"name":s,"exchange":"NSE","yf_ticker":f"{s}.NS"} for s in _FALLBACK]
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    capital    = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct   = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    max_risk   = capital * risk_pct / 100
    st.metric("Max risk/trade", f"₹{max_risk:,.0f}")
    st.divider()
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    min_score  = st.slider("Min score to show", 0, 10, 6)
    sig_filter = st.selectbox("Signal filter", ["All","BUY","WATCH"])
    max_workers= st.slider("Parallel workers", 1, 10, 5)
    batch_size = st.slider("Batch size", 10, 100, 40)
    min_price  = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price  = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.warning("⚠️ Small caps are more volatile. Position sizes are auto-reduced by 40%.")
    st.caption("Not SEBI-registered advice.")

# ── ANALYSIS FUNCTION ─────────────────────────────────────────────────────────
def fetch_and_score(stock_info: dict) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True, timeout=15)
        if df is None or len(df) < 55:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        df['EMA20']  = df['Close'].ewm(span=20).mean()
        df['EMA50']  = df['Close'].ewm(span=50).mean()
        df['SMA200'] = df['Close'].rolling(min(200, len(df))).mean()
        df['VolMA20']= df['Volume'].rolling(20).mean()
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + g / l.replace(0, 1e-9)))
        tr = pd.concat([df['High'] - df['Low'],
                        (df['High'] - df['Close'].shift()).abs(),
                        (df['Low']  - df['Close'].shift()).abs()], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean()

        r = df.iloc[-1]
        price  = float(r['Close'])
        if not (min_price <= price <= max_price):
            return None

        e50    = float(r['EMA50'])   if not pd.isna(r['EMA50'])   else price
        sma200 = float(r['SMA200'])  if not pd.isna(r['SMA200'])  else price
        rsi    = float(r['RSI'])     if not pd.isna(r['RSI'])     else 50
        vma    = float(r['VolMA20']) if not pd.isna(r['VolMA20']) else 1
        vol    = float(r['Volume'])
        atr    = float(r['ATR'])     if not pd.isna(r['ATR'])     else price * 0.02
        vol_ratio = vol / vma if vma > 0 else 1

        rhi  = float(df['Close'].rolling(20).max().iloc[-1])
        pb   = (rhi - price) / rhi * 100 if rhi > 0 else 0
        weekly = df['Close'].resample('W').last().dropna()
        weekly_up = (float(weekly.iloc[-1]) > float(weekly.iloc[-5])) if len(weekly) >= 5 else True

        score = 0
        if price > e50:      score += 2
        if price > sma200:   score += 2
        if 38 <= rsi <= 62:  score += 2
        if vol_ratio >= 1.2: score += 2
        if 3 <= pb <= 18:    score += 1
        if weekly_up:        score += 1

        hi52 = float(df['Close'].rolling(min(252, len(df))).max().iloc[-1])
        near52 = (price / hi52) > 0.97 if hi52 > 0 else False
        rw = float(df['Close'].iloc[-20:].max() - df['Close'].iloc[-20:].min()) / float(df['Close'].iloc[-20:].min()) * 100

        setup = ("52W High BO" if near52 and vol_ratio >= 1.5
                 else "Breakout" if rw < 8 and vol_ratio >= 1.5
                 else "Pullback" if 3 <= pb <= 18 and price > e50
                 else "MA Bounce" if abs(price - e50) / price * 100 < 1.5
                 else "Developing")

        if score < min_score:
            return None

        signal = "BUY" if score >= 8 and weekly_up else "WATCH" if score >= 5 else "SKIP"
        if sig_filter != "All" and signal != sig_filter:
            return None

        stop   = round(price - 1.5 * atr, 2)
        target = round(price + 3.0 * atr, 2)

        exch = stock_info.get("exchange", "NSE")
        cap  = ("Large" if price > 10000 or any(s in stock_info["symbol"] for s in
                ["RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","LT","BAJFINANCE"])
                else "Small" if price < 200 else "Mid")
        risk_mult = 0.6 if cap == "Small" else 0.8 if cap == "Mid" else 1.0
        qty = max(1, int((capital * risk_pct / 100 * risk_mult) / max(price - stop, 0.01)))

        return {
            "Ticker":   stock_info["symbol"],
            "Name":     stock_info.get("name", stock_info["symbol"])[:30],
            "Exchange": exch,
            "Cap":      cap,
            "Price ₹":  round(price, 2),
            "Score":    score,
            "Signal":   signal,
            "Setup":    setup,
            "RSI":      round(rsi, 1),
            "Vol ×":    round(vol_ratio, 2),
            "Pullback%":round(pb, 1),
            "Stop ₹":   stop,
            "Target ₹": target,
            "Qty":      qty,
            "PotProfit":round((target - price) * qty, 0),
            "MaxLoss":  round((price - stop) * qty, 0),
        }
    except Exception:
        return None

# ── MAIN UI ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, color in [
    (c1, f"{UNIVERSE_SIZE:,}", "Stocks in Universe", "#58a6ff"),
    (c2, "Pullback + Breakout", "Setups", "#3fb950"),
    (c3, "Score ≥ 8", "BUY signal", "#ffa657"),
    (c4, "40%", "Backtest Return", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)

st.markdown("---")

if st.button("🔍 Scan ALL stocks for swing setups", type="primary", use_container_width=True):
    stocks_to_scan = [s for s in ALL_STOCKS_DATA
                      if s.get("exchange", "NSE") in exchange_filter]
    total = len(stocks_to_scan)
    st.info(f"Scanning **{total:,} stocks** | Min score: {min_score} | Signal: {sig_filter}")

    prog    = st.progress(0)
    prog_txt= st.empty()
    results = []
    scanned = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_and_score, s): s for s in stocks_to_scan}
        for fut in as_completed(futures):
            scanned += 1
            try:
                r = fut.result()
                if r:
                    results.append(r)
            except Exception:
                pass
            if scanned % 20 == 0 or scanned == total:
                prog.progress(scanned / total)
                prog_txt.markdown(f"Scanned **{scanned:,}/{total:,}** | Found: **{len(results)}** setups")

    prog.progress(1.0)
    results.sort(key=lambda x: x["Score"], reverse=True)
    st.session_state["swing_all"] = results
    st.success(f"✅ Done! Found **{len(results)}** swing setups from {total:,} stocks.")

# ── DISPLAY ───────────────────────────────────────────────────────────────────
if "swing_all" in st.session_state:
    res = st.session_state["swing_all"]
    buys   = [r for r in res if r["Signal"] == "BUY"]
    watchs = [r for r in res if r["Signal"] == "WATCH"]
    lc = [r for r in buys if r["Cap"] == "Large"]
    mc = [r for r in buys if r["Cap"] == "Mid"]
    sc = [r for r in buys if r["Cap"] == "Small"]

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    for col, val, lbl in [(c1,len(res),"Total found"),(c2,len(buys),"BUY signals"),
                           (c3,len(lc),"Large cap"),(c4,len(mc),"Mid cap"),
                           (c5,len(sc),"Small cap"),(c6,len(watchs),"WATCH")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    cols_show = ["Ticker","Name","Exchange","Cap","Price ₹","Score","Signal","Setup","RSI","Vol ×","Stop ₹","Target ₹","Qty","PotProfit","MaxLoss"]
    for cap_name, cap_list, note in [
        ("🟢 Large Cap BUY Signals", lc, None),
        ("🔵 Mid Cap BUY Signals",   mc, None),
        ("🟡 Small Cap BUY Signals", sc, "⚠️ Small caps carry higher risk. Position sizes auto-reduced 40%. Verify liquidity before buying."),
        ("👁️ WATCH List",            watchs, None),
    ]:
        if cap_list:
            st.subheader(cap_name)
            if note:
                st.warning(note)
            st.dataframe(pd.DataFrame(cap_list)[cols_show], use_container_width=True, hide_index=True)

    with st.expander("📋 Full results table"):
        st.dataframe(pd.DataFrame(res)[cols_show], use_container_width=True, hide_index=True)
else:
    st.info(f"👆 Click the scan button above to screen all {UNIVERSE_SIZE:,} NSE + BSE stocks.")
    st.markdown("""
    **Strategy:** Finds two setups:
    - **Pullback** — Strong stock dipped 5-15% from highs, bouncing back. Buy the dip.
    - **Breakout** — Stock breaking above a tight consolidation range on high volume.

    **Score 8-10 = BUY | Score 5-7 = WATCH | Below 5 = SKIP**
    """)
