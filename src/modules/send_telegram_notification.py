import os
import logging
import requests
from src.modules.fetch_position_details import fetch_position_details
from src.modules.initialize_exchange import initialize_exchange

TELEGRAM_CONFIG = {
    'bot_token': os.environ.get('TELEGRAM_BOT_TOKEN'),
    'chat_id': os.environ.get('TELEGRAM_CHAT_ID')
}

def send_telegram_notification(message, exchange=None):
    bot_token = TELEGRAM_CONFIG['bot_token']
    chat_id = TELEGRAM_CONFIG['chat_id']
    if bot_token and chat_id:
        try:
            extra_info = ""
            if exchange is None:
                exchange = initialize_exchange()
            if exchange:
                balance = exchange.fetch_balance()
                usdt_balance = balance['USDT']['free']
                
                position_details = fetch_position_details(exchange)
                position_info = f"Buy Positions: {position_details['buy']} ({position_details['total_buy']:.4f} contracts)\n" \
                                f"Sell Positions: {position_details['sell']} ({position_details['total_sell']:.4f} contracts)"
                
                extra_info = f"\nCurrent Balance: {usdt_balance:.2f} USDT\n{position_info}"
            
            final_message = f"{message}{extra_info}"

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": final_message}
            requests.post(url, json=payload)

        except Exception as e:
            logging.error(f'Error sending Telegram notification: {e}')
    else:
        logging.warning('Telegram bot token or chat ID not set')
