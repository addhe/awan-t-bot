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
                }
            )

            if self.config["testnet"]:
                exchange.set_sandbox_mode(True)

            return exchange

        except Exception as e:
            logger.error(
                f"Failed to initialize exchange: {e}"
            )
            raise

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
            DataFrame with OHLCV data
        """
        # Configure timeouts
        self.exchange.options["timeout"] = (
            self.system_config["connection_timeout"] * 1000
        )
        self.exchange.options["recvWindow"] = (
            self.system_config["read_timeout"] * 1000
        )

        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv:
            logger.warning(
                f"No OHLCV data returned for {symbol}",
                symbol=symbol,
                timeframe=timeframe,
            )
            return pd.DataFrame()

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        logger.debug(
            f"Fetched {len(df)} OHLCV candles for {symbol}",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
        )

        return df

    @rate_limited_api()
    @handle_exchange_errors(notify=True)
    @retry_with_backoff(max_retries=3)
    async def get_all_balances(self) -> Dict[str, float]:
        """Get available balances for all assets with rate limiting

        Returns:
            Dictionary of asset balances
        """
        account_info = self.exchange.fetch_balance()
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
    async def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current ticker information for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker information or None if error
        """
        ticker = self.exchange.fetch_ticker(symbol)
        logger.debug(
            f"Fetched ticker for {symbol}",
            symbol=symbol,
            last_price=ticker.get("last"),
        )
        return ticker

    @handle_exchange_errors(notify=False)
    async def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Current price or 0 if error
        """
        ticker = await self.get_ticker(symbol)
        price = float(ticker["last"]) if ticker and "last" in ticker else 0
        return price

    @rate_limited_api()
    @handle_exchange_errors(notify=True)
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
            
            order = await self.exchange.create_market_buy_order(symbol, quantity)
            
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
    async def place_market_sell(
        self, symbol: str, quantity: float
    ) -> Dict[str, Any]:
        """Place a market sell order and return execution details.

        Args:
            symbol: Trading pair symbol
            quantity: Order quantity

        Returns:
            Dict containing order details: 
            {'order_id', 'symbol', 'average_price', 'filled_quantity'}
            Returns empty dict on failure before execution.
        """
        try:
            # Ensure quantity precision is respected
            # quantity = self.exchange.amount_to_precision(symbol, quantity)

            order = await self.exchange.create_market_sell_order(symbol, quantity)
            
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
                # Fallback or decide how to handle incomplete data

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
            logger.error(f"Failed to place market sell order for {symbol}: {e}", 
                         symbol=symbol, quantity=quantity, exc_info=True)
            raise # Let the decorator handle notification/reraising

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
            logger.error(
                f"Error cancelling order {order_id} for {symbol}: {e}"
            )
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
            logger.error(
                f"Error fetching open orders for {symbol}: {e}"
            )
            return []
