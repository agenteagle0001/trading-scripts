#!/usr/bin/env python3
"""Executor - combines signals and decides to trade"""

import pickle, requests, re, numpy as np, time, json
from datetime import datetime
from scipy.stats import norm
from scipy.optimize import root_scalar
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import base64, uuid

API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
KEY_PATH = "/home/colton/.openclaw/workspace/secrets/kalshi.pem"
MODEL_PATH = "/home/colton/.openclaw/workspace/kalshi/model.pkl"
MODEL_V2_PATH = "/home/colton/.openclaw/workspace/kalshi/model_v2.pkl"
TRAINING_LOG = "/home/colton/.openclaw/workspace/kalshi/ml_training_log.json"
STATE_FILE = "/home/colton/.openclaw/workspace/kalshi/executor_state.json"
TRADE_LOG = "/home/colton/.openclaw/workspace/kalshi/trade_log.json"

TARGET_DOLLAR = 4.00  # Fixed position size per trade
RISK_FREE = 0.05
IMPLIED_VOL = 0.55

# Cache for Kraken candles
_candle_cache = None
_candle_cache_time = 0

def get_kraken_candles(force_refresh=False):
    """Get Kraken 15-min candles, cached for 5 minutes"""
    global _candle_cache, _candle_cache_time
    if _candle_cache is not None and not force_refresh and time.time() - _candle_cache_time < 300:
        return _candle_cache
    
    try:
        r = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15", timeout=10)
        data = r.json()["result"]["XXBTZUSD"]
        candles = {}
        for c in data:
            ts = int(c[0])
            candles[ts] = {"open": float(c[1]), "close": float(c[4]), "high": float(c[2]), "low": float(c[3])}
        _candle_cache = candles
        _candle_cache_time = time.time()
        return candles
    except Exception as e:
        print(f"Kraken candles error: {e}")
        return _candle_cache if _candle_cache else {}

def get_btc_momentum():
    """Get BTC momentum features over prior candles"""
    candles = get_kraken_candles()
    if not candles:
        return {"momentum_15min": 0, "momentum_45min": 0, "btc_direction": 0, "btc_change": 0}
    
    sorted_ts = sorted(candles.keys())
    if len(sorted_ts) < 5:
        return {"momentum_15min": 0, "momentum_45min": 0, "btc_direction": 0, "btc_change": 0}
    
    # Most recent candle
    latest_ts = sorted_ts[-1]
    latest = candles[latest_ts]
    
    # 15-min momentum (last candle return)
    mom_15 = (latest["close"] - latest["open"]) / latest["open"]
    
    # 45-min momentum (last 3 candles)
    mom_45 = 0
    if len(sorted_ts) >= 3:
        start_ts = sorted_ts[-3]
        start_close = candles[start_ts]["close"]
        mom_45 = (latest["close"] - start_close) / start_close
    
    # BTC direction (current candle)
    btc_dir = 1 if latest["close"] > latest["open"] else 0
    btc_change = mom_15
    
    return {
        "momentum_15min": mom_15,
        "momentum_45min": mom_45,
        "btc_direction": btc_dir,
        "btc_change": btc_change
    }

def get_order_flow_signal():
    """Get order flow signal from Kraken"""
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5)
        data = r.json()['result']['XXBTZUSD']
        best_bid = float(data['b'][0])
        best_ask = float(data['a'][0])
        last_price = float(data['c'][0])
        mid = (best_bid + best_ask) / 2
        position = (last_price - mid) / mid
        if position > 0.001:
            return "BULLISH"
        elif position < -0.001:
            return "BEARISH"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def get_realized_vol():
    """Get 24h realized volatility from Kraken"""
    try:
        r = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60")
        candles = r.json()['result']['XXBTZUSD']
        closes = [float(c[4]) for c in candles[-25:]]
        returns = np.diff(np.log(closes))
        return np.std(returns) * np.sqrt(24 * 365)
    except:
        return 0.55

def compute_implied_vol(S, K, T, market_prob, r=RISK_FREE, guess=0.5):
    """Calculate IV from market price"""
    def objective(vol):
        try:
            d1 = (np.log(S/K) + (r + vol**2/2)*T) / (vol*np.sqrt(T))
            d2 = d1 - vol*np.sqrt(T)
            fair = norm.cdf(d1)
            return fair - market_prob
        except:
            return 0
    try:
        sol = root_scalar(objective, bracket=[0.01, 3.0], x0=guess)
        return sol.root if sol.converged else None
    except:
        return None

def compute_fair_prob(S, K, T, vol=IMPLIED_VOL, r=RISK_FREE):
    """Compute fair probability using Black-Scholes"""
    try:
        if T <= 0 or vol <= 0:
            return 0.5
        d1 = (np.log(S/K) + (r + vol**2/2)*T) / (vol*np.sqrt(T))
        return norm.cdf(d1)
    except:
        return 0.5

def load_training_log():
    """Load training data log"""
    try:
        with open(TRAINING_LOG) as f:
            return json.load(f)
    except:
        return {"signals": []}

def save_training_log(log):
    """Save training data log"""
    with open(TRAINING_LOG, "w") as f:
        json.dump(log, f, indent=2)

def log_signal(signal_data):
    """Log signal data for future model training"""
    log = load_training_log()
    log["signals"].append({
        "timestamp": datetime.now().isoformat(),
        **signal_data
    })
    # Keep last 10000 entries
    if len(log["signals"]) > 10000:
        log["signals"] = log["signals"][-10000:]
    save_training_log(log)

def get_all_signals():
    """Get all trading signals including momentum features"""
    # Load V2 model if available, else fallback to V1
    try:
        with open(MODEL_V2_PATH, "rb") as f:
            model_data = pickle.load(f)
        model_v2 = model_data["model"]
        scaler_v2 = model_data["scaler"]
        use_v2 = True
    except:
        use_v2 = False
    
    # Get BTC data
    btc = requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD").json()
    btc_price = float(btc['result']['XXBTZUSD']['c'][0])
    
    # Get current market
    markets = requests.get("https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open", 
                         headers={"apikey": API_KEY}).json()['markets']
    market = markets[0]
    ticker = market['ticker']
    strike = float(market.get('floor_strike', btc_price))
    
    # Parse time to expiry from ticker (format: KXBTC15M-YYMMDDHHMM-TYPE)
    tte_minutes = 15  # default 15-min contracts
    m = re.search(r'-(\d{2})(\w{3})(\d{2})(\d{4})-', ticker)
    if m:
        yy, mon, dd, hhmm = m.group(1), m.group(2), m.group(3), m.group(4)
        months = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
        try:
            expiry_dt = datetime(int("20"+yy), months[mon.upper()], int(dd), int(hhmm[:2]), int(hhmm[2:]))
            tte_minutes = max(1, min(120, (expiry_dt - datetime.now()).total_seconds() / 60))
        except:
            pass
    
    yes_bid = float(market.get('yes_bid_dollars', 50) or 50)
    yes_ask = float(market.get('yes_ask_dollars', 50) or 50)
    kalshi_prob = (yes_bid + yes_ask) / 2
    
    T = 15 / (365.25 * 24 * 4)
    vol = get_realized_vol()
    fair_prob = compute_fair_prob(btc_price, strike, T, vol)
    mispricing = fair_prob - kalshi_prob
    
    # Get BTC momentum
    momentum = get_btc_momentum()
    
    # V1 model prediction (old tautology model)
    try:
        with open(MODEL_PATH, "rb") as f:
            m = pickle.load(m)
        model_v1, scaler_v1 = m["model"], m["scaler"]
        X_v1 = scaler_v1.transform([[fair_prob, kalshi_prob, mispricing, 15, vol]])
        pred_v1 = model_v1.predict(X_v1)[0]
        conf_v1 = model_v1.predict_proba(X_v1)[0][1]
    except:
        pred_v1, conf_v1 = 1, 0.5
    
    # V2 model prediction (momentum-based)
    ml_direction_v2 = None
    ml_confidence_v2 = None
    if use_v2:
        try:
            X_v2 = scaler_v2.transform([[fair_prob, kalshi_prob, momentum["momentum_15min"], momentum["momentum_45min"],
                                        tte_minutes / 120.0]])
            pred_v2 = model_v2.predict(X_v2)[0]
            conf_v2 = model_v2.predict_proba(X_v2)[0][1]
            ml_direction_v2 = "YES" if pred_v2 == 1 else "NO"
            ml_confidence_v2 = conf_v2
        except Exception as e:
            print(f"V2 model error: {e}")
            ml_direction_v2 = None
            ml_confidence_v2 = None
    
    # Log signal data for training
    log_signal({
        "ticker": ticker,
        "btc_price": btc_price,
        "strike": strike,
        "fair_prob": fair_prob,
        "kalshi_prob": kalshi_prob,
        "mispricing": mispricing,
        "momentum_15min": momentum["momentum_15min"],
        "momentum_45min": momentum["momentum_45min"],
        "btc_direction": momentum["btc_direction"],
        "entry_price": kalshi_prob,
        "ml_direction_v1": "YES" if pred_v1 == 1 else "NO",
        "ml_confidence_v1": conf_v1,
        "ml_direction_v2": ml_direction_v2,
        "ml_confidence_v2": ml_confidence_v2,
        "tte_minutes": tte_minutes,
    })
    
    return {
        'ticker': ticker,
        'btc': btc_price,
        'strike': strike,
        'fair': fair_prob,
        'kalshi': kalshi_prob,
        'tte_minutes': tte_minutes,
        'mispricing': mispricing,
        'momentum_15min': momentum["momentum_15min"],
        'momentum_45min': momentum["momentum_45min"],
        'btc_direction': momentum["btc_direction"],
        'ml_direction': "YES" if pred_v1 == 1 else "NO",
        'ml_confidence': conf_v1,
        'ml_direction_v2': ml_direction_v2,
        'ml_confidence_v2': ml_confidence_v2,
    }

def get_ml_signal_v2(signals):
    """Get trading signal from V2 model (momentum-based)"""
    if signals['ml_direction_v2'] is None:
        return None, 0
    
    # Strategy: 
    # - YES when fair_prob >= 0.55 AND momentum_45min > 0
    # - NO when fair_prob < 0.45 AND momentum_45min < 0
    fair = signals['fair']
    mom45 = signals['momentum_45min']
    conf = signals['ml_confidence_v2']
    
    if fair >= 0.55 and mom45 > 0:
        return "YES", conf
    elif fair < 0.45 and mom45 < 0:
        return "NO", conf
    else:
        return None, conf  # No signal

def should_trade(signals, state):
    """Determine if we should trade based on signals"""
    # Check if we already have a position
    position = get_position()
    if position and position.get("ticker") == signals['ticker']:
        return None, "Already in position"
    
    # Get V2 signal
    ml_direction, ml_confidence = get_ml_signal_v2(signals)
    
    if ml_direction is None:
        return None, "No V2 signal"
    
    # Also check V1 + mispricing for confirmation
    ml_signal = signals['ml_confidence'] > 0.90
    mispricing_signal = abs(signals['mispricing']) > 0.25
    price_ok = signals['kalshi'] > 0.50
    
    order_flow = get_order_flow_signal()
    
    # V2 says YES
    if ml_direction == "YES":
        if ml_signal and mispricing_signal and price_ok and order_flow in ["BULLISH", "NEUTRAL"]:
            return "YES", f"V2 YES {ml_confidence:.0%} + V1 confirm"
        elif price_ok and signals['momentum_15min'] > 0:
            # V2-only trade with momentum filter
            return "YES", f"V2 YES {ml_confidence:.0%} (momentum filter)"
        return None, "V2 YES but filters failed"
    
    # V2 says NO
    elif ml_direction == "NO":
        if ml_signal and mispricing_signal and price_ok and order_flow in ["BEARISH", "NEUTRAL"]:
            return "NO", f"V2 NO {ml_confidence:.0%} + V1 confirm"
        return None, "V2 NO but filters failed"
    
    return None, "No signal"

# ===== Legacy functions for compatibility =====

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"last_market": None, "entry_price": None, "position": None}

def check_min_hold(state):
    if not state.get("entry_time"):
        return False
    if time.time() - state["entry_time"] < 120:
        return True
    return False

def check_stop_loss(signals, state, minutes_left=15):
    if not state.get("entry_price") or not state.get("position"):
        return None
    
    entry = state["entry_price"]
    current = signals["kalshi"]
    direction = state["position"]
    
    if direction == "yes":
        pnl_pct = (current - entry) / entry
    else:
        pnl_pct = (entry - current) / entry
    
    time_factor = max(0.5, min(2.0, minutes_left / 7.0))
    adjusted_stop = 0.20 * time_factor
    
    if pnl_pct > 0.20:
        return "TAKE_PROFIT"
    if pnl_pct < -adjusted_stop:
        return "STOP_LOSS"
    return None

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_position():
    """Check current position from Kalshi API"""
    try:
        ts = str(int(time.time() * 1000))
        path = "/trade-api/v2/portfolio/positions"
        msg = f"{ts}GET{path}"
        
        with open(KEY_PATH, "rb") as f:
            pk = serialization.load_pem_private_key(f.read(), password=None)
        sig = pk.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        
        h = {"KALSHI-ACCESS-KEY": API_KEY, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(), 
             "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}
        
        r = requests.get("https://api.elections.kalshi.com" + path, headers=h)
        if r.status_code == 200:
            data = r.json()
            for pos in data.get("market_positions", []):
                if float(pos.get("position_fp", 0)) > 0:
                    return {"ticker": pos["ticker"], "size": float(pos["position_fp"])}
    except Exception as e:
        print(f"Position check error: {e}")
    return None

def check_orders_in_market(ticker):
    """Check if there are OPEN orders in the current market"""
    try:
        ts = str(int(time.time() * 1000))
        path = "/trade-api/v2/portfolio/orders"
        msg = f"{ts}GET{path}"
        
        with open(KEY_PATH, "rb") as f:
            pk = serialization.load_pem_private_key(f.read(), password=None)
        sig = pk.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        
        h = {"KALSHI-ACCESS-KEY": API_KEY, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(), 
             "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}
        
        r = requests.get("https://api.elections.kalshi.com" + path, headers=h)
        if r.status_code == 200:
            orders = r.json().get("orders", [])
            for o in orders:
                if o.get("ticker") == ticker and o.get("status") in ["open", "pending"]:
                    return True
    except Exception as e:
        print(f"Order check error: {e}")
    return False

def execute_trade(ticker, direction, price):
    ts = str(int(time.time() * 1000))
    path = "/trade-api/v2/portfolio/orders"
    msg = f"{ts}POST{path}"
    
    with open(KEY_PATH, "rb") as f:
        pk = serialization.load_pem_private_key(f.read(), password=None)
    sig = pk.sign(msg.encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    
    h = {"KALSHI-ACCESS-KEY": API_KEY, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(), 
         "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}
    count = max(1, round(TARGET_DOLLAR / price))
    data = {"ticker": ticker, "action": "buy" if direction == "yes" else "sell", 
            "side": direction, "count": count, "type": "limit", f"{direction}_price": min(99, max(1, int(price * 100) + 1)), 
            "client_order_id": str(uuid.uuid4())}
    
    r = requests.post("https://api.elections.kalshi.com" + path, headers=h, json=data)
    return r.status_code, r.text, count

if __name__ == "__main__":
    signals = get_all_signals()
    state = load_state()
    
    print(f"\n=== Signals ===")
    print(f"Ticker: {signals['ticker']} (last: {state.get('last_market')})")
    print(f"Fair: {signals['fair']:.1%}, Kalshi: {signals['kalshi']:.1%}, Mis: {signals['mispricing']:+.1%}")
    print(f"V1 ML: {signals['ml_direction']} {signals['ml_confidence']:.0%}")
    print(f"V2 ML: {signals['ml_direction_v2']} {signals['ml_confidence_v2']:.0%}" if signals['ml_direction_v2'] else "V2 ML: N/A")
    print(f"Momentum: 15min={signals['momentum_15min']:+.3f}, 45min={signals['momentum_45min']:+.3f}, BTC_dir={signals['btc_direction']}")
    
    direction, reason = should_trade(signals, state)
    print(f"Decision: {direction} ({reason})")
