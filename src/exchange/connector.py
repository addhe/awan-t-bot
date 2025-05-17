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

    def _initialize_exchange(self):
        """Initialize the exchange connection"""
        try:
            exchange_name = self.config["name"].lower()
            logger.info(f"Initializing {exchange_name} exchange connection...")
            
            # Check if exchange is supported by CCXT
            if exchange_name not in ccxt.exchanges:
                raise ValueError(f"Exchange {exchange_name} is not supported by CCXT")
            
            # Get exchange class
            exchange_class = getattr(ccxt, exchange_name)
            
            # Prepare config
            exchange_config = {
                "apiKey": self.config["api_key"],
                "secret": self.config["api_secret"],
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",  # Default to spot market
                    "adjustForTimeDifference": True,
                    "recvWindow": self.system_config.get("read_timeout", 30) * 1000,
                },
                "timeout": self.system_config.get("connection_timeout", 30) * 1000,
                "verbose": self.system_config.get("debug", False),  # Enable verbose mode for debugging
            }
            
            logger.debug(f"Exchange config: {exchange_config}")
            
            # Initialize exchange
            exchange = exchange_class(exchange_config)
            
            # Set sandbox mode if enabled
            if self.config.get("testnet", False):
                logger.info("Enabling testnet/sandbox mode")
                exchange.set_sandbox_mode(True)
            
            # Load markets
            try:
                logger.info("Loading markets...")
                exchange.load_markets()
                logger.info(f"Successfully loaded {len(exchange.markets)} markets")
            except Exception as e:
                logger.warning(f"Could not load markets: {e}")
            
            # Test connectivity
            try:
                logger.info("Testing exchange connectivity...")
                exchange.fetch_time()
                logger.info("Exchange connectivity test successful")
            except Exception as e:
                logger.warning(f"Exchange connectivity test failed: {e}")
            
            logger.info(f"Successfully initialized {exchange_name} exchange")
            return exchange

        except Exception as e:
            error_msg = f"Failed to initialize exchange {self.config.get('name', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    async def _safe_async_call(self, method_name, *args, **kwargs):
        """Safely call a method that might be async or sync

        Args:
            method_name: Name of the method to call on self.exchange
            *args: Arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        Returns:
            Result of the method call
        """
        try:
            # Log the method call with parameters (without sensitive data)
            safe_kwargs = {k: '***' if 'secret' in k.lower() or 'key' in k.lower() else v 
                          for k, v in kwargs.items()}
            logger.info(f"Calling exchange method: {method_name}")
            logger.debug(f"Method args: {args}, kwargs: {safe_kwargs}")
            
            # Get the method from the exchange instance
            if not hasattr(self.exchange, method_name):
                raise AttributeError(f"Exchange does not have method: {method_name}")
                
            method = getattr(self.exchange, method_name)

            # Check if the method is a coroutine function
            import inspect
            import asyncio
            
            if inspect.iscoroutinefunction(method):
                # If async, call with await
                logger.debug(f"{method_name} is a coroutine function, calling with await")
                result = await method(*args, **kwargs)
            else:
                # If not async, run in executor to avoid blocking the event loop
                logger.debug(f"{method_name} is not a coroutine, running in executor")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,  # Use default executor
                    lambda: method(*args, **kwargs)
                )
            
            # Log successful call
            logger.debug(f"Successfully called {method_name}")
            return result
            
        except ccxt.NetworkError as e:
            logger.error(f"Network error in {method_name}: {str(e)}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error in {method_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {method_name}: {str(e)}", exc_info=True)
            raise

    @rate_limited_api()
    @handle_exchange_errors(notify=False)
    @retry_with_backoff(max_retries=3)
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """Fetch OHLCV data from exchange or Redis cache

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1h', '15m')
            limit: Number of candles to fetch

        Returns:
            DataFrame with OHLCV data or empty DataFrame on failure.
        """
        # Import Redis manager here to avoid circular imports
        from src.utils.redis_manager import redis_manager

        # Try to get data from Redis first
        cached_df = None
        try:
            cached_df = redis_manager.get_ohlcv(symbol, timeframe)
            if cached_df is not None and len(cached_df) >= limit:
                logger.info(
                    f"Using cached OHLCV data from Redis",
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=len(cached_df)
                )
                # Return the most recent 'limit' candles
                return cached_df.sort_index(ascending=False).head(limit).sort_index()
        except Exception as redis_err:
            logger.warning(f"Error accessing Redis cache: {redis_err}")

        # If not in cache or not enough data, fetch from exchange
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
                # If we have cached data but not enough, return what we have
                if cached_df is not None:
                    logger.warning(f"Using partial cached data due to API failure")
                    return cached_df
                return pd.DataFrame()  # Return empty dataframe on failure

        # handle_exchange_errors returns None on failure after retries
        if ohlcv is None:
            logger.warning(
                f"Failed to fetch OHLCV data for {symbol} after retries.",
                symbol=symbol,
                timeframe=timeframe,
            )
            # If we have cached data but not enough, return what we have
            if cached_df is not None:
                logger.warning(f"Using partial cached data due to API failure")
                return cached_df
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
    async def get_all_balances(self) -> Dict[str, Dict[str, float]]:
        """Get available, used, and total balances for all assets

        Returns:
            Dictionary containing balance information for each asset:
            {
                'BTC': {'free': 0.1, 'used': 0.0, 'total': 0.1},
                'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0},
                ...
            }
        """
        balances = {}

        try:
            # Try with different account types if needed
            account_types = [None, 'future', 'spot', 'margin', 'swap']
            account_info = None
            last_error = None

            for account_type in account_types:
                try:
                    params = {'type': account_type} if account_type is not None else {}
                    logger.debug(f"Trying to fetch balance with params: {params}")
                    account_info = await self._safe_async_call('fetch_balance', params)

                    # Log raw response for debugging
                    logger.debug(f"Raw response from exchange: {account_info}")
                    
                    # If we get here, the call was successful
                    logger.info(f"Successfully fetched balance with params: {params}")
                    
                    # Check if we got valid data
                    if account_info and (account_info.get('free') or account_info.get('total')):
                        logger.info(f"Found valid balance data with account type: {account_type}")
                        break
                    else:
                        logger.warning(f"No balance data found with account type: {account_type}")
                except Exception as e:
                    last_error = e
                    logger.warning(f"Failed to fetch balance with params {params}: {str(e)}", exc_info=True)

                except Exception as e:
                    last_error = e
                    logger.warning(f"Failed to fetch balance with params {params}: {e}")

            # If all attempts failed
            if account_info is None:
                logger.error(f"All balance fetch attempts failed. Last error: {last_error}")
                return {}

            # Log raw account info for debugging (safely)
            try:
                # Try to get a string representation of the response
                response_str = str(account_info)
                if len(response_str) > 500:  # Truncate very large responses
                    response_str = response_str[:500] + '... (truncated)'
                
                logger.info(f"Raw exchange response: {response_str}")
                
                # Try to extract and log balance info
                if hasattr(account_info, 'keys'):
                    logger.info(f"Response keys: {list(account_info.keys())}")
                    
                    # Check common balance keys
                    for key in ['free', 'used', 'total', 'info', 'balances']:
                        if key in account_info:
                            logger.info(f"Found key '{key}' in response")
                            
                            # Log first few items if it's a dict
                            if isinstance(account_info[key], dict):
                                items = list(account_info[key].items())[:5]  # First 5 items
                                logger.info(f"First few items in '{key}': {items}")
            except Exception as e:
                logger.error(f"Error logging account info: {e}", exc_info=True)

            # Handle different exchange response formats
            if not isinstance(account_info, dict):
                logger.error(f"Unexpected account_info type: {type(account_info)}")
                return {}

            # Try to extract balances from different possible locations
            balance_data = None
            for key in ['info', 'result', 'data']:
                if key in account_info and isinstance(account_info[key], dict):
                    balance_data = account_info[key]
                    break

            # If no nested data found, use the account_info directly
            balance_data = balance_data or account_info

            # Binance specific handling - check for 'balances' in the response
            if 'balances' in balance_data and isinstance(balance_data['balances'], list):
                logger.info("Found 'balances' list in response, processing Binance format")
                for balance in balance_data['balances']:
                    try:
                        asset = balance.get('asset')
                        if not asset:
                            continue
                            
                        free = float(balance.get('free', 0) or 0)
                        locked = float(balance.get('locked', 0) or 0)
                        total = free + locked
                        
                        if free > 0 or locked > 0:
                            balances[asset] = {
                                'free': free,
                                'used': locked,
                                'total': total
                            }
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing balance for {balance}: {e}", exc_info=True)
            else:
                # Original handling for other exchanges
                free_balances = balance_data.get('free', {}) or {}
                used_balances = balance_data.get('used', {}) or {}
                total_balances = balance_data.get('total', {}) or {}

                # Get all asset symbols
                all_assets = set()
                for bal_dict in [free_balances, used_balances, total_balances]:
                    if isinstance(bal_dict, dict):
                        all_assets.update(k for k in bal_dict.keys() if k is not None)

                # Process each asset
                for asset in all_assets:
                    if not asset:  # Skip None or empty keys
                        continue

                    try:
                        free = float(free_balances.get(asset, 0) or 0)
                        used = float(used_balances.get(asset, 0) or 0)
                        total = float(total_balances.get(asset, 0) or 0)

                        # Only include assets with non-zero balance
                        if free > 0 or used > 0 or total > 0:
                            balances[asset] = {
                                'free': free,
                                'used': used,
                                'total': total
                            }
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error processing balance for {asset}: {e}")

            logger.info(
                f"Fetched balances for {len(balances)} assets",
                assets=list(balances.keys()),
                total_assets=len(balances),
                usdt_balance=balances.get('USDT', {}).get('total', 0)
            )

        except Exception as e:
            logger.error(f"Unexpected error in get_all_balances: {e}", exc_info=True)
            return {}

        return balances

    @rate_limited_api()
    @handle_exchange_errors(notify=False)
    @retry_with_backoff(max_retries=3)
    async def get_available_balance(self, asset: str) -> float:
        """Get available balance for a specific asset

        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')

        Returns:
            Available (free) balance for the asset or 0 if not found/error
        """
        try:
            balances = await self.get_all_balances()
            asset_balance = balances.get(asset, {})

            # Get free balance, fallback to 0 if not found
            available = float(asset_balance.get('free', 0) or 0)

            logger.info(
                f"Available balance for {asset}",
                asset=asset,
                free_balance=available,
                used_balance=asset_balance.get('used', 0),
                total_balance=asset_balance.get('total', 0)
            )

            return available
        except Exception as e:
            logger.error(
                f"Failed to get available balance for {asset}: {e}",
                asset=asset,
                exc_info=True
            )
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
