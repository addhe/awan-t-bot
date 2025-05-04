import logging
from typing import Dict, Any, Tuple


def calculate_position_size(
    balance: float,
    entry_price: float,
    stop_loss: float,
    exchange: Any,
    volatility: float,
) -> float:
    try:
        risk_per_trade = balance * 0.01  # 1% risk per trade
        price_difference = abs(entry_price - stop_loss)
        position_size = risk_per_trade / price_difference

        # Adjust for volatility
        if volatility > 0.02:  # High volatility
            position_size *= 0.8  # Reduce position size by 20%

        return position_size
    except Exception as e:
        logging.error(
            f"Error calculating position size: {e}"
        )
        raise


def validate_position_size(
    position_size: float,
    market_price: float,
    balance: float,
    min_order_size: float,
) -> Tuple[bool, str]:
    try:
        # Check if position size is too small
        if position_size < min_order_size:
            return (
                False,
                "Position size {} is below minimum order size {}".format(
                    position_size,
                    min_order_size
                )
            )

        # Check if position value exceeds available balance
        position_value = position_size * market_price
        if position_value > balance:
            return (
                False,
                "Position value {} exceeds available balance {}".format(
                    position_value,
                    balance
                )
            )

        # Check if position size is reasonable (not too large)
        if position_value > balance * 0.2:  # Max 20% of balance per trade
            return (
                False,
                (
                    f"Position value {position_value} exceeds 20% of balance"
                ),
            )

        return True, "Position size is valid"
    except Exception as e:
        logging.error(
            f"Error validating position size: {e}"
        )
        raise


def calculate_dynamic_stop_loss(
    df: Dict[str, Any], side: str, market_price: float
) -> float:
    try:
        atr = df["atr"].iloc[-1]

        if side == "buy":
            stop_loss = market_price - (
                atr * 2
            )  # 2 ATR below entry for long positions
        else:
            stop_loss = market_price + (
                atr * 2
            )  # 2 ATR above entry for short positions

        return stop_loss
    except Exception as e:
        logging.error(
            f"Error calculating dynamic stop loss: {e}"
        )
        raise


def manage_position_risk(
    position_size: float, market_price: float, balance: float
) -> Dict[str, Any]:
    try:
        position_value = position_size * market_price
        risk_percentage = (position_value / balance) * 100

        risk_assessment = {
            "position_value": position_value,
            "risk_percentage": risk_percentage,
            "is_high_risk": risk_percentage
            > 5,  # Consider high risk if >5% of balance
            "recommended_size": (
                position_size
                if risk_percentage <= 5
                else (balance * 0.05) / market_price
            ),
        }

        return risk_assessment
    except Exception as e:
        logging.error(
            f"Error managing position risk: {e}"
        )
        raise


def assess_risk_conditions(
    df: Dict[str, Any], balance: float, exchange: Any
) -> Dict[str, bool]:
    try:
        # Check various risk conditions
        volatility = df["volatility"].iloc[-1]
        avg_volatility = df["volatility"].mean()
        rsi = df["rsi"].iloc[-1]

        risk_conditions = {
            "high_volatility": volatility > avg_volatility * 1.5,
            "extreme_rsi": rsi > 75 or rsi < 25,
            "low_balance": balance < 100,  # Minimum balance threshold
            "market_unstable": check_market_stability(df),
        }

        return risk_conditions
    except Exception as e:
        logging.error(
            f"Error assessing risk conditions: {e}"
        )
        raise


def check_market_stability(df: Dict[str, Any]) -> bool:
    try:
        # Calculate price stability
        recent_prices = df["close"].tail(20)
        price_volatility = recent_prices.std() / recent_prices.mean()

        # Calculate volume stability
        recent_volumes = df["volume"].tail(20)
        volume_volatility = recent_volumes.std() / recent_volumes.mean()

        return price_volatility > 0.03 or volume_volatility > 0.5
    except Exception as e:
        logging.error(
            f"Error checking market stability: {e}"
        )
        raise


def limit_position_size(
    size: float, market_price: float, balance: float
) -> float:
    max_position_value = balance * 0.2  # Maximum 20% of balance
    return min(size, max_position_value / market_price)
