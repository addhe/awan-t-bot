import pandas as pd
import logging
from typing import Dict, Any
from src.strategies.boll_stoch_strategy import BollStochStrategy


def calculate_indicators(
    timeframe_data: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Calculate indicators for each timeframe.

    Args:
        timeframe_data (Dict[str, pd.DataFrame]): A dictionary containing
            timeframe data.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary containing calculated
            indicators for each timeframe.
    """
    try:
        strategy = BollStochStrategy()

        # Calculate indicators for each timeframe
        for timeframe, df in timeframe_data.items():
            df = strategy.calculate_indicators(df)
            timeframe_data[timeframe] = df

        return timeframe_data
    except Exception as e:
        logging.error(f"Error calculating indicators: {e}")
        raise


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_macd(
    prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple:
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line


def check_market_conditions(
    timeframe_data: Dict[str, pd.DataFrame]
) -> Dict[str, Any]:
    try:
        strategy = BollStochStrategy()

        # Get trading signals and confidence
        signal, confidence, levels = strategy.analyze_signals(timeframe_data)

        # Get current market state from 1h timeframe
        df_1h = timeframe_data.get("1h")
        if df_1h is None or len(df_1h) < 1:
            raise ValueError("No 1h timeframe data available")

        current_price = df_1h["close"].iloc[-1]
        bb_upper = df_1h["bb_upper"].iloc[-1]
        bb_lower = df_1h["bb_lower"].iloc[-1]

        # Determine market state
        if current_price > bb_upper:
            market_state = "overbought"
        elif current_price < bb_lower:
            market_state = "oversold"
        else:
            market_state = "neutral"

        return {
            "signal": signal,
            "confidence": confidence,
            "market_state": market_state,
            "stop_loss": levels["stop_loss"],
            "take_profit": levels["take_profit"],
            "current_price": current_price,
        }
    except Exception as e:
        logging.error(f"Error checking market conditions: {e}")
        raise


def analyze_market_depth(exchange, symbol: str, side: str) -> Dict[str, float]:
    try:
        orderbook = exchange.fetch_order_book(symbol)

        if side == "buy":
            relevant_side = orderbook["asks"][:5]  # Top 5 ask prices
        else:
            relevant_side = orderbook["bids"][:5]  # Top 5 bid prices

        total_volume = sum(order[1] for order in relevant_side)
        weighted_price = (
            sum(order[0] * order[1] for order in relevant_side) / total_volume
        )

        return {
            "weighted_price": weighted_price,
            "total_volume": total_volume,
            "spread": orderbook["asks"][0][0] - orderbook["bids"][0][0],
        }
    except Exception as e:
        logging.error(f"Error analyzing market depth: {e}")
        raise


def check_trend_strength(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        # Calculate ADX for trend strength
        tr = df["high"] - df["low"]
        tr = tr.rolling(window=14).mean()

        # Calculate directional movement
        plus_dm = df["high"].diff()
        minus_dm = df["low"].diff()

        plus_dm = plus_dm.where(plus_dm > 0, 0)
        minus_dm = minus_dm.where(minus_dm < 0, 0).abs()

        # Smooth the directional movement
        plus_di = (plus_dm.rolling(window=14).mean() / tr) * 100
        minus_di = (minus_dm.rolling(window=14).mean() / tr) * 100

        # Calculate ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        adx = dx.rolling(window=14).mean()

        return {
            "trend_strength": adx.iloc[-1],
            "trend_direction": (
                "bullish"
                if plus_di.iloc[-1] > minus_di.iloc[-1]
                else "bearish"
            ),
            "adx": adx.iloc[-1],
            "plus_di": plus_di.iloc[-1],
            "minus_di": minus_di.iloc[-1],
        }
    except Exception as e:
        logging.error(f"Error checking trend strength: {e}")
        raise
