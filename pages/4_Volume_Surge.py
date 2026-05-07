import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')
from fast_scan import fast_scan_all, load_cached_results, clear_cache


st.set_page_config(page_title="Volume Surge — All NSE+BSE", page_icon="📊", layout="wide")

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

st.title("📊 Volume Surge Screener — Follow the Big Money | All NSE + BSE")
st.caption("Scans all ~5,500+ stocks. Catches institutional buying the moment it happens.")

st.markdown("""
<div style='background:#161b22;border-left:4px solid #ffa657;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0;font-size:0.88rem;color:#c9d1d9'>
<b>How this works:</b> Big mutual funds and FIIs cannot hide when they buy — their trades show as massive volume spikes
(2.5× or more than normal). When volume surges AND price goes up on that day, smart money is accumulating.
You follow them in. <b>Score 4-5/5 = BUY.</b>
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
        "HEROMOTOCO","BAJAJ-AUTO","GRASIM","M&M","KPITTECH","PERSISTENT","COFORGE",
        "MPHASIS","TANLA","DEEPAKNITRI","NAVINFLUOR","FINEORG","IRCTC","TATAPOWER",
        "DMART","SIEMENS","HAVELLS","PIDILITIND","BERGEPAINT","MUTHOOTFIN","LUPIN",
        "BIOCON","GLAND","ALKEM","AMBUJACEM","SHRIRAMFIN","CHOLAFIN","BANDHANBNK",
        "FEDERALBNK","IDFCFIRSTB","GREENPANEL","CENTURYPLY","POLYCAB","DIXON","AMBER",
        "VGUARD","ASTRAL","BEL","HAL","GODREJPROP","MANAPPURAM","UJJIVAN","CREDITACC",
        "TATAELXSI","BALKRISIND","ENDURANCE","COLPAL","DABUR","MARICO","EMAMILTD",
        "LAURUSLABS","GRANULES","INTELLECT","MASTEK","NEWGEN","GALAXYSURF","NOCIL",
        "AAVAS","HOMEFIRST","EQUITASBNK","SUPREMEIND","RATNAMANI","PCBL","PAGEIND",
    ]
    ALL_STOCKS_DATA = [{"symbol":s,"name":s,"exchange":"NSE","yf_ticker":f"{s}.NS"} for s in _FALLBACK]
    UNIVERSE_SIZE = len(ALL_STOCKS_DATA)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    capital       = st.number_input("Capital ₹", value=100000, step=5000)
    risk_pct      = st.slider("Risk per trade %", 1.0, 3.0, 2.0, 0.5)
    vol_threshold = st.slider("Volume surge (× normal)", 1.5, 5.0, 2.5, 0.5)
    lookback      = st.slider("Look for surge in last N days", 1, 5, 2)
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    max_workers   = st.slider("Parallel workers", 1, 10, 5)
    min_price     = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price     = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.markdown("**Strategy rules:**")
    st.markdown(f"- Volume {vol_threshold}× the 20-day average")
    st.markdown("- Price closed UP on the surge day")
    st.markdown("- Stock above EMA50 (uptrend)")
    st.markdown("- RSI not overbought (< 70)")
    st.markdown("- Price not too extended from EMA20")
    st.caption("Not SEBI-registered advice.")

# ── ANALYSIS ──────────────────────────────────────────────────────────────────
def fetch_and_score(stock_info: dict, df=None) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        # df is now passed in by fast_scan_all (batch download)
        if df is None or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        df['EMA50']   = df['Close'].ewm(span=50).mean()
        df['EMA20']   = df['Close'].ewm(span=20).mean()
        df['VolMA20'] = df['Volume'].rolling(20).mean()
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI']      = 100 - (100 / (1 + g / l.replace(0, 1e-9)))
        df['VolRatio'] = df['Volume'] / df['VolMA20']
        df['UpDay']    = df['Close'] > df['Close'].shift(1)

        # Check last N days for a volume surge
        recent     = df.iloc[-lookback:]
        surge_rows = recent[recent['VolRatio'] >= vol_threshold]
        if surge_rows.empty:
            return None

        surge_row = surge_rows.iloc[-1]
        latest    = df.iloc[-1]
        price     = float(latest['Close'])
        if not (min_price <= price <= max_price):
            return None

        rsi         = float(latest['RSI'])    if not pd.isna(latest['RSI'])    else 50
        ema50       = float(latest['EMA50'])  if not pd.isna(latest['EMA50'])  else price
        ema20       = float(latest['EMA20'])  if not pd.isna(latest['EMA20'])  else price
        vol_ratio   = float(surge_row['VolRatio'])
        up_on_surge = bool(surge_row['UpDay'])
        above_ema   = price > ema50
        rsi_ok      = rsi < 70
        not_extended= price < ema20 * 1.08

        score = sum([vol_ratio >= vol_threshold, up_on_surge, above_ema, rsi_ok, not_extended])
        if score < 3:
            return None

        signal = "BUY" if score >= 4 and up_on_surge else "WATCH" if score >= 3 else "SKIP"
        if signal == "SKIP":
            return None

        stop   = round(float(surge_row['Low']) * 0.99, 2)
        atr    = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])
        target = round(price + atr * 3, 2)
        qty    = max(1, int((capital * risk_pct / 100) / max(price - stop, 0.01)))
        surge_date = surge_row.name.strftime('%d %b') if hasattr(surge_row.name, 'strftime') else "recent"

        return {
            "Ticker":       stock_info["symbol"],
            "Name":         stock_info.get("name", stock_info["symbol"])[:28],
            "Exchange":     stock_info.get("exchange","NSE"),
            "Price ₹":      round(price, 2),
            "Surge Date":   surge_date,
            "Vol Ratio":    f"{round(vol_ratio,1)}×",
            "Up on Surge":  "✅" if up_on_surge  else "❌",
            "Above EMA50":  "✅" if above_ema    else "❌",
            "RSI ok":       "✅" if rsi_ok       else "❌",
            "Not Extended": "✅" if not_extended else "❌",
            "RSI":          round(rsi, 1),
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
    (c2, f"{vol_threshold}× Volume", "Surge Threshold", "#3fb950"),
    (c3, "Institutional", "Signal Source", "#ffa657"),
    (c4, "Fast Moves", "Trade Style", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
st.markdown("---")


def _score_fn_wrapper(stock_info: dict, df) -> dict | None:
    return fetch_and_score(stock_info, df)

if st.button("🔍 Detect volume surges across ALL stocks", use_container_width=True):
    cached = load_cached_results("volume", cache_hours=4)
    if cached:
        st.success(f"⚡ Loaded **{len(cached)}** results from cache (≤4h old). Use 'Clear cache' below to force re-scan.")
        st.session_state["vol_results"] = cached
    else:
        prog   = st.progress(0)
        status = st.empty()
        results = fast_scan_all(
            all_stocks      = ALL_STOCKS_DATA,
            score_fn        = _score_fn_wrapper,
            exchange_filter = exchange_filter,
            min_price       = min_price,
            max_price       = max_price,
            period          = "6mo",
            batch_size      = 50,
            progress_bar    = prog,
            status_text     = status,
            cache_key       = "volume",
            cache_hours     = 4,
        )
        results.sort(key=lambda x: x.get("Score /5", 0), reverse=True)
        st.session_state["vol_results"] = results
        st.success(f"✅ Done! Found **{len(results)}** signals.")

if st.button("🗑️ Clear cache & re-scan fresh", key="clr_volume"):
    clear_cache("volume")
    if "vol_results" in st.session_state:
        del st.session_state["vol_results"]
    st.rerun()

if "vol_results" in st.session_state:
    res    = st.session_state["vol_results"]
    buys   = [r for r in res if r["Signal"] == "BUY"]
    watchs = [r for r in res if r["Signal"] == "WATCH"]

    c1, c2, c3 = st.columns(3)
    for col, val, lbl in [(c1,len(res),"Surges found"),(c2,len(buys),"BUY signals"),(c3,len(watchs),"WATCH signals")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    cols_show = ["Ticker","Name","Exchange","Price ₹","Surge Date","Vol Ratio","RSI","Stop ₹","Target ₹","Qty","PotProfit ₹","MaxLoss ₹"]
    cols_check= ["Ticker","Name","Vol Ratio","Up on Surge","Above EMA50","RSI ok","Not Extended","Score /5"]

    if buys:
        st.subheader("🟢 Institutional buying detected — BUY signals")
        st.dataframe(pd.DataFrame(buys)[cols_show], use_container_width=True, hide_index=True)
        st.subheader("Condition checklist")
        st.dataframe(pd.DataFrame(buys)[cols_check], use_container_width=True, hide_index=True)

    if watchs:
        st.subheader("🟡 WATCH — surge detected but not all criteria met")
        st.dataframe(pd.DataFrame(watchs)[cols_check], use_container_width=True, hide_index=True)

    with st.expander("📋 All surges found"):
        st.dataframe(pd.DataFrame(res)[cols_show], use_container_width=True, hide_index=True)
else:
    st.info(f"👆 Click the scan button to screen all {UNIVERSE_SIZE:,} stocks for unusual volume.")
