#!/usr/bin/env python3
"""
Train the final predictive model.
Strategy: fair_prob >= 0.55 + positive momentum → YES
          fair_prob < 0.45 + negative momentum → NO
          otherwise → no trade
"""
import json
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
import pickle

# Load predictive dataset
with open("/home/colton/.openclaw/workspace/kalshi/ml_dataset_pred.json") as f:
    dataset = json.load(f)

print(f"Dataset: {len(dataset)} samples")

# Features: avg_fair, mom1, mom3, btc_dir, entry_price
X = np.array([[d["avg_fair"], d["mom1"], d["mom3"], d["btc_dir"], d["entry_price"]] for d in dataset])
y = np.array([d["label"] for d in dataset])

feat_names = ["fair_prob", "momentum_15min", "momentum_45min", "btc_direction", "entry_price"]

# Scale
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train model
print("\n=== Gradient Boosting Model ===")
gb = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
scores = cross_val_score(gb, X_scaled, y, cv=5, scoring="accuracy")
print(f"CV Accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")
gb.fit(X_scaled, y)

print("\nFeature importances:")
for name, imp in sorted(zip(feat_names, gb.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name}: {imp:.3f}")

# What the model learns
y_pred = gb.predict(X_scaled)
print(f"\nTraining accuracy: {(y_pred == y).mean():.3f}")

# Proposed trading strategy
print("\n=== Proposed Trading Strategy ===")
print("Rule: ONLY trade when:")
print("  - fair_prob >= 0.55 (Kalshi underpricing YES)")
print("  - BTC momentum_45min > 0 (BTC showing positive momentum)")
print()
print("Expected behavior:")
print("  - YES trades only when both conditions met")
print("  - If fair_prob < 0.45 and momentum negative → NO trade")
print("  - Otherwise → no trade (wait for better setup)")

# Analyze on training data
fair_thresh = 0.55
mom_thresh = 0

yes_trades = [d for d in dataset if d["avg_fair"] >= fair_thresh and d["mom3"] > mom_thresh]
no_trades = [d for d in dataset if d["avg_fair"] < 0.45 and d["mom3"] < 0]
skip_trades = [d for d in dataset if not (d["avg_fair"] >= fair_thresh and d["mom3"] > mom_thresh) and not (d["avg_fair"] < 0.45 and d["mom3"] < 0)]

print(f"\nOn training data ({len(dataset)} markets):")
print(f"  YES signals: {len(yes_trades)} ({sum(1 for t in yes_trades if t['label']==1)}W/{sum(1 for t in yes_trades if t['label']==0)}L)")
if yes_trades:
    print(f"  YES win rate: {sum(1 for t in yes_trades if t['label']==1)/len(yes_trades):.1%}")
    print(f"  YES avg P&L: ${sum(t['label'] for t in yes_trades)/len(yes_trades)*100 - (1-sum(t['label'] for t in yes_trades)/len(yes_trades))*50:.1f}% per trade")
print(f"  NO signals: {len(no_trades)} ({sum(1 for t in no_trades if t['label']==0)}W/{sum(1 for t in no_trades if t['label']==1)}L)")
print(f"  Skipped (no clear signal): {len(skip_trades)}")

# Save the model
model_data = {
    "model": gb,
    "scaler": scaler,
    "fair_thresh": fair_thresh,
    "mom_thresh": mom_thresh,
    "n_samples": len(dataset),
}
with open("/home/colton/.openclaw/workspace/kalshi/model_v2.pkl", "wb") as f:
    pickle.dump(model_data, f)

print(f"\nModel saved to model_v2.pkl")

# Also print what we'd do on each market if we had real-time data
print("\n=== What the strategy would do ===")
for d in sorted(dataset, key=lambda x: x["avg_fair"], reverse=True)[:10]:
    signal = "YES" if d["avg_fair"] >= fair_thresh and d["mom3"] > mom_thresh else ("NO" if d["avg_fair"] < 0.45 and d["mom3"] < 0 else "SKIP")
    outcome = "WIN" if d["label"] == 1 else "LOSS"
    print(f"  {d['ticker']}: fair={d['avg_fair']:.2f} mom3={d['mom3']:+.4f} → {signal} (actual: {outcome})")
