# Awan Trading Bot

## Latest Update (2025-05-13)

Added Docker support, data persistence, and enhanced trading features:
- Implemented Docker and Docker Compose for easy deployment
- Added Redis for caching OHLCV data, indicators, and trading signals
- Integrated PostgreSQL with TimescaleDB for long-term data storage and analysis
- Added option to disable stop loss and only sell when minimum profit is reached
- Enhanced position management with configurable minimum profit percentage
- Improved data synchronization between Redis (cache) and PostgreSQL (persistent storage)
- Enhanced error handling for insufficient balance scenarios
- Improved indicator calculation with better NaN handling
- Fixed position tracking with pending_close flag

## Previous Update (2025-05-10)

Enhanced monitoring and position management:
- Added confidence level monitoring system for trading signals
- Improved position tracking with balance verification
- Fixed take profit execution and position status updates
- Enhanced error handling for insufficient balance scenarios
- Added detailed signal analysis and visualization tools

## Previous Update (2025-05-04)

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
- BTC/USDT (`BTCUSDT`)
- ETH/USDT (`ETHUSDT`)
- SOL/USDT (`SOLUSDT`)

## Risk Management
- Maksimal 3 posisi terbuka bersamaan (`max_open_trades`).
- Alokasi modal per trade: 5% dari balance (`position_size_pct`).
- Stop loss: 2% dari harga entry (`stop_loss_pct`).
- Take profit: 3% dari harga entry (`take_profit_pct`).
- Trailing stop loss: 1% aktif setelah profit 1% (`trailing_stop_pct`, `trailing_stop_activation_pct`).
- Daily loss limit: 3% (`daily_loss_limit`).
- Drawdown protection: 5% (`drawdown_limit`).

## Technical Features
- Real-time market data analysis
- Multi-timeframe signal weighting
- Confidence level monitoring and analysis
- Telegram notifications for:
  - Trade entries/exits
  - Risk alerts
  - System status
  - Confidence levels
- Performance tracking
- System health monitoring
- Error recovery system
- Balance verification for position management

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

# Utility Scripts
confidence_check.py      # Analyze and display confidence levels
status_check.py          # Check bot status and active trades
run.sh                   # Start the trading bot
stop.sh                  # Stop the trading bot gracefully

# Docker Support
Dockerfile              # Container definition for the trading bot
docker-compose.yml      # Multi-container setup (bot, Redis, PostgreSQL)
redis.conf              # Redis configuration with persistence
init-postgres.sql       # PostgreSQL initialization script
```

## Docker Deployment

The bot now supports containerized deployment using Docker and Docker Compose, which provides:
- Easy deployment across different environments
- Data persistence through Redis and PostgreSQL
- Improved reliability and scalability

### Prerequisites
- Docker and Docker Compose installed on your system

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/awan-t-bot.git
cd awan-t-bot

# Configure environment variables (optional)
cp .env.example .env
# Edit .env with your credentials

# Build and start the containers
docker-compose up -d

# View logs
docker-compose logs -f trading-bot
```

### Configuration

Create a `.env` file in the project root with the following variables:

```
REDIS_PASSWORD=YourStrongRedisPassword
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YourStrongPostgresPassword
POSTGRES_DB=tradingdb
```

### Data Persistence

The Docker setup includes:
- **Redis** for caching OHLCV data and indicators with persistence
- **PostgreSQL with TimescaleDB** for long-term storage of trading data

Data is stored in Docker volumes:
- `redis-data`: Redis data files (RDB and AOF)
- `postgres-data`: PostgreSQL database files

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure:
   ```env
   BINANCE_API_KEY=your_api_key
   BINANCE_API_SECRET=your_api_secret
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   USE_TESTNET=False # Set to True to use testnet
   ```

## Configuration

Konfigurasi utama terdapat dalam file `config/settings.py` dan `.env`. Lihat `CONFIGURATION_GUIDE.md` untuk detail lengkap setiap parameter.

### Contoh Konfigurasi Utama (`config/settings.py`)

```python
# Trading Configuration
TRADING_CONFIG = {
    'max_open_trades': 3,              # Maksimal posisi terbuka bersamaan
    'position_size_pct': 0.05,         # Alokasi modal 5% per trade
    'stop_loss_pct': 0.02,             # Stop loss 2%
    'take_profit_pct': 0.03,           # Take profit 3%
    'trailing_stop_pct': 0.01,         # Trailing stop 1%
    'trailing_stop_activation_pct': 0.01 # Aktifkan trailing stop setelah profit 1%
}

# System Configuration
SYSTEM_CONFIG = {
    'connection_timeout': 10,          # seconds
    'read_timeout': 30,                # seconds
    'retry_count': 3,                  # Jumlah retry jika gagal
    'retry_delay': 1,                  # Jeda antar retry (seconds)
    'rate_limit_buffer': 0.8,          # Gunakan 80% dari rate limit API
    'main_loop_interval_seconds': 60,  # Target cycle duration
    'status_update_interval_seconds': 3600, # Log status every hour
    'health_check_interval_seconds': 300, # Check health every 5 mins
}

# Strategy Configuration (Contoh untuk BollStochStrategy)
STRATEGY_CONFIG = {
    "boll_length": 20,
    "boll_std": 2,
    "ema_length": 50,
    "stoch_length": 14,
    "stoch_smooth_k": 3,
    "stoch_smooth_d": 3,
    "stoch_oversold": 20,
    "stoch_overbought": 80,
}

# Pair Configuration (Contoh)
TRADING_PAIRS = [
    {
        "symbol": "BTCUSDT",
        "min_quantity": 0.00001,
        "price_precision": 2,
        "quantity_precision": 5,
        "max_position_qty": 0.001,
        "timeframes": ["1h", "4h"],
    },
    # ... konfigurasi pair lainnya
]
```

**Catatan Penting:**
- Alokasi modal (`position_size_pct`) dihitung berdasarkan persentase dari *total balance* Anda saat trade dibuka.
- Pastikan nilai `min_quantity` dan `quantity_precision` sesuai dengan aturan exchange.
- Sesuaikan semua parameter di `config/settings.py` sesuai toleransi risiko dan strategi Anda.

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
# Check current status and confidence levels
./status_check.py

# Check detailed confidence levels
./confidence_check.py

# View confidence levels from past hours
./confidence_check.py -t 3

# View detailed trading conditions
./confidence_check.py -d
```

2. Via Status Files:
```bash
# Bot status
cat status/bot_status.json

# Active trades
cat status/active_trades.json

# Confidence levels
cat status/confidence_levels.json
```

3. Via Telegram:
- Hourly status updates
- Trade notifications
- Error alerts
- Confidence level updates

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
Confidence: 0.75

📈 Performance (24h):
Trades: 8
Win Rate: 75.0%
Profit: 2.15%

🎯 Current Confidence Levels:
BTCUSDT: 0.62
ETHUSDT: 0.62
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

## Trading Frequency Expectations

The bot uses a conservative trading strategy that prioritizes quality signals over quantity of trades. With the default configuration (`min_confidence: 0.7`), the bot may not trade for several hours or even days if market conditions don't meet the required criteria.

Factors affecting trading frequency:

1. **Confidence Threshold**: The bot only trades when confidence level exceeds 70% (configurable)
2. **Market Conditions**: All required conditions must align across multiple timeframes
3. **Trading Pairs**: Limited to configured pairs (default: BTC/USDT, ETH/USDT, SOL/USDT)

To increase trading frequency, you can:
- Lower the confidence threshold in `config/settings.py` (`min_confidence: 0.6`)
- Add more trading pairs
- Adjust timeframe weights to favor shorter timeframes

Use the `confidence_check.py` tool to monitor how close the bot is to executing trades.

## License

MIT
