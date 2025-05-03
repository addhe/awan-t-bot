"""
Telegram utilities for bot notifications
"""
import logging
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)
_bot = None

def setup_telegram(token: str, chat_id: str) -> None:
    """Initialize Telegram bot"""
    global _bot
    try:
        _bot = Bot(token=token)
        # Test the connection
        _bot.get_me()
        logger.info("Telegram bot initialized successfully")
    except TelegramError as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        _bot = None

async def send_telegram_message(message: str) -> None:
    """Send message via Telegram"""
    from config.settings import TELEGRAM_CONFIG

    if not TELEGRAM_CONFIG['enabled'] or not _bot:
        return

    try:
        await _bot.send_message(
            chat_id=TELEGRAM_CONFIG['chat_id'],
            text=message,
            parse_mode='HTML'
        )
    except TelegramError as e:
        logger.error(f"Failed to send Telegram message: {e}")
