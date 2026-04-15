#!/usr/bin/env python3
"""Alpaca Paper Trading - Sell puts on bullish signals with exit rules"""
import yfinance as yf
import os
import json, subprocess, glob, re, requests
from datetime import datetime

API_KEY = "PK2XSTA527FYCWHKBHA7LLN67W"
SECRET_KEY = "53Afp7yyB8Mzw8rXpVWUZnJ8uyRbVi1zqDzBbDthQM5o"
PAPER_URL = "https://paper-api.alpaca.markets"
PAPER_LOG = "/home/colton/.openclaw/workspace/trading/alpaca_trades.json"
SCAN_DIR = "/home/colton/.openclaw/workspace/agents/stock-scanner/scans"

# Exit rules
TAKE_PROFIT_PCT = 0.55  # Close when we've earned 55% of premium
STOP_LOSS_PCT = 0.25   # Lose premium + 25% of premium = 1.25x premium
MAX_DTE = 3             # Close if <= 3 DTE (never hold through expiry)
COOLDOWN_HOURS = 24     # Don't re-enter a symbol within this many hours of closing

def get_alpaca_option(symbol, option_type="put"):
    """Get option in Alpaca format using yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        expiries = ticker.options
        if not expiries:
            return None
        
        expiry = expiries[0]
        opts = ticker.option_chain(expiry)
        
        if option_type == "put":
            options = opts.puts
        else:
            options = opts.calls
        
        current_price = ticker.info.get('currentPrice', 100)
        # Sell put 5% OTM
        target_strike = current_price * 0.95
        
        options['distance'] = abs(options['strike'] - target_strike)
        closest = options.nsmallest(1, 'distance').iloc[0]
        strike = closest['strike']
        
        exp_str = expiry.replace('-', '')[2:]
        strike_str = str(int(strike * 1000)).zfill(8)
        
        # Collateral needed: strike price × 100 (for cash-secured put)
        collateral_needed = strike * 100
        
        return {
            'alpaca_symbol': f"{symbol.upper()}{exp_str}P{strike_str}",
            'strike': strike,
            'bid': closest['bid'],
            'ask': closest['ask'],
            'expiry': expiry,
            'premium_collected': closest['bid'],  # What we collect when selling
            'current_price': current_price,
            'collateral_needed': collateral_needed
        }
    except Exception as e:
        print(f"Error getting option for {symbol}: {e}")
        return None

def get_latest_scan():
    scans = glob.glob(f"{SCAN_DIR}/*.txt")
    if not scans:
        return []
    # Prefer bullish_scan files, sort by mtime descending
    bullish_files = sorted([s for s in scans if 'bullish' in s], key=lambda f: -os.path.getmtime(f))
    scan_files = sorted([s for s in scans if '_scan.txt' in s and 'bullish_scan' not in s], key=lambda f: -os.path.getmtime(f))
    candidates = bullish_files + scan_files
    if not candidates:
        return []
    latest = candidates[0]
    
    symbols = []
    with open(latest) as f:
        for line in f:
            parts = line.strip().split()
            # Need at least: SYMBOL $ PRICE
            if len(parts) < 3:
                continue
            # Skip header/noise lines
            first = parts[0]
            if first in ('TOP', 'Symbol', 'Filters', 'Scan', 'Total', 'Rank', 'NOTE:', 'SCAN', 'BULLISH', 'DATA', 'SPY', '-', 'OBSERVATIONS', 'Showing'):
                continue
            if first.startswith('=') or first.startswith('---'):
                continue
            # Old numbered format: "1. MU" or "  1   INTC  $  62.59"
            if first[0].isdigit():
                for p in parts:
                    if p.replace('.', '').replace(',', '').isalpha() and len(p) >= 2 and p.replace('.', '').replace(',', '').isupper():
                        sym = p.replace('.', '').replace(',', '')
                        if sym not in ('USD', 'RSI', 'MACD', 'YES', 'NO', 'BULL'):
                            symbols.append(sym)
                        break
                continue
            # New tabular format: "SYMBOL $ PRICE" (parts[0]=SYMBOL, parts[1]='$')
            if parts[1] == '$' and len(parts[0]) >= 2 and parts[0].isalpha():
                symbols.append(parts[0])
    return symbols[:3]

def get_positions():
    """Get current positions from Alpaca"""
    headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
    r = requests.get(f'{PAPER_URL}/v2/positions', headers=headers)
    if r.status_code == 200:
        return r.json()
    return []

def get_option_quote(symbol):
    """Get current quote for an option"""
    headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
    r = requests.get(f'{PAPER_URL}/v2/options/{symbol}', headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def close_position(symbol, reason):
    """Close an option position"""
    headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
    r = requests.delete(f'{PAPER_URL}/v2/positions/{symbol}', headers=headers)
    print(f"  {'✅' if r.status_code == 200 else '❌'} Closed {symbol}: {reason}")
    return r.status_code == 200

def load_log():
    try:
        with open(PAPER_LOG) as f:
            return json.load(f)
    except:
        return {"trades": []}

def save_log(log):
    with open(PAPER_LOG, "w") as f:
        json.dump(log, f, indent=2)

def get_dte(opt_symbol):
    """Parse DTE from option symbol like MU260327P00360000"""
    try:
        # Format: SYMYYMMDDP... (8-char date starting at index of P - 8)
        p_idx = opt_symbol.index('P')
        date_str = opt_symbol[p_idx - 8 : p_idx]
        expiry = datetime.strptime(date_str, "%y%m%d")
        dte = (expiry.date() - datetime.now().date()).days
        return dte
    except:
        return 999

def check_exits(positions, log):
    """Check if any positions hit exit conditions"""
    headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
    
    for pos in positions:
        opt_symbol = pos.get('symbol', '')
        trade = None
        if 'P' not in opt_symbol:  # Only handle put options
            continue
        
        # Get premium collected from trade log, or estimate from avg_entry_price
        premium_collected = 0
        for t in log.get('trades', []):
            if t.get('option_symbol') == opt_symbol and t.get('status') == 'open':
                premium_collected = t.get('premium_collected', 0)
                break
        
        # Fallback: estimate premium from avg_entry_price if not in log
        if premium_collected <= 0:
            try:
                avg_entry = float(pos.get('avg_entry_price', 0))
                if avg_entry > 0:
                    premium_collected = avg_entry
            except:
                pass
        
        if premium_collected <= 0:
            print(f"  {opt_symbol}: no premium data, skipping exit check")
            continue
        
        # Get current price directly from position data (already has current_price)
        current_price = float(pos.get('current_price', 0))
        if current_price <= 0:
            # Fallback: try market data API
            try:
                r = requests.get(f'{PAPER_URL}/v2/stocks/{opt_symbol[:4]}/quotes/latest', headers=headers, timeout=5)
                if r.status_code == 200:
                    q = r.json().get('quote', {})
                    current_price = float(q.get('ap', 0))
            except:
                pass
            if current_price <= 0:
                print(f"  {opt_symbol}: could not get current price, skipping")
                continue
        
        # Calculate P&L as percentage of premium collected
        # When we sell a put, we collect premium. If price goes up, we gain (price drops).
        # If price goes down, we lose (price rises).
        pnl_pct = (premium_collected - current_price) / premium_collected
        
        print(f"  {opt_symbol}: premium=${premium_collected:.2f} current=${current_price:.2f} P&L={pnl_pct:+.1%}")
        
        # Take profit: we've kept 55% of the premium
        if pnl_pct >= TAKE_PROFIT_PCT:
            close_position(opt_symbol, f"TAKE PROFIT {pnl_pct:.1%}")
            if trade:
                trade['status'] = 'closed'
                trade['exit_reason'] = 'take_profit'
                trade['exit_pnl_pct'] = pnl_pct
                trade['closed_at'] = datetime.now().isoformat()
        
        # Stop loss: we've lost 25% of premium
        elif pnl_pct <= -STOP_LOSS_PCT:
            close_position(opt_symbol, f"STOP LOSS {pnl_pct:.1%}")
            if trade:
                trade['status'] = 'closed'
                trade['exit_reason'] = 'stop_loss'
                trade['exit_pnl_pct'] = pnl_pct
                trade['closed_at'] = datetime.now().isoformat()

        # DTE rule: close if <= MAX_DTE to avoid assignment risk
        dte = get_dte(opt_symbol)
        if 0 < dte <= MAX_DTE:
            close_position(opt_symbol, f"DTE {dte}d - closing before expiry")
            if trade:
                trade['status'] = 'closed'
                trade['exit_reason'] = 'dte_exit'
                trade['exit_pnl_pct'] = pnl_pct
                trade['closed_at'] = datetime.now().isoformat()
    
    return log

def main():
    print(f"=== Alpaca Options Trading === {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Strategy: Sell puts on bullish signals | TP: {TAKE_PROFIT_PCT:.0%} | SL: {STOP_LOSS_PCT:.0%}")
    
    log = load_log()
    positions = get_positions()
    
    # Check open positions for exit conditions
    print("\n--- Checking Positions ---")
    opts = [p for p in positions if 'P' in p.get('symbol', '')]
    if not opts:
        print("No open put positions")
    else:
        print(f"Open positions: {len(opts)}")
        check_exits(opts, log)
        save_log(log)
    
    # Get signals and place new trades
    print("\n--- Scanning for Signals ---")
    symbols = get_latest_scan()
    print(f"Top signals: {symbols}")
    
    # Get recently closed symbols (within cooldown)
    recently_closed = set()
    cutoff = datetime.now().timestamp() - COOLDOWN_HOURS * 3600
    for t in log.get('trades', []):
        if t.get('status') == 'closed' and t.get('closed_at'):
            try:
                closed_ts = datetime.fromisoformat(t['closed_at']).timestamp()
                if closed_ts >= cutoff:
                    # Extract stock symbol from option symbol (e.g. "TSLA260415P00342500" -> "TSLA")
                    opt = t.get('option_symbol', '')
                    if opt:
                        # Extract stock symbol: letters at start before digits
                        import re
                        m = re.match(r'^([A-Z]+)', opt)
                        if m:
                            recently_closed.add(m.group(1))
            except:
                pass
    
    for symbol in symbols:
        # Check if already have position in this stock
        if any(symbol in p.get('symbol', '') for p in opts):
            print(f"{symbol}: Already have position")
            continue
        # Check cooldown
        if symbol in recently_closed:
            print(f"{symbol}: Cooldown ({COOLDOWN_HOURS}h since last close)")
            continue
        
        # Sell put
        opt = get_alpaca_option(symbol)
        if not opt:
            print(f"{symbol}: Could not get option data")
            continue
        
        # Check if we can afford the collateral (need buying power >= strike * 100)
        headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
        r = requests.get(f'{PAPER_URL}/v2/account', headers=headers)
        if r.status_code == 200:
            account = r.json()
            buying_power = float(account.get('buying_power', 0))
            if opt['collateral_needed'] > buying_power:
                print(f"{symbol}: Need ${opt['collateral_needed']:,.0f} collateral, have ${buying_power:,.0f} - skipping")
                continue
        
        # Place sell to open order
        order = {
            "symbol": opt['alpaca_symbol'],
            "qty": "1",
            "side": "sell",
            "type": "market",
            "time_in_force": "gtc"
        }
        
        headers = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY}
        r = requests.post(f'{PAPER_URL}/v2/orders', headers=headers, json=order)
        
        if r.status_code == 201:
            order_resp = r.json()
            print(f"✅ SOLD PUT: {symbol} {opt['alpaca_symbol']} @ ${opt['premium_collected']:.2f}")
            print(f"   Strike: ${opt['strike']} | Exp: {opt['expiry']} | Stock: ${opt['current_price']:.2f}")
            
            log["trades"].append({
                "symbol": symbol,
                "option_symbol": opt['alpaca_symbol'],
                "strike": opt['strike'],
                "expiry": opt['expiry'],
                "premium_collected": opt['premium_collected'],
                "entry_price": opt['premium_collected'],
                "timestamp": datetime.now().isoformat(),
                "status": "open",
                "order_id": order_resp.get('id')
            })
            save_log(log)
        else:
            print(f"❌ Failed: {symbol} - {r.text}")
    
    # Print summary
    print("\n--- Today's Summary ---")
    open_trades = [t for t in log.get('trades', []) if t.get('status') == 'open']
    closed_trades = [t for t in log.get('trades', []) if t.get('status') == 'closed']
    print(f"Open positions: {len(open_trades)}")
    print(f"Closed today: {len(closed_trades)}")

if __name__ == "__main__":
    main()
