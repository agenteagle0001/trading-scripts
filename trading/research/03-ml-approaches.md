# ML Strategies for SPY

## Priority: ML → Technical

## Viable ML Approaches

### 1. Gradient Boosting (XGBoost, LightGBM) ⭐⭐⭐⭐⭐
- **Best for:** Tabular data, feature importance, explainability
- **Inputs:** Technical indicators + macro features
- **Output:** Classification (up/down) or regression (returns)
- **Papers:** Many quant funds use this as baseline

### 2. Random Forest
- **Pros:** Robust, handles noise well
- **Cons:** Less performant than boosting typically

### 3. LSTM/GRU (Recurrent Neural Networks) ⭐⭐⭐⭐
- **Best for:** Sequential patterns, regime detection
- **Risk:** Overfitting on financial data
- **Tip:** Use attention mechanisms, keep sequences short (20-60 days)

### 4. Transformer/Attention
- **State-of-the-art** but overkill for SPY alone
- Works better with multi-asset

### 5. Ensemble Methods
- Combine predictions from multiple models
- Voting or stacking

## Traditional Technical Strategies (Secondary)

- **Mean reversion:** RSI < 30 buy, > 70 sell
- **Momentum:** MACD crossover, MA200 breakouts
- **Volatility breakout:** ATR-based position sizing
- **Pairs trading:** SPY vs constituent ETFs

## Approach for This Project

### Phase 1: Baseline
1. Pull SPY data (2000-2025)
2. Engineer 20-30 features (technicals + time)
3. Train XGBoost classifier (next day direction)
4. Walk-forward validation

### Phase 2: Enhance
- Add LSTM for sequence patterns
- Ensemble with baseline
- Test on paper trading

### Phase 3: Deploy
- Connect to Alpaca paper trading
- Live evaluation

## Risk Management

- **Max drawdown:** 25% (stop trading if hit)
- **Position size:** $500 max
- **Features:**
  - Position sizing by confidence
  - Daily max positions: 3
  - Stop-loss: 2% (adjustable)

## Next Steps

1. Get API keys
2. Pull historical data
3. Build feature pipeline
4. Train first model
