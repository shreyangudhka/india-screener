"""
stocks_universe.py  ─  SPEED ENGINE for all 8 screeners
═══════════════════════════════════════════════════════
KEY FUNCTIONS
  get_all_stocks()      → list of {symbol, name, exchange, yf_ticker}
  get_bulk_prices()     → {yf_ticker: price}  ← 500 stocks per HTTP call
  download_batch()      → {yf_ticker: DataFrame}  ← N stocks per HTTP call
  get_stock_count()     → int

HOW THIS MAKES THE SCREENERS 10-20× FASTER
  Old: yf.download("RELIANCE.NS") × 2000 = 2000 HTTP requests
  New: yf.download(["REL","TCS",...50 more]) = 1 HTTP request per batch

  Price pre-filter: fetch ALL prices in 4 requests, drop out-of-range stocks
  before downloading expensive OHLCV data → skips ~40-60% of stocks.
"""

import os, json, requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

_UNIVERSE_CACHE = "universe_cache.json"
_PRICE_CACHE    = "price_cache.json"

# ── Fallback list (used if NSE/BSE APIs are blocked) ────────────────────────
_FALLBACK = [
    # Large Cap
    {"symbol":"RELIANCE",   "name":"Reliance Industries",     "exchange":"NSE","yf_ticker":"RELIANCE.NS"},
    {"symbol":"TCS",        "name":"Tata Consultancy",        "exchange":"NSE","yf_ticker":"TCS.NS"},
    {"symbol":"HDFCBANK",   "name":"HDFC Bank",               "exchange":"NSE","yf_ticker":"HDFCBANK.NS"},
    {"symbol":"INFY",       "name":"Infosys",                 "exchange":"NSE","yf_ticker":"INFY.NS"},
    {"symbol":"ICICIBANK",  "name":"ICICI Bank",              "exchange":"NSE","yf_ticker":"ICICIBANK.NS"},
    {"symbol":"HINDUNILVR", "name":"Hindustan Unilever",      "exchange":"NSE","yf_ticker":"HINDUNILVR.NS"},
    {"symbol":"SBIN",       "name":"State Bank of India",     "exchange":"NSE","yf_ticker":"SBIN.NS"},
    {"symbol":"BAJFINANCE", "name":"Bajaj Finance",           "exchange":"NSE","yf_ticker":"BAJFINANCE.NS"},
    {"symbol":"BHARTIARTL", "name":"Bharti Airtel",           "exchange":"NSE","yf_ticker":"BHARTIARTL.NS"},
    {"symbol":"KOTAKBANK",  "name":"Kotak Mahindra Bank",     "exchange":"NSE","yf_ticker":"KOTAKBANK.NS"},
    {"symbol":"LT",         "name":"Larsen & Toubro",         "exchange":"NSE","yf_ticker":"LT.NS"},
    {"symbol":"ITC",        "name":"ITC Limited",             "exchange":"NSE","yf_ticker":"ITC.NS"},
    {"symbol":"AXISBANK",   "name":"Axis Bank",               "exchange":"NSE","yf_ticker":"AXISBANK.NS"},
    {"symbol":"ASIANPAINT", "name":"Asian Paints",            "exchange":"NSE","yf_ticker":"ASIANPAINT.NS"},
    {"symbol":"MARUTI",     "name":"Maruti Suzuki",           "exchange":"NSE","yf_ticker":"MARUTI.NS"},
    {"symbol":"SUNPHARMA",  "name":"Sun Pharmaceutical",      "exchange":"NSE","yf_ticker":"SUNPHARMA.NS"},
    {"symbol":"TITAN",      "name":"Titan Company",           "exchange":"NSE","yf_ticker":"TITAN.NS"},
    {"symbol":"WIPRO",      "name":"Wipro",                   "exchange":"NSE","yf_ticker":"WIPRO.NS"},
    {"symbol":"ULTRACEMCO", "name":"UltraTech Cement",        "exchange":"NSE","yf_ticker":"ULTRACEMCO.NS"},
    {"symbol":"ONGC",       "name":"ONGC",                    "exchange":"NSE","yf_ticker":"ONGC.NS"},
    {"symbol":"NTPC",       "name":"NTPC",                    "exchange":"NSE","yf_ticker":"NTPC.NS"},
    {"symbol":"POWERGRID",  "name":"Power Grid Corp",         "exchange":"NSE","yf_ticker":"POWERGRID.NS"},
    {"symbol":"NESTLEIND",  "name":"Nestle India",            "exchange":"NSE","yf_ticker":"NESTLEIND.NS"},
    {"symbol":"TECHM",      "name":"Tech Mahindra",           "exchange":"NSE","yf_ticker":"TECHM.NS"},
    {"symbol":"HCLTECH",    "name":"HCL Technologies",        "exchange":"NSE","yf_ticker":"HCLTECH.NS"},
    {"symbol":"M&M",        "name":"Mahindra & Mahindra",     "exchange":"NSE","yf_ticker":"M&M.NS"},
    {"symbol":"TATAMOTORS", "name":"Tata Motors",             "exchange":"NSE","yf_ticker":"TATAMOTORS.NS"},
    {"symbol":"TATASTEEL",  "name":"Tata Steel",              "exchange":"NSE","yf_ticker":"TATASTEEL.NS"},
    {"symbol":"HINDALCO",   "name":"Hindalco Industries",     "exchange":"NSE","yf_ticker":"HINDALCO.NS"},
    {"symbol":"JSWSTEEL",   "name":"JSW Steel",               "exchange":"NSE","yf_ticker":"JSWSTEEL.NS"},
    {"symbol":"COALINDIA",  "name":"Coal India",              "exchange":"NSE","yf_ticker":"COALINDIA.NS"},
    {"symbol":"GRASIM",     "name":"Grasim Industries",       "exchange":"NSE","yf_ticker":"GRASIM.NS"},
    {"symbol":"ADANIENT",   "name":"Adani Enterprises",       "exchange":"NSE","yf_ticker":"ADANIENT.NS"},
    {"symbol":"ADANIPORTS", "name":"Adani Ports",             "exchange":"NSE","yf_ticker":"ADANIPORTS.NS"},
    {"symbol":"BRITANNIA",  "name":"Britannia Industries",    "exchange":"NSE","yf_ticker":"BRITANNIA.NS"},
    {"symbol":"DIVISLAB",   "name":"Divi's Laboratories",     "exchange":"NSE","yf_ticker":"DIVISLAB.NS"},
    {"symbol":"DRREDDY",    "name":"Dr. Reddy's Labs",        "exchange":"NSE","yf_ticker":"DRREDDY.NS"},
    {"symbol":"CIPLA",      "name":"Cipla",                   "exchange":"NSE","yf_ticker":"CIPLA.NS"},
    {"symbol":"EICHERMOT",  "name":"Eicher Motors",           "exchange":"NSE","yf_ticker":"EICHERMOT.NS"},
    {"symbol":"HEROMOTOCO", "name":"Hero MotoCorp",           "exchange":"NSE","yf_ticker":"HEROMOTOCO.NS"},
    {"symbol":"BAJAJ-AUTO", "name":"Bajaj Auto",              "exchange":"NSE","yf_ticker":"BAJAJ-AUTO.NS"},
    {"symbol":"APOLLOHOSP", "name":"Apollo Hospitals",        "exchange":"NSE","yf_ticker":"APOLLOHOSP.NS"},
    {"symbol":"INDUSINDBK", "name":"IndusInd Bank",           "exchange":"NSE","yf_ticker":"INDUSINDBK.NS"},
    {"symbol":"SBILIFE",    "name":"SBI Life Insurance",      "exchange":"NSE","yf_ticker":"SBILIFE.NS"},
    {"symbol":"HDFCLIFE",   "name":"HDFC Life Insurance",     "exchange":"NSE","yf_ticker":"HDFCLIFE.NS"},
    {"symbol":"BPCL",       "name":"BPCL",                    "exchange":"NSE","yf_ticker":"BPCL.NS"},
    {"symbol":"IOC",        "name":"Indian Oil Corp",         "exchange":"NSE","yf_ticker":"IOC.NS"},
    {"symbol":"GAIL",       "name":"GAIL India",              "exchange":"NSE","yf_ticker":"GAIL.NS"},
    {"symbol":"HAVELLS",    "name":"Havells India",           "exchange":"NSE","yf_ticker":"HAVELLS.NS"},
    {"symbol":"PIDILITIND", "name":"Pidilite Industries",     "exchange":"NSE","yf_ticker":"PIDILITIND.NS"},
    {"symbol":"SIEMENS",    "name":"Siemens India",           "exchange":"NSE","yf_ticker":"SIEMENS.NS"},
    {"symbol":"ABB",        "name":"ABB India",               "exchange":"NSE","yf_ticker":"ABB.NS"},
    {"symbol":"BOSCHLTD",   "name":"Bosch Limited",           "exchange":"NSE","yf_ticker":"BOSCHLTD.NS"},
    {"symbol":"COLPAL",     "name":"Colgate-Palmolive",       "exchange":"NSE","yf_ticker":"COLPAL.NS"},
    {"symbol":"DABUR",      "name":"Dabur India",             "exchange":"NSE","yf_ticker":"DABUR.NS"},
    {"symbol":"MARICO",     "name":"Marico",                  "exchange":"NSE","yf_ticker":"MARICO.NS"},
    {"symbol":"GODREJCP",   "name":"Godrej Consumer Products","exchange":"NSE","yf_ticker":"GODREJCP.NS"},
    {"symbol":"TATACONSUM", "name":"Tata Consumer Products",  "exchange":"NSE","yf_ticker":"TATACONSUM.NS"},
    {"symbol":"LICI",       "name":"LIC of India",            "exchange":"NSE","yf_ticker":"LICI.NS"},
    {"symbol":"IRCTC",      "name":"IRCTC",                   "exchange":"NSE","yf_ticker":"IRCTC.NS"},
    {"symbol":"HAL",        "name":"Hindustan Aeronautics",   "exchange":"NSE","yf_ticker":"HAL.NS"},
    {"symbol":"BEL",        "name":"Bharat Electronics",      "exchange":"NSE","yf_ticker":"BEL.NS"},
    {"symbol":"BHEL",       "name":"Bharat Heavy Electricals","exchange":"NSE","yf_ticker":"BHEL.NS"},
    # Mid Cap
    {"symbol":"PERSISTENT", "name":"Persistent Systems",      "exchange":"NSE","yf_ticker":"PERSISTENT.NS"},
    {"symbol":"MPHASIS",    "name":"Mphasis",                 "exchange":"NSE","yf_ticker":"MPHASIS.NS"},
    {"symbol":"COFORGE",    "name":"Coforge",                 "exchange":"NSE","yf_ticker":"COFORGE.NS"},
    {"symbol":"LTTS",       "name":"L&T Technology Services", "exchange":"NSE","yf_ticker":"LTTS.NS"},
    {"symbol":"KPIT",       "name":"KPIT Technologies",       "exchange":"NSE","yf_ticker":"KPIT.NS"},
    {"symbol":"ASTRAL",     "name":"Astral Limited",          "exchange":"NSE","yf_ticker":"ASTRAL.NS"},
    {"symbol":"POLYCAB",    "name":"Polycab India",           "exchange":"NSE","yf_ticker":"POLYCAB.NS"},
    {"symbol":"VOLTAS",     "name":"Voltas",                  "exchange":"NSE","yf_ticker":"VOLTAS.NS"},
    {"symbol":"CROMPTON",   "name":"Crompton Greaves",        "exchange":"NSE","yf_ticker":"CROMPTON.NS"},
    {"symbol":"VGUARD",     "name":"V-Guard Industries",      "exchange":"NSE","yf_ticker":"VGUARD.NS"},
    {"symbol":"AIAENG",     "name":"AIA Engineering",         "exchange":"NSE","yf_ticker":"AIAENG.NS"},
    {"symbol":"CUMMINSIND", "name":"Cummins India",           "exchange":"NSE","yf_ticker":"CUMMINSIND.NS"},
    {"symbol":"THERMAX",    "name":"Thermax",                 "exchange":"NSE","yf_ticker":"THERMAX.NS"},
    {"symbol":"ESCORTS",    "name":"Escorts Kubota",          "exchange":"NSE","yf_ticker":"ESCORTS.NS"},
    {"symbol":"TVSMOTOR",   "name":"TVS Motor Company",       "exchange":"NSE","yf_ticker":"TVSMOTOR.NS"},
    {"symbol":"BALKRISIND", "name":"Balkrishna Industries",   "exchange":"NSE","yf_ticker":"BALKRISIND.NS"},
    {"symbol":"EXIDEIND",   "name":"Exide Industries",        "exchange":"NSE","yf_ticker":"EXIDEIND.NS"},
    {"symbol":"MOTHERSON",  "name":"Samvardhana Motherson",   "exchange":"NSE","yf_ticker":"MOTHERSON.NS"},
    {"symbol":"BHARATFORG", "name":"Bharat Forge",            "exchange":"NSE","yf_ticker":"BHARATFORG.NS"},
    {"symbol":"PAGEIND",    "name":"Page Industries",         "exchange":"NSE","yf_ticker":"PAGEIND.NS"},
    {"symbol":"DMART",      "name":"Avenue Supermarts",       "exchange":"NSE","yf_ticker":"DMART.NS"},
    {"symbol":"TRENT",      "name":"Trent",                   "exchange":"NSE","yf_ticker":"TRENT.NS"},
    {"symbol":"CHOLAFIN",   "name":"Cholamandalam Finance",   "exchange":"NSE","yf_ticker":"CHOLAFIN.NS"},
    {"symbol":"M&MFIN",     "name":"M&M Financial Services",  "exchange":"NSE","yf_ticker":"M&MFIN.NS"},
    {"symbol":"MUTHOOTFIN", "name":"Muthoot Finance",         "exchange":"NSE","yf_ticker":"MUTHOOTFIN.NS"},
    {"symbol":"MANAPPURAM", "name":"Manappuram Finance",      "exchange":"NSE","yf_ticker":"MANAPPURAM.NS"},
    {"symbol":"SBICARD",    "name":"SBI Cards",               "exchange":"NSE","yf_ticker":"SBICARD.NS"},
    {"symbol":"HDFCAMC",    "name":"HDFC AMC",                "exchange":"NSE","yf_ticker":"HDFCAMC.NS"},
    {"symbol":"NIPPONLIFE", "name":"Nippon Life India AMC",   "exchange":"NSE","yf_ticker":"NIPPONLIFE.NS"},
    {"symbol":"ICICIGI",    "name":"ICICI Lombard",           "exchange":"NSE","yf_ticker":"ICICIGI.NS"},
    {"symbol":"TORNTPHARM", "name":"Torrent Pharmaceuticals", "exchange":"NSE","yf_ticker":"TORNTPHARM.NS"},
    {"symbol":"AUROPHARMA", "name":"Aurobindo Pharma",        "exchange":"NSE","yf_ticker":"AUROPHARMA.NS"},
    {"symbol":"LUPIN",      "name":"Lupin",                   "exchange":"NSE","yf_ticker":"LUPIN.NS"},
    {"symbol":"ALKEM",      "name":"Alkem Laboratories",      "exchange":"NSE","yf_ticker":"ALKEM.NS"},
    {"symbol":"IPCALAB",    "name":"IPCA Laboratories",       "exchange":"NSE","yf_ticker":"IPCALAB.NS"},
    {"symbol":"LALPATHLAB", "name":"Dr Lal PathLabs",         "exchange":"NSE","yf_ticker":"LALPATHLAB.NS"},
    {"symbol":"OBEROIRLTY", "name":"Oberoi Realty",           "exchange":"NSE","yf_ticker":"OBEROIRLTY.NS"},
    {"symbol":"DLF",        "name":"DLF",                     "exchange":"NSE","yf_ticker":"DLF.NS"},
    {"symbol":"GODREJPROP", "name":"Godrej Properties",       "exchange":"NSE","yf_ticker":"GODREJPROP.NS"},
    {"symbol":"PRESTIGE",   "name":"Prestige Estates",        "exchange":"NSE","yf_ticker":"PRESTIGE.NS"},
    {"symbol":"INDHOTEL",   "name":"Indian Hotels",           "exchange":"NSE","yf_ticker":"INDHOTEL.NS"},
    {"symbol":"ZOMATO",     "name":"Zomato",                  "exchange":"NSE","yf_ticker":"ZOMATO.NS"},
    {"symbol":"NYKAA",      "name":"FSN E-Commerce (Nykaa)",  "exchange":"NSE","yf_ticker":"NYKAA.NS"},
    {"symbol":"IDFCFIRSTB", "name":"IDFC First Bank",         "exchange":"NSE","yf_ticker":"IDFCFIRSTB.NS"},
    {"symbol":"BANDHANBNK", "name":"Bandhan Bank",            "exchange":"NSE","yf_ticker":"BANDHANBNK.NS"},
    {"symbol":"AUBANK",     "name":"AU Small Finance Bank",   "exchange":"NSE","yf_ticker":"AUBANK.NS"},
    {"symbol":"RBLBANK",    "name":"RBL Bank",                "exchange":"NSE","yf_ticker":"RBLBANK.NS"},
    {"symbol":"FEDERALBNK", "name":"Federal Bank",            "exchange":"NSE","yf_ticker":"FEDERALBNK.NS"},
    {"symbol":"KARURVYSYA", "name":"Karur Vysya Bank",        "exchange":"NSE","yf_ticker":"KARURVYSYA.NS"},
    {"symbol":"SCHAEFFLER", "name":"Schaeffler India",        "exchange":"NSE","yf_ticker":"SCHAEFFLER.NS"},
    {"symbol":"BRIGADE",    "name":"Brigade Enterprises",     "exchange":"NSE","yf_ticker":"BRIGADE.NS"},
    {"symbol":"CESC",       "name":"CESC",                    "exchange":"NSE","yf_ticker":"CESC.NS"},
    # Small Cap
    {"symbol":"TANLA",      "name":"Tanla Platforms",         "exchange":"NSE","yf_ticker":"TANLA.NS"},
    {"symbol":"INTELLECT",  "name":"Intellect Design Arena",  "exchange":"NSE","yf_ticker":"INTELLECT.NS"},
    {"symbol":"MASTEK",     "name":"Mastek",                  "exchange":"NSE","yf_ticker":"MASTEK.NS"},
    {"symbol":"ZENSAR",     "name":"Zensar Technologies",     "exchange":"NSE","yf_ticker":"ZENSAR.NS"},
    {"symbol":"BIRLASOFT",  "name":"Birlasoft",               "exchange":"NSE","yf_ticker":"BIRLASOFT.NS"},
    {"symbol":"HAPPSTMNDS", "name":"Happiest Minds",          "exchange":"NSE","yf_ticker":"HAPPSTMNDS.NS"},
    {"symbol":"EQUITASBNK", "name":"Equitas Small Fin Bank",  "exchange":"NSE","yf_ticker":"EQUITASBNK.NS"},
    {"symbol":"DEEPAKNTR",  "name":"Deepak Nitrite",          "exchange":"NSE","yf_ticker":"DEEPAKNTR.NS"},
    {"symbol":"AARTIIND",   "name":"Aarti Industries",        "exchange":"NSE","yf_ticker":"AARTIIND.NS"},
    {"symbol":"VINATIORG",  "name":"Vinati Organics",         "exchange":"NSE","yf_ticker":"VINATIORG.NS"},
    {"symbol":"FLUOROCHEM", "name":"Gujarat Fluorochemicals", "exchange":"NSE","yf_ticker":"FLUOROCHEM.NS"},
    {"symbol":"PIIND",      "name":"PI Industries",           "exchange":"NSE","yf_ticker":"PIIND.NS"},
    {"symbol":"RALLIS",     "name":"Rallis India",            "exchange":"NSE","yf_ticker":"RALLIS.NS"},
    {"symbol":"DHANUKA",    "name":"Dhanuka Agritech",        "exchange":"NSE","yf_ticker":"DHANUKA.NS"},
    {"symbol":"IGL",        "name":"Indraprastha Gas",        "exchange":"NSE","yf_ticker":"IGL.NS"},
    {"symbol":"MGL",        "name":"Mahanagar Gas",           "exchange":"NSE","yf_ticker":"MGL.NS"},
    {"symbol":"CDSL",       "name":"CDSL",                    "exchange":"NSE","yf_ticker":"CDSL.NS"},
    {"symbol":"BSE",        "name":"BSE Limited",             "exchange":"NSE","yf_ticker":"BSE.NS"},
    {"symbol":"MCX",        "name":"MCX India",               "exchange":"NSE","yf_ticker":"MCX.NS"},
    {"symbol":"NUVOCO",     "name":"Nuvoco Vistas",           "exchange":"NSE","yf_ticker":"NUVOCO.NS"},
    {"symbol":"JKCEMENT",   "name":"JK Cement",               "exchange":"NSE","yf_ticker":"JKCEMENT.NS"},
    {"symbol":"RAMCOCEM",   "name":"Ramco Cements",           "exchange":"NSE","yf_ticker":"RAMCOCEM.NS"},
    {"symbol":"SUPRAJIT",   "name":"Suprajit Engineering",    "exchange":"NSE","yf_ticker":"SUPRAJIT.NS"},
    {"symbol":"MINDA",      "name":"Minda Corporation",       "exchange":"NSE","yf_ticker":"MINDA.NS"},
    {"symbol":"LAXMIMACH",  "name":"Lakshmi Machine Works",   "exchange":"NSE","yf_ticker":"LAXMIMACH.NS"},
    {"symbol":"KIRLOSENG",  "name":"Kirloskar Electric",      "exchange":"NSE","yf_ticker":"KIRLOSENG.NS"},
    {"symbol":"ELGIEQUIP",  "name":"Elgi Equipments",         "exchange":"NSE","yf_ticker":"ELGIEQUIP.NS"},
    {"symbol":"KRBL",       "name":"KRBL",                    "exchange":"NSE","yf_ticker":"KRBL.NS"},
    {"symbol":"AVANTIFEED", "name":"Avanti Feeds",            "exchange":"NSE","yf_ticker":"AVANTIFEED.NS"},
    {"symbol":"ABBOTINDIA", "name":"Abbott India",            "exchange":"NSE","yf_ticker":"ABBOTINDIA.NS"},
    {"symbol":"NATCOPHARM", "name":"Natco Pharma",            "exchange":"NSE","yf_ticker":"NATCOPHARM.NS"},
    {"symbol":"GRANULES",   "name":"Granules India",          "exchange":"NSE","yf_ticker":"GRANULES.NS"},
    {"symbol":"WELSPUNLIV", "name":"Welspun Living",          "exchange":"NSE","yf_ticker":"WELSPUNLIV.NS"},
    {"symbol":"TRIDENT",    "name":"Trident",                 "exchange":"NSE","yf_ticker":"TRIDENT.NS"},
    {"symbol":"PCBL",       "name":"PCBL",                    "exchange":"NSE","yf_ticker":"PCBL.NS"},
    {"symbol":"ATUL",       "name":"Atul",                    "exchange":"NSE","yf_ticker":"ATUL.NS"},
    {"symbol":"NOCIL",      "name":"NOCIL",                   "exchange":"NSE","yf_ticker":"NOCIL.NS"},
    {"symbol":"NAVINFLUOR", "name":"Navin Fluorine",          "exchange":"NSE","yf_ticker":"NAVINFLUOR.NS"},
    {"symbol":"SHRIRAMFIN", "name":"Shriram Finance",         "exchange":"NSE","yf_ticker":"SHRIRAMFIN.NS"},
    {"symbol":"IIFL",       "name":"IIFL Finance",            "exchange":"NSE","yf_ticker":"IIFL.NS"},
    {"symbol":"VBL",        "name":"Varun Beverages",         "exchange":"NSE","yf_ticker":"VBL.NS"},
    {"symbol":"DEVYANI",    "name":"Devyani International",   "exchange":"NSE","yf_ticker":"DEVYANI.NS"},
    {"symbol":"WESTLIFE",   "name":"Westlife Foodworld",      "exchange":"NSE","yf_ticker":"WESTLIFE.NS"},
    {"symbol":"KALYANKJIL", "name":"Kalyan Jewellers",        "exchange":"NSE","yf_ticker":"KALYANKJIL.NS"},
    {"symbol":"SENCO",      "name":"Senco Gold",              "exchange":"NSE","yf_ticker":"SENCO.NS"},
    {"symbol":"BIKAJI",     "name":"Bikaji Foods",            "exchange":"NSE","yf_ticker":"BIKAJI.NS"},
    {"symbol":"DODLA",      "name":"Dodla Dairy",             "exchange":"NSE","yf_ticker":"DODLA.NS"},
    {"symbol":"PNBHOUSING", "name":"PNB Housing Finance",     "exchange":"NSE","yf_ticker":"PNBHOUSING.NS"},
    {"symbol":"CANFINHOME", "name":"Can Fin Homes",           "exchange":"NSE","yf_ticker":"CANFINHOME.NS"},
    {"symbol":"AAVAS",      "name":"Aavas Financiers",        "exchange":"NSE","yf_ticker":"AAVAS.NS"},
    {"symbol":"HOMEFIRST",  "name":"Home First Finance",      "exchange":"NSE","yf_ticker":"HOMEFIRST.NS"},
    {"symbol":"TORNTPOWER", "name":"Torrent Power",           "exchange":"NSE","yf_ticker":"TORNTPOWER.NS"},
    {"symbol":"TIINDIA",    "name":"Tube Investments of India","exchange":"NSE","yf_ticker":"TIINDIA.NS"},
    {"symbol":"FINEORG",    "name":"Fine Organic Industries", "exchange":"NSE","yf_ticker":"FINEORG.NS"},
    {"symbol":"CONCOR",     "name":"Container Corp of India", "exchange":"NSE","yf_ticker":"CONCOR.NS"},
    {"symbol":"BLUEDART",   "name":"Blue Dart Express",       "exchange":"NSE","yf_ticker":"BLUEDART.NS"},
    {"symbol":"SUNTV",      "name":"Sun TV Network",          "exchange":"NSE","yf_ticker":"SUNTV.NS"},
    {"symbol":"RVNL",       "name":"Rail Vikas Nigam",        "exchange":"NSE","yf_ticker":"RVNL.NS"},
    {"symbol":"IRFC",       "name":"IRFC",                    "exchange":"NSE","yf_ticker":"IRFC.NS"},
    {"symbol":"HUDCO",      "name":"HUDCO",                   "exchange":"NSE","yf_ticker":"HUDCO.NS"},
    {"symbol":"NBCC",       "name":"NBCC India",              "exchange":"NSE","yf_ticker":"NBCC.NS"},
    {"symbol":"MAZAGON",    "name":"Mazagon Dock",            "exchange":"NSE","yf_ticker":"MAZDOCK.NS"},
    {"symbol":"GRINDWELL",  "name":"Grindwell Norton",        "exchange":"NSE","yf_ticker":"GRINDWELL.NS"},
    {"symbol":"INDIGRID",   "name":"IndiGrid InvIT",          "exchange":"NSE","yf_ticker":"INDIGRID.NS"},
    {"symbol":"GREENPANEL", "name":"Greenpanel Industries",   "exchange":"NSE","yf_ticker":"GREENPANEL.NS"},
    {"symbol":"CENTURYPLY", "name":"Century Plyboards",       "exchange":"NSE","yf_ticker":"CENTURYPLY.NS"},
    {"symbol":"DIXON",      "name":"Dixon Technologies",      "exchange":"NSE","yf_ticker":"DIXON.NS"},
    {"symbol":"AMBER",      "name":"Amber Enterprises",       "exchange":"NSE","yf_ticker":"AMBER.NS"},
    {"symbol":"SUPREMEIND", "name":"Supreme Industries",      "exchange":"NSE","yf_ticker":"SUPREMEIND.NS"},
    {"symbol":"RATNAMANI",  "name":"Ratnamani Metals",        "exchange":"NSE","yf_ticker":"RATNAMANI.NS"},
    {"symbol":"UJJIVAN",    "name":"Ujjivan Financial",       "exchange":"NSE","yf_ticker":"UJJIVANSFB.NS"},
    {"symbol":"CREDITACC",  "name":"CreditAccess Grameen",    "exchange":"NSE","yf_ticker":"CREDITACC.NS"},
    {"symbol":"TATAELXSI",  "name":"Tata Elxsi",             "exchange":"NSE","yf_ticker":"TATAELXSI.NS"},
    {"symbol":"ENDURANCE",  "name":"Endurance Technologies",  "exchange":"NSE","yf_ticker":"ENDURANCE.NS"},
    {"symbol":"GABRIEL",    "name":"Gabriel India",           "exchange":"NSE","yf_ticker":"GABRIEL.NS"},
    {"symbol":"NEWGEN",     "name":"Newgen Software",         "exchange":"NSE","yf_ticker":"NEWGEN.NS"},
    {"symbol":"DATAMATICS", "name":"Datamatics Global",       "exchange":"NSE","yf_ticker":"DATAMATICS.NS"},
    {"symbol":"GALAXYSURF", "name":"Galaxy Surfactants",      "exchange":"NSE","yf_ticker":"GALAXYSURF.NS"},
    {"symbol":"INOXWIND",   "name":"Inox Wind",               "exchange":"NSE","yf_ticker":"INOXWIND.NS"},
    {"symbol":"SUZLON",     "name":"Suzlon Energy",           "exchange":"NSE","yf_ticker":"SUZLON.NS"},
    {"symbol":"TATAPOWER",  "name":"Tata Power",              "exchange":"NSE","yf_ticker":"TATAPOWER.NS"},
    {"symbol":"ADANIGREEN", "name":"Adani Green Energy",      "exchange":"NSE","yf_ticker":"ADANIGREEN.NS"},
    {"symbol":"BIOCON",     "name":"Biocon",                  "exchange":"NSE","yf_ticker":"BIOCON.NS"},
    {"symbol":"GLAND",      "name":"Gland Pharma",            "exchange":"NSE","yf_ticker":"GLAND.NS"},
    {"symbol":"LAURUSLABS", "name":"Laurus Labs",             "exchange":"NSE","yf_ticker":"LAURUSLABS.NS"},
    {"symbol":"AMBUJACEM",  "name":"Ambuja Cements",          "exchange":"NSE","yf_ticker":"AMBUJACEM.NS"},
    {"symbol":"APOLLOTYRE", "name":"Apollo Tyres",            "exchange":"NSE","yf_ticker":"APOLLOTYRE.NS"},
    {"symbol":"NILKAMAL",   "name":"Nilkamal",                "exchange":"NSE","yf_ticker":"NILKAMAL.NS"},
    {"symbol":"EMAMILTD",   "name":"Emami",                   "exchange":"NSE","yf_ticker":"EMAMILTD.NS"},
    {"symbol":"JYOTHY",     "name":"Jyothy Labs",             "exchange":"NSE","yf_ticker":"JYOTHYLAB.NS"},
    {"symbol":"RADICO",     "name":"Radico Khaitan",          "exchange":"NSE","yf_ticker":"RADICO.NS"},
    {"symbol":"SUBROS",     "name":"Subros",                  "exchange":"NSE","yf_ticker":"SUBROS.NS"},
    {"symbol":"ROUTE",      "name":"Route Mobile",            "exchange":"NSE","yf_ticker":"ROUTE.NS"},
    {"symbol":"APLAPOLLO",  "name":"APL Apollo Tubes",        "exchange":"NSE","yf_ticker":"APLAPOLLO.NS"},
    {"symbol":"MHRIL",      "name":"Mahindra Holidays",       "exchange":"NSE","yf_ticker":"MHRIL.NS"},
    {"symbol":"FINOLEX",    "name":"Finolex Industries",      "exchange":"NSE","yf_ticker":"FINPIPE.NS"},
    {"symbol":"BERGEPAINT", "name":"Berger Paints",           "exchange":"NSE","yf_ticker":"BERGEPAINT.NS"},
    {"symbol":"KANSAINER",  "name":"Kansai Nerolac",          "exchange":"NSE","yf_ticker":"KANSAINER.NS"},
    {"symbol":"AKZOINDIA",  "name":"Akzo Nobel India",        "exchange":"NSE","yf_ticker":"AKZOINDIA.NS"},
    {"symbol":"INDIGOPNTS", "name":"Indigo Paints",           "exchange":"NSE","yf_ticker":"INDIGOPNTS.NS"},
    {"symbol":"MCDOWELL-N", "name":"United Spirits",          "exchange":"NSE","yf_ticker":"MCDOWELL-N.NS"},
]


# ═══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════

def get_all_stocks(force_refresh: bool = False) -> list[dict]:
    """
    Returns list of stock dicts: {symbol, name, exchange, yf_ticker}
    Tries NSE & BSE APIs, caches for 24 hours, falls back to built-in list.
    """
    if not force_refresh:
        cached = _load(_UNIVERSE_CACHE)
        if cached and _fresh(cached.get("ts"), hours=24):
            return cached["stocks"]

    stocks = _fetch_nse() + _fetch_sme() + _fetch_bse()

    if len(stocks) < 200:
        stocks = _FALLBACK

    # Deduplicate by yf_ticker
    seen = set()
    unique = []
    for s in stocks:
        k = s.get("yf_ticker","")
        if k and k not in seen:
            seen.add(k)
            unique.append(s)

    _save(_UNIVERSE_CACHE, {"ts": _now(), "stocks": unique})
    return unique


def get_stock_count() -> int:
    return len(get_all_stocks())


def get_bulk_prices(stock_dicts: list[dict], force: bool = False) -> dict:
    """
    ★ SPEED TRICK — fetches ALL prices in 4 HTTP requests (not 2000).
    Returns {yf_ticker: float_price}

    Usage:
        prices = get_bulk_prices(ALL_STOCKS_DATA)
        cheap  = [s for s in ALL_STOCKS_DATA if 10 <= prices.get(s["yf_ticker"], 0) <= 5000]
    """
    cached = _load(_PRICE_CACHE)
    if not force and cached and _fresh(cached.get("ts"), minutes=30):
        return cached.get("prices", {})

    tickers = [s["yf_ticker"] for s in stock_dicts]
    prices  = {}
    BATCH   = 500  # yfinance handles ~500 per call reliably

    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        try:
            raw = yf.download(
                batch, period="2d", interval="1d",
                progress=False, auto_adjust=True,
                group_by="ticker", threads=True,
            )
            if len(batch) == 1:
                try:
                    prices[batch[0]] = float(raw["Close"].dropna().iloc[-1])
                except Exception:
                    pass
            else:
                for t in batch:
                    try:
                        prices[t] = float(raw[t]["Close"].dropna().iloc[-1])
                    except Exception:
                        pass
        except Exception:
            pass

    if prices:
        _save(_PRICE_CACHE, {"ts": _now(), "prices": prices})
    return prices


def download_batch(
    stock_dicts: list[dict],
    period: str = "6mo",
    interval: str = "1d",
) -> dict:
    """
    ★ SPEED TRICK — downloads OHLCV for N stocks in ONE HTTP request.

    Old code (inside ThreadPoolExecutor):
        yf.download("RELIANCE.NS")   # 1 request
        yf.download("TCS.NS")        # 1 request  ...× 2000 = slow

    New code:
        download_batch(batch_of_50)  # 1 request for all 50

    Returns {yf_ticker: DataFrame}
    Use in batches of 40-60 for best reliability.
    """
    if not stock_dicts:
        return {}

    tickers = [s["yf_ticker"] for s in stock_dicts]
    result  = {}

    try:
        raw = yf.download(
            tickers, period=period, interval=interval,
            progress=False, auto_adjust=True,
            group_by="ticker", threads=True,
        )

        if len(tickers) == 1:
            if not raw.empty:
                # Normalize columns
                df = raw.copy()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = [c.capitalize() for c in df.columns]
                result[tickers[0]] = df

        else:
            for t in tickers:
                try:
                    sub = raw[t].copy()
                    sub = sub.dropna(how="all")
                    if len(sub) < 30:
                        continue
                    if isinstance(sub.columns, pd.MultiIndex):
                        sub.columns = sub.columns.get_level_values(0)
                    sub.columns = [c.capitalize() for c in sub.columns]
                    result[t] = sub
                except Exception:
                    pass

    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════

_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def _fetch_nse() -> list[dict]:
    try:
        r = requests.get(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            headers=_HDR, timeout=20,
        )
        if r.status_code == 200:
            from io import StringIO
            df  = pd.read_csv(StringIO(r.text))
            col = next((c for c in df.columns if "SYMBOL" in c.upper()), None)
            if col:
                return [
                    {"symbol": s.strip(), "name": s.strip(),
                     "exchange": "NSE", "yf_ticker": f"{s.strip()}.NS"}
                    for s in df[col].dropna() if str(s).strip()
                ]
    except Exception:
        pass
    return []

def _fetch_sme() -> list[dict]:
    try:
        r = requests.get(
            "https://archives.nseindia.com/content/equities/EMERGE_EQUITY_L.csv",
            headers=_HDR, timeout=20,
        )
        if r.status_code == 200:
            from io import StringIO
            df  = pd.read_csv(StringIO(r.text))
            col = next((c for c in df.columns if "SYMBOL" in c.upper()), None)
            if col:
                return [
                    {"symbol": s.strip(), "name": s.strip(),
                     "exchange": "NSE-SME", "yf_ticker": f"{s.strip()}.NS"}
                    for s in df[col].dropna() if str(s).strip()
                ]
    except Exception:
        pass
    return []

def _fetch_bse() -> list[dict]:
    try:
        r = requests.get(
            "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
            "?Group=&Scripcode=&industry=&segment=Equity&status=Active",
            headers=_HDR, timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return [
                    {"symbol": str(item.get("scrip_cd","")),
                     "name":   item.get("short_name", str(item.get("scrip_cd",""))),
                     "exchange": "BSE",
                     "yf_ticker": f"{item.get('scrip_cd','')}.BO"}
                    for item in data if item.get("scrip_cd")
                ]
    except Exception:
        pass
    return []

def _fresh(ts: str | None, hours: int = 0, minutes: int = 0) -> bool:
    if not ts:
        return False
    try:
        return (datetime.now() - datetime.fromisoformat(ts)) < timedelta(hours=hours, minutes=minutes)
    except Exception:
        return False

def _now()  -> str:  return datetime.now().isoformat()

def _load(p: str):
    try:
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _save(p: str, d: dict):
    try:
        with open(p, "w") as f:
            json.dump(d, f)
    except Exception:
        pass
