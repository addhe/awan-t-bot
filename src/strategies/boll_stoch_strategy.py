import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from ta.volatility import BollingerBands
from ta.momentum import StochasticRSI
from ta.trend import EMAIndicator

logger = logging.getLogger(__name__)

class BollStochStrategy:
    def __init__(
        self,
        boll_window: int = 20,
        boll_std: float = 2.0,
        ema_window: int = 20,
        stoch_window: int = 14,
        stoch_smooth_k: int = 3,
        stoch_smooth_d: int = 3,
        timeframes: List[str] = ["15m", "1h", "4h", "1d"]
    ):
        self.boll_window = boll_window
        self.boll_std = boll_std
        self.ema_window = ema_window
        self.stoch_window = stoch_window
        self.stoch_smooth_k = stoch_smooth_k
        self.stoch_smooth_d = stoch_smooth_d
        self.timeframes = timeframes

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators for the strategy."""
        try:
            # Bollinger Bands
            bb = BollingerBands(
                close=df["close"],
                window=self.boll_window,
                window_dev=self.boll_std
            )
            df["bb_upper"] = bb.bollinger_hband().fillna(method='ffill')
            df["bb_middle"] = bb.bollinger_mavg().fillna(method='ffill')
            df["bb_lower"] = bb.bollinger_lband().fillna(method='ffill')

            # EMA
            ema = EMAIndicator(close=df["close"], window=self.ema_window)
            df["ema"] = ema.ema_indicator().fillna(method='ffill')

            # Stochastic RSI
            stoch = StochasticRSI(
                close=df["close"],
                window=self.stoch_window,
                smooth1=self.stoch_smooth_k,
                smooth2=self.stoch_smooth_d
            )
            df["stoch_k"] = stoch.stochrsi_k().fillna(method='ffill')
            df["stoch_d"] = stoch.stochrsi_d().fillna(method='ffill')

            # Handle any remaining NaN values
            for col in ['bb_upper', 'bb_middle', 'bb_lower', 'ema', 'stoch_k', 'stoch_d']:
                if df[col].isna().any():
                    df[col] = df[col].fillna(df['close'])
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            # Set default values if calculation fails
            df["bb_upper"] = df["close"]
            df["bb_middle"] = df["close"]
            df["bb_lower"] = df["close"]
            df["ema"] = df["close"]
            df["stoch_k"] = 50
            df["stoch_d"] = 50

        return df

    def analyze_signals(
        self,
        timeframe_data: Dict[str, pd.DataFrame]
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Analyze signals across multiple timeframes and return trading decision.
        Returns: (signal, confidence, levels)
        """
        signals = []
        confidence = 0.0

        for tf in self.timeframes:
            if tf not in timeframe_data:
                continue

            df = timeframe_data[tf]
            if len(df) < 2:  # Need at least 2 candles
                continue

            # Get latest values
            current_price = df["close"].iloc[-1]
            bb_upper = df["bb_upper"].iloc[-1]
            bb_lower = df["bb_lower"].iloc[-1]
            bb_middle = df["bb_middle"].iloc[-1]
            ema = df["ema"].iloc[-1]
            stoch_k = df["stoch_k"].iloc[-1]
            stoch_d = df["stoch_d"].iloc[-1]

            # Signal conditions
            # Long signal
            if (current_price < bb_lower and  # Price below lower BB
                current_price > ema and       # Price above EMA
                stoch_k < 20 and             # Oversold
                stoch_k > stoch_d):          # Stoch crossover
                signals.append(("buy", self._get_timeframe_weight(tf)))

            # Short signal
            elif (current_price > bb_upper and  # Price above upper BB
                  current_price < ema and       # Price below EMA
                  stoch_k > 80 and             # Overbought
                  stoch_k < stoch_d):          # Stoch crossunder
                signals.append(("sell", self._get_timeframe_weight(tf)))

        # Aggregate signals
        if not signals:
            return "neutral", 0.0, {
                "stop_loss": 0.0,
                "take_profit": 0.0
            }

        # Calculate final signal and confidence
        buy_weight = sum(w for s, w in signals if s == "buy")
        sell_weight = sum(w for s, w in signals if s == "sell")

        if buy_weight > sell_weight:
            signal = "buy"
            confidence = buy_weight / (buy_weight + sell_weight)
        elif sell_weight > buy_weight:
            signal = "sell"
            confidence = sell_weight / (buy_weight + sell_weight)
        else:
            signal = "neutral"
            confidence = 0.0

        # Calculate stop loss and take profit levels
        levels = self._calculate_risk_levels(
            signal,
            timeframe_data["1h"],  # Use 1h timeframe for risk levels
            confidence
        )

        return signal, confidence, levels

    def _get_timeframe_weight(self, timeframe: str) -> float:
        """Get weight for timeframe importance."""
        weights = {
            "15m": 0.1,
            "1h": 0.3,
            "4h": 0.3,
            "1d": 0.3
        }
        return weights.get(timeframe, 0.0)

    def _calculate_risk_levels(
        self,
        signal: str,
        df: pd.DataFrame,
        confidence: float
    ) -> Dict[str, float]:
        """Calculate stop loss and take profit levels."""
        current_price = df["close"].iloc[-1]
        atr = df["high"].iloc[-1] - df["low"].iloc[-1]  # Simple volatility measure

        if signal == "buy":
            stop_loss = current_price - (atr * 2)
            take_profit = current_price + (atr * 3)
        elif signal == "sell":
            stop_loss = current_price + (atr * 2)
            take_profit = current_price - (atr * 3)
        else:
            stop_loss = take_profit = 0.0

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }

    def should_sell(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """Check if we should sell based on current conditions

        Args:
            df (pd.DataFrame): DataFrame with price data and indicators

        Returns:
            Tuple[bool, float]: (should_sell, confidence)
        """
        try:
            if len(df) < 2:  # Need at least 2 candles
                return False, 0.0

            # Get latest values
            current_price = df["close"].iloc[-1]
            bb_upper = df["bb_upper"].iloc[-1]
            bb_middle = df["bb_middle"].iloc[-1]
            ema = df["ema"].iloc[-1]
            stoch_k = df["stoch_k"].iloc[-1]
            stoch_d = df["stoch_d"].iloc[-1]

            # Sell conditions
            if (current_price > bb_upper and    # Price above upper BB
                current_price < ema and         # Price below EMA
                stoch_k > 80 and               # Overbought
                stoch_k < stoch_d):            # Stoch crossunder

                # Calculate confidence based on how overbought we are
                confidence = min((stoch_k - 80) / 20, 1.0)  # Scale 80-100 to 0-1
                return True, confidence

            return False, 0.0

        except Exception as e:
            logger.error(f"Error in should_sell: {e}")
            return False, 0.0
            
    def calculate_position_size(
        self,
        balance: float,
        current_price: float,
        pair_config: Dict[str, Any],
        trading_config: Dict[str, Any]
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
        try:
            # Get allocation settings
            allocation_pct = trading_config.get('allocation_per_trade', 0.2)  # Default 20%
            min_allocation = trading_config.get('min_allocation_usdt', 10)  # Default 10 USDT
            max_allocation = trading_config.get('max_allocation_usdt', 100)  # Default 100 USDT
            
            # Calculate allocation amount
            allocation = balance * allocation_pct
            
            # Apply min/max limits
            allocation = max(min(allocation, max_allocation), min_allocation)
            
            # Calculate quantity
            quantity = allocation / current_price
            
            # Round to required precision
            quantity = round(quantity, pair_config['quantity_precision'])
            
            # Return quantity and allocation info
            return quantity, {
                'allocation_pct': allocation_pct * 100,
                'allocation_usdt': allocation,
                'max_allocation': max_allocation
            }
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0, {
                'allocation_pct': 0,
                'allocation_usdt': 0,
                'max_allocation': 0
            }
