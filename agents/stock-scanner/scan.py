import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime

tickers = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "AVGO",
    "COST", "ORCL", "CRM", "ADBE", "PYPL", "INTC", "QCOM", "TXN", "AMAT", "MU",
    "IBM", "GS", "JPM", "BAC", "WFC", "V", "MA", "DIS", "KO", "PEP"
]

def get_price_col(df, name):
    """Extract price column from yfinance multi-index df"""
    if isinstance(df.columns, pd.MultiIndex):
        return df[name].squeeze()
    return df[name]

def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def macd_bull_cross(macd, signal):
    """Check if MACD crossed above signal in last 5 days"""
    for i in range(-5, 0):
        if i < -len(macd) or i-1 < -len(macd):
            continue
        if macd.iloc[i] > signal.iloc[i] and macd.iloc[i-1] <= signal.iloc[i-1]:
            return True
    return False

results = []

print("Fetching SPY data...")
spy = yf.download("SPY", period="3mo", interval="1d", progress=False)
spy_close = get_price_col(spy, 'Close')
spy_20d_pct = (spy_close.iloc[-1] / spy_close.iloc[-21] - 1) * 100 if len(spy_close) > 21 else 0
spy_60d_pct = (spy_close.iloc[-1] / spy_close.iloc[-61] - 1) * 100 if len(spy_close) > 61 else 0

print(f"SPY 20d change: {spy_20d_pct:.2f}%, SPY 60d change: {spy_60d_pct:.2f}%")
print("Scanning stocks...\n")

for ticker in tickers:
    try:
        data = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if len(data) < 30:
            print(f"  {ticker}: insufficient data")
            continue

        close = get_price_col(data, 'Close')
        volume = get_price_col(data, 'Volume')

        # RSI
        rsi = calc_rsi(close, 14)
        rsi_val = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else None

        # Volume ratio
        vol_avg20 = volume.rolling(20, min_periods=20).mean()
        vol_ratio = float(volume.iloc[-1]) / float(vol_avg20.iloc[-1]) if float(vol_avg20.iloc[-1]) > 0 else 0

        # MACD bull cross
        macd_line, signal_line = calc_macd(close)
        bull_cross = macd_bull_cross(macd_line, signal_line)

        # Relative strength vs SPY
        if len(close) > 21:
            stock_20d_pct = (float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100
        else:
            stock_20d_pct = 0
        if len(close) > 61:
            stock_60d_pct = (float(close.iloc[-1]) / float(close.iloc[-61]) - 1) * 100
        else:
            stock_60d_pct = stock_20d_pct

        rs_20d = (stock_20d_pct / spy_20d_pct) if spy_20d_pct != 0 else 0
        rs_60d = (stock_60d_pct / spy_60d_pct) if spy_60d_pct != 0 else 0

        price = float(close.iloc[-1])

        results.append({
            'ticker': ticker,
            'price': price,
            'rsi': rsi_val,
            'vol_ratio': vol_ratio,
            'rs_20d': rs_20d,
            'rs_60d': rs_60d,
            'stock_20d_pct': stock_20d_pct,
            'stock_60d_pct': stock_60d_pct,
            'macd_cross': bull_cross,
        })
        print(f"  {ticker}: price=${price:.2f}, rsi={rsi_val:.1f}, vol_ratio={vol_ratio:.2f}, rs_20d={rs_20d:.2f}, macd_cross={bull_cross}")
    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")

# Score stocks
scored = []
for r in results:
    score = 0
    if r['rsi'] and 40 <= r['rsi'] <= 70:
        score += (r['rsi'] - 40) / 30 * 30  # 0-30 points for RSI in range
    if r['vol_ratio'] >= 1.2:
        score += min(r['vol_ratio'] - 1.0, 1.0) * 25  # 0-25 points for volume
    rs_avg = (r['rs_20d'] + r['rs_60d']) / 2
    if rs_avg > 0:
        score += min((rs_avg - 1.0) * 15, 30)  # up to 30 points for RS vs SPY
    if r['macd_cross']:
        score += 15  # bonus for MACD bull cross
    r['score'] = score
    scored.append(r)

scored.sort(key=lambda x: x['score'], reverse=True)

print("\n=== TOP 5 ===")
for i, r in enumerate(scored[:5]):
    rs_avg = ((r['rs_20d'] + r['rs_60d']) / 2 - 1) * 100
    print(f"{i+1}. {r['ticker']} | Price: ${r['price']:.2f} | RSI: {r['rsi']:.1f} | RS vs SPY: +{rs_avg:.1f}% | Score: {r['score']:.1f} | MACD: {r['macd_cross']}")

# Write report
report_lines = []
report_lines.append("TOP 5 BULLISH SIGNALS - 2026-04-03 10:30 CDT\n")
for i, r in enumerate(scored[:5]):
    rs_avg = ((r['rs_20d'] + r['rs_60d']) / 2 - 1) * 100
    reason = f"MACD bull cross + RSI {r['rsi']:.0f} + volume {r['vol_ratio']:.1f}x"
    report_lines.append(f"{i+1}. {r['ticker']} | Price: ${r['price']:.2f} | RSI: {r['rsi']:.1f} | RS vs SPY: +{rs_avg:.1f}%")
    report_lines.append(f"   {reason}\n")

report_lines.append(f"""
Full scan details:
SPY 20d change: {spy_20d_pct:.2f}%
SPY 60d change: {spy_60d_pct:.2f}%

All results (sorted by score):
""")
for r in scored:
    rs_avg = ((r['rs_20d'] + r['rs_60d']) / 2 - 1) * 100
    rsi_str = f"{r['rsi']:.1f}" if r['rsi'] else "N/A"
    report_lines.append(f"  {r['ticker']:6s} | ${r['price']:8.2f} | RSI: {rsi_str:>5s} | Vol: {r['vol_ratio']:.2f}x | RS: {rs_avg:+6.1f}% | MACD: {r['macd_cross']} | Score: {r['score']:.1f}")

report = "\n".join(report_lines)
with open("/home/colton/.openclaw/workspace/agents/stock-scanner/scans/20260403_1030.txt", "w") as f:
    f.write(report)

print("\nReport saved to /home/colton/.openclaw/workspace/agents/stock-scanner/scans/20260403_1030.txt")
