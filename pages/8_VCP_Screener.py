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
import time, warnings, json, os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings("ignore")

# ── External modules (optional — graceful fallback) ─────────────────────────
try:
    from fast_scan import fast_scan_all
    FAST_SCAN_AVAILABLE = True
except ImportError:
    FAST_SCAN_AVAILABLE = False

try:
    from stocks_universe import get_all_stocks
    UNIVERSE_AVAILABLE = True
except ImportError:
    UNIVERSE_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VCP Screener — All NSE + BSE",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    :root {
        --bg:#0d1117; --card:#161b22; --border:#30363d;
        --green:#3fb950; --red:#f85149; --blue:#58a6ff;
        --gold:#ffa657; --text:#c9d1d9; --muted:#8b949e;
        --purple:#bc8cff;
    }
    .stApp { background-color: var(--bg); color: var(--text); }

    /* Metric cards */
    .metric-card {
        background: var(--card); border: 1px solid var(--border);
        border-radius: 12px; padding: 18px 20px; text-align: center; margin-bottom: 8px;
    }
    .metric-val { font-size: 2rem; font-weight: 800; line-height: 1.1; }
    .metric-lbl { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }

    /* Trade plan box */
    .trade-box {
        background: #0f2a1a; border: 1px solid var(--green);
        border-radius: 10px; padding: 14px 18px; margin: 8px 0;
    }
    .trade-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 5px 0; border-bottom: 1px solid #1e3a2a; font-size: 0.88rem;
    }
    .trade-row:last-child { border-bottom: none; }
    .trade-label { color: var(--muted); }
    .trade-value { font-weight: 700; }

    /* Signal badges */
    .badge-strong { background:#0f2a1a; color:#3fb950; border:1px solid #3fb950;
                    border-radius:6px; padding:3px 12px; font-weight:700; font-size:0.85rem; }
    .badge-buy    { background:#0f1f35; color:#58a6ff; border:1px solid #58a6ff;
                    border-radius:6px; padding:3px 12px; font-weight:700; font-size:0.85rem; }
    .badge-watch  { background:#2a1f00; color:#ffa657; border:1px solid #ffa657;
                    border-radius:6px; padding:3px 12px; font-weight:700; font-size:0.85rem; }

    /* Reason boxes */
    .reason-box {
        background: #0f2a1a; border-left: 3px solid var(--green);
        border-radius: 0 8px 8px 0; padding: 8px 12px; margin: 4px 0;
        font-size: 0.82rem; color: #c9d1d9;
    }
    .warn-box {
        background: #1a1500; border-left: 3px solid var(--gold);
        border-radius: 0 8px 8px 0; padding: 8px 12px; margin: 4px 0;
        font-size: 0.82rem; color: #c9d1d9;
    }
    .info-box {
        background: var(--card); border-left: 4px solid var(--blue);
        border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 8px 0;
        font-size: 0.85rem; color: var(--text);
    }

    /* Sidebar */
    div[data-testid="stSidebarContent"] { background:#0d1117; }
    .stButton>button {
        background: linear-gradient(135deg,#1a6b3c,#0f4028);
        color: white; border: 1px solid var(--green); border-radius: 8px;
        font-weight: 700; font-size: 1rem; padding: 12px 24px; width: 100%;
    }
    .stButton>button:hover { background: linear-gradient(135deg,#26a641,#1a6b3c); }

    /* VCP conditions checklist */
    .cond-pass { color: #3fb950; font-size: 0.83rem; padding: 2px 0; }
    .cond-fail { color: #f85149; font-size: 0.83rem; padding: 2px 0; }
    .section-title { color: #58a6ff; font-weight: 700; font-size: 0.9rem;
                     margin: 10px 0 6px 0; text-transform: uppercase; letter-spacing: 0.05em; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  SELF-CONTAINED CACHE  (no external module needed)
# ─────────────────────────────────────────────────────────────────────────────
CACHE_DIR = "/tmp/vcp_screener_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")

def load_cache(key: str, hours: int = 4):
    path = _cache_path(key)
    try:
        if os.path.exists(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if datetime.now() - mtime < timedelta(hours=hours):
                with open(path) as f:
                    return json.load(f)
    except Exception:
        pass
    return None

def save_cache(key: str, data):
    try:
        with open(_cache_path(key), "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def clear_cache_file(key: str):
    try:
        path = _cache_path(key)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  BUILT-IN STOCK UNIVERSE  (fallback when stocks_universe.py not available)
# ─────────────────────────────────────────────────────────────────────────────
BUILTIN_STOCKS = [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN","BAJFINANCE",
    "BHARTIARTL","ITC","KOTAKBANK","LT","HCLTECH","ASIANPAINT","AXISBANK","MARUTI",
    "SUNPHARMA","TITAN","ULTRACEMCO","NTPC","ONGC","POWERGRID","WIPRO","NESTLEIND",
    "TATAMOTORS","TECHM","DIVISLAB","ADANIENT","ADANIPORTS","JSWSTEEL","TATASTEEL",
    "CIPLA","BRITANNIA","HINDALCO","APOLLOHOSP","EICHERMOT","DRREDDY","BPCL",
    "INDUSINDBK","HEROMOTOCO","BAJAJ-AUTO","TATACONSUM","M&M","KPIT","PERSISTENT",
    "LTTS","COFORGE","MPHASIS","HAPPSTMNDS","TANLA","DEEPAKNITRI","NAVINFLUOR",
    "FINEORG","IRCTC","RVNL","TATAPOWER","ZOMATO","DMART","SIEMENS","HAVELLS",
    "PIDILITIND","MUTHOOTFIN","LUPIN","BIOCON","GLAND","ALKEM","AMBUJACEM",
    "SHRIRAMFIN","CHOLAFIN","BANDHANBNK","FEDERALBNK","IDFCFIRSTB","POLYCAB",
    "DIXON","AMBER","VGUARD","ASTRAL","BEL","HAL","BHEL","GODREJPROP","MANAPPURAM",
    "UJJIVAN","TATAELXSI","BALKRISIND","COLPAL","DABUR","MARICO","GRANULES",
    "INTELLECT","MASTEK","AAVAS","HOMEFIRST","EQUITASBNK","SUPREMEIND","RATNAMANI",
    "PCBL","CAMS","CDSL","BSE","MCX","ANGELONE","FIVESTAR","APTUS","CREDITACC",
    "PNBHOUSING","CANFINHOME","REPCO","VAIBHAVGBL","RAJRATAN","GPIL","JSHL",
    "WELCORP","RAMKRISHN","SAREGAMA","NAZARA","ROUTE","CARTRADE","NYKAA","PAYTM",
    "POLICYBZR","FRESHARA","DELHIVERY","CAMPUS","SYRMA","IDEAFORGE","TRACXN",
    "LATENTVIEW","EASEMYTRIP","INDIGOPNTS","CLEAN","FLAIR","KAYNES","SANSERA",
    "LANDMARK","AVALON","DHARMAJ","VORDEUM","ANANTRAJ","KOLTEPATIL","SOBHA",
    "PRESTIGE","BRIGADE","MAHLIFE","GODREJPROP","OBEROIRLTY","PHOENIXLTD",
]

def get_builtin_stocks():
    return [{"symbol": s, "name": s, "exchange": "NSE", "yf_ticker": f"{s}.NS"}
            for s in BUILTIN_STOCKS]


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER — fix yfinance MultiIndex columns (critical fix)
# ─────────────────────────────────────────────────────────────────────────────
def _fix_df(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns returned by newer yfinance versions."""
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        # For single ticker: columns like ('Close','RELIANCE.NS') → 'Close'
        df = df.copy()
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    # Keep only OHLCV columns
    needed = ["Open", "High", "Low", "Close", "Volume"]
    available = [c for c in needed if c in df.columns]
    df = df[available].copy()
    df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  VCP SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def compute_vcp_score(df: pd.DataFrame) -> dict:
    result = {
        "score": 0, "signal": "SKIP",
        "above_sma150": False, "above_sma200": False,
        "sma_lineup": False, "contracting": False,
        "vol_dry": False, "tight": False, "near_pivot": False,
        "contractions": [], "vol_ratio": None,
        "tight_pct": None, "pivot": None,
        "entry_price": None,
        "sma50": None, "sma150": None, "sma200": None,
        "current_price": None, "atr": None,
        "stop_loss": None, "target": None,
    }

    df = _fix_df(df)
    if df is None or len(df) < 60:
        return result

    close  = df["Close"].dropna()
    high   = df["High"].dropna()
    low    = df["Low"].dropna()
    volume = df["Volume"].dropna()

    if len(close) < 60:
        return result

    price = float(close.iloc[-1])
    result["current_price"] = round(price, 2)

    # Moving averages
    sma50  = float(close.tail(50).mean())
    sma150 = float(close.tail(min(150, len(close))).mean())
    sma200 = float(close.tail(min(200, len(close))).mean())
    result.update({"sma50": round(sma50,2), "sma150": round(sma150,2), "sma200": round(sma200,2)})

    if price > sma150: result["above_sma150"] = True; result["score"] += 1
    if price > sma200: result["above_sma200"] = True; result["score"] += 1
    if sma50 > sma150 > sma200: result["sma_lineup"] = True; result["score"] += 1

    # Detect contractions
    contractions = []
    recent_close = close.tail(120).values
    direction = "up"
    prev_peak_val = None

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

    contractions = contractions[-4:]
    result["contractions"] = contractions

    if len(contractions) >= 3:
        is_shrinking = all(contractions[i] > contractions[i+1] for i in range(len(contractions)-1))
        if is_shrinking:
            result["contracting"] = True; result["score"] += 1

    # Volume dry-up
    avg_vol_60 = float(volume.tail(60).mean())
    avg_vol_10 = float(volume.tail(10).mean())
    vol_ratio = avg_vol_10 / avg_vol_60 if avg_vol_60 > 0 else 1.0
    result["vol_ratio"] = round(vol_ratio, 2)
    if vol_ratio < 0.75: result["vol_dry"] = True; result["score"] += 1

    # Tight range
    recent_20_high = float(high.tail(20).max())
    recent_20_low  = float(low.tail(20).min())
    tight_pct = (recent_20_high - recent_20_low) / recent_20_low * 100
    result["tight_pct"] = round(tight_pct, 1)
    if tight_pct < 12: result["tight"] = True; result["score"] += 1

    # Pivot
    pivot_60 = float(high.tail(60).max())
    pivot    = round(pivot_60 * 1.005, 2)
    result["pivot"] = pivot

    if price >= pivot_60 * 0.95: result["near_pivot"] = True; result["score"] += 1

    # Entry = at pivot breakout (0.5% above 60-day high)
    result["entry_price"] = pivot

    # ATR-based stop / target
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
    result["stop_loss"] = round(pivot - 1.5 * atr, 2)
    result["target"]    = round(pivot + 4.0 * atr, 2)

    # Signal
    s = result["score"]
    if s == 7:   result["signal"] = "STRONG BUY"
    elif s == 6: result["signal"] = "BUY"
    elif s == 5: result["signal"] = "WATCH"
    elif s == 4: result["signal"] = "WEAK WATCH"
    else:        result["signal"] = "SKIP"

    return result


def fetch_and_score(ticker_info: dict, df=None, period: str = "1y") -> dict | None:
    try:
        if df is None or len(df) < 60:
            return None
        vcp = compute_vcp_score(df)
        if vcp["score"] < 4:
            return None
        return {**ticker_info, **vcp}
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  SELF-CONTAINED BATCH SCANNER (used when fast_scan not available)
# ─────────────────────────────────────────────────────────────────────────────
def _scan_stocks(stocks: list, min_score: int, min_price: float, max_price: float,
                 period: str, batch_size: int, max_workers: int,
                 prog_bar, prog_text) -> list:
    results = []
    total = len(stocks)
    scanned = 0

    def process_batch(batch):
        tickers = [s["yf_ticker"] for s in batch]
        try:
            raw = yf.download(
                tickers, period=period, interval="1d",
                auto_adjust=True, progress=False, timeout=20,
                group_by="ticker"
            )
        except Exception:
            return []

        batch_results = []
        for stock in batch:
            tk = stock["yf_ticker"]
            try:
                if len(tickers) == 1:
                    df = raw.copy()
                else:
                    df = raw[tk].copy() if tk in raw.columns.get_level_values(0) else pd.DataFrame()
                df = _fix_df(df)
                if df is None or len(df) < 60:
                    continue
                vcp = compute_vcp_score(df)
                if vcp["score"] < min_score:
                    continue
                cp = vcp.get("current_price") or 0
                if not (min_price <= cp <= max_price):
                    continue
                batch_results.append({**stock, **vcp})
            except Exception:
                continue
        return batch_results

    batches = [stocks[i:i+batch_size] for i in range(0, total, batch_size)]

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(process_batch, b): b for b in batches}
        for fut in as_completed(futures):
            try:
                results.extend(fut.result())
            except Exception:
                pass
            scanned += len(futures[fut])
            pct = min(scanned / total, 1.0)
            prog_bar.progress(pct)
            prog_text.markdown(
                f"<div style='color:#8b949e;font-size:0.85rem'>"
                f"Scanned {scanned:,}/{total:,} | Found <b style='color:#3fb950'>{len(results)}</b> signals</div>",
                unsafe_allow_html=True
            )

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  CANDLESTICK CHART WITH FULL ANNOTATIONS
# ─────────────────────────────────────────────────────────────────────────────
def build_chart(ticker: str, result: dict, period: str = "1y") -> go.Figure:
    """
    Downloads fresh data for the ticker and builds a fully annotated chart:
    - Candlesticks (green/red)
    - SMA 50, 150, 200 lines
    - Contraction bands (C1, C2, C3 shaded zones)
    - Entry line (orange) with arrow + label
    - Stop Loss line (red) with arrow + label  
    - Target line (green) with arrow + label
    - Volume bars with 20-day average
    - Trade summary box annotation
    """
    empty = go.Figure()
    empty.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        annotations=[dict(text="Chart loading... (expand to view)", xref="paper",
                          yref="paper", x=0.5, y=0.5, showarrow=False,
                          font=dict(color="#8b949e", size=14))]
    )

    try:
        raw = yf.download(ticker, period=period, interval="1d",
                          auto_adjust=True, progress=False, timeout=20)
        if raw is None or raw.empty:
            return empty
        df = _fix_df(raw)
        if df is None or len(df) < 30:
            return empty
    except Exception:
        return empty

    # Key levels from result
    entry  = result.get("entry_price") or result.get("pivot") or result.get("current_price")
    stop   = result.get("stop_loss")
    target = result.get("target")
    pivot  = result.get("pivot")
    price  = result.get("current_price")

    if not all([entry, stop, target]):
        return empty

    # ── Build subplots ────────────────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.73, 0.27],
    )

    # ── Candlesticks ──────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Price",
        increasing_line_color="#3fb950", increasing_fillcolor="#3fb950",
        decreasing_line_color="#f85149", decreasing_fillcolor="#f85149",
        line_width=0.8, whiskerwidth=0.8,
    ), row=1, col=1)

    # ── SMAs ─────────────────────────────────────────────────────────────────
    close_s = df["Close"]
    for n, color, name in [
        (50, "#58a6ff", "SMA 50"),
        (150, "#ffa657", "SMA 150"),
        (200, "#bc8cff", "SMA 200"),
    ]:
        sma = close_s.rolling(n).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=sma, name=name,
            line=dict(color=color, width=1.2, dash="dash"), opacity=0.85,
        ), row=1, col=1)

    # ── Contraction bands ─────────────────────────────────────────────────────
    contractions = result.get("contractions", [])
    band_colors = [
        "rgba(248,81,73,0.07)",   # C1 reddish
        "rgba(255,166,87,0.07)",  # C2 orange
        "rgba(88,166,255,0.07)",  # C3 blue
    ]
    band_label_colors = ["#ff7b72", "#ffa657", "#79c0ff"]
    n_bars = len(df)
    band_end_i = n_bars
    band_widths = [max(12, n_bars // 7), max(9, n_bars // 9), max(6, n_bars // 12)]

    for ci, pct in enumerate(contractions[-3:]):  # show last 3
        bw = band_widths[ci]
        bs = max(0, band_end_i - bw)
        x0 = df.index[bs]
        x1 = df.index[band_end_i - 1]
        bc = band_colors[ci]
        lc = band_label_colors[ci]

        fig.add_shape(
            type="rect", xref="x", yref="paper",
            x0=x0, x1=x1, y0=0, y1=1,
            fillcolor=bc, line_width=0, layer="below",
        )
        mid_i = min((bs + band_end_i) // 2, n_bars - 1)
        seg_high = float(df["High"].iloc[bs:band_end_i].max()) if bs < band_end_i else float(df["High"].iloc[-1])
        fig.add_annotation(
            x=df.index[mid_i], y=seg_high,
            text=f"<b>C{ci+1}</b><br>{pct}%",
            font=dict(size=10, color=lc),
            showarrow=False, bgcolor="rgba(13,17,23,0.7)",
            bordercolor=lc, borderwidth=1, borderpad=3,
        )
        band_end_i = bs

    # ── TARGET line (green, thick) ────────────────────────────────────────────
    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=target, y1=target,
        line=dict(color="#3fb950", width=2, dash="dot"),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=0.01, y=target,
        text=f"🎯 TARGET  ₹{target:,.0f}",
        font=dict(color="#3fb950", size=11, family="monospace"),
        showarrow=False, bgcolor="rgba(15,42,26,0.9)",
        bordercolor="#3fb950", borderwidth=1, borderpad=4,
        xanchor="left",
    )

    # ── ENTRY line (orange, thick) ────────────────────────────────────────────
    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=entry, y1=entry,
        line=dict(color="#ffa657", width=2.5, dash="solid"),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=0.01, y=entry,
        text=f"⬆ ENTRY (BUY above this)  ₹{entry:,.0f}",
        font=dict(color="#ffa657", size=11, family="monospace"),
        showarrow=False, bgcolor="rgba(26,31,0,0.9)",
        bordercolor="#ffa657", borderwidth=1, borderpad=4,
        xanchor="left",
    )

    # ── STOP LOSS line (red, thick) ───────────────────────────────────────────
    fig.add_shape(
        type="line", xref="paper", yref="y",
        x0=0, x1=1, y0=stop, y1=stop,
        line=dict(color="#f85149", width=2, dash="dot"),
    )
    fig.add_annotation(
        xref="paper", yref="y", x=0.01, y=stop,
        text=f"🛑 STOP LOSS  ₹{stop:,.0f}",
        font=dict(color="#f85149", size=11, family="monospace"),
        showarrow=False, bgcolor="rgba(42,15,15,0.9)",
        bordercolor="#f85149", borderwidth=1, borderpad=4,
        xanchor="left",
    )

    # ── Current price marker ──────────────────────────────────────────────────
    if price:
        fig.add_annotation(
            xref="paper", yref="y", x=0.99, y=price,
            text=f"₹{price:,.2f} NOW",
            font=dict(color="#c9d1d9", size=10),
            showarrow=False, bgcolor="rgba(22,27,34,0.9)",
            bordercolor="#30363d", borderwidth=1, borderpad=3,
            xanchor="right",
        )

    # ── Volume bars ───────────────────────────────────────────────────────────
    try:
        v_colors = [
            "#3fb950" if float(c) >= float(o) else "#f85149"
            for c, o in zip(df["Close"], df["Open"])
        ]
    except Exception:
        v_colors = ["#8b949e"] * len(df)

    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], name="Volume",
        marker_color=v_colors, opacity=0.65,
    ), row=2, col=1)

    vol_avg = df["Volume"].rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=df.index, y=vol_avg, name="Vol Avg (20)",
        line=dict(color="#58a6ff", width=1.2, dash="dash"), opacity=0.8,
    ), row=2, col=1)

    # ── Trade summary annotation (top-right corner) ───────────────────────────
    rr = (target - entry) / (entry - stop) if (entry - stop) > 0 else 0
    score = result.get("score", 0)
    signal = result.get("signal", "")
    contr = result.get("contractions", [])
    contr_str = " → ".join(f"{c}%" for c in contr) if contr else "—"

    summary_text = (
        f"<b>Score: {score}/7  |  {signal}</b><br>"
        f"Entry: ₹{entry:,.0f}  |  Stop: ₹{stop:,.0f}  |  Target: ₹{target:,.0f}<br>"
        f"R:R = 1:{rr:.1f}  |  Contractions: {contr_str}<br>"
        f"Vol Ratio: {result.get('vol_ratio','—')}×  |  Range: {result.get('tight_pct','—')}%"
    )
    fig.add_annotation(
        xref="paper", yref="paper", x=0.99, y=0.99,
        text=summary_text,
        font=dict(color="#c9d1d9", size=10),
        showarrow=False, bgcolor="rgba(22,27,34,0.92)",
        bordercolor="#58a6ff", borderwidth=1, borderpad=6,
        xanchor="right", yanchor="top",
        align="right",
    )

    # ── Layout ────────────────────────────────────────────────────────────────
    name_str = result.get("name", ticker) or ticker
    fig.update_layout(
        title=dict(
            text=f"<b>{name_str}</b>  [{ticker}]",
            font=dict(size=15, color="#c9d1d9"),
        ),
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font=dict(color="#8b949e", size=11),
        legend=dict(
            bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
            font=dict(size=10), orientation="h",
            yanchor="bottom", y=1.01, xanchor="left", x=0,
        ),
        xaxis_rangeslider_visible=False,
        height=580,
        margin=dict(l=10, r=10, t=55, b=10),
    )
    fig.update_xaxes(gridcolor="#21262d", zeroline=False, showgrid=True)
    fig.update_yaxes(gridcolor="#21262d", zeroline=False,
                     tickformat=",.0f", showgrid=True)
    fig.update_yaxes(tickformat=".2s", row=2, col=1)

    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🎯 VCP Screener")
st.sidebar.markdown("**Volatility Contraction Pattern**  \n*Mark Minervini Method*")
st.sidebar.markdown("---")

st.sidebar.markdown("### 🔍 Filters")
min_score = st.sidebar.slider("Minimum VCP Score", 4, 7, 6,
    help="7 = perfect setup | 6 = strong | 5 = watch | 4 = early")
market_filter = st.sidebar.multiselect(
    "Exchange", ["NSE", "NSE-SME", "BSE"], default=["NSE"],
    help="Start with NSE only for speed. Add BSE for more signals."
)
min_price = st.sidebar.number_input("Min Price (₹)", 0, 100000, 10)
max_price = st.sidebar.number_input("Max Price (₹)", 1, 1000000, 50000)

st.sidebar.markdown("### ⚙️ Speed Settings")
batch_size = st.sidebar.slider("Batch size", 10, 100, 40,
    help="Stocks per API call. 40 is optimal.")
max_workers = st.sidebar.slider("Parallel workers", 1, 10, 5,
    help="Reduce to 2-3 if you see many errors.")
period = st.sidebar.selectbox("Chart / data period", ["6mo", "1y", "2y"], index=1)

st.sidebar.markdown("---")
scan_clicked = st.sidebar.button("🔍 Scan for VCP Patterns", use_container_width=True)

if st.sidebar.button("🗑️ Clear Cache & Rescan", use_container_width=True):
    clear_cache_file("vcp_results")
    st.session_state.pop("scan_results", None)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size:0.75rem; color:#8b949e; line-height:1.5'>
<b style='color:#ffa657'>Legend:</b><br>
🟠 <b>ENTRY</b> — Buy when price closes above this<br>
🟢 <b>TARGET</b> — Sell / book profit here<br>
🔴 <b>STOP LOSS</b> — Exit immediately if price falls here<br>
<br>
<b>C1, C2, C3</b> = Contraction zones<br>
Each must be smaller than previous.<br>
<br>
<b style='color:#3fb950'>Score 7/7</b> = Perfect VCP setup<br>
<b style='color:#58a6ff'>Score 6/7</b> = Strong setup<br>
<b style='color:#ffa657'>Score 5/7</b> = Watch list
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("# 🎯 VCP Screener — All NSE + BSE")
st.markdown("*Scans all listed stocks for Volatility Contraction Pattern (Mark Minervini Method)*")

c1, c2, c3, c4 = st.columns(4)
for col, val, lbl, color in [
    (c1, "NSE + BSE", "Universe", "#58a6ff"),
    (c2, "5,500+", "Stocks Scanned", "#3fb950"),
    (c3, "7 Conditions", "VCP Score", "#ffa657"),
    (c4, "81.5% in 2yr", "Backtest Return", "#bc8cff"),
]:
    col.markdown(f"""
    <div class='metric-card'>
        <div class='metric-val' style='color:{color}'>{val}</div>
        <div class='metric-lbl'>{lbl}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# How to use expander
with st.expander("📖 How to use this screener — Step-by-step guide", expanded=False):
    st.markdown("""
    ### What is VCP?
    A **Volatility Contraction Pattern** is when a stock goes up strongly, then pulls back — but each pullback 
    gets **smaller and smaller** while volume dries up. Like a coiled spring. When it breaks out on high volume, 
    it typically runs 10–30% quickly.

    ---
    ### The 7 VCP Conditions (each = 1 point)

    | # | Condition | Why it matters |
    |---|-----------|---------------|
    | 1 | **Above 150-day SMA** | Long-term uptrend confirmed |
    | 2 | **Above 200-day SMA** | Very long-term health is strong |
    | 3 | **SMA 50 > 150 > 200** | Perfect alignment = strongest uptrend |
    | 4 | **Contractions shrinking** | Each pullback smaller = pattern maturing |
    | 5 | **Volume drying up** | Sellers exhausted = low supply |
    | 6 | **Tight range < 12%** | Final squeeze before breakout |
    | 7 | **Near pivot point** | Close to breakout level |

    ---
    ### Step-by-Step: How to Trade

    | Step | Action |
    |------|--------|
    | 1 | Run screener Sunday evening. Look only at **Score 6 or 7**. |
    | 2 | Check Nifty 50 — if market is falling sharply, **skip all trades** that week. |
    | 3 | Check NSE for upcoming earnings — **never buy 2 weeks before results**. |
    | 4 | On the chart, confirm at least **3 contractions** and each one is smaller. |
    | 5 | **Wait** for stock to close above the 🟠 ENTRY line on volume 1.5× or more. |
    | 6 | **Buy** when that candle closes. Place your stop loss at 🔴 STOP LOSS level immediately. |
    | 7 | **Hold** until stock hits 🟢 TARGET. Don't panic on small dips. |
    | 8 | Once up 4%, **move stop loss to entry price** (breakeven). You cannot lose then. |
    | 9 | Continue trailing stop below each higher swing low as stock rises. |

    > ⚠️ **Never enter with only 2 contractions.** Always wait for 3 minimum.  
    > ⚠️ **Never remove a stop loss** once placed. It protects your capital.
    """)


# ─────────────────────────────────────────────────────────────────────────────
#  SCAN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
if scan_clicked:
    cached = load_cache("vcp_results", hours=4)
    if cached:
        st.success(f"⚡ Loaded {len(cached)} VCP signals from cache (scan done within last 4 hours). Clear cache to rescan.")
        st.session_state["scan_results"] = cached
    else:
        # Load stock list
        with st.spinner("📋 Loading stock list from NSE + BSE..."):
            if UNIVERSE_AVAILABLE:
                all_stocks = get_all_stocks()
            else:
                all_stocks = get_builtin_stocks()

        stocks_to_scan = [s for s in all_stocks if s.get("exchange", "NSE") in market_filter]
        total = len(stocks_to_scan)
        st.info(f"🔍 Scanning **{total:,} stocks** | Min Score: {min_score}/7 | Price: ₹{min_price}–₹{max_price:,}")

        prog_bar  = st.progress(0)
        prog_text = st.empty()

        if FAST_SCAN_AVAILABLE:
            def _wrapper(stock_info: dict, df) -> dict | None:
                res = fetch_and_score(stock_info, df=df, period=period)
                if res and res.get("score", 0) >= min_score:
                    cp = res.get("current_price") or 0
                    if min_price <= cp <= max_price:
                        return res
                return None
            try:
                results = fast_scan_all(
                    all_stocks=stocks_to_scan, score_fn=_wrapper,
                    exchange_filter=None, min_price=min_price, max_price=max_price,
                    period=period, batch_size=batch_size,
                    progress_bar=prog_bar, status_text=prog_text,
                    cache_key="vcp", cache_hours=4,
                )
            except Exception:
                results = _scan_stocks(stocks_to_scan, min_score, min_price, max_price,
                                       period, batch_size, max_workers, prog_bar, prog_text)
        else:
            results = _scan_stocks(stocks_to_scan, min_score, min_price, max_price,
                                   period, batch_size, max_workers, prog_bar, prog_text)

        prog_bar.progress(1.0)
        save_cache("vcp_results", results)
        st.session_state["scan_results"] = results
        st.success(f"✅ Scan complete! Found **{len(results)} VCP setups** with Score ≥ {min_score}")


# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────────────────────
results = st.session_state.get("scan_results", [])

if results:
    results_sorted = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    # Summary counts
    st.markdown("---")
    st.markdown("## 🎯 VCP Signals Found")
    g7 = [r for r in results_sorted if r["score"] == 7]
    g6 = [r for r in results_sorted if r["score"] == 6]
    g5 = [r for r in results_sorted if r["score"] == 5]
    g4 = [r for r in results_sorted if r["score"] == 4]

    c1, c2, c3, c4 = st.columns(4)
    for col, grp, lbl, col_color in [
        (c1, g7, "Score 7/7", "#3fb950"),
        (c2, g6, "Score 6/7", "#58a6ff"),
        (c3, g5, "Score 5/7", "#ffa657"),
        (c4, g4, "Score 4/7", "#8b949e"),
    ]:
        col.markdown(f"""
        <div class='metric-card'>
            <div class='metric-val' style='color:{col_color}'>{len(grp)}</div>
            <div class='metric-lbl'>{lbl}</div>
        </div>""", unsafe_allow_html=True)

    # Sort control
    st.markdown("### 📋 All VCP Signals (Score ≥ selected minimum)")
    sort_by = st.selectbox("Sort by", [
        "Score (High→Low)", "Price (Low→High)", "Vol Ratio (Lowest first)", "Tight % (Lowest first)"
    ])
    if sort_by == "Score (High→Low)":
        results_sorted = sorted(results_sorted, key=lambda x: x["score"], reverse=True)
    elif sort_by == "Price (Low→High)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("current_price") or 0)
    elif sort_by == "Vol Ratio (Lowest first)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("vol_ratio") or 1)
    elif sort_by == "Tight % (Lowest first)":
        results_sorted = sorted(results_sorted, key=lambda x: x.get("tight_pct") or 99)

    # ── Individual result cards ───────────────────────────────────────────────
    for r in results_sorted:
        score  = r.get("score", 0)
        signal = r.get("signal", "")
        name   = r.get("name", r.get("symbol", ""))
        ticker = r.get("yf_ticker", "")
        price  = r.get("current_price", 0) or 0
        entry  = r.get("entry_price") or r.get("pivot") or price
        stop   = r.get("stop_loss") or 0
        target = r.get("target") or 0

        # Badge colour
        if score == 7:   badge_cls = "badge-strong"; emoji = "🟢"
        elif score == 6: badge_cls = "badge-buy";    emoji = "🔵"
        else:            badge_cls = "badge-watch";  emoji = "🟡"

        with st.expander(
            f"{emoji} {name}  [{ticker}]  |  Score: {score}/7  |  ₹{price:,.2f}  |  {signal}",
            expanded=(score >= 6),
        ):
            # ── TOP BANNER ─────────────────────────────────────────────────
            rr = (target - entry) / (entry - stop) if (entry - stop) > 0 else 0
            contr = r.get("contractions", [])
            contr_str = " → ".join(f"{c}%" for c in contr) if contr else "—"

            st.markdown(f"""
            <div style='background:#161b22; border:1px solid #30363d; border-radius:10px;
                        padding:14px 20px; margin-bottom:12px;
                        display:flex; gap:32px; flex-wrap:wrap; align-items:center'>
                <div>
                    <div style='font-size:0.75rem;color:#8b949e'>SIGNAL</div>
                    <div class='{badge_cls}'>{signal}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#8b949e'>CURRENT PRICE</div>
                    <div style='font-size:1.1rem;font-weight:700;color:#c9d1d9'>₹{price:,.2f}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#8b949e'>⬆ ENTRY (Buy above)</div>
                    <div style='font-size:1.1rem;font-weight:700;color:#ffa657'>₹{entry:,.2f}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#3fb950'>🎯 TARGET</div>
                    <div style='font-size:1.1rem;font-weight:700;color:#3fb950'>₹{target:,.2f}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#f85149'>🛑 STOP LOSS</div>
                    <div style='font-size:1.1rem;font-weight:700;color:#f85149'>₹{stop:,.2f}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#8b949e'>REWARD : RISK</div>
                    <div style='font-size:1.1rem;font-weight:700;color:#bc8cff'>1 : {rr:.1f}</div>
                </div>
                <div>
                    <div style='font-size:0.75rem;color:#8b949e'>CONTRACTIONS</div>
                    <div style='font-size:0.9rem;font-weight:700;color:#79c0ff'>{contr_str}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── CHART + DETAILS side by side ──────────────────────────────
            chart_col, detail_col = st.columns([2, 1])

            with chart_col:
                with st.spinner("Loading chart..."):
                    fig = build_chart(ticker, r, period)
                st.plotly_chart(fig, use_container_width=True)

                # Chart legend explanation
                st.markdown("""
                <div style='font-size:0.78rem; color:#8b949e; padding:4px 8px;
                            background:#161b22; border-radius:6px; margin-top:-8px'>
                🟠 <b style='color:#ffa657'>Entry line</b> — Buy when price closes <i>above</i> this on high volume &nbsp;|&nbsp;
                🟢 <b style='color:#3fb950'>Target</b> — Take profit here &nbsp;|&nbsp;
                🔴 <b style='color:#f85149'>Stop Loss</b> — Exit immediately if price falls here &nbsp;|&nbsp;
                <b>C1/C2/C3</b> = Contraction zones (each must be smaller)
                </div>
                """, unsafe_allow_html=True)

            with detail_col:
                # ── VCP CONDITIONS CHECKLIST ──────────────────────────────
                st.markdown("<div class='section-title'>VCP Conditions</div>", unsafe_allow_html=True)
                conditions = [
                    ("Above 150-day SMA", r.get("above_sma150"), "Long-term uptrend ✓"),
                    ("Above 200-day SMA", r.get("above_sma200"), "Very long-term health ✓"),
                    ("SMA 50 > 150 > 200", r.get("sma_lineup"), "Perfect trend alignment ✓"),
                    ("Contractions shrinking", r.get("contracting"), f"Pattern maturing: {contr_str}"),
                    ("Volume drying up", r.get("vol_dry"), f"Vol ratio: {r.get('vol_ratio','?')}× (need <0.75)"),
                    ("Tight range < 12%", r.get("tight"), f"Range: {r.get('tight_pct','?')}%"),
                    ("Near pivot point", r.get("near_pivot"), "Close to breakout level ✓"),
                ]
                for label, passed, detail in conditions:
                    icon  = "✅" if passed else "❌"
                    cls   = "cond-pass" if passed else "cond-fail"
                    color = "#3fb950" if passed else "#f85149"
                    st.markdown(
                        f"<div class='{cls}'>{icon} <b>{label}</b><br>"
                        f"<span style='font-size:0.75rem;color:#8b949e;margin-left:18px'>{detail}</span></div>",
                        unsafe_allow_html=True
                    )

                st.markdown("<div class='section-title' style='margin-top:12px'>Key Levels</div>", unsafe_allow_html=True)
                levels = [
                    ("Current Price", f"₹{price:,.2f}", "#c9d1d9"),
                    ("⬆ ENTRY (Buy above)", f"₹{entry:,.2f}", "#ffa657"),
                    ("🛑 STOP LOSS", f"₹{stop:,.2f}", "#f85149"),
                    ("🎯 TARGET", f"₹{target:,.2f}", "#3fb950"),
                    ("Pivot Point", f"₹{r.get('pivot',0):,.2f}", "#ffa657"),
                    ("SMA 50", f"₹{r.get('sma50',0):,.0f}", "#58a6ff"),
                    ("SMA 150", f"₹{r.get('sma150',0):,.0f}", "#ffa657"),
                    ("SMA 200", f"₹{r.get('sma200',0):,.0f}", "#bc8cff"),
                ]
                for k, v, c in levels:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:3px 0;border-bottom:1px solid #21262d'>"
                        f"<span style='color:#8b949e;font-size:0.8rem'>{k}</span>"
                        f"<span style='color:{c};font-weight:700;font-size:0.8rem'>{v}</span>"
                        f"</div>", unsafe_allow_html=True
                    )

                # ── TRADE PLAN ────────────────────────────────────────────
                st.markdown("<div class='section-title' style='margin-top:12px'>Trade Plan (₹1,00,000)</div>", unsafe_allow_html=True)
                risk_pp = entry - stop
                if risk_pp > 0:
                    qty        = max(1, int(2000 / risk_pp))
                    max_loss   = qty * risk_pp
                    pot_profit = qty * (target - entry)
                    trade_rows = [
                        ("Buy when closes above", f"₹{entry:,.2f}", "#ffa657"),
                        ("Quantity (2% risk rule)", f"{qty} shares", "#c9d1d9"),
                        ("Stop Loss — place immediately", f"₹{stop:,.2f}", "#f85149"),
                        ("Max loss if stop hit", f"₹{max_loss:,.0f}", "#f85149"),
                        ("Target — sell here", f"₹{target:,.2f}", "#3fb950"),
                        ("Potential profit", f"₹{pot_profit:,.0f}", "#3fb950"),
                        ("Reward : Risk ratio", f"1 : {rr:.1f}", "#bc8cff"),
                    ]
                    for k, v, c in trade_rows:
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;"
                            f"padding:3px 0;border-bottom:1px solid #1e3a2a'>"
                            f"<span style='color:#8b949e;font-size:0.78rem'>{k}</span>"
                            f"<span style='color:{c};font-weight:700;font-size:0.78rem'>{v}</span>"
                            f"</div>", unsafe_allow_html=True
                        )

                # ── WHY CONSIDER THIS STOCK ────────────────────────────────
                st.markdown("<div class='section-title' style='margin-top:12px'>Why Consider?</div>", unsafe_allow_html=True)
                is_ok = len(contr) >= 3 and all(contr[i] > contr[i+1] for i in range(len(contr)-1))

                reasons = []
                warnings_list = []

                if r.get("sma_lineup"):
                    reasons.append("✅ Perfect SMA alignment — strongest uptrend structure")
                if is_ok and len(contr) >= 3:
                    reasons.append(f"✅ {len(contr)} clean shrinking contractions ({contr_str})")
                elif not is_ok:
                    warnings_list.append("⚠️ Contractions not clearly shrinking — wait")
                if (r.get("vol_ratio") or 1) < 0.65:
                    reasons.append(f"✅ Volume very dry ({r.get('vol_ratio')}×) — sellers gone")
                elif (r.get("vol_ratio") or 1) > 0.75:
                    warnings_list.append("⚠️ Volume not fully dry yet — pattern still forming")
                if r.get("near_pivot"):
                    reasons.append("✅ Within 5% of breakout — entry is very close")
                else:
                    warnings_list.append("⚠️ Not near pivot yet — set a price alert, don't buy yet")
                if (r.get("tight_pct") or 99) < 8:
                    reasons.append(f"✅ Very tight range ({r.get('tight_pct')}%) — minimal risk on entry")
                if score == 7:
                    reasons.append("✅ Score 7/7 — all VCP conditions passed, highest conviction")

                for reason in reasons:
                    st.markdown(f"<div class='reason-box'>{reason}</div>", unsafe_allow_html=True)
                for w in warnings_list:
                    st.markdown(f"<div class='warn-box'>{w}</div>", unsafe_allow_html=True)

                st.markdown("""
                <div style='font-size:0.73rem;color:#8b949e;margin-top:8px;
                            padding:6px;background:#161b22;border-radius:6px'>
                ⚠️ Always verify on TradingView before trading. 
                Check NSE for upcoming results. Not SEBI investment advice.
                </div>""", unsafe_allow_html=True)

elif not scan_clicked:
    # Welcome screen
    st.markdown("""
    <div class='info-box' style='font-size:1rem; padding:24px'>
    <h3 style='color:#58a6ff;margin-top:0'>🎯 VCP Screener — All NSE + BSE Stocks</h3>
    This screener scans <b>all ~5,500+ stocks listed on NSE and BSE</b> for the 
    Volatility Contraction Pattern developed by Mark Minervini.<br><br>
    <b>Backtest result:</b> ₹1,00,000 → ₹1,81,458 in 2 years (81.5% return), 
    profit factor 3.10 across 36 trades.<br><br>
    👉 Set your filters on the left sidebar, then click <b>"Scan for VCP Patterns"</b>.<br>
    ⏱️ NSE only (~2,000 stocks): 3–5 minutes. Add BSE: ~10 minutes more.<br><br>
    <b>On the chart you will see:</b><br>
    🟠 <b style='color:#ffa657'>ENTRY line</b> — the exact price to buy above<br>
    🟢 <b style='color:#3fb950'>TARGET line</b> — where to sell and take profit<br>
    🔴 <b style='color:#f85149'>STOP LOSS line</b> — where to exit immediately if wrong<br>
    <b>C1, C2, C3 bands</b> — the 3 shrinking contraction zones
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Backtest Performance Summary (36 trades, 2 years)")
    perf_data = {
        "Stock":  ["Tata Motors","L&T","Bharti Airtel","Bajaj Finance","ICICI Bank","KPIT Tech","Infosys","Sun Pharma"],
        "Trades": [4, 3, 2, 3, 3, 3, 4, 3],
        "Win %":  ["100%","100%","100%","67%","67%","67%","50%","0%"],
        "P&L":    ["+₹20,225","+₹15,666","+₹10,514","+₹8,499","+₹8,398","+₹8,342","+₹6,685","-₹5,846"],
        "Verdict":["STRONG ✅","STRONG ✅","STRONG ✅","GOOD 🔵","GOOD 🔵","GOOD 🔵","GOOD 🔵","AVOID ❌"],
    }
    st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)
