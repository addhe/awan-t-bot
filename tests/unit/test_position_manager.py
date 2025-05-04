"""
Unit tests for PositionManager
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.core.position_manager import PositionManager


@pytest.fixture
def mock_exchange():
    """Create a mock ExchangeConnector"""
    mock = MagicMock()

    # Setup async mock responses
    mock.get_current_price = AsyncMock(return_value=35000)
    mock.place_market_buy = AsyncMock(return_value={
        "order_id": "test_order_id",
        "symbol": "BTC/USDT",
        "side": "buy",
        "filled_quantity": 0.01,
        "average_price": 35000,
    })
    mock.place_market_sell = AsyncMock(return_value={
        "order_id": "test_sell_id",
        "symbol": "BTC/USDT",
        "side": "sell",
        "filled_quantity": 0.01,
        "average_price": 36000,
    })

    # Create a DataFrame for mock_fetch_ohlcv
    df = pd.DataFrame(
        {
            "open": [34000, 34500],
            "high": [35000, 35500],
            "low": [33500, 34000],
            "close": [34500, 35000],
            "volume": [10.5, 15.2],
        }
    )
    # Add some indicator values for testing
    df["bb_upper"] = [36000, 36500]
    df["bb_middle"] = [34500, 35000]
    df["bb_lower"] = [33000, 33500]
    df["ema"] = [34200, 34700]
    df["stoch_k"] = [85, 75]
    df["stoch_d"] = [80, 85]

    # Setup fetch_ohlcv as AsyncMock
    mock.fetch_ohlcv = AsyncMock(return_value=df)

    # Setup fetch_open_orders as AsyncMock
    mock.fetch_open_orders = AsyncMock(return_value=[])

    # Setup cancel_order as AsyncMock
    mock.cancel_order = AsyncMock(return_value=True)

    return mock


@pytest.fixture
def mock_monitor():
    """Create a mock BotStatusMonitor"""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_strategy():
    """Create a mock trading strategy"""
    mock = MagicMock()

    mock.should_sell.return_value = (True, 0.8)
    mock.calculate_indicators.side_effect = (
        lambda df: df
    )  # Return df unchanged

    return mock


@pytest.fixture
def position_manager(mock_exchange, mock_monitor):
    """Create a PositionManager with mock dependencies"""
    trading_config = {
        "max_open_trades": 5,
        "allocation_per_trade": 0.2,
        "min_allocation_usdt": 10,
        "max_allocation_usdt": 100,
    }

    manager = PositionManager(mock_exchange, trading_config, mock_monitor)
    return manager


class TestPositionManager:
    """Test PositionManager class"""

    @pytest.mark.asyncio
    async def test_open_position(
        self, position_manager, mock_exchange, mock_monitor
    ):
        """Test opening a position"""
        # Setup test data
        symbol = "BTC/USDT"
        quantity = 0.01
        risk_level = {"stop_loss": 33000, "take_profit": 38000}
        confidence = 0.7
        pair_config = {"symbol": "BTC/USDT", "min_quantity": 0.001}

        # Call the method
        result = await position_manager.open_position(
            symbol, quantity, risk_level, confidence, pair_config
        )

        # Check if methods were called correctly
        mock_exchange.place_market_buy.assert_called_once_with(
            symbol, quantity
        )

        # Validate active_trades was updated
        assert symbol in position_manager.active_trades
        assert position_manager.active_trades[symbol]["entry_price"] == 35000
        assert position_manager.active_trades[symbol]["quantity"] == quantity

        # Validate result
        assert result["symbol"] == symbol
        assert result["entry_price"] == 35000

    @pytest.mark.asyncio
    async def test_close_position(
        self, position_manager, mock_exchange, mock_monitor
    ):
        """Test closing a position"""
        # Setup test data
        symbol = "BTC/USDT"
        entry_price = 35000
        quantity = 0.01
        close_reason = "take_profit"

        # Add a test trade to active_trades
        position_manager.active_trades[symbol] = {
            "entry_price": entry_price,
            "quantity": quantity,
            "entry_time": datetime.now().isoformat(),
        }

        # Mock the current price for exit_price
        mock_exchange.get_current_price = AsyncMock(return_value=36000)

        # Call the method
        result = await position_manager.close_position(
            symbol, close_reason
        )

        # Check if methods were called correctly
        mock_exchange.place_market_sell.assert_called_once_with(
            symbol, quantity
        )

        # Check if completed trade was saved
        mock_monitor.save_completed_trade.assert_called_once()
        saved_trade = mock_monitor.save_completed_trade.call_args[0][0]
        assert saved_trade["symbol"] == symbol
        assert saved_trade["entry_price"] == entry_price
        assert saved_trade["close_reason"] == close_reason

        # Validate trade was removed from active trades
        assert symbol not in position_manager.active_trades

        # Validate result
        assert result["symbol"] == symbol
        assert result["entry_price"] == entry_price
        assert result["exit_price"] == 36000  # From mock_exchange.place_market_sell.return_value
        assert result["close_reason"] == close_reason

    @pytest.mark.asyncio
    async def test_check_positions(
        self, position_manager, mock_exchange, mock_strategy
    ):
        """Test checking positions for exit conditions"""
        # Setup test data
        symbol = "BTC/USDT"
        entry_price = 35000
        quantity = 0.01

        # Add a test trade to active_trades
        position_manager.active_trades[symbol] = {
            "entry_price": entry_price,
            "quantity": quantity,
            "entry_time": datetime.now().isoformat(),
            "stop_loss": 33000,
            "take_profit": 38000,
        }

        # Setup trading config with trailing stop
        position_manager.config = {
            "trailing_stop_pct": 0.02,
            "trailing_stop_activation_pct": 0.01,
        }

        # Mock the place_market_sell to return a valid result
        mock_exchange.place_market_sell = AsyncMock(return_value={
            "order_id": "test_sell_id",
            "average_price": 36000,
            "filled_quantity": 0.01,
        })

        # Mock get_current_price for _update_trades_status call
        mock_exchange.get_current_price = AsyncMock(return_value=36000)

        # Call the method
        closed_positions = await position_manager.check_positions(
            mock_strategy
        )

        # Check if methods were called correctly
        mock_exchange.fetch_ohlcv.assert_called_once_with(
            symbol, timeframe="15m", limit=10
        )
        mock_strategy.calculate_indicators.assert_called_once()
        mock_strategy.should_sell.assert_called_once()

        # Validate result
        assert len(closed_positions) == 1
        assert closed_positions[0]["symbol"] == symbol
        assert (
            closed_positions[0]["close_reason"] == "signal"
        )  # Because mock should_sell returns True

        # Validate trade was removed from active trades
        assert symbol not in position_manager.active_trades

    @pytest.mark.asyncio
    async def test_update_trades_status(
        self, position_manager, mock_exchange, mock_monitor
    ):
        """Test updating trade status"""
        # Setup test data
        symbols = ["BTC/USDT", "ETH/USDT"]

        # Add test trades to active_trades
        for symbol in symbols:
            position_manager.active_trades[symbol] = {
                "entry_price": 35000,
                "quantity": 0.01,
                "entry_time": datetime.now().isoformat(),
            }

        # Ensure get_current_price returns a value
        mock_exchange.get_current_price = AsyncMock(return_value=36000)

        # Call the method
        await position_manager._update_trades_status()

        # Check if methods were called correctly
        assert mock_exchange.get_current_price.call_count == 2
        mock_monitor.update_trades.assert_called_once()

        # Validate the trades info passed to update_trades
        trades_info = mock_monitor.update_trades.call_args[0][0]
        assert len(trades_info) == 2
        symbols_in_trades = [trade["symbol"] for trade in trades_info]
        assert all(symbol in symbols_in_trades for symbol in symbols)
