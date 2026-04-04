#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# Stock list
stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD', 'NFLX', 'AVGO',
          'COST', 'ORCL', 'CRM', 'ADBE', 'PYPL', 'INTC', 'QCOM', 'TXN', 'AMAT', 'MU',
          'IBM', 'GS', 'JPM', 'BAC', 'WFC', 'V', 'MA', 'DIS', 'KO', 'PEP']

# Fetch SPY for relative strength calculation
print("Fetching SPY data...")
spy_df = yf.download('SPY', period='3mo', progress=False)
spy = spy_df['Close']['SPY'] if ('Close', 'SPY') in spy_df.columns else spy_df['Close'].iloc[:, 0]
spy_returns = float(spy.pct_change(20).dropna().iloc[-1]) if len(spy) > 20 else 0

results = []

print(f"SPY 20-day return: {spy_returns*100:.2f}%\n")
print("Scanning stocks...")

for symbol in stocks:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3mo')
        
        if len(hist) < 26:
            continue
            
        close = hist['Close']
        volume = hist['Volume']
        
        # Current price
        price = close.iloc[-1]
        
        # RSI(14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_current = float(rsi.iloc[-1])
        
        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        # MACD bull cross: MACD crosses above signal in last 5 days
        macd_bull_cross = False
        for i in range(-4, 0):
            if macd.iloc[i] > signal.iloc[i] and macd.iloc[i-1] <= signal.iloc[i-1]:
                macd_bull_cross = True
                break
        
        # Volume ratio
        vol_avg20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio = float(volume.iloc[-1] / vol_avg20) if vol_avg20 > 0 else 0
        
        # 20-day return
        ret_20d = float((close.iloc[-1] / close.iloc[-20] - 1)) if len(close) >= 20 else 0
        
        # Relative strength vs SPY (ratio of returns)
        rs_vs_spy = float(ret_20d / spy_returns) if spy_returns != 0 else 0
        
        # Store result
        results.append({
            'symbol': symbol,
            'price': float(price),
            'rsi': rsi_current,
            'macd_bull_cross': macd_bull_cross,
            'vol_ratio': vol_ratio,
            'ret_20d': ret_20d * 100,
            'rs_vs_spy': rs_vs_spy,
        })
        
    except Exception as e:
        print(f"Error with {symbol}: {e}")

# Convert to DataFrame
df = pd.DataFrame(results)

# Calculate a composite bullish score (higher = more bullish)
# Weight: MACD cross (+30), RSI in 40-70 range (+20), volume spike (+25), RS vs SPY (+25)
df['macd_score'] = df['macd_bull_cross'].astype(int) * 30
df['rsi_score'] = df.apply(lambda x: 20 if 40 <= x['rsi'] <= 70 else (10 if 30 <= x['rsi'] < 40 or 70 < x['rsi'] <= 80 else 0), axis=1)
df['vol_score'] = df['vol_ratio'].apply(lambda x: min(x / 1.2, 1.5) * 25 if x > 1.2 else x * 25)
df['rs_score'] = df['rs_vs_spy'].clip(lower=0).rank(pct=True) * 25

df['total_score'] = df['macd_score'] + df['rsi_score'] + df['vol_score'] + df['rs_score']

# Sort by total score
df_sorted = df.sort_values('total_score', ascending=False)

# Filter: MACD bull cross, RSI 40-70, Volume > 1.2x
bullish = df[
    (df['macd_bull_cross'] == True) & 
    (df['rsi'] >= 40) & (df['rsi'] <= 70) &
    (df['vol_ratio'] > 1.2)
].copy()

if len(bullish) == 0:
    print("NOTE: No stocks meet ALL criteria (MACD bull cross + RSI 40-70 + Vol >1.2x)")
    print("Showing top 5 by composite bullish score instead:\n")
    top5 = df_sorted.head(5)
else:
    bullish['score'] = (70 - bullish['rsi']) * 0.3 + bullish['vol_ratio'] * 10 + bullish['rs_vs_spy'] * 20
    bullish = bullish.sort_values('score', ascending=False)
    top5 = bullish.head(5)

print(f"\n=== TOP 5 BULLISH STOCKS ===\n")
for i, row in top5.iterrows():
    criteria = []
    if row['macd_bull_cross']: criteria.append("MACD")
    if 40 <= row['rsi'] <= 70: criteria.append(f"RSI={row['rsi']:.0f}")
    if row['vol_ratio'] > 1.2: criteria.append(f"Vol={row['vol_ratio']:.2f}x")
    print(f"{row['symbol']}: Price=${row['price']:.2f}, RSI={row['rsi']:.1f}, RS vs SPY={row['rs_vs_spy']:.2f}x")
    print(f"   20d Return={row['ret_20d']:.1f}%, Vol Ratio={row['vol_ratio']:.2f}x, MACD Bull Cross={'Yes' if row['macd_bull_cross'] else 'No'}")
    print(f"   Criteria met: {', '.join(criteria) if criteria else 'Best available match'}\n")

# Save full results
today_str = datetime.now().strftime('%Y%m%d')
output_path = f'/home/colton/.openclaw/workspace/agents/stock-scanner/scans/{today_str}_full_scan.txt'

with open(output_path, 'w') as f:
    f.write(f"BULLISH STOCK SCAN RESULTS\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"SPY 20-day return: {spy_returns*100:.2f}%\n\n")
    
    f.write("=== ALL SCANNED STOCKS (sorted by score) ===\n")
    f.write(df_sorted[['symbol','price','rsi','macd_bull_cross','vol_ratio','ret_20d','rs_vs_spy','total_score']].to_string(index=False))
    f.write("\n\n")
    
    f.write("=== TOP 5 BULLISH STOCKS ===\n")
    for i, row in top5.iterrows():
        f.write(f"{row['symbol']}: Price=${row['price']:.2f}, RSI={row['rsi']:.1f}, RS vs SPY={row['rs_vs_spy']:.2f}x\n")
        f.write(f"   20d Return={row['ret_20d']:.1f}%, Vol Ratio={row['vol_ratio']:.2f}x, MACD Bull Cross={'Yes' if row['macd_bull_cross'] else 'No'}\n\n")

print(f"Full results saved to: {output_path}")
