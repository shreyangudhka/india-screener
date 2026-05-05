import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Swing Screener", page_icon="🔄", layout="wide")

st.markdown("""
<style>
.stMetric { background:#f8f9fa; border-radius:10px; padding:12px; }
.cap-large { background:#e8f5e9; color:#1b5e20; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.cap-mid   { background:#e3f2fd; color:#0d47a1; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.cap-small { background:#fff3e0; color:#e65100; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.buy-badge { background:#d4edda; color:#155724; padding:3px 10px; border-radius:12px; font-weight:600; font-size:13px; }
.watch-badge { background:#fff3cd; color:#856404; padding:3px 10px; border-radius:12px; font-weight:600; font-size:13px; }
</style>""", unsafe_allow_html=True)

st.title("🔄 Swing Trading Screener — Large + Mid + Small Cap")
st.caption("154 NSE stocks across all market caps. Pullback and Breakout setups.")

# ── Complete stock universe ───────────────────────────────────────────────────
STOCKS = {
    "Large Cap - Banking":  ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","SBIN.NS","BAJFINANCE.NS","INDUSINDBK.NS"],
    "Large Cap - IT":       ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS","LTIM.NS"],
    "Large Cap - Auto":     ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS"],
    "Large Cap - Pharma":   ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","AUROPHARMA.NS"],
    "Large Cap - Energy":   ["RELIANCE.NS","ONGC.NS","BPCL.NS","NTPC.NS","POWERGRID.NS","ADANIPORTS.NS"],
    "Large Cap - FMCG":     ["HINDUNILVR.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","GODREJCP.NS"],
    "Large Cap - Infra":    ["LT.NS","ULTRACEMCO.NS","TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"],
    "Large Cap - Consumer": ["ASIANPAINT.NS","TITAN.NS","DMART.NS","BHARTIARTL.NS"],
    "Mid Cap - Finance":    ["FEDERALBNK.NS","IDFCFIRSTB.NS","CHOLAFIN.NS","MUTHOOTFIN.NS","MANAPPURAM.NS"],
    "Mid Cap - IT":         ["MPHASIS.NS","KPITTECH.NS","TATAELXSI.NS","PERSISTENT.NS","COFORGE.NS","LTTS.NS"],
    "Mid Cap - Pharma":     ["LAURUSLABS.NS","GRANULES.NS","NATCOPHARM.NS","GLENMARK.NS","ALKEM.NS","TORNTPHARM.NS"],
    "Mid Cap - Chemicals":  ["DEEPAKNTR.NS","NAVINFLUOR.NS","FINEORG.NS","PIIND.NS","TATACHEM.NS","AARTIIND.NS"],
    "Mid Cap - Auto Anc":   ["BALKRISIND.NS","ENDURANCE.NS","TIINDIA.NS","SUNDRMFAST.NS","MOTHERSON.NS","SUPRAJIT.NS"],
    "Mid Cap - Consumer":   ["RADICO.NS","JYOTHYLAB.NS","VSTIND.NS","MARICO.NS","EMAMILTD.NS","COLPAL.NS"],
    "Mid Cap - Building":   ["CENTURYPLY.NS","GREENPANEL.NS","ASTRAL.NS","APLAPOLLO.NS","SUPREMEIND.NS"],
    "Mid Cap - Tech":       ["TANLA.NS","HAPPSTMNDS.NS","BIRLASOFT.NS","ROUTE.NS"],
    "Small Cap - IT":       ["INTELLECT.NS","MASTEK.NS","NEWGEN.NS","DATAMATICS.NS","RATEGAIN.NS"],
    "Small Cap - Pharma":   ["SOLARA.NS","IOLCP.NS","MARKSANS.NS","WOCKPHARMA.NS","CAPLIPOINT.NS"],
    "Small Cap - Chemicals":["GALAXYSURF.NS","NOCIL.NS","SUDARSCHEM.NS","ROSSELLIND.NS"],
    "Small Cap - Finance":  ["AAVAS.NS","HOMEFIRST.NS","CREDITACC.NS","UJJIVANSFB.NS","EQUITASBNK.NS"],
    "Small Cap - Auto":     ["CRAFTSMAN.NS","IFBIND.NS","SUBROS.NS","LUMAXTECH.NS","GABRIEL.NS"],
    "Small Cap - Consumer": ["VENKEYS.NS","BIKAJI.NS","DEVYANI.NS","SAPPHIRE.NS"],
    "Small Cap - Infra":    ["BRIGADE.NS","MAHLIFE.NS","PHOENIXLTD.NS","SOBHA.NS"],
    "Small Cap - Textiles": ["PAGEIND.NS","KITEX.NS","RUPA.NS","VARDHMAN.NS"],
}

CAP_TYPE = {}
for k, v in STOCKS.items():
    cap = "Large" if "Large" in k else "Mid" if "Mid" in k else "Small"
    for s in v: CAP_TYPE[s] = cap

ALL_TICKERS = [(s,k) for k,v in STOCKS.items() for s in v]

with st.sidebar:
    st.header("⚙️ Settings")
    capital   = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct  = st.slider("Risk per trade (%)", 1.0, 3.0, 2.0, 0.5)
    max_risk  = capital * risk_pct / 100
    st.metric("Max risk/trade", f"₹{max_risk:,.0f}")
    st.divider()
    cap_filter = st.multiselect("Market cap", ["Large","Mid","Small"], default=["Large","Mid","Small"])
    min_score  = st.slider("Min score", 0, 10, 6)
    sig_filter = st.selectbox("Signal", ["All","BUY","WATCH"])
    st.divider()
    st.markdown("**Small cap warning:**")
    st.warning("Small caps are more volatile. Use smaller position sizes for small caps. Never put more than 10% of capital in one small cap.")
    st.caption("Not SEBI advice.")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 55: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except: return None

def score_stock(df, ticker, sector):
    df = df.copy()
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    df['SMA200']= df['Close'].rolling(200).mean() if len(df)>=200 else np.nan
    df['VolMA20']=df['Volume'].rolling(20).mean()
    d=df['Close'].diff(); g=d.clip(lower=0).rolling(14).mean()
    l=(-d.clip(upper=0)).rolling(14).mean()
    df['RSI']=100-(100/(1+g/l.replace(0,1e-9)))
    tr=pd.concat([df['High']-df['Low'],
                  (df['High']-df['Close'].shift()).abs(),
                  (df['Low']-df['Close'].shift()).abs()],axis=1).max(axis=1)
    df['ATR']=tr.rolling(14).mean()
    r=df.iloc[-1]; price=float(r['Close'])
    e50=float(r['EMA50']) if not pd.isna(r['EMA50']) else price
    sma200=float(r['SMA200']) if not pd.isna(r['SMA200']) else price
    rsi=float(r['RSI']) if not pd.isna(r['RSI']) else 50
    vol=float(r['Volume']); vma=float(r['VolMA20']) if not pd.isna(r['VolMA20']) else vol
    atr=float(r['ATR']) if not pd.isna(r['ATR']) else price*0.02
    vol_ratio=vol/vma if vma>0 else 1
    rhi=float(df['Close'].rolling(20).max().iloc[-1])
    pb=(rhi-price)/rhi*100 if rhi>0 else 0
    weekly=df['Close'].resample('W').last().dropna()
    weekly_up=(float(weekly.iloc[-1])>float(weekly.iloc[-5])) if len(weekly)>=5 else True
    score=0
    if price>e50:     score+=2
    if price>sma200:  score+=2
    if 38<=rsi<=62:   score+=2
    if vol_ratio>=1.2:score+=2
    if 3<=pb<=18:     score+=1
    if weekly_up:     score+=1
    hi52=float(df['Close'].rolling(min(252,len(df))).max().iloc[-1])
    near52=(price/hi52)>0.97
    rw=float(df['Close'].iloc[-20:].max()-df['Close'].iloc[-20:].min())/float(df['Close'].iloc[-20:].min())*100
    setup=("52W High BO" if near52 and vol_ratio>=1.5
           else "Breakout" if rw<8 and vol_ratio>=1.5
           else "Pullback" if 3<=pb<=18 and price>e50
           else "MA Bounce" if abs(price-e50)/price*100<1.5
           else "Developing")
    signal="BUY" if score>=8 and weekly_up else "WATCH" if score>=5 else "SKIP"
    stop=round(price-1.5*atr,2); target=round(price+3*atr,2)
    cap=CAP_TYPE.get(ticker,"Mid")
    # Small caps: reduce position size due to higher risk
    risk_mult=0.6 if cap=="Small" else 0.8 if cap=="Mid" else 1.0
    qty=max(1,int((capital*risk_pct/100*risk_mult)/max(price-stop,0.01)))
    return {"Ticker":ticker.replace(".NS",""),"Sector":sector,"Cap":cap,
            "Price":round(price,2),"Score":score,"Signal":signal,"Setup":setup,
            "RSI":round(rsi,1),"Vol":round(vol_ratio,2),"Stop":stop,"Target":target,
            "Qty":qty,"PB%":round(pb,1),"Hi52":round(hi52,2)}

tickers_filtered = [(s,k) for s,k in ALL_TICKERS if CAP_TYPE.get(s,"Mid") in cap_filter]

if st.button("🔍 Scan all stocks", type="primary", use_container_width=True):
    results=[]
    bar=st.progress(0,"Scanning…")
    for i,(t,sec) in enumerate(tickers_filtered):
        bar.progress((i+1)/len(tickers_filtered), f"Checking {t.replace('.NS','')}…")
        df=fetch(t)
        if df is not None: results.append(score_stock(df,t,sec))
    bar.empty()
    results.sort(key=lambda x:x['Score'],reverse=True)
    st.session_state["swing_all"]=results

if "swing_all" in st.session_state:
    res=st.session_state["swing_all"]
    filt=[r for r in res if r['Score']>=min_score and
          (sig_filter=="All" or r['Signal']==sig_filter)]
    buys=[r for r in filt if r['Signal']=="BUY"]
    watchs=[r for r in filt if r['Signal']=="WATCH"]
    lc=[r for r in filt if r['Cap']=="Large"]
    mc=[r for r in filt if r['Cap']=="Mid"]
    sc=[r for r in filt if r['Cap']=="Small"]

    c1,c2,c3,c4,c5,c6=st.columns(6)
    c1.metric("Scanned",len(res))
    c2.metric("Buy signals",len(buys))
    c3.metric("Large cap",len([r for r in buys if r['Cap']=="Large"]))
    c4.metric("Mid cap",len([r for r in buys if r['Cap']=="Mid"]))
    c5.metric("Small cap",len([r for r in buys if r['Cap']=="Small"]))
    c6.metric("Watch",len(watchs))
    st.divider()

    for cap_name,cap_list,cap_html in [
        ("Large Cap Signals",lc,"cap-large"),
        ("Mid Cap Signals",mc,"cap-mid"),
        ("Small Cap Signals",sc,"cap-small"),
    ]:
        if cap_list:
            st.subheader(cap_name)
            if cap_html=="cap-small":
                st.warning("⚠️ Small caps are higher risk. Position sizes are automatically reduced by 40%. Always verify liquidity before buying.")
            df_show=pd.DataFrame(cap_list)[["Ticker","Sector","Cap","Price","Score","Signal",
                                             "Setup","RSI","Vol","Stop","Target","Qty","PB%"]]
            st.dataframe(df_show,use_container_width=True,hide_index=True)

    st.divider()
    with st.expander("Show full results table"):
        df_all=pd.DataFrame(filt).sort_values("Score",ascending=False)
        st.dataframe(df_all[["Ticker","Cap","Sector","Price","Score","Signal","Setup","RSI","Vol","Stop","Target","Qty"]],
                     use_container_width=True,hide_index=True)
else:
    st.info("Click the button above to scan all 154 stocks across Large, Mid and Small cap.")
    col1,col2,col3=st.columns(3)
    col1.metric("Large cap stocks","~55")
    col2.metric("Mid cap stocks","~55")
    col3.metric("Small cap stocks","~44")
