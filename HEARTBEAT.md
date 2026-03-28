# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

## Trading Monitor (Active)

Run every 30 min during market hours (9:30 AM - 4:00 PM ET):

```bash
python3 /home/colton/.openclaw/workspace/trading/auto_monitor.py
```

## Alert Triggers

| Condition | Action |
|-----------|--------|
| AMD < $184.30 | 🚨 STOP-LOSS - close position immediately |
| Position > 5 days | 💰 Take profit - close position |
| Order filled | 📝 Update paper-trading.md |
| Order expired | 🔄 Re-evaluate strategy |

## Manual Commands

```bash
# Quick check
python3 /home/colton/.openclaw/workspace/trading/monitor.py

# Full auto monitor with actions
python3 /home/colton/.openclaw/workspace/trading/auto_monitor.py
```
