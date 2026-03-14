#!/usr/bin/env python3
"""Kalshi BTC 15-min monitor - minimal version"""

import requests, time, csv, os, pickle
from datetime import datetime

API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
DATA_FILE = "/home/colton/.openclaw/workspace/kalshi/data.csv"

print("Minimal version - basic data collection")
print("Will use ML predictions when script is fixed")

# Test basic API
resp = requests.get("https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open", 
                   headers={"apikey": API_KEY})
print(f"Markets: {len(resp.json().get('markets', []))}")
