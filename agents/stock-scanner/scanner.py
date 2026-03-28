#!/usr/bin/env python3
"""
Bullish Stock Scanner
Criteria:
- MACD bull cross on daily (MACD line crosses above signal line)
- RSI between 40-70
- Volume > 1.2x 20-day average
- Relative strength vs SPY
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Stock list
STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD', 'NFLX', 'AVGO', 
          'COST', 'ORCL', 'CRM', 'ADBE', 'PYPL', 'INTC', 'QCOM', 'TXN', 'AMAT', 'MU', 
          'IBM', 'GS', 'JPM', 'BAC', 'WFC', 'V', 'MA', 'DIS', 'KO', 'PEP']

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD and signal line"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    return macd_line, signal_line

def check_macd_bull_cross(macd, signal):
    """Check if MACD had a bull cross recently (yesterday or today)"""
    if len(macd) < 2:
        return False, 0
    
    # Yesterday: MACD below signal
    # Today: MACD above signal
    yesterday = macd.iloc[-2] < signal.iloc[-2]
    today = macd.iloc[-1] > signal.iloc[-1]
    
    # Also check for recent bullish momentum
    macd_change = macd.iloc[-1] - macd.iloc[-2]
    
    return yesterday and today, macd_change

def get_stock_data(ticker, period='3mo'):
    """Get stock data"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def scan_stock(ticker):
    """Scan a single stock for bullish criteria"""
    result = {
        'ticker': ticker,
        'macd_bull_cross': False,
        'rsi': 0,
        'rsi_ok': False,
        'volume_ratio': 0,
        'volume_ok': False,
        'rs_vs_spy': 0,
        'price': 0,
        'macd_change': 0,
        'score': 0,
        'reasons': []
    }
    
    # Get data
    df = get_stock_data(ticker)
    if df is None or len(df) < 30:
        return result
    
    spy_df = get_stock_data('SPY')
    if spy_df is None or len(spy_df) < 30:
        return result
    
    # Get latest price
    result['price'] = df['Close'].iloc[-1]
    
    # Calculate RSI
    rsi = calculate_rsi(df['Close'])
    result['rsi'] = rsi.iloc[-1]
    result['rsi_ok'] = 40 <= result['rsi'] <= 70
    if result['rsi_ok']:
        result['score'] += 25
        result['reasons'].append(f"RSI in sweet spot: {result['rsi']:.1f}")
    
    # Calculate MACD
    macd_line, signal_line = calculate_macd(df['Close'])
    is_bull_cross, macd_change = check_macd_bull_cross(macd_line, signal_line)
    result['macd_bull_cross'] = is_bull_cross
    result['macd_change'] = macd_change
    
    if is_bull_cross:
        result['score'] += 35
        result['reasons'].append("MACD bull cross (daily)")
    
    # Volume analysis
    avg_volume = df['Volume'].rolling(window=20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    result['volume_ratio'] = current_volume / avg_volume if avg_volume > 0 else 0
    result['volume_ok'] = result['volume_ratio'] > 1.2
    
    if result['volume_ok']:
        result['score'] += 20
        result['reasons'].append(f"Volume {result['volume_ratio']:.1f}x avg")
    
    # Relative Strength vs SPY
    stock_returns = (df['Close'].iloc[-1] / df['Close'].iloc[-20] - 1) * 100 if len(df) >= 20 else 0
    spy_returns = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[-20] - 1) * 100 if len(spy_df) >= 20 else 0
    
    result['rs_vs_spy'] = stock_returns - spy_returns
    
    if result['rs_vs_spy'] > 0:
        result['score'] += 20
        result['reasons'].append(f"RS vs SPY: +{result['rs_vs_spy']:.1f}%")
    
    return result

def main():
    print("=" * 60)
    print(f"BULLISH STOCK SCAN - {datetime.now().strftime('%B %d, %Y')}")
    print("Criteria: MACD bull cross, RSI 40-70, Vol >1.2x, RS vs SPY")
    print("=" * 60)
    
    results = []
    
    for ticker in STOCKS:
        print(f"Scanning {ticker}...", end=" ")
        result = scan_stock(ticker)
        results.append(result)
        print(f"RSI: {result['rsi']:.1f}, Score: {result['score']}")
    
    # Filter stocks with at least some bullish signals
    bullish_stocks = [r for r in results if r['score'] > 0]
    bullish_stocks.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "=" * 60)
    print("TOP 10 BULLISH STOCKS")
    print("=" * 60)
    
    top_10 = bullish_stocks[:10]
    
    now = datetime.now()
    output_lines = []
    output_lines.append("=" * 60)
    output_lines.append("BULLISH STOCK SCAN RESULTS")
    output_lines.append(f"Scan Date: {now.strftime('%B %d, %Y')}")
    output_lines.append(f"Scan Time: {now.strftime('%H:%M')}")
    output_lines.append("=" * 60)
    output_lines.append("")
    output_lines.append("CRITERIA:")
    output_lines.append("- MACD bull cross on daily chart")
    output_lines.append("- RSI between 40-70 (sweet spot)")
    output_lines.append("- Volume > 1.2x 20-day average")
    output_lines.append("- Relative strength vs SPY")
    output_lines.append("")
    output_lines.append("-" * 60)
    output_lines.append("TOP 10 STOCKS")
    output_lines.append("-" * 60)
    
    for i, stock in enumerate(top_10, 1):
        print(f"\n{i}. {stock['ticker']} - ${stock['price']:.2f}")
        print(f"   Score: {stock['score']}/100")
        print(f"   RSI: {stock['rsi']:.1f} {'✓' if stock['rsi_ok'] else '✗'}")
        print(f"   MACD Bull Cross: {'✓' if stock['macd_bull_cross'] else '✗'}")
        print(f"   Volume Ratio: {stock['volume_ratio']:.2f}x {'✓' if stock['volume_ok'] else '✗'}")
        print(f"   RS vs SPY: {stock['rs_vs_spy']:+.1f}%")
        print(f"   Reasons: {', '.join(stock['reasons'])}")
        
        output_lines.append(f"\n{i}. {stock['ticker']} - ${stock['price']:.2f}")
        output_lines.append(f"   Score: {stock['score']}/100")
        output_lines.append(f"   RSI: {stock['rsi']:.1f}")
        output_lines.append(f"   MACD Bull Cross: {'Yes' if stock['macd_bull_cross'] else 'No'}")
        output_lines.append(f"   Volume Ratio: {stock['volume_ratio']:.2f}x")
        output_lines.append(f"   RS vs SPY: {stock['rs_vs_spy']:+.1f}%")
        output_lines.append(f"   Reasons: {', '.join(stock['reasons'])}")
    
    output_lines.append("")
    output_lines.append("-" * 60)
    output_lines.append("SUMMARY")
    output_lines.append("-" * 60)
    
    total_scanned = len(results)
    with_signals = len(bullish_stocks)
    
    output_lines.append(f"Total stocks scanned: {total_scanned}")
    output_lines.append(f"Stocks with bullish signals: {with_signals}")
    output_lines.append(f"Top performer: {top_10[0]['ticker']} (score: {top_10[0]['score']})")
    
    print(f"\n\nSummary: Scanned {total_scanned} stocks, {with_signals} with bullish signals")
    print(f"Top performer: {top_10[0]['ticker']}")
    
    return output_lines

if __name__ == "__main__":
    lines = main()
    
    # Save to file
    output_file = "/home/colton/.openclaw/workspace/agents/stock-scanner/scans/20260303_0929.txt"
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"\nResults saved to: {output_file}")
