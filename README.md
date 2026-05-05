# 🇮🇳 India Stock Screener Hub

4 free swing trading screeners for NSE stocks. Live data. No coding needed to use.

## The 4 Screeners

| Screener | Strategy | Best for |
|---|---|---|
| Swing Screener | Pullback + Breakout | 1–4 week holds |
| Momentum Screener | 52-week high breakouts | 2–6 week holds |
| RSI Reversal | Buy oversold bounces | 1–3 week holds |
| Trend Strength | ADX trend following | 3–8 week holds |

## How to run on your laptop

1. Install Python from python.org
2. Open terminal/command prompt in this folder
3. Type: `pip install -r requirements.txt`
4. Type: `streamlit run Home.py`
5. Browser opens automatically

## How to deploy FREE on Streamlit Cloud (access from phone anywhere)

1. Upload all these files to a GitHub repo (see steps below)
2. Go to share.streamlit.io
3. Sign in with GitHub
4. Click New App
5. Select your repo
6. Set main file to: `Home.py`
7. Click Deploy
8. Save the link on your phone

## Files in this folder

```
Home.py                        ← Main homepage (run this)
requirements.txt               ← Libraries needed
pages/
  1_Swing_Screener.py          ← Swing trading screener
  2_Momentum_Screener.py       ← 52W high momentum screener  
  3_RSI_Reversal.py            ← RSI dip buying screener
  4_Volume_Surge.py            ← Volume surge / smart money screener
  5_Trend_Strength.py          ← ADX trend strength screener
```

## Rules to follow (most important)

- Only trade BUY signals — never SKIP
- Always use the stop loss shown — no exceptions
- Never risk more than 2% per trade
- Maximum 3-4 open trades at a time
- Run screeners on Sunday evening to plan the week

## Disclaimer

Educational purpose only. Not SEBI-registered financial advice.
Always verify signals on TradingView or Zerodha Kite before placing real orders.
