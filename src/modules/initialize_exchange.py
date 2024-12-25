import ccxt
import logging
import os

API_KEY = os.environ.get('API_KEY_BINANCE')
API_SECRET = os.environ.get('API_SECRET_BINANCE')

def initialize_exchange():
    try:
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'options': {'defaultType': 'future'}
        })
        exchange.set_sandbox_mode(True)  # Set ke False untuk live trading
        exchange.load_markets()
        logging.info("Markets loaded successfully")

        return exchange
    except Exception as e:
        logging.error(f'Failed to initialize exchange: {e}')
        raise