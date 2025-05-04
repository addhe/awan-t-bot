import os

"""
Bot configuration settings
"""

# Trading pairs configuration
TRADING_PAIRS = [
    {
        "symbol": "BTCUSDT",
        "min_quantity": 0.00001,
        "price_precision": 2,
        "quantity_precision": 5,
        "max_position_qty": 0.001,
        "timeframes": ["1h", "4h"],
    },
    {
        "symbol": "ETHUSDT",
        "min_quantity": 0.001,
        "price_precision": 2,
        "quantity_precision": 5,
        "max_position_qty": 0.01,
        "timeframes": ["1h", "4h"],
    },
]

# Strategy configuration
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

# Trading configuration
TRADING_CONFIG = {
    "max_open_trades": 3,
    "position_size_pct": 0.05,  # 5% of balance per trade
    "stop_loss_pct": 0.02,  # 2% stop loss
    "take_profit_pct": 0.03,  # 3% take profit
    "trailing_stop_pct": 0.01,  # 1% trailing stop
    "trailing_stop_activation_pct": 0.01,  # Activate trailing stop after 1% profit
}

# System configuration
SYSTEM_CONFIG = {
    # Connection settings
    "connection_timeout": 10,  # seconds
    "read_timeout": 30,  # seconds
    "retry_count": 3,
    "retry_delay": 1,  # seconds
    "retry_wait": 5,  # seconds to wait after an error in main loop
    
    # Rate limiting
    "rate_limit_buffer": 0.8,  # 80% of rate limit
    "max_requests_per_minute": 45,  # Maximum API requests per minute
    "max_orders_per_second": 5,  # Maximum orders per second
    
    # Circuit breaker settings
    "error_threshold": 5,  # Number of errors before circuit breaker trips
    "circuit_timeout": 600,  # Seconds to keep circuit breaker open (10 minutes)
    
    # Backoff settings
    "initial_backoff": 1,  # Initial backoff in seconds
    "max_backoff": 60,  # Maximum backoff in seconds
    "backoff_factor": 2,  # Multiplier for exponential backoff
    
    # Intervals
    "main_loop_interval_seconds": 60, # Interval for the main processing loop
    "status_update_interval_seconds": 3600, # How often to log/send status updates (1 hour)
    "health_check_interval_seconds": 300, # How often to check exchange/system health (5 minutes)
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "file": "logs/trading_bot.log",
    "max_bytes": 10 * 1024 * 1024,  # 10 MB
    "backup_count": 3,
}

# Telegram configuration
TELEGRAM_CONFIG = {
    "enabled": True,
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "notification_level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
}

# Exchange configuration
EXCHANGE_CONFIG = {
    "name": "binance",
    "api_key": os.getenv("BINANCE_API_KEY", ""),
    "api_secret": os.getenv("BINANCE_API_SECRET", ""),
    "testnet": os.getenv("USE_TESTNET", "False").lower() == "true",
}

# Default configuration
CONFIG = {
    "trading_pairs": TRADING_PAIRS,
    "strategy": STRATEGY_CONFIG,
    "trading": TRADING_CONFIG,
    "system": SYSTEM_CONFIG,
    "logging": LOGGING_CONFIG,
    "telegram": TELEGRAM_CONFIG,
    "exchange": EXCHANGE_CONFIG,
}
