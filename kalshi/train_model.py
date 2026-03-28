#!/usr/bin/env python3
"""
Train a proper ML model on the labeled dataset.
Features: fair_prob, time_remaining, btc_direction, entry_price
Label: 1 = YES won, 0 = NO won
"""
import json
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import cross_val_score, LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
import pickle

# Load dataset
with open("/home/colton/.openclaw/workspace/kalshi/ml_dataset.json") as f:
    dataset = json.load(f)

print(f"Dataset: {len(dataset)} samples")

# Remove samples without BTC direction (no Kraken data)
dataset = [d for d in dataset if d["btc_direction"] is not None]
print(f"After filtering for BTC data: {len(dataset)} samples")

# Build feature matrix
X = []
y = []
for d in dataset:
    # Features: fair_prob, time_remaining, btc_direction, btc_change, entry_price
    X.append([
        d["fair_prob"],
        d["time_remaining"] / 15.0,  # Normalize to 0-1
        d["btc_direction"],
        d["btc_change"] if d["btc_change"] else 0,
        d["entry_price"],
    ])
    y.append(d["label"])

X = np.array(X)
y = np.array(y)

print(f"\nFeature matrix shape: {X.shape}")
print(f"Class distribution: {sum(y)} YES, {len(y)-sum(y)} NO")

# Feature names
feat_names = ["fair_prob", "time_remaining_norm", "btc_direction", "btc_change", "entry_price"]

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train Gradient Boosting (like the original)
print("\n=== Gradient Boosting ===")
gb = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
gb_scores = cross_val_score(gb, X_scaled, y, cv=min(10, len(y)), scoring="accuracy")
print(f"CV Accuracy: {gb_scores.mean():.3f} (+/- {gb_scores.std():.3f})")
gb.fit(X_scaled, y)

# Feature importances
print("\nFeature importances:")
for name, imp in sorted(zip(feat_names, gb.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name}: {imp:.3f}")

# Predictions on training data
y_pred = gb.predict(X_scaled)
print(f"\nTraining accuracy: {(y_pred == y).mean():.3f}")

# What does the model learn?
print("\n=== What the model predicts ===")
# If BTC is UP, what does model say?
btc_up = [X[i] for i in range(len(X)) if X[i][2] > 0]  # btc_direction = 1
btc_down = [X[i] for i in range(len(X)) if X[i][2] == 0]  # btc_direction = 0

if btc_up:
    X_up = np.array(btc_up)
    X_up_scaled = scaler.transform(X_up)
    pred_up = gb.predict(X_up_scaled)
    print(f"When BTC UP: {sum(pred_up)} YES / {len(pred_up)-sum(pred_up)} NO")

if btc_down:
    X_down = np.array(btc_down)
    X_down_scaled = scaler.transform(X_down)
    pred_down = gb.predict(X_down_scaled)
    print(f"When BTC DOWN: {sum(pred_down)} YES / {len(pred_down)-sum(pred_down)} NO")

# Compare to fair_prob alone
print("\n=== fair_prob alone ===")
for threshold in [0.50, 0.55, 0.60, 0.65, 0.70]:
    pred_at_threshold = (X[:, 0] >= threshold).astype(int)
    acc = (pred_at_threshold == y).mean()
    print(f"  fair_prob >= {threshold}: accuracy = {acc:.3f}")

# What if we use btc_direction alone?
print("\n=== btc_direction alone ===")
pred_btc = X[:, 2].astype(int)
acc = (pred_btc == y).mean()
print(f"  btc_direction alone: accuracy = {acc:.3f}")

# Save model
model_data = {
    "model": gb,
    "scaler": scaler,
    "trained_at": str(np.datetime64("now")),
    "n_samples": len(dataset)
}
with open("/home/colton/.openclaw/workspace/kalshi/model_v2.pkl", "wb") as f:
    pickle.dump(model_data, f)

print("\nModel saved to model_v2.pkl")

# Sanity check: what would a simple strategy do?
# Strategy: trade YES when fair_prob > 0.55 AND btc_direction == 1
print("\n=== Proposed Strategy ===")
for fair_thresh in [0.50, 0.55, 0.60]:
    mask = (X[:, 0] >= fair_thresh) & (X[:, 2] > 0)
    if mask.sum() > 0:
        subset_y = y[mask]
        wins = (subset_y == 1).sum()
        losses = (subset_y == 0).sum()
        print(f"fair_prob >= {fair_thresh} + BTC up: {mask.sum()} trades, {wins}W/{losses}L, win rate={wins/mask.sum():.1%}")
