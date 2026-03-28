# Advanced Trading Strategies for SPY

## Executive Summary

Current baseline: RF accuracy 53%, returns underperforming buy&hold. Need more sophisticated approaches.

---

## 1. ML Strategies

### XGBoost / LightGBM
- **Why:** Best for tabular financial data
- **Features needed:**
  - Price returns (1d, 5d, 20d, 50d)
  - Technicals (RSI, MACD, Bollinger, ATR)
  - Volume indicators (OBV, volume ratio)
  - Volatility (VIX, realized vol)
  - Macro (yields, DXY)
- **Approach:**
  - Binary classification (up/down)
  - Walk-forward validation
  - Feature importance pruning
- **Risk:** Overfitting on noise

### LSTM / GRU
- **Why:** Capture sequential patterns
- **Architecture:**
  - Input: 20-60 day sequences
  - LSTM(32) → Dropout(0.2) → Dense(1)
  - Attention layer recommended
- **Challenge:** Financial data is noisy; LSTM often fails

### Transformer (State-of-the-art)
- Overkill for single ticker
- Better for multi-asset portfolios

### Ensemble
- Combine: XGBoost + RF + LogReg
- Voting or stacking
- Reduces variance

---

## 2. Options Data & Execution

### Free Options Data Sources
| Source | Type | Cost |
|--------|------|------|
| Yahoo Finance | IV, options chain | Free |
| Alpha Vantage | EOD options | Free tier |
| CBOE | VIX, indices | Free |

### Options Features
- **IV (Implied Volatility)** - proxy for market fear
- **IV Rank** - current vs 52-week IV
- **Put/Call Ratio** - sentiment indicator
- **Option Volume** - activity spike detection

### Alpaca Options Trading
- Paper trading available
- Requires options approval on account
- API: `POST /v1/options/orders`
- Note: Not all tickers available

---

## 3. Feature Engineering

### Price Features
- Returns: 1d, 5d, 10d, 20d, 50d, 200d
- Price to SMA ratios (10, 20, 50, 200)
- High/Low range

### Technical Indicators
| Indicator | Signal |
|-----------|--------|
| RSI(14) | <30 oversold, >70 overbought |
| MACD | Cross above = bullish |
| Bollinger Bands | Mean reversion |
| ATR | Volatility / position sizing |

### Volume
- Volume / 20d SMA
- On-Balance Volume (OBV)
- Volume momentum

### Macro
- VIX level (fear gauge)
- VIX regime (low/mid/high)
- Treasury yields (if available)

### Time
- Day of week
- Month/quarter
- Pre-holiday effect

---

## 4. Strategy Ideas

### A. Momentum Strategy
- **Entry:** return_5d > 0 AND return_20d > 0
- **Exit:** return_5d < 0
- **Tested:** +2.3% return, 40 trades

### B. Mean Reversion (RSI)
- **Entry:** RSI < 35
- **Exit:** RSI > 55
- **Tested:** -2.7% return

### C. Volatility Breakout
- **Entry:** Close > Upper Bollinger Band
- **Exit:** ATR-based stop

### D. Regime Filter
- Only trade when VIX < 20 (low fear)
- Avoid tail risk

---

## 5. Risk Management

| Rule | Value |
|------|-------|
| Max Drawdown | 25% → STOP |
| Position Size | $500 max |
| Stop Loss | 2% |
| Max Positions | 3 concurrent |
| Max Trades/Day | 10 |

---

## 6. Next Steps

1. ~~Get more features~~ - VIX data fetching needed
2. ~~Walk-forward validation~~ - Completed, mixed results
3. ~~Try sklearn GB/RF~~ - Working, no pip needed
4. Paper trade anyway - AMD order placed

---

## ML Results Summary

### Stock Screening (10 stocks)
| Ticker | Strategy | BuyHold | Alpha |
|--------|----------|---------|-------|
| AMD | +44.1% | +31.6% | +12.4% |
| CRM | -18.9% | -24.3% | +5.4% |
| AMZN | -3.3% | -8.6% | +5.3% |
| NFLX | -23.9% | -28.9% | +5.0% |

### Walk-Forward (AMD)
- Average: -8.4% alpha (underperforms)
- Models converge to "just hold" in uptrending market

### Key Insight
Beating SPY/indices consistently is very hard. Individual stocks show more alpha potential but still inconsistent.

### Recommendations
1. Focus on risk management over alpha
2. Use ML as signal filter, not prediction engine
3. Consider simpler trend-following (MA crossovers)
4. Paper trade to learn system behavior

---

_Last updated: 2026-02-27_
