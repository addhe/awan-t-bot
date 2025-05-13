# Trading Bot Architecture Overview

This document describes the high-level architecture of the trading bot codebase, its main components, and how they interact.

---

## 1. High-Level Structure

```
awan-t-bot/
├── bot.py                # Main entry point
├── config/               # Configuration files (settings.py)
├── src/
│   ├── core/             # Core trading logic (trading bot, position management)
│   ├── exchange/         # Exchange connectors and API integration
│   ├── strategies/       # Trading strategies (signal generation, indicator logic)
│   ├── utils/            # Utilities: logging, status, error handling, rate limiting, Redis
│   └── ...               # Other supporting modules
├── tests/                # Unit and integration tests
├── docker-compose.yml    # Multi-container Docker configuration
├── Dockerfile            # Container definition for the trading bot
├── redis.conf            # Redis configuration with persistence
├── init-postgres.sql     # PostgreSQL initialization script
├── requirements.txt      # Python dependencies
└── README.md             # User documentation
```

---

## 2. Main Components

### a. Entry Point
- **`bot.py`**: Script to start the trading bot. Initializes components and runs the main event loop.

### b. Configuration
- **`config/settings.py`**: File konfigurasi utama berisi semua parameter trading, strategi, sistem, exchange, logging, dan Telegram.
- **`.env`**: API keys dan sensitive credentials.

### c. Core Logic (`src/core/`)
- **`trading_bot.py`**: Orchestrates the trading process (initialization, main loop, signal handling, order execution, monitoring).
- **`position_manager.py`**: Manages open/closed positions, tracks trade lifecycle and risk.

### d. Exchange Integration (`src/exchange/`)
- **`connector.py`**: Handles communication with the exchange API (order placement, fetching balances, etc).

### e. Strategies (`src/strategies/`)
- **`boll_stoch_strategy.py`**, **`spot_strategy.py`**: Implements trading signal logic, indicator calculation (Bollinger Bands, EMA, Stochastic RSI, etc), and buy/sell decision-making. Parameter strategi dikonfigurasi dalam `config/settings.py`.

### f. Utilities (`src/utils/`)
- **`status_monitor.py`**: Tracks and logs bot/trade status to files.
- **`error_handlers.py`**: Decorators and helpers for robust error handling.
- **`structured_logger.py`**: Structured logging for debugging and monitoring.
- **`rate_limiter.py`**: Prevents API rate limit violations.
- **`telegram_utils.py`**: Telegram notification integration.
- **`redis_manager.py`**: Manages Redis connection and operations for caching OHLCV data, indicators, and trading signals.
- **`postgres_manager.py`**: Handles PostgreSQL database operations for long-term data storage.
- **`data_sync.py`**: Synchronizes data between Redis (short-term cache) and PostgreSQL (long-term storage).

### g. Data Persistence
- **Redis**: In-memory database with persistence for caching OHLCV data, indicators, and trading signals. Provides fast access to frequently used data and reduces API calls to exchanges.
- **PostgreSQL with TimescaleDB**: Time-series database for long-term storage of trading data, performance metrics, and historical analysis. Enables comprehensive backtesting and performance analysis.

### g. Tests (`tests/`)
- Unit and integration tests for core logic, strategies, and utilities.

---

## 3. Data Flow & Interaction

1. **Initialization**: `bot.py` loads configuration, initializes exchange connector, strategy, position manager, Redis, and PostgreSQL connections.
2. **Data Caching**: The bot first checks Redis for cached OHLCV data and indicators before calling exchange APIs.
3. **Main Loop**: The bot fetches market data, runs strategy logic to generate signals, and manages positions/orders accordingly.
4. **Signal Generation**: Strategies process price data and indicators to decide buy/sell/hold.
5. **Signal Storage**: Trading signals are stored in Redis for quick access and prioritization of trading pairs.
6. **Order Management**: Position manager and exchange connector handle order placement, updates, and closing.
7. **Data Synchronization**: Periodically, data is synchronized between Redis (cache) and PostgreSQL (persistent storage).
8. **Monitoring & Logging**: Status and trade events are logged, and notifications sent if enabled.
9. **Error Handling**: All major operations are wrapped with error handling and logging for reliability.

---

## 4. Extensibility
- **Add new strategies**: Place new strategy modules in `src/strategies/` and configure their parameters within `config/settings.py`.
- **Support new exchanges**: Implement new connector in `src/exchange/` and update configuration in `config/settings.py`.
- **Custom risk management**: Extend `position_manager.py` or add new modules in `src/core/` or `src/risk_management.py` (jika dibuat).

---

## 5. Diagram (Simplified)

```
[bot.py]
   |
   v
[trading_bot.py] <--> [position_manager.py]
   |                        |
   |                        v
   |                  [exchange connector]
   |                        |
   v                        v
[strategy (signal)] <--> [redis_manager] <--> [postgres_manager]
   |                        |                       |
   |                        v                       v
   |                  [data_sync] -------------> [PostgreSQL]
   |                        |
   v                        v
[utils: logging, status, error handling]
```

---

For further details, refer to the inline documentation in each module and the README.md.
