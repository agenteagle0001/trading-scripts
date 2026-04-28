#!/usr/bin/env python3
"""Auto stock trader with RSI signals and P/L exits"""

import requests, time
from datetime import datetime

ALPACA_KEY = "PKINE663HL65ZL4UCILI3CKFFS"
ALPACA_SECRET = "E23srWhSph8d97FH1oErGwomqhto4jNdWgemk9egV2Wh"
BASE_URL = "https://paper-api.alpaca.markets/v2"
HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

STOP_LOSS = 0.03
TAKE_PROFIT = 0.10

def get_positions():
    r = requests.get(f"{BASE_URL}/positions", headers=HEADERS)
    return r.json() if r.status_code == 200 else []

def place_order(symbol, qty, side):
    data = {"symbol": symbol, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"}
    return requests.post(f"{BASE_URL}/orders", headers=HEADERS, json=data)

def check_exits():
    positions = get_positions()
    print(f"Checking {len(positions)} positions...")
    for p in positions:
        try:
            cost = abs(float(p.get('cost_basis', 0)))
            mv = abs(float(p.get('market_value', 0)))
            if cost > 0:
                pl_pct = (mv - cost) / cost
                qty = max(1, int(abs(float(p.get('qty', 1)))))
                
                if pl_pct <= -STOP_LOSS:
                    print(f"🚨 STOP LOSS: {p['symbol']} at {pl_pct:.1%}")
                    place_order(p['symbol'], qty, "sell")
                elif pl_pct >= TAKE_PROFIT:
                    print(f"💰 TAKE PROFIT: {p['symbol']} at {pl_pct:.1%}")
                    place_order(p['symbol'], qty, "sell")
        except Exception as e:
            print(f"Error: {e}")

print(f"=== Auto Trader Started {datetime.now()} ===")
while True:
    check_exits()
    time.sleep(60)
