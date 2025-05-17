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
        min_confidence: float = 0.6,
        **kwargs,  # Accept any additional parameters
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

    def _validate_price_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean price data"""
        # Create a copy to avoid modifying the original
        df = df.copy()

        # Check for NaN or infinite values in price columns
        price_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in price_cols:
            if col not in df.columns:
                continue

            # Replace inf/-inf with NaN first
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)

            # Count NaN values before filling
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.warning(
                    f"Found {nan_count} NaN values in {col} column",
                    column=col,
                    nan_count=nan_count
                )

                # For price columns, use forward fill then backward fill
                if col in ['open', 'high', 'low', 'close']:
                    df[col] = df[col].ffill().bfill()
                    # If still NaN, use previous close for OHLC
                    if df[col].isna().any():
                        if col == 'close':
                            df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
                        else:
                            df[col] = df[col].fillna(df['close'])
                # For volume, fill with 0
                elif col == 'volume':
                    df[col] = df[col].fillna(0)

        # Ensure all price columns are positive
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].clip(lower=1e-8)  # Small positive value to avoid division by zero

        return df

    @handle_strategy_errors(notify=True)
    def calculate_indicators(self, df: pd.DataFrame, symbol: str = "", timeframe: str = "") -> pd.DataFrame:
        """Calculate all technical indicators for the strategy.

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading pair symbol (for Redis caching)
            timeframe: Timeframe (for Redis caching)

        Returns:
            DataFrame with indicators added
        """
        if df.empty:
            logger.warning(
                "Empty DataFrame provided for indicator calculation"
            )
            return df

        # Validate and clean price data first
        try:
            df = self._validate_price_data(df)
        except Exception as e:
            logger.error(f"Error validating price data: {e}")
            return df

        # Try to get cached indicators if symbol and timeframe are provided
        if symbol and timeframe:
            try:
                from src.utils.redis_manager import redis_manager

                cached_indicators = redis_manager.get_indicators(symbol, timeframe)
                if cached_indicators is not None:
                    common_timestamps = df.index.intersection(cached_indicators.index)

                    if len(common_timestamps) > 0:
                        logger.info(
                            f"Using cached indicators from Redis",
                            symbol=symbol,
                            timeframe=timeframe,
                            cached_rows=len(common_timestamps),
                            total_rows=len(df)
                        )

                        # Merge only indicator columns that don't exist in df
                        indicator_cols = [col for col in cached_indicators.columns
                                        if col not in ['open', 'high', 'low', 'close', 'volume']]

                        for ts in common_timestamps:
                            for col in indicator_cols:
                                if ts in df.index and ts in cached_indicators.index:
                                    df.at[ts, col] = cached_indicators.at[ts, col]

                        # Verify all indicators were properly merged
                        missing_indicators = [col for col in indicator_cols
                                           if col not in df.columns or df[col].isna().all()]

                        if not missing_indicators:
                            return df

                        logger.debug(
                            f"Need to calculate {len(missing_indicators)} missing indicators",
                            missing_indicators=missing_indicators
                        )
            except Exception as e:
                logger.warning(f"Error getting cached indicators: {e}")

        # Check if we have enough data for calculations
        min_required_candles = max(self.boll_window, self.ema_window, self.stoch_window) + 20  # Increased buffer
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

        # Ensure we have enough valid data points
        valid_data_ratio = df['close'].count() / len(df)
        if valid_data_ratio < 0.8:  # Less than 80% valid data
            logger.warning(
                f"Low valid data ratio: {valid_data_ratio:.1%}",
                valid_ratio=valid_data_ratio
            )

        # Calculate indicators with error handling
        try:
            # Bollinger Bands with NaN handling
            bb = BollingerBands(
                close=df["close"],
                window=self.boll_window,
                window_dev=self.boll_std,
            )

            # Calculate bands with error handling
            df["bb_middle"] = bb.bollinger_mavg()
            df["bb_upper"] = bb.bollinger_hband()
            df["bb_lower"] = bb.bollinger_lband()

            # EMA with error handling
            try:
                ema = EMAIndicator(close=df["close"], window=self.ema_window)
                df["ema"] = ema.ema_indicator()
            except Exception as e:
                logger.error(f"Error calculating EMA: {e}")
                df["ema"] = df["close"].rolling(window=self.ema_window, min_periods=1).mean()

            # Stochastic RSI with error handling
            try:
                stoch = StochRSIIndicator(
                    close=df["close"],
                    window=self.stoch_window,
                    smooth1=self.stoch_smooth_k,
                    smooth2=self.stoch_smooth_d,
                )
                df["stoch_k"] = stoch.stochrsi_k()
                df["stoch_d"] = stoch.stochrsi_d()
            except Exception as e:
                logger.error(f"Error calculating Stochastic RSI: {e}")
                # Fallback to simple RSI if Stochastic fails
                from ta.momentum import RSIIndicator
                rsi = RSIIndicator(close=df["close"], window=self.stoch_window)
                df["stoch_k"] = df["stoch_d"] = rsi.rsi()
        except Exception as e:
            logger.critical(f"Critical error in indicator calculation: {e}")
            # If all else fails, use simple moving averages
            df["bb_middle"] = df["close"].rolling(window=self.boll_window, min_periods=1).mean()
            df["bb_upper"] = df["bb_middle"] + df["close"].rolling(window=self.boll_window, min_periods=1).std() * self.boll_std
            df["bb_lower"] = df["bb_middle"] - df["close"].rolling(window=self.boll_window, min_periods=1).std() * self.boll_std
            df["ema"] = df["close"].ewm(span=self.ema_window, min_periods=1).mean()

            # Simple RSI as fallback
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.stoch_window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.stoch_window).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            df["stoch_k"] = df["stoch_d"] = rsi

        # Define indicator columns for validation
        indicator_columns = ["bb_upper", "bb_middle", "bb_lower", "ema", "stoch_k", "stoch_d"]

        # Handle NaN values in each indicator column
        for col in indicator_columns:
            if col not in df.columns:
                # If column is missing, create it with close price as fallback
                df[col] = df["close"]
                logger.warning(f"Missing indicator column: {col}, using close price as fallback")
                continue

            # Replace infinite values
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)

            # Count NaN values before filling
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.debug(
                    f"Filling {nan_count} NaN values in {col}",
                    column=col,
                    nan_count=nan_count
                )

                # Special handling for different indicator types
                if col in ["bb_upper", "bb_lower"]:
                    # For Bollinger Bands, use a percentage of close price
                    multiplier = 1.02 if col == "bb_upper" else 0.98
                    df[col] = df[col].fillna(df["close"] * multiplier)
                elif col == "bb_middle":
                    # For middle band, use close price or SMA
                    df[col] = df[col].fillna(df["close"].rolling(window=self.boll_window, min_periods=1).mean())
                elif col == "ema":
                    # For EMA, use close price or SMA
                    df[col] = df[col].fillna(df["close"].ewm(span=self.ema_window, min_periods=1).mean())
                elif col in ["stoch_k", "stoch_d"]:
                    # For oscillators, use 50 as neutral value
                    df[col] = df[col].fillna(50)

        # Final validation - ensure no NaN values remain
        remaining_nan = {col: df[col].isna().sum() for col in indicator_columns}
        if any(remaining_nan.values()):
            logger.warning(
                f"Remaining NaN values after filling: {remaining_nan}",
                remaining_nan=remaining_nan
            )
            # Last resort: fill with close price or 50 for oscillators
            for col in indicator_columns:
                if df[col].isna().any():
                    if col in ["stoch_k", "stoch_d"]:
                        df[col] = df[col].fillna(50)
                    else:
                        df[col] = df[col].fillna(df["close"])

        # Ensure all indicators are within valid ranges
        df["stoch_k"] = df["stoch_k"].clip(0, 100)
        df["stoch_d"] = df["stoch_d"].clip(0, 100)

        # Ensure Bollinger Bands make logical sense
        mask = df["bb_upper"] <= df["bb_lower"]
        if mask.any():
            logger.warning(
                f"Found {mask.sum()} rows where upper band <= lower band, adjusting...",
                affected_rows=mask.sum()
            )
            df.loc[mask, "bb_upper"] = df.loc[mask, "bb_middle"] + (df.loc[mask, "bb_middle"] - df.loc[mask, "bb_lower"])

            # Final check
            final_nan = {col: df[col].isna().sum() for col in indicator_columns}
            if sum(final_nan.values()) > 0:
                logger.critical(
                    "CRITICAL: Still have NaN values after aggressive filling",
                    final_nan=final_nan
                )
                # As absolute last resort, drop rows, but log this as a critical issue
                df = df.dropna(subset=indicator_columns)
                logger.warning(f"Dropped rows with NaN values, {len(df)} rows remaining")

        # Save indicators to Redis if symbol and timeframe are provided
        if symbol and timeframe:
            try:
                # Import Redis manager here to avoid circular imports
                from src.utils.redis_manager import redis_manager

                # Save indicators to Redis
                redis_manager.save_indicators(symbol, timeframe, df)
                logger.debug(
                    f"Saved indicators to Redis",
                    symbol=symbol,
                    timeframe=timeframe,
                    rows=len(df)
                )
            except Exception as e:
                logger.warning(f"Error saving indicators to Redis: {e}")

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

            # Check if at least 3 of 4 buy conditions are met (more flexible approach)
            buy_conditions_met = sum(buy_conditions.values())
            sell_conditions_met = sum(sell_conditions.values())

            if buy_conditions_met >= 3:  # At least 3 of 4 conditions
                tf_weight = self._get_timeframe_weight(tf)
                # Adjust weight based on how many conditions are met
                adjusted_weight = tf_weight * (buy_conditions_met / 4)
                signals.append(("buy", adjusted_weight))
                logger.info(
                    f"Buy signal detected in {tf} timeframe with {buy_conditions_met}/4 conditions",
                    timeframe=tf,
                    weight=adjusted_weight,
                    original_weight=tf_weight,
                    conditions_met=buy_conditions_met,
                    conditions=buy_conditions,
                    price=current_price,
                    bb_lower=bb_lower,
                    stoch_k=stoch_k,
                    stoch_d=stoch_d
                )
            # Check if at least 3 of 4 sell conditions are met (more flexible approach)
            elif sell_conditions_met >= 3:  # At least 3 of 4 conditions
                tf_weight = self._get_timeframe_weight(tf)
                # Adjust weight based on how many conditions are met
                adjusted_weight = tf_weight * (sell_conditions_met / 4)
                signals.append(("sell", adjusted_weight))
                logger.info(
                    f"Sell signal detected in {tf} timeframe with {sell_conditions_met}/4 conditions",
                    timeframe=tf,
                    weight=adjusted_weight,
                    original_weight=tf_weight,
                    conditions_met=sell_conditions_met,
                    conditions=sell_conditions,
                    price=current_price,
                    bb_upper=bb_upper,
                    stoch_k=stoch_k,
                    stoch_d=stoch_d
                )
            else:
                # Log which conditions were not met for debugging
                if any(buy_conditions.values()):
                    met_buy = {k: v for k, v in buy_conditions.items() if v}
                    failed_buy = {k: v for k, v in buy_conditions.items() if not v}
                    logger.debug(
                        f"Insufficient buy conditions in {tf} ({sum(buy_conditions.values())}/4 met)",
                        timeframe=tf,
                        met_conditions=met_buy,
                        failed_conditions=failed_buy
                    )
                if any(sell_conditions.values()):
                    met_sell = {k: v for k, v in sell_conditions.items() if v}
                    failed_sell = {k: v for k, v in sell_conditions.items() if not v}
                    logger.debug(
                        f"Insufficient sell conditions in {tf} ({sum(sell_conditions.values())}/4 met)",
                        timeframe=tf,
                        met_conditions=met_sell,
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
