#!/usr/bin/env python3
"""Paper trading with proper P&L tracking"""
import sys
sys.path.insert(0, '/home/colton/.openclaw/workspace/kalshi')
from executor import get_all_signals, get_order_flow_signal
import json
from datetime import datetime
import requests

PAPER_LOG = "/home/colton/.openclaw/workspace/kalshi/paper_trades.json"
SHARES = 5

def load_log():
    try:
        with open(PAPER_LOG) as f:
            return json.load(f)
    except:
        return {"trades": []}

def save_log(log):
    with open(PAPER_LOG, "w") as f:
        json.dump(log, f, indent=2)

def check_signal():
    """Check if we should trade"""
    signals = get_all_signals()
    order_flow = get_order_flow_signal()
    
    ml_signal = signals['ml_confidence'] > 0.90
    mispricing_signal = abs(signals['mispricing']) > 0.25
    
    # Only trade when price > 0.50 (only buy YES at high prices)
    price_ok = signals['kalshi'] > 0.50
    
    if ml_signal and mispricing_signal and price_ok:
        if (signals['ml_direction'] == 'YES' and order_flow in ['BULLISH', 'NEUTRAL']) or \
           (signals['ml_direction'] == 'NO' and order_flow in ['BEARISH', 'NEUTRAL']):
            return {
                "signal": True,
                "ticker": signals['ticker'],
                "direction": signals['ml_direction'],
                "entry_price": signals['kalshi'],
                "ml_confidence": signals['ml_confidence'],
                "mispricing": signals['mispricing'],
                "order_flow": order_flow,
                "timestamp": datetime.now().isoformat()
            }
    
    return {"signal": False}

def resolve_trades():
    """Check for resolved markets and calculate P&L"""
    log = load_log()
    API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
    
    try:
        r = requests.get("https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&limit=100", 
                        headers={"apikey": API_KEY}, timeout=10)
        markets = r.json().get("markets", [])
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return log
    
    # Get finalized markets
    finalized = {m['ticker']: m for m in markets if m['status'] == 'finalized'}
    
    updated = 0
    for trade in log["trades"]:
        if trade.get("resolved"):
            continue
        
        ticker = trade["ticker"]
        if ticker in finalized:
            m = finalized[ticker]
            result = m.get("result", "")  # "yes" or "no"
            direction = trade["direction"]
            
            # Determine win/loss
            if direction == "YES":
                won = (result == "yes")
            else:
                won = (result == "no")
            
            entry = trade["entry_price"]
            
            # Calculate P&L (5 shares, binary payout)
            if won:
                # Paid entry cents per share, got $1 per share
                pnl = (1.0 - entry) * 100 * SHARES
            else:
                # Paid entry cents, got $0
                pnl = -entry * 100 * SHARES
            
            trade["result"] = result
            trade["won"] = won
            trade["pnl"] = pnl
            trade["resolved_at"] = datetime.now().isoformat()
            updated += 1
    
    if updated:
        save_log(log)
        print(f"Resolved {updated} trades")
    
    return log

if __name__ == "__main__":
    # Check for new signal
    signal = check_signal()
    
    if signal["signal"]:
        log = load_log()
        
        # Only log if we don't already have a trade for this market
        existing = [t for t in log["trades"] if t["ticker"] == signal["ticker"] and not t.get("exited")]
        if not existing:
            log["trades"].append(signal)
            save_log(log)
            print(f"=== PAPER TRADE ===")
            print(f"Ticker: {signal['ticker']}")
            print(f"Direction: {signal['direction']}")
            print(f"Entry: ${signal['entry_price']}")
            print(f"ML: {signal['ml_confidence']:.0%}")
    
    # Check for resolutions
    log = resolve_trades()
    
    # Print summary
    trades = log["trades"]
    resolved = [t for t in trades if t.get("resolved")]
    if resolved:
        wins = [t for t in resolved if t.get("won")]
        losses = [t for t in resolved if not t.get("won")]
        total_pnl = sum(t.get("pnl", 0) for t in resolved)
        
        print(f"\n=== SUMMARY ===")
        print(f"Resolved: {len(resolved)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win %: {len(wins)/len(resolved)*100:.1f}%")
        print(f"Total P&L: ${total_pnl:.2f}")
