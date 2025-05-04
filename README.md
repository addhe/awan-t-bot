# Awan Trading Bot

## Latest Update (2025-05-04)

Major refactoring and code improvements:
- Restructured codebase into modular components
- Enhanced error handling with custom decorators
- Implemented structured logging for better debugging
- Added comprehensive unit tests
- Improved code maintainability and readability

## Strategy Overview

The bot implements a sophisticated multi-timeframe analysis strategy using:
- Bollinger Bands (BB) for trend and volatility
- Exponential Moving Average (EMA) for trend confirmation
- Stochastic RSI for momentum signals

### Entry Conditions
- Price near BB bands (oversold/overbought)
- EMA trend confirmation
- Stochastic RSI crossover
- Multi-timeframe confirmation (15m, 1h, 4h, 1d)

### Exit Conditions
- Dynamic stop-loss based on volatility
- Take-profit at BB mean reversion
- Trailing stop when in profit

## Supported Trading Pairs
- BTC/USDT
- ETH/USDT
- SOL/USDT

## Risk Management
- 2% max risk per trade
- Dynamic position sizing
- Maximum 3 concurrent positions
- Adaptive stop-loss levels
- Emergency stop on:
  - Daily loss > 5%
  - Drawdown > 15%
  - 3 consecutive losses

## Technical Features
- Real-time market data analysis
- Multi-timeframe signal weighting
- Telegram notifications for:
  - Trade entries/exits
  - Risk alerts
  - System status
- Performance tracking
- System health monitoring
- Error recovery system

## Project Structure
```
src/
  ├── exchange/
  │    ├── connector.py      # Exchange connection, API calls
  │
  ├── core/
  │    ├── trading_bot.py    # Core bot logic
  │    └── position_manager.py # Position tracking, risk management
  │
  ├── strategies/
  │    └── boll_stoch_strategy.py # Bollinger Bands + Stochastic RSI strategy
  │
  └── utils/
       ├── error_handlers.py   # Error handling decorators
       ├── status_monitor.py   # Bot status monitoring
       ├── structured_logger.py # Enhanced logging
       └── telegram_utils.py   # Telegram notifications
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure:
   ```env
   API_KEY_BINANCE=your_api_key
   API_SECRET_BINANCE=your_api_secret
   TELEGRAM_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## Configuration

### Trading Parameters (`config/settings.py`)

```python
# Position Sizing
TRADING_CONFIG = {
    'max_open_trades': 3,
    'stake_currency': 'USDT',
    'stake_amount': 'dynamic',  # Based on balance
}

# Balance-based Position Sizing
< 100 USDT:
- 30% max per trade
- 1 position max
- Target: 3.0%
- Stop: 2.0%

100-500 USDT:
- 25% max per trade
- 2 positions max
- Target: 2.5%
- Stop: 1.8%

500-1000 USDT:
- 20% max per trade
- 2 positions max
- Target: 2.0%
- Stop: 1.5%

1000+ USDT:
- 15% max per trade
- 3 positions max
- Target: 1.8%
- Stop: 1.2%
```

### Network & Safety (`config/settings.py`)

```python
SYSTEM_CONFIG = {
    'check_interval': 60,          # seconds
    'max_requests_per_minute': 45,  # API rate limit
    'max_orders_per_second': 5,     # Order rate limit
    'connection_timeout': 10,       # seconds
    'circuit_timeout': 600,         # 10 minutes timeout
    'error_threshold': 5            # errors before circuit breaks
}
```

## Usage

### Starting the Bot
```bash
# Start bot
./run.sh

# Stop bot gracefully
./stop.sh
```

### Running Tests
```bash
# Run all unit tests
python -m pytest tests/unit

# Run specific test file
python -m pytest tests/unit/test_exchange_connector.py

# Run with coverage report
python -m pytest tests/unit --cov=src
```

### Monitoring

1. Via Command Line:
```bash
# Check current status
./status_check.py
```

2. Via Status Files:
```bash
# Bot status
cat status/bot_status.json

# Active trades
cat status/active_trades.json
```

3. Via Telegram:
- Hourly status updates
- Trade notifications
- Error alerts

### Status Report Example
```
🤖 Bot Status Report

Status: 🟢 Running
Uptime: 2.5 hours

💰 Balance:
USDT: 487.12345678
BTC: 0.00123456

📊 Active Trades (1):
BTC/USDT:
Entry: 40000.00000000
Current: 40100.00000000
P/L: +0.25%

📈 Performance (24h):
Trades: 8
Win Rate: 75.0%
Profit: 2.15%
```

### Safety Features

1. Rate Limiting:
- 45 requests/minute max
- 5 orders/second max
- Automatic backoff

2. Circuit Breaker:
- Activates after 5 errors in 10 minutes
- Auto-recovery after timeout
- Telegram notifications

3. Balance Protection:
- Dynamic position sizing
- Automatic USDT conversion
- Minimum trade size: 15 USDT

4. Network Resilience:
- Exponential backoff
- Connection timeouts
- Automatic retry with backoff

## Known Limitations

1. High volatility periods may result in:
   - Wider stops
   - Lower position sizes
   - More false signals

2. Market conditions where the strategy performs poorly:
   - Choppy, sideways markets
   - Extreme volatility events
   - Low liquidity periods

## Disclaimer

**⚠️ HIGH RISK WARNING**

This is a sophisticated trading bot operating on cryptocurrency spot markets. Significant financial losses are possible. Only use this if you:
- Fully understand the implemented strategy
- Have extensive crypto spot trading experience
- Can afford to lose the capital you're trading with
- Have thoroughly tested in paper trading first

The developers assume no responsibility for any financial losses.

## Strategy Details

### Multi-Timeframe Analysis
- Primary: 1h timeframe
- Confirmation: 4h timeframe
- Trend: 1d timeframe

### Entry Conditions
1. Bollinger Bands squeeze
2. Stochastic RSI crossover
3. EMA trend confirmation
4. Volume confirmation

### Exit Conditions
1. Take Profit: Dynamic (1.8% - 3.0%)
2. Stop Loss: Dynamic (1.2% - 2.0%)
3. Trailing stop when in profit

### Risk Management & Position Sizing

#### Balance Requirements
- Minimum recommended: $100 USDT
- Optimal recommended: $500 USDT

#### Position Size Calculation
Example with $500 USDT balance:
- Risk per trade: 0.5% = $2.5 USDT
- Stop loss: 1%
- Leverage: 2x
```
Position size = (Risk × Leverage) ÷ Stop Loss
For BTC at $40,000:
$2.5 × 2 ÷ $400 = 0.0125 BTC ≈ $500 position value
```

#### Risk Controls
1. **Daily Loss Limit**: 3%
   - With $500 balance = $15 max daily loss
   - Bot stops trading if reached

2. **Drawdown Protection**: 5%
   - Maximum drawdown = $25 on $500
   - Size reduction or trading pause

3. **Volatility Adjustments**
   - High volatility (>5%): Size -30%
   - Low volatility (<2%): Size +20%

#### Take Profit Strategy
1. **Partial TP 1** (70% of position)
   - Target: 1% profit
   - Example: $350 from $500 position

2. **Partial TP 2** (30% of position)
   - Target: 2% profit
   - Example: Remaining $150

#### Trailing Stop
- Activates at 1% profit
- Follows price at 0.5% distance
- Helps secure profits in trends

#### Trading Limits
- Max 3 simultaneous positions
- Max 5 trades per day
- Min market volume: $5,000
- Excluded hours: 00:00, 01:00, 23:00 UTC

## Troubleshooting

### Bot Restart & Recovery

Bot aman untuk di-restart kapanpun menggunakan `run.sh` karena memiliki beberapa mekanisme safety:

1. **State Recovery**
   - Menyimpan status trading di `status/active_trades.json`
   - Saat restart akan:
     * Membaca status trading terakhir
     * Melanjutkan monitoring posisi yang masih terbuka
     * Tidak membuka posisi duplikat

2. **Graceful Shutdown & Restart**
   - Memiliki signal handler untuk SIGTERM
   - Saat restart akan:
     * Menginisialisasi ulang koneksi ke exchange
     * Memverifikasi balance
     * Mengecek health system
     * Mengirim notifikasi Telegram

3. **Safety Checks**
   - Sebelum membuka posisi baru:
     * Verifikasi tidak ada posisi duplikat
     * Cek balance tersedia
     * Pastikan tidak melebihi limit trading

4. **Error Recovery**
   - Circuit breaker aktif jika:
     * 5 error dalam 10 menit
     * Auto-recovery setelah timeout
     * Notifikasi via Telegram

**Prosedur Restart yang Aman:**
1. Cek error di `logs/trading_bot.log`
2. Jalankan `./run.sh`
3. Monitor notifikasi Telegram
4. Verifikasi status bot

### Common Issues

1. Network Errors:
```
🔴 Network error: Connection timeout
- Check your internet connection
- Bot will automatically retry
```

2. API Errors:
```
🔴 Exchange error: Invalid API key
- Verify API key permissions
- Check IP whitelist
```

3. Balance Issues:
```
🔴 Insufficient funds
- Check minimum trade size (15 USDT)
- Verify asset conversion settings
```

## License

MIT
