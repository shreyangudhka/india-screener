# stocks_universe.py
# Complete NSE stock universe — Large Cap + Mid Cap + Small Cap
# Import this in any screener: from stocks_universe import STOCKS, CAP_TYPE, ALL_TICKERS

STOCKS = {
    # ── LARGE CAP (~55 stocks) ───────────────────────────────────────
    "Large Cap - Banking":  ["HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS","KOTAKBANK.NS","SBIN.NS","BAJFINANCE.NS","INDUSINDBK.NS","BANDHANBNK.NS"],
    "Large Cap - IT":       ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS","LTIM.NS"],
    "Large Cap - Auto":     ["TATAMOTORS.NS","MARUTI.NS","M&M.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS","EICHERMOT.NS"],
    "Large Cap - Pharma":   ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","AUROPHARMA.NS"],
    "Large Cap - Energy":   ["RELIANCE.NS","ONGC.NS","BPCL.NS","NTPC.NS","POWERGRID.NS","ADANIPORTS.NS"],
    "Large Cap - FMCG":     ["HINDUNILVR.NS","NESTLEIND.NS","BRITANNIA.NS","DABUR.NS","GODREJCP.NS","MARICO.NS"],
    "Large Cap - Infra":    ["LT.NS","ULTRACEMCO.NS","TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"],
    "Large Cap - Consumer": ["ASIANPAINT.NS","TITAN.NS","DMART.NS","BHARTIARTL.NS"],

    # ── MID CAP (~55 stocks) ─────────────────────────────────────────
    "Mid Cap - Finance":    ["FEDERALBNK.NS","IDFCFIRSTB.NS","CHOLAFIN.NS","MUTHOOTFIN.NS","MANAPPURAM.NS","RBLBANK.NS"],
    "Mid Cap - IT":         ["MPHASIS.NS","KPITTECH.NS","TATAELXSI.NS","PERSISTENT.NS","COFORGE.NS","LTTS.NS","ROUTE.NS"],
    "Mid Cap - Pharma":     ["LAURUSLABS.NS","GRANULES.NS","NATCOPHARM.NS","GLENMARK.NS","ALKEM.NS","TORNTPHARM.NS","JBCHEPHARM.NS"],
    "Mid Cap - Chemicals":  ["DEEPAKNTR.NS","NAVINFLUOR.NS","FINEORG.NS","PIIND.NS","TATACHEM.NS","AARTIIND.NS"],
    "Mid Cap - Auto Anc":   ["BALKRISIND.NS","ENDURANCE.NS","TIINDIA.NS","SUNDRMFAST.NS","MOTHERSON.NS","SUPRAJIT.NS"],
    "Mid Cap - Consumer":   ["RADICO.NS","JYOTHYLAB.NS","VSTIND.NS","EMAMILTD.NS","COLPAL.NS","ZYDUSWELL.NS"],
    "Mid Cap - Building":   ["CENTURYPLY.NS","GREENPANEL.NS","ASTRAL.NS","APLAPOLLO.NS","SUPREMEIND.NS"],
    "Mid Cap - Tech":       ["TANLA.NS","HAPPSTMNDS.NS","BIRLASOFT.NS","INTELLECT.NS"],

    # ── SMALL CAP (~44 stocks) ───────────────────────────────────────
    "Small Cap - IT":       ["MASTEK.NS","NEWGEN.NS","DATAMATICS.NS","RATEGAIN.NS","NUCLEUS.NS"],
    "Small Cap - Pharma":   ["SOLARA.NS","IOLCP.NS","MARKSANS.NS","CAPLIPOINT.NS","SHILPAMED.NS"],
    "Small Cap - Chemicals":["GALAXYSURF.NS","NOCIL.NS","SUDARSCHEM.NS","ROSSELLIND.NS","DMCC.NS"],
    "Small Cap - Finance":  ["AAVAS.NS","HOMEFIRST.NS","CREDITACC.NS","UJJIVANSFB.NS","EQUITASBNK.NS"],
    "Small Cap - Auto":     ["CRAFTSMAN.NS","IFBIND.NS","SUBROS.NS","LUMAXTECH.NS","GABRIEL.NS"],
    "Small Cap - Consumer": ["VENKEYS.NS","BIKAJI.NS","DEVYANI.NS","SAPPHIRE.NS","CCL.NS"],
    "Small Cap - Infra":    ["BRIGADE.NS","MAHLIFE.NS","PHOENIXLTD.NS","SOBHA.NS","GPPL.NS"],
    "Small Cap - Textiles": ["PAGEIND.NS","KITEX.NS","RUPA.NS","VARDHMAN.NS"],
}

# Cap type lookup
CAP_TYPE = {}
for k, v in STOCKS.items():
    cap = "Large" if "Large" in k else "Mid" if "Mid" in k else "Small"
    for s in v:
        CAP_TYPE[s] = cap

# All tickers as flat list with sector
ALL_TICKERS = [(s, k) for k, v in STOCKS.items() for s in v]

# Summary
LARGE_CAP = [s for s,c in CAP_TYPE.items() if c=="Large"]
MID_CAP   = [s for s,c in CAP_TYPE.items() if c=="Mid"]
SMALL_CAP = [s for s,c in CAP_TYPE.items() if c=="Small"]
