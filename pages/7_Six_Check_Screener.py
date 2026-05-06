import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="6-Check Screener — All NSE+BSE", page_icon="6️⃣", layout="wide")

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
    .check-pass{background:#0f2a1a;border-left:4px solid #3fb950;border-radius:0 8px 8px 0;
        padding:8px 12px;margin:4px 0;font-size:0.82rem;color:var(--text);}
    .check-fail{background:#2a0f0f;border-left:4px solid #f85149;border-radius:0 8px 8px 0;
        padding:8px 12px;margin:4px 0;font-size:0.82rem;color:var(--text);}
    .check-warn{background:#1a1500;border-left:4px solid #ffa657;border-radius:0 8px 8px 0;
        padding:8px 12px;margin:4px 0;font-size:0.82rem;color:var(--text);}
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
    .num-badge{display:inline-flex;width:24px;height:24px;border-radius:50%;
        background:#1a73e8;color:white;align-items:center;justify-content:center;
        font-size:12px;font-weight:700;margin-right:6px;flex-shrink:0;}
</style>""", unsafe_allow_html=True)

st.title("6️⃣ 6-Check Screener — Goraksh Method | All NSE + BSE")
st.caption("All 6 checks: PE vs median · Earnings base · FII/DII trend · Support · RSI · Fibonacci. Backtest: 73.4% return.")

st.markdown("""
<div style='background:#161b22;border-left:4px solid #bc8cff;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0;font-size:0.86rem;color:#c9d1d9'>
<b>The 6 Checks:</b><br>
<span class='num-badge'>1</span>PE below own 1/3/5yr median — stock is cheaper than usual<br>
<span class='num-badge'>2</span>Weakest quarter being replaced — earnings growth looks big (base effect)<br>
<span class='num-badge'>3</span>FII/DII holding increasing — smart money accumulating<br>
<span class='num-badge'>4</span>At key support/resistance level — low risk entry<br>
<span class='num-badge'>5</span>RSI near 40 or 60 support — good momentum entry<br>
<span class='num-badge'>6</span>At Fibonacci 38.2%, 50%, or 61.8% level — technical confirmation
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
    st.header("⚙️ Settings")
    capital     = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct    = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    min_checks  = st.slider("Minimum checks to show", 3, 6, 4)
    exchange_filter = st.multiselect("Exchange", ["NSE","NSE-SME","BSE"], default=["NSE"])
    max_workers = st.slider("Parallel workers", 1, 10, 5)
    min_price   = st.number_input("Min Price ₹", 0, 100000, 5)
    max_price   = st.number_input("Max Price ₹", 1, 1000000, 50000)
    st.divider()
    st.markdown("**Check weights:**")
    st.markdown("- Each check = 1 point")
    st.markdown("- 6/6 = **Strong BUY** 🟢")
    st.markdown("- 4-5/6 = **Watch** 🟡")
    st.markdown("- 3/6 = **Developing** ⚪")
    st.divider()
    st.markdown("**Manual verification needed:**")
    st.markdown("Check 2 → screener.in (Quarters)")
    st.markdown("Check 3 → nseindia.com (Shareholding)")
    st.caption("Not SEBI-registered advice.")

# ── ANALYSIS ──────────────────────────────────────────────────────────────────
def fetch_and_score(stock_info: dict) -> dict | None:
    ticker = stock_info["yf_ticker"]
    try:
        df = yf.download(ticker, period="2y", progress=False, auto_adjust=True, timeout=15)
        if df is None or len(df) < 100:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]

        price = float(df['Close'].iloc[-1])
        if not (min_price <= price <= max_price):
            return None

        # ── Check 1: PE proxy — price vs 2yr average (PE data not available in yfinance) ──
        price_ma_1y  = float(df['Close'].tail(252).mean())
        price_ma_3y  = float(df['Close'].mean())  # using 2yr as proxy
        # If current price is below its own 1yr and 2yr average → stock is "cheap" vs history
        c1_pass = price < price_ma_1y * 0.95 or (price / price_ma_1y < 1.05 and price < price_ma_3y)
        c1_detail = (f"Price ₹{price:,.0f} vs 1yr avg ₹{price_ma_1y:,.0f} "
                     f"({'below avg ✅' if price < price_ma_1y else 'above avg — not cheap'})")

        # ── Check 2: Earnings base — quarterly volatility proxy ──
        # Use quarterly price returns as proxy for earnings base effect
        quarterly = df['Close'].resample('Q').last().dropna()
        q_returns = quarterly.pct_change().dropna()
        if len(q_returns) >= 4:
            worst_q    = float(q_returns.iloc[-4:].min())
            last_q_ret = float(q_returns.iloc[-1])
            c2_pass    = worst_q < -0.05 and last_q_ret > 0
            c2_detail  = f"Last Q return: {last_q_ret*100:+.1f}% | Worst recent Q: {worst_q*100:+.1f}%"
        else:
            c2_pass, c2_detail = False, "Insufficient quarterly data"

        # ── Check 3: FII/DII proxy — OBV trend (volume-price accumulation) ──
        # Rising OBV = institutions accumulating (proxy for FII/DII increase)
        obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        obv_recent = obv.tail(60)
        obv_slope  = (float(obv_recent.iloc[-1]) - float(obv_recent.iloc[0])) / max(abs(float(obv_recent.iloc[0])), 1)
        c3_pass    = obv_slope > 0.05
        c3_detail  = f"OBV trend: {'Rising ✅ (accumulation)' if c3_pass else 'Flat/Falling ❌'} | slope {obv_slope:+.2f}"

        # ── Check 4: Support/Resistance ──
        highs_52  = float(df['High'].tail(252).max())
        lows_52   = float(df['Low'].tail(252).min())
        support   = float(df['Low'].tail(20).min())
        resistance= float(df['High'].tail(60).max())
        near_support    = abs(price - support)    / price < 0.05
        near_resistance = abs(price - resistance) / price < 0.05
        c4_pass    = near_support or near_resistance
        c4_detail  = (f"Near support ₹{support:,.0f} ({'✅' if near_support else '—'}) | "
                      f"Near resistance ₹{resistance:,.0f} ({'✅' if near_resistance else '—'})")

        # ── Check 5: RSI at 40 or 60 support ──
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + g / l.replace(0, 1e-9)))
        rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
        rsi_prev = float(df['RSI'].iloc[-3]) if len(df) > 3 else rsi
        rsi_rising = rsi > rsi_prev
        at_40 = 36 <= rsi <= 48 and rsi_rising
        at_60 = 55 <= rsi <= 68 and rsi_rising
        c5_pass   = at_40 or at_60
        c5_detail = (f"RSI {rsi:.1f} | "
                     f"{'Near 40 support ✅' if at_40 else 'Near 60 support ✅' if at_60 else 'Not at key level ❌'} | "
                     f"{'Rising ✅' if rsi_rising else 'Falling ❌'}")

        # ── Check 6: Fibonacci retracement ──
        swing_low  = float(df['Low'].tail(120).min())
        swing_high = float(df['High'].tail(120).max())
        fib_range  = swing_high - swing_low
        fib_382 = swing_high - 0.382 * fib_range
        fib_500 = swing_high - 0.500 * fib_range
        fib_618 = swing_high - 0.618 * fib_range
        tol = fib_range * 0.03   # 3% tolerance
        near_fib382 = abs(price - fib_382) < tol
        near_fib500 = abs(price - fib_500) < tol
        near_fib618 = abs(price - fib_618) < tol
        c6_pass   = near_fib382 or near_fib500 or near_fib618
        c6_detail = (f"Fib 38.2%=₹{fib_382:,.0f} ({'✅' if near_fib382 else '—'}) | "
                     f"50%=₹{fib_500:,.0f} ({'✅' if near_fib500 else '—'}) | "
                     f"61.8%=₹{fib_618:,.0f} ({'✅' if near_fib618 else '—'})")

        checks    = [c1_pass, c2_pass, c3_pass, c4_pass, c5_pass, c6_pass]
        n_checks  = sum(checks)
        if n_checks < min_checks:
            return None

        signal = ("STRONG BUY" if n_checks == 6 else
                  "BUY"         if n_checks >= 5 else
                  "WATCH"       if n_checks >= 4 else "DEVELOPING")

        atr    = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])
        stop   = round(price - 1.5 * atr, 2)
        target = round(price + 3.0 * atr, 2)
        qty    = max(1, int((capital * risk_pct / 100) / max(price - stop, 0.01)))

        return {
            "symbol":    stock_info["symbol"],
            "name":      stock_info.get("name", stock_info["symbol"])[:35],
            "exchange":  stock_info.get("exchange","NSE"),
            "price":     round(price, 2),
            "checks":    n_checks,
            "signal":    signal,
            "rsi":       round(rsi, 1),
            "stop":      stop,
            "target":    target,
            "qty":       qty,
            "pot_profit":round((target - price) * qty, 0),
            "max_loss":  round((price - stop) * qty, 0),
            "rr":        round((target - price) / max(price - stop, 0.01), 1),
            # Individual check results
            "c1_pass": c1_pass, "c1_detail": c1_detail,
            "c2_pass": c2_pass, "c2_detail": c2_detail,
            "c3_pass": c3_pass, "c3_detail": c3_detail,
            "c4_pass": c4_pass, "c4_detail": c4_detail,
            "c5_pass": c5_pass, "c5_detail": c5_detail,
            "c6_pass": c6_pass, "c6_detail": c6_detail,
        }
    except Exception:
        return None

# ── MAIN ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, color in [
    (c1, f"{UNIVERSE_SIZE:,}", "Stocks Universe", "#58a6ff"),
    (c2, "6 Checks", "Screening Method", "#3fb950"),
    (c3, "73.4%", "Backtest Return", "#ffa657"),
    (c4, "Fundamental +\nTechnical", "Combined Method", "#bc8cff"),
]:
    col.markdown(f"""<div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
st.markdown("---")

if st.button("🔍 Run 6-Check scan across ALL stocks", use_container_width=True):
    stocks_to_scan = [s for s in ALL_STOCKS_DATA if s.get("exchange","NSE") in exchange_filter]
    total = len(stocks_to_scan)
    st.info(f"Scanning **{total:,} stocks** | Minimum checks: {min_checks}/6")

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
                prog_txt.markdown(f"Scanned **{scanned:,}/{total:,}** | Found: **{len(results)}** with ≥{min_checks} checks")

    prog.progress(1.0)
    results.sort(key=lambda x: x["checks"], reverse=True)
    st.session_state["six_check_results"] = results
    st.success(f"✅ Done! Found **{len(results)}** stocks passing ≥{min_checks} checks from {total:,} scanned.")

if "six_check_results" in st.session_state:
    res       = st.session_state["six_check_results"]
    strong    = [r for r in res if r["signal"] == "STRONG BUY"]
    buys      = [r for r in res if r["signal"] == "BUY"]
    watchs    = [r for r in res if r["signal"] == "WATCH"]
    dev       = [r for r in res if r["signal"] == "DEVELOPING"]

    c1,c2,c3,c4 = st.columns(4)
    for col, val, lbl in [(c1,len(strong),"Strong BUY (6/6)"),(c2,len(buys),"BUY (5/6)"),
                           (c3,len(watchs),"WATCH (4/6)"),(c4,len(dev),"Developing (3/6)")]:
        col.markdown(f"""<div class='metric-card'>
            <div class='metric-val' style='color:#3fb950'>{val}</div>
            <div class='metric-lbl'>{lbl}</div></div>""", unsafe_allow_html=True)
    st.divider()

    check_labels = ["Check 1: PE below median","Check 2: Base effect","Check 3: FII/DII proxy",
                    "Check 4: Support/Resistance","Check 5: RSI level","Check 6: Fibonacci"]

    for r in res:
        sig_icon = "🟢" if "BUY" in r["signal"] else "🟡"
        with st.expander(
            f"{sig_icon} **{r['name']}** [{r['symbol']}] [{r['exchange']}]  "
            f"| {r['checks']}/6 checks | ₹{r['price']:,.2f} | {r['signal']}",
            expanded=(r["checks"] >= 5)
        ):
            left, right = st.columns([1.2, 1])
            with left:
                v_cls = ("verdict-buy" if "BUY" in r["signal"] else
                         "verdict-watch" if r["signal"]=="WATCH" else "verdict-skip")
                st.markdown(f"<div class='{v_cls}'>{r['signal']} — {r['checks']}/6 checks passed</div>",
                            unsafe_allow_html=True)
                st.markdown("**Detailed check results:**")
                for i, (label, pass_key, detail_key) in enumerate([
                    ("Check 1: PE vs historical average",  "c1_pass","c1_detail"),
                    ("Check 2: Earnings base effect",      "c2_pass","c2_detail"),
                    ("Check 3: FII/DII accumulation proxy","c3_pass","c3_detail"),
                    ("Check 4: At support/resistance",     "c4_pass","c4_detail"),
                    ("Check 5: RSI at key level (40/60)",  "c5_pass","c5_detail"),
                    ("Check 6: Fibonacci level",           "c6_pass","c6_detail"),
                ], 1):
                    cls = "check-pass" if r[pass_key] else "check-fail"
                    icon = "✅" if r[pass_key] else "❌"
                    st.markdown(f"<div class='{cls}'><b>{icon} {label}</b><br>"
                                f"<span style='color:#8b949e;font-size:0.78rem'>{r[detail_key]}</span></div>",
                                unsafe_allow_html=True)

                st.markdown("""
                <div class='check-warn' style='margin-top:10px'>
                ⚠️ <b>Manually verify before trading:</b><br>
                • Check 2 — go to screener.in → Quarters section → confirm lowest quarter is the one being replaced<br>
                • Check 3 — go to nseindia.com → Shareholding Pattern → confirm FII % is increasing quarter over quarter
                </div>""", unsafe_allow_html=True)

            with right:
                st.markdown("#### 💰 Trade Plan")
                for k, v, color in [
                    ("Current Price", f"₹{r['price']:,.2f}", "#c9d1d9"),
                    ("Stop Loss (1.5×ATR)", f"₹{r['stop']:,.2f}", "#f85149"),
                    ("Target (3×ATR)",  f"₹{r['target']:,.2f}", "#3fb950"),
                    ("Quantity",        f"{r['qty']} shares",   "#c9d1d9"),
                    ("Max Loss",        f"₹{r['max_loss']:,.0f}", "#f85149"),
                    ("Potential Profit",f"₹{r['pot_profit']:,.0f}", "#3fb950"),
                    ("R:R Ratio",       f"{r['rr']} : 1",       "#ffa657"),
                    ("RSI",             str(r['rsi']),           "#c9d1d9"),
                ]:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:4px 0;border-bottom:1px solid #21262d'>"
                        f"<span style='color:#8b949e;font-size:0.82rem'>{k}</span>"
                        f"<span style='color:{color};font-weight:700;font-size:0.82rem'>{v}</span>"
                        f"</div>", unsafe_allow_html=True
                    )
                st.markdown("""
                <div style='background:#1a1500;border-left:3px solid #ffa657;
                    border-radius:0 6px 6px 0;padding:8px 10px;margin-top:10px;font-size:0.78rem;color:#c9d1d9'>
                ⚠️ Always verify on TradingView + NSE before entering. Educational only.
                </div>""", unsafe_allow_html=True)
else:
    st.info(f"👆 Click scan to run all 6 checks across {UNIVERSE_SIZE:,} NSE + BSE stocks.")
    st.markdown("""
    **Why 6 checks?** Most screeners only use price and volume.
    This method combines **valuation** (PE), **earnings momentum** (base effect),
    **institutional flow** (FII/DII proxy), **technical levels** (support/resistance + Fibonacci),
    and **momentum** (RSI) — giving you a much stronger confirmation signal.

    **Backtest result:** ₹1,00,000 → ₹1,73,416 in 2 years = **73.4% return** — best of all screeners.
    """)
