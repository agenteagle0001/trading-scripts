#!/usr/bin/env python3
"""
Options Position Monitor
Run this to check and manage the AMD put position
"""

import json
import math
import subprocess
from scipy.stats import norm

# Alpaca API keys
API_KEY = "PK2XSTA527FYCWHKBHA7LLN67W"
SECRET_KEY = "53Afp7yyB8Mzw8rXpVWUZnJ8uyRbVi1zqDzBbDthQM5o"

# Position parameters
STRIKE = 190
STOP_LOSS_PCT = 0.03  # 3%
TAKE_PROFIT_DAYS = 5

def get_amd_price():
    """Get current AMD price"""
    result = subprocess.run([
        "curl", "-s", 
        "https://query1.finance.yahoo.com/v8/finance/chart/AMD?interval=1m&range=1d",
        "-H", "User-Agent: Mozilla/5.0"
    ], capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data['chart']['result'][0]['meta']['regularMarketPrice']

def get_option_price(S, K, T, sigma=0.35):
    """Calculate Black-Scholes put price"""
    r = 0.045
    if T <= 0:
        return max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def check_position():
    """Check current position status"""
    result = subprocess.run([
        "curl", "-s",
        f"https://paper-api.alpaca.markets/v2/positions",
        "-H", f"APCA-API-KEY-ID: {API_KEY}",
        "-H", f"APCA-API-SECRET-KEY: {SECRET_KEY}"
    ], capture_output=True, text=True)
    
    positions = json.loads(result.stdout)
    amd_pos = [p for p in positions if p.get('symbol','').startswith('AMD')]
    
    if amd_pos:
        for p in amd_pos:
            print(f"Position: {p['symbol']}")
            print(f"  Qty: {p['qty']}")
            print(f"  Avg price: {p.get('avg_entry_price', 'N/A')}")
            print(f"  Current value: {p.get('market_value', 'N/A')}")
            print(f"  P/L: {p.get('unrealized_pl', 'N/A')}")
    else:
        print("No AMD positions")

def check_orders():
    """Check pending orders"""
    result = subprocess.run([
        "curl", "-s",
        f"https://paper-api.alpaca.markets/v2/orders?status=open",
        "-H", f"APCA-API-KEY-ID: {API_KEY}",
        "-H", f"APCA-API-SECRET-KEY: {SECRET_KEY}"
    ], capture_output=True, text=True)
    
    orders = json.loads(result.stdout)
    amd_orders = [o for o in orders if o.get('symbol','').startswith('AMD')]
    
    if amd_orders:
        print("\nPending orders:")
        for o in amd_orders:
            print(f"  {o['symbol']}: {o['side']} {o['qty']} @ ${o.get('limit_price', 'market')} ({o['status']})")

if __name__ == "__main__":
    print("=" * 50)
    print("AMD Options Position Monitor")
    print("=" * 50)
    
    # Get current AMD price
    amd_price = get_amd_price()
    print(f"\nAMD Price: ${amd_price:.2f}")
    
    # Calculate option metrics
    days_to_exp = 20  # Approx
    T = days_to_exp / 365
    opt_price = get_option_price(amd_price, STRIKE, T)
    
    print(f"Strike: ${STRIKE}")
    print(f"Option theoretical price: ${opt_price:.2f}")
    print(f"Stop loss level: ${STRIKE * (1-STOP_LOSS_PCT):.2f}")
    
    # Check position and orders
    check_position()
    check_orders()
    
    # Recommendations
    print("\n" + "=" * 50)
    print("Recommendations:")
    if amd_price < STRIKE * (1 - STOP_LOSS_PCT):
        print("⚠️ STOP LOSS TRIGGERED - Consider closing position")
    elif amd_price > STRIKE * 1.03:
        print("✅ Position is safe (stock > 3% above strike)")
    else:
        print("⏳ Monitor - stock is near strike")
