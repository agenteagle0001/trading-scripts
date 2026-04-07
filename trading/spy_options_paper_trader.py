#!/usr/bin/env python3
"""
SPY Options Paper Trader
Executes vertical spreads on Alpaca Paper trading.
"""
import sys
import json
import time
import requests
from datetime import datetime
from math import ceil

sys.path.insert(0, '/home/colton/.openclaw/workspace/trading')
from spy_options_scanner import main as get_signal

# Alpaca API (Paper)
BASE_URL = "https://paper-api.alpaca.markets"
API_KEY = "PK2XSTA527FYCWHKBHA7LLN67W"
SECRET_KEY = "53Afp7yyB8Mzw8rXpVWUZnJ8uyRbVi1zqDzBbDthQM5o"

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

# Trading parameters
MAX_POSITION_VALUE = 1000  # $1,000 max per spread
MAX_SPREADS = 5
DAYS_BEFORE_CLOSE = 7
PROFIT_TARGET = 0.50  # 50% of spread width
STOP_LOSS = 0.20  # 20% loss on spread

TRADE_LOG = "/home/colton/.openclaw/workspace/trading/spy_trades.json"

def get_account():
    """Get account info"""
    r = requests.get(f"{BASE_URL}/v2/account", headers=HEADERS)
    return r.json()

def get_positions():
    """Get current options positions"""
    r = requests.get(f"{BASE_URL}/v2/positions", headers=HEADERS)
    return r.json() if r.status_code == 200 else []

def get_spy_price():
    """Get current SPY price"""
    r = requests.get("https://data.alpaca.markets/v2/stocks/SPY/latest", headers=HEADERS)
    if r.status_code == 200:
        return float(r.json()['last']['lp'])
    return None

def calculate_spread_cost(spy_price, long_strike, short_strike, is_call=True):
    """
    Estimate the cost of a vertical spread.
    For a $5 wide spread, cost is roughly $2.50-$3.50 (debit spread)
    """
    if is_call:
        # Bull call spread: ITM call + OTM short call
        intrinsic_long = max(spy_price - long_strike, 0)
        intrinsic_short = max(spy_price - short_strike, 0)
    else:
        # Bear put spread: ITM put + OTM short put
        intrinsic_long = max(long_strike - spy_price, 0)
        intrinsic_short = max(short_strike - spy_price, 0)
    
    # Estimated cost (simplified - actual cost varies with IV)
    spread_width = abs(short_strike - long_strike)
    estimated_cost = spread_width * 0.70  # Assume 70% of width as cost
    
    return estimated_cost

def get_options_contracts(spy_price, expiration, direction, delta_target=50):
    """
    Get options contracts for the spread.
    Returns the strike prices for the spread.
    """
    # We'll construct the symbol ourselves
    # SPY_YYYYMMDD_PPPPS strike format for Alpaca
    # For example: SPY_20260321_P00500000 (for $500 put)
    
    if direction == "BULLISH":
        # Buy ATM call, sell OTM call (+$5)
        long_strike = round(spy_price / 1)  # Round to nearest dollar
        short_strike = long_strike + 5
    else:
        # Buy ATM put, sell OTM put (-$5)  
        long_strike = round(spy_price / 1)
        short_strike = long_strike - 5
    
    return {
        'long_strike': long_strike,
        'short_strike': short_strike,
        'spread_type': 'CALL' if direction == "BULLISH" else 'PUT'
    }

def calculate_contracts_needed(spy_price, spread_cost):
    """Calculate how many spreads we can afford"""
    if spread_cost <= 0:
        return 1
    max_spreads = int(MAX_POSITION_VALUE / spread_cost)
    return max(1, max_spreads)

def place_spread_order(spy_price, expiration, strikes, direction, qty=1):
    """
    Place a vertical spread order.
    For paper trading, we'll track this manually.
    """
    spread_type = 'CALL' if direction == "BULLISH" else 'PUT'
    
    # Alpaca options symbols: SPY + expiration + P/C + strike price
    # Example: SPY260321P00500000 (Mar 21, 2026, $500 put)
    
    long_strike = strikes['long_strike']
    short_strike = strikes['short_strike']
    
    # Long leg (buy)
    if spread_type == 'CALL':
        long_symbol = f"SPY{expiration}C{int(long_strike * 1000):08d}"
        short_symbol = f"SPY{expiration}C{int(short_strike * 1000):08d}"
    else:
        long_symbol = f"SPY{expiration}P{int(long_strike * 1000):08d}"
        short_symbol = f"SPY{expiration}P{int(short_strike * 1000):08d}"
    
    # Calculate max profit and loss
    spread_width = abs(short_strike - long_strike)
    max_profit = (spread_width * 100 - 0) * qty  # Width minus cost
    max_loss = 0 * qty  # Just the cost
    
    return {
        'timestamp': datetime.now().isoformat(),
        'direction': direction,
        'expiration': expiration,
        'long_symbol': long_symbol,
        'short_symbol': short_symbol,
        'long_strike': long_strike,
        'short_strike': short_strike,
        'spread_width': spread_width,
        'qty': qty,
        'spread_cost_estimate': spread_width * 0.70 * qty,
        'max_profit_estimate': (spread_width * 0.30) * qty,  # 30% of width as profit potential
        'max_loss_estimate': spread_width * 0.70 * qty,
        'status': 'OPEN',
        'entry_price': spy_price
    }

def load_trades():
    """Load trade log"""
    try:
        with open(TRADE_LOG) as f:
            return json.load(f)
    except:
        return {"trades": [], "summary": {"total_pnl": 0, "wins": 0, "losses": 0}}

def save_trades(trades):
    """Save trade log"""
    with open(TRADE_LOG, "w") as f:
        json.dump(trades, f, indent=2)

def check_and_close_expired(trades):
    """Check for trades that should be closed"""
    today = datetime.now()
    closed = 0
    
    for trade in trades["trades"]:
        if trade.get("status") != "OPEN":
            continue
        
        # Check if 7 days passed
        entry_time = datetime.fromisoformat(trade['timestamp'])
        days_elapsed = (today - entry_time).days
        
        if days_elapsed >= DAYS_BEFORE_CLOSE:
            trade['status'] = 'CLOSED'
            trade['close_reason'] = 'TIME_EXPIRED'
            trade['close_price'] = trade['spread_cost_estimate']  # Estimate
            closed += 1
    
    if closed:
        print(f"Closed {closed} trades due to time expiration")
    
    return closed

def main():
    print(f"=== SPY Options Paper Trader === {datetime.now().strftime('%H:%M')}")
    
    # Load current trades
    trades = load_trades()
    open_trades = [t for t in trades["trades"] if t.get("status") == "OPEN"]
    
    print(f"Open spreads: {len(open_trades)}/{MAX_SPREADS}")
    
    # Check for expired trades
    check_and_close_expired(trades)
    
    # Check if we can open new trades (1 per day limit)
    today_trades = [t for t in open_trades if t['timestamp'].startswith(datetime.now().strftime('%Y-%m-%d'))]
    if len(today_trades) > 0:
        print(f"Already traded today ({len(today_trades)} trade(s))")
        print("Summary:")
        print(f"  Open: {len(open_trades)}")
        print(f"  Total P&L: ${trades['summary']['total_pnl']:.2f}")
        return
    
    # Check if we have room for more spreads
    if len(open_trades) >= MAX_SPREADS:
        print(f"Max spreads reached ({MAX_SPREADS})")
        return
    
    # Get ML signal
    print("\nGenerating signal...")
    signal = get_signal()
    
    # scanner.main() returns a wrapper dict with 'signal' as the inner signal
    if isinstance(signal, dict) and 'signal' in signal and isinstance(signal['signal'], dict):
        signal = signal['signal']
    
    if not signal or signal.get('signal') == "SKIP":
        print("No trade signal - confidence below threshold")
        return
    
    print(f"\nSignal: {signal['direction']} with {signal['confidence']:.1%} confidence")
    
    # Get current SPY price
    spy_price = get_spy_price()
    if not spy_price:
        print("Failed to get SPY price")
        return
    
    print(f"SPY Price: ${spy_price:.2f}")
    
    # Get strike selection
    strikes = signal.get('strikes', {})
    direction = signal['direction']
    expiration = signal.get('expiration', datetime.now().strftime('%Y%m%d'))
    
    # Calculate spread cost
    spread_cost = calculate_spread_cost(spy_price, strikes['long_strike'], strikes['short_strike'])
    contracts_needed = calculate_contracts_needed(spy_price, spread_cost)
    
    print(f"Spread: {strikes['spread_type']}")
    print(f"Strikes: ${strikes['long_strike']} / ${strikes['short_strike']}")
    print(f"Estimated cost: ${spread_cost:.2f} x {contracts_needed} = ${spread_cost * contracts_needed:.2f}")
    
    # Create the trade
    trade = place_spread_order(
        spy_price, 
        expiration, 
        strikes, 
        direction,
        qty=contracts_needed
    )
    
    print(f"\n=== TRADE PLACED ===")
    print(f"Direction: {trade['direction']}")
    print(f"Long: {trade['long_symbol']}")
    print(f"Short: {trade['short_symbol']}")
    print(f"Qty: {trade['qty']} spread(s)")
    print(f"Max Profit: ${trade['max_profit_estimate']:.2f}")
    print(f"Max Loss: ${trade['max_loss_estimate']:.2f}")
    
    # Add to trades
    trades["trades"].append(trade)
    save_trades(trades)
    
    print(f"\nSaved to {TRADE_LOG}")

if __name__ == "__main__":
    main()