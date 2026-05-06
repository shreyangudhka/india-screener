"""
Home.py — India Stock Screener Hub
All NSE + BSE stocks | 8 screeners | Mark Minervini VCP
"""
import streamlit as st

st.set_page_config(
    page_title="India Stock Screener Hub",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d;
            --green:#3fb950; --red:#f85149; --blue:#58a6ff;
            --gold:#ffa657; --text:#c9d1d9; --muted:#8b949e; }
    .stApp { background-color: var(--bg); color: var(--text); }
    div[data-testid="stSidebarContent"] { background:#0d1117; }
    .hero {
        background: linear-gradient(135deg,#0f2a1a 0%,#0d1117 50%,#1a1f29 100%);
        border: 1px solid var(--border); border-radius:16px;
        padding: 40px; text-align:center; margin-bottom:24px;
    }
    .hero h1 { color:white; font-size:2.4rem; margin:0 0 8px 0; }
    .hero p  { color:var(--muted); font-size:1.05rem; margin:0; }
    .screener-card {
        background:var(--card); border:1px solid var(--border);
        border-radius:12px; padding:20px; margin-bottom:12px;
        transition: border-color 0.2s;
    }
    .screener-card:hover { border-color: var(--blue); }
    .screener-card h3 { color:var(--blue); margin:0 0 6px 0; font-size:1.05rem; }
    .screener-card p  { color:var(--muted); margin:0; font-size:0.85rem; }
    .badge {
        display:inline-block; padding:2px 10px; border-radius:20px;
        font-size:0.75rem; font-weight:700; margin-right:6px;
    }
    .badge-green  { background:#0f2a1a; color:var(--green); border:1px solid var(--green); }
    .badge-blue   { background:#0f1a2a; color:var(--blue);  border:1px solid var(--blue);  }
    .badge-gold   { background:#1a1500; color:var(--gold);  border:1px solid var(--gold);  }
    .stat-row { display:flex; gap:16px; justify-content:center; flex-wrap:wrap; margin:16px 0; }
    .stat-box {
        background:var(--card); border:1px solid var(--border); border-radius:10px;
        padding:14px 20px; text-align:center; min-width:120px;
    }
    .stat-val { font-size:1.6rem; font-weight:800; color:var(--green); }
    .stat-lbl { font-size:0.75rem; color:var(--muted); }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='hero'>
    <h1>📈 India Stock Screener Hub</h1>
    <p>8 professional screeners · All NSE + BSE stocks (~5,500+) · Mark Minervini VCP · Educational use only</p>
    <div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>5,500+</div><div class='stat-lbl'>Stocks (NSE+BSE)</div></div>
        <div class='stat-box'><div class='stat-val'>8</div><div class='stat-lbl'>Screeners</div></div>
        <div class='stat-box'><div class='stat-val'>81.5%</div><div class='stat-lbl'>VCP Backtest Return</div></div>
        <div class='stat-box'><div class='stat-val'>73.4%</div><div class='stat-lbl'>6-Check Return</div></div>
        <div class='stat-box'><div class='stat-val'>Free</div><div class='stat-lbl'>Forever</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Screeners ─────────────────────────────────────────────────────────────────
st.markdown("### 🔍 Available Screeners")
st.markdown("*Click any screener in the left sidebar to open it.*")

screeners = [
    ("🌀", "8_VCP_Screener", "VCP Screener — ALL NSE + BSE",
     "The best screener. Scans all ~5,500 listed stocks for Mark Minervini's Volatility Contraction Pattern. "
     "Backtest: 81.5% return. Score 6-7 = strong buy.",
     ["Best Performer", "Candlestick Charts", "Full NSE+BSE"]),
    ("📈", "1_Swing_Screener", "Swing Trading Screener",
     "Finds pullback and breakout setups in uptrending stocks. Uses 50/200 DMA + RSI + volume. "
     "Backtest: 40% return over 2 years.",
     ["Pullback", "Breakout", "All Caps"]),
    ("🚀", "2_Momentum_Screener", "Momentum Screener",
     "Finds stocks making 52-week highs with rising volume. Rides strong trends. "
     "Best for bull markets.",
     ["52W High", "Volume Surge", "Trend"]),
    ("📉", "3_RSI_Reversal", "RSI Reversal Screener",
     "Finds quality stocks that have dipped too much. RSI < 40 reversal. "
     "Backtest: 80% win rate. Best for beginners.",
     ["High Win Rate", "Beginner Friendly", "Mean Reversion"]),
    ("⚡", "4_Volume_Surge", "Volume Surge Screener",
     "Finds stocks with unusual volume spikes. Volume 2×+ average = institutional buying. "
     "Fast-moving setups.",
     ["Institutional", "Fast Moves", "Volume"]),
    ("💪", "5_Trend_Strength", "Trend Strength Screener",
     "Ranks stocks by ADX trend strength. Strong trends = more reliable entries. "
     "Best combined with VCP.",
     ["ADX", "Trend Quality", "Ranking"]),
    ("🧠", "6_Smart_Reasoning_Screener", "Smart Reasoning Screener",
     "Shows plain-English reasons WHY to buy or avoid each stock. Full trade plan generated automatically. "
     "Best for learning.",
     ["AI Reasoning", "Full Plan", "Education"]),
    ("✅", "7_Six_Check_Screener", "6-Check Screener (Goraksh Method)",
     "Combines PE below median + earnings base effect + FII/DII increasing + support/resistance + RSI + Fibonacci. "
     "Backtest: 73.4% return.",
     ["Fundamental", "FII/DII", "Fibonacci"]),
]

for icon, page, title, desc, tags in screeners:
    badge_html = "".join(
        f"<span class='badge badge-{'green' if i==0 else 'blue' if i==1 else 'gold'}'>{t}</span>"
        for i, t in enumerate(tags)
    )
    st.markdown(f"""
    <div class='screener-card'>
        <h3>{icon} {title}</h3>
        <p>{desc}</p>
        <div style='margin-top:8px'>{badge_html}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── Universe info ─────────────────────────────────────────────────────────────
st.markdown("### 📊 Stock Universe — How It Works")
col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    **What stocks are included?**
    - ✅ All ~2,000 NSE equity stocks
    - ✅ All ~400 NSE SME stocks  
    - ✅ All ~5,500 BSE equity stocks
    - ✅ Total: ~5,500 unique stocks (auto-deduplicated)
    
    **How is the list fetched?**
    - Downloads fresh from NSE India archives
    - Downloads fresh from BSE India API
    - Cached locally for 24 hours
    - Falls back to a 600-stock list if offline
    """)
with col2:
    st.markdown("""
    **Recommended approach:**
    1. Start with **NSE only** (better liquidity)
    2. Add **NSE-SME** for small cap opportunities
    3. Add **BSE** for stocks not listed on NSE
    
    **Scan time estimates:**
    - NSE only (~2,000 stocks): ~5-8 minutes
    - NSE + SME (~2,400 stocks): ~8-12 minutes
    - All including BSE (~5,500): ~20-30 minutes
    
    *Use 5 parallel workers and batch size 40 for best results.*
    """)

st.markdown("---")
st.markdown("""
<p style='color:#8b949e; font-size:0.8rem; text-align:center'>
⚠️ This tool is for educational purposes only. Not SEBI-registered financial advice. 
Always verify signals on TradingView before placing real trades. Past performance does not guarantee future results.
</p>
""", unsafe_allow_html=True)
