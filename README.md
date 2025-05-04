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
    'rate_limit_buffer': 0.8           # Gunakan 80% dari rate limit API
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
