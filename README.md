# Trading Scripts

Automated trading and content creation tools.

## Kalshi BTC Trading Bot

### Executor
```bash
python3 kalshi/executor.py
```

Features:
- ML signal (>55% confidence)
- Mispricing trigger (>8%)
- One trade per market
- Stop loss (10% time-adjusted)
- Take profit (20%)
- Trade logging

### Background Downloader
```bash
python3 instagram/download_backgrounds.py
```
Downloads bokeh backgrounds from Pexels API.

## Files
- `kalshi/executor.py` - Main trading executor
- `kalshi/ml_signal.py` - Standalone ML signal script
- `instagram/download_backgrounds.py` - Pexels background downloader
