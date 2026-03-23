#!/usr/bin/env python3
"""
SPY Options ML Model v2
Predicts: Will next-day volatility be ABOVE average? (useful for spreads)
Labels: 1 = high volatility day, 0 = low volatility day
"""
import pickle
import json
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

MODEL_PATH = "/home/colton/.openclaw/workspace/trading/spy_model.pkl"
TRAINING_LOG = "/home/colton/.openclaw/workspace/trading/spy_training_log.json"
DATA_FILE = "/home/colton/.openclaw/workspace/trading/spy_ml_data.csv"

def fetch_spy_data(days=500):
    try:
        df = yf.download("SPY", period=f"{days}d")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching: {e}")
        return None

def calculate_features(df):
    df = df.copy()
    
    # Volatility features
    df['return_1d'] = df['Close'].pct_change(1)
    df['return_5d'] = df['Close'].pct_change(5)
    
    # High-low range as % of close
    df['daily_range'] = (df['High'] - df['Low']) / df['Close']
    df['avg_range_5d'] = df['daily_range'].rolling(5).mean()
    df['avg_range_20d'] = df['daily_range'].rolling(20).mean()
    
    # Is today's range bigger than average?
    df['range_percentile'] = df['daily_range'] / df['avg_range_20d']
    
    # Volatility (rolling std)
    df['volatility_5d'] = df['return_1d'].rolling(5).std()
    df['volatility_20d'] = df['return_1d'].rolling(20).std()
    df['vol_ratio'] = df['volatility_5d'] / df['volatility_20d']
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    bb_20 = df['Close'].rolling(20)
    df['bb_std'] = bb_20.std()
    df['bb_width'] = (2 * df['bb_std']) / df['Close']
    
    # Gap
    df['gap'] = (df['Open'] / df['Close'].shift(1)) - 1
    
    # Volume
    df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
    
    # Momentum
    df['momentum_5d'] = df['Close'] / df['Close'].shift(5) - 1
    
    # Moving averages
    df['sma_20'] = df['Close'].rolling(20).mean()
    df['above_20ma'] = (df['Close'] > df['sma_20']).astype(int)
    
    # Next-day volatility (TARGET)
    df['next_range'] = df['daily_range'].shift(-1)
    df['avg_next_range'] = df['next_range'].rolling(20).mean()
    df['target'] = (df['next_range'] > df['avg_next_range']).astype(int)
    
    return df.dropna()

def build_dataset(df):
    feature_cols = [
        'daily_range', 'range_percentile', 'vol_ratio',
        'rsi', 'macd_hist', 'bb_width', 'gap', 
        'volume_ratio', 'momentum_5d', 'above_20ma',
        'avg_range_5d', 'avg_range_20d'
    ]
    
    X = df[feature_cols].values
    y = df['target'].values
    
    return X, y, feature_cols

def train():
    print("=== SPY Volatility ML Model ===")
    print(f"Target: Next-day volatility > average")
    
    print("Fetching data...")
    df = fetch_spy_data(500)
    if df is None:
        return None
    
    df = calculate_features(df)
    print(f"Data: {len(df)} rows")
    
    X, y, feature_names = build_dataset(df)
    print(f"Dataset: {len(X)} samples")
    print(f"Class balance: {sum(y)} HIGH VOL / {len(y)-sum(y)} LOW VOL ({sum(y)/len(y)*100:.1f}% high vol days)")
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42
    )
    
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring='accuracy')
    print(f"\nCV Accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    
    model.fit(X_scaled, y)
    train_acc = (model.predict(X_scaled) == y).mean()
    print(f"Training accuracy: {train_acc:.3f}")
    
    print("\nFeature importances:")
    for name, imp in sorted(zip(feature_names, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name}: {imp:.3f}")
    
    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'trained_at': datetime.now().isoformat(),
        'n_samples': len(X),
        'cv_accuracy': float(cv_scores.mean()),
    }
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"\nModel saved: {MODEL_PATH}")
    
    # Also save to CSV
    df.to_csv(DATA_FILE)
    print(f"Data saved: {DATA_FILE}")
    
    return model_data

def get_signal():
    """Get current signal"""
    try:
        with open(MODEL_PATH, 'rb') as f:
            model_data = pickle.load(f)
    except:
        return None
    
    df = fetch_spy_data(200)  # Need more days for rolling windows
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = calculate_features(df)
    
    if len(df) < 50:
        return None
    
    feature_names = model_data['feature_names']
    latest = df[feature_names].iloc[-1:].values
    
    if np.isnan(latest).any():
        return None
    
    latest_scaled = model_data['scaler'].transform(latest)
    pred = model_data['model'].predict(latest_scaled)[0]
    prob = model_data['model'].predict_proba(latest_scaled)[0]
    
    return {
        'signal': 'HIGH_VOL' if pred == 1 else 'LOW_VOL',
        'confidence': max(prob),
        'prob_high_vol': prob[1],
        'prob_low_vol': prob[0],
    }

if __name__ == "__main__":
    train()
    print("\n=== Current Signal ===")
    sig = get_signal()
    if sig:
        print(f"Signal: {sig['signal']}")
        print(f"Confidence: {sig['confidence']:.1%}")
        print(f"High vol prob: {sig['prob_high_vol']:.1%}")
    else:
        print("No signal available")
