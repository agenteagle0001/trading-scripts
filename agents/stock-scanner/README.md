# Stock Scanner Agent

This sub-agent scans stocks for trading opportunities.

## Role
- Scan multiple stocks for signals
- Run ML models (Random Forest, XGBoost)
- Find options opportunities
- Report findings to main agent

## Tools
- Execute Python scripts for data analysis
- Web search for news/sentiment
- Send messages to main session

## Model
- Primary: minimax-portal/MiniMax-M2.5
- Fallback: ollama/qwen3:14b (if available)

## Schedule
- Run scans on market open (9:30 AM ET)
- Additional runs as requested

## Output
- Save scan results to /home/colton/.openclaw/workspace/agents/stock-scanner/scans/
- Alert main agent on significant signals
