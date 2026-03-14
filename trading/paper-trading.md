# Paper Trading Log

## Account
- Paper trading balance: $100,355.42
- Options level: 3 (enabled)
- Max position: $500 (or 1 contract ~$2000 margin)
- Max drawdown: 25%

## Active Positions

| Symbol | Type | Qty | Strike | Entry Price | Current Price | P/L | Status |
|--------|------|-----|--------|-------------|---------------|-----|--------|
| AMD260320P00190000 | Put (sell) | 1 | $190 | $2.50 | - | - | accepted |

## Strategy: Sell Cash-Secured Put
- **Signal:** ML probability < 0.50 (bearish)
- **Strike:** 5% OTM ($190 vs $200 spot)
- **Premium:** $2.50 × 100 = **$250 credit**
- **Theoretical price:** $2.40 (Black-Scholes)
- **Break-even:** $187.60
- **Stop-loss:** 3% below strike ($184.30)
- **Take profit:** 5 trading days

## Trade Logic (Autonomous)

```python
# Monitor daily:
# 1. Get current AMD price
# 2. If price < $184.30 (3% stop) → BUY TO CLOSE
# 3. If held 5 days → BUY TO CLOSE (take profit)
# 4. If price > $195 (far OTM) → Let it ride
```

## Orders

| Date | Symbol | Side | Qty | Price | Status |
|------|--------|------|-----|-------|--------|
| 2026-02-28 | AMD | buy | 2 | market | canceled |
| 2026-02-28 | AMD260320P00190000 | sell | 1 | $3.50 | canceled (replaced) |
| 2026-02-28 | AMD260320P00190000 | sell | 1 | $2.50 | accepted |

## Performance

- Premium target: $250
- Status: Pending fill

---

_Updated: 2026-02-28_
