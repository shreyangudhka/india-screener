"""
stocks_universe.py
──────────────────────────────────────────────────────────────────────────────
Dynamically fetches ALL listed stocks from NSE (~2,000) and BSE (~5,500+).
Falls back to a large hardcoded list if the download fails.
Results are cached locally for 24 hours to avoid repeated downloads.
──────────────────────────────────────────────────────────────────────────────
"""

import os, json, time, io, logging
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("stocks_universe")

# ── Cache config ──────────────────────────────────────────────────────────────
CACHE_FILE   = Path(".cache/stocks_universe.json")
CACHE_EXPIRY = 24 * 3600   # refresh every 24 hours

# ── NSE & BSE public endpoints ────────────────────────────────────────────────
NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME_URL    = "https://archives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"

BSE_EQUITY_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    "?Group=&Scripcode=&industry=&segment=Equity&status=Active"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────────────────────
#  NSE FETCHER
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_nse_stocks() -> list[dict]:
    """Download ALL NSE equity + NSE SME stocks."""
    stocks = []

    for url, exchange_tag in [(NSE_EQUITY_URL, "NSE"), (NSE_SME_URL, "NSE-SME")]:
        try:
            session = requests.Session()
            # NSE requires a cookie — prime it first
            session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            df = pd.read_csv(io.StringIO(resp.text))
            df.columns = df.columns.str.strip()

            # Expected columns: SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING,
            #                   PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE
            for _, row in df.iterrows():
                sym = str(row.get("SYMBOL", "")).strip()
                name = str(row.get("NAME OF COMPANY", "")).strip()
                if sym and name and sym != "nan":
                    stocks.append({
                        "symbol":   sym,
                        "nse_code": sym,
                        "bse_code": "",
                        "name":     name,
                        "exchange": exchange_tag,
                        "yf_ticker": f"{sym}.NS",
                    })

            log.info(f"{exchange_tag}: fetched {len(df)} stocks from {url}")
        except Exception as e:
            log.warning(f"{exchange_tag} fetch failed: {e}")

    return stocks


# ─────────────────────────────────────────────────────────────────────────────
#  BSE FETCHER
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_bse_stocks() -> list[dict]:
    """Download ALL BSE-listed equity stocks."""
    stocks = []
    try:
        resp = requests.get(BSE_EQUITY_URL, headers={
            **HEADERS, "Referer": "https://www.bseindia.com/"
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # BSE JSON structure: list of dicts with keys like
        # Scrip_Cd, Scrip_Name, Status, Group, Face_Value, ISIN_Number, Mktcap
        items = data if isinstance(data, list) else data.get("Table", [])

        for item in items:
            scrip_code = str(item.get("Scrip_Cd", "")).strip()
            name       = str(item.get("Scrip_Name", "")).strip()
            status     = str(item.get("Status", "")).strip().upper()
            if scrip_code and name and scrip_code != "nan" and status != "SUSPENDED":
                stocks.append({
                    "symbol":    name.split(" ")[0].upper()[:20],
                    "nse_code":  "",
                    "bse_code":  scrip_code,
                    "name":      name,
                    "exchange":  "BSE",
                    "yf_ticker": f"{scrip_code}.BO",
                })

        log.info(f"BSE: fetched {len(stocks)} stocks")
    except Exception as e:
        log.warning(f"BSE fetch failed: {e}")

    return stocks


# ─────────────────────────────────────────────────────────────────────────────
#  MERGE  NSE + BSE  (deduplicate by name similarity)
# ─────────────────────────────────────────────────────────────────────────────
def _merge(nse: list[dict], bse: list[dict]) -> list[dict]:
    """
    Prefer NSE tickers when available (better liquidity, stricter listing).
    Add BSE-only stocks that are not already in NSE list.
    """
    seen_names = {s["name"].lower()[:25] for s in nse}
    merged = list(nse)

    for s in bse:
        key = s["name"].lower()[:25]
        if key not in seen_names:
            merged.append(s)
            seen_names.add(key)

    log.info(f"Total after merge: {len(merged)} unique stocks (NSE + BSE)")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
#  CACHE  helpers
# ─────────────────────────────────────────────────────────────────────────────
def _load_cache() -> list[dict] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE) as f:
            payload = json.load(f)
        age = time.time() - payload.get("ts", 0)
        if age < CACHE_EXPIRY:
            log.info(f"Using cached stock list ({len(payload['stocks'])} stocks, "
                     f"age {age/3600:.1f}h)")
            return payload["stocks"]
    except Exception:
        pass
    return None


def _save_cache(stocks: list[dict]):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"ts": time.time(), "stocks": stocks}, f)
    log.info(f"Cached {len(stocks)} stocks → {CACHE_FILE}")


# ─────────────────────────────────────────────────────────────────────────────
#  LARGE FALLBACK  (used when network is unavailable)
#  Contains ~600 commonly traded NSE stocks across all market caps
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_STOCKS_NSE = [
    # LARGE CAP — NIFTY 50
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","HINDUNILVR","SBIN","BAJFINANCE",
    "BHARTIARTL","ITC","KOTAKBANK","LT","HCLTECH","ASIANPAINT","AXISBANK","MARUTI",
    "SUNPHARMA","TITAN","ULTRACEMCO","NTPC","ONGC","POWERGRID","BAJAJFINSV","WIPRO",
    "NESTLEIND","TATAMOTORS","TECHM","DIVISLAB","ADANIENT","ADANIPORTS","JSWSTEEL",
    "TATASTEEL","COALINDIA","CIPLA","GRASIM","BRITANNIA","HINDALCO","APOLLOHOSP",
    "EICHERMOT","DRREDDY","BPCL","INDUSINDBK","HEROMOTOCO","SHREECEM","SBILIFE",
    "HDFCLIFE","BAJAJ-AUTO","UPL","TATACONSUM","M&M",
    # LARGE CAP — NIFTY NEXT 50
    "DMART","SIEMENS","HAVELLS","PIDILITIND","BERGEPAINT","MUTHOOTFIN","TORNTPHARM",
    "AUROPHARMA","LUPIN","BIOCON","GLAND","IPCALAB","ALKEM","TORNTPOWER","TATAPOWER",
    "ADANIGREEN","ADANITRANS","TATACOMM","MCDOWELL-N","PAGEIND","COLPAL","DABUR",
    "GODREJCP","MARICO","PGHH","EMAMILTD","TVSMOTOR","BOSCHLTD","CUMMINSIND",
    "BALKRISIND","APOLLOTYRE","AMBUJACEM","ACCLTD","SHRIRAMFIN","CHOLAFIN","HDFCAMC",
    "ICICIGI","ICICIPRULI","SBICARD","BANDHANBNK","FEDERALBNK","IDFCFIRSTB",
    "RBLBANK","PNB","CANBK","UNIONBANK","INDIANB","IOB","BANKINDIA","CENTRALBK",
    # MID CAP
    "GODREJPROP","OBEROIRLTY","PRESTIGE","PHOENIXLTD","SOBHA","MAHLIFE",
    "KPITECH","PERSISTENT","LTTS","COFORGE","MPHASIS","HEXAWARE","SONACOMS",
    "MINDTREE","NIITTECH","HAPPSTMNDS","TANLA","MASTEK","KPITTECH","NEWGEN",
    "DEEPAKNITRI","FINPIPE","SRF","AARTIIND","NAVINFLUOR","ALKYLAMINE","FINEORG",
    "CLEAN","SUDARSCHEM","VINDHYATEL","GALAXYSURF","TATACHEM","PIDILITIND","BASF",
    "GUJFLUORO","NOCIL","ATUL","VINYLINDIA","CHEM","VINATIORGA",
    "IDFCFIRSTB","CREDITACC","UJJIVANSFB","EQUITASBNK","SURYODAY","JSFB",
    "MAHINDCIE","MOTHERSON","ENDURANCE","SUPRAJIT","WABCO","GABRIEL","SUBROS",
    "EXIDEIND","AMARA","MINDA","UNOMINDA","SANSERA","SUNDRMFAST","FIEMIND",
    "ESCORT","VSTTILLERS","GREAVES","ASHOKLEY","TATAELXSI","ZOMATO","NYKAA",
    "PAYTM","POLICYBZR","DELHIVERY","MAPMYINDIA","IRCTC","RVNL","RITES","IRFC",
    "RAILVIKAS","TITAGARH","TEXRAIL","WABCOINDIA","KECL","KALPATPOWR","VOLTAMP",
    "INOXWIND","SUZLON","TRIL","GREENKO","ACME","ADANIPOWER","TORNTPOWER",
    "CESC","NHPC","SJVN","THERMAX","BHEL","BEL","HAL","COCHINSHIP","GRSE","BEML",
    "MAZAGON","GDPL","APOLLOHOSP","NARAYANHC","MAXHEALTH","FORTIS","THYROCARE",
    "KRSNAA","VIJAYA","RAINBOW","KIMS","ASTER","METROPOLIS","LALPATHLAB",
    "DRREDDYS","SUNPHARMADV","CADILAHC","PFIZER","ABBOTINDIA","ASTRAZEN",
    "GLAXO","SANOFI","WOCKPHARMA","GLENMARK","ERIS","JB","MANKIND","MEDANTA",
    # SMALL CAP
    "TIPSINDLTD","RADIOCITY","TVTODAY","NDTV","JAGRAN","DBCORP","HMVL",
    "GREENPANEL","CENTURYPLY","GREENPLY","ACTION","KITEX","RUPA","SOMANYCERA",
    "KAJARIACER","ORIENTBELL","NITCO","HSIL","CERA","HINDWAREAP",
    "IGARASHI","PRAJIND","HLEGLAS","GARWALLBANK","SAKSOFT","DATAMATICS",
    "CYIENT","ZENSAR","SONATASOFT","RAMSYSCORP","TATAELXSI","INFIBEAM",
    "PCBL","NOCIL","ELGI","GRINDWELL","RATNAMANI","MAHASTEEL","MANAPPURAM",
    "IIFL","MUTHOOTCAP","UJJIVAN","SATIN","SPANDANA","CREDITACC",
    "VSBLTY","IRIS","DEEPAK","FOSECOIND","TIINDIA","SUVENPHAR","NEULANDLAB",
    "SEQUENT","JYOTHY","EMAMI","BAJAJCON","GILLETTE","GODFRYPHLP","VSTIN",
    "TASTYBITE","ZYDUSWELL","CHOLAHLDNG","REPCO","CANFINHOME","LICHSGFIN",
    "GRUH","APTUS","AAVAS","HOMEFIRST","SATINDLTD","BIRLAMONEY","GEOJITFSL",
    "NUVAMA","5PAISA","MOTILALOFS","ISEC","EDELWEISS","JM","KARURVYSYA",
    "CITYUNIONBK","LAKSHVILAS","DCBBANK","JKBANK","SOUTHBANK","KTKBANK",
    "TATAMET","NATIONALUM","HINDCOPPER","MOIL","NMDC","GALLANTT","APL","AARTI",
    "GMDCLTD","BANKBARODA","UCOBANKLTD","ANDHRABANK","SYNDIBANK","DENABANK",
    "PIIND","JUBLPHARMA","GRANULES","MEDICO","STRIDES","SOLARA","LAURUS",
    "SUVEN","DIVIS","BIOCON","GLAND","HIKAL","NAVIN","LAURUSLABS",
    "ASTEC","AIMCO","TATACHEM","GHCL","NIRLON","MOLDTKPAC","MOLD-TEK",
    "PODDARMENT","TEXINFRA","SHAKTIPUMP","ISGEC","THIRUMALAI","KANCHI",
    "GESHIP","SCAPL","SEACOAST","SNOWMAN","MAHLOG","GATI","SAFEXPRESS",
    "BLUESTARCO","VOLTAS","SYMPHONY","AMBER","DIXON","VGUARD","POLYCAB",
    "FINOLEX","HAVELLS","CROMPTON","ORIENTELEC","KANSAINER","AKZOINDIA",
    "VIKASECO","VAIBHAVGBL","THANGAMAL","RAJESHEXPO","PCJEWELLER","TRIBHOVN",
    "TFCILTD","HUDCO","NBCC","NCC","AHLUCONT","DBRL","DILIPBUILDCON","PNCINFRA",
    "KNRCON","H.G.INFRA","SADBHAV","JPPOWER","JPASSOCIAT","JKCEMENT","SAGAR",
    "RAMCOCEM","HEIDELBERG","JKLAKSHMI","SANGHIBUILDER","BIRLACORPN","PRISMCEM",
    "WHLIL","WINDLAS","EIDPARRY","TRIVENI","BALRAMCHIN","DHAMPUR","BAJAJHIND",
    "DCMSHRIRAM","COROMANDEL","GNFC","ASTRAL","FINOLEX","SUPREME","NILKAMAL",
    "PLASTIBLEN","PGEL","VIP","SAMSONITE","SAFARI","SKFINDIA","TIMKEN","SCHAEFFLER",
    "FAG","GREAVESCOT","KIRLOSKAR","GRAPHITE","HEG","PHILIPCARB","RAIN","OCCL",
    "WELSPUN","RSWM","VARDHMAN","ARVIND","Raymond","MAFATLAL","GRASIM","JINDALPOLY",
    "JBMA","MAHINDRA","MAZDOCK","COCHINSHIP","GRSE","GARDENSILK","FILATEX",
]

def _build_fallback() -> list[dict]:
    stocks = []
    cap_map = {
        # Large caps (first ~100)
        **{s: "Large" for s in FALLBACK_STOCKS_NSE[:100]},
        # Mid caps (next ~200)
        **{s: "Mid" for s in FALLBACK_STOCKS_NSE[100:300]},
        # Small caps (rest)
        **{s: "Small" for s in FALLBACK_STOCKS_NSE[300:]},
    }
    for sym in FALLBACK_STOCKS_NSE:
        stocks.append({
            "symbol":    sym,
            "nse_code":  sym,
            "bse_code":  "",
            "name":      sym,
            "exchange":  "NSE",
            "yf_ticker": f"{sym}.NS",
            "cap":       cap_map.get(sym, "Mid"),
        })
    return stocks


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────
def get_all_stocks(force_refresh: bool = False) -> list[dict]:
    """
    Returns a list of dicts, each with keys:
        symbol, nse_code, bse_code, name, exchange, yf_ticker

    On first call (or after 24h), downloads fresh lists from NSE & BSE.
    Subsequent calls within 24h return the cached list instantly.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    log.info("Downloading fresh stock lists from NSE and BSE …")
    nse_stocks = _fetch_nse_stocks()
    bse_stocks = _fetch_bse_stocks()

    if nse_stocks or bse_stocks:
        all_stocks = _merge(nse_stocks, bse_stocks)
    else:
        log.warning("Both NSE and BSE downloads failed — using fallback list")
        all_stocks = _build_fallback()

    _save_cache(all_stocks)
    return all_stocks


def get_nse_tickers(stocks: list[dict] | None = None) -> list[str]:
    """Return yfinance-compatible NSE tickers (SYMBOL.NS)."""
    if stocks is None:
        stocks = get_all_stocks()
    return [s["yf_ticker"] for s in stocks if s["exchange"] in ("NSE", "NSE-SME")]


def get_bse_tickers(stocks: list[dict] | None = None) -> list[str]:
    """Return yfinance-compatible BSE tickers (SCRIPCODE.BO)."""
    if stocks is None:
        stocks = get_all_stocks()
    return [s["yf_ticker"] for s in stocks if s["exchange"] == "BSE"]


def get_stock_count() -> dict:
    stocks = get_all_stocks()
    nse = sum(1 for s in stocks if "NSE" in s["exchange"])
    bse = sum(1 for s in stocks if s["exchange"] == "BSE")
    return {"total": len(stocks), "nse": nse, "bse": bse}


# ─────────────────────────────────────────────────────────────────────────────
#  BATCH DOWNLOAD helper  (used by screeners)
# ─────────────────────────────────────────────────────────────────────────────
def download_batch(tickers: list[str], period: str = "6mo",
                   batch_size: int = 50) -> dict:
    """
    Download OHLCV data for a list of tickers in batches.
    Returns {ticker: pd.DataFrame} for tickers that have data.
    Skips tickers with no data silently.
    """
    import yfinance as yf

    result = {}
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            raw = yf.download(
                batch, period=period, interval="1d",
                group_by="ticker", auto_adjust=True,
                progress=False, threads=True, timeout=30,
            )
            for ticker in batch:
                try:
                    if len(batch) == 1:
                        df = raw
                    else:
                        df = raw[ticker] if ticker in raw.columns.get_level_values(0) else pd.DataFrame()
                    df = df.dropna(how="all")
                    if len(df) >= 30:
                        result[ticker] = df
                except Exception:
                    failed.append(ticker)
        except Exception as e:
            log.warning(f"Batch {i//batch_size + 1} failed: {e}")
            failed.extend(batch)

    log.info(f"Downloaded {len(result)} stocks | Failed: {len(failed)}")
    return result
