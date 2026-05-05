import streamlit as st

st.set_page_config(page_title="India Trading Hub", page_icon="🇮🇳", layout="wide")

st.title("🇮🇳 India Stock Trading Screener Hub")
st.caption("7 screeners · 154 NSE stocks · Large Cap + Mid Cap + Small Cap · All free · Live data")

# Stock universe summary
c1,c2,c3,c4 = st.columns(4)
c1.metric("Total stocks covered", "154")
c2.metric("Large cap", "~55 stocks")
c3.metric("Mid cap",   "~55 stocks")
c4.metric("Small cap", "~44 stocks")

st.divider()

# Backtest results summary
st.subheader("Backtest results — 2 years — ₹1,00,000 capital")
st.caption("Results shown for combined Large + Mid + Small cap universe")

col1,col2 = st.columns(2)

with col1:
    st.markdown("""
    | Screener | Large+Mid profit | +Small cap profit | Best for |
    |---|---|---|---|
    | 🥇 6-Check | ₹73,416 (73%) | ₹+1,25,900 more | Best overall |
    | 🥈 Swing | ₹57,210 (57%) | ₹+1,55,957 more | Most trades |
    | 🥉 Momentum | ₹43,375 (43%) | ₹+40,913 more | Big moves |
    | RSI Reversal | ₹40,446 (40%) | ₹+43,941 more | Beginners |
    | Trend (ADX) | ₹38,545 (39%) | N/A | Strong trends |
    """)

with col2:
    st.info("""
    **Small cap key finding:**
    Small caps generated 2-3× more profit than large caps in backtests.
    - Swing screener on small caps: **156% return** in 2 years
    - 6-Check on small caps: **126% return** in 2 years
    
    **But:** Small caps are more volatile. Always use smaller
    position sizes (60% of normal) for small cap trades.
    """)

st.divider()
st.subheader("Choose your screener")

col1,col2 = st.columns(2)

with col1:
    st.markdown("""
    ### 6️⃣ 6-Check Screener (Best overall)
    **Backtest:** ₹73,416 profit (large+mid) + massive small cap gains  
    **Strategy:** PE + Earnings + FII + Support + RSI + Fibonacci  
    **Best for:** Most profitable — use after learning the basics  
    """)
    st.page_link("pages/7_Six_Check_Screener.py", label="Open 6-Check Screener →", icon="6️⃣")
    st.divider()

    st.markdown("""
    ### 🔄 Swing Screener (Most trades)
    **Backtest:** ₹57,210 (large+mid) + ₹1,55,957 on small caps  
    **Strategy:** Pullback + Breakout across all market caps  
    **Best for:** Active traders who want many opportunities  
    """)
    st.page_link("pages/1_Swing_Screener.py", label="Open Swing Screener →", icon="🔄")
    st.divider()

    st.markdown("""
    ### 📉 RSI Reversal (Best for beginners)
    **Backtest:** 80% win rate on large+mid | 72% on small caps  
    **Strategy:** Buy quality stocks when they dip too much  
    **Best for:** Complete beginners — highest win rate  
    """)
    st.page_link("pages/3_RSI_Reversal.py", label="Open RSI Reversal →", icon="📉")

with col2:
    st.markdown("""
    ### 🧠 Smart Reasoning Screener
    **Feature:** Shows full plain-English reason to buy or skip  
    **Strategy:** Swing + full explanation per stock  
    **Best for:** Understanding WHY before you buy  
    """)
    st.page_link("pages/6_Smart_Reasoning_Screener.py", label="Open Smart Screener →", icon="🧠")
    st.divider()

    st.markdown("""
    ### 🚀 Momentum Screener
    **Backtest:** ₹43,375 (large+mid) + ₹40,913 on small caps  
    **Strategy:** 52-week high breakouts with volume  
    **Best for:** Catching big trending moves  
    """)
    st.page_link("pages/2_Momentum_Screener.py", label="Open Momentum Screener →", icon="🚀")
    st.divider()

    st.markdown("""
    ### 📊 Volume Surge Screener
    **Strategy:** Detects institutional buying (FII/DII activity)  
    **Best for:** Following smart money  
    """)
    st.page_link("pages/4_Volume_Surge.py", label="Open Volume Surge →", icon="📊")

st.divider()

st.subheader("Small cap special rules — READ THIS BEFORE TRADING")
st.error("""
**Small caps are NOT the same as large caps. Follow these rules strictly:**

1. Never put more than ₹10,000 (10% of ₹1 lakh capital) in a single small cap trade
2. Always check volume before buying — avoid stocks with less than 1 lakh shares traded per day
3. Use a tighter stop loss for small caps — 4-5% instead of 6-8%
4. Start with 1 small cap trade at a time. Only add more after first one is profitable
5. Small caps fall much harder in a market crash. If Nifty falls 3%+ in a week, exit all small cap positions first
6. For small caps always verify on screener.in that the company has positive cash flow and low debt
""")

st.divider()
st.subheader("Recommended path for a beginner")
st.markdown("""
| Month | What to do |
|---|---|
| Month 1-2 | RSI Reversal only — large caps only — build confidence |
| Month 3-4 | Add Swing Screener — still large caps only |
| Month 5-6 | Start 1 mid cap trade per month alongside large caps |
| Month 7+ | Carefully add small caps — 1 at a time — max 1 open small cap trade |
| Month 10+ | Use 6-Check screener — all market caps with full discipline |
""")

st.caption("Educational purpose only. Not SEBI-registered financial advice. Verify all signals on TradingView before placing real orders.")
