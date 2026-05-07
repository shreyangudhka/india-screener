import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')
from fast_scan import fast_scan_all, load_cached_results, clear_cache


st.set_page_config(page_title="Smart Reasoning — All NSE+BSE", page_icon="🧠", layout="wide")

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
    .reason-box{background:#0f1a2a;border-left:4px solid #58a6ff;border-radius:0 8px 8px 0;
        padding:10px 14px;margin:6px 0;font-size:0.83rem;color:var(--text);line-height:1.6;}
    .warn-box{background:#1a1500;border-left:4px solid #ffa657;border-radius:0 8px 8px 0;
        padding:10px 14px;margin:6px 0;font-size:0.83rem;color:var(--text);line-height:1.6;}
    .good-box{background:#0f2a1a;border-left:4px solid #3fb950;border-radius:0 8px 8px 0;
        padding:10px 14px;margin:6px 0;font-size:0.83rem;color:var(--text);line-height:1.6;}
    .danger-box{background:#2a0f0f;border-left:4px solid #f85149;border-radius:0 8px 8px 0;
        padding:10px 14px;margin:6px 0;font-size:0.83rem;color:var(--text);line-height:1.6;}
    .verdict-buy{background:#0f2a1a;border:2px solid #3fb950;border-radius:10px;
        padding:12px;text-align:center;font-size:1.1rem;font-weight:700;color:#3fb950;margin-bottom:10px;}
    .verdict-watch{background:#1a1500;border:2px solid #ffa657;border-radius:10px;
        padding:12px;text-align:center;font-size:1.1rem;font-weight:700;color:#ffa657;margin-bottom:10px;}
    .verdict-skip{background:#2a0f0f;border:2px solid #f85149;border-radius:10px;
        padding:12px;text-align:center;font-size:1.1rem;font-weight:700;color:#f85149;margin-bottom:10px;}
    .metric-card{background:var(--card);border:1px solid var(--border);
        border-radius:10px;padding:14px 18px;text-align:center;margin-bottom:8px;}
    .metric-val{font-size:1.8rem;font-weight:800;}
    .metric-lbl{font-size:0.75rem;color:var(--muted);margin-top:2px;}
</style>""", unsafe_allow_html=True)

st.title("🧠 Smart Reasoning Screener — WHY to Buy or Skip | All NSE + BSE")
st.caption("Every flagged stock gets a full plain-English explanation. Scans all ~5,500+ listed stocks.")

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
    st.header("⚙️ Settings")
    capital     = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct    = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    min_score   = st.slider("Minimum score to show", 0, 10, 5)
    show_only   = st.selectbox("Show signals", ["All", "BUY only", "BUY + WATCH"])
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    max_workers = st.slider("Parallel workers", 1, 10, 5)
    min_price   = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price   = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.markdown("**Scoring system (out of 10):**")
    st.markdown("- Above EMA50: +2  |  Above SMA200: +2")
    st.markdown("- RSI 38-62: +2  |  Volume 1.2×: +2")
    st.markdown("- Pullback 3-18%: +1  |  Weekly uptrend: +1")
    st.markdown("**Score 8+ = BUY | 5-7 = WATCH**")
    st.caption("Not SEBI-registered advice.")

# ── ANALYSIS ──────────────────────────────────────────────────────────────────
def fetch_and_score(stock_info: dict, df=None) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        # df is now passed in by fast_scan_all (batch download)
        if df is None or len(df) < 55:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        df['EMA20']   = df['Close'].ewm(span=20).mean()
        df['EMA50']   = df['Close'].ewm(span=50).mean()
        df['SMA200']  = df['Close'].rolling(min(200, len(df))).mean()
        df['VolMA20'] = df['Volume'].rolling(20).mean()
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + g / l.replace(0, 1e-9)))
        tr = pd.concat([df['High'] - df['Low'],
                        (df['High'] - df['Close'].shift()).abs(),
                        (df['Low']  - df['Close'].shift()).abs()], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean()

        r = df.iloc[-1]
        price = float(r['Close'])
        if not (min_price <= price <= max_price):
            return None

        e20    = float(r['EMA20'])   if not pd.isna(r['EMA20'])   else price
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
        weekly_up = float(weekly.iloc[-1]) > float(weekly.iloc[-5]) if len(weekly) >= 5 else True
        hi52 = float(df['Close'].rolling(min(252, len(df))).max().iloc[-1])

        score = 0
        if price > e50:      score += 2
        if price > sma200:   score += 2
        if 38 <= rsi <= 62:  score += 2
        if vol_ratio >= 1.2: score += 2
        if 3 <= pb <= 18:    score += 1
        if weekly_up:        score += 1

        if score < min_score:
            return None
        signal = "BUY" if score >= 8 and weekly_up else "WATCH" if score >= 5 else "SKIP"
        if show_only == "BUY only" and signal != "BUY":
            return None
        if show_only == "BUY + WATCH" and signal == "SKIP":
            return None

        stop   = round(price - 1.5 * atr, 2)
        target = round(price + 3.0 * atr, 2)
        qty    = max(1, int((capital * risk_pct / 100) / max(price - stop, 0.01)))

        # Build plain-English reasons
        reasons_buy, reasons_warn = [], []
        if price > e50:
            reasons_buy.append(f"✅ Price ₹{price:,.0f} is above 50-day EMA ₹{e50:,.0f} — uptrend confirmed")
        else:
            reasons_warn.append(f"⚠️ Price ₹{price:,.0f} is below 50-day EMA ₹{e50:,.0f} — no uptrend yet")
        if price > sma200:
            reasons_buy.append(f"✅ Above 200-day SMA ₹{sma200:,.0f} — long-term health is strong")
        else:
            reasons_warn.append(f"⚠️ Below 200-day SMA ₹{sma200:,.0f} — long-term trend is weak")
        if 38 <= rsi <= 62:
            reasons_buy.append(f"✅ RSI {rsi:.0f} is in ideal entry zone (38–62) — not overbought, not oversold")
        elif rsi > 70:
            reasons_warn.append(f"⚠️ RSI {rsi:.0f} is overbought — risk of pullback, wait for lower entry")
        else:
            reasons_warn.append(f"⚠️ RSI {rsi:.0f} is weak — momentum not yet recovered")
        if vol_ratio >= 1.5:
            reasons_buy.append(f"✅ Volume is {vol_ratio:.1f}× normal — strong institutional interest")
        elif vol_ratio >= 1.2:
            reasons_buy.append(f"✅ Volume {vol_ratio:.1f}× average — decent buying interest")
        else:
            reasons_warn.append(f"⚠️ Volume only {vol_ratio:.1f}× normal — low participation, wait for volume")
        if 5 <= pb <= 15:
            reasons_buy.append(f"✅ Pulled back {pb:.1f}% from recent high — ideal entry zone, not extended")
        elif pb > 18:
            reasons_warn.append(f"⚠️ Pulled back {pb:.1f}% — quite deep, check if fundamental reason")
        if weekly_up:
            reasons_buy.append("✅ Weekly chart is in uptrend — big picture is bullish")
        else:
            reasons_warn.append("⚠️ Weekly chart is not in uptrend — wait for weekly confirmation")
        if (price / hi52) > 0.97:
            reasons_buy.append(f"✅ Near 52-week high ₹{hi52:,.0f} — strong momentum, new highs expected")

        return {
            "symbol":       stock_info["symbol"],
            "name":         stock_info.get("name", stock_info["symbol"])[:35],
            "exchange":     stock_info.get("exchange","NSE"),
            "price":        round(price, 2),
            "score":        score,
            "signal":       signal,
            "rsi":          round(rsi, 1),
            "vol_ratio":    round(vol_ratio, 2),
            "pullback":     round(pb, 1),
            "e50":          round(e50, 2),
            "sma200":       round(sma200, 2),
            "stop":         stop,
            "target":       target,
            "qty":          qty,
            "pot_profit":   round((target - price) * qty, 0),
            "max_loss":     round((price - stop) * qty, 0),
            "rr":           round((target - price) / max(price - stop, 0.01), 1),
            "reasons_buy":  reasons_buy,
            "reasons_warn": reasons_warn,
        }
    except Exception:
        return None

# ── MAIN ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, color in [
    (c1, f"{UNIVERSE_SIZE:,}", "Stocks Universe", "#58a6ff"),
    (c2, "Plain English", "Reasoning Style", "#3fb950"),
    (c3, "Full Trade Plan", "Auto Generated", "#ffa657"),
    (c4, "Score /10", "Scoring System", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
st.markdown("---")


def _score_fn_wrapper(stock_info: dict, df) -> dict | None:
    return fetch_and_score(stock_info, df)

if st.button("🔍 Scan ALL stocks with full reasoning", use_container_width=True):
    cached = load_cached_results("reasoning", cache_hours=4)
    if cached:
        st.success(f"⚡ Loaded **{len(cached)}** results from cache (≤4h old). Use 'Clear cache' below to force re-scan.")
        st.session_state["reasoning_results"] = cached
    else:
        prog   = st.progress(0)
        status = st.empty()
        results = fast_scan_all(
            all_stocks      = ALL_STOCKS_DATA,
            score_fn        = _score_fn_wrapper,
            exchange_filter = exchange_filter,
            min_price       = min_price,
            max_price       = max_price,
            period          = "1y",
            batch_size      = 50,
            progress_bar    = prog,
            status_text     = status,
            cache_key       = "reasoning",
            cache_hours     = 4,
        )
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        st.session_state["reasoning_results"] = results
        st.success(f"✅ Done! Found **{len(results)}** signals.")

if st.button("🗑️ Clear cache & re-scan fresh", key="clr_reasoning"):
    clear_cache("reasoning")
    if "reasoning_results" in st.session_state:
        del st.session_state["reasoning_results"]
    st.rerun()

if "reasoning_results" in st.session_state:
    res    = st.session_state["reasoning_results"]
    buys   = [r for r in res if r["signal"] == "BUY"]
    watchs = [r for r in res if r["signal"] == "WATCH"]

    c1, c2, c3 = st.columns(3)
    for col, val, lbl in [(c1,len(res),"Total found"),(c2,len(buys),"BUY signals"),(c3,len(watchs),"WATCH signals")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    for r in res:
        sig_color = "#3fb950" if r["signal"]=="BUY" else "#ffa657" if r["signal"]=="WATCH" else "#f85149"
        sig_icon  = "🟢" if r["signal"]=="BUY" else "🟡"
        with st.expander(
            f"{sig_icon} **{r['name']}** [{r['symbol']}] [{r['exchange']}]  "
            f"| Score: {r['score']}/10 | ₹{r['price']:,.2f} | {r['signal']}",
            expanded=(r["score"] >= 8)
        ):
            left, right = st.columns([1.2, 1])
            with left:
                # Verdict
                verdict_cls = "verdict-buy" if r["signal"]=="BUY" else "verdict-watch"
                verdict_txt = (f"✅ BUY — Score {r['score']}/10" if r["signal"]=="BUY"
                               else f"👁️ WATCH — Score {r['score']}/10")
                st.markdown(f"<div class='{verdict_cls}'>{verdict_txt}</div>", unsafe_allow_html=True)

                st.markdown("**Reasons to consider buying:**")
                for reason in r["reasons_buy"]:
                    st.markdown(f"<div class='good-box'>{reason}</div>", unsafe_allow_html=True)

                if r["reasons_warn"]:
                    st.markdown("**Caution points:**")
                    for warn in r["reasons_warn"]:
                        st.markdown(f"<div class='warn-box'>{warn}</div>", unsafe_allow_html=True)

            with right:
                st.markdown("#### 💰 Trade Plan")
                st.markdown(f"**Capital:** ₹{capital:,.0f}")
                for k, v, color in [
                    ("Current Price", f"₹{r['price']:,.2f}", "#c9d1d9"),
                    ("Entry (at breakout)", f"₹{r['price']:,.2f}", "#ffa657"),
                    ("Stop Loss", f"₹{r['stop']:,.2f}", "#f85149"),
                    ("Target", f"₹{r['target']:,.2f}", "#3fb950"),
                    ("Quantity", f"{r['qty']} shares", "#c9d1d9"),
                    ("Max Loss", f"₹{r['max_loss']:,.0f}", "#f85149"),
                    ("Potential Profit", f"₹{r['pot_profit']:,.0f}", "#3fb950"),
                    ("R:R Ratio", f"{r['rr']} : 1", "#ffa657"),
                ]:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:4px 0;border-bottom:1px solid #21262d'>"
                        f"<span style='color:#8b949e;font-size:0.82rem'>{k}</span>"
                        f"<span style='color:{color};font-weight:700;font-size:0.82rem'>{v}</span>"
                        f"</div>", unsafe_allow_html=True
                    )

                st.markdown("---")
                st.markdown("#### 📊 Technical Summary")
                for k, v in [("RSI", r["rsi"]),("Volume ×", r["vol_ratio"]),
                              ("Pullback %", f"{r['pullback']}%"),
                              ("EMA 50", f"₹{r['e50']:,.0f}"),("SMA 200", f"₹{r['sma200']:,.0f}")]:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #21262d'>"
                        f"<span style='color:#8b949e;font-size:0.8rem'>{k}</span>"
                        f"<span style='color:#c9d1d9;font-weight:600;font-size:0.8rem'>{v}</span>"
                        f"</div>", unsafe_allow_html=True
                    )

                st.markdown("""
                <div style='background:#1a1500;border-left:3px solid #ffa657;
                    border-radius:0 6px 6px 0;padding:8px 10px;margin-top:10px;font-size:0.78rem;color:#c9d1d9'>
                ⚠️ Verify on TradingView. Check NSE for upcoming earnings dates.
                This is educational — not SEBI-registered advice.
                </div>""", unsafe_allow_html=True)
else:
    st.info(f"👆 Click scan to analyse all {UNIVERSE_SIZE:,} stocks with plain-English reasoning.")
    st.markdown("""
    **This screener is unique** — it doesn't just give you a buy/skip signal.
    It tells you *exactly why* a stock looks good or risky, in plain language anyone can understand.

    Each result shows:
    - ✅ Every positive reason to consider the trade
    - ⚠️ Every caution or risk to be aware of
    - A complete trade plan with entry, stop, target, quantity, and R:R ratio
    """)
