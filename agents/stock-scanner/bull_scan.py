import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "AVGO",
           "COST", "ORCL", "CRM", "ADBE", "PYPL", "INTC", "QCOM", "TXN", "AMAT", "MU",
           "IBM", "GS", "JPM", "BAC", "WFC", "V", "MA", "DIS", "KO", "PEP", "SPY"]

results = []

for ticker in tickers:
    try:
        data = yf.download(ticker, period="3mo", interval="1d", auto_adjust=True, progress=False)
        if len(data) < 60:
            continue
        
        close = data['Close'].squeeze()
        volume = data['Volume'].squeeze()
        
        # SMA
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        
        # RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        macd_bull_cross = (macd.iloc[-2] < signal.iloc[-2]) and (macd.iloc[-1] > signal.iloc[-1])
        
        # Volume
        vol_avg = volume.rolling(20).mean().iloc[-1]
        vol_today = volume.iloc[-1]
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 0
        
        # RS vs SPY (need SPY data)
        results.append({
            'ticker': ticker,
            'price': close.iloc[-1],
            'rsi': rsi_val,
            'macd_cross': macd_bull_cross,
            'vol_ratio': vol_ratio,
            'close': close
        })
    except Exception as e:
        pass

# Get SPY for RS calculation
spy = yf.download("SPY", period="3mo", interval="1d", auto_adjust=True, progress=False)
spy_close = spy['Close'].squeeze()
spy_sma20 = spy_close.rolling(20).mean()
spy_rsi_vals = []
for r in results:
    if len(r['close']) >= 20 and len(spy_close) >= 20:
        stock_sma20 = r['close'].rolling(20).mean().iloc[-1]
        spy_sma20_val = spy_sma20.iloc[-1]
        rs_pct = ((r['price'] / r['close'].rolling(20).mean().iloc[-1]) / (spy_close.iloc[-1] / spy_sma20_val)) * 100 - 100
        rsi_vals = r['rsi']
        spy_rsi_vals.append(rs_pct)
    else:
        spy_rsi_vals.append(np.nan)

output = []
for i, r in enumerate(results):
    if pd.isna(r['rsi']) or pd.isna(spy_rsi_vals[i]):
        continue
    # Filters: RSI 40-70, volume >1.2x, MACD bull cross
    if 40 <= r['rsi'] <= 70 and r['vol_ratio'] > 1.2 and r['macd_cross']:
        output.append({
            'Symbol': r['ticker'],
            'Price': round(r['price'], 2),
            'RSI': round(r['rsi'], 1),
            'RS_vs_SPY': round(spy_rsi_vals[i], 2),
            'Vol_x': round(r['vol_ratio'], 2)
        })

output.sort(key=lambda x: x['RS_vs_SPY'], reverse=True)
top5 = output[:5]

print("TOP 5 BULLISH SCAN -", datetime.now().strftime("%Y-%m-%d %H:%M"))
print("="*50)
if top5:
    print(f"{'Symbol':<8} {'Price':>10} {'RSI':>8} {'RS vs SPY %':>14} {'Vol x':>8}")
    print("-"*50)
    for t in top5:
        print(f"{t['Symbol']:<8} ${t['Price']:>9.2f} {t['RSI']:>8.1f} {t['RS_vs_SPY']:>+14.2f} {t['Vol_x']:>8.2f}")
else:
    print("No stocks meeting all criteria.")
print("="*50)
print("Criteria: RSI 40-70, Vol>1.2x avg, MACD bull cross")
