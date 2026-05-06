import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Momentum Screener — All NSE+BSE", page_icon="🚀", layout="wide")

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

st.title("🚀 Momentum Screener — 52-Week High Breakouts | All NSE + BSE")
st.caption("Scans all ~5,500+ listed stocks. Stocks near 52-week highs with strong volume tend to keep going up.")

st.markdown("""
<div style='background:#161b22;border-left:4px solid #58a6ff;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0;font-size:0.88rem;color:#c9d1d9'>
<b>How this works:</b> Stocks making new 52-week highs on high volume have institutional buyers behind them.
This screener finds them when they just broke out — you ride the next leg up.
<b>Score 4/4 = BUY | Score 3/4 = WATCH</b>
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
        "CIPLA","BRITANNIA","HINDALCO","APOLLOHOSP","EICHERMOT","DRREDDY","BPCL",
        "INDUSINDBK","HEROMOTOCO","BAJAJ-AUTO","TATACONSUM","M&M","KPITTECH","PERSISTENT",
        "COFORGE","MPHASIS","TANLA","DEEPAKNITRI","NAVINFLUOR","FINEORG","IRCTC","RVNL",
        "TATAPOWER","ADANIGREEN","ZOMATO","DMART","SIEMENS","HAVELLS","PIDILITIND",
        "BERGEPAINT","MUTHOOTFIN","LUPIN","BIOCON","GLAND","ALKEM","APOLLOTYRE","AMBUJACEM",
        "SHRIRAMFIN","CHOLAFIN","BANDHANBNK","FEDERALBNK","IDFCFIRSTB","GREENPANEL",
        "CENTURYPLY","POLYCAB","DIXON","AMBER","VGUARD","ASTRAL","BEL","HAL","BHEL",
        "GODREJPROP","MANAPPURAM","UJJIVAN","CREDITACC","TATAELXSI","BALKRISIND",
        "ENDURANCE","TIINDIA","SUNDRMFAST","MOTHERSON","COLPAL","DABUR","MARICO","EMAMILTD",
        "LAURUSLABS","GRANULES","INTELLECT","MASTEK","NEWGEN","GALAXYSURF","NOCIL",
        "AAVAS","HOMEFIRST","EQUITASBNK","GABRIEL","SUPREMEIND","RATNAMANI","PCBL","PAGEIND",
    ]
    ALL_STOCKS_DATA = [{"symbol":s,"name":s,"exchange":"NSE","yf_ticker":f"{s}.NS"} for s in _FALLBACK]
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    capital     = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct    = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    stop_pct    = st.slider("Stop loss % below entry", 3, 8, 5)
    target_mul  = st.slider("Target (× stop distance)", 1.5, 4.0, 2.5, 0.5)
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    max_workers = st.slider("Parallel workers", 1, 10, 5)
    min_price   = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price   = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown("- Price within 3% of 52-week high")
    st.markdown("- Volume 1.5× 20-day average")
    st.markdown("- RSI above 55 (momentum)")
    st.markdown("- Above 50-day EMA")
    st.caption("Not SEBI-registered advice.")

# ── ANALYSIS FUNCTION ─────────────────────────────────────────────────────────
def fetch_and_score(stock_info: dict) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True, timeout=15)
        if df is None or len(df) < 60:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        df['EMA50']   = df['Close'].ewm(span=50).mean()
        df['VolMA20'] = df['Volume'].rolling(20).mean()
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + g / l.replace(0, 1e-9)))

        r = df.iloc[-1]
        price = float(r['Close'])
        if not (min_price <= price <= max_price):
            return None

        hi52      = float(df['Close'].rolling(min(252, len(df))).max().iloc[-1])
        near52    = (price / hi52) >= 0.97 if hi52 > 0 else False
        vol_ratio = float(r['Volume']) / float(r['VolMA20']) if not pd.isna(r['VolMA20']) and float(r['VolMA20']) > 0 else 0
        vol_ok    = vol_ratio >= 1.5
        rsi       = float(r['RSI']) if not pd.isna(r['RSI']) else 50
        rsi_ok    = rsi > 55
        ema_ok    = price > float(r['EMA50']) if not pd.isna(r['EMA50']) else False

        score = sum([near52, vol_ok, rsi_ok, ema_ok])
        if score < 3:
            return None

        signal  = "BUY" if score == 4 else "WATCH" if score == 3 else "SKIP"
        pct_hi  = round((price / hi52 - 1) * 100, 1) if hi52 > 0 else 0
        stop    = round(price * (1 - stop_pct / 100), 2)
        target  = round(price + (price - stop) * target_mul, 2)
        qty     = max(1, int((capital * risk_pct / 100) / max(price - stop, 0.01)))

        return {
            "Ticker":       stock_info["symbol"],
            "Name":         stock_info.get("name", stock_info["symbol"])[:28],
            "Exchange":     stock_info.get("exchange", "NSE"),
            "Price ₹":      round(price, 2),
            "52W High ₹":   round(hi52, 2),
            "From High %":  f"{pct_hi}%",
            "Vol Ratio":    f"{round(vol_ratio,1)}×",
            "RSI":          round(rsi, 1),
            "Score /4":     score,
            "Signal":       signal,
            "Near 52W":     "✅" if near52 else "❌",
            "Vol Surge":    "✅" if vol_ok  else "❌",
            "RSI > 55":     "✅" if rsi_ok  else "❌",
            "Above EMA50":  "✅" if ema_ok  else "❌",
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
    (c2, "52W Highs", "Signal Type", "#3fb950"),
    (c3, "Score 4/4", "BUY Signal", "#ffa657"),
    (c4, "Bull Market", "Best Condition", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
st.markdown("---")

if st.button("🔍 Scan ALL stocks for momentum breakouts", use_container_width=True):
    stocks_to_scan = [s for s in ALL_STOCKS_DATA if s.get("exchange","NSE") in exchange_filter]
    total = len(stocks_to_scan)
    st.info(f"Scanning **{total:,} stocks** from: {', '.join(exchange_filter)}")

    prog     = st.progress(0)
    prog_txt = st.empty()
    results  = []
    scanned  = 0

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
                prog_txt.markdown(f"Scanned **{scanned:,}/{total:,}** | Found: **{len(results)}** signals")

    prog.progress(1.0)
    results.sort(key=lambda x: x["Score /4"], reverse=True)
    st.session_state["mom_results"] = results
    st.success(f"✅ Done! Found **{len(results)}** momentum setups from {total:,} stocks.")

if "mom_results" in st.session_state:
    res    = st.session_state["mom_results"]
    buys   = [r for r in res if r["Signal"] == "BUY"]
    watchs = [r for r in res if r["Signal"] == "WATCH"]

    c1, c2, c3 = st.columns(3)
    for col, val, lbl in [(c1, len(res),"Total found"),(c2, len(buys),"BUY (4/4)"),(c3, len(watchs),"WATCH (3/4)")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    cols_show = ["Ticker","Name","Exchange","Price ₹","52W High ₹","From High %","Vol Ratio","RSI","Signal","Stop ₹","Target ₹","Qty","PotProfit ₹","MaxLoss ₹"]
    if buys:
        st.subheader("🟢 BUY signals — all 4 criteria met")
        st.dataframe(pd.DataFrame(buys)[cols_show], use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 WATCH — 3 of 4 criteria met")
        st.dataframe(pd.DataFrame(watchs)[["Ticker","Name","Exchange","Price ₹","Near 52W","Vol Surge","RSI > 55","Above EMA50","Score /4"]], use_container_width=True, hide_index=True)

    with st.expander("📋 Full results table"):
        st.dataframe(pd.DataFrame(res)[cols_show], use_container_width=True, hide_index=True)
else:
    st.info(f"👆 Click the scan button to screen all {UNIVERSE_SIZE:,} stocks.")
