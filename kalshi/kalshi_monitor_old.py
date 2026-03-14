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
from scipy.optimize import fsolve, root_scalar

# --- CONFIGURATION ---
API_KEY_ID = "7c519784-3932-46e6-8547-fa945541304e"
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

# ==================== DATA LOGGING ====================
import csv
import os

DATA_FILE = "/home/colton/.openclaw/workspace/kalshi/data.csv"

def init_data_file():
    """Initialize CSV file for data logging."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'btc_price', 'btc_volume', 'eth_price', 'kalshi_prob', 'fair_prob', 'strike', 'mispricing', 'iv', 'minutes_left', 'direction'])

def log_data(timestamp, btc_price, btc_volume, eth_price, kalshi_prob, fair_prob, strike, mispricing, iv, minutes_left):
    """Log data point to CSV."""
    direction = "YES" if mispricing > 0.15 else ("NO" if mispricing < -0.06 else "HOLD")
    with open(DATA_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, btc_price, eth_price, kalshi_prob, fair_prob, strike, mispricing, iv, minutes_left, direction])

# Paper Trading
TRADES_FILE = "/home/colton/.openclaw/workspace/kalshi/trades.csv"

def init_trades_file():
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['entry_time', 'ticker', 'direction', 'entry_price', 'strike', 'kalshi_prob', 'fair_prob', 'mispricing', 'exit_time', 'exit_price', 'outcome', 'pnl'])

def log_paper_trade(ticker, direction, entry_price, strike, kalshi_prob, fair_prob, mispricing):
    with open(TRADES_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([time.time(), ticker, direction, entry_price, strike, kalshi_prob, fair_prob, mispricing, '', '', '', ''])
    log(f"PAPER: {direction} at ${entry_price} mispricing:{mispricing:.2%}", "TRADE")


def analyze_performance():
    """Analyze logged data for prediction accuracy."""
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if len(rows) < 10:
        return
    edge_yes = [r for r in rows if r['direction'] == 'YES']
    edge_no = [r for r in rows if r['direction'] == 'NO']
    log(f"Analysis: {len(edge_yes)} YES signals, {len(edge_no)} NO signals", "ANALYSIS")

# Initialize on startup
init_data_file()
init_trades_file()

# Data storage
timestamps = []
btc_prices = []
eth_prices = []
kalshi_probs = []
current_market_ticker = None
reference_price = None

# Logging
def get_ml_direction(fair_prob, kalshi_prob, mispricing, minutes_left, iv):
    """Use ML model for direction."""
    try:
        import pickle, numpy as np
        try:
            with open("/home/colton/.openclaw/workspace/kalshi/model.pkl", "rb") as f:
                m = pickle.load(f)
            model, scaler = m["model"], m["scaler"]
            X = np.array([[fair_prob, kalshi_prob, mispricing, minutes_left, iv, 0]])
            X_scaled = scaler.transform(X)
            pred = model.predict(X_scaled)[0]
            prob = model.predict_proba(X_scaled)[0][1]
            if prob > 0.55:
                return "YES" if pred == 1 else "NO"
        pass
    return "HOLD"

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}")

# Load the Private Key for signing
try:
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    print(f"Loaded private key from {PRIVATE_KEY_PATH}")
except Exception as e:
    print(f"Error loading private key: {e}")
    print("Make sure to copy your .pem file to the secrets folder")
    private_key = None

def kalshi_auth_headers(method, path):
    """Generates the required RSA-PSS signature headers for Kalshi."""
    if private_key is None:
        return {"Error": "No private key loaded"}
    
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
    if "Error" in headers:
        return []
    
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
        return None, None

def get_btc_price_and_volume():
    """Get current BTC price and volume from Kraken."""
    try:
        resp = requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['error']:
            raise Exception(data['error'])
        price = float(data['result']['XXBTZUSD']['c'][0])
        volume = float(data['result']['XXBTZUSD']['v'][1])
        return price, volume
    except Exception as e:
        print(f"[ERROR] Failed to get BTC price: {e}")
        return None, None

def get_current_eth_price():
    """Get current ETH price from Kraken."""
    try:
        resp = requests.get("https://api.kraken.com/0/public/Ticker?pair=XETHZUSD", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data['error']:
            raise Exception(data['error'])
        return float(data['result']['XETHZUSD']['c'][0])
    except Exception as e:
        print(f"[ERROR] Failed to get ETH price: {e}")
        return None, None

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
        return None, None
    except Exception as e:
        print(f"Error fetching historical BTC price: {e}")
        return None, None

def compute_implied_vol(S, K, T, market_prob, r=RISK_FREE_RATE, q=DIVIDEND_YIELD, guess=0.5):
    if T < 1e-6:  # Too small → skip or return None, None
        return None, None
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
            return None, None
    except:
        return None, None
        
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

def compute_correlation_and_lag():
    if len(btc_prices) < MIN_SAMPLES:
        return None, None, None, None
    
    btc = np.array(btc_prices[-CORR_WINDOW:])
    prob = np.array(kalshi_probs[-CORR_WINDOW:])
    
    delta_btc = np.diff(btc)
    delta_prob = np.diff(prob)
    
    min_len = min(len(delta_btc), len(delta_prob))
    delta_btc = delta_btc[:min_len]
    delta_prob = delta_prob[:min_len]
    
    if min_len < 2:
        return None, None, None, None
    
    corr = np.correlate(delta_prob, delta_btc, mode='full')
    lags = np.arange(-min_len + 1, min_len)
    
    max_idx = np.argmax(corr)
    best_lag = lags[max_idx]
    best_corr = corr[max_idx] / min_len
    
    time_delta = best_lag * INTERVAL
    return best_corr, best_lag, time_delta

# Main monitoring loop
print("Starting BTC 15-min monitoring script...")
print("Press Ctrl+C to stop")
log("Monitor starting", "START")

while True:
    try:
        current_time = time.time()
        btc_data = get_btc_price_and_volume()
        btc_price, btc_volume = btc_data if btc_data else (None, None)
        eth_price = get_current_eth_price()
        markets = get_open_btc15m_markets()
        
        if not markets:
            log("No 15-min BTC markets open, waiting...", "WARN")
            time.sleep(INTERVAL)
            continue
            
        if markets and btc_price is not None:
            eth_str = f"${eth_price:.2f}" if eth_price else "N/A"
            log(f"BTC: ${btc_price:.2f} | ETH: {eth_str}", "DATA")
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
                print(f"\n=== New market {current_market_ticker}, reference BTC: ${reference_price:.2f} ===")
            
            # Get actual strike from Kalshi
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

            print(f"Strike: ${strike:.2f}")      
            
            kalshi_prob = get_market_prob(ticker)
            if kalshi_prob is not None:
                timestamps.append(current_time)
                btc_prices.append(btc_price)
                eth_prices.append(eth_price)
                kalshi_probs.append(kalshi_prob)
                
                eth_str = f"${eth_price:.2f}" if eth_price else "N/A"
                print(f"[{datetime.fromtimestamp(current_time)}] BTC: ${btc_price:.2f}, ETH: {eth_str}, Kalshi Prob Up: {kalshi_prob:.4f}")
                
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
                # log_data called after minutes_left defined
                minutes_left = time_to_expiry * 365.25 * 24 * 60
                log_data(current_time, btc_price, btc_volume, eth_price, kalshi_prob, fair_prob, strike, mispricing, iv if iv else 0, minutes_left)
                print(f"Fair Prob Up: {fair_prob:.4f} (mispricing: {mispricing:+.4f}) | ~{minutes_left:.1f} min left")
                # Use ML model for direction
                ml_direction = get_ml_direction(fair_prob, kalshi_prob, mispricing, minutes_left, iv if iv else 0.5)
                if ml_direction in ["YES", "NO"]:
                    direction = ml_direction
                    log(f"ML SIGNAL: {direction}", "ML")
                if abs(mispricing) > 0.08:  # Strong signal - 8% threshold and time_to_expiry > 300 / (365.25 * 86400):  # >5 min
                    direction = "YES" if mispricing > 0 else "NO"
                    log(f"PAPER TRADE SIGNAL: {direction} mispricing={mispricing:+.4f}", "TRADE")
                # Log the signal
                log_paper_trade(ticker, direction, btc_price, strike, kalshi_prob, fair_prob, mispricing)
                
                # detect opportunity using strike
                if strike is not None:
                    delta_btc_from_strike = btc_price - strike
                    if delta_btc_from_strike > MOVE_THRESHOLD and kalshi_prob < 0.5 + PROB_LAG_THRESHOLD:
                        print(">>> Opportunity: BTC up from strike, Kalshi lagging - Consider buying YES")
                    elif delta_btc_from_strike < -MOVE_THRESHOLD and kalshi_prob > 0.5 - PROB_LAG_THRESHOLD:
                        print(">>> Opportunity: BTC down from strike, Kalshi lagging - Consider buying NO")
                        
                if abs(mispricing) > 0.10 and time_to_expiry > 5/(365.25*24*3600):  # >5 min left
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
    except KeyboardInterrupt:
        print("\nStopping...")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(INTERVAL)

# ==================== BACKTESTER ====================
def run_backtest():
    """
    Backtest the strategy using historical data.
    """
    import json
    from datetime import timedelta
    
    log("Starting backtest...", "BACKTEST")
    
    # Load historical data if available
    # For now, simulate using stored data
    if len(btc_prices) < 10:
        log("Not enough data for backtest. Need at least 10 samples.", "WARN")
        return
    
    # Simple strategy: buy when fair_prob > kalshi_prob + threshold
    THRESHOLD = 0.05
    
    trades = []
    for i in range(1, len(kalshi_probs)):
        fair = compute_fair_prob(
            btc_prices[i], 
            strike, 
            15/(365.25*24*60),  # 15 min
            vol=IMPLIED_VOL
        )
        kalshi = kalshi_probs[i]
        
        if fair - kalshi > THRESHOLD:
            trades.append({"time": i, "action": "BUY_YES", "fair": fair, "kalshi": kalshi})
        elif kalshi - fair > THRESHOLD:
            trades.append({"time": i, "action": "BUY_NO", "fair": fair, "kalshi": kalshi})
    
    log(f"Backtest: {len(trades)} potential trades found", "BACKTEST")
    
    if trades:
        print("\n=== BACKTEST RESULTS ===")
        for t in trades[:10]:
            print(f"  {t}")
    
    return trades

def compute_eth_btc_correlation():
    """Compute correlation between ETH moves and BTC moves."""
    if len(eth_prices) < 10 or len(btc_prices) < 10:
        return None, None
    
    btc = np.array(btc_prices[-CORR_WINDOW:])
    eth = np.array(eth_prices[-CORR_WINDOW:])
    
    delta_btc = np.diff(btc)
    delta_eth = np.diff(eth)
    
    if len(delta_btc) < 2:
        return None, None
    
    corr = np.corrcoef(delta_btc, delta_eth)[0, 1]
    return corr

# ==================== ANALYSIS ====================
def run_analysis():
    """Analyze logged data for strategy performance."""
    import os
    if not os.path.exists(DATA_FILE):
        log("No data file found", "ANALYZE")
        return
    
    with open(DATA_FILE, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if len(rows) < 5:
        log(f"Only {len(rows)} samples, need more", "ANALYZE")
        return
    
    # Analyze by direction
    yes_signals = [r for r in rows if r['direction'] == 'YES']
    no_signals = [r for r in rows if r['direction'] == 'NO']
    hold_signals = [r for r in rows if r['direction'] == 'HOLD']
    
    # Calculate average mispricing
    yes_mispricing = [float(r['mispricing']) for r in yes_signals] if yes_signals else []
    no_mispricing = [float(r['mispricing']) for r in no_signals] if no_signals else []
    
    print("\n" + "="*50)
    print("=== STRATEGY ANALYSIS ===")
    print(f"Total samples: {len(rows)}")
    print(f"YESSignals: {len(yes_signals)} (avg mispricing: {sum(yes_mispricing)/len(yes_mispricing):.3f})")
    print(f"NO Signals: {len(no_signals)} (avg mispricing: {sum(no_mispricing)/len(no_mispricing):.3f})")
    print(f"HOLD: {len(hold_signals)}")
    
    # Calculate edge strength
    avg_mispricing = sum([float(r['mispricing']) for r in rows]) / len(rows)
    print(f"\nAvg Mispricing: {avg_mispricing:.4f}")
    
    # Look for patterns
    high_mispricing = [r for r in rows if abs(float(r['mispricing'])) > 0.08]
    print(f"High Mispricing (>8%): {len(high_mispricing)}")
    
    print("="*50 + "\n")

# Run analysis every 5 minutes
if len(kalshi_probs) > 0 and len(kalshi_probs) % 10 == 0:
    run_analysis()

# ==================== PAPER TRADING LOG ====================
TRADES_FILE = "/home/colton/.openclaw/workspace/kalshi/trades.csv"

def init_trades_file():
    import os
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['entry_time', 'ticker', 'direction', 'entry_price', 'strike', 'kalshi_prob', 'fair_prob', 'mispricing', 'exit_time', 'exit_price', 'outcome', 'pnl'])

def log_paper_trade(ticker, direction, entry_price, strike, kalshi_prob, fair_prob, mispricing):
    """Log a paper trade entry."""
    with open(TRADES_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([time.time(), ticker, direction, entry_price, strike, kalshi_prob, fair_prob, mispricing, '', '', '', ''])
    log(f"PAPER TRADE: {direction} at ${entry_price}", "TRADE")

# Initialize
init_trades_file()

# ==================== ML MODEL ====================
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import numpy as np
import pickle

# Train model on existing data
def train_model():
    import csv
    with open(DATA_FILE) as f:
        data = list(csv.DictReader(f))
    
    X = []
    y = []
    
    for i, r in enumerate(data):
        if i < len(data) - 30 and float(r['minutes_left']) > 2:
            try:
                strike = float(r['strike'])
                fair = float(r['fair_prob'])
                kalshi = float(r['kalshi_prob'])
                mis = float(r['mispricing'])
                mins = float(r['minutes_left'])
                iv = float(r.get('iv', 0.5) or 0.5)
                
                # Get outcome
                outcome = None
                for j in range(i+1, min(i+30, len(data))):
                    if abs(float(data[j]['strike']) - strike) < 1:
                        outcome = 1 if float(data[j]['btc_price']) > strike else 0
                        break
                
                if outcome is not None:
                    X.append([fair, kalshi, mis, mins, iv, 0])  # volume = 0 for now
                    y.append(outcome)
            except:
                pass
    
    if len(X) > 100:
        X = np.array(X)
        y = np.array(y)
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = GradientBoostingClassifier(n_estimators=100, max_depth=3)
        model.fit(X_scaled, y)
        
        # Save
        with open('/home/colton/.openclaw/workspace/kalshi/model.pkl', 'wb') as f:
            pickle.dump({'model': model, 'scaler': scaler}, f)
        
        return model, scaler
    return None, None

# Try load or train
try:
    with open('/home/colton/.openclaw/workspace/kalshi/model.pkl', 'rb') as f:
        m = pickle.load(f)
        ML_MODEL = m['model']
        ML_SCALER = m['scaler']
    log("ML Model loaded", "ML")
except:
    log("Training ML model...", "ML")
    ML_MODEL, ML_SCALER = train_model()
    if ML_MODEL:
        log("ML Model trained", "ML")

def get_ml_prediction(fair_prob, kalshi_prob, mispricing, minutes_left, iv):
    if ML_MODEL is None:
        return None
    try:
        features = np.array([[fair_prob, kalshi_prob, mispricing, minutes_left, iv, 0]])
        features_scaled = ML_SCALER.transform(features)
        pred = ML_MODEL.predict(features_scaled)[0]
        prob = ML_MODEL.predict_proba(features_scaled)[0][1]
        return pred, prob
    except:
        return None

# Run training on startup
if ML_MODEL is None:
    train_model()

def get_ml_direction(fair_prob, kalshi_prob, mispricing, minutes_left, iv):
    """Use ML model for trading decisions."""
    pred = get_ml_prediction(fair_prob, kalshi_prob, mispricing, minutes_left, iv)
    if pred is None:
        return "HOLD"
    direction, confidence = pred
    if confidence > 0.55:  # Only trade when >55% confidence
        return "YES" if direction == 1 else "NO"
    return "HOLD"

# === ML PREDICTIONS ===
def get_ml_prediction(fair_prob, kalshi_prob, mispricing, minutes_left, iv):
    try:
        import pickle, numpy as np
        with open('/home/colton/.openclaw/workspace/kalshi/model.pkl', 'rb') as f:
            m = pickle.load(f)
        model = m['model']
        scaler = m['scaler']
        X = np.array([[fair_prob, kalshi_prob, mispricing, minutes_left, iv, 0]])
        X_s = scaler.transform(X)
        pred = model.predict(X_s)[0]
        prob = model.predict_proba(X_s)[0][1]
        if prob > 0.55:
            return "YES" if pred == 1 else "NO"
    except:
        pass
    return "HOLD"

# Replace direction calculation with ML in main loop
