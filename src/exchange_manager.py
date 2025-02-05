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

            # Initialize exchange
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000
                }
            })

            # Set up exchange-specific configurations
            self.exchange.load_markets()
            self.exchange.symbol = self.config['symbol']

            # Set leverage
            self._set_leverage()

            # Set margin type
            self._set_margin_type()

            logging.info(f"Exchange initialized successfully for {self.config['symbol']}")
            return self.exchange

        except Exception as e:
            logging.critical(f"Failed to initialize exchange: {e}")
            raise

    def _set_leverage(self) -> None:
        """Set leverage for trading."""
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")

            self.exchange.fapiPrivatePostLeverage({
                'symbol': self.exchange.market(self.config['symbol'])['id'],
                'leverage': self.config['leverage']
            })
            logging.info(f"Leverage set to {self.config['leverage']}x")

        except Exception as e:
            logging.error(f"Failed to set leverage: {e}")
            raise

    def _set_margin_type(self) -> None:
        """Set margin type to ISOLATED."""
        try:
            if not self.exchange:
                raise ValueError("Exchange not initialized")

            self.exchange.fapiPrivatePostMarginType({
                'symbol': self.exchange.market(self.config['symbol'])['id'],
                'marginType': 'ISOLATED'
            })
            logging.info("Margin type set to ISOLATED")

        except ccxt.ExchangeError as e:
            if "No need to change margin type" not in str(e):
                logging.error(f"Failed to set margin type: {e}")
                raise
        except Exception as e:
            logging.error(f"Failed to set margin type: {e}")
            raise

    def validate_exchange_config(self) -> bool:
        """Validate exchange configuration."""
        try:
            if not self.exchange:
                return False

            # Test API connectivity
            self.exchange.fetch_balance()

            # Verify market exists and is active
            market = self.exchange.market(self.config['symbol'])
            if not market['active']:
                logging.error(f"Market {self.config['symbol']} is not active")
                return False

            # Verify trading is enabled
            if not market.get('info', {}).get('trading', True):
                logging.error(f"Trading is disabled for {self.config['symbol']}")
                return False

            return True

        except Exception as e:
            logging.error(f"Exchange configuration validation failed: {e}")
            return False

    def get_exchange(self) -> Optional[ccxt.Exchange]:
        """Get the initialized exchange instance."""
        return self.exchange

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
