import os
import logging
import ccxt
from typing import Optional, Dict, Any

from config import CONFIG

class ExchangeManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchange: Optional[ccxt.Exchange] = None

    def initialize_exchange(self) -> ccxt.Exchange:
        """Initialize and configure the exchange."""
        try:
            api_key = os.environ.get('API_KEY_BINANCE')
            api_secret = os.environ.get('API_SECRET_BINANCE')

            if not api_key or not api_secret:
                raise ValueError("API credentials not found in environment variables")

            # Initialize exchange with testnet settings
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000,
                    'test': True  # Enable testnet
                },
                'urls': {
                    'api': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1',
                    },
                    'test': {
                        'public': 'https://testnet.binancefuture.com/fapi/v1',
                        'private': 'https://testnet.binancefuture.com/fapi/v1',
                    }
                }
            })

            # Load markets to ensure connection works
            self.exchange.load_markets()

            # Set margin type to isolated
            try:
                self.exchange.fapiPrivatePostMarginType({
                    'symbol': CONFIG['symbol'].replace('/', ''),
                    'marginType': 'ISOLATED'
                })
                logging.info("Margin type set to isolated")
            except Exception as e:
                if 'already' not in str(e):
                    logging.error(f"Error setting margin type: {e}")
                    raise

            return self.exchange

        except Exception as e:
            logging.critical(f"Failed to initialize exchange: {e}")
            raise

    def set_leverage(self, leverage: int) -> bool:
        """Set leverage for trading."""
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")

            self.exchange.fapiPrivatePostLeverage({
                'symbol': CONFIG['symbol'].replace('/', ''),
                'leverage': leverage
            })
            logging.info(f"Leverage set to {leverage}x")
            return True

        except Exception as e:
            logging.error(f"Failed to set leverage: {e}")
            return False

    def set_margin_type(self, margin_type: str = 'ISOLATED') -> bool:
        """Set margin type for trading."""
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")

            self.exchange.fapiPrivatePostMarginType({
                'symbol': CONFIG['symbol'].replace('/', ''),
                'marginType': margin_type
            })
            logging.info(f"Margin type set to {margin_type}")
            return True

        except Exception as e:
            if 'already' not in str(e):
                logging.error(f"Failed to set margin type: {e}")
                return False
            return True

def initialize_exchange() -> Optional[ccxt.Exchange]:
    """
    Initialize and return the exchange instance.
    This is a convenience function that uses ExchangeManager internally.

    Returns:
        ccxt.Exchange: Initialized exchange instance
    """
    try:
        manager = ExchangeManager(CONFIG)
        return manager.initialize_exchange()
    except Exception as e:
        logging.error(f"Failed to initialize exchange: {e}")
        return None
