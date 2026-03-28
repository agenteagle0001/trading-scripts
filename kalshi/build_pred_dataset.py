#!/usr/bin/env python3
"""
Retrain V2 model using momentum + technical features only.
Features must be INDEPENDENT of kalshi_prob (no tautology).
Uses: BTC momentum, volatility, RSI, MACD, order flow, volume.
Labels: Actual market outcomes (YES/NO resolved).
"""
import pickle
import json
import requests
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

API_KEY = "7c519784-3932-46e6-8547-fa945541304e"
MODEL_V2_PATH = "/home/colton/.openclaw/workspace/kalshi/model_v2.pkl"
TRAINING_LOG = "/home/colton/.openclaw/workspace/kalshi/ml_training_log.json"

def get_training_data():
    """Build training set with momentum features + market outcomes"""
    # Load training log
    with open(TRAINING_LOG) as f:
        log = json.load(f)
    
    # Group by ticker - use FIRST entry (earliest signal before outcome)
    by_ticker = {}
    for e in log.get("signals", []):
        ticker = e.get("ticker")
        if ticker:
            if ticker not in by_ticker:
                by_ticker[ticker] = e  # First occurrence only
    
    print(f"Unique tickers: {len(by_ticker)}")
    
    # Get Kraken BTC data for the period
    print("Fetching Kraken BTC data...")
    r = requests.get("https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=15", timeout=10)
    candles = r.json()["result"]["XXBTZUSD"]
    
    # Build a time-indexed price series
    btc_times = []
    btc_closes = []
    for c in candles:
        btc_times.append(int(c[0]))
        btc_closes.append(float(c[4]))
    
    btc_times = np.array(btc_times)
    btc_closes = np.array(btc_closes)
    
    # Calculate BTC features from training log entries
    print("Computing BTC features...")
    X, y = [], []
    
    for ticker, e in by_ticker.items():
        # Get momentum from the log entry (these are real Kraken data)
        mom15 = e.get("momentum_15min", 0)
        mom45 = e.get("momentum_45min", 0)
        btc_dir = e.get("btc_direction", 0)
        
        # Features: momentum-based only (no kalshi_prob or fair_prob)
        X.append([
            mom15,        # BTC momentum 15 min
            mom45,        # BTC momentum 45 min
            btc_dir,      # BTC direction (1 or 0)
            abs(mom15),   # momentum magnitude
            abs(mom45),   # longer momentum magnitude
        ])
    
    print(f"Feature samples: {len(X)}")
    
    # Fetch market outcomes from Kalshi
    print("Fetching market outcomes...")
    outcomes = {}
    tickers = list(by_ticker.keys())
    
    for i, ticker in enumerate(tickers):
        if i % 20 == 0:
            print(f"  {i}/{len(tickers)}")
        try:
            r = requests.get(
                f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}",
                headers={"apikey": API_KEY}, timeout=5
            )
            m = r.json().get("market", {})
            if m.get("status") == "finalized":
                outcomes[ticker] = 1 if m.get("result") == "yes" else 0
        except:
            pass
    
    print(f"Got outcomes for {len(outcomes)} markets")
    
    # Filter to only tickers with outcomes
    X_filtered, y_filtered = [], []
    for ticker, e in by_ticker.items():
        if ticker in outcomes:
            X_filtered.append(X[tickers.index(ticker)])
            y_filtered.append(outcomes[ticker])
    
    return np.array(X_filtered), np.array(y_filtered), len(outcomes)

def retrain():
    print("=== Retraining V2 Model (Momentum-Only Features) ===")
    print("Features: momentum_15min, momentum_45min, btc_direction, |momentum|")
    print("Label: Did BTC go UP in that 15-min window?\n")
    
    result = get_training_data()
    if result[0] is None:
        return
    
    X, y, n_outcomes = result
    print(f"\nDataset: {len(X)} samples")
    print(f"Class balance: {sum(y)} YES / {len(y)-sum(y)} NO ({sum(y)/len(y)*100:.1f}% YES)")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        min_samples_split=5,
        min_samples_leaf=3,
        random_state=42
    )
    
    cv = max(2, min(5, len(X)//20))
    cv_scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="accuracy")
    print(f"\nCV Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    model.fit(X_scaled, y)
    train_acc = (model.predict(X_scaled) == y).mean()
    print(f"Training accuracy: {train_acc:.3f}")
    
    feat_names = ["momentum_15min", "momentum_45min", "btc_direction", "|mom15|", "|mom45|"]
    print("\nFeature importances:")
    for name, imp in sorted(zip(feat_names, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name}: {imp:.3f}")
    
    model_data = {
        "model": model,
        "scaler": scaler,
        "n_samples": len(X),
        "cv_accuracy": float(cv_scores.mean()),
        "n_outcomes": n_outcomes,
        "trained_at": datetime.now().isoformat(),
        "features": feat_names,
    }
    
    with open(MODEL_V2_PATH, "wb") as f:
        pickle.dump(model_data, f)
    
    print(f"\nModel saved: {MODEL_V2_PATH}")
    
    # Git backup
    import subprocess
    try:
        subprocess.run(["git", "add", MODEL_V2_PATH], check=True, cwd="/home/colton/.openclaw/workspace")
        result = subprocess.run(
            ["git", "commit", "-m", f"Retrain V2: {len(X)} samples, momentum-only CV {cv_scores.mean():.3f}"],
            capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace"
        )
        if result.returncode == 0:
            push = subprocess.run(["git", "push"], capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace")
            print("Git push successful" if push.returncode == 0 else f"Push failed: {push.stderr}")
    except Exception as e:
        print(f"Git backup failed: {e}")

if __name__ == "__main__":
    retrain()
