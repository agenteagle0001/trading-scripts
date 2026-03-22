#!/usr/bin/env python3
"""
Retrain ML model using accumulated training data from ml_training_log.json.
Run this weekly via cron to keep the model fresh.
"""
import pickle
import json
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from datetime import datetime

MODEL_V2_PATH = "/home/colton/.openclaw/workspace/kalshi/model_v2.pkl"
TRAINING_LOG = "/home/colton/.openclaw/workspace/kalshi/ml_training_log.json"

def load_training_data():
    """Load and filter training data that has outcomes"""
    try:
        with open(TRAINING_LOG) as f:
            log = json.load(f)
    except:
        print("No training log found")
        return None, None
    
    # Filter to entries with resolved outcomes
    entries = [e for e in log.get("signals", []) if e.get("result") is not None]
    
    if len(entries) < 50:
        print(f"Not enough training data: {len(entries)} samples (need 50+)")
        return None, None
    
    # Build feature matrix and labels
    X = []
    y = []
    
    for e in entries:
        # Features: fair_prob, momentum_15min, momentum_45min, btc_direction, entry_price
        try:
            X.append([
                e.get("fair_prob", 0.5),
                e.get("momentum_15min", 0),
                e.get("momentum_45min", 0),
                e.get("btc_direction", 0),
                e.get("kalshi_prob", 0.5),
            ])
            y.append(1 if e.get("result") == "yes" else 0)
        except:
            continue
    
    return np.array(X), np.array(y), len(entries)

def retrain():
    print(f"=== ML Model Retraining === {datetime.now().isoformat()}")
    
    X, y, n_samples = load_training_data()
    if X is None:
        return
    
    print(f"Training samples: {n_samples}")
    print(f"Class distribution: {sum(y)} YES / {len(y)-sum(y)} NO")
    
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
    cv_scores = cross_val_score(model, X_scaled, y, cv=min(5, n_samples//10), scoring="accuracy")
    print(f"CV Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    # Fit on full data
    model.fit(X_scaled, y)
    train_acc = (model.predict(X_scaled) == y).mean()
    print(f"Training accuracy: {train_acc:.3f}")
    
    # Feature importance
    feat_names = ["fair_prob", "momentum_15min", "momentum_45min", "btc_direction", "entry_price"]
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
            ["git", "commit", "-m", f"Retrain ML model: {n_samples} samples, CV acc {cv_scores.mean():.3f}"],
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
