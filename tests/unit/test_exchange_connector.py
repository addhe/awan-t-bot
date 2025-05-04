"""
Unit tests for ExchangeConnector
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.exchange.connector import ExchangeConnector

# Test configuration
MOCK_EXCHANGE_CONFIG = {
    "name": "binance",
    "api_key": "test_key",
    "api_secret": "test_secret",
    "testnet": True,
}

MOCK_SYSTEM_CONFIG = {
    "connection_timeout": 10,
    "read_timeout": 60,
    "retry_wait": 5,
    "check_interval": 60,
}


@pytest.fixture
def mock_ccxt():
    """Mock the ccxt library"""
    with patch("src.exchange.connector.ccxt") as mock_ccxt:
        # Setup mock exchange instance
        mock_exchange = MagicMock()
        mock_ccxt.binance.return_value = mock_exchange

        # Setup mock responses
        mock_exchange.fetch_ohlcv.return_value = [
            [
                1625097600000,
                35000,
                36000,
                34500,
                35500,
                10.5,
            ],  # timestamp, open, high, low, close, volume
            [1625097900000, 35500, 36200, 35000, 36000, 15.2],
        ]

        mock_exchange.fetch_balance.return_value = {
            "free": {"BTC": 0.1, "USDT": 1000}
        }

        mock_exchange.fetch_ticker.return_value = {
            "symbol": "BTC/USDT",
            "last": 35000,
        }

        mock_exchange.create_market_buy_order.return_value = {
            "id": "test_order_id",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.01,
            "price": 35000,
        }

        mock_exchange.create_market_sell_order.return_value = {
            "id": "test_order_id",
            "symbol": "BTC/USDT",
            "side": "sell",
            "amount": 0.01,
            "price": 35000,
        }

        yield mock_ccxt, mock_exchange


@pytest.fixture
def exchange_connector(mock_ccxt):
    """Create an ExchangeConnector instance with mocked ccxt"""
    _, _ = mock_ccxt  # Unpack the tuple but we don't need it here
    connector = ExchangeConnector(MOCK_EXCHANGE_CONFIG, MOCK_SYSTEM_CONFIG)
    return connector


class TestExchangeConnector:
    """Test ExchangeConnector class"""

    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, exchange_connector, mock_ccxt):
        """Test fetching OHLCV data"""
        _, mock_exchange = mock_ccxt

        # Call the method
        df = await exchange_connector.fetch_ohlcv(
            "BTC/USDT", timeframe="1h", limit=10
        )

        # Check if ccxt method was called correctly
        mock_exchange.fetch_ohlcv.assert_called_once_with(
            "BTC/USDT", "1h", limit=10
        )

        # Validate result
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "open" in df.columns
        assert "close" in df.columns
        assert df["close"].iloc[-1] == 36000

    @pytest.mark.asyncio
    async def test_get_all_balances(self, exchange_connector, mock_ccxt):
        """Test fetching all balances"""
        _, mock_exchange = mock_ccxt

        # Call the method
        balances = await exchange_connector.get_all_balances()

        # Check if ccxt method was called correctly
        mock_exchange.fetch_balance.assert_called_once()

        # Validate result
        assert isinstance(balances, dict)
        assert "BTC" in balances
        assert "USDT" in balances
        assert balances["BTC"] == 0.1
        assert balances["USDT"] == 1000

    @pytest.mark.asyncio
    async def test_get_current_price(self, exchange_connector, mock_ccxt):
        """Test getting current price"""
        _, mock_exchange = mock_ccxt

        # Call the method
        price = await exchange_connector.get_current_price("BTC/USDT")

        # Check if ccxt method was called correctly
        mock_exchange.fetch_ticker.assert_called_once_with("BTC/USDT")

        # Validate result
        assert price == 35000

    @pytest.mark.asyncio
    async def test_place_market_buy(self, exchange_connector, mock_ccxt):
        """Test placing market buy order"""
        _, mock_exchange = mock_ccxt

        # Call the method
        order = await exchange_connector.place_market_buy("BTC/USDT", 0.01)

        # Check if ccxt method was called correctly
        mock_exchange.create_market_buy_order.assert_called_once_with(
            "BTC/USDT", 0.01
        )

        # Validate result
        assert order["id"] == "test_order_id"
        assert order["side"] == "buy"

    @pytest.mark.asyncio
    async def test_place_market_sell(self, exchange_connector, mock_ccxt):
        """Test placing market sell order"""
        _, mock_exchange = mock_ccxt

        # Call the method
        order = await exchange_connector.place_market_sell("BTC/USDT", 0.01)

        # Check if ccxt method was called correctly
        mock_exchange.create_market_sell_order.assert_called_once_with(
            "BTC/USDT", 0.01
        )

        # Validate result
        assert order["id"] == "test_order_id"
        assert order["side"] == "sell"

    @pytest.mark.asyncio
    async def test_network_error_handling(self, exchange_connector, mock_ccxt):
        """Test handling of network errors"""
        _, mock_exchange = mock_ccxt

        # Setup mock to raise NetworkError
        import ccxt

        mock_exchange.fetch_ohlcv.side_effect = ccxt.NetworkError(
            "Network error"
        )

        # Call the method - should not raise but return empty DataFrame
        df = await exchange_connector.fetch_ohlcv("BTC/USDT")

        # Validate result
        assert isinstance(df, pd.DataFrame)
        assert df.empty
