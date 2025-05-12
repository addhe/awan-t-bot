"""
Exchange connector for cryptocurrency trading
"""

import ccxt
import pandas as pd
from typing import Dict, Any, Optional

from src.utils.rate_limiter import rate_limited_api
from src.utils.error_handlers import (
    handle_exchange_errors,
    retry_with_backoff,
)
from src.utils.structured_logger import get_logger

logger = get_logger(__name__)


class ExchangeConnector:
    """
    Handles all exchange interactions with proper rate limiting and error
    handling
    """

    def __init__(
        self, exchange_config: Dict[str, Any], system_config: Dict[str, Any]
    ):
        """
        Initialize exchange connection.

        Args:
            exchange_config: Exchange configuration (name, api_key, api_secret,
                testnet)
            system_config: System configuration (timeouts, rate limits, etc.)
        """
        self.config = exchange_config
        self.system_config = system_config
        self.exchange = self._initialize_exchange()

    def _initialize_exchange(self) -> ccxt.Exchange:
        """Initialize the exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.config["name"])
            exchange = exchange_class(
                {
                    "apiKey": self.config["api_key"],
                    "secret": self.config["api_secret"],
                    "enableRateLimit": True,
                    # Set timeouts during initialization
                    "options": {
                        "timeout": self.system_config.get("connection_timeout", 30) * 1000,
                        "recvWindow": self.system_config.get("read_timeout", 30) * 1000,
                    }
                }
            )

            if self.config["testnet"]:
                exchange.set_sandbox_mode(True)

            logger.info(f"Initialized {self.config['name']} exchange. Testnet: {self.config['testnet']}")
            return exchange

        except Exception as e:
            logger.error(
                f"Failed to initialize exchange: {e}", exc_info=True
            )
            raise

    async def _safe_async_call(self, method_name, *args, **kwargs):
        """Safely call a method that might be async or sync

        Args:
            method_name: Name of the method to call on self.exchange
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        Returns:
            Result of the method call
        """
        method = getattr(self.exchange, method_name)

        # Periksa apakah metode adalah coroutine function
        import inspect
        if inspect.iscoroutinefunction(method):
            # Jika async, panggil dengan await
            logger.debug(f"{method_name} adalah coroutine function, memanggil dengan await")
            return await method(*args, **kwargs)
        else:
            # Jika bukan async, panggil sebagai fungsi normal
            logger.debug(f"{method_name} bukan coroutine function, memanggil sebagai fungsi normal")
            return method(*args, **kwargs)

    @rate_limited_api()
    @handle_exchange_errors(notify=False)
    @retry_with_backoff(max_retries=3)
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """Fetch OHLCV data from exchange with rate limiting

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1h', '15m')
            limit: Number of candles to fetch

        Returns:
            DataFrame with OHLCV data or empty DataFrame on failure.
        """
        # Timeouts are now set during initialization
        logger.info(
            f"Requesting OHLCV data with explicit limit parameter",
            symbol=symbol,
            timeframe=timeframe,
            requested_limit=limit
        )
        try:
            ohlcv = await self._safe_async_call('fetch_ohlcv', symbol, timeframe, limit=limit)
        except Exception as e:
            logger.error(f"Error in fetch_ohlcv: {e}")
            # Fallback to direct call if _safe_async_call fails
            try:
                logger.debug(f"Fallback to direct call for fetch_ohlcv")
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return pd.DataFrame()  # Return empty dataframe on failure
        # handle_exchange_errors returns None on failure after retries
        if ohlcv is None:
            logger.warning(
                f"Failed to fetch OHLCV data for {symbol} after retries.",
                symbol=symbol,
                timeframe=timeframe,
            )
            return pd.DataFrame() # Return empty dataframe as per docstring

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Log dengan level INFO untuk memastikan terlihat di log
        logger.info(
            f"Fetched OHLCV candles: requested={limit}, received={len(df)}",
            symbol=symbol,
            timeframe=timeframe,
            requested_limit=limit,
            received_candles=len(df),
            received_vs_requested=f"{len(df)}/{limit}"
        )

        logger.debug(
            f"Fetched {len(df)} OHLCV candles for {symbol}",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
        )

        return df

    @rate_limited_api()
    @handle_exchange_errors(notify=False) # Notify false, as price is often polled
    @retry_with_backoff(max_retries=3) # Added retry
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current ticker information for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker information or None if error after retries.
        """
        try:
            ticker = await self._safe_async_call('fetch_ticker', symbol)
        except Exception as e:
            logger.error(f"Error in get_ticker: {e}")
            # Fallback to direct call
            try:
                logger.debug(f"Fallback to direct call for fetch_ticker")
                ticker = self.exchange.fetch_ticker(symbol)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return None
        if ticker:
            logger.debug(
                f"Fetched ticker for {symbol}",
                symbol=symbol,
                last_price=ticker.get("last"),
            )
        # handle_exchange_errors returns None on failure
        return ticker

    @rate_limited_api() # Added rate limit consistency
    @handle_exchange_errors(notify=False)
    @retry_with_backoff(max_retries=3) # Added retry consistency
    async def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Current price or 0 if error after retries.
        """
        ticker = await self.get_ticker(symbol)
        # get_ticker now returns None on failure after retries
        if ticker and "last" in ticker and ticker["last"] is not None:
            try:
                price = float(ticker["last"])
                return price
            except (ValueError, TypeError) as e:
                 logger.warning(f"Could not convert last price '{ticker['last']}' to float for {symbol}: {e}",
                              symbol=symbol, ticker_price=ticker['last'])
                 return 0.0 # Return 0 if conversion fails
        else:
            logger.warning(f"Could not get ticker or last price for {symbol} after retries.", symbol=symbol)
            return 0.0 # Return 0 if ticker failed or no last price

    @rate_limited_api()
    @handle_exchange_errors(notify=True)
    @retry_with_backoff(max_retries=3)
    async def get_all_balances(self) -> Dict[str, float]:
        """Get available balances for all assets with rate limiting

        Returns:
            Dictionary of asset balances
        """
        try:
            account_info = await self._safe_async_call('fetch_balance')
        except Exception as e:
            logger.error(f"Error in fetch_balance: {e}")
            # Fallback to direct call
            try:
                logger.debug(f"Fallback to direct call for fetch_balance")
                account_info = self.exchange.fetch_balance()
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return {}  # Return empty dict on failure

        balances = {}

        if "free" in account_info:
            # Filter out zero balances and format
            for asset, amount in account_info["free"].items():
                if amount > 0:
                    balances[asset] = amount

        logger.info(
            f"Fetched balances for {len(balances)} assets",
            assets=list(balances.keys()),
        )
        return balances

    @rate_limited_api()
    @handle_exchange_errors(notify=False)
    @retry_with_backoff(max_retries=3)
    async def get_available_balance(self, asset: str) -> float:
        """Get available balance for a specific asset

        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')

        Returns:
            Available balance for the asset or 0 if not found/error
        """
        try:
            balances = await self.get_all_balances()
            available = balances.get(asset, 0)

            logger.info(
                f"Available balance for {asset}: {available}",
                asset=asset,
                available=available
            )

            return available
        except Exception as e:
            logger.error(f"Failed to get available balance for {asset}: {e}",
                      asset=asset, exc_info=True)
            return 0

    @rate_limited_api()
    @handle_exchange_errors(notify=True)
    @retry_with_backoff(max_retries=3)
    async def place_market_buy(
        self, symbol: str, quantity: float
    ) -> Dict[str, Any]:
        """Place a market buy order and return execution details.

        Args:
            symbol: Trading pair symbol
            quantity: Order quantity

        Returns:
            Dict containing order details:
            {'order_id', 'symbol', 'average_price', 'filled_quantity'}
            Returns empty dict on failure before execution.
        """
        try:
            # Ensure quantity precision is respected if needed (depends on exchange)
            # quantity = self.exchange.amount_to_precision(symbol, quantity)

            try:
                order = await self._safe_async_call('create_market_buy_order', symbol, quantity)
            except Exception as e:
                logger.error(f"Error in create_market_buy_order: {e}")
                # Fallback to direct call
                order = self.exchange.create_market_buy_order(symbol, quantity)

            order_id = order.get("id")
            avg_price = order.get("average")
            filled_qty = order.get("filled")

            if order_id is None or avg_price is None or filled_qty is None:
                logger.warning(
                    f"Market buy order for {symbol} executed but details missing.",
                    symbol=symbol,
                    quantity=quantity,
                    order_data=order,
                )
                # Fallback or decide how to handle incomplete data
                # For now, return potentially incomplete dict but log it.

            logger.info(
                f"Placed market buy order for {symbol}",
                symbol=symbol,
                requested_quantity=quantity,
                filled_quantity=filled_qty,
                average_price=avg_price,
                order_id=order_id,
            )

            return {
                "order_id": order_id,
                "symbol": symbol,
                "average_price": avg_price,
                "filled_quantity": filled_qty,
            }
        except Exception as e:
            # Handle_exchange_errors decorator will catch this,
            # but logging specific context here can be useful.
            logger.error(f"Failed to place market buy order for {symbol}: {e}",
                         symbol=symbol, quantity=quantity, exc_info=True)
            # Re-raise or return indication of failure if decorator doesn't handle it fully
            raise # Let the decorator handle notification/reraising

    @rate_limited_api()
    @handle_exchange_errors(notify=True)
    @retry_with_backoff(max_retries=3)
    async def place_market_sell(
        self, symbol: str, quantity: float
    ) -> Dict[str, Any]:
        """Place a market sell order

        Args:
            symbol: Trading pair symbol
            quantity: Quantity to sell

        Returns:
            Order result with order_id, symbol, average_price, filled_quantity
        """
        try:
            # Extract base currency from symbol (e.g., 'BTCUSDT' -> 'BTC')
            base_currency = None
            if symbol.endswith('USDT'):
                base_currency = symbol[:-4]  # Remove 'USDT'
            elif 'BTC' in symbol and not symbol.startswith('BTC'):
                base_currency = symbol.split('BTC')[0]

            # Check available balance before attempting to sell
            if base_currency:
                available_balance = await self.get_available_balance(base_currency)
                if available_balance < quantity:
                    error_msg = f"Insufficient balance for {symbol}. Required: {quantity} {base_currency}, Available: {available_balance} {base_currency}"
                    logger.error(error_msg)
                    raise Exception(f"binance Account has insufficient balance for requested action. Available: {available_balance} {base_currency}, Required: {quantity} {base_currency}")

            # Precision handling - commented out for now
            # quantity = self.exchange.amount_to_precision(symbol, quantity)

            try:
                logger.info(f"Attempting to create market sell order for {symbol}",
                           symbol=symbol, quantity=quantity)
                order = await self._safe_async_call('create_market_sell_order', symbol, quantity)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error in create_market_sell_order: {error_msg}")

                # Check if this is an insufficient balance error
                if "insufficient balance" in error_msg.lower():
                    # Get available balance for better error message
                    if base_currency:
                        try:
                            available = await self.get_available_balance(base_currency)
                            raise Exception(f"binance Account has insufficient balance for requested action. Available: {available} {base_currency}, Required: {quantity} {base_currency}")
                        except:
                            # If we can't get balance, just re-raise the original error
                            raise e
                    else:
                        raise e

                # Fallback to direct call for other errors
                logger.warning(f"Falling back to synchronous call for {symbol}")
                order = self.exchange.create_market_sell_order(symbol, quantity)

            order_id = order.get("id")
            avg_price = order.get("average")
            filled_qty = order.get("filled")

            if order_id is None or avg_price is None or filled_qty is None:
                logger.warning(
                    f"Market sell order for {symbol} executed but details missing.",
                    symbol=symbol,
                    quantity=quantity,
                    order_data=order,
                )
                # Try to extract values from order data if possible
                if avg_price is None:
                    avg_price = order.get("price", 0)
                if filled_qty is None:
                    filled_qty = quantity  # Assume all filled if not specified

            logger.info(
                f"Placed market sell order for {symbol}",
                symbol=symbol,
                requested_quantity=quantity,
                filled_quantity=filled_qty,
                average_price=avg_price,
                order_id=order_id,
            )

            return {
                "order_id": order_id,
                "symbol": symbol,
                "average_price": avg_price,
                "filled_quantity": filled_qty,
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to place market sell order for {symbol}: {error_msg}",
                         symbol=symbol, quantity=quantity, exc_info=True)

            # Provide more specific error for insufficient balance
            if "insufficient balance" in error_msg.lower():
                # Extract base currency from symbol if possible
                base_currency = None
                if symbol.endswith('USDT'):
                    base_currency = symbol[:-4]

                # Try to get available balance for better error message
                if base_currency:
                    try:
                        available = await self.get_available_balance(base_currency)
                        raise Exception(f"binance Account has insufficient balance for requested action. Available: {available} {base_currency}, Required: {quantity} {base_currency}")
                    except:
                        # If we can't get balance, just re-raise the original error
                        raise e

            # For other errors, just re-raise
            raise  # Let the decorator handle notification/reraising

    @rate_limited_api()
    @handle_exchange_errors(notify=True) # Added error handler
    @retry_with_backoff(max_retries=3) # Added retry
    async def cancel_order(self, order_id: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Cancel an open order

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol

        Returns:
            Cancellation information dict or None if cancellation fails after retries.
        """
        # Decorators now handle errors and retries
        try:
            result = await self._safe_async_call('cancel_order', order_id, symbol)
        except Exception as e:
            logger.error(f"Error in cancel_order: {e}")
            # Fallback to direct call
            try:
                logger.debug(f"Fallback to direct call for cancel_order")
                result = self.exchange.cancel_order(order_id, symbol)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return None
        if result:
             logger.info(f"Successfully cancelled order {order_id} for {symbol}",
                         order_id=order_id, symbol=symbol)
        # handle_exchange_errors returns None on failure
        return result

    @rate_limited_api()
    @handle_exchange_errors(notify=False) # Added error handler
    @retry_with_backoff(max_retries=3) # Added retry
    async def fetch_open_orders(self, symbol: str) -> Optional[list]:
        """Fetch open orders for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            List of open orders or None if fetch fails after retries.
        """
        # Decorators now handle errors and retries
        try:
            orders = await self._safe_async_call('fetch_open_orders', symbol)
        except Exception as e:
            logger.error(f"Error in fetch_open_orders: {e}")
            # Fallback to direct call
            try:
                logger.debug(f"Fallback to direct call for fetch_open_orders")
                orders = self.exchange.fetch_open_orders(symbol)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return None
        if orders is not None: # Check if fetch was successful (not None)
             logger.debug(f"Fetched {len(orders)} open orders for {symbol}",
                          symbol=symbol, count=len(orders))
        # handle_exchange_errors returns None on failure
        return orders
