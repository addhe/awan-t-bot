# awan-t-bot
this is only testing, don't use this code unless you know what you're doing. no guarantee it's working

# Crypto Trading Bot

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

## Configuration
Key parameters in `CONFIG`:
- `symbol`: Trading pair (default: 'BTC/USDT')
- `leverage`: Trading leverage (default: 3)
- `risk_percentage`: Risk per trade (default: 2%)
- etc.

## Features
- Automated trading based on technical indicators
- Risk management
- Performance tracking
- Telegram notifications
- Emergency stop function
