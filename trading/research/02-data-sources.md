# Data Sources

## Free Options for SPY

| Source | Real-time | Historical | Cost | Notes |
|--------|-----------|------------|------|-------|
| **Yahoo Finance** | ❌ Delayed | 20+ years | Free | Best for historical backtesting |
| **Alpaca** | ❌ Delayed (free) | 6+ years | Free | Need Gold for real-time |
| **Alpha Vantage** | ✅ $0.02/call | 20+ years | Free tier | 500 calls/day |
| **Polygon.io** | ❌ Delayed | 10+ years | Free tier | Good APIs |
| **IEX Cloud** | ✅ | 5+ years | Free tier | 50k credits/mo |

## Recommendation

**Yahoo Finance (yfinance)** — easiest for historical, great for backtesting.
**Alpaca** — for paper trading integration.

## Setup Needed

1. Get free API keys:
   - [Alpaca](https://alpaca.markets/) (paper trading + execution)
   - [Alpha Vantage](https://www.alphavantage.co/) (backup data)

2. Store in `trading/secrets/keys.env`:
   ```
   ALPACA_API_KEY=your_key
   ALPACA_SECRET_KEY=your_secret
   ```

---

## Feature Ideas for SPY ML

### Price-based
- Returns (1d, 5d, 20d)
- Volatility (realized, implied via ATM straddle)
- High/Low/Close ratios

### Technical
- RSI, MACD, Bollinger Bands
- Moving average crossovers
- Volume + OBV

### Macro (if available)
- VIX level
- Treasury yields (2y, 10y)
- Dollar index (DXY)

### Time-based
- Day of week
- Month/quarter
- Market open/close regime
