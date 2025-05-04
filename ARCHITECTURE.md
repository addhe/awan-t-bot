# Trading Bot Architecture Overview

This document describes the high-level architecture of the trading bot codebase, its main components, and how they interact.

---

## 1. High-Level Structure

```
awan-t-bot/
├── bot.py                # Main entry point
├── config/               # Configuration files (settings, strategies, exchange)
├── src/
│   ├── core/             # Core trading logic (trading bot, position management)
│   ├── exchange/         # Exchange connectors and API integration
│   ├── strategies/       # Trading strategies (signal generation, indicator logic)
│   ├── utils/            # Utilities: logging, status, error handling, rate limiting
│   └── ...               # Other supporting modules
├── tests/                # Unit and integration tests
├── requirements.txt      # Python dependencies
└── README.md             # User documentation
```

---

## 2. Main Components

### a. Entry Point
- **`bot.py`**: Script to start the trading bot. Initializes components and runs the main event loop.

### b. Configuration
- **`config/settings.py`**: Trading parameters (max positions, allocation, etc).
- **`config/strategy_config.py`**: Strategy-specific settings.
- **`.env`**: API keys and sensitive credentials.

### c. Core Logic (`src/core/`)
- **`trading_bot.py`**: Orchestrates the trading process (initialization, main loop, signal handling, order execution, monitoring).
- **`position_manager.py`**: Manages open/closed positions, tracks trade lifecycle and risk.

### d. Exchange Integration (`src/exchange/`)
- **`connector.py`**: Handles communication with the exchange API (order placement, fetching balances, etc).

### e. Strategies (`src/strategies/`)
- **`boll_stoch_strategy.py`**, **`spot_strategy.py`**: Implements trading signal logic, indicator calculation (Bollinger Bands, EMA, Stochastic RSI, etc), and buy/sell decision-making.

### f. Utilities (`src/utils/`)
- **`status_monitor.py`**: Tracks and logs bot/trade status to files.
- **`error_handlers.py`**: Decorators and helpers for robust error handling.
- **`structured_logger.py`**: Structured logging for debugging and monitoring.
- **`rate_limiter.py`**: Prevents API rate limit violations.
- **`telegram_utils.py`**: Telegram notification integration.

### g. Tests (`tests/`)
- Unit and integration tests for core logic, strategies, and utilities.

---

## 3. Data Flow & Interaction

1. **Initialization**: `bot.py` loads configuration, initializes exchange connector, strategy, and position manager.
2. **Main Loop**: The bot fetches market data, runs strategy logic to generate signals, and manages positions/orders accordingly.
3. **Signal Generation**: Strategies process price data and indicators to decide buy/sell/hold.
4. **Order Management**: Position manager and exchange connector handle order placement, updates, and closing.
5. **Monitoring & Logging**: Status and trade events are logged, and notifications sent if enabled.
6. **Error Handling**: All major operations are wrapped with error handling and logging for reliability.

---

## 4. Extensibility
- **Add new strategies**: Place new strategy modules in `src/strategies/` and update configuration.
- **Support new exchanges**: Implement new connector in `src/exchange/`.
- **Custom risk management**: Extend `position_manager.py` or add new modules in `src/core/` or `src/risk_management.py`.

---

## 5. Diagram (Simplified)

```
[bot.py]
   |
   v
[trading_bot.py] <--> [position_manager.py]
   |                        |
   v                        v
[strategy (signal)]     [exchange connector]
   |                        |
   v                        v
[utils: logging, status, error handling]
```

---

For further details, refer to the inline documentation in each module and the README.md.
