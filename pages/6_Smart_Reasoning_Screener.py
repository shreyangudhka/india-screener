import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="Smart Screener with Reasoning", page_icon="🧠", layout="wide")

st.markdown("""
<style>
.reason-box { background:#f0f7ff; border-left:4px solid #1a73e8; border-radius:6px; padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.7; }
.warn-box   { background:#fff8e1; border-left:4px solid #f9a825; border-radius:6px; padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.7; }
.danger-box { background:#ffeaea; border-left:4px solid #e53935; border-radius:6px; padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.7; }
.good-box   { background:#e8f5e9; border-left:4px solid #2e7d32; border-radius:6px; padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.7; }
.verdict-buy  { background:#e8f5e9; border:2px solid #2e7d32; border-radius:10px; padding:14px; text-align:center; font-size:18px; font-weight:700; color:#1b5e20; }
.verdict-watch{ background:#fff8e1; border:2px solid #f9a825; border-radius:10px; padding:14px; text-align:center; font-size:18px; font-weight:700; color:#e65100; }
.verdict-skip { background:#ffeaea; border:2px solid #e53935; border-radius:10px; padding:14px; text-align:center; font-size:18px; font-weight:700; color:#b71c1c; }
.check  { color:#2e7d32; font-weight:700; }
.cross  { color:#e53935; font-weight:700; }
.warn   { color:#f57c00; font-weight:700; }
.signal-bar { height:12px; border-radius:6px; margin:4px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 Smart Screener — Shows You WHY to Buy or Skip")
st.caption("Every stock gets a full plain-English explanation. No more guessing.")

STOCKS = {
    "Banking":  ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","SBIN.NS","BAJFINANCE.NS","INDUSINDBK.NS"],
    "IT":       ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
    "Auto":     ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS"],
    "Pharma":   ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","AUROPHARMA.NS"],
    "Energy":   ["RELIANCE.NS","ONGC.NS","BPCL.NS","ADANIPORTS.NS","POWERGRID.NS","NTPC.NS"],
    "FMCG":     ["HINDUNILVR.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS"],
    "Infra":    ["LT.NS","ULTRACEMCO.NS","JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS"],
    "Telecom":  ["BHARTIARTL.NS"],
    "Consumer": ["ASIANPAINT.NS","TITAN.NS","DMART.NS"],
}

ALL_STOCKS = [(s, sec) for sec, lst in STOCKS.items() for s in lst]

with st.sidebar:
    st.header("⚙️ Settings")
    capital    = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct   = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    min_score  = st.slider("Minimum score to show", 0, 10, 4)
    show_only  = st.selectbox("Show signals", ["All", "BUY only", "BUY + WATCH"])
    sel_sectors= st.multiselect("Sectors", list(STOCKS.keys()), default=list(STOCKS.keys()))
    st.divider()
    st.markdown("**Scoring system (out of 10):**")
    st.markdown("- Above EMA50 → 2 pts")
    st.markdown("- Above SMA200 → 2 pts")
    st.markdown("- RSI 38–62 → 2 pts")
    st.markdown("- Volume above avg → 2 pts")
    st.markdown("- Pullback 3–18% → 1 pt")
    st.markdown("- Weekly uptrend → 1 pt")
    st.divider()
    st.caption("Not SEBI-registered advice. Verify on TradingView before trading.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 55: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except: return None

def analyse_stock(df, ticker, sector):
    df = df.copy()
    df['EMA20']  = df['Close'].ewm(span=20).mean()
    df['EMA50']  = df['Close'].ewm(span=50).mean()
    df['SMA200'] = df['Close'].rolling(200).mean() if len(df) >= 200 else np.nan
    df['VolMA20']= df['Volume'].rolling(20).mean()
    d = df['Close'].diff()
    g = d.clip(lower=0).rolling(14).mean()
    l = (-d.clip(upper=0)).rolling(14).mean()
    df['RSI']    = 100 - (100/(1 + g/l.replace(0,1e-9)))
    tr = pd.concat([df['High']-df['Low'],
                    (df['High']-df['Close'].shift()).abs(),
                    (df['Low'] -df['Close'].shift()).abs()], axis=1).max(axis=1)
    df['ATR']    = tr.rolling(14).mean()

    r     = df.iloc[-1]
    r_prev= df.iloc[-2]
    price = float(r['Close'])
    ema20 = float(r['EMA20'])  if not pd.isna(r['EMA20'])  else price
    ema50 = float(r['EMA50'])  if not pd.isna(r['EMA50'])  else price
    sma200= float(r['SMA200']) if not pd.isna(r['SMA200']) else price
    rsi   = float(r['RSI'])    if not pd.isna(r['RSI'])    else 50
    vol   = float(r['Volume'])
    volma = float(r['VolMA20'])if not pd.isna(r['VolMA20'])else vol
    atr   = float(r['ATR'])    if not pd.isna(r['ATR'])    else price*0.02

    # ── Individual checks ──────────────────────────────────────────
    above_ema50  = price > ema50
    above_sma200 = price > sma200 if not pd.isna(r['SMA200']) else above_ema50
    rsi_ok       = 38 <= rsi <= 62
    vol_ratio    = vol / volma if volma > 0 else 1
    vol_ok       = vol_ratio >= 1.2
    recent_high  = float(df['Close'].rolling(20).max().iloc[-1])
    pullback_pct = (recent_high - price) / recent_high * 100 if recent_high > 0 else 0
    pullback_ok  = 3 <= pullback_pct <= 18
    weekly = df['Close'].resample('W').last().dropna()
    weekly_up = (float(weekly.iloc[-1]) > float(weekly.iloc[-5])) if len(weekly) >= 5 else above_ema50

    # Earnings warning check
    earnings_warning = False  # flag for near-results caution

    # Setup detection
    range_width = (df['Close'].iloc[-20:].max() - df['Close'].iloc[-20:].min()) / df['Close'].iloc[-20:].min() * 100
    hi52 = float(df['Close'].rolling(min(252,len(df))).max().iloc[-1])
    near52 = (price / hi52) > 0.97

    if near52 and vol_ok:
        setup = "52W High Breakout"
    elif range_width < 8 and vol_ok:
        setup = "Range Breakout"
    elif pullback_ok and above_ema50:
        setup = "Pullback in Uptrend"
    elif abs(price - ema20)/price*100 < 1.5:
        setup = "EMA20 Bounce"
    else:
        setup = "Developing"

    # Scoring
    score = 0
    if above_ema50:  score += 2
    if above_sma200: score += 2
    if rsi_ok:       score += 2
    if vol_ok:       score += 2
    if pullback_ok:  score += 1
    if weekly_up:    score += 1

    # Signal
    signal = "BUY" if score >= 8 and weekly_up else "WATCH" if score >= 5 else "SKIP"

    # Trade levels
    stop   = round(price - 1.5*atr, 2)
    target = round(price + 3.0*atr, 2)
    qty    = max(1, int((capital*risk_pct/100) / max(price-stop, 0.01)))
    rr     = round((target-price)/(price-stop), 1) if price > stop else 0
    pct_from_hi = round((price/hi52 - 1)*100, 1)

    # ── Plain English reasoning ─────────────────────────────────────
    reasons_for  = []
    reasons_against = []
    warnings     = []

    # Positive reasons
    if above_sma200:
        gap = round((price/sma200 - 1)*100, 1)
        reasons_for.append(f"Stock is in a long-term uptrend — trading {gap}% above its 200-day average. This means the big picture is healthy.")
    if above_ema50:
        reasons_for.append(f"Price is above the 50-day EMA (₹{ema50:.0f}), confirming a medium-term uptrend. The stock is in good shape on a weekly basis.")
    if pullback_ok:
        reasons_for.append(f"The stock has pulled back {pullback_pct:.1f}% from its recent high of ₹{recent_high:.0f}. This is a healthy dip — not a crash — giving you a lower-risk entry point.")
    if rsi_ok:
        reasons_for.append(f"RSI is at {rsi:.0f} — in the sweet spot of 38–62. Not overbought (no panic buying) and not oversold (no panic selling). Healthy momentum.")
    if vol_ok:
        reasons_for.append(f"Today's trading volume is {vol_ratio:.1f}× the normal average. Higher volume means more conviction behind the price move.")
    if weekly_up:
        reasons_for.append("The weekly chart trend is pointing upward — you are trading with the wind behind you, not against it.")
    if near52:
        reasons_for.append(f"Price is within 3% of its 52-week high (₹{hi52:.0f}). Stocks near all-time or yearly highs often continue higher — strength begets strength.")
    if setup == "Pullback in Uptrend":
        reasons_for.append("Classic pullback setup: uptrend intact, temporary dip, momentum starting to recover. This is one of the most reliable swing trading patterns.")
    if setup == "Range Breakout":
        reasons_for.append("Stock has been consolidating in a tight range and is now breaking out with volume. Like a coiled spring releasing — a breakout after consolidation is powerful.")

    # Negative reasons
    if not above_sma200:
        reasons_against.append(f"⚠️ Price (₹{price:.0f}) is BELOW the 200-day SMA (₹{sma200:.0f}). This means the stock is in a long-term downtrend. High risk.")
    if not above_ema50:
        reasons_against.append(f"Price is below the 50-day EMA — medium term trend is down. Not ideal for a buy trade.")
    if rsi > 70:
        reasons_against.append(f"RSI is {rsi:.0f} — overbought territory. The stock has run up too fast. Better to wait for a pullback before buying.")
    if rsi < 35:
        reasons_against.append(f"RSI is {rsi:.0f} — very oversold. Could mean the stock is under heavy selling pressure. Wait for stabilisation first.")
    if not vol_ok:
        reasons_against.append(f"Volume is only {vol_ratio:.1f}× normal — below our 1.2× threshold. Low volume moves are less reliable and can reverse quickly.")
    if not weekly_up:
        reasons_against.append("The weekly trend is flat or down — you would be fighting the bigger trend. Wait for the weekly to turn upward.")
    if pullback_pct > 20:
        reasons_against.append(f"The stock has fallen {pullback_pct:.1f}% from its recent high — this is more than a normal pullback and could indicate real selling pressure.")
    if pct_from_hi < -30:
        reasons_against.append(f"Stock is {abs(pct_from_hi):.0f}% below its 52-week high. This signals fundamental weakness, not just a dip.")

    # Warnings
    if rr < 2:
        warnings.append(f"R:R ratio is only {rr} — below our 2:1 minimum. The risk is not justified by the potential reward at current price.")
    if pullback_pct < 3 and not near52:
        warnings.append("The stock hasn't pulled back enough from its recent high. Waiting for a 5–8% dip would give a better entry.")

    # Overall plain-English verdict
    if signal == "BUY":
        verdict_text = f"✅ BUY SIGNAL — Score {score}/10"
        verdict_class = "verdict-buy"
        summary = f"This stock is showing {len(reasons_for)} strong positive signals and only {len(reasons_against)} concerns. The setup is a '{setup}' — one of the better swing trading opportunities right now. Entry around ₹{price:.0f}, stop at ₹{stop:.0f}, target ₹{target:.0f}."
    elif signal == "WATCH":
        verdict_text = f"🟡 WATCH — Score {score}/10"
        verdict_class = "verdict-watch"
        summary = f"Some positive signals but not all criteria are met yet. Keep this on your radar. {len(reasons_against)} things need to improve before entering. Do not buy yet."
    else:
        verdict_text = f"⛔ SKIP — Score {score}/10"
        verdict_class = "verdict-skip"
        summary = f"Too many concerns right now — {len(reasons_against)} red flags. The risk is higher than the reward. There are better opportunities in the market."

    return {
        "name":       ticker.replace(".NS",""),
        "sector":     sector,
        "price":      round(price, 2),
        "score":      score,
        "signal":     signal,
        "setup":      setup,
        "rsi":        round(rsi, 1),
        "vol_ratio":  round(vol_ratio, 2),
        "ema50":      round(ema50, 2),
        "sma200":     round(sma200, 2),
        "pullback":   round(pullback_pct, 1),
        "hi52":       round(hi52, 2),
        "pct_hi52":   pct_from_hi,
        "stop":       stop,
        "target":     target,
        "qty":        qty,
        "rr":         rr,
        "above_ema50":  above_ema50,
        "above_sma200": above_sma200,
        "rsi_ok":       rsi_ok,
        "vol_ok":       vol_ok,
        "pullback_ok":  pullback_ok,
        "weekly_up":    weekly_up,
        "reasons_for":  reasons_for,
        "reasons_against": reasons_against,
        "warnings":     warnings,
        "verdict_text": verdict_text,
        "verdict_class":verdict_class,
        "summary":      summary,
    }

def render_stock_card(r):
    icon = {"BUY":"🟢","WATCH":"🟡","SKIP":"🔴"}.get(r["signal"],"⚪")
    with st.expander(f"{icon} **{r['name']}** ({r['sector']}) — Score {r['score']}/10 — {r['setup']} — ₹{r['price']}", expanded=(r["signal"]=="BUY")):

        # Verdict banner
        st.markdown(f'<div class="{r["verdict_class"]}">{r["verdict_text"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:14px;margin:8px 0 14px;color:#333;">{r["summary"]}</div>', unsafe_allow_html=True)

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Price",   f"₹{r['price']}")
        col2.metric("Score",   f"{r['score']}/10")
        col3.metric("RSI",     r['rsi'])
        col4.metric("Vol ratio",f"{r['vol_ratio']}×")
        col5.metric("R:R",     f"{r['rr']} : 1")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### ✅ Reasons to buy")
            if r["reasons_for"]:
                for reason in r["reasons_for"]:
                    st.markdown(f'<div class="good-box">✔ {reason}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="danger-box">No strong buy reasons found.</div>', unsafe_allow_html=True)

        with c2:
            st.markdown("##### ❌ Reasons to be careful")
            if r["reasons_against"]:
                for reason in r["reasons_against"]:
                    st.markdown(f'<div class="danger-box">✘ {reason}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="good-box">No major concerns found.</div>', unsafe_allow_html=True)

        if r["warnings"]:
            st.markdown("##### ⚠️ Cautions")
            for w in r["warnings"]:
                st.markdown(f'<div class="warn-box">⚠ {w}</div>', unsafe_allow_html=True)

        st.divider()
        st.markdown("##### 📋 Technical checklist")
        checks = [
            ("Price above 50-day EMA",    r["above_ema50"],  f"Price ₹{r['price']} vs EMA50 ₹{r['ema50']}"),
            ("Price above 200-day SMA",   r["above_sma200"], f"Price ₹{r['price']} vs SMA200 ₹{r['sma200']}"),
            ("RSI in healthy range 38–62", r["rsi_ok"],      f"Current RSI: {r['rsi']}"),
            ("Volume above average",       r["vol_ok"],      f"Volume ratio: {r['vol_ratio']}× (need 1.2×)"),
            ("Pullback 3–18% from high",   r["pullback_ok"], f"Pulled back {r['pullback']}% from ₹{r['hi52']}"),
            ("Weekly trend is up",         r["weekly_up"],   "Based on last 10 weeks"),
        ]
        for label, passed, detail in checks:
            icon2 = "✅" if passed else "❌"
            color = "#2e7d32" if passed else "#c62828"
            st.markdown(f'<div style="font-size:13px;padding:5px 0;border-bottom:1px solid #eee;">'
                        f'{icon2} <b style="color:{color}">{label}</b> — <span style="color:#555">{detail}</span></div>',
                        unsafe_allow_html=True)

        if r["signal"] == "BUY":
            st.divider()
            st.markdown("##### 💰 Trade plan")
            t1,t2,t3,t4 = st.columns(4)
            t1.metric("Entry around",  f"₹{r['price']}")
            t2.metric("Stop loss at",  f"₹{r['stop']}", delta=f"-{round((r['price']-r['stop'])/r['price']*100,1)}%", delta_color="inverse")
            t3.metric("Target",        f"₹{r['target']}", delta=f"+{round((r['target']-r['price'])/r['price']*100,1)}%")
            t4.metric("Qty to buy",    f"{r['qty']} shares")
            max_loss = round((r['price']-r['stop'])*r['qty'], 0)
            pot_gain = round((r['target']-r['price'])*r['qty'], 0)
            st.info(f"💡 **Position size:** ₹{r['qty']*r['price']:,.0f} deployed · **Max you can lose:** ₹{max_loss:,.0f} · **Potential profit:** ₹{pot_gain:,.0f}")
            st.caption("Always verify this setup on TradingView before placing any real order.")

# ─── Main app ───────────────────────────────────────────────────────────────

tickers = [(s, sec) for sec, lst in STOCKS.items() for s in lst if sec in sel_sectors]

if st.button("🔍 Scan & explain all stocks", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Analysing stocks…")
    for i, (ticker, sector) in enumerate(tickers):
        bar.progress((i+1)/len(tickers), f"Analysing {ticker.replace('.NS','')}…")
        df = fetch_data(ticker)
        if df is not None:
            results.append(analyse_stock(df, ticker, sector))
    bar.empty()
    results.sort(key=lambda x: x["score"], reverse=True)
    st.session_state["smart_results"] = results

if "smart_results" in st.session_state:
    results = st.session_state["smart_results"]

    # Apply filters
    filtered = [r for r in results if r["score"] >= min_score]
    if show_only == "BUY only":
        filtered = [r for r in filtered if r["signal"] == "BUY"]
    elif show_only == "BUY + WATCH":
        filtered = [r for r in filtered if r["signal"] in ("BUY","WATCH")]

    buys   = [r for r in results if r["signal"] == "BUY"]
    watchs = [r for r in results if r["signal"] == "WATCH"]
    skips  = [r for r in results if r["signal"] == "SKIP"]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Scanned",       len(results))
    c2.metric("Buy signals",   len(buys),   delta="Act on these")
    c3.metric("Watch signals", len(watchs), delta="Monitor these")
    c4.metric("Skip",          len(skips))

    st.divider()

    if not filtered:
        st.info("No stocks match your current filters. Try lowering the minimum score.")
    else:
        st.caption(f"Showing {len(filtered)} stocks — click any row to see full analysis and reasoning")
        for r in filtered:
            render_stock_card(r)
else:
    st.info("👆 Click the button above to scan stocks and see why you should or should not buy each one.")
    st.markdown("""
    **What makes this screener different:**
    - Every stock gets a full plain-English explanation
    - You see exactly WHY a stock scored well or poorly
    - Specific reasons for AND against buying
    - Complete trade plan with exact entry, stop, and target
    - Checklist of every technical condition checked
    """)
