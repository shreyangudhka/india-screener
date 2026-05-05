import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="India Swing Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stMetric { background: #f8f9fa; border-radius: 10px; padding: 12px; }
    .buy-badge { background: #d4edda; color: #155724; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 13px; }
    .watch-badge { background: #fff3cd; color: #856404; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 13px; }
    .avoid-badge { background: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 13px; }
    .score-high { color: #155724; font-weight: 700; }
    .score-mid  { color: #856404; font-weight: 700; }
    .score-low  { color: #721c24; font-weight: 700; }
    h1, h2, h3 { color: #1a1a2e; }
    .stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ── Stock universe ────────────────────────────────────────────────────────────
STOCKS = {
    "Banking":  ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","SBIN.NS","BAJFINANCE.NS"],
    "IT":       ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"],
    "Auto":     ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS"],
    "Pharma":   ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS"],
    "Energy":   ["RELIANCE.NS","ONGC.NS","BPCL.NS","ADANIPORTS.NS"],
    "FMCG":     ["HINDUNILVR.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS"],
    "Infra":    ["LT.NS","NTPC.NS","POWERGRID.NS"],
    "Telecom":  ["BHARTIARTL.NS"],
}

ALL_STOCKS = [(s, sec) for sec, lst in STOCKS.items() for s in lst]

# ── Helper functions ──────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(ticker, period="6mo"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except:
        return None

def compute_indicators(df):
    df = df.copy()
    df["EMA20"]  = ta.trend.EMAIndicator(df["Close"], window=20).ema_indicator()
    df["EMA50"]  = ta.trend.EMAIndicator(df["Close"], window=50).ema_indicator()
    df["SMA200"] = ta.trend.SMAIndicator(df["Close"], window=200).sma_indicator() if len(df) >= 200 else np.nan
    df["RSI"]    = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    df["VolMA20"]= df["Volume"].rolling(20).mean()
    df["ATR"]    = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14).average_true_range()
    bb = ta.volatility.BollingerBands(df["Close"], window=20)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_lower"] = bb.bollinger_lband()
    return df

def score_stock(df, ticker):
    if df is None or len(df) < 55:
        return None
    df = compute_indicators(df)
    latest = df.iloc[-1]
    price  = float(latest["Close"])
    score  = 0
    signals = {}

    # 1. Above EMA50
    above_ema50 = price > float(latest["EMA50"]) if pd.notna(latest["EMA50"]) else False
    signals["Above EMA50"] = above_ema50
    if above_ema50: score += 2

    # 2. Above SMA200
    above_sma200 = price > float(latest["SMA200"]) if pd.notna(latest["SMA200"]) else above_ema50
    signals["Above SMA200"] = above_sma200
    if above_sma200: score += 2

    # 3. RSI in sweet spot
    rsi = float(latest["RSI"]) if pd.notna(latest["RSI"]) else 50
    rsi_ok = 38 <= rsi <= 62
    signals[f"RSI {rsi:.0f} (38–62)"] = rsi_ok
    if rsi_ok: score += 2

    # 4. Volume confirmation
    vol_ratio = float(latest["Volume"]) / float(latest["VolMA20"]) if float(latest["VolMA20"]) > 0 else 1
    vol_ok = vol_ratio >= 1.2
    signals[f"Volume {vol_ratio:.1f}× avg"] = vol_ok
    if vol_ok: score += 2

    # 5. Pullback setup — price pulled back 5–15% from recent high then bouncing
    recent_high = float(df["Close"].rolling(20).max().iloc[-1])
    pullback_pct = (recent_high - price) / recent_high * 100
    pullback_ok = 3 <= pullback_pct <= 18
    signals[f"Pullback {pullback_pct:.1f}% from high"] = pullback_ok
    if pullback_ok: score += 1

    # 6. Weekly trend (last 10 weeks slope)
    weekly = df["Close"].resample("W").last().dropna()
    if len(weekly) >= 5:
        slope = (float(weekly.iloc[-1]) - float(weekly.iloc[-5])) / float(weekly.iloc[-5]) * 100
        weekly_up = slope > 0
    else:
        weekly_up = above_ema50
    signals["Weekly trend up"] = weekly_up
    if weekly_up: score += 1

    # Setup classification
    recent_range = df["Close"].iloc[-20:]
    range_width  = (recent_range.max() - recent_range.min()) / recent_range.min() * 100
    if range_width < 8 and vol_ok:
        setup = "Breakout"
    elif pullback_ok and above_ema50:
        setup = "Pullback"
    elif abs(price - float(latest["EMA20"])) / price * 100 < 1.5:
        setup = "MA Bounce"
    else:
        setup = "Pullback"

    hi52 = float(df["Close"].rolling(min(252, len(df))).max().iloc[-1])
    near52 = (price / hi52) > 0.97
    if near52 and vol_ok:
        setup = "52W High BO"

    signal = "BUY" if score >= 8 and weekly_up else "WATCH" if score >= 5 else "AVOID"

    atr = float(latest["ATR"]) if pd.notna(latest["ATR"]) else price * 0.02
    stop  = round(price - 1.5 * atr, 2)
    target= round(price + 3.0 * atr, 2)
    rr = round((target - price) / (price - stop), 2) if price > stop else 0

    return {
        "Ticker": ticker.replace(".NS",""),
        "Price": round(price, 2),
        "Setup": setup,
        "RSI": round(rsi, 1),
        "Vol ratio": round(vol_ratio, 2),
        "Score": score,
        "Signal": signal,
        "Stop": stop,
        "Target": target,
        "R:R": rr,
        "Signals": signals,
        "DF": df,
    }

def run_backtest(ticker, setup_type, capital, risk_pct, period="1y"):
    df = fetch_data(ticker, period=period)
    if df is None or len(df) < 60:
        return None, []
    df = compute_indicators(df)
    trades = []
    in_trade = False
    entry_price = stop_price = target_price = qty = 0

    for i in range(55, len(df) - 1):
        row = df.iloc[i]
        price = float(row["Close"])
        rsi   = float(row["RSI"]) if pd.notna(row["RSI"]) else 50
        ema50 = float(row["EMA50"]) if pd.notna(row["EMA50"]) else price
        vol   = float(row["Volume"])
        volma = float(row["VolMA20"]) if float(row["VolMA20"]) > 0 else vol
        atr   = float(row["ATR"]) if pd.notna(row["ATR"]) else price * 0.015

        # Exit logic
        if in_trade:
            next_close = float(df.iloc[i+1]["Close"])
            if next_close <= stop_price:
                pnl = (stop_price - entry_price) * qty
                trades.append({"Date": df.index[i+1], "Type": "Exit-Stop", "Price": stop_price,
                                "PnL": round(pnl, 2), "Return%": round(pnl/(entry_price*qty)*100, 2)})
                in_trade = False
            elif next_close >= target_price:
                pnl = (target_price - entry_price) * qty
                trades.append({"Date": df.index[i+1], "Type": "Exit-Target", "Price": target_price,
                                "PnL": round(pnl, 2), "Return%": round(pnl/(entry_price*qty)*100, 2)})
                in_trade = False
            continue

        # Entry logic
        recent_high = float(df["Close"].iloc[max(0,i-20):i].max())
        pullback_pct = (recent_high - price) / recent_high * 100 if recent_high > 0 else 0
        prev_close = float(df.iloc[i-1]["Close"])

        if setup_type in ("Pullback", "Both"):
            if (price > ema50 and 3 <= pullback_pct <= 18 and
                    38 <= rsi <= 58 and price > prev_close and vol > volma * 1.1):
                entry_price  = price
                stop_price   = round(price - 1.5 * atr, 2)
                target_price = round(price + 3.0 * atr, 2)
                max_risk = capital * risk_pct / 100
                qty = max(1, int(max_risk / (entry_price - stop_price)))
                trades.append({"Date": df.index[i], "Type": "Entry-Pullback", "Price": entry_price,
                                "PnL": 0, "Return%": 0})
                in_trade = True

        if setup_type in ("Breakout", "Both") and not in_trade:
            range_hi = float(df["Close"].iloc[max(0,i-15):i].max())
            if (price > range_hi * 0.995 and vol > volma * 1.5 and price > ema50):
                entry_price  = price
                stop_price   = round(range_hi * 0.97, 2)
                target_price = round(price + (price - stop_price) * 2.5, 2)
                max_risk = capital * risk_pct / 100
                qty = max(1, int(max_risk / (entry_price - stop_price)))
                trades.append({"Date": df.index[i], "Type": "Entry-Breakout", "Price": entry_price,
                                "PnL": 0, "Return%": 0})
                in_trade = True

    exits = [t for t in trades if t["Type"].startswith("Exit")]
    return trades, exits

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📈 India Swing Trading Screener")
st.caption("Live NSE data · Nifty 50 & Nifty Next 50 universe · Refresh every hour")

with st.sidebar:
    st.header("⚙️ Settings")
    capital = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    max_risk = capital * risk_pct / 100
    st.metric("Max risk / trade", f"₹{max_risk:,.0f}")
    st.divider()
    sel_sectors = st.multiselect("Sectors", list(STOCKS.keys()), default=list(STOCKS.keys()))
    min_score   = st.slider("Min score", 0, 10, 5)
    signal_filter = st.selectbox("Signal", ["All", "BUY", "WATCH", "AVOID"])
    st.divider()
    st.caption("Data via Yahoo Finance (yfinance). For educational use only. Not SEBI-registered advice.")

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Screener", "📊 Backtester", "🧮 Risk Calc", "📓 Trade Journal"])

# ─── TAB 1: SCREENER ──────────────────────────────────────────────────────────
with tab1:
    selected_tickers = [(s, sec) for sec, lst in STOCKS.items()
                        for s in lst if sec in sel_sectors]

    if st.button("🔄 Run screener", type="primary", use_container_width=True):
        results = []
        prog = st.progress(0, text="Fetching live NSE data…")
        for idx, (ticker, sector) in enumerate(selected_tickers):
            prog.progress((idx+1)/len(selected_tickers),
                          text=f"Analysing {ticker.replace('.NS','')}…")
            df = fetch_data(ticker)
            res = score_stock(df, ticker)
            if res:
                res["Sector"] = sector
                results.append(res)
        prog.empty()
        st.session_state["screener_results"] = results

    if "screener_results" in st.session_state:
        results = st.session_state["screener_results"]
        filtered = [r for r in results
                    if r["Score"] >= min_score
                    and (signal_filter == "All" or r["Signal"] == signal_filter)]
        filtered.sort(key=lambda x: x["Score"], reverse=True)

        buy_count   = sum(1 for r in filtered if r["Signal"] == "BUY")
        watch_count = sum(1 for r in filtered if r["Signal"] == "WATCH")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stocks scanned",  len(results))
        c2.metric("Buy signals",     buy_count)
        c3.metric("Watch signals",   watch_count)
        c4.metric("Showing",         len(filtered))

        st.divider()

        for r in filtered:
            sig_color = {"BUY": "🟢", "WATCH": "🟡", "AVOID": "🔴"}.get(r["Signal"], "⚪")
            with st.expander(f"{sig_color} **{r['Ticker']}** ({r['Sector']}) · Score {r['Score']}/10 · {r['Setup']} · ₹{r['Price']}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Price",   f"₹{r['Price']}")
                col2.metric("Stop",    f"₹{r['Stop']}")
                col3.metric("Target",  f"₹{r['Target']}")
                col4.metric("R:R",     f"{r['R:R']} : 1")

                st.markdown("**Signal checklist:**")
                for label, passed in r["Signals"].items():
                    icon = "✅" if passed else "❌"
                    st.markdown(f"{icon} {label}")

                qty = max(1, int(max_risk / max(r["Price"] - r["Stop"], 0.01)))
                pos_size = qty * r["Price"]
                st.info(f"💡 Position size: **{qty} shares** · Deployed: **₹{pos_size:,.0f}** · "
                        f"Max loss: **₹{(r['Price'] - r['Stop']) * qty:,.0f}**")
    else:
        st.info("👆 Click **Run screener** to fetch live NSE data and scan stocks.")

# ─── TAB 2: BACKTESTER ────────────────────────────────────────────────────────
with tab2:
    st.subheader("Strategy Backtester")
    st.caption("Simulates the pullback and/or breakout strategy on historical NSE data.")

    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        bt_ticker = st.selectbox("Stock", [s.replace(".NS","") for s,_ in ALL_STOCKS])
    with bc2:
        bt_setup  = st.selectbox("Setup", ["Both", "Pullback", "Breakout"])
    with bc3:
        bt_period = st.selectbox("Period", ["6mo", "1y", "2y", "3y"])
    with bc4:
        bt_capital = st.number_input("Capital ₹", value=capital, step=5000, key="bt_cap")
        bt_risk    = st.number_input("Risk %", value=risk_pct, step=0.5, key="bt_risk")

    if st.button("▶️ Run backtest", type="primary", use_container_width=True):
        with st.spinner(f"Backtesting {bt_ticker}…"):
            all_trades, exits = run_backtest(
                bt_ticker + ".NS", bt_setup, bt_capital, bt_risk, bt_period)

        if not exits:
            st.warning("No completed trades found. Try a longer period or different setup.")
        else:
            wins  = [t for t in exits if t["PnL"] > 0]
            losses= [t for t in exits if t["PnL"] <= 0]
            total_pnl = sum(t["PnL"] for t in exits)
            win_rate  = len(wins) / len(exits) * 100
            avg_win   = np.mean([t["PnL"] for t in wins]) if wins else 0
            avg_loss  = np.mean([t["PnL"] for t in losses]) if losses else 0
            profit_factor = abs(sum(t["PnL"] for t in wins) / sum(t["PnL"] for t in losses)) if losses else 99

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Total trades",    len(exits))
            m2.metric("Win rate",        f"{win_rate:.1f}%")
            m3.metric("Total P&L",       f"₹{total_pnl:,.0f}",
                      delta=f"{'+'  if total_pnl>=0 else ''}{total_pnl/bt_capital*100:.1f}%")
            m4.metric("Avg win",         f"₹{avg_win:,.0f}")
            m5.metric("Avg loss",        f"₹{avg_loss:,.0f}")
            m6.metric("Profit factor",   f"{profit_factor:.2f}")

            st.divider()

            # Equity curve
            equity = [bt_capital]
            for t in exits:
                equity.append(equity[-1] + t["PnL"])
            eq_df = pd.DataFrame({"Equity (₹)": equity})
            st.subheader("Equity curve")
            st.line_chart(eq_df)

            # Trade log
            st.subheader("Trade log")
            trade_df = pd.DataFrame(exits)
            trade_df["Date"] = pd.to_datetime(trade_df["Date"]).dt.strftime("%d %b %Y")
            trade_df["Result"] = trade_df["PnL"].apply(lambda x: "✅ Win" if x > 0 else "❌ Loss")
            trade_df["PnL"] = trade_df["PnL"].apply(lambda x: f"₹{x:+,.0f}")
            trade_df["Return%"] = trade_df["Return%"].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(trade_df[["Date","Type","Price","PnL","Return%","Result"]],
                         use_container_width=True, hide_index=True)

# ─── TAB 3: RISK CALC ─────────────────────────────────────────────────────────
with tab3:
    st.subheader("Position Size Calculator")
    rc1, rc2 = st.columns(2)
    with rc1:
        r_capital = st.number_input("Capital (₹)", value=capital,  key="r_cap")
        r_risk    = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, key="r_risk")
        r_entry   = st.number_input("Entry price (₹)", value=1500.0)
    with rc2:
        r_stop    = st.number_input("Stop loss (₹)", value=1425.0)
        r_target  = st.number_input("Target (₹)",    value=1620.0)

    if r_entry > r_stop > 0:
        max_r    = r_capital * r_risk / 100
        stop_diff= r_entry - r_stop
        qty      = max(1, int(max_r / stop_diff))
        pos_size = qty * r_entry
        pot_profit = qty * (r_target - r_entry)
        rr       = (r_target - r_entry) / stop_diff
        stop_pct = stop_diff / r_entry * 100
        deploy   = pos_size / r_capital * 100

        st.divider()
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Max risk",       f"₹{max_r:,.0f}")
        m2.metric("Qty to buy",     f"{qty}")
        m3.metric("Position size",  f"₹{pos_size:,.0f}")
        m4.metric("Pot. profit",    f"₹{pot_profit:,.0f}")
        m5.metric("Stop %",         f"{stop_pct:.1f}%")
        m6.metric("R:R ratio",      f"{rr:.1f} : 1",
                  delta="Good" if rr >= 2 else "Too low",
                  delta_color="normal" if rr >= 2 else "inverse")

        st.progress(min(1.0, deploy/100), text=f"Capital deployed: {deploy:.0f}%")

        if rr < 2:
            st.warning("⚠️ R:R below 2:1 — consider skipping this trade or adjusting your target.")
        else:
            st.success("✅ Valid setup. R:R is acceptable.")
    else:
        st.info("Enter entry and stop loss prices above.")

# ─── TAB 4: JOURNAL ───────────────────────────────────────────────────────────
with tab4:
    st.subheader("Trade Journal")
    if "journal" not in st.session_state:
        st.session_state.journal = []

    with st.form("add_trade"):
        jc1, jc2, jc3 = st.columns(3)
        with jc1:
            j_date   = st.date_input("Date", value=datetime.today())
            j_stock  = st.text_input("Stock", placeholder="ICICIBANK")
            j_setup  = st.selectbox("Setup", ["Pullback","Breakout","52W High","MA Bounce"])
        with jc2:
            j_entry  = st.number_input("Entry ₹", min_value=0.0, value=0.0)
            j_exit   = st.number_input("Exit ₹",  min_value=0.0, value=0.0)
            j_qty    = st.number_input("Qty",      min_value=1,   value=1)
        with jc3:
            j_notes  = st.text_area("Notes / reason for trade", height=120)
        submitted = st.form_submit_button("➕ Add trade", use_container_width=True)
        if submitted and j_stock and j_entry > 0 and j_exit > 0:
            pnl = round((j_exit - j_entry) * j_qty, 2)
            st.session_state.journal.append({
                "Date": j_date.strftime("%d %b %Y"),
                "Stock": j_stock.upper(),
                "Setup": j_setup,
                "Entry": j_entry,
                "Exit": j_exit,
                "Qty": j_qty,
                "PnL": pnl,
                "Result": "Win" if pnl > 0 else "Loss",
                "Notes": j_notes,
            })
            st.success(f"Trade logged! P&L: ₹{pnl:+,.0f}")

    if st.session_state.journal:
        jdf = pd.DataFrame(st.session_state.journal)
        total = jdf["PnL"].sum()
        wins  = (jdf["PnL"] > 0).sum()
        wr    = wins / len(jdf) * 100

        jm1, jm2, jm3, jm4 = st.columns(4)
        jm1.metric("Total trades",  len(jdf))
        jm2.metric("Win rate",      f"{wr:.1f}%")
        jm3.metric("Total P&L",     f"₹{total:+,.0f}")
        jm4.metric("Wins / Losses", f"{wins} / {len(jdf)-wins}")

        jdf_show = jdf.copy()
        jdf_show["PnL"] = jdf_show["PnL"].apply(lambda x: f"₹{x:+,.0f}")
        st.dataframe(jdf_show[["Date","Stock","Setup","Entry","Exit","Qty","PnL","Result","Notes"]],
                     use_container_width=True, hide_index=True)

        if st.button("🗑️ Clear journal"):
            st.session_state.journal = []
            st.rerun()
    else:
        st.info("No trades logged yet. Add your first trade above.")

st.divider()
st.caption("Built for educational purposes. Always verify signals on TradingView / Zerodha Kite before placing orders. Not SEBI-registered financial advice.")
