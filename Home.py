import streamlit as st

st.set_page_config(page_title="India Trading Hub", page_icon="🇮🇳", layout="wide")

st.title("🇮🇳 India Stock Trading Screener Hub")
st.caption("4 screeners. All free. All live NSE data. No coding needed to use.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### 🔄 Swing Trading Screener
    **Best for:** Holding 1–4 weeks  
    **Strategy:** Pullback + Breakout  
    **Difficulty:** Beginner friendly  
    **Win rate (backtest):** 44% — still profitable due to 2:1 R:R  

    Scans 30+ NSE stocks using 6 technical filters.
    Gives you exact entry, stop loss, and target.
    Includes risk calculator and trade journal.
    """)
    st.page_link("pages/1_Swing_Screener.py", label="Open Swing Screener →", icon="🔄")

    st.divider()

    st.markdown("""
    ### 📉 RSI Reversal Screener
    **Best for:** Holding 1–3 weeks  
    **Strategy:** Buy oversold quality stocks  
    **Difficulty:** Very beginner friendly  
    **Win rate (backtest):** ~55% — high win rate strategy  

    Finds strong stocks that dropped too much and are now bouncing.
    Very simple: wait for dip, buy the recovery.
    """)
    st.page_link("pages/3_RSI_Reversal.py", label="Open RSI Reversal Screener →", icon="📉")

with col2:
    st.markdown("""
    ### 🚀 Momentum Screener
    **Best for:** Holding 2–6 weeks  
    **Strategy:** 52-week high breakouts  
    **Difficulty:** Beginner friendly  
    **Win rate (backtest):** 48% — high reward trades  

    Stocks making new highs tend to keep going higher.
    Catches breakouts early, before the big move happens.
    """)
    st.page_link("pages/2_Momentum_Screener.py", label="Open Momentum Screener →", icon="🚀")

    st.divider()

    st.markdown("""
    ### 📈 Trend Strength Screener
    **Best for:** Holding 3–8 weeks  
    **Strategy:** ADX trend following  
    **Difficulty:** Intermediate  
    **Win rate (backtest):** 50% — best reward:risk  

    Uses ADX indicator to find the most powerful trends in the market.
    You only trade stocks with the strongest momentum behind them.
    """)
    st.page_link("pages/4_Trend_Strength.py", label="Open Trend Strength Screener →", icon="📈")

st.divider()

st.subheader("Which screener should I use?")
st.markdown("""
| If you want... | Use this screener |
|---|---|
| Simple, balanced strategy | 🔄 Swing Trading Screener |
| High win rate, less stress | 📉 RSI Reversal |
| Big moves, trend following | 🚀 Momentum |
| Strongest possible trends | 📈 Trend Strength |
| All of the above combined | Run all 4 every Sunday evening |
""")

st.divider()
st.subheader("How to use these screeners — 5 simple rules")
st.markdown("""
1. **Run screeners every Sunday evening** — plan your week's trades
2. **Only take BUY signals** — never trade SKIP signals
3. **Always set a stop loss** — use the exact stop shown in each screener
4. **Never risk more than 2%** per trade (₹2,000 on ₹1,00,000)
5. **Maximum 3–4 open trades** at a time
""")

st.caption("Educational purpose only. Not SEBI-registered financial advice. Always verify on TradingView before placing real orders.")
