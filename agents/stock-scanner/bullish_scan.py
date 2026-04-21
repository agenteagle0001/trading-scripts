#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

now = datetime.now()
date_str = now.strftime("%Y-%m-%d %H:%M")
date_file = now.strftime("%Y%m%d_%H%M")

symbols = [
    # Original 30
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD', 'NFLX', 'AVGO',
    'COST', 'ORCL', 'CRM', 'ADBE', 'PYPL', 'INTC', 'QCOM', 'TXN', 'AMAT', 'MU',
    'IBM', 'GS', 'JPM', 'BAC', 'WFC', 'V', 'MA', 'DIS', 'KO', 'PEP',
    # Tech/semi momentum (top 5)
    'SOXX', 'PLTR', 'CRWD', 'PANW', 'SNOW',
    # Consumer/retail (top 5)
    'WMT', 'LOW', 'HD', 'SBUX', 'MAR',
    # Financials (top 5)
    'SCHW', 'BLK', 'MSCI', 'SPGI', 'COIN',
    # Energy/industrials (top 5)
    'XOM', 'CAT', 'DE', 'HON', 'RTX',
]

# Get SPY data for relative strength
spy_df = yf.download('SPY', period='3mo', progress=False)
spy = spy_df['Close'].squeeze()
spy_30d_avg = spy.tail(30).mean()

results = []

for sym in symbols:
    try:
        df = yf.download(sym, period='3mo', progress=False)
        
        if df.empty or len(df) < 50:
            continue
        
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        
        # Calculate RSI (14 period)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_current = rsi.iloc[-1]
        
        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        # MACD bull cross: MACD crossed above signal in last 5 days
        macd_bull_cross = False
        for i in range(-5, 0):
            if macd.iloc[i] > signal.iloc[i] and macd.iloc[i-1] <= signal.iloc[i-1]:
                macd_bull_cross = True
                break
        
        # RSI 40-70
        rsi_ok = 40 <= rsi_current <= 70
        
        # Today's volume vs 20-day avg
        vol_avg = volume.tail(20).mean()
        vol_today = volume.iloc[-1]
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 0
        
        # RS vs SPY (percent difference from 30d avg)
        sym_30d_avg = close.tail(30).mean()
        sym_vs_spy = ((sym_30d_avg / spy_30d_avg) * 100) - 100
        
        # Current price
        price = close.iloc[-1]
        
        if macd_bull_cross and rsi_ok:
            results.append({
                'Symbol': sym,
                'Price': round(float(price), 2),
                'RSI': round(float(rsi_current), 1),
                'RS_vs_SPY_pct': round(float(sym_vs_spy), 1),
                'Vol_Ratio': round(float(vol_ratio), 2)
            })
            
    except Exception as e:
        print(f"Error with {sym}: {e}")
        continue

# Sort by RS vs SPY
results.sort(key=lambda x: x['RS_vs_SPY_pct'], reverse=True)
top5 = results[:5]

output = []
output.append("TOP 5 BULLISH SIGNALS")
output.append("=" * 50)
output.append(f"{'Symbol':<8} {'Price':>10} {'RSI':>8} {'RS vs SPY %':>12}")
output.append("-" * 50)
for r in top5:
    output.append(f"{r['Symbol']:<8} ${r['Price']:>9.2f} {r['RSI']:>8.1f} {r['RS_vs_SPY_pct']:>+11.1f}%")

output.append("")
output.append(f"Filters: MACD bull cross (5d), RSI 40-70")
output.append(f"Scan time: {date_str} CST")
output.append(f"Total matches: {len(results)}")

print("\n".join(output))

# Save to file with dynamic path
output_path = f'/home/colton/.openclaw/workspace/agents/stock-scanner/scans/{date_file}_bullish.txt'
with open(output_path, 'w') as f:
    f.write("\n".join(output))

print(f"\nSaved to {output_path}")
