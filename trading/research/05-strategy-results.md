# Trading Strategy Results

## Best Strategy: RF + Enhanced Features + Momentum

### Configuration
- Model: Random Forest (150 trees, depth 6)
- Features: 17 features (returns, SMA, RSI, MACD, Bollinger, volume)
- Filter: Require 5-day momentum positive

### Results (AMD, Test Period)
| Config | Return | B&H | Alpha | Trades |
|--------|--------|-----|-------|--------|
| RF t=0.45 + momentum | **+33.5%** | +31.6% | **+1.9%** | 29 |
| RF t=0.45 no momentum | +20.5% | +31.6% | -11.1% | 41 |

## Simple Backup Strategies

| Strategy | Return | B&H | Alpha | Trades |
|----------|--------|-----|-------|--------|
| RSI Mean Reversion | +10.7% | +23.5% | -12.8% | 6 |
| Price Breakout | +18.0% | +23.5% | -5.5% | 1 |
| SMA Crossover | -11.1% | +23.5% | -34.6% | 4 |
| SMA + RSI Filter | +0.0% | +23.5% | -23.5% | 0 |

## Feature Importance (Top 10)

1. return_1d: 0.070
2. volume_ratio: 0.070
3. rsi_14: 0.069
4. bb_position: 0.066
5. macd: 0.064
6. macd_hist: 0.063
7. atr_14: 0.062
8. volatility_20d: 0.060
9. return_5d: 0.059
10. return_10d: 0.059

## Recommendations

1. **Primary:** Use RF with 17 features + momentum filter
2. **Backup:** RSI mean reversion if ML fails
3. **Risk:** Max drawdown 25%, $500 max position

---

_Last updated: 2026-02-27_
