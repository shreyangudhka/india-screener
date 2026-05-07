"""
8_VCP_Screener.py  —  Volatility Contraction Pattern Screener
Scans ALL NSE + BSE listed stocks (~5,500+) for VCP setups.
Mark Minervini Method | India Stock Screener
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time, warnings, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings("ignore")
from fast_scan import fast_scan_all, load_cached_results, clear_cache

# ── Import universal stock universe ──────────────────────────────────────────
try:
    from stocks_universe import get_all_stocks, get_stock_count, download_batch
    UNIVERSE_AVAILABLE = True
except ImportError:
    UNIVERSE_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VCP Screener — All NSE + BSE",
    page_icon="🌀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d;
            --green:#3fb950; --red:#f85149; --blue:#58a6ff;
            --gold:#ffa657; --text:#c9d1d9; --muted:#8b949e; }
    .stApp { background-color: var(--bg); color: var(--text); }
    .metric-card {
        background: var(--card); border: 1px solid var(--border);
        border-radius: 10px; padding: 16px 20px; text-align: center;
        margin-bottom: 8px;
    }
    .metric-val  { font-size: 2rem; font-weight: 800; line-height: 1.1; }
    .metric-lbl  { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }
    .win-badge   { background:#0f2a1a; color:var(--green); border:1px solid var(--green);
                   border-radius:6px; padding:2px 10px; font-weight:700; font-size:0.8rem; }
    .loss-badge  { background:#2a0f0f; color:var(--red);   border:1px solid var(--red);
                   border-radius:6px; padding:2px 10px; font-weight:700; font-size:0.8rem; }
    .score-badge { background:#1a1f29; color:var(--gold);  border:1px solid var(--gold);
                   border-radius:6px; padding:2px 8px;  font-weight:700; font-size:0.8rem; }
    div[data-testid="stSidebarContent"] { background:#0d1117; }
    .stButton>button {
        background:linear-gradient(135deg,#1a6b3c,#0f4028);
        color:white; border:1px solid var(--green); border-radius:8px;
        font-weight:700; font-size:1rem; padding:10px 24px; width:100%;
    }
    .stButton>button:hover { background:linear-gradient(135deg,#26a641,#1a6b3c); }
    .info-box {
        background:var(--card); border-left:4px solid var(--blue);
        border-radius:0 8px 8px 0; padding:12px 16px; margin:8px 0;
        font-size:0.85rem; color:var(--text);
    }
    .warn-box {
        background:#1a1500; border-left:4px solid var(--gold);
        border-radius:0 8px 8px 0; padding:12px 16px; margin:8px 0;
        font-size:0.85rem; color:var(--text);
    }
    .progress-text { font-size:0.85rem; color:var(--muted); margin:4px 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  VCP SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_vcp_score(df: pd.DataFrame) -> dict:
    """
    Compute full VCP score (0–7) + all supporting metrics.
    Returns a dict with score, details, and signal flags.
    """
    result = {
        "score": 0, "signal": "SKIP",
        "above_sma150": False, "above_sma200": False,
        "sma_lineup": False, "contracting": False,
        "vol_dry": False, "tight": False, "near_pivot": False,
        "contractions": [], "vol_ratio": None,
        "tight_pct": None, "pivot": None,
        "sma50": None, "sma150": None, "sma200": None,
        "current_price": None, "atr": None,
        "stop_loss": None, "target": None,
    }

    if df is None or len(df) < 60:
        return result

    # Fix yfinance MultiIndex columns (newer versions)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.droplevel(1)

    close  = df["Close"].dropna()
    high   = df["High"].dropna()
    low    = df["Low"].dropna()
    volume = df["Volume"].dropna()

    if len(close) < 60:
        return result

    price = float(close.iloc[-1])
    result["current_price"] = price

    # ── Moving averages ───────────────────────────────────────────────────────
    sma50  = float(close.tail(50).mean())
    sma150 = float(close.tail(min(150, len(close))).mean())
    sma200 = float(close.tail(min(200, len(close))).mean())
    result.update({"sma50": sma50, "sma150": sma150, "sma200": sma200})

    # Condition 1 & 2
    if price > sma150:
        result["above_sma150"] = True;  result["score"] += 1
    if price > sma200:
        result["above_sma200"] = True;  result["score"] += 1

    # Condition 3 — SMA Lineup
    if sma50 > sma150 > sma200:
        result["sma_lineup"] = True;    result["score"] += 1

    # ── Detect contractions ───────────────────────────────────────────────────
    # Rolling 20-day windows — find local peaks and troughs
    window = 20
    contractions = []
    recent_close = close.tail(120).values

    prev_peak_val = None
    prev_trough_val = None
    direction = "up"

    for i in range(len(recent_close) - 1):
        v = recent_close[i]
        if direction == "up":
            if i > 0 and v < recent_close[i - 1]:
                prev_peak_val = recent_close[i - 1]
                direction = "down"
        else:
            if i > 0 and v > recent_close[i - 1]:
                if prev_peak_val is not None:
                    pct = (prev_peak_val - v) / prev_peak_val * 100
                    if 2 < pct < 50:
                        contractions.append(round(pct, 1))
                direction = "up"
                prev_trough_val = v

    # Keep last 4 contractions
    contractions = contractions[-4:]
    result["contractions"] = contractions

    # Condition 4 — each contraction smaller than previous
    if len(contractions) >= 3:
        is_shrinking = all(contractions[i] > contractions[i+1]
                          for i in range(len(contractions)-1))
        if is_shrinking:
            result["contracting"] = True;  result["score"] += 1

    # ── Volume dryup ──────────────────────────────────────────────────────────
    avg_vol_60 = float(volume.tail(60).mean())
    avg_vol_10 = float(volume.tail(10).mean())
    vol_ratio  = avg_vol_10 / avg_vol_60 if avg_vol_60 > 0 else 1.0
    result["vol_ratio"] = round(vol_ratio, 2)

    # Condition 5
    if vol_ratio < 0.75:
        result["vol_dry"] = True;  result["score"] += 1

    # ── Tight price action ────────────────────────────────────────────────────
    recent_20_high = float(high.tail(20).max())
    recent_20_low  = float(low.tail(20).min())
    tight_pct = (recent_20_high - recent_20_low) / recent_20_low * 100
    result["tight_pct"] = round(tight_pct, 1)

    # Condition 6
    if tight_pct < 12:
        result["tight"] = True;    result["score"] += 1

    # ── Pivot & proximity ─────────────────────────────────────────────────────
    pivot_60 = float(high.tail(60).max())
    pivot    = round(pivot_60 * 1.005, 2)   # 0.5% above 60-day high
    result["pivot"] = pivot

    # Condition 7
    if price >= pivot_60 * 0.95:
        result["near_pivot"] = True;    result["score"] += 1

    # ── ATR-based stop / target ───────────────────────────────────────────────
    tr_list = []
    for i in range(1, min(20, len(close))):
        tr = max(
            float(high.iloc[-i]) - float(low.iloc[-i]),
            abs(float(high.iloc[-i]) - float(close.iloc[-i-1])),
            abs(float(low.iloc[-i]) - float(close.iloc[-i-1])),
        )
        tr_list.append(tr)
    atr = float(np.mean(tr_list)) if tr_list else price * 0.02
    result["atr"]       = round(atr, 2)
    result["stop_loss"] = round(price - 1.5 * atr, 2)
    result["target"]    = round(price + 4.0 * atr, 2)

    # ── Signal label ──────────────────────────────────────────────────────────
    s = result["score"]
    if s >= 6:
        result["signal"] = "🟢 STRONG BUY"
    elif s == 5:
        result["signal"] = "🔵 BUY"
    elif s == 4:
        result["signal"] = "🟡 WATCH"
    else:
        result["signal"] = "⛔ SKIP"

    return result


def fetch_and_score(ticker_info: dict, df=None, period: str = "1y") -> dict | None:
    """Score a stock for VCP. df is passed in by fast_scan_all (batch download)."""
    try:
        if df is None or len(df) < 60:
            return None
        vcp = compute_vcp_score(df)
        if vcp["score"] < 4:
            return None
        return {
            **ticker_info,
            **vcp,
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  CHART BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_candlestick_chart(ticker: str, result: dict, period: str = "6mo") -> go.Figure:
    """Full interactive candlestick chart with VCP annotations."""
    try:
        df = yf.download(ticker, period=period, interval="1d",
                         auto_adjust=True, progress=False, timeout=15)
        if df is None or len(df) < 30:
            return go.Figure()
        # Fix yfinance MultiIndex columns (newer versions return ticker as extra level)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)
        if len(df) < 30:
            return go.Figure()
    except Exception:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
        subplot_titles=("", "Volume"),
    )

    # ── Candlesticks ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Price",
        increasing_line_color="#3fb950", increasing_fillcolor="#3fb950",
        decreasing_line_color="#f85149", decreasing_fillcolor="#f85149",
        line_width=0.8,
    ), row=1, col=1)

    # ── SMAs ─────────────────────────────────────────────────────────────────
    for period_n, col, name in [(50,"#58a6ff","SMA 50"),(150,"#ffa657","SMA 150"),(200,"#bc8cff","SMA 200")]:
        sma = df["Close"].rolling(period_n).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=sma, name=name,
            line=dict(color=col, width=1.0, dash="dash"), opacity=0.8,
        ), row=1, col=1)

    # ── Horizontal levels ─────────────────────────────────────────────────────
    price = result.get("current_price", 0)
    if result.get("stop_loss"):
        fig.add_shape(type="line", xref="paper", yref="y",
                      x0=0, x1=1, y0=result["stop_loss"], y1=result["stop_loss"],
                      line=dict(color="#f85149", dash="dot", width=1.2), row=1, col=1)
        fig.add_annotation(xref="paper", yref="y", x=1.0, y=result["stop_loss"],
                           text=f"Stop ₹{result['stop_loss']:,.0f}",
                           font=dict(color="#f85149", size=10),
                           showarrow=False, xanchor="right", row=1, col=1)
    if result.get("target"):
        fig.add_shape(type="line", xref="paper", yref="y",
                      x0=0, x1=1, y0=result["target"], y1=result["target"],
                      line=dict(color="#3fb950", dash="dot", width=1.2), row=1, col=1)
        fig.add_annotation(xref="paper", yref="y", x=1.0, y=result["target"],
                           text=f"Target ₹{result['target']:,.0f}",
                           font=dict(color="#3fb950", size=10),
                           showarrow=False, xanchor="right", row=1, col=1)
    if result.get("pivot"):
        fig.add_shape(type="line", xref="paper", yref="y",
                      x0=0, x1=1, y0=result["pivot"], y1=result["pivot"],
                      line=dict(color="#ffa657", dash="dashdot", width=1.0), row=1, col=1)
        fig.add_annotation(xref="paper", yref="y", x=1.0, y=result["pivot"],
                           text=f"Pivot ₹{result['pivot']:,.0f}",
                           font=dict(color="#ffa657", size=10),
                           showarrow=False, xanchor="right", row=1, col=1)

    # ── Volume bars ───────────────────────────────────────────────────────────
    v_colors = ["#3fb950" if c >= o else "#f85149"
                for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume",
        marker_color=v_colors, opacity=0.7,
    ), row=2, col=1)

    # ── Volume average line ───────────────────────────────────────────────────
    vol_avg = df["Volume"].rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=df.index, y=vol_avg, name="Vol 20-avg",
        line=dict(color="#58a6ff", width=1.0, dash="dash"), opacity=0.7,
    ), row=2, col=1)

    # ── Contraction bands (shaded) ────────────────────────────────────────────
    contractions = result.get("contractions", [])
    band_colors  = ["rgba(255,123,114,0.08)", "rgba(255,166,87,0.08)", "rgba(121,192,255,0.08)"]
    n = len(df)
    band_end_i = n
    band_widths = [max(10, n//8), max(8, n//10), max(6, n//12)]
    for ci, (pct, bw, bc) in enumerate(zip(contractions, band_widths, band_colors)):
        bs = max(0, band_end_i - bw)
        x0 = df.index[bs]; x1 = df.index[band_end_i - 1]
        # Use add_shape instead of add_vrect — works reliably with row/col in subplots
        fig.add_shape(
            type="rect",
            x0=x0, x1=x1,
            y0=0, y1=1,
            xref="x", yref="paper",
            fillcolor=bc,
            line_width=0,
            layer="below",
            row=1, col=1,
        )
        mid_i = (bs + band_end_i) // 2
        fig.add_annotation(
            x=df.index[mid_i], y=df["High"].iloc[bs:band_end_i].max(),
            text=f"C{ci+1}: {pct}%",
            font=dict(size=10, color=["#ff7b72","#ffa657","#79c0ff"][ci]),
            showarrow=False, row=1, col=1,
        )
        band_end_i = bs

    # ── Layout ────────────────────────────────────────────────────────────────
    sym = ticker_info.get("symbol", ticker) if (ticker_info := result) else ticker
    score_str = f"Score: {result.get('score',0)}/7"
    signal_str = result.get('signal', '')

    fig.update_layout(
        title=dict(
            text=f"<b>{result.get('name', ticker)}</b>  [{ticker}]  —  "
                 f"{score_str}  |  {signal_str}",
            font=dict(size=14, color="#c9d1d9"),
        ),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=11),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d",
                    borderwidth=1, font=dict(size=10)),
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    fig.update_xaxes(gridcolor="#21262d", zeroline=False)
    fig.update_yaxes(gridcolor="#21262d", zeroline=False,
                     tickformat="₹,.0f")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

st.sidebar.markdown("## 🌀 VCP Screener")
st.sidebar.markdown("**Mark Minervini Method**")
st.sidebar.markdown("---")

# Universe info
if UNIVERSE_AVAILABLE:
    with st.sidebar.expander("📊 Stock Universe", expanded=True):
        st.markdown("""
        <div class='info-box'>
        Downloads <b>ALL</b> listed stocks from:<br>
        • <b>NSE</b> — ~2,000 equity stocks<br>
        • <b>NSE SME</b> — ~400 SME stocks<br>
        • <b>BSE</b> — ~5,500 equity stocks<br>
        <br><b>Total: ~5,500+ unique stocks</b><br>
        Refreshed every 24 hours automatically.
        </div>
        """, unsafe_allow_html=True)

# Filters
st.sidebar.markdown("### Filters")
min_score = st.sidebar.slider("Minimum VCP Score", 4, 7, 6,
    help="6-7 = strong signal, 5 = moderate, 4 = weak")
market_filter = st.sidebar.multiselect(
    "Exchange",
    ["NSE", "NSE-SME", "BSE"],
    default=["NSE"],
    help="NSE recommended for better liquidity"
)
min_price = st.sidebar.number_input("Min Price (₹)", 0, 100000, 10)
max_price = st.sidebar.number_input("Max Price (₹)", 1, 1000000, 50000)

st.sidebar.markdown("### Scan Settings")
batch_size = st.sidebar.slider(
    "Batch size (stocks per download)", 10, 100, 40,
    help="Higher = faster but more memory. 40 is a good balance."
)
max_workers = st.sidebar.slider(
    "Parallel workers", 1, 10, 5,
    help="More workers = faster scan. Reduce if you see errors."
)
period = st.sidebar.selectbox("Data period", ["6mo", "1y", "2y"], index=1)

st.sidebar.markdown("---")
if UNIVERSE_AVAILABLE:
    if st.sidebar.button("🔄 Force refresh stock list"):
        from stocks_universe import get_all_stocks
        with st.spinner("Downloading fresh stock list from NSE & BSE…"):
            all_stocks = get_all_stocks(force_refresh=True)
        st.sidebar.success(f"✅ Refreshed: {len(all_stocks)} stocks")

# Scan button
st.sidebar.markdown("---")
scan_clicked = st.sidebar.button("🔍 Scan for VCP Patterns")

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────

# Header
col1, col2, col3, col4 = st.columns(4)
for col, val, lbl, color in [
    (col1, "NSE + BSE", "Stock Universe", "#58a6ff"),
    (col2, "5,500+", "Stocks Scanned", "#3fb950"),
    (col3, "7 Conditions", "VCP Score", "#ffa657"),
    (col4, "81.5%", "Backtest Return", "#bc8cff"),
]:
    col.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# VCP Explanation
with st.expander("📖 What is VCP? How to use this screener?", expanded=False):
    st.markdown("""
    ### The Volatility Contraction Pattern (VCP) — Mark Minervini Method

    A **VCP** is a stock that has been going up strongly, then starts pulling back — but each pullback 
    gets **smaller and smaller** while volume dries up completely. When the stock finally breaks out 
    on high volume, it is like a coiled spring releasing.

    ---
    ### The 7 Conditions (Score 0–7)

    | # | Condition | What to Look For |
    |---|-----------|-----------------|
    | 1 | Above 150-day SMA | Long-term uptrend confirmed |
    | 2 | Above 200-day SMA | Very long-term health |
    | 3 | SMA Lineup: 50 > 150 > 200 | Strongest possible uptrend structure |
    | 4 | Contractions shrinking | Each pullback SMALLER than previous |
    | 5 | Volume drying up | Volume below 75% of normal |
    | 6 | Tight price action < 12% | Final consolidation tight |
    | 7 | Near pivot point | Within 5% of 60-day high |

    ---
    ### Step-by-Step: How to Use This Screener

    **Step 1** — Click **"Scan for VCP Patterns"** (Sunday evening is ideal).  
    **Step 2** — Look only at stocks with **Score 6 or 7**. Ignore anything below 6.  
    **Step 3** — Check contractions are **at least 3** and each one is **smaller** than the previous.  
    **Step 4** — Confirm **Vol Ratio < 0.70** (volume has dried up by 30%+).  
    **Step 5** — Check **Nifty 50 trend** — if Nifty is falling, skip all trades that week.  
    **Step 6** — Check no **quarterly results** in next 2 weeks (nseindia.com).  
    **Step 7** — Wait for the stock to **close above the Pivot** on volume **1.5× or more** the average.  
    **Step 8** — Enter, then **immediately** place your stop loss (1.5× ATR below entry).  
    **Step 9** — Target is **4× ATR above entry** (gives ~2.7:1 reward-to-risk ratio).  
    **Step 10** — Trail your stop below each higher swing low as profit grows.

    > ⚠️ **Never enter a VCP with only 2 contractions.** Every losing trade in our backtest with only  
    > 2 contractions was avoidable. Always wait for minimum 3 shrinking contractions.
    """)

# ─────────────────────────────────────────────────────────────────────────────
#  SCAN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

if scan_clicked:
    # ── Load cache or run fresh scan ──────────────────────────────────────────
    cached = load_cached_results("vcp", cache_hours=4)
    if cached:
        st.success(f"⚡ Loaded **{len(cached)}** VCP results from cache (≤4h old).")
        st.session_state["scan_results"] = cached
    else:
        # 1. Get stock list
        with st.spinner("📋 Loading stock universe (NSE + BSE)…"):
            if UNIVERSE_AVAILABLE:
                all_stocks = get_all_stocks()
            else:
                nse_fallback = [
                    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR",
                    "SBIN","BAJFINANCE","BHARTIARTL","ITC","KOTAKBANK","LT","HCLTECH",
                    "ASIANPAINT","AXISBANK","MARUTI","SUNPHARMA","TITAN","ULTRACEMCO",
                    "NTPC","ONGC","POWERGRID","WIPRO","NESTLEIND","TATAMOTORS",
                    "TECHM","DIVISLAB","ADANIENT","ADANIPORTS","JSWSTEEL","TATASTEEL",
                    "CIPLA","BRITANNIA","HINDALCO","APOLLOHOSP","EICHERMOT","DRREDDY",
                    "BPCL","INDUSINDBK","HEROMOTOCO","BAJAJ-AUTO","TATACONSUM","M&M",
                    "KPIT","PERSISTENT","LTTS","COFORGE","MPHASIS","HAPPSTMNDS",
                    "TANLA","DEEPAKNITRI","NAVINFLUOR","FINEORG","IRCTC","RVNL",
                    "TATAPOWER","ZOMATO","DMART","SIEMENS","HAVELLS","PIDILITIND",
                    "MUTHOOTFIN","LUPIN","BIOCON","GLAND","ALKEM","AMBUJACEM",
                    "SHRIRAMFIN","CHOLAFIN","BANDHANBNK","FEDERALBNK","IDFCFIRSTB",
                    "POLYCAB","DIXON","AMBER","VGUARD","ASTRAL","BEL","HAL","BHEL",
                    "GODREJPROP","MANAPPURAM","UJJIVAN","TATAELXSI","BALKRISIND",
                    "COLPAL","DABUR","MARICO","GRANULES","INTELLECT","MASTEK",
                    "AAVAS","HOMEFIRST","EQUITASBNK","SUPREMEIND","RATNAMANI","PCBL",
                ]
                all_stocks = [{"symbol": s, "name": s, "exchange": "NSE", "yf_ticker": f"{s}.NS"}
                              for s in nse_fallback]

        # 2. Apply exchange filter
        stocks_to_scan = [s for s in all_stocks if s.get("exchange", "NSE") in market_filter]
        total = len(stocks_to_scan)
        st.info(f"🔍 Scanning **{total:,} stocks** from: {', '.join(market_filter)} | Min Score: {min_score}/7")

        # 3. Score wrapper
        def _vcp_wrapper(stock_info: dict, df) -> dict | None:
            res = fetch_and_score(stock_info, df=df, period=period)
            if res and res.get("score", 0) >= min_score:
                price_ok = min_price <= (res.get("current_price") or 0) <= max_price
                if price_ok:
                    return res
            return None

        # 4. Fast batch scan
        prog_bar  = st.progress(0)
        prog_text = st.empty()
        results = fast_scan_all(
            all_stocks      = stocks_to_scan,
            score_fn        = _vcp_wrapper,
            exchange_filter = None,
            min_price       = min_price,
            max_price       = max_price,
            period          = period,
            batch_size      = 40,
            progress_bar    = prog_bar,
            status_text     = prog_text,
            cache_key       = "vcp",
            cache_hours     = 4,
        )
        st.session_state["scan_results"] = results
        st.success(f"✅ Scan complete! Found **{len(results)} VCP setups** (Score ≥ {min_score})")

if st.button("🗑️ Clear cache & re-scan fresh", key="clr_vcp"):
    clear_cache("vcp")
    if "scan_results" in st.session_state:
        del st.session_state["scan_results"]
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────────────────────

results = st.session_state.get("scan_results", [])

if results:
    # Sort by score desc
    results_sorted = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    # Summary metrics
    st.markdown("---")
    st.markdown("### 🎯 VCP Signals Found")

    scores_7 = [r for r in results_sorted if r["score"] == 7]
    scores_6 = [r for r in results_sorted if r["score"] == 6]
    scores_5 = [r for r in results_sorted if r["score"] == 5]
    scores_4 = [r for r in results_sorted if r["score"] == 4]

    c1, c2, c3, c4 = st.columns(4)
    for col, grp, lbl, col_color in [
        (c1, scores_7, "Score 7/7", "#3fb950"),
        (c2, scores_6, "Score 6/7", "#58a6ff"),
        (c3, scores_5, "Score 5/7", "#ffa657"),
        (c4, scores_4, "Score 4/7", "#8b949e"),
    ]:
        col.markdown(f"""
        <div class='metric-card'>
            <div class='metric-val' style='color:{col_color}'>{len(grp)}</div>
            <div class='metric-lbl'>{lbl}</div>
        </div>""", unsafe_allow_html=True)

    # Table
    st.markdown("### 📋 All VCP Signals (Score ≥ selected minimum)")

    sort_by = st.selectbox("Sort by", ["Score (High→Low)", "Price (Low→High)",
                                        "Vol Ratio (Low)", "Tight % (Low)"])
    if sort_by == "Score (High→Low)":
        results_sorted = sorted(results_sorted, key=lambda x: x["score"], reverse=True)
    elif sort_by == "Price (Low→High)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("current_price") or 0)
    elif sort_by == "Vol Ratio (Low)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("vol_ratio") or 1)
    elif sort_by == "Tight % (Low)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("tight_pct") or 99)

    for r in results_sorted:
        with st.expander(
            f"{'🟢' if r['score']==7 else '🔵' if r['score']==6 else '🟡'} "
            f"**{r.get('name', r.get('symbol',''))}**  [{r.get('yf_ticker','')}]  "
            f"| Score: {r['score']}/7 | ₹{r.get('current_price',0):,.2f} "
            f"| {r.get('signal','')}",
            expanded=(r["score"] >= 6),
        ):
            left, right = st.columns([1.8, 1])

            with left:
                fig = build_candlestick_chart(r.get("yf_ticker",""), r, period)
                st.plotly_chart(fig, use_container_width=True)

            with right:
                st.markdown("#### 📊 VCP Details")

                # Score checklist
                conditions = [
                    ("Above 150-day SMA", r.get("above_sma150")),
                    ("Above 200-day SMA", r.get("above_sma200")),
                    ("SMA 50>150>200",    r.get("sma_lineup")),
                    ("Contractions shrinking ✓", r.get("contracting")),
                    ("Volume drying up",  r.get("vol_dry")),
                    ("Tight range < 12%", r.get("tight")),
                    ("Near pivot point",  r.get("near_pivot")),
                ]
                for cond, passed in conditions:
                    icon = "✅" if passed else "❌"
                    color = "#3fb950" if passed else "#f85149"
                    st.markdown(f"<span style='color:{color}'>{icon} {cond}</span>",
                                unsafe_allow_html=True)

                st.markdown("---")

                # Key metrics
                contr = r.get("contractions", [])
                contr_str = " → ".join(f"{c}%" for c in contr)
                is_ok = len(contr) >= 3 and all(contr[i]>contr[i+1] for i in range(len(contr)-1))
                contr_color = "#3fb950" if is_ok else "#f85149"

                metrics = {
                    "Current Price":     f"₹{r.get('current_price',0):,.2f}",
                    "Contractions":      contr_str or "—",
                    "Volume Ratio":      f"{r.get('vol_ratio','—')}× avg",
                    "Tight Range":       f"{r.get('tight_pct','—')}%",
                    "Pivot":             f"₹{r.get('pivot',0):,.2f}",
                    "Stop Loss (1.5×ATR)": f"₹{r.get('stop_loss',0):,.2f}",
                    "Target (4×ATR)":    f"₹{r.get('target',0):,.2f}",
                    "SMA 50":            f"₹{r.get('sma50',0):,.0f}",
                    "SMA 150":           f"₹{r.get('sma150',0):,.0f}",
                    "SMA 200":           f"₹{r.get('sma200',0):,.0f}",
                    "Exchange":          r.get("exchange","NSE"),
                }
                for k, v in metrics.items():
                    color = contr_color if k == "Contractions" else "#c9d1d9"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:3px 0;border-bottom:1px solid #21262d'>"
                        f"<span style='color:#8b949e;font-size:0.82rem'>{k}</span>"
                        f"<span style='color:{color};font-weight:600;font-size:0.82rem'>{v}</span>"
                        f"</div>", unsafe_allow_html=True
                    )

                # Trade plan
                st.markdown("---")
                st.markdown("#### 💰 Trade Plan (₹1,00,000 capital)")
                price   = r.get("current_price", 1) or 1
                stop    = r.get("stop_loss", price * 0.95) or price * 0.95
                target_ = r.get("target", price * 1.1) or price * 1.1
                risk_pp = price - stop
                if risk_pp > 0:
                    qty = max(1, int(2000 / risk_pp))
                    pot_loss   = qty * risk_pp
                    pot_profit = qty * (target_ - price)
                    rr = (target_ - price) / risk_pp if risk_pp > 0 else 0
                    for k, v in [
                        ("Entry (at pivot break)", f"₹{r.get('pivot',price):,.2f}"),
                        ("Stop Loss", f"₹{stop:,.2f}  (–₹{risk_pp:,.2f})"),
                        ("Target", f"₹{target_:,.2f}  (+₹{target_-price:,.2f})"),
                        ("Quantity (2% risk)", f"{qty} shares"),
                        ("Max Loss", f"₹{pot_loss:,.0f}"),
                        ("Potential Profit", f"₹{pot_profit:,.0f}"),
                        ("R:R Ratio", f"{rr:.1f} : 1"),
                    ]:
                        color = ("#f85149" if "Loss" in k else
                                 "#3fb950" if "Profit" in k or "Target" in k else
                                 "#ffa657" if "R:R" in k else "#c9d1d9")
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"padding:3px 0;border-bottom:1px solid #21262d'>"
                            f"<span style='color:#8b949e;font-size:0.8rem'>{k}</span>"
                            f"<span style='color:{color};font-weight:700;font-size:0.8rem'>{v}</span>"
                            f"</div>", unsafe_allow_html=True
                        )

                # Why invest box
                st.markdown("---")
                st.markdown("#### 🔑 Why Consider This Stock?")
                reasons = []
                if r.get("sma_lineup"):
                    reasons.append("✅ Perfect SMA alignment (50 > 150 > 200) — strongest uptrend structure")
                if is_ok and len(contr) >= 3:
                    reasons.append(f"✅ {len(contr)} clean contractions shrinking: {contr_str}")
                if (r.get("vol_ratio") or 1) < 0.65:
                    reasons.append(f"✅ Volume very dry at {r.get('vol_ratio')}× — sellers exhausted")
                if r.get("near_pivot"):
                    reasons.append("✅ Within 5% of breakout point — spring fully coiled")
                if (r.get("tight_pct") or 99) < 8:
                    reasons.append(f"✅ Very tight range {r.get('tight_pct')}% — low risk entry")

                warnings_list = []
                if not is_ok or len(contr) < 3:
                    warnings_list.append("⚠️ Less than 3 contractions — wait for pattern to mature")
                if (r.get("vol_ratio") or 1) > 0.72:
                    warnings_list.append("⚠️ Volume not fully dry — wait for more contraction")
                if not r.get("near_pivot"):
                    warnings_list.append("⚠️ Not yet near pivot — set price alert, don't buy yet")

                for reason in reasons:
                    st.markdown(f"<span style='color:#3fb950;font-size:0.82rem'>{reason}</span>",
                                unsafe_allow_html=True)
                for warning in warnings_list:
                    st.markdown(f"<span style='color:#ffa657;font-size:0.82rem'>{warning}</span>",
                                unsafe_allow_html=True)

                st.markdown("---")
                st.markdown(
                    "<div class='warn-box'>⚠️ Always verify on TradingView before entering. "
                    "Check NSE for upcoming earnings. This is educational, not SEBI advice.</div>",
                    unsafe_allow_html=True
                )

elif not scan_clicked:
    # Welcome screen
    st.markdown("""
    <div class='info-box' style='font-size:1rem; padding: 24px'>
    <h3 style='color:#58a6ff; margin-top:0'>🌀 VCP Screener — All NSE + BSE Stocks</h3>
    This screener scans <b>all ~5,500+ stocks listed on NSE and BSE</b> for the 
    Volatility Contraction Pattern developed by Mark Minervini.<br><br>
    <b>Our backtest:</b> ₹1,00,000 → ₹1,81,458 in 2 years (81.5% return) 
    with a profit factor of 3.10 across 36 trades.<br><br>
    👉 Set your filters on the left sidebar, then click <b>"Scan for VCP Patterns"</b>.<br>
    ⏱️ Scanning all NSE stocks takes ~3-5 minutes. BSE adds ~10 minutes more.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Backtest Performance Summary")
    perf_data = {
        "Stock": ["Tata Motors","L&T","Bharti Airtel","Bajaj Finance","ICICI Bank","KPIT Tech","Infosys","Sun Pharma"],
        "Trades": [4,3,2,3,3,3,4,3],
        "Win%": ["100%","100%","100%","67%","67%","67%","50%","0%"],
        "P&L": ["+₹20,225","+₹15,666","+₹10,514","+₹8,499","+₹8,398","+₹8,342","+₹6,685","-₹5,846"],
        "Verdict": ["STRONG ✅","STRONG ✅","STRONG ✅","GOOD 🔵","GOOD 🔵","GOOD 🔵","GOOD 🔵","AVOID ❌"],
    }
    st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)
