#!/usr/bin/env python3
"""
Build a proper ML dataset from Kalshi + Kraken data.
Labels: 1 = YES won (BTC up), 0 = NO won (BTC down)
Features: fair_prob, time_remaining, BTC momentum, etc.
"""
import requests
import csv
import json
import re
import time
from datetime import datetime, timezone
from collections import defaultdict

API_KEY = "7c519784-3932-46e6-8547-fa945541304e"  # From live_trader.py
HEADERS = {"apikey": API_KEY}
KRAKEN_URL = "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15"

# Load Kraken OHLC data
print("Loading Kraken candles...")
r = requests.get(KRAKEN_URL, timeout=10)
candles_data = r.json()["result"]["XXBTZUSD"]
# candles_data format: [timestamp, open, high, low, close, vwap, volume, count]
candles = {}
for c in candles_data:
    ts = int(c[0])  # Unix timestamp
    candles[ts] = {
        "open": float(c[1]),
        "high": float(c[2]),
        "low": float(c[3]),
        "close": float(c[4]),
    }

print(f"Loaded {len(candles)} Kraken candles")
# Range: {min_ts} to {max_ts}

# Load kalshi.log for fair_prob snapshots per market
print("Loading kalshi.log for fair_prob data...")
market_fairs = defaultdict(list)
current_ticker = None
with open("/home/colton/.openclaw/workspace/kalshi/kalshi.log") as f:
    for line in f:
        if "New market" in line:
            m = re.search(r"New market (.+?),", line)
            if m:
                current_ticker = m.group(1)
        if "Fair Prob Up:" in line and "min left" in line:
            m_match = re.search(r"Fair Prob Up: ([\d.]+).*?([\d.]+) min left", line)
            if m_match and current_ticker:
                fair = float(m_match.group(1))
                mins = float(m_match.group(2))
                market_fairs[current_ticker].append({"fair": fair, "mins": mins})

print(f"Loaded fair_prob for {len(market_fairs)} markets")

# Parse CSV trades and get outcomes
print("Loading trades from CSV...")
# Group trades by ticker
ticker_trades = defaultdict(list)
with open("/home/colton/.openclaw/media/inbound/Kalshi-Transactions-2026_1---9b8ffcfa-f0e1-417d-a2aa-c6907ecdb4b5.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["type"] != "trade":
            continue
        ticker = row["market_ticker"]
        ticker_trades[ticker].append({
            "side": row["side"],
            "entry": int(row["entry_price_cents"]) / 100.0,
            "exit": int(row["exit_price_cents"]) / 100.0,
            "pnl": int(row["realized_pnl_with_fees_cents"]),
            "open_ts": row["open_timestamp"],
            "close_ts": row["close_timestamp"],
        })

print(f"Loaded {len(ticker_trades)} unique markets from CSV")

# Get Kalshi outcomes for each market
print("Fetching Kalshi market outcomes...")
outcomes = {}
tickers_to_query = list(ticker_trades.keys())
for i, ticker in enumerate(tickers_to_query):
    if i % 20 == 0:
        print(f"  Progress: {i}/{len(tickers_to_query)}")
    try:
        r = requests.get(
            f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}",
            headers=HEADERS, timeout=10
        )
        data = r.json()
        m = data.get("market", {})
        if m.get("status") == "finalized":
            result = m.get("result")  # "yes" or "no"
            outcomes[ticker] = result
            time.sleep(0.05)  # Rate limit
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")

print(f"Got outcomes for {len(outcomes)} markets")

# Build dataset
print("Building dataset...")
dataset = []
skipped = 0

for ticker, trades in ticker_trades.items():
    if ticker not in outcomes:
        skipped += 1
        continue
    
    outcome = 1 if outcomes[ticker] == "yes" else 0  # 1 = YES won
    
    # Get fair_prob snapshots for this market
    fairs = market_fairs.get(ticker, [])
    if not fairs:
        skipped += 1
        continue
    
    # Use average fair_prob for this market
    avg_fair = sum(f["fair"] for f in fairs) / len(fairs)
    max_fair = max(f["fair"] for f in fairs)
    min_fair = min(f["fair"] for f in fairs)
    avg_mins = sum(f["mins"] for f in fairs) / len(fairs)
    
    # Get first trade's entry info
    first_trade = trades[0]
    
    # Match to Kraken candle using open timestamp
    # Parse the open_timestamp to find the 15-min candle
    open_dt = datetime.fromisoformat(first_trade["open_ts"].replace("Z", "+00:00"))
    open_ts = int(open_dt.timestamp())
    
    # Find the 15-min candle that contains this timestamp
    candle_ts = (open_ts // 900) * 900  # Round down to 15-min boundary
    
    btc_direction = None
    btc_change = None
    if candle_ts in candles:
        c = candles[candle_ts]
        btc_change = (c["close"] - c["open"]) / c["open"]
        btc_direction = 1 if c["close"] > c["open"] else 0
    
    # Features: fair_prob, avg_mins, btc_direction, btc_change, entry_price
    entry = first_trade["entry"]
    dataset.append({
        "ticker": ticker,
        "label": outcome,
        "fair_prob": avg_fair,
        "max_fair": max_fair,
        "min_fair": min_fair,
        "time_remaining": avg_mins,
        "btc_direction": btc_direction,
        "btc_change": btc_change,
        "entry_price": entry,
        "num_trades": len(trades),
        "total_pnl": sum(t["pnl"] for t in trades),
    })

print(f"Built dataset with {len(dataset)} samples (skipped {skipped})")

# Save dataset
with open("/home/colton/.openclaw/workspace/kalshi/ml_dataset.json", "w") as f:
    json.dump(dataset, f, indent=2)

print(f"Dataset saved to ml_dataset.json")

# Analyze
yes_wins = [d for d in dataset if d["label"] == 1]
no_wins = [d for d in dataset if d["label"] == 0]
print(f"\nDataset summary:")
print(f"  YES wins: {len(yes_wins)}")
print(f"  NO wins: {len(no_wins)}")
print(f"  Avg fair_prob for YES wins: {sum(d['fair_prob'] for d in yes_wins)/len(yes_wins):.3f}")
print(f"  Avg fair_prob for NO wins: {sum(d['fair_prob'] for d in no_wins)/len(no_wins):.3f}")
if yes_wins:
    btc_yes = [d for d in yes_wins if d['btc_direction'] is not None]
    print(f"  BTC up when YES won: {sum(d['btc_direction'] for d in btc_yes)}/{len(btc_yes)}")
if no_wins:
    btc_no = [d for d in no_wins if d['btc_direction'] is not None]
    print(f"  BTC up when NO won: {sum(d['btc_direction'] for d in btc_no)}/{len(btc_no)}")
