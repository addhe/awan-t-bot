"""
Exchange connector for cryptocurrency trading
"""
import logging
import ccxt
import pandas as pd
from typing import Dict, Any, Optional

from src.utils.rate_limiter import rate_limited_api

logger = logging.getLogger(__name__)

class ExchangeConnector:
    """Handles all exchange interactions with proper rate limiting and error handling"""
    
    def __init__(self, exchange_config: Dict[str, Any], system_config: Dict[str, Any]):
        """Initialize exchange connection
        
        Args:
            exchange_config: Exchange configuration (name, api_key, api_secret, testnet)
            system_config: System configuration (timeouts, rate limits, etc.)
        """
        self.config = exchange_config
        self.system_config = system_config
        self.exchange = self._initialize_exchange()
    
    def _initialize_exchange(self) -> ccxt.Exchange:
        """Initialize the exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.config['name'])
            exchange = exchange_class({
                'apiKey': self.config['api_key'],
                'secret': self.config['api_secret'],
                'enableRateLimit': True
            })

            if self.config['testnet']:
                exchange.set_sandbox_mode(True)

            return exchange

        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise
            
    @rate_limited_api()
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data from exchange with rate limiting
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1h', '15m')
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Configure timeouts
            self.exchange.options['timeout'] = self.system_config['connection_timeout'] * 1000
            self.exchange.options['recvWindow'] = self.system_config['read_timeout'] * 1000

            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                logger.warning(f"No OHLCV data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV data for {symbol}: {e}")
            return pd.DataFrame()

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV data for {symbol}: {e}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching OHLCV data for {symbol}: {e}")
            return pd.DataFrame()
            
    @rate_limited_api()
    async def get_all_balances(self) -> Dict[str, float]:
        """Get available balances for all assets with rate limiting
        
        Returns:
            Dictionary of asset balances
        """
        try:
            balances = {}
            account_info = self.exchange.fetch_balance()
            
            if 'free' in account_info:
                # Filter out zero balances and format 
                for asset, amount in account_info['free'].items():
                    if amount > 0:
                        balances[asset] = amount
            
            return balances

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching balances: {e}")
            return {}

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching balances: {e}")
            return {}

        except Exception as e:
            logger.error(f"Error fetching balances: {e}")
            return {}
            
    @rate_limited_api()
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current ticker information for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Ticker information or None if error
        """
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
            
    async def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price or 0 if error
        """
        try:
            ticker = await self.get_ticker(symbol)
            return float(ticker['last']) if ticker and 'last' in ticker else 0
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return 0
            
    @rate_limited_api()
    async def place_market_buy(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place a market buy order
        
        Args:
            symbol: Trading pair symbol
            quantity: Order quantity
            
        Returns:
            Order information
        """
        try:
            order = self.exchange.create_market_buy_order(symbol, quantity)
            logger.info(f"Placed market buy order for {quantity} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Error placing market buy order for {symbol}: {e}")
            raise
            
    @rate_limited_api()
    async def place_market_sell(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place a market sell order
        
        Args:
            symbol: Trading pair symbol
            quantity: Order quantity
            
        Returns:
            Order information
        """
        try:
            order = self.exchange.create_market_sell_order(symbol, quantity)
            logger.info(f"Placed market sell order for {quantity} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Error placing market sell order for {symbol}: {e}")
            raise
            
    @rate_limited_api()
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol
            
        Returns:
            Cancellation information
        """
        try:
            return self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Error cancelling order {order_id} for {symbol}: {e}")
            raise
            
    @rate_limited_api()
    async def fetch_open_orders(self, symbol: str) -> list:
        """Fetch open orders for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            List of open orders
        """
        try:
            return self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            logger.error(f"Error fetching open orders for {symbol}: {e}")
            return []
