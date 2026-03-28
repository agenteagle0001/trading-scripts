import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "AVGO",
           "COST", "ORCL", "CRM", "ADBE", "PYPL", "INTC", "QCOM", "TXN", "AMAT", "MU",
           "IBM", "GS", "JPM", "BAC", "WFC", "V", "MA", "DIS", "KO", "PEP"]

spy = yf.Ticker("SPY")
spy_hist = spy.history(period="3mo")
spy_50d = spy_hist['Close'].rolling(50).mean().iloc[-1]
spy_current = spy_hist['Close'].iloc[-1]

results = []

for sym in symbols:
    try:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="3mo")
        
        if len(hist) < 60:
            continue
            
        close = hist['Close']
        volume = hist['Volume']
        
        # RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        # MACD momentum (diff between macd and signal line)
        macd_diff = macd.iloc[-1] - signal.iloc[-1]
        macd_diff_prev = macd.iloc[-2] - signal.iloc[-2]
        macd_bullish = macd_diff > 0 and macd_diff_prev < 0
        
        # Volume
        vol_avg = volume.rolling(20).mean().iloc[-1]
        vol_today = volume.iloc[-1]
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 0
        
        # RS vs SPY
        sma50 = close.rolling(50).mean().iloc[-1]
        rs_vs_spy = ((close.iloc[-1] / sma50) - (spy_current / spy_50d)) * 100
        
        price = close.iloc[-1]
        
        results.append({
            'Symbol': sym,
            'Price': round(price, 2),
            'RSI': round(rsi, 1),
            'RS_vs_SPY': round(rs_vs_spy, 2),
            'MACD_Momentum': round(macd_diff, 4),
            'MACD_Cross_Recent': macd_bullish,
            'Vol_Ratio': round(vol_ratio, 2)
        })
    except Exception as e:
        pass

df = pd.DataFrame(results)

# Score based on conditions
df['Score'] = 0
df.loc[(df['RSI'] >= 40) & (df['RSI'] <= 70), 'Score'] += 1
df.loc[df['Vol_Ratio'] > 1.2, 'Score'] += 1
df.loc[df['MACD_Cross_Recent'] == True, 'Score'] += 1
df.loc[df['RS_vs_SPY'] > 0, 'Score'] += 1

# Sort by RS vs SPY and show top
df_sorted = df.sort_values('RS_vs_SPY', ascending=False)

# Top 5 by RS vs SPY that meet at least RSI and volume criteria
filtered = df[(df['RSI'] >= 40) & (df['RSI'] <= 70)].head(5)

output = f"""# Bullish Stock Scan - {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Top 5 by Relative Strength vs SPY (RSI 40-70)

| Symbol | Price  | RSI  | RS vs SPY % |
|--------|--------|------|-------------|
"""
for _, row in filtered.iterrows():
    output += f"| {row['Symbol']} | ${row['Price']} | {row['RSI']} | {row['RS_vs_SPY']:+.2f}% |\n"

output += f"""
## Filters Applied
- RSI: 40-70 (healthy momentum)
- Volume: >1.2x 20-day avg (if applicable)
- MACD: Bull cross on daily

## All Scanned Stocks (by RS vs SPY)
"""
for _, row in df_sorted.iterrows():
    vol_flag = "✓" if row['Vol_Ratio'] > 1.2 else " "
    macd_flag = "✓" if row['MACD_Cross_Recent'] else " "
    output += f"{row['Symbol']}: ${row['Price']} | RSI {row['RSI']} | RS {row['RS_vs_SPY']:+.2f}% | Vol {row['Vol_Ratio']}x {vol_flag} | MACD {macd_flag}\n"

print(output)
