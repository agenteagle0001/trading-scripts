#!/bin/bash
cd /home/colton/.openclaw/workspace/kalshi

# Run executor
nohup python3 -u executor.py > executor.log 2>&1 &
echo "$(date): Ran executor" >> executor.log
