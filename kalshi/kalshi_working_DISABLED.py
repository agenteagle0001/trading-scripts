# Install the correct package if not already
# pip install cryptography requests numpy scipy

import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import numpy as np
from datetime import datetime
from datetime import timezone
from scipy.stats import norm  # For norm.cdf in fair prob model
from scipy.optimize import fsolve

# --- CONFIGURATION ---
API_KEY_ID = "bd283026-0d00-4b06-97cf-9d8ac919114f"
PRIVATE_KEY_PATH = "/home/colton/.openclaw/workspace/secrets/kalshi.pem"
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

INTERVAL = 30  # Sampling interval in seconds
MIN_SAMPLES = 20  # Minimum samples before computing correlation
CORR_WINDOW = 100  # Use last N samples for correlation calculation
MOVE_THRESHOLD = 50  # USD move threshold for opportunity detection
PROB_LAG_THRESHOLD = 0.05  # Probability change threshold for lag detection

# Fair Prob Model Parameters (adjust as needed)
IMPLIED_VOL = 0.55  # Annualized volatility (42% based on recent BTC IV levels; can be dynamic)
RISK_FREE_RATE = 0.0  # Risk-free rate (set to 0 for crypto, as no meaningful interest)
DIVIDEND_YIELD = 0.0  # No dividends for BTC

# Data storage
timestamps = []
btc_prices = []
kalshi_probs = []
current_market_ticker = None
reference_price = None

# Load the Private Key for signing
with open(PRIVATE_KEY_PATH, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

def kalshi_auth_headers(method, path):
    """Generates the required RSA-PSS signature headers for Kalshi."""
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + method + path
    
    signature = private_key.sign(
        msg.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    
    return {
        "KALSHI-API-KEY": API_KEY_ID,
        "KALSHI-API-SIGNATURE": base64.b64encode(signature).decode('utf-8'),
        "KALSHI-API-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }

def get_open_btc15m_markets():
    path = "/markets"
    params = {"series_ticker": "KXBTC15M", "status": "open"}
    
    headers = kalshi_auth_headers("GET", path)
    
    response = requests.get(BASE_URL + path, headers=headers, params=params)
    
    if response.status_code == 200:
        markets = response.json().get('markets', [])
        return markets
    else:
        print(f"Error {response.status_code}: {response.text}")
        return []

def get_market_prob(ticker):
    path = f"/markets/{ticker}"
    headers = kalshi_auth_headers("GET", path)
    
    response = requests.get(BASE_URL + path, headers=headers)
    
    if response.status_code == 200:
        market = response.json().get('market', {})
        yes_bid = market.get('yes_bid', 0) / 100.0
        yes_ask = market.get('yes_ask', 0) / 100.0
        return (yes_bid + yes_ask) / 2
    else:
        print(f"Error fetching prob for {ticker}: {response.status_code} - {response.text}")
        return None

def get_current_btc_price():
    try:
        resp = requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD")
        resp.raise_for_status()
        data = resp.json()
        if data['error']:
            raise Exception(data['error'])
        return float(data['result']['XXBTZUSD']['c'][0])
    except Exception as e:
        print(f"Error fetching BTC price from Kraken: {e}")
        return None

def get_btc_price_at_time(dt):
    unix = int(dt.timestamp()) - 3600  # Fetch last hour to be safe
    try:
        resp = requests.get("https://api.kraken.com/0/public/OHLC?pair=XXBTZUSD&interval=1&since=" + str(unix))
        resp.raise_for_status()
        data = resp.json()
        if data['error']:
            raise Exception(data['error'])
        ohlc = data['result']['XXBTZUSD']
        open_unix = int(dt.replace(second=0, microsecond=0).timestamp())  # Minute start
        for candle in ohlc:
            if candle[0] == open_unix:
                return float(candle[1])  # Use open price of the minute
        return None
    except Exception as e:
        print(f"Error fetching historical BTC price: {e}")
        return None

def compute_implied_vol(S, K, T, market_prob, r=RISK_FREE_RATE, q=DIVIDEND_YIELD, guess=0.5):
    if T < 1e-6:  # Too small → skip or return None
        return None
    def objective(vol):
        if vol <= 0:
            return 1.0
        d1 = (np.log(S / K) + (r - q + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
        d2 = d1 - vol * np.sqrt(T)
        model_prob = norm.cdf(d2)
        return model_prob - market_prob
    
    try:
        # Use bounded solver for stability
        sol = root_scalar(objective, bracket=[0.01, 5.0], x0=guess, method='brentq')
        if sol.converged:
            return sol.root
        else:
            return None
    except:
        return None
        
def compute_fair_prob(current_price, strike, time_to_expiry, vol=IMPLIED_VOL, r=RISK_FREE_RATE, q=DIVIDEND_YIELD):
    """
    Calculates the "fair" probability of finishing above strike using a Black-Scholes-like model for binary option.
    time_to_expiry: in years (e.g., 15 minutes = 15/1440/365 ≈ 0.000285)
    vol: annualized volatility (e.g., 0.42 for 42%)
    """
    if time_to_expiry <= 0:
        return 1.0 if current_price > strike else 0.0
    
    ln_ratio = np.log(current_price / strike)
    d1 = (ln_ratio + (r - q + 0.5 * vol**2) * time_to_expiry) / (vol * np.sqrt(time_to_expiry))
    d2 = d1 - vol * np.sqrt(time_to_expiry)
    fair_prob = norm.cdf(d2)  # Correct: Probability of finishing above strike (binary call)
    return fair_prob


def place_order(ticker, side, price):
    global last_market, trade_placed
    import uuid, time, requests
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    import base64
    API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
    KEY_PATH = "/home/colton/.openclaw/workspace/secrets/kalshi.pem"
    BASE = "https://api.elections.kalshi.com"
    ts = str(int(time.time() * 1000))
    path = "/trade-api/v2/portfolio/orders"
    msg = f"{ts}POST{path}"
    with open(KEY_PATH, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)
    sig = pk.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
    h = {"KALSHI-ACCESS-KEY": API_KEY, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(), "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}
    data = {"ticker": ticker, "action": "buy" if side == "yes" else "sell", "side": side, "count": 5, "type": "limit", f"{side}_price": int(price), "client_order_id": str(uuid.uuid4())}
    r = requests.post(BASE + path, headers=h, json=data)
    print(f"*** ORDER: {r.status_code} {r.text[:80]} ***")
    trade_placed = True
    last_market = ticker

def compute_correlation_and_lag():
    if len(btc_prices) < MIN_SAMPLES:
        return None, None, None
    
    btc = np.array(btc_prices[-CORR_WINDOW:])
    prob = np.array(kalshi_probs[-CORR_WINDOW:])
    
    delta_btc = np.diff(btc)
    delta_prob = np.diff(prob)
    
    min_len = min(len(delta_btc), len(delta_prob))
    delta_btc = delta_btc[:min_len]
    delta_prob = delta_prob[:min_len]
    
    if min_len < 2:
        return None, None, None
    
    corr = np.correlate(delta_prob, delta_btc, mode='full')
    lags = np.arange(-min_len + 1, min_len)
    
    max_idx = np.argmax(corr)
    best_lag = lags[max_idx]
    best_corr = corr[max_idx] / min_len
    
    time_delta = best_lag * INTERVAL
    return best_corr, best_lag, time_delta

# Main monitoring loop
print("Starting BTC 15-min monitoring script...")
while True:
    current_time = time.time()
    btc_price = get_current_btc_price()
    markets = get_open_btc15m_markets()
    
    if markets and btc_price is not None:
        # Auto-detect current market (soonest closing)
        markets.sort(key=lambda m: datetime.fromisoformat(m['close_time'].replace('Z', '+00:00')))
        market = markets[0]  # Earliest close_time
        
        ticker = market['ticker']
        if ticker != current_market_ticker:
            current_market_ticker = ticker
            open_time_str = market.get('open_time')
            if open_time_str:
                open_dt = datetime.fromisoformat(open_time_str.replace('Z', '+00:00'))
                reference_price = get_btc_price_at_time(open_dt) or btc_price
            else:
                reference_price = btc_price
            print(f"New market {current_market_ticker}, reference BTC: ${reference_price:.2f}")
        
        # Get actual strike from Kalshi (floor_strike if available, else reference)
        # Try common fields; print market once if needed to inspect
        strike = None
        if 'strike_level' in market:
            strike = float(market['strike_level'])
        elif 'threshold' in market:
            strike = float(market['threshold'])
        elif 'floor_strike' in market and market['floor_strike'] is not None:
            strike = float(market['floor_strike'])
        else:
            # Fallback: parse from ticker (e.g., last part after '-')
            try:
                strike_str = ticker.split('-')[-1]
                strike = float(strike_str) if strike_str.isdigit() else reference_price
            except:
                strike = reference_price

        print(f"Using strike: ${strike:.2f} (from API/ticker parse)")      
        #print(f"Strike source: field='{strike}' (full market keys: {list(market.keys())}")  # Temporarily, then comment out
        
        kalshi_prob = get_market_prob(ticker)
        if kalshi_prob is not None:
            timestamps.append(current_time)
            btc_prices.append(btc_price)
            kalshi_probs.append(kalshi_prob)
            
            print(f"[{datetime.fromtimestamp(current_time)}] BTC: ${btc_price:.2f}, Kalshi Prob Up: {kalshi_prob:.4f}")
            
            # Fair Prob Calculation
            close_time_str = market['close_time']
            close_dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            current_utc = datetime.fromtimestamp(current_time, tz=timezone.utc)
            time_to_expiry = (close_dt - current_utc).total_seconds() / (365.25 * 24 * 3600)  # In years

            if time_to_expiry <= 0:
                fair_prob = 1.0 if btc_price > strike else 0.0
            else:
                fair_prob = compute_fair_prob(btc_price, strike, time_to_expiry)
                
            iv = compute_implied_vol(btc_price, strike, time_to_expiry, kalshi_prob)
            if iv is not None and 0.1 < iv < 2.0:  # Reasonable range
                print(f"Implied Vol to match Kalshi: {iv:.2%}")
            else:
                print("Implied Vol: N/A (near expiry or numerical issue)")

            mispricing = fair_prob - kalshi_prob
            minutes_left = time_to_expiry * 365.25 * 24 * 60
            print(f"Fair Prob Up: {fair_prob:.4f} (mispricing: {mispricing:+.4f}) | ~{minutes_left:.1f} min left")
            if abs(mispricing) > 0.06 and time_to_expiry > 300 / (365.25 * 86400):  # >5 min
                direction = "YES" if mispricing > 0 else "NO"
                print(f"*** EDGE ALERT: Mispricing {mispricing:+.4f} → Consider {direction} ***")
            
            # Detect opportunity using strike
            if strike is not None:
                delta_btc_from_strike = btc_price - strike
                if delta_btc_from_strike > MOVE_THRESHOLD and kalshi_prob < 0.5 + PROB_LAG_THRESHOLD:
                    print("Opportunity: BTC up from strike, Kalshi lagging - Consider buying YES")
                    # Uncomment to place real order
                    place_order(ticker, "yes", 10)
                elif delta_btc_from_strike < -MOVE_THRESHOLD and kalshi_prob > 0.5 - PROB_LAG_THRESHOLD:
                    print("Opportunity: BTC down from strike, Kalshi lagging - Consider buying NO")
                    place_order(ticker, "no", 10)
                    
            if abs(mispricing) > 0.08 and time_to_expiry > 5/(365.25*24*3600):  # >5 min left
                print(f"*** Large mispricing detected: {mispricing:+.4f} ***")
            
            # Compute and print correlation if enough data
            corr, lag, delta = compute_correlation_and_lag()
            if corr is not None:
                print(f"Correlation: {corr:.4f}, Best Lag: {lag} samples, Time Delta: {delta} seconds")
                if lag > 0:
                    print("Kalshi moves lead BTC moves.")
                elif lag < 0:
                    print("BTC moves lead Kalshi moves.")
                else:
                    print("Moves are synchronous.")
    
    time.sleep(INTERVAL)