"""
Unit tests for BollStochStrategy
"""

import pytest
import pandas as pd
import numpy as np

from src.strategies.boll_stoch_strategy import BollStochStrategy


@pytest.fixture
def strategy():
    """Create a BollStochStrategy instance"""
    return BollStochStrategy(
        boll_window=20,
        boll_std=2.0,
        ema_window=50,
        stoch_window=14,
        stoch_smooth_k=3,
        stoch_smooth_d=3,
        timeframes=["15m", "1h", "4h"],
    )


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing"""
    # Create sample price data
    np.random.seed(42)  # For reproducibility
    n = 100
    close_prices = np.random.normal(35000, 1000, n).cumsum()  # Random walk

    df = pd.DataFrame(
        {
            "open": close_prices - np.random.normal(100, 50, n),
            "high": close_prices + np.random.normal(200, 100, n),
            "low": close_prices - np.random.normal(200, 100, n),
            "close": close_prices,
            "volume": np.random.normal(10, 5, n),
        }
    )

    # Set datetime index
    date_range = pd.date_range(start="2023-01-01", periods=n, freq="15min")
    df.index = date_range

    return df


class TestBollStochStrategy:
    """Test BollStochStrategy class"""

    def test_calculate_indicators(self, strategy, sample_df):
        """Test calculating indicators"""
        # Call the method
        result_df = strategy.calculate_indicators(sample_df)

        # Validate result
        assert "bb_upper" in result_df.columns
        assert "bb_middle" in result_df.columns
        assert "bb_lower" in result_df.columns
        assert "ema" in result_df.columns
        assert "stoch_k" in result_df.columns
        assert "stoch_d" in result_df.columns

        # Check that indicators are calculated correctly
        assert not result_df["bb_upper"].isna().any()
        assert not result_df["bb_middle"].isna().any()
        assert not result_df["bb_lower"].isna().any()
        assert not result_df["ema"].isna().any()
        assert not result_df["stoch_k"].isna().any()
        assert not result_df["stoch_d"].isna().any()

        # Check Bollinger Bands relationship
        assert (result_df["bb_upper"] > result_df["bb_middle"]).all()
        assert (result_df["bb_middle"] > result_df["bb_lower"]).all()

    def test_analyze_signals_no_data(self, strategy):
        """Test analyze_signals with no data"""
        # Call the method with empty timeframe_data
        signal, confidence, risk_levels = strategy.analyze_signals({})

        # Validate result
        assert signal == "neutral"
        assert confidence == 0.0
        assert "stop_loss" in risk_levels
        assert "take_profit" in risk_levels

    def test_analyze_signals_buy(self, strategy, sample_df):
        """Test analyze_signals with buy signal"""
        # Modify the dataframe to create a buy signal
        df = sample_df.copy()
        result_df = strategy.calculate_indicators(df)

        # Set up conditions for a buy signal in the last candle
        # Price below lower BB, above EMA, stoch_k < 20 and stoch_k > stoch_d
        result_df.iloc[-1, result_df.columns.get_loc("close")] = (
            result_df["bb_lower"].iloc[-1] * 0.99
        )
        result_df.iloc[-1, result_df.columns.get_loc("ema")] = (
            result_df["close"].iloc[-1] * 0.98
        )
        result_df.iloc[-1, result_df.columns.get_loc("stoch_k")] = 15
        result_df.iloc[-1, result_df.columns.get_loc("stoch_d")] = 10

        # Call the method
        timeframe_data = {"15m": result_df}
        signal, confidence, risk_levels = strategy.analyze_signals(
            timeframe_data
        )

        # Validate result
        assert signal == "buy"
        assert confidence > 0.0
        assert "stop_loss" in risk_levels
        assert "take_profit" in risk_levels

    def test_analyze_signals_sell(self, strategy, sample_df):
        """Test analyze_signals with sell signal"""
        # Modify the dataframe to create a sell signal
        df = sample_df.copy()
        result_df = strategy.calculate_indicators(df)

        # Set up conditions for a sell signal in the last candle
        # Price above upper BB, below EMA, stoch_k > 80 and stoch_k < stoch_d
        result_df.iloc[-1, result_df.columns.get_loc("close")] = (
            result_df["bb_upper"].iloc[-1] * 1.01
        )
        result_df.iloc[-1, result_df.columns.get_loc("ema")] = (
            result_df["close"].iloc[-1] * 1.02
        )
        result_df.iloc[-1, result_df.columns.get_loc("stoch_k")] = 85
        result_df.iloc[-1, result_df.columns.get_loc("stoch_d")] = 90

        # Call the method
        timeframe_data = {"15m": result_df}
        signal, confidence, risk_levels = strategy.analyze_signals(
            timeframe_data
        )

        # Validate result
        assert signal == "sell"
        assert confidence > 0.0
        assert "stop_loss" in risk_levels
        assert "take_profit" in risk_levels

    def test_should_sell(self, strategy, sample_df):
        """Test should_sell method"""
        # Modify the dataframe to create sell conditions
        df = sample_df.copy()
        result_df = strategy.calculate_indicators(df)

        # Set up sell conditions
        result_df.iloc[-1, result_df.columns.get_loc("close")] = (
            result_df["bb_upper"].iloc[-1] * 1.01
        )
        result_df.iloc[-1, result_df.columns.get_loc("ema")] = (
            result_df["close"].iloc[-1] * 1.02
        )
        result_df.iloc[-1, result_df.columns.get_loc("stoch_k")] = 85
        result_df.iloc[-1, result_df.columns.get_loc("stoch_d")] = 90

        # Call the method
        should_sell, confidence = strategy.should_sell(result_df)

        # Validate result
        assert should_sell is True
        assert confidence > 0.0

    def test_calculate_pnl(self, strategy):
        """Test calculate_pnl method"""
        # Call the method
        entry_price = 35000
        current_price = 36000
        pnl = strategy.calculate_pnl(entry_price, current_price)

        # Validate result
        assert pnl == ((current_price - entry_price) / entry_price) * 100
        assert pnl == pytest.approx(2.857, abs=0.001)  # 2.857% profit

    def test_calculate_position_size(self, strategy):
        """Test calculate_position_size method"""
        # Setup test data
        balance = 1000
        current_price = 35000
        pair_config = {"symbol": "BTC/USDT", "quantity_precision": 5}
        trading_config = {
            "allocation_per_trade": 0.2,
            "min_allocation_usdt": 10,
            "max_allocation_usdt": 100,
        }

        # Call the method
        quantity, allocation_info = strategy.calculate_position_size(
            balance, current_price, pair_config, trading_config
        )

        # Validate result
        expected_allocation = min(
            balance * trading_config["allocation_per_trade"],
            trading_config["max_allocation_usdt"],
        )
        expected_quantity = expected_allocation / current_price

        assert quantity == round(
            expected_quantity, pair_config["quantity_precision"]
        )
        assert (
            allocation_info["allocation_pct"]
            == trading_config["allocation_per_trade"] * 100
        )
        assert allocation_info["allocation_usdt"] == expected_allocation
