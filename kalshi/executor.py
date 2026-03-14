#!/usr/bin/env python3
"""Executor - combines signals and decides to trade"""

import pickle, requests, numpy as np, time, json
from scipy.stats import norm
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64, uuid

MODEL_PATH = "/home/colton/.openclaw/workspace/kalshi/model.pkl"
API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
KEY_PATH = "/home/colton/.openclaw/workspace/secrets/kalshi.pem"
STATE_FILE = "/home/colton/.openclaw/workspace/kalshi/executor_state.json"

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except: return {"last_market": None, "entry_price": None, "position": None}



def check_stop_loss(signals, state, minutes_left=15):
    """Time-adjusted stop loss"""
    if not state.get("entry_price") or not state.get("position"):
        return None
    
    entry = state["entry_price"]
    current = signals["kalshi"]
    direction = state["position"]
    
    # Calculate P/L
    if direction == "yes":
        pnl_pct = (current - entry) / entry
    else:
        pnl_pct = (entry - current) / entry
    
    # Time-adjusted stop (10% base)
    time_factor = max(0.5, min(2.0, minutes_left / 7.0))
    adjusted_stop = 0.10 * time_factor
    
    # Also check for take profit at 20%
    if pnl_pct > 0.20:
        return "TAKE_PROFIT"
    
    if pnl_pct < -adjusted_stop:
        return "STOP_LOSS"
    
    return None

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_all_signals():
    with open(MODEL_PATH, "rb") as f:
        m = pickle.load(f)
    model, scaler = m["model"], m["scaler"]
    
    btc = requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD").json()
    btc_price = float(btc['result']['XXBTZUSD']['c'][0])
    
    markets = requests.get("https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open", 
                         headers={"apikey": API_KEY}).json()['markets']
    market = markets[0]
    ticker = market['ticker']
    strike = float(market.get('strike', btc_price))
    
    yes_bid = float(market.get('yes_bid_dollars', 50) or 50)
    yes_ask = float(market.get('yes_ask_dollars', 50) or 50)
    kalshi_prob = (yes_bid + yes_ask) / 2
    
    T = 15 / (365.25 * 24 * 4)
    vol = 0.55
    d2 = (np.log(btc_price / strike) + 0.5 * vol**2 * T) / (vol * np.sqrt(T))
    fair_prob = norm.cdf(d2)
    mispricing = fair_prob - kalshi_prob
    
    X = scaler.transform([[fair_prob, kalshi_prob, mispricing, 15, vol]])
    pred = model.predict(X)[0]
    conf = model.predict_proba(X)[0][1]
    
    return {'ticker': ticker, 'btc': btc_price, 'strike': strike, 'fair': fair_prob, 
            'kalshi': kalshi_prob, 'mispricing': mispricing, 
            'ml_direction': "YES" if pred == 1 else "NO", 'ml_confidence': conf}

def should_trade(signals, state):
    trades = []
    if signals['ml_confidence'] > 0.55:
        trades.append(f"ML {signals['ml_direction']} {signals['ml_confidence']:.0%}")
    if abs(signals['mispricing']) > 0.08:
        trades.append(f"Mispricing {signals['mispricing']:+.0%}")
    
    # One trade per market
    if state.get("last_market") == signals['ticker']:
        return []
    return trades

def execute_trade(ticker, direction, price):
    ts = str(int(time.time() * 1000))
    path = "/trade-api/v2/portfolio/orders"
    msg = f"{ts}POST{path}"
    
    with open(KEY_PATH, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)
    sig = pk.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    
    h = {"KALSHI-ACCESS-KEY": API_KEY, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(), 
         "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}
    data = {"ticker": ticker, "action": "buy" if direction == "yes" else "sell", 
            "side": direction, "count": 5, "type": "limit", f"{direction}_price": int(price * 100), 
            "client_order_id": str(uuid.uuid4())}
    
    r = requests.post("https://api.elections.kalshi.com" + path, headers=h, json=data)
    return r.status_code, r.text

if __name__ == "__main__":
    signals = get_all_signals()
    state = load_state()
    
    print(f"\n=== Signals ===")
    print(f"Ticker: {signals['ticker']} (last: {state.get('last_market')})")
    print(f"Fair: {signals['fair']:.1%}, Kalshi: {signals['kalshi']:.1%}, Mis: {signals['mispricing']:+.1%}")
    print(f"ML: {signals['ml_direction']} {signals['ml_confidence']:.0%}")
    
    trades = should_trade(signals, state)
    
    # Check stop loss / take profit
    exit_signal = check_stop_loss(signals, state)
    if exit_signal:
        print(f"=== {exit_signal} - would exit position ===")
        # Could add exit order here
    
    if trades:
        print(f"=== Trade Signals: {trades} ===")
        direction = signals['ml_direction'].lower()
        price = signals['kalshi']
        status, resp = execute_trade(signals['ticker'], direction, price)
        print(f"Order: {status} {resp[:80]}")
        if status == 201:
            save_state({"last_market": signals['ticker'], "entry_price": signals['kalshi'], "position": direction})
    else:
        print("=== No trade (same market or no signal) ===")
