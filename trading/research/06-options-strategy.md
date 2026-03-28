# Refined Options Strategy

## Strategy: Sell Cash-Secured Put

### Parameters (Optimized)
| Parameter | Value | Description |
|-----------|-------|-------------|
| **Sell Threshold** | 0.50 | When ML probability < 0.5 (bearish) |
| **Stop Loss** | 3% | Close if stock drops >3% from strike |
| **Take Profit** | 5 days | Close after 5 days if not stopped |
| **Position Size** | 1 contract max | ~$2000 collateral |

### Results (AMD Backtest)
| Strategy | Return | vs B&H | Trades |
|----------|--------|--------|--------|
| **Sell Put (refined)** | **+204%** | **+172%** | 55 |
| Sell Put (no stops) | +602% | +570% | 47 |
| Buy Protective Put | 0% | -31% | 6-12 |
| Collar | +2.8% | -29% | 6 |

### Why This Works
1. **High win rate** — most puts expire worthless (stock stays above strike)
2. **Limited risk** — stop-loss caps downside
3. **Quick turnover** — 5-day take profit locks in gains

### Risk Rules
- **Max loss per trade:** ~$600 (3% × $20000 strike)
- **Max open positions:** 1 at a time
- **Weekly limit:** 3 trades max
- **Max drawdown:** 25% → STOP

### Trade Execution
1. Get ML signal (prob < 0.50)
2. Calculate strike: 5% OTM from current price
3. Sell put, collect premium
4. Monitor daily:
   - Stop loss: close if stock < strike × 0.97
   - Take profit: close after 5 days
5. Repeat

### Example Trade
- AMD at $200 → Sell $190 put for $3.50 premium = $350 credit
- If stock stays > $190 for 5 days → Keep $350 (1.75% return)
- If stock drops to $183 → Loss ~$350 (stop triggered)

---

_Last updated: 2026-02-27_
