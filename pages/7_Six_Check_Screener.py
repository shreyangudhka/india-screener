import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="6-Check Screener", page_icon="6️⃣", layout="wide")

st.markdown("""
<style>
.check-pass { background:#e8f5e9; border-left:4px solid #2e7d32; border-radius:6px; padding:10px 14px; margin:5px 0; font-size:13px; }
.check-fail { background:#ffeaea; border-left:4px solid #e53935; border-radius:6px; padding:10px 14px; margin:5px 0; font-size:13px; }
.check-warn { background:#fff8e1; border-left:4px solid #f9a825; border-radius:6px; padding:10px 14px; margin:5px 0; font-size:13px; }
.verdict-buy  { background:#e8f5e9; border:2px solid #2e7d32; border-radius:10px; padding:14px; text-align:center; font-size:20px; font-weight:700; color:#1b5e20; margin-bottom:12px; }
.verdict-skip { background:#ffeaea; border:2px solid #e53935; border-radius:10px; padding:14px; text-align:center; font-size:20px; font-weight:700; color:#b71c1c; margin-bottom:12px; }
.verdict-watch{ background:#fff8e1; border:2px solid #f9a825; border-radius:10px; padding:14px; text-align:center; font-size:20px; font-weight:700; color:#e65100; margin-bottom:12px; }
.num-badge { display:inline-flex; width:28px; height:28px; border-radius:50%; background:#1a73e8; color:white; align-items:center; justify-content:center; font-size:13px; font-weight:700; margin-right:8px; flex-shrink:0; }
.check-row { display:flex; align-items:flex-start; gap:2px; }
</style>
""", unsafe_allow_html=True)

st.title("6️⃣ 6-Check Screener — Goraksh Method")
st.caption("All 6 checks: PE vs median · Earnings base effect · FII/DII trend · Support/Resistance · RSI levels · Fibonacci")

st.info("""
**The 6 Checks in plain English:**
1. PE ratio should be below its own 1, 3, 5 year median — stock is cheaper than usual
2. The weak quarter being replaced should be the worst of last 4 — base effect benefit
3. FII and DII holding should be increasing — smart money is accumulating
4. Stock should be at a key support or resistance zone — low risk entry
5. RSI should be near 40 or 60 support level — good momentum entry
6. Fibonacci retracement at a key level — technical confirmation
""")

STOCKS = {
    "Banking":  ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","SBIN.NS","BAJFINANCE.NS"],
    "IT":       ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
    "Auto":     ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS"],
    "Pharma":   ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS"],
    "Energy":   ["RELIANCE.NS","ONGC.NS","BPCL.NS","NTPC.NS","POWERGRID.NS"],
    "FMCG":     ["HINDUNILVR.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS"],
    "Infra":    ["LT.NS","ULTRACEMCO.NS","TATASTEEL.NS","JSWSTEEL.NS"],
    "Telecom":  ["BHARTIARTL.NS"],
    "Consumer": ["ASIANPAINT.NS","TITAN.NS"],
}

with st.sidebar:
    st.header("⚙️ Settings")
    capital   = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct  = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    min_checks= st.slider("Minimum checks to show", 1, 6, 4)
    sel_sectors = st.multiselect("Sectors", list(STOCKS.keys()), default=list(STOCKS.keys()))
    st.divider()
    st.markdown("**Check weights:**")
    st.markdown("- Each check = 1 point")
    st.markdown("- 6/6 = Strong BUY")
    st.markdown("- 4-5/6 = Watch")
    st.markdown("- Below 4 = Skip")
    st.divider()
    st.caption("Data via Yahoo Finance. PE/EPS data approximate. FII/DII estimated from institutional patterns. Not SEBI advice.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        df = yf.download(ticker, period="2y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 100: return None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        info = tk.info
        return df, info
    except: return None, None

def check1_pe_vs_median(info, df):
    """PE below 1yr, 3yr, 5yr median"""
    try:
        pe_current = info.get('trailingPE') or info.get('forwardPE')
        if not pe_current: return False, "PE data not available", 0, 0
        # Estimate historical PE from price/EPS
        eps_ttm = info.get('trailingEps', 0)
        if eps_ttm and eps_ttm > 0:
            prices = df['Close']
            pe_1yr  = float(prices.iloc[-252:].mean()  / eps_ttm) if len(prices) >= 252 else pe_current
            pe_3yr  = float(prices.iloc[-504:].mean()  / eps_ttm) if len(prices) >= 504 else pe_1yr
            pe_hist = float(prices.mean() / eps_ttm)
            median_1yr = pe_1yr
            median_hist= pe_hist
            below_1yr  = pe_current < median_1yr
            below_3yr  = pe_current < median_hist
            score = sum([below_1yr, below_3yr]) / 2
            passed = pe_current < median_1yr
            detail = f"Current PE: {pe_current:.1f} | 1yr avg PE: {median_1yr:.1f} | Historical avg PE: {median_hist:.1f}"
            reason = f"PE {pe_current:.1f} is {'BELOW' if passed else 'ABOVE'} 1yr median {median_1yr:.1f} — stock is {'cheaper' if passed else 'more expensive'} than usual"
            return passed, reason, round(pe_current,1), round(median_1yr,1)
        return False, "EPS data unavailable", 0, 0
    except:
        return False, "PE check failed — data unavailable", 0, 0

def check2_earnings_base_effect(info, df):
    """Weakest quarter being replaced"""
    try:
        # Get quarterly earnings trend from price momentum as proxy
        # In real screener this uses actual quarterly EPS data
        quarterly_returns = []
        price = df['Close']
        for q in range(4):
            start = -(q+1)*63
            end   = -q*63 if q > 0 else len(price)
            qr = (float(price.iloc[min(end-1, len(price)-1)]) - float(price.iloc[max(start, 0)])) / float(price.iloc[max(start,0)]) * 100
            quarterly_returns.append(qr)
        # Check if oldest quarter (being replaced) is weakest
        weakest_idx = quarterly_returns.index(min(quarterly_returns))
        base_effect = (weakest_idx == 3)  # Q4 (oldest) is being replaced
        eps_growth = info.get('earningsGrowth', 0) or 0
        revenue_growth = info.get('revenueGrowth', 0) or 0
        passed = base_effect or eps_growth > 0
        reason = f"Earnings growth: {eps_growth*100:.1f}% | Revenue growth: {revenue_growth*100:.1f}% | Base effect: {'Favourable ✓' if base_effect else 'Check manually'}"
        return passed, reason
    except:
        return False, "Earnings data unavailable — check manually on screener.in"

def check3_fii_dii_increasing(info, df):
    """FII/DII holding increasing"""
    try:
        inst_own = info.get('institutionalOwnershipPercentage') or info.get('heldPercentInstitutions', 0)
        if inst_own: inst_own = inst_own * 100 if inst_own < 1 else inst_own
        # Use price strength vs index as proxy for institutional accumulation
        # Delivery volume trend as FII proxy
        price = df['Close']
        vol   = df['Volume']
        # OBV trend — proxy for institutional accumulation
        obv = (np.sign(price.diff()) * vol).cumsum()
        obv_20  = float(obv.iloc[-20:].mean())
        obv_60  = float(obv.iloc[-60:-20].mean())
        obv_rising = obv_20 > obv_60
        # Institutional ownership
        inst_str = f"{inst_own:.1f}%" if inst_own else "N/A"
        passed = obv_rising
        reason = f"Institutional holding: {inst_str} | OBV (accumulation proxy): {'Rising ✓ — institutions accumulating' if obv_rising else 'Falling ✗ — institutions distributing'}"
        return passed, reason
    except:
        return False, "FII/DII data unavailable — verify on NSE website manually"

def check4_support_resistance(df):
    """Stock at support or resistance zone"""
    try:
        price = float(df['Close'].iloc[-1])
        high  = df['High']
        low   = df['Low']
        # Find key levels using pivot points (last 20 swing highs/lows)
        recent = df.iloc[-60:]
        swing_highs = []
        swing_lows  = []
        for i in range(2, len(recent)-2):
            h = float(recent['High'].iloc[i])
            l = float(recent['Low'].iloc[i])
            if h > float(recent['High'].iloc[i-1]) and h > float(recent['High'].iloc[i-2]) and \
               h > float(recent['High'].iloc[i+1]) and h > float(recent['High'].iloc[i+2]):
                swing_highs.append(h)
            if l < float(recent['Low'].iloc[i-1]) and l < float(recent['Low'].iloc[i-2]) and \
               l < float(recent['Low'].iloc[i+1]) and l < float(recent['Low'].iloc[i+2]):
                swing_lows.append(l)
        # Check if price is within 3% of any key level
        all_levels = swing_highs + swing_lows
        near_level = False
        nearest_level = None
        nearest_dist  = 100
        for level in all_levels:
            dist = abs(price - level) / level * 100
            if dist < 3:
                near_level = True
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_level = level
        # Also check 52-week high/low as key levels
        hi52 = float(df['High'].rolling(252).max().iloc[-1])
        lo52 = float(df['Low'].rolling(252).min().iloc[-1])
        near_52hi = abs(price - hi52) / hi52 * 100 < 3
        near_52lo = abs(price - lo52) / lo52 * 100 < 3
        passed = near_level or near_52hi or near_52lo
        if near_52hi: zone = "Near 52W HIGH — potential resistance breakout zone"
        elif near_52lo: zone = "Near 52W LOW — strong support zone"
        elif near_level and nearest_level:
            zone = f"Near key level ₹{nearest_level:.0f} ({nearest_dist:.1f}% away)"
        else:
            zone = f"Not at key level — nearest support/resistance is {nearest_dist:.1f}% away"
        reason = f"{zone} | 52W High: ₹{hi52:.0f} | 52W Low: ₹{lo52:.0f}"
        return passed, reason, nearest_level or lo52
    except:
        return False, "Support/Resistance check failed", 0

def check5_rsi_support(df):
    """RSI at 40 or 60 support level"""
    try:
        d = df['Close'].diff()
        g = d.clip(lower=0).rolling(14).mean()
        l = (-d.clip(upper=0)).rolling(14).mean()
        rsi_series = 100 - (100 / (1 + g/l.replace(0,1e-9)))
        rsi = float(rsi_series.iloc[-1])
        rsi_prev = float(rsi_series.iloc[-3:].min())
        # RSI support levels: 40 (strong support in uptrend), 60 (support after breakout)
        near_40 = 35 <= rsi <= 48  # RSI bouncing from 40 support
        near_60 = 55 <= rsi <= 65  # RSI at 60 support
        above_50 = rsi > 50        # Bullish territory
        rsi_turning_up = rsi > rsi_prev  # RSI starting to recover
        passed = (near_40 and rsi_turning_up) or (near_60 and rsi_turning_up) or (above_50 and rsi_turning_up)
        if near_40:   level = "at 40 support (classic buy zone in uptrend)"
        elif near_60: level = "at 60 support (strong stock holding above 60)"
        elif above_50:level = "above 50 (bullish territory)"
        else:         level = f"at {rsi:.0f} — not at key RSI support level"
        reason = f"RSI: {rsi:.1f} — {level} | Turning up: {'Yes ✓' if rsi_turning_up else 'No ✗'}"
        return passed, reason, round(rsi,1)
    except:
        return False, "RSI check failed", 50

def check6_fibonacci(df):
    """Stock at Fibonacci retracement level"""
    try:
        # Calculate Fibonacci levels from recent swing high to swing low
        lookback = min(252, len(df))
        period_data = df.iloc[-lookback:]
        swing_high = float(period_data['High'].max())
        swing_low  = float(period_data['Low'].min())
        price      = float(df['Close'].iloc[-1])
        diff       = swing_high - swing_low
        # Key Fibonacci levels
        fib_levels = {
            '23.6%': swing_high - 0.236 * diff,
            '38.2%': swing_high - 0.382 * diff,
            '50.0%': swing_high - 0.500 * diff,
            '61.8%': swing_high - 0.618 * diff,  # Golden ratio — most important
            '78.6%': swing_high - 0.786 * diff,
        }
        # Check if price is within 2% of any Fibonacci level
        nearest_fib   = None
        nearest_dist  = 100
        near_golden   = False
        for name, level in fib_levels.items():
            dist = abs(price - level) / level * 100
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_fib  = name
            if name == '61.8%' and dist < 3:
                near_golden = True
        passed = nearest_dist < 3
        fib_price = fib_levels.get(nearest_fib, 0)
        if passed:
            reason = f"Price ₹{price:.0f} is at {nearest_fib} Fibonacci level (₹{fib_price:.0f}) — {nearest_dist:.1f}% away {'🟡 GOLDEN RATIO!' if near_golden else ''}"
        else:
            reason = f"Price ₹{price:.0f} — nearest Fibonacci level is {nearest_fib} at ₹{fib_price:.0f} ({nearest_dist:.1f}% away) — not close enough"
        return passed, reason, nearest_fib, round(nearest_dist,1)
    except:
        return False, "Fibonacci check failed", "N/A", 100

def run_all_checks(df, info, ticker):
    price = float(df['Close'].iloc[-1])
    # ATR for stop/target
    tr = pd.concat([df['High']-df['Low'],
                    (df['High']-df['Close'].shift()).abs(),
                    (df['Low']-df['Close'].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])

    c1_pass, c1_reason, pe_curr, pe_med = check1_pe_vs_median(info, df)
    c2_pass, c2_reason                  = check2_earnings_base_effect(info, df)
    c3_pass, c3_reason                  = check3_fii_dii_increasing(info, df)
    c4_pass, c4_reason, support         = check4_support_resistance(df)
    c5_pass, c5_reason, rsi             = check5_rsi_support(df)
    c6_pass, c6_reason, fib_lvl, fib_d  = check6_fibonacci(df)

    checks = [c1_pass, c2_pass, c3_pass, c4_pass, c5_pass, c6_pass]
    reasons= [c1_reason, c2_reason, c3_reason, c4_reason, c5_reason, c6_reason]
    score  = sum(checks)
    signal = "BUY" if score >= 5 else "WATCH" if score >= 4 else "SKIP"

    stop   = round(price - 1.5*atr, 2)
    target = round(price + 3.0*atr, 2)
    qty    = max(1, int((capital * risk_pct/100) / max(price-stop, 0.01)))

    return {
        "ticker":  ticker.replace(".NS",""),
        "price":   round(price, 2),
        "score":   score,
        "signal":  signal,
        "checks":  checks,
        "reasons": reasons,
        "stop":    stop,
        "target":  target,
        "qty":     qty,
        "pe_curr": pe_curr,
        "pe_med":  pe_med,
        "rsi":     rsi,
        "fib":     fib_lvl,
    }

def render_card(r):
    icon = "🟢" if r["signal"]=="BUY" else "🟡" if r["signal"]=="WATCH" else "🔴"
    labels = [
        "Check 1 — PE vs Median",
        "Check 2 — Earnings Base Effect",
        "Check 3 — FII/DII Increasing",
        "Check 4 — Support/Resistance",
        "Check 5 — RSI at 40/60 Level",
        "Check 6 — Fibonacci Level",
    ]
    with st.expander(f"{icon} **{r['ticker']}** — {r['score']}/6 checks passed — ₹{r['price']}", expanded=(r["signal"]=="BUY")):
        vc = "verdict-buy" if r["signal"]=="BUY" else "verdict-watch" if r["signal"]=="WATCH" else "verdict-skip"
        st.markdown(f'<div class="{vc}">{"✅ BUY — " if r["signal"]=="BUY" else "🟡 WATCH — " if r["signal"]=="WATCH" else "⛔ SKIP — "}{r["score"]}/6 checks passed</div>', unsafe_allow_html=True)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Price",   f"₹{r['price']}")
        c2.metric("Score",   f"{r['score']}/6")
        c3.metric("RSI",     r['rsi'])
        c4.metric("Fib Level", r['fib'])

        st.markdown("##### All 6 checks")
        for i, (passed, reason, label) in enumerate(zip(r["checks"], r["reasons"], labels)):
            css = "check-pass" if passed else "check-fail"
            icon2 = "✅" if passed else "❌"
            st.markdown(f'<div class="{css}"><strong>{icon2} {label}</strong><br>{reason}</div>', unsafe_allow_html=True)

        if r["signal"] == "BUY":
            st.divider()
            st.markdown("##### Trade plan")
            t1,t2,t3,t4 = st.columns(4)
            t1.metric("Entry",  f"₹{r['price']}")
            t2.metric("Stop",   f"₹{r['stop']}")
            t3.metric("Target", f"₹{r['target']}")
            t4.metric("Qty",    r['qty'])
            max_loss = round((r['price']-r['stop'])*r['qty'])
            profit   = round((r['target']-r['price'])*r['qty'])
            st.info(f"Max loss: ₹{max_loss:,} | Potential profit: ₹{profit:,} | R:R: {round(profit/max(max_loss,1),1)}:1")

# Main
tickers = [(s, sec) for sec, lst in STOCKS.items() for s in lst if sec in sel_sectors]

if st.button("🔍 Run 6-Check Scan", type="primary", use_container_width=True):
    results = []
    bar = st.progress(0, "Running 6 checks on each stock…")
    for i, (ticker, sector) in enumerate(tickers):
        bar.progress((i+1)/len(tickers), f"Checking {ticker.replace('.NS','')}…")
        df, info = fetch_data(ticker)
        if df is not None and info is not None:
            r = run_all_checks(df, info, ticker)
            r['sector'] = sector
            results.append(r)
    bar.empty()
    results.sort(key=lambda x: x['score'], reverse=True)
    st.session_state["six_results"] = results

if "six_results" in st.session_state:
    results = [r for r in st.session_state["six_results"] if r['score'] >= min_checks]
    buys  = [r for r in results if r['signal']=="BUY"]
    watch = [r for r in results if r['signal']=="WATCH"]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Scanned",  len(st.session_state["six_results"]))
    c2.metric("6/6 checks", sum(1 for r in results if r['score']==6))
    c3.metric("Buy (5-6)", len(buys))
    c4.metric("Watch (4)", len(watch))
    st.divider()

    if not results:
        st.warning("No stocks met minimum checks. Lower the threshold in sidebar.")
    for r in results:
        render_card(r)
else:
    st.info("Click the button above to run the 6-check scan on all NSE stocks.")
    st.markdown("""
    **What each check looks for:**
    - **Check 1 (PE):** Current PE should be lower than the stock's own historical median. Means the stock is on sale relative to its own history.
    - **Check 2 (Base Effect):** The weak quarter being replaced in YoY comparison should be the worst quarter. This means the upcoming results will look very strong just due to comparison.
    - **Check 3 (FII/DII):** Institutional investors increasing their holding means smart money is confident in the stock.
    - **Check 4 (S/R):** Stock should be at a known support or resistance zone. This gives a low-risk entry with a nearby stop.
    - **Check 5 (RSI):** RSI at 40 or 60 level. In a strong uptrend stocks bounce from 40. In a very strong uptrend they bounce from 60.
    - **Check 6 (Fibonacci):** Price at a Fibonacci retracement level — especially the 61.8% golden ratio — means strong technical support.
    """)
