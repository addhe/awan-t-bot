import logging
from typing import Dict, Any, Optional
import ccxt
import pandas as pd
from datetime import datetime
import telegram
from telegram.error import TelegramError

def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str,
                limit: int = 50, timeframe: str = '1m') -> pd.DataFrame:
    try:
        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        return df
    except Exception as e:
        logging.error(f"Error fetching OHLCV data: {e}")
        raise

def calculate_min_order_size(exchange: ccxt.Exchange, symbol: str,
                           market_price: float) -> float:
    try:
        market = exchange.market(symbol)

        # Get minimum amount from market limits
        min_amount = market['limits']['amount']['min']

        # Calculate minimum order size in quote currency
        min_order_size = min_amount * market_price

        # Apply a small buffer to ensure we're above minimum
        return min_order_size * 1.01
    except Exception as e:
        logging.error(f"Error calculating minimum order size: {e}")
        raise

# Telegram bot instance
_bot: Optional[telegram.Bot] = None

def setup_telegram(bot_token: str, chat_id: str) -> None:
    """Initialize Telegram bot"""
    global _bot
    try:
        _bot = telegram.Bot(token=bot_token)
        # Test the connection
        _bot.send_message(chat_id=chat_id, text="🤖 Telegram bot initialized")
    except TelegramError as e:
        logging.error(f"Failed to initialize Telegram bot: {e}")
        raise

def send_telegram_message(message: str) -> None:
    """Send message via Telegram"""
    from config.settings import TELEGRAM_CONFIG

    if not TELEGRAM_CONFIG['enabled'] or not _bot:
        return

    try:
        _bot.send_message(
            chat_id=TELEGRAM_CONFIG['chat_id'],
            text=message,
            parse_mode='HTML'
        )
    except TelegramError as e:
        logging.error(f"Failed to send Telegram message: {e}")

def update_market_data(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        current_price = df['close'].iloc[-1]
        current_volume = df['volume'].iloc[-1]

        # Calculate price change
        price_change = (current_price - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100

        # Calculate volume change
        volume_change = (current_volume - df['volume'].iloc[-2]) / df['volume'].iloc[-2] * 100

        return {
            'current_price': current_price,
            'current_volume': current_volume,
            'price_change_percent': price_change,
            'volume_change_percent': volume_change,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error updating market data: {e}")
        raise

def validate_config() -> bool:
    """
    Validate the configuration settings
    """
    from config.settings import TRADING_CONFIG, EXCHANGE_CONFIG, TELEGRAM_CONFIG

    try:
        # Validate trading config
        if TRADING_CONFIG['max_open_trades'] < 1:
            logging.error("max_open_trades must be at least 1")
            return False

        # Validate exchange config
        if not EXCHANGE_CONFIG['api_key'] or not EXCHANGE_CONFIG['api_secret']:
            logging.error("Missing API credentials")
            return False

        # Validate Telegram config if enabled
        if TELEGRAM_CONFIG['enabled']:
            if not TELEGRAM_CONFIG['bot_token'] or not TELEGRAM_CONFIG['chat_id']:
                logging.error("Telegram enabled but missing bot_token or chat_id")
                return False

        return True

    except Exception as e:
        logging.error(f"Error validating config: {e}")
        return False
