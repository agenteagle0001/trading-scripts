#!/bin/bash
# Hourly bullish scan during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)

cd /home/colton/.openclaw/workspace

# Send task to stock scanner sub-agent
/home/colton/.npm-global/bin/openclaw sessions spawn --runtime subagent --cwd /home/colton/.openclaw/workspace/agents/stock-scanner --label "scan-$(date +%H%M)" --task "Run a bullish stock scan on a sample of 30 popular stocks (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AMD, NFLX, AVGO, COST, ORCL, CRM, ADBE, PYPL, INTC, QCOM, TXN, AMAT, MU, IBM, GS, JPM, BAC, WFC, V, MA, DIS, KO, PEP, MO). Focus on: MACD bull cross on daily, RSI 40-70, volume >1.2x avg, RS vs SPY. Report top 10 stocks with reasons. Save results to /home/colton/.openclaw/workspace/agents/stock-scanner/scans/$(date +%Y%m%d_%H%M).txt" --mode run

