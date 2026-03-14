#!/usr/bin/env python3
"""ML Signal Script - run standalone to get ML predictions"""

import pickle, requests, numpy as np
from scipy.stats import norm

MODEL_PATH = "/home/colton/.openclaw/workspace/kalshi/model.pkl"
API_KEY = "7c519784-3932-46e6-8547-fa945541304e"

def get_ml_signal():
    # Load ML model
    with open(MODEL_PATH, "rb") as f:
        m = pickle.load(f)
    model, scaler = m["model"], m["scaler"]

    # Get BTC
    btc_price = float(requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD").json()['result']['XXBTZUSD']['c'][0])

    # Get market
    markets = requests.get(f"https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open", 
                          headers={"apikey": API_KEY}).json()['markets']
    market = markets[0]
    ticker = market['ticker']
    strike = float(market.get('strike', btc_price))

    # Get probability (in dollars, no division)
    yes_bid = float(market.get('yes_bid_dollars', 50) or 50)
    yes_ask = float(market.get('yes_ask_dollars', 50) or 50)
    kalshi_prob = (yes_bid + yes_ask) / 2  # Already in dollars

    # Fair prob
    time_to_expiry = 15 / (365.25 * 24 * 4)  # 15 min
    vol = 0.55
    d2 = (np.log(btc_price / strike) + 0.5 * vol**2 * time_to_expiry) / (vol * np.sqrt(time_to_expiry))
    fair_prob = norm.cdf(d2)
    
    mispricing = fair_prob - kalshi_prob

    # ML prediction
    X = scaler.transform([[fair_prob, kalshi_prob, mispricing, 15, vol]])
    pred = model.predict(X)[0]
    conf = model.predict_proba(X)[0][1]
    direction = "YES" if pred == 1 else "NO"

    return {
        'ticker': ticker,
        'btc': btc_price,
        'strike': strike,
        'fair': fair_prob,
        'kalshi': kalshi_prob,
        'mispricing': mispricing,
        'direction': direction,
        'confidence': conf
    }

if __name__ == "__main__":
    s = get_ml_signal()
    print(f"\n=== ML Signal ===")
    print(f"Ticker: {s['ticker']}")
    print(f"BTC: ${s['btc']:.0f}, Strike: ${s['strike']:.0f}")
    print(f"Fair: {s['fair']:.1%}, Kalshi: {s['kalshi']:.1%}, Mis: {s['mispricing']:+.1%}")
    print(f"*** ML: {s['direction']} {s['confidence']:.0%} ***")
