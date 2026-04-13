#!/usr/bin/env python3
"""
Retrain ML model using ALL market snapshots from market_history.json.
Trains on ALL resolved contracts (not just traded ones) for maximum signal.
"""
import pickle
import json
import re
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from datetime import datetime

MODEL_V2_PATH = "/home/colton/.openclaw/workspace/kalshi/model_v2.pkl"
HISTORY_LOG = "/home/colton/.openclaw/workspace/kalshi/market_history.json"

def parse_ticker_expiry(ticker):
    """Extract expiry datetime from ticker like KXBTC15M-26APR072230-30"""
    # Format: KXBTC15M-YYMMDDHHMM-TYPE
    m = re.search(r'-(\d{2})(\w{3})(\d{2})(\d{4})-', ticker)
    if not m:
        return None
    yy, mon, dd, hhmm = m.group(1), m.group(2), m.group(3), m.group(4)
    months = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,
              'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
    try:
        year = 2000 + int(yy)
        month = months.get(mon.upper(), 1)
        day = int(dd)
        hour = int(hhmm[:2])
        minute = int(hhmm[2:])
        from datetime import datetime as dt
        return dt(year, month, day, hour, minute)
    except:
        return None

def load_training_data():
    """Load ALL market snapshots with resolved outcomes from market history."""
    try:
        with open(HISTORY_LOG) as f:
            history = json.load(f)
    except Exception as e:
        print(f"No market history found: {e}")
        return None, None, 0
    
    snapshots = history.get("snapshots", [])
    
    # Filter to entries with resolved outcomes
    resolved = [s for s in snapshots if s.get("result") is not None]
    
    if len(resolved) < 30:
        print(f"Not enough resolved snapshots: {len(resolved)} (need 30+)")
        return None, None, 0
    
    # Build feature matrix and labels
    X = []
    y = []
    now = datetime.now()
    
    for s in resolved:
        try:
            expiry = parse_ticker_expiry(s.get("ticker", ""))
            if expiry:
                # Time to expiry in minutes (cap at 120 to avoid outliers)
                from datetime import timedelta
                tte = max(0, min(120, (expiry - now).total_seconds() / 60))
            else:
                tte = 15  # default
            
            X.append([
                s.get("fair_prob", 0.5),       # fair probability estimate
                s.get("kalshi_prob", 0.5),    # market's implied probability
                s.get("momentum_15min", 0),   # short-term momentum
                s.get("momentum_45min", 0),   # medium-term momentum
                tte / 120.0,                   # normalized time to expiry (0-1)
            ])
            y.append(1 if s.get("result") == "yes" else 0)
        except Exception as e:
            continue
    
    if len(X) < 30:
        print(f"Not enough valid samples after parsing: {len(X)}")
        return None, None, 0
    
    print(f"Resolved snapshots: {len(resolved)} | Used in training: {len(X)}")
    print(f"Total snapshots logged: {len(snapshots)}")
    traded = [s for s in resolved if s.get("traded")]
    print(f"  (Traded: {len(traded)}, Market-only: {len(resolved)-len(traded)})")
    
    return np.array(X), np.array(y), len(X)

def retrain():
    print(f"=== ML Model Retraining (All Market Snapshots) === {datetime.now().isoformat()}")
    
    X, y, n_samples = load_training_data()
    if X is None:
        return
    
    print(f"Training samples: {n_samples}")
    print(f"Class distribution: {int(sum(y))} YES / {int(len(y)-sum(y))} NO")
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train Gradient Boosting
    model = GradientBoostingClassifier(
        n_estimators=100, 
        max_depth=3, 
        random_state=42,
        min_samples_split=max(5, int(n_samples * 0.1)),
        min_samples_leaf=max(2, int(n_samples * 0.05))
    )
    
    # Cross-validation
    n_cv = max(3, min(5, n_samples // 20))
    cv_scores = cross_val_score(model, X_scaled, y, cv=n_cv, scoring="accuracy")
    print(f"CV Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    # Fit on full data
    model.fit(X_scaled, y)
    train_acc = (model.predict(X_scaled) == y).mean()
    print(f"Training accuracy: {train_acc:.3f}")
    
    # Feature importance
    feat_names = ["fair_prob", "kalshi_prob", "momentum_15m", "momentum_45m", "time_to_exp"]
    print("\nFeature importances:")
    for name, imp in sorted(zip(feat_names, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name}: {imp:.3f}")
    
    # Save model
    model_data = {
        "model": model,
        "scaler": scaler,
        "trained_at": datetime.now().isoformat(),
        "n_samples": n_samples,
        "cv_accuracy": float(cv_scores.mean()),
    }
    
    with open(MODEL_V2_PATH, "wb") as f:
        pickle.dump(model_data, f)
    
    print(f"\nModel saved to {MODEL_V2_PATH}")
    
    # Commit and push updated model
    try:
        import subprocess
        subprocess.run(["git", "add", MODEL_V2_PATH], check=True, cwd="/home/colton/.openclaw/workspace")
        result = subprocess.run(
            ["git", "commit", "-m", f"Retrain ML: {n_samples} samples, CV acc {cv_scores.mean():.3f}"],
            capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace"
        )
        if result.returncode == 0:
            print(f"Git commit successful")
            push = subprocess.run(["git", "push"], capture_output=True, text=True, cwd="/home/colton/.openclaw/workspace")
            if push.returncode == 0:
                print("Git push successful")
            else:
                print(f"Git push failed: {push.stderr}")
        else:
            print(f"Git commit: {result.stdout} {result.stderr}")
    except Exception as e:
        print(f"Git backup failed: {e}")
    
    print(f"Retrain again when you have more data!")

if __name__ == "__main__":
    retrain()
