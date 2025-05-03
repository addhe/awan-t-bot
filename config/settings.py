"""
Bot configuration settings
"""

# Trading pairs configuration
TRADING_PAIRS = [
    {
        'symbol': 'BTCUSDT',
        'min_quantity': 0.00001,
        'price_precision': 2,
        'quantity_precision': 5
    },
    {
        'symbol': 'ETHUSDT',
        'min_quantity': 0.0001,
        'price_precision': 2,
        'quantity_precision': 4
    },
    {
        'symbol': 'SOLUSDT',
        'min_quantity': 0.01,
        'price_precision': 3,
        'quantity_precision': 2
    }
]

# Strategy configuration
STRATEGY_CONFIG = {
    'boll_window': 20,
    'boll_std': 2.0,
    'ema_window': 20,
    'stoch_window': 14,
    'stoch_smooth_k': 3,
    'stoch_smooth_d': 3,
    'min_profit': 0.015,  # 1.5% minimum profit
    'stop_loss': 0.01,    # 1% stop loss
}

# Trading configuration
TRADING_CONFIG = {
    'max_open_trades': 3,
    'max_trade_retry': 3,
    'order_timeout': 60,  # seconds
    'cancel_after': 300,  # cancel order if not filled after 5 minutes
    'allocation_per_trade': 0.2,  # 20% dari balance untuk setiap trade
    'min_allocation_usdt': 10,  # Minimum 10 USDT per trade
    'max_allocation_usdt': 100,  # Maximum 100 USDT per trade
}

# Timeframes to analyze
TIMEFRAMES = ['15m', '1h', '4h', '1d']

# System configuration
SYSTEM_CONFIG = {
    'check_interval': 60,  # seconds between checks
    'health_check_interval': 300,  # seconds between health checks
    'max_api_retries': 3,
    'retry_wait': 10,  # seconds to wait between retries

    # Rate limiting
    'max_requests_per_minute': 45,  # Binance limit is 50/minute for spot
    'max_orders_per_second': 5,    # Binance limit is 10/second

    # Network timeouts
    'connection_timeout': 10,  # seconds
    'read_timeout': 30,       # seconds

    # Backoff settings
    'initial_backoff': 1,     # seconds
    'max_backoff': 300,       # 5 minutes
    'backoff_factor': 2,      # exponential backoff

    # Circuit breaker
    'error_threshold': 5,     # errors before circuit breaks
    'circuit_timeout': 600,   # 10 minutes timeout
}

# Logging configuration
LOG_CONFIG = {
    'log_level': 'INFO',
    'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_file': 'logs/trading_bot.log',
    'max_file_size': 5 * 1024 * 1024,  # 5 MB
    'backup_count': 3
}

import os

# Telegram configuration
TELEGRAM_CONFIG = {
    'enabled': True,
    'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'notification_types': [
        'trade_entry',
        'trade_exit',
        'error',
        'warning',
        'system'
    ]
}

# Exchange configuration
EXCHANGE_CONFIG = {
    'name': 'binance',
    'api_key': os.getenv('BINANCE_API_KEY', ''),
    'api_secret': os.getenv('BINANCE_API_SECRET', ''),
    'testnet': os.getenv('USE_TESTNET', 'False').lower() == 'true'
}
