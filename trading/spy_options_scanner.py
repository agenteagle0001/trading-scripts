#!/usr/bin/env python3
"""
SPY Options Scanner v2
Combines ML volatility prediction with technical analysis for options trading.
"""
import sys
import json
import pickle
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

sys.path.insert(0, '/home/colton/.openclaw/workspace/trading')
from spy_ml_model import get_signal as get_ml_signal, train as train_ml_model

MODEL_PATH = "/home/colton/.openclaw/workspace/trading/spy_model.pkl"

def get_technical_signal():
    """Rule-based technical signal (same as before)"""
    spy = yf.Ticker("SPY")
    df = spy.history(period="100d")
    
    close = df['Close'].iloc[-1]
    sma_20 = df['Close'].rolling(20).mean().iloc[-1]
    sma_50 = df['Close'].rolling(50).mean().iloc[-1]
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    macd = (ema12 - ema26).iloc[-1]
    macd_signal = df['Close'].ewm(span=9).mean().iloc[-1]
    macd_hist = macd - macd_signal
    
    # Score
    score = 0
    reasons = []
    
    if rsi < 30:
        score += 2
        reasons.append(f"RSI oversold ({rsi:.1f})")
    elif rsi > 70:
        score -= 2
        reasons.append(f"RSI overbought ({rsi:.1f})")
    
    if macd_hist > 0:
        score += 2
        reasons.append("MACD histogram positive")
    else:
        score -= 2
        reasons.append("MACD histogram negative")
    
    if close > sma_20:
        score += 1
        reasons.append("Above 20 MA")
    else:
        score -= 1
        reasons.append("Below 20 MA")
    
    if close > sma_50:
        score += 1
        reasons.append("Above 50 MA")
    else:
        score -= 1
        reasons.append("Below 50 MA")
    
    max_score = 6
    confidence = min(abs(score) / max_score, 1.0)
    
    if score > 0:
        direction = "BULLISH"
    elif score < 0:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return {
        'direction': direction,
        'score': score,
        'confidence': confidence,
        'rsi': rsi,
        'macd_hist': macd_hist,
        'reasons': reasons,
        'price': close
    }

def get_combined_signal():
    """Combine ML volatility with technical direction"""
    # Get ML signal
    ml = get_ml_signal()
    
    # Get technical signal
    tech = get_technical_signal()
    
    return ml, tech

def select_spread_strategy(ml, tech):
    """Select spread strategy based on signals"""
    spy = yf.Ticker("SPY")
    price = spy.history(period="1d")['Close'].iloc[-1]
    
    # Base strategy from technical direction
    direction = tech['direction']
    confidence = tech['confidence']
    
    # Adjust for volatility
    high_vol = ml and ml.get('signal') == 'HIGH_VOL'
    
    if high_vol and confidence < 0.5:
        # High vol + low confidence = skip or use iron condor
        return None, "HIGH_VOL_LOW_CONF", price
    
    if high_vol:
        # High vol = sell premium strategies
        spread_type = "IRON_CONDOR" if abs(tech['score']) < 2 else "BULL_PUT_SPREAD" if direction == "BULLISH" else "BEAR_CALL_SPREAD"
    else:
        # Low vol = buy premium or directional
        spread_type = "BULL_CALL_SPREAD" if direction == "BULLISH" else "BEAR_PUT_SPREAD"
    
    # Only trade if confidence > 60%
    if confidence < 0.60:
        return None, "LOW_CONFIDENCE", price
    
    return spread_type, direction, price

def get_signal():
    """Compatibility function for paper_trader.py"""
    ml, tech = get_combined_signal()
    spread_type, decision, price = select_spread_strategy(ml, tech)
    
    if spread_type is None:
        return {'signal': 'SKIP', 'confidence': 0}
    
    # Calculate strikes
    atm = round(price)
    if spread_type == "BULL_CALL_SPREAD":
        long_strike = atm
        short_strike = atm + 5
    elif spread_type == "BEAR_PUT_SPREAD":
        long_strike = atm
        short_strike = atm - 5
    elif spread_type == "BULL_PUT_SPREAD":
        long_strike = atm - 5
        short_strike = atm
    elif spread_type == "BEAR_CALL_SPREAD":
        short_strike = atm
        long_strike = atm + 5
    else:
        long_strike = atm
        short_strike = atm + 5 if decision == "BULLISH" else atm - 5
    
    return {
        'direction': decision,
        'confidence': tech['confidence'],
        'spread_type': spread_type,
        'strikes': {
            'spread_type': spread_type,
            'long_strike': long_strike,
            'short_strike': short_strike,
        },
        'price': price,
    }

def main():
    print("=== SPY Options Scanner v2 ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    ml, tech = get_combined_signal()
    
    print(f"\nML Signal:")
    if ml:
        print(f"  Volatility: {ml['signal']} ({ml['confidence']:.1%} confidence)")
        print(f"  High vol prob: {ml['prob_high_vol']:.1%}")
    else:
        print("  No ML signal (run train first)")
    
    print(f"\nTechnical Signal:")
    print(f"  Direction: {tech['direction']} (score: {tech['score']:+.0f})")
    print(f"  Confidence: {tech['confidence']:.1%}")
    print(f"  RSI: {tech['rsi']:.1f}")
    print(f"  MACD hist: {tech['macd_hist']:.4f}")
    print(f"  Price: ${tech['price']:.2f}")
    print(f"  Reasons:")
    for r in tech['reasons']:
        print(f"    - {r}")
    
    signal = get_signal()
    
    print(f"\n=== Decision ===")
    if signal.get('signal') == 'SKIP':
        print(f"SKIP: {signal.get('decision', 'LOW_CONFIDENCE')}")
    else:
        print(f"Direction: {signal['direction']}")
        print(f"Strategy: {signal['spread_type']}")
        print(f"SPY Price: ${signal['price']:.2f}")
        print(f"  Strikes: Long ${signal['strikes']['long_strike']} / Short ${signal['strikes']['short_strike']}")
    
    return {
        'ml_signal': ml,
        'tech_signal': tech,
        'signal': signal,
    }

if __name__ == "__main__":
    result = main()
    if result:
        print("\n" + json.dumps(result, indent=2, default=str))
