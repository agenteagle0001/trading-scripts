# Trading Project Setup

## Config

- **Max Drawdown:** 25%
- **Position Size:** $500 max
- **Target:** SPY (S&P 500 ETF)
- **Timeline:** Mixed (based on strategy)

## API Keys

Store in `trading/secrets/`

```
alpaca_api_key=
alpaca_secret_key=
polygon_api_key=
alpha_vantage_api_key=
```

## Agent Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                         │
│              (Coordinates agents)                       │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   RESEARCHER │  │   STRATEGIST │  │   BACKTESTER  │
│  - Data fetch│  │ - Model build│  │ - Validate    │
│  - Feature   │  │ - Strategy   │  │ - Metrics     │
│    engineering   │    design    │  │ - Walk-forward│
└───────────────┘  └───────────────┘  └───────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                 ┌───────────────┐
                 │    TRADER     │
                 │ - Paper/live  │
                 │ - Risk mgmt   │
                 └───────────────┘
```

## Phase 1 Status

- [x] Architecture defined
- [ ] Get API keys (Alpaca recommended)
- [ ] Pull SPY historical data
- [ ] Build feature pipeline

---

_Last updated: 2026-02-27_
