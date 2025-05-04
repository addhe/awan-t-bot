from typing import Dict, Any, Tuple
from dataclasses import dataclass
from typing import Optional


@dataclass
class TradingConfig:
    symbol: str
    leverage: int
    timeframe: str
    risk_percentage: float
    max_position_size: float
    min_balance: float
    max_daily_trades: int
    max_daily_loss_percent: float
    max_drawdown_percent: float
    partial_tp_1: float
    partial_tp_2: float
    tp1_target: float
    tp2_target: float
    trailing_distance_pct: float
    initial_profit_for_trailing_stop: float
    fee_rate: float

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "TradingConfig":
        return cls(
            symbol=config["symbol"],
            leverage=config["leverage"],
            timeframe=config["timeframe"],
            risk_percentage=config["risk_percentage"],
            max_position_size=config["max_position_size"],
            min_balance=config["min_balance"],
            max_daily_trades=config["max_daily_trades"],
            max_daily_loss_percent=config["max_daily_loss_percent"],
            max_drawdown_percent=config["max_drawdown_percent"],
            partial_tp_1=config["partial_tp_1"],
            partial_tp_2=config["partial_tp_2"],
            tp1_target=config["tp1_target"],
            tp2_target=config["tp2_target"],
            trailing_distance_pct=config["trailing_distance_pct"],
            initial_profit_for_trailing_stop=config[
                "initial_profit_for_trailing_stop"
            ],
            fee_rate=config["fee_rate"],
        )

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the trading configuration.

        Returns:
            Tuple[bool, Optional[str]]: A tuple containing a boolean indicating
                whether the configuration is valid and an optional error
                message.
        """
        try:
            if not (1 <= self.leverage <= 20):
                return False, "Leverage must be between 1 and 20"

            if not (0.1 <= self.risk_percentage <= 5):
                return False, "Risk percentage must be between 0.1% and 5%"

            if not (5 <= self.min_balance <= 1000000):
                return (
                    False,
                    "Minimum balance must be between 5 and 1,000,000 USDT",
                )

            if self.timeframe not in [
                "1m",
                "3m",
                "5m",
                "15m",
                "30m",
                "1h",
                "2h",
                "4h",
            ]:
                return False, "Invalid timeframe"

            if not (1 <= self.max_daily_trades <= 100):
                return False, "Max daily trades must be between 1 and 100"

            if not (1 <= self.max_daily_loss_percent <= 20):
                return (
                    False,
                    "Max daily loss percent must be between 1% and 20%",
                )

            if not (5 <= self.max_drawdown_percent <= 50):
                return False, (
                    "Max drawdown percent must be between 5% and 50%"
                )

            if not (0.1 <= self.partial_tp_1 + self.partial_tp_2 <= 1):
                return (
                    False,
                    "Sum of partial take profits must be between 0.1 and 1",
                )

            if not (0.001 <= self.trailing_distance_pct <= 0.05):
                return False, "Trailing distance must be between 0.1% and 5%"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"


def validate_exchange_config(exchange: Any) -> Tuple[bool, Optional[str]]:
    """Validate exchange configuration and connectivity."""
    try:
        # Test API connectivity
        exchange.fetch_balance()

        # Verify market exists
        markets = exchange.load_markets()
        if exchange.symbol not in markets:
            return False, f"Market {exchange.symbol} not found"

        # Check trading enabled
        market = markets[exchange.symbol]
        if not market["active"]:
            return False, f"Market {exchange.symbol} is not active"

        return True, None

    except Exception as e:
        return False, f"Exchange configuration error: {str(e)}"
