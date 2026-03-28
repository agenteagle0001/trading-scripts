#!/usr/bin/env python3
"""Retrain ML model on recent data"""
import numpy as np, pickle, re
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from datetime import datetime

data = []
with open("/home/colton/.openclaw/workspace/kalshi/kalshi.log") as f:
    for line in f:
        if "Fair Prob Up:" in line and "min left" in line:
            match = re.search(r'Fair Prob Up: ([\d.]+).*?mispricing: ([+-]?[\d.]+).*?([\d.]+) min left', line)
            if match:
                fair = float(match.group(1))
                mispricing = float(match.group(2))
                mins = float(match.group(3))
                label = 1 if mispricing > 0 else 0
                data.append([fair, mispricing, mins/15, label])

if len(data) < 100:
    print("Not enough data to retrain")
    exit()

X = np.array(data)
y = X[:, -1]
X = X[:, :-1]

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
model.fit(X_scaled, y)

new_model = {"model": model, "scaler": scaler, "trained_at": str(datetime.now())}
with open("/home/colton/.openclaw/workspace/kalshi/model.pkl", "wb") as f:
    pickle.dump(new_model, f)

print(f"Model retrained with {len(data)} samples at {new_model['trained_at']}")
