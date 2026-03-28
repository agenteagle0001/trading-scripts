#!/bin/bash
# Add weekly Sunday midnight ML model retrain
(crontab -l 2>/dev/null | grep -v retrain; echo "0 0 * * 0 /usr/bin/python3 /home/colton/.openclaw/workspace/kalshi/retrain_model.py >> /tmp/retrain.log 2>&1") | crontab -
