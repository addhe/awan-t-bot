#!/usr/bin/env python
"""
Refactored trading bot entry point
"""
import os
import time
import asyncio
import logging
from logging.handlers import RotatingFileHandler

from src.core.trading_bot import TradingBot
from config.settings import LOG_CONFIG

# Setup logging
os.makedirs('logs', exist_ok=True)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(LOG_CONFIG['log_level'])

# Remove any existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create formatters
log_formatter = logging.Formatter(LOG_CONFIG['log_format'])

# Create handlers
file_handler = RotatingFileHandler(
    LOG_CONFIG['log_file'],
    maxBytes=LOG_CONFIG['max_file_size'],
    backupCount=LOG_CONFIG['backup_count']
)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Add handlers to root logger
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Get module logger
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for the trading bot"""
    bot = TradingBot()
    await bot.initialize()
    await bot.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
