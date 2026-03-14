#!/bin/bash
cd /home/colton/.openclaw/workspace/kalshi

# Check if already running
if pgrep -f "kalshi_working.py" > /dev/null; then
    exit 0
fi

# Restart
nohup python3 -u kalshi_working.py > kalshi.log 2>&1 &
echo "$(date): Restarted" >> kalshi_restarts.log
