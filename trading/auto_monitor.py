#!/usr/bin/env python3
"""
Automated Trading Monitor - Autonomous Version
Run via heartbeat or cron
"""

import json
import math
import subprocess
import sys
from scipy.stats import norm

# Config
API_KEY = "PK2XSTA527FYCWHKBHA7LLN67W"
SECRET_KEY = "53Afp7yyB8Mzw8rXpVWUZnJ8uyRbVi1zqDzBbDthQM5o"

STRIKE = 190
STOP_LOSS_PCT = 0.03  # 3%
ENTRY_DAY = "2026-02-28"  # Set when trade opened

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def get_amd_price():
    result = run_cmd('curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AMD?interval=1m&range=1d" -H "User-Agent: Mozilla/5.0"')
    try:
        data = json.loads(result)
        return data['chart']['result'][0]['meta']['regularMarketPrice']
    except:
        return None

def get_option_price(S, K, T, sigma=0.35):
    r = 0.045
    if T <= 0:
        return max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def get_positions():
    result = run_cmd(f'curl -s -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {SECRET_KEY}" "https://paper-api.alpaca.markets/v2/positions"')
    return json.loads(result)

def get_orders():
    result = run_cmd(f'curl -s -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {SECRET_KEY}" "https://paper-api.alpaca.markets/v2/orders?status=open"')
    return json.loads(result)

def close_position(symbol):
    """Buy to close the position"""
    # First get current option price
    price_result = run_cmd('curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AMD?interval=1d&range=5d" -H "User-Agent: Mozilla/5.0"')
    try:
        data = json.loads(price_result)
        S = data['chart']['result'][0]['meta']['regularMarketPrice']
        T = 20 / 365
        # Use slightly higher price to ensure fill
        close_price = get_option_price(S, STRIKE, T) * 1.1
    except:
        close_price = 2.50  # Fallback
    
    order = {
        "symbol": symbol,
        "qty": "1",
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "limit_price": f"{close_price:.2f}"
    }
    
    cmd = f'''curl -s -X POST "https://paper-api.alpaca.markets/v2/orders" \
      -H "APCA-API-KEY-ID: {API_KEY}" \
      -H "APCA-API-SECRET-KEY: {SECRET_KEY}" \
      -H "Content-Type: application/json" \
      -d '{json.dumps(order)}' '''
    
    return run_cmd(cmd)

def main():
    print("=" * 60)
    print("AUTOMATED TRADING MONITOR")
    print("=" * 60)
    
    # Get AMD price
    amd_price = get_amd_price()
    if not amd_price:
        print("ERROR: Could not get AMD price")
        sys.exit(1)
    
    print(f"\nAMD Price: ${amd_price:.2f}")
    print(f"Strike: ${STRIKE}")
    print(f"Stop-loss level: ${STRIKE * (1-STOP_LOSS_PCT):.2f}")
    
    # Check positions
    positions = get_positions()
    amd_positions = [p for p in positions if 'AMD' in p.get('symbol', '')]
    
    # Check orders
    orders = get_orders()
    amd_orders = [o for o in orders if 'AMD' in o.get('symbol', '')]
    
    print(f"\nPositions: {len(amd_positions)}")
    print(f"Pending orders: {len(amd_orders)}")
    
    # Check stop-loss
    stop_level = STRIKE * (1 - STOP_LOSS_PCT)
    
    if amd_price < stop_level:
        print(f"\n⚠️ STOP LOSS TRIGGERED!")
        print(f"AMD ${amd_price:.2f} < ${stop_level:.2f}")
        
        if amd_positions:
            for pos in amd_positions:
                symbol = pos['symbol']
                print(f"Closing position: {symbol}")
                result = close_position(symbol)
                print(f"Close order result: {result[:200]}...")
        
        print("\n🚨 ALERT: Stop-loss triggered - position closed")
        print("Action: Manual review recommended")
    
    elif amd_price > 195:  # Safe zone
        print(f"\n✅ Position is SAFE")
        print(f"AMD ${amd_price:.2f} > $195 (well above stop)")
    
    elif amd_positions:
        print(f"\n⚠️ MONITOR - Price near stop level")
        print("Consider setting alert or preparing to close")
    
    elif amd_orders:
        print(f"\n⏳ Order pending fill")
        for o in amd_orders:
            print(f"  {o['symbol']}: {o['side']} {o['qty']} @ ${o.get('limit_price', 'market')}")
    
    else:
        print("\nℹ️ No positions or pending orders")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
