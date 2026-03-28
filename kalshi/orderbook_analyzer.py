#!/usr/bin/env python3
"""Order flow analysis from Kraken ticker with logging"""
import requests, time, json
from datetime import datetime

LOG_FILE = "/home/colton/.openclaw/workspace/kalshi/orderbook_log.json"

def get_order_flow():
    """Get Kraken ticker for order flow"""
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")
    data = r.json()['result']['XXBTZUSD']
    
    best_ask = float(data['a'][0])
    best_bid = float(data['b'][0])
    last_price = float(data['c'][0])
    volume_24h = float(data['v'][1])
    
    return {
        'best_ask': best_ask,
        'best_bid': best_bid,
        'last_price': last_price,
        'mid': (best_ask + best_bid) / 2,
        'spread': best_ask - best_bid,
        'volume_24h': volume_24h,
    }

def log_result(data, signal):
    """Log result with timestamp"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        **data,
        'signal': signal
    }
    
    # Load existing
    try:
        with open(LOG_FILE) as f:
            logs = json.load(f)
    except:
        logs = []
    
    logs.append(entry)
    
    # Keep last 1000
    logs = logs[-1000:]
    
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)
    
    return entry

def analyze():
    """Analyze order flow"""
    data = get_order_flow()
    
    price_position = (data['last_price'] - data['mid']) / data['mid']
    spread_pct = (data['spread'] / data['mid']) * 100
    
    if price_position > 0.001:
        signal = "BULLISH"
    elif price_position < -0.001:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"
    
    entry = log_result(data, signal)
    
    ts = entry['timestamp'][11:19]
    print(f"[{ts}] Last: ${data['last_price']:.0f} | Mid: ${data['mid']:.0f} | {signal}")
    
    return entry

if __name__ == "__main__":
    analyze()
