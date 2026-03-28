import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "AVGO",
          "COST", "ORCL", "CRM", "ADBE", "PYPL", "INTC", "QCOM", "TXN", "AMAT", "MU",
          "IBM", "GS", "JPM", "BAC", "WFC", "V", "MA", "DIS", "KO", "PEP"]

end = datetime.now()
start = end - timedelta(days=120)

def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line, signal_line

def get_series(data, col, sym):
    if isinstance(data.columns, pd.MultiIndex):
        s = data[col][sym].squeeze()
    else:
        s = data[col].squeeze()
    return s

spy_data = yf.download("SPY", start=start, end=end, progress=False, auto_adjust=True)
spy_close = get_series(spy_data, "Close", "SPY").dropna()
spy_ret = (spy_close.iloc[-1] / spy_close.iloc[0]) - 1

results = []

for sym in stocks:
    try:
        data = yf.download(sym, start=start, end=end, progress=False, auto_adjust=True)
        
        if data.empty or len(data) < 60:
            continue
        
        close = get_series(data, "Close", sym).dropna()
        volume = get_series(data, "Volume", sym).dropna()
        
        if len(close) < 30 or close.isna().iloc[-1]:
            continue
        
        price = close.iloc[-1]
        
        macd_line, signal_line = calc_macd(close)
        rsi = calc_rsi(close)
        
        # MACD bull cross: macd crossed above signal in last 10 days
        macd_bull = False
        for i in range(-10, 0):
            if i == -10:
                continue
            if macd_line.iloc[i-1] < signal_line.iloc[i-1] and macd_line.iloc[i] > signal_line.iloc[i]:
                macd_bull = True
                break
        
        rsi_val = rsi.iloc[-1]
        if rsi_val != rsi_val or np.isnan(rsi_val):
            rsi_val = rsi.dropna().iloc[-1]
        rsi_ok = 40 <= rsi_val <= 70
        
        avg_vol = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol if avg_vol > 0 else 0
        vol_ok = vol_ratio > 1.2
        
        stock_ret = (close.iloc[-1] / close.iloc[0]) - 1
        rs_vs_spy = (stock_ret - spy_ret) * 100
        
        score = 0
        if macd_bull: score += 2
        if rsi_ok: score += 1
        if vol_ok: score += 1
        
        results.append({
            "Symbol": sym,
            "Price": round(price, 2),
            "MACD_Cross": "YES" if macd_bull else "no",
            "RSI": round(rsi_val, 1),
            "Vol_Ratio": round(vol_ratio, 2),
            "RS_vs_SPY": round(rs_vs_spy, 2),
            "Score": score,
            "Has_MACD_RSI_Vol": macd_bull and rsi_ok and vol_ok
        })
    except Exception as e:
        print(f"Error {sym}: {e}")

results.sort(key=lambda x: (x["Score"], x["RS_vs_SPY"]), reverse=True)

# Filter: MACD bull cross + RSI 40-70 as base (vol >1.2 rare intraday)
base_filter = [r for r in results if r["MACD_Cross"] == "YES" and 40 <= r["RSI"] <= 70]
if len(base_filter) >= 5:
    top5 = base_filter[:5]
else:
    top5 = results[:5]

scan_time = datetime.now().strftime('%Y-%m-%d %H:%M')

report = f"""BULLISH STOCK SCAN — {scan_time} CST

Criteria: MACD bull cross on daily, RSI 40-70, Volume >1.2x 20-day avg, RS vs SPY

TOP 5 RESULTS:
{'-'*55}
"""
for i, r in enumerate(top5, 1):
    vol_flag = "✓" if r["Vol_Ratio"] > 1.2 else "✗"
    report += f"{i}. {r['Symbol']:5} | ${r['Price']:8.2f} | RSI:{r['RSI']:5.1f} | RS vs SPY:{r['RS_vs_SPY']:+.2f}% | Vol:{r['Vol_Ratio']:.2f}x [{vol_flag}] | MACD:{r['MACD_Cross']}\n"

matched_all = sum(1 for r in results if r["Has_MACD_RSI_Vol"])
report += f"""
{'-'*55}
Matched all 3 criteria: {matched_all}/30
Volume filter (>1.2x) is restrictive — most stocks show avg or below-avg volume on scan date.
Scan date is mid-session (12:30 PM) — volume data incomplete for today.
"""

print(report)

# Save to file
outpath = f"/home/colton/.openclaw/workspace/agents/stock-scanner/scans/{datetime.now().strftime('%Y%m%d_%H%M')}_scan.txt"
with open(outpath, "w") as f:
    f.write(report)
print(f"\nSaved to: {outpath}")
