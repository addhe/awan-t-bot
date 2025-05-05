import pandas as pd
from typing import Dict, List, Tuple, Any
from ta.volatility import BollingerBands
from ta.momentum import StochRSIIndicator
from ta.trend import EMAIndicator

from src.utils.error_handlers import handle_strategy_errors
from src.utils.structured_logger import get_logger

logger = get_logger(__name__)


class BollStochStrategy:
    def __init__(
        self,
        boll_length: int = 20,
        boll_std: float = 2.0,
        ema_length: int = 20,
        stoch_length: int = 14,
        stoch_smooth_k: int = 3,
        stoch_smooth_d: int = 3,
        stoch_oversold: int = 20,
        stoch_overbought: int = 80,
    ):
        # Map config names to internal variable names
        self.boll_window = boll_length
        self.boll_std = boll_std
        self.ema_window = ema_length
        self.stoch_window = stoch_length
        self.stoch_smooth_k = stoch_smooth_k
        self.stoch_smooth_d = stoch_smooth_d
        self.stoch_oversold = stoch_oversold
        self.stoch_overbought = stoch_overbought

    @handle_strategy_errors(notify=True)
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators for the strategy."""
        if df.empty:
            logger.warning(
                "Empty DataFrame provided for indicator calculation"
            )
            return df

        # Check if we have enough data for calculations
        min_required_candles = max(self.boll_window, self.ema_window, self.stoch_window) + 10
        if len(df) < min_required_candles:
            logger.warning(
                f"Not enough data for reliable indicators. Have {len(df)} candles, need at least {min_required_candles}",
                candles=len(df),
                required=min_required_candles
            )
            # We'll still try to calculate, but results may be unreliable

        logger.debug(
            f"Calculating indicators on {len(df)} candles",
            candles=len(df),
            window=self.boll_window,
            std=self.boll_std,
        )

        # Make a copy to avoid SettingWithCopyWarning
        df = df.copy()

        # Ensure no NaN in price data
        if df['close'].isna().any():
            logger.warning("NaN values found in close prices, forward filling")
            df['close'] = df['close'].ffill().bfill()  # Forward then backward fill

        # Bollinger Bands
        bb = BollingerBands(
            close=df["close"],
            window=self.boll_window,
            window_dev=self.boll_std,
        )
        df["bb_upper"] = bb.bollinger_hband().ffill()
        df["bb_middle"] = bb.bollinger_mavg().ffill()
        df["bb_lower"] = bb.bollinger_lband().ffill()

        # EMA
        ema = EMAIndicator(close=df["close"], window=self.ema_window)
        df["ema"] = ema.ema_indicator().ffill()

        # Stochastic RSI
        stoch = StochRSIIndicator(
            close=df["close"],
            window=self.stoch_window,
            smooth1=self.stoch_smooth_k,
            smooth2=self.stoch_smooth_d,
        )
        df["stoch_k"] = stoch.stochrsi_k().ffill()
        df["stoch_d"] = stoch.stochrsi_d().ffill()

        # Handle any remaining NaN values
        indicator_columns = [
            "bb_upper", "bb_middle", "bb_lower", "ema", "stoch_k", "stoch_d"
        ]

        # First check how many NaN values we have
        nan_counts = {col: df[col].isna().sum() for col in indicator_columns}
        total_nan = sum(nan_counts.values())

        if total_nan > 0:
            logger.warning(
                f"Total {total_nan} NaN values found in indicators",
                nan_counts=nan_counts,
                row_count=len(df),
            )

            # Fill NaN values with appropriate defaults
            for col in indicator_columns:
                if df[col].isna().any():
                    if col in ["bb_upper", "bb_middle", "bb_lower", "ema"]:
                        # For price-based indicators, use close price
                        df[col] = df[col].fillna(df["close"])
                    elif col in ["stoch_k", "stoch_d"]:
                        # For oscillators, use middle value (50)
                        df[col] = df[col].fillna(50)

        # Verify no NaN values remain
        remaining_nan = {col: df[col].isna().sum() for col in indicator_columns}
        if sum(remaining_nan.values()) > 0:
            logger.error(
                "Failed to remove all NaN values from indicators",
                remaining_nan=remaining_nan
            )
            # Last resort: drop NaN rows, but this is not ideal
            df = df.dropna(subset=indicator_columns)
            logger.warning(f"Dropped rows with NaN values, {len(df)} rows remaining")

        return df

    @handle_strategy_errors(notify=False)
    def analyze_signals(
        self, timeframe_data: Dict[str, pd.DataFrame]
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Analyze signals across multiple timeframes and return trading decision.
        Returns: (signal, confidence, levels)
        """
        signals = []
        confidence = 0.0
        available_timeframes = list(timeframe_data.keys())

        if not available_timeframes:
            logger.warning("No timeframe data available for signal analysis")
            return "neutral", 0.0, {"stop_loss": 0.0, "take_profit": 0.0}

        logger.debug(
            f"Analyzing signals across {len(available_timeframes)} available timeframes",
            timeframes=available_timeframes,
        )

        # Track conditions for each timeframe for better debugging
        timeframe_conditions = {}

        for tf in available_timeframes:
            if tf not in timeframe_data:
                continue

            df = timeframe_data[tf]
            if len(df) < 2:  # Need at least 2 candles
                logger.warning(
                    f"Not enough candles for {tf} timeframe",
                    timeframe=tf,
                    candle_count=len(df),
                )
                continue

            # Get latest values
            current_price = df["close"].iloc[-1]
            bb_upper = df["bb_upper"].iloc[-1]
            bb_lower = df["bb_lower"].iloc[-1]
            bb_middle = df["bb_middle"].iloc[-1]  # Added for reference
            ema = df["ema"].iloc[-1]
            stoch_k = df["stoch_k"].iloc[-1]
            stoch_d = df["stoch_d"].iloc[-1]

            # Calculate distances and percentages for better context
            bb_upper_distance = ((bb_upper - current_price) / current_price) * 100
            bb_lower_distance = ((current_price - bb_lower) / current_price) * 100
            ema_distance = ((current_price - ema) / current_price) * 100
            stoch_diff = stoch_k - stoch_d

            # Store conditions for this timeframe
            timeframe_conditions[tf] = {
                "price": current_price,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "ema": ema,
                "stoch_k": stoch_k,
                "stoch_d": stoch_d,
                "bb_upper_distance": f"{bb_upper_distance:.2f}%",
                "bb_lower_distance": f"{bb_lower_distance:.2f}%",
                "ema_distance": f"{ema_distance:.2f}%",
                "stoch_diff": stoch_diff,
                "is_oversold": stoch_k < self.stoch_oversold,
                "is_overbought": stoch_k > self.stoch_overbought,
                "stoch_crossover": stoch_k > stoch_d,
                "stoch_crossunder": stoch_k < stoch_d,
                "price_below_bb_lower": current_price < bb_lower,
                "price_above_bb_upper": current_price > bb_upper,
                "price_above_ema": current_price > ema,
                "price_below_ema": current_price < ema,
            }

            logger.debug(
                f"Indicators for {tf}",
                timeframe=tf,
                **timeframe_conditions[tf]
            )

            # Signal conditions
            # Long signal
            buy_conditions = {
                "price_below_bb_lower": current_price < bb_lower,
                "price_above_ema": current_price > ema,
                "stoch_oversold": stoch_k < self.stoch_oversold,
                "stoch_crossover": stoch_k > stoch_d
            }

            # Short signal
            sell_conditions = {
                "price_above_bb_upper": current_price > bb_upper,
                "price_below_ema": current_price < ema,
                "stoch_overbought": stoch_k > self.stoch_overbought,
                "stoch_crossunder": stoch_k < stoch_d
            }

            # Check if all buy conditions are met
            if all(buy_conditions.values()):
                tf_weight = self._get_timeframe_weight(tf)
                signals.append(("buy", tf_weight))
                logger.info(
                    f"Buy signal detected in {tf} timeframe",
                    timeframe=tf,
                    weight=tf_weight,
                    conditions=buy_conditions,
                    price=current_price,
                    bb_lower=bb_lower,
                    stoch_k=stoch_k,
                    stoch_d=stoch_d
                )
            # Check if all sell conditions are met
            elif all(sell_conditions.values()):
                tf_weight = self._get_timeframe_weight(tf)
                signals.append(("sell", tf_weight))
                logger.info(
                    f"Sell signal detected in {tf} timeframe",
                    timeframe=tf,
                    weight=tf_weight,
                    conditions=sell_conditions,
                    price=current_price,
                    bb_upper=bb_upper,
                    stoch_k=stoch_k,
                    stoch_d=stoch_d
                )
            else:
                # Log which conditions were not met for debugging
                if any(buy_conditions.values()):
                    failed_buy = {k: v for k, v in buy_conditions.items() if not v}
                    logger.debug(
                        f"Some buy conditions not met in {tf}",
                        timeframe=tf,
                        failed_conditions=failed_buy
                    )
                if any(sell_conditions.values()):
                    failed_sell = {k: v for k, v in sell_conditions.items() if not v}
                    logger.debug(
                        f"Some sell conditions not met in {tf}",
                        timeframe=tf,
                        failed_conditions=failed_sell
                    )

        # Log overall conditions summary
        logger.info(
            f"Signal analysis complete across {len(available_timeframes)} timeframes",
            signals_detected=len(signals),
            timeframe_conditions=timeframe_conditions
        )

        # Aggregate signals
        if not signals:
            logger.info("No trading signals detected in any timeframe")
            return "neutral", 0.0, {"stop_loss": 0.0, "take_profit": 0.0}

        # Calculate final signal and confidence
        buy_weight = sum(w for s, w in signals if s == "buy")
        sell_weight = sum(w for s, w in signals if s == "sell")

        if buy_weight > sell_weight:
            signal = "buy"
            confidence = buy_weight / (buy_weight + sell_weight)
            logger.info(
                f"Final signal: BUY with confidence {confidence:.2f}",
                buy_weight=buy_weight,
                sell_weight=sell_weight,
                confidence=confidence
            )
        elif sell_weight > buy_weight:
            signal = "sell"
            confidence = sell_weight / (buy_weight + sell_weight)
            logger.info(
                f"Final signal: SELL with confidence {confidence:.2f}",
                buy_weight=buy_weight,
                sell_weight=sell_weight,
                confidence=confidence
            )
        else:
            signal = "neutral"
            confidence = 0.0
            logger.info("Final signal: NEUTRAL (equal weights)")

        # Calculate stop loss and take profit levels
        levels = self._calculate_risk_levels(
            signal,
            # Use the shortest available timeframe's data for levels, or handle missing data
            timeframe_data.get(min(available_timeframes, key=lambda x: pd.Timedelta(x)), pd.DataFrame()),
            confidence,
        )

        return signal, confidence, levels

    def _get_timeframe_weight(self, timeframe: str) -> float:
        """Get weight for timeframe importance."""
        weights = {"15m": 0.1, "1h": 0.3, "4h": 0.3, "1d": 0.3}
        weight = weights.get(timeframe, 0.1)  # Default to 0.1 for unknown timeframes
        logger.debug(f"Timeframe weight for {timeframe}: {weight}")
        return weight

    def _calculate_risk_levels(
        self, signal: str, df: pd.DataFrame, confidence: float
    ) -> Dict[str, float]:
        """Calculate stop loss and take profit levels."""
        current_price = df["close"].iloc[-1]
        atr = (
            df["high"].iloc[-1] - df["low"].iloc[-1]
        )  # Simple volatility measure

        if signal == "buy":
            stop_loss = current_price - (atr * 2)
            take_profit = current_price + (atr * 3)
        elif signal == "sell":
            stop_loss = current_price + (atr * 2)
            take_profit = current_price - (atr * 3)
        else:
            stop_loss = take_profit = 0.0

        return {"stop_loss": stop_loss, "take_profit": take_profit}

    @handle_strategy_errors(notify=False)
    def should_sell(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """Check if we should sell based on current conditions

        Args:
            df (pd.DataFrame): DataFrame with price data and indicators

        Returns:
            Tuple[bool, float]: (should_sell, confidence)
        """
        if len(df) < 2:  # Need at least 2 candles
            logger.warning(
                "Not enough data to check sell conditions", rows=len(df)
            )
            return False, 0.0

        # Get latest values
        current_price = df["close"].iloc[-1]
        bb_upper = df["bb_upper"].iloc[-1]
        # bb_middle = df["bb_middle"].iloc[-1]
        ema = df["ema"].iloc[-1]
        stoch_k = df["stoch_k"].iloc[-1]
        stoch_d = df["stoch_d"].iloc[-1]

        logger.debug(
            "Checking sell conditions",
            price=current_price,
            bb_upper=bb_upper,
            ema=ema,
            stoch_k=stoch_k,
            stoch_d=stoch_d,
        )

        # Sell conditions
        if (
            current_price > bb_upper  # Price above upper BB
            and current_price < ema  # Price below EMA
            and stoch_k > 80  # Overbought
            and stoch_k < stoch_d
        ):  # Stoch crossunder

            # Calculate confidence based on how overbought we are
            confidence = min((stoch_k - 80) / 20, 1.0)  # Scale 80-100 to 0-1

            logger.info(
                "Sell signal detected",
                price=current_price,
                bb_upper=bb_upper,
                stoch_k=stoch_k,
                confidence=confidence,
            )

            return True, confidence

        return False, 0.0

    @handle_strategy_errors(notify=False)
    def calculate_pnl(self, entry_price: float, current_price: float) -> float:
        """Calculate profit/loss for a trade

        Args:
            entry_price (float): Entry price of the trade
            current_price (float): Current price of the asset

        Returns:
            float: Profit/loss percentage
        """
        if not current_price or not entry_price:
            logger.warning(
                "Invalid prices for PnL calculation",
                entry_price=entry_price,
                current_price=current_price,
            )
            return 0.0

        pnl = ((current_price - entry_price) / entry_price) * 100

        logger.debug(
            "PnL calculated",
            entry_price=entry_price,
            current_price=current_price,
            pnl=f"{pnl:.2f}%",
        )

        return pnl

    @handle_strategy_errors(notify=False)
    def calculate_position_size(
        self,
        balance: float,
        current_price: float,
        pair_config: Dict[str, Any],
        trading_config: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate position size based on balance and allocation settings

        Args:
            balance (float): Available balance in USDT
            current_price (float): Current price of the asset
            pair_config (Dict[str, Any]): Trading pair configuration
            trading_config (Dict[str, Any]): Trading configuration

        Returns:
            Tuple[float, Dict[str, Any]]: (quantity, allocation_info)
        """
        # Get allocation settings
        allocation_pct = trading_config.get(
            "allocation_per_trade", 0.2
        )  # Default 20%
        min_allocation = trading_config.get(
            "min_allocation_usdt", 10
        )  # Default 10 USDT
        max_allocation = trading_config.get(
            "max_allocation_usdt", 100
        )  # Default 100 USDT

        logger.debug(
            "Calculating position size",
            balance=balance,
            price=current_price,
            allocation_pct=allocation_pct,
            min_allocation=min_allocation,
            max_allocation=max_allocation,
        )

        # Calculate allocation amount
        allocation = balance * allocation_pct

        # Apply min/max limits
        original_allocation = allocation
        allocation = max(min(allocation, max_allocation), min_allocation)

        if allocation != original_allocation:
            logger.info(
                "Adjusted allocation based on limits",
                original=original_allocation,
                adjusted=allocation,
                reason="min_max_limits",
            )

        # Calculate quantity
        quantity = allocation / current_price

        # Round to required precision
        precision = pair_config["quantity_precision"]
        rounded_quantity = round(quantity, precision)

        if rounded_quantity != quantity:
            logger.debug(
                "Rounded quantity to required precision",
                original=quantity,
                rounded=rounded_quantity,
                precision=precision,
            )

        logger.info(
            "Position size calculated",
            symbol=pair_config["symbol"],
            quantity=rounded_quantity,
            allocation_usdt=allocation,
            allocation_pct=allocation_pct * 100,
        )

        # Return quantity and allocation info
        return rounded_quantity, {
            "allocation_pct": allocation_pct * 100,
            "allocation_usdt": allocation,
            "max_allocation": max_allocation,
        }
