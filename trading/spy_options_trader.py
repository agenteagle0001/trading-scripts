#!/usr/bin/env python3
"""
SPY Options Trader - Live trading via Alpaca Paper
Uses signals from spy_options_scanner.py and executes spreads via Alpaca API.
"""
import sys, json, requests
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, '/home/colton/.openclaw/workspace/trading')
from spy_options_scanner import get_signal as get_scanner_signal

# Alpaca Paper credentials
API_KEY = "PKINE663HL65ZL4UCILI3CKFFS"
SECRET_KEY = "E23srWhSph8d97FH1oErGwomqhto4jNdWgemk9egV2Wh"
PAPER_URL = "https://paper-api.alpaca.markets"
TRADE_LOG = "/home/colton/.openclaw/workspace/trading/spy_live_trades.json"

# Exit rules
TAKE_PROFIT_PCT = 0.50   # Close when we've earned 50% of max profit
STOP_LOSS_PCT = 1.00     # Stop when we've lost 100% of premium paid
MAX_DTE = 5               # Never hold through expiry

HEADERS = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}

# ─── Alpaca helpers ────────────────────────────────────────────────────────────

def get_option_price(symbol):
    """Get current price for an option."""
    try:
        r = requests.get(f'{PAPER_URL}/v2/options/{symbol}', headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return float(data.get('trade', data.get('quote', {})).get('p', 0))
    except:
        pass
    return None

def get_spy_option_chain(expiry):
    """Get SPY options chain for a specific expiry via yfinance."""
    spy = yf.Ticker("SPY")
    try:
        opts = spy.option_chain(expiry)
        return opts.calls, opts.puts
    except:
        return None, None

def get_spy_price():
    """Get current SPY price."""
    try:
        spy = yf.Ticker("SPY")
        return spy.info.get('currentPrice') or spy.history(period='1d')['Close'].iloc[-1]
    except:
        return None

def place_spread_order(legs, strategy_name, spy_price, net_credit=2.0):
    """Place spread as two separate orders."""
    results = []
    for leg in legs:
        # Calculate limit price: for buy use ask+0.10, for sell use bid-0.10
        if leg['side'] == 'buy':
            limit_price = round(abs(net_credit) + 0.10, 2)
        else:
            limit_price = round(max(0.01, abs(net_credit) - 0.10), 2)
        
        order = {
            "symbol": leg["symbol"],
            "qty": "1",
            "side": leg["side"],
            "type": "limit",
            "limit_price": str(limit_price),
            "time_in_force": "day"
        }
        r = requests.post(f'{PAPER_URL}/v2/orders', headers=HEADERS, json=order, timeout=30)
        ok = r.status_code in (201, 200)
        status = "OK" if ok else f"FAIL {r.status_code}: {r.text[:100]}"
        print(f"  {'BUY' if leg['side']=='buy' else 'SELL'} {leg['symbol']}: {status}")
        try:
            results.append(r.json() if ok else None)
        except:
            results.append(None)
    
    if all(r is not None for r in results):
        return {'id': 'spread', 'legs': results}
    return None



def load_log():
    try:
        with open(TRADE_LOG) as f:
            return json.load(f)
    except:
        return {"trades": [], "summary": {"total_pnl": 0, "open_pnl": 0, "closed_pnl": 0}}

def save_log(log):
    with open(TRADE_LOG, 'w') as f:
        json.dump(log, f, indent=2)

# ─── Spread construction ───────────────────────────────────────────────────────

def build_spread(symbol, direction, spread_type, spy_price, expiration):
    """
    Build a multi-leg spread for SPY.
    direction: 'BULLISH' or 'BEARISH'
    spread_type: 'BULL_CALL_SPREAD', 'BEAR_PUT_SPREAD', etc.
    """
    spy = yf.Ticker(symbol)
    exp_str = expiration.strftime('%Y-%m-%d')
    
    try:
        opts = spy.option_chain(exp_str)
    except Exception as e:
        print(f"  Error fetching options: {e}")
        return None
    
    calls = opts.calls.copy()
    puts = opts.puts.copy()
    
    # ATM strike
    atm = round(spy_price / 1)  # whole dollars
    otm_distance = 5  # $5-wide spreads
    
    legs = []
    
    if spread_type == 'BULL_CALL_SPREAD':
        long_strike = atm        # buy ATM call
        short_strike = atm + otm_distance  # sell OTM call
        long_opt = calls[calls['strike'] == long_strike]
        short_opt = calls[calls['strike'] == short_strike]
        if long_opt.empty or short_opt.empty:
            return None
        long_ask = long_opt.iloc[0]['ask']
        short_bid = short_opt.iloc[0]['bid']
        long_sym = long_opt.iloc[0]['contractSymbol']
        short_sym = short_opt.iloc[0]['contractSymbol']
        net_credit = round(short_bid - long_ask, 2)
        legs = [
            {"symbol": short_sym, "side": "sell", "qty": 1},
            {"symbol": long_sym, "side": "buy", "qty": 1},
        ]
        max_profit = round((short_strike - long_strike) * 100 - net_credit * 100, 2)
        max_loss = round(net_credit * 100, 2)
        
    elif spread_type == 'BEAR_PUT_SPREAD':
        long_strike = atm        # buy ATM put
        short_strike = atm - otm_distance  # sell OTM put
        long_opt = puts[puts['strike'] == long_strike]
        short_opt = puts[puts['strike'] == short_strike]
        if long_opt.empty or short_opt.empty:
            return None
        long_ask = long_opt.iloc[0]['ask']
        short_bid = short_opt.iloc[0]['bid']
        long_sym = long_opt.iloc[0]['contractSymbol']
        short_sym = short_opt.iloc[0]['contractSymbol']
        net_credit = round(short_bid - long_ask, 2)
        legs = [
            {"symbol": short_sym, "side": "sell", "qty": 1},
            {"symbol": long_sym, "side": "buy", "qty": 1},
        ]
        max_profit = round((long_strike - short_strike) * 100 - net_credit * 100, 2)
        max_loss = round(net_credit * 100, 2)
        
    elif spread_type == 'BULL_PUT_SPREAD':
        # Sell OTM put, buy further OTM put
        # Bull put spread = sell higher strike, buy lower strike (credit received)
        short_strike = atm - otm_distance  # sell this higher OTM put
        long_strike = atm - (2 * otm_distance)  # buy this lower OTM put (protection)
        short_opt = puts[puts['strike'] == short_strike]
        long_opt = puts[puts['strike'] == long_strike]
        if short_opt.empty or long_opt.empty:
            return None
        short_bid = short_opt.iloc[0]['bid']
        long_ask = long_opt.iloc[0]['ask']
        short_sym = short_opt.iloc[0]['contractSymbol']
        long_sym = long_opt.iloc[0]['contractSymbol']
        net_credit = round(short_bid - long_ask, 2)
        legs = [
            {"symbol": short_sym, "side": "sell", "qty": 1},
            {"symbol": long_sym, "side": "buy", "qty": 1},
        ]
        max_profit = round(net_credit * 100, 2)
        max_loss = round((short_strike - long_strike) * 100 - net_credit * 100, 2)
        
    elif spread_type == 'BEAR_CALL_SPREAD':
        # Bear call spread = sell lower strike call, buy higher strike call (credit received)
        short_strike = atm + otm_distance  # sell this lower OTM call
        long_strike = atm + (2 * otm_distance)  # buy this higher OTM call (cap upside)
        short_opt = calls[calls['strike'] == short_strike]
        long_opt = calls[calls['strike'] == long_strike]
        if short_opt.empty or long_opt.empty:
            return None
        short_bid = short_opt.iloc[0]['bid']
        long_ask = long_opt.iloc[0]['ask']
        short_sym = short_opt.iloc[0]['contractSymbol']
        long_sym = long_opt.iloc[0]['contractSymbol']
        net_credit = round(short_bid - long_ask, 2)
        legs = [
            {"symbol": short_sym, "side": "sell", "qty": 1},
            {"symbol": long_sym, "side": "buy", "qty": 1},
        ]
        max_profit = round(net_credit * 100, 2)
        max_loss = round((long_strike - short_strike) * 100 - net_credit * 100, 2)
    
    else:
        print(f"  Unknown spread type: {spread_type}")
        return None
    
    return {
        'legs': legs,
        'expiration': exp_str,
        'net_credit': net_credit,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'long_strike': long_strike if 'long_strike' in dir() else None,
        'short_strike': short_strike if 'short_strike' in dir() else None,
    }

# ─── Exit checks ─────────────────────────────────────────────────────────────

def check_and_close_trades(log):
    """Check open positions for exit conditions."""
    r = requests.get(f'{PAPER_URL}/v2/positions', headers=HEADERS)
    if r.status_code != 200:
        print(f"  Could not fetch positions: {r.status_code}")
        return log
    
    positions = r.json()
    open_trades = [t for t in log['trades'] if t.get('status') == 'open']
    
    closed_count = 0
    for trade in open_trades:
        # Find matching position in Alpaca
        sym = trade.get('option_symbol', '')
        if not sym:
            continue
        
        pos = next((p for p in positions if p.get('symbol', '').startswith(sym[:20])), None)
        if not pos:
            # Check option price directly
            price = get_option_price(sym)
            if price is None:
                continue
        else:
            price = float(pos.get('market_value', 0)) / float(pos.get('qty', 1)) if pos.get('qty') else 0
        
        entry_cost = trade.get('entry_credit', 0)
        spread_cost = trade.get('spread_cost', entry_cost)
        
        # Current P&L as a fraction of max profit
        if trade.get('spread_type', '').startswith('BULL') or 'CALL' in trade.get('spread_type', ''):
            # For debit spreads: we paid net debit, profit is when spread widens
            current_pnl = -price * 100  # negative since we paid
        else:
            current_pnl = -price * 100
        
        net_pnl = current_pnl + entry_cost * 100  # net of what we paid/received
        pct_of_max = net_pnl / trade.get('max_profit', 1) if trade.get('max_profit', 0) > 0 else 0
        
        # Take profit
        if pct_of_max >= TAKE_PROFIT_PCT:
            print(f"  🎯 Take profit on {sym} ({pct_of_max:.0%} of max)")
            close_resp = requests.delete(f'{PAPER_URL}/v2/positions/{sym}', headers=HEADERS)
            if close_resp.status_code in (200, 204):
                trade['status'] = 'closed'
                trade['close_reason'] = 'TAKE_PROFIT'
                trade['close_pnl'] = round(net_pnl, 2)
                trade['close_time'] = datetime.now().isoformat()
                log['summary']['total_pnl'] += net_pnl
                closed_count += 1
        
        # Stop loss
        elif pct_of_max <= -STOP_LOSS_PCT:
            print(f"  🛑 Stop loss on {sym} ({pct_of_max:.0%} of max)")
            close_resp = requests.delete(f'{PAPER_URL}/v2/positions/{sym}', headers=HEADERS)
            if close_resp.status_code in (200, 204):
                trade['status'] = 'closed'
                trade['close_reason'] = 'STOP_LOSS'
                trade['close_pnl'] = round(net_pnl, 2)
                trade['close_time'] = datetime.now().isoformat()
                log['summary']['total_pnl'] += net_pnl
                closed_count += 1
        
        # Check DTE
        expiry = trade.get('expiration', '')
        if expiry:
            try:
                exp_date = datetime.strptime(expiry, '%Y-%m-%d')
                dte = (exp_date - datetime.now()).days
                if dte <= 1:
                    print(f"  ⏰ Expiring soon ({dte}d) - closing {sym}")
                    close_resp = requests.delete(f'{PAPER_URL}/v2/positions/{sym}', headers=HEADERS)
                    if close_resp.status_code in (200, 204):
                        trade['status'] = 'closed'
                        trade['close_reason'] = 'DTE_EXPIRY'
                        trade['close_pnl'] = round(net_pnl, 2)
                        trade['close_time'] = datetime.now().isoformat()
                        log['summary']['total_pnl'] += net_pnl
                        closed_count += 1
            except:
                pass
    
    if closed_count:
        print(f"  Closed {closed_count} trade(s)")
    
    return log

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== SPY Options Trader === {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    log = load_log()
    spy_price = get_spy_price()
    if not spy_price:
        print("Could not get SPY price - skipping")
        return
    
    spy = f"SPY"
    spy_str = f"SPY (${spy_price:.2f})"
    print(f"SPY: {spy_str}")
    
    # Check exits on open positions
    log = check_and_close_trades(log)
    open_trades = [t for t in log['trades'] if t.get('status') == 'open']
    print(f"Open positions: {len(open_trades)}")
    
    if len(open_trades) >= 5:
        print("Max positions (5) reached - skipping new entry")
        save_log(log)
        return
    
    # Get signal from scanner
    result = get_scanner_signal()
    if isinstance(result, dict) and 'signal' in result:
        inner = result.get('signal', {})
        if isinstance(inner, dict):
            result = inner
    
    if not result or result.get('signal') == 'SKIP':
        print("No trade signal (confidence below threshold)")
        save_log(log)
        return
    
    direction = result.get('direction')
    spread_type = result.get('spread_type')
    confidence = result.get('confidence', 0)
    
    print(f"\nSignal: {direction} | Spread: {spread_type} | Confidence: {confidence:.0%}")
    
    # Get next Friday expiry (or nearest weekly)
    spy_obj = yf.Ticker(spy)
    expiries = list(spy_obj.options)
    if not expiries:
        print("No expiries available")
        save_log(log)
        return
    
    # Pick expiry ~7-14 days out
    target_dte = 7
    expiration = None
    for exp in sorted(expiries):
        dte = (datetime.strptime(exp, '%Y-%m-%d') - datetime.now()).days
        if 5 <= dte <= 14:
            expiration = datetime.strptime(exp, '%Y-%m-%d')
            print(f"Using expiry: {exp} ({dte}d DTE)")
            break
    
    if not expiration:
        expiration = datetime.strptime(sorted(expiries)[0], '%Y-%m-%d')
        print(f"Using nearest expiry: {expiration.strftime('%Y-%m-%d')}")
    
    # Build the spread
    spread = build_spread(spy, direction, spread_type, spy_price, expiration)
    if not spread:
        print("Failed to build spread - could not find strikes")
        save_log(log)
        return
    
    print(f"  Net debit: ${abs(spread['net_credit']):.2f}/share | Max profit: ${spread['max_profit']:.2f} | Max loss: ${spread['max_loss']:.2f}")
    
    # Place order
    print(f"  Placing {spread_type} order...")
    order_resp = place_spread_order(spread['legs'], spread_type, spy_price, net_credit=spread['net_credit'])
    
    if order_resp:
        trade_entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": direction,
            "spread_type": spread_type,
            "expiration": spread['expiration'],
            "legs": spread['legs'],
            "net_credit": spread['net_credit'],
            "max_profit": spread['max_profit'],
            "max_loss": spread['max_loss'],
            "entry_credit": spread['net_credit'],
            "spy_price": spy_price,
            "confidence": confidence,
            "status": "open",
            "order_id": order_resp.get('id'),
        }
        log['trades'].append(trade_entry)
        print(f"  ✅ {spread_type} opened: ${spread['net_credit']:.2f} credit")
    
    save_log(log)
    total = log['summary']['total_pnl']
    print(f"\nTotal P&L: ${total:.2f}")
    print(f"Open trades: {len([t for t in log['trades'] if t.get('status')=='open'])}")

if __name__ == '__main__':
    main()
