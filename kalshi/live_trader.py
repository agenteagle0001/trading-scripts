#!/usr/bin/env python3
"""Live trading - uses V2 ML model with BTC momentum signals"""
import sys
import time
sys.path.insert(0, '/home/colton/.openclaw/workspace/kalshi')
from executor import (
    get_all_signals, get_ml_signal_v2, get_order_flow_signal,
    execute_trade, get_position, load_state, save_state, log_signal
)
import json
import requests
from datetime import datetime

API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
KEY_PATH = "/home/colton/.openclaw/workspace/secrets/kalshi.pem"
LIVE_LOG = "/home/colton/.openclaw/workspace/kalshi/live_trades.json"
TARGET_DOLLAR = 4.00  # Fixed position size per trade

def load_log():
    try:
        with open(LIVE_LOG) as f:
            return json.load(f)
    except:
        return {"trades": []}

def save_log(log):
    with open(LIVE_LOG, "w") as f:
        json.dump(log, f, indent=2)

def resolve_trades():
    """Check for resolved markets and calculate P&L"""
    log = load_log()

    try:
        r = requests.get(
            "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&limit=100",
            headers={"apikey": API_KEY}, timeout=10
        )
        markets = r.json().get("markets", [])
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return

    finalized = {m['ticker']: m for m in markets if m['status'] == 'finalized'}

    updated = 0
    for trade in log["trades"]:
        if trade.get("resolved"):
            continue

        ticker = trade["ticker"]
        if ticker in finalized:
            m = finalized[ticker]
            result = m.get("result", "")
            direction = trade["direction"]

            won = (direction == "YES" and result == "yes") or (direction == "NO" and result == "no")
            entry = trade["entry_price"]
            count = trade.get("count", 1)
            position_cost = entry * count

            if won:
                pnl = (1.0 - entry) * count
            else:
                pnl = -position_cost

            trade["result"] = result
            trade["won"] = won
            trade["pnl"] = pnl
            trade["resolved"] = True
            trade["resolved_at"] = datetime.now().isoformat()

            # Update training log with outcome
            _update_training_log_outcome(ticker, result, won)
            updated += 1

    if updated:
        print(f"Resolved {updated} trades")
        save_log(log)

def _update_training_log_outcome(ticker, result, won):
    """Update training log with trade outcome"""
    try:
        with open("/home/colton/.openclaw/workspace/kalshi/ml_training_log.json") as f:
            log = json.load(f)

        # Find and update the matching signal entry
        for entry in reversed(log.get("signals", [])):
            if entry.get("ticker") == ticker and "result" not in entry:
                entry["result"] = result
                entry["won"] = won
                entry["resolved_at"] = datetime.now().isoformat()
                break

        with open("/home/colton/.openclaw/workspace/kalshi/ml_training_log.json", "w") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print(f"Training log update error: {e}")

def main():
    print(f"=== LIVE TRADING === {datetime.now().strftime('%H:%M')}")

    # Resolve any finalized trades first
    resolve_trades()

    # Check for existing position
    position = get_position()
    if position and position.get("ticker"):
        print(f"Already in position: {position['ticker']}")
        return

    # Get all signals
    signals = get_all_signals()
    order_flow = get_order_flow_signal()

    # Get V2 ML signal
    ml_direction, ml_confidence = get_ml_signal_v2(signals)

    # Display signal status
    print(f"Ticker: {signals['ticker']}")
    print(f"Fair: {signals['fair']:.1%} | Kalshi: {signals['kalshi']:.1%} | Mispricing: {signals['mispricing']:+.1%}")
    print(f"V1 ML: {signals['ml_direction']} {signals['ml_confidence']:.0%}")
    print(f"V2 ML: {ml_direction} {ml_confidence:.0%}" if ml_direction else "V2: No signal")
    print(f"Momentum: 15min={signals['momentum_15min']:+.3f}, 45min={signals['momentum_45min']:+.3f}")
    print(f"Order flow: {order_flow}")

    # Decide to trade
    if ml_direction is None:
        print("No trade: V2 model returned no signal")
        return

    # Apply additional filters
    # Entry price filter: only trade in sweet spot 50-70 cents
    price_ok = 0.50 < signals['kalshi'] < 0.70
    mispricing_ok = abs(signals['mispricing']) > 0.25
    ml_v1_ok = signals['ml_confidence'] > 0.90

    # Trade logic: V2 signal + price filter + momentum confirmation
    if ml_direction == "YES":
        if not price_ok:
            print(f"No trade: entry price ${signals['kalshi']:.3f} outside 0.50-0.70 range")
            return
        # V2 momentum-based YES signal
        direction = "yes"
        print(f"=== TRADE SIGNAL ===")
        print(f"Direction: YES | Price: ${signals['kalshi']:.3f}")
        print(f"Confidence: {ml_confidence:.0%} | Fair prob: {signals['fair']:.1%}")

    elif ml_direction == "NO":
        if not price_ok:
            print(f"No trade: entry price ${signals['kalshi']:.3f} outside 0.50-0.70 range")
            return
        direction = "no"
        print(f"=== TRADE SIGNAL ===")
        print(f"Direction: NO | Price: ${signals['kalshi']:.3f}")
        print(f"Confidence: {ml_confidence:.0%} | Fair prob: {signals['fair']:.1%}")

    # Execute trade
    status, resp, count = execute_trade(signals['ticker'], direction, signals['kalshi'])
    position_cost = signals['kalshi'] * count

    print(f"Status: {status}")
    print(f"Contracts: {count} @ ${signals['kalshi']:.3f} = ${position_cost:.2f}")
    print(f"Response: {resp[:200] if resp else 'None'}")

    if status == 201:
        # Log the trade
        log = load_log()
        log["trades"].append({
            "timestamp": datetime.now().isoformat(),
            "ticker": signals['ticker'],
            "direction": ml_direction,
            "entry_price": signals['kalshi'],
            "count": count,
            "position_cost": position_cost,
            "fair_prob": signals['fair'],
            "momentum_15min": signals['momentum_15min'],
            "momentum_45min": signals['momentum_45min'],
            "ml_confidence_v2": ml_confidence,
            "status": status,
            "response": resp[:200] if resp else None
        })
        save_log(log)

        # Save state
        save_state({
            "last_market": signals['ticker'],
            "entry_price": signals['kalshi'],
            "position": direction,
            "entry_time": time.time()
        })

        print(f"Trade logged: {ml_direction} at ${signals['kalshi']:.3f}")
    else:
        print("Trade FAILED - check response")

if __name__ == "__main__":
    main()
