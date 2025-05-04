"""
Unit tests for TradingBot.

This module contains unit tests for the TradingBot class.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock
from src.core.trading_bot import TradingBot


class AsyncMockWithContext(AsyncMock):
    """
    Async mock that can be used as context manager.

    This class is used to create a mock object
    that can be used as a context manager.
    """
    """Async mock that can be used as context manager"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def mock_exchange():
    """Create a mock ExchangeConnector"""
    mock = AsyncMock()

    # Setup mock responses
    mock.get_all_balances.return_value = {"BTC": 0.1, "USDT": 1000}
    mock.get_current_price.return_value = 35000

    async def mock_fetch_ohlcv(symbol, timeframe="15m", limit=10):
        """Mock fetch_ohlcv method"""
        df = pd.DataFrame(
            {
                "open": [34000, 34500],
                "high": [35000, 35500],
                "low": [33500, 34000],
                "close": [34500, 35000],
                "volume": [10.5, 15.2],
            }
        )
        return df

    mock.fetch_ohlcv.side_effect = mock_fetch_ohlcv

    return mock


@pytest.fixture
def mock_strategy():
    """Create a mock trading strategy"""
    mock = MagicMock()

    # Setup mock responses
    mock.calculate_indicators.side_effect = (
        lambda df: df
    )  # Return df unchanged
    mock.analyze_signals.return_value = (
        "neutral",
        0.0,
        {"stop_loss": 0, "take_profit": 0},
    )
    mock.should_sell.return_value = (False, 0.0)
    mock.calculate_position_size.return_value = (
        0.01,
        {"allocation_pct": 20, "allocation_usdt": 100, "max_allocation": 100},
    )

    return mock


@pytest.fixture
def mock_position_manager():
    """Create a mock PositionManager"""
    mock = AsyncMock()

    # Setup mock responses
    mock.active_trades = {}
    mock.check_positions.return_value = []

    return mock


@pytest.fixture
def mock_monitor():
    """Create a mock BotStatusMonitor"""
    mock = MagicMock()

    # Setup mock responses
    mock.get_completed_trades.return_value = []
    mock.format_status_message.return_value = "Status message"

    return mock


@pytest.fixture
def trading_bot(
    monkeypatch,
    mock_exchange,
    mock_strategy,
    mock_position_manager,
    mock_monitor,
):
    """Create a TradingBot with mock dependencies"""
    # Setup patches
    monkeypatch.setattr(
        "src.core.trading_bot.ExchangeConnector", lambda *args: mock_exchange
    )
    monkeypatch.setattr(
        "src.core.trading_bot.BollStochStrategy",
        lambda **kwargs: mock_strategy,
    )
    monkeypatch.setattr(
        "src.core.trading_bot.PositionManager",
        lambda *args: mock_position_manager,
    )
    monkeypatch.setattr(
        "src.core.trading_bot.send_telegram_message", AsyncMock()
    )

    # Create bot instance and inject mock monitor
    bot = TradingBot()
    bot.monitor = mock_monitor
    
    # Explicitly set exchange, strategy, and position_manager
    bot.exchange = mock_exchange
    bot.strategy = mock_strategy
    bot.position_manager = mock_position_manager

    return (
        bot,
        mock_exchange,
        mock_strategy,
        mock_position_manager,
        mock_monitor,
    )


class TestTradingBot:
    """Test TradingBot class"""

    @pytest.mark.asyncio
    async def test_initialize(self, trading_bot):
        """Test bot initialization"""
        bot, mock_exchange, mock_strategy, mock_position_manager, _ = (
            trading_bot
        )

        # Call the method
        await bot.initialize()

        # Validate components are correctly initialized
        assert bot.exchange == mock_exchange
        assert bot.strategy == mock_strategy
        assert bot.position_manager == mock_position_manager

    @pytest.mark.asyncio
    async def test_check_health(self, trading_bot):
        """Test health check"""
        bot, mock_exchange, _, _, _ = trading_bot

        # Call the method
        result = await bot.check_health()

        # Check if exchange method was called
        mock_exchange.get_all_balances.assert_called_once()

        # Validate result
        assert result is True

    @pytest.mark.asyncio
    async def test_check_health_no_balance(self, trading_bot):
        """Test health check with no balance"""
        bot, mock_exchange, _, _, _ = trading_bot

        # Setup mock to return empty balance
        mock_exchange.get_all_balances.return_value = {}

        # Call the method
        result = await bot.check_health()

        # Validate result
        assert result is False

    @pytest.mark.asyncio
    async def test_process_pair_no_signal(self, trading_bot):
        """Test processing a pair with no buy signal"""
        bot, mock_exchange, mock_strategy, _, _ = trading_bot

        # Setup mock to return neutral signal
        mock_strategy.analyze_signals.return_value = (
            "neutral",
            0.0,
            {"stop_loss": 0, "take_profit": 0},
        )

        # Call the method
        pair_config = {
            "symbol": "BTC/USDT",
            "min_quantity": 0.001,
            "quantity_precision": 5,
        }
        result = await bot.process_pair(pair_config)

        # Check if methods were called correctly
        mock_exchange.fetch_ohlcv.assert_called()
        mock_strategy.analyze_signals.assert_called_once()

        # Validate result
        assert result is False

    @pytest.mark.asyncio
    async def test_process_pair_buy_signal(self, trading_bot):
        """Test processing a pair with buy signal"""
        bot, mock_exchange, mock_strategy, mock_position_manager, _ = (
            trading_bot
        )

        # Setup mock to return buy signal
        mock_strategy.analyze_signals.return_value = (
            "buy",
            0.8,
            {"stop_loss": 33000, "take_profit": 38000},
        )

        # Call the method
        pair_config = {
            "symbol": "BTC/USDT",
            "min_quantity": 0.001,
            "quantity_precision": 5,
        }
        result = await bot.process_pair(pair_config)

        # Check if methods were called correctly
        mock_exchange.fetch_ohlcv.assert_called()
        mock_strategy.analyze_signals.assert_called_once()
        mock_exchange.get_all_balances.assert_called_once()
        mock_exchange.get_current_price.assert_called_once_with("BTC/USDT")
        mock_strategy.calculate_position_size.assert_called_once()
        mock_position_manager.open_position.assert_called_once()

        # Validate result
        assert result is True

    @pytest.mark.asyncio
    async def test_update_status(self, trading_bot):
        """Test updating bot status"""
        bot, mock_exchange, _, _, mock_monitor = trading_bot

        # Call the method
        await bot.update_status()

        # Check if methods were called correctly
        mock_exchange.get_all_balances.assert_called_once()
        mock_monitor.update_bot_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_performance(self, trading_bot):
        """Test calculating performance metrics"""
        bot, _, _, _, mock_monitor = trading_bot

        # Setup mock to return some completed trades
        mock_monitor.get_completed_trades.return_value = [
            {"profit": 2.5},
            {"profit": -1.2},
            {"profit": 3.0},
        ]

        # Call the method
        performance = bot._calculate_performance()

        # Check if monitor method was called
        mock_monitor.get_completed_trades.assert_called_once()

        # Validate result
        assert performance["total_trades"] == 3
        assert performance["win_rate"] == pytest.approx(
            66.67, abs=0.01
        )  # 2/3 winning trades
        assert performance["total_profit"] == pytest.approx(4.3, abs=0.01)
