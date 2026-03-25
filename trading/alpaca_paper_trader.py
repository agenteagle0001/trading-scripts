#!/usr/bin/env python3
"""Alpaca Paper Trading - Automated with real option placement"""
import yfinance as yf
import json, subprocess, glob, re
from datetime import datetime

API_KEY = "PK2XSTA527FYCWHKBHA7LLN67W"
SECRET_KEY = "53Afp7yyB8Mzw8rXpVWUZnJ8uyRbVi1zqDzBbDthQM5o"
PAPER_URL = "https://paper-api.alpaca.markets"
PAPER_LOG = "/home/colton/.openclaw/workspace/trading/alpaca_trades.json"
SCAN_DIR = "/home/colton/.openclaw/workspace/agents/stock-scanner/scans"

def get_alpaca_option(symbol, target_delta=-0.2):
    """Get option in Alpaca format using yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        expiries = ticker.options
        if not expiries:
            return None
        
        expiry = expiries[0]
        opts = ticker.option_chain(expiry)
        puts = opts.puts
        
        current_price = ticker.info.get('currentPrice', 100)
        target_strike = current_price * 0.95
        
        puts['distance'] = abs(puts['strike'] - target_strike)
        closest = puts.nsmallest(1, 'distance').iloc[0]
        strike = closest['strike']
        
        exp_str = expiry.replace('-', '')[2:]
        strike_str = str(int(strike * 1000)).zfill(8)
        
        return {
            'alpaca_symbol': f"{symbol.upper()}{exp_str}P{strike_str}",
            'strike': strike,
            'bid': closest['bid'],
            'ask': closest['ask'],
            'expiry': expiry
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_latest_scan():
    scans = glob.glob(f"{SCAN_DIR}/*.txt")
    if not scans:
        return []
    # Prioritize: bullish_scan files first, then _scan.txt files
    bullish_files = sorted([s for s in scans if 'bullish_scan' in s], reverse=True)
    scan_files = sorted([s for s in scans if '_scan.txt' in s and 'bullish_scan' not in s], reverse=True)
    
    candidates = bullish_files + scan_files
    if not candidates:
        return []
    latest = candidates[0]
    
    symbols = []
    with open(latest) as f:
        for line in f:
            # Match lines like "1. AMAT  | $374.70" (bullish_scan format)
            match = re.search(r'\d+\.\s+([A-Z]+)\s+\|', line)
            if match:
                symbols.append(match.group(1))
            # Match lines like "AMD     $   215.99    63.4      +6.97%" (tabular)
            elif re.search(r'\|\s+\$', line):
                sym = re.search(r'([A-Z]{2,5})\s+\$', line)
                if sym:
                    symbols.append(sym.group(1))
    return symbols[:3]

def place_order(symbol, qty=1):
    """Place order on Alpaca"""
    opt = get_alpaca_option(symbol)
    if not opt:
        return None
    
    order = {
        "symbol": opt['alpaca_symbol'],
        "qty": str(qty),
        "side": "sell",
        "type": "market",
        "time_in_force": "day"
    }
    
    cmd = ['curl', '-s', '-X', 'POST', f'{PAPER_URL}/v2/orders',
           '-H', f'APCA-API-KEY-ID: {API_KEY}',
           '-H', f'APCA-API-SECRET-KEY: {SECRET_KEY}',
           '-H', 'Content-Type: application/json',
           '-d', json.dumps(order)]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout), opt

def get_positions():
    result = subprocess.run(
        ['curl', '-s', '-H', f'APCA-API-KEY-ID: {API_KEY}', '-H', f'APCA-API-SECRET-KEY: {SECRET_KEY}',
         f'{PAPER_URL}/v2/positions'],
        capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return []

def load_log():
    try:
        with open(PAPER_LOG) as f:
            return json.load(f)
    except:
        return {"trades": []}

def save_log(log):
    with open(PAPER_LOG, "w") as f:
        json.dump(log, f, indent=2)

def main():
    print(f"=== Alpaca Options Trading === {datetime.now().strftime('%H:%M')}")
    
    log = load_log()
    positions = get_positions()
    
    # Get open option positions
    opts = [p for p in positions if 'P' in p.get('symbol', '')]
    print(f"Open positions: {len(opts)}")
    for p in opts:
        print(f"  {p['symbol']}: {p.get('qty')} @ {p.get('avg_entry_price')} = {p.get('market_value')}")
    
    # Get signals
    symbols = get_latest_scan()
    
    for symbol in symbols:
        # Check if already have position
        if any(symbol in p.get('symbol', '') for p in opts):
            print(f"{symbol}: Already in position")
            continue
        
        # Place order
        result, opt = place_order(symbol)
        
        if result.get('id'):
            print(f"✅ Placed: {symbol} {opt['alpaca_symbol']} @ ${opt['ask']:.2f}")
            
            log["trades"].append({
                "symbol": symbol,
                "option_symbol": opt['alpaca_symbol'],
                "strike": opt['strike'],
                "premium": opt['ask'],
                "timestamp": datetime.now().isoformat(),
                "status": "open",
                "order_id": result.get('id')
            })
            save_log(log)
        else:
            print(f"❌ Failed: {symbol} - {result}")

if __name__ == "__main__":
    main()
