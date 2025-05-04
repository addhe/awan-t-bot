"""
Spot market trading strategy using Bollinger Bands, EMA, and Stochastic RSI
"""

import pandas as pd
from typing import Dict, Tuple, Any
from ta.volatility import BollingerBands
from ta.momentum import StochRSIIndicator
from ta.trend import EMAIndicator
import logging


class SpotStrategy:
    def __init__(
        self,
        boll_window: int = 20,
        boll_std: float = 2.0,
        ema_window: int = 20,
        stoch_window: int = 14,
        stoch_smooth_k: int = 3,
        stoch_smooth_d: int = 3,
        min_profit: float = 0.02,    # 2% minimum profit
        stop_loss: float = 0.015,    # 1.5% stop loss
        max_allocation_pct: float = 0.3,  # 30% maximum allocation
    ):
        self.max_allocation_pct = max_allocation_pct
        self.boll_window = boll_window
        self.boll_std = boll_std
        self.ema_window = ema_window
        self.stoch_window = stoch_window
        self.stoch_smooth_k = stoch_smooth_k
        self.stoch_smooth_d = stoch_smooth_d
        self.min_profit = min_profit
        self.stop_loss = stop_loss

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators with fallback for missing/NaN columns.
        """
        try:
            # Bollinger Bands
            bb = BollingerBands(
                close=df["close"],
                window=self.boll_window,
                window_dev=self.boll_std
            )
            df["bb_upper"] = bb.bollinger_hband()
            df["bb_middle"] = bb.bollinger_mavg()
            df["bb_lower"] = bb.bollinger_lband()

            # EMA
            ema = EMAIndicator(close=df["close"], window=self.ema_window)
            df["ema"] = ema.ema_indicator()

            # Stochastic RSI
            stoch = StochRSIIndicator(
                close=df["close"],
                window=self.stoch_window,
                smooth1=self.stoch_smooth_k,
                smooth2=self.stoch_smooth_d,
            )
            df["stoch_k"] = stoch.stochrsi_k()
            df["stoch_d"] = stoch.stochrsi_d()

            # Fallback: pastikan semua kolom indikator utama ada dan isi NaN
            # dengan harga close
            required_cols = [
                "bb_upper",
                "bb_middle",
                "bb_lower",
                "ema",
                "stoch_k",
                "stoch_d",
            ]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = df["close"]
                else:
                    df[col] = df[col].fillna(df["close"])

            return df

        except Exception as e:
            logging.error(f"Error calculating indicators: {e}")
            # Fallback: jika error,
            # pastikan semua kolom minimal diisi harga close
            required_cols = [
                "bb_upper",
                "bb_lower",
                "ema",
                "stoch_k",
                "stoch_d",
            ]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = df["close"]
                else:
                    df[col] = df[col].fillna(df["close"])
            return df

    def should_buy(
        self, df: pd.DataFrame
    ) -> Tuple[bool, float, Dict[str, float]]:
        """
        Check if we should buy based on our strategy. Safe with fallback for
        missing/NaN columns.
        Returns:
            (should_buy, confidence, levels)
        """
        try:
            if len(df) < 2:
                return False, 0, {}

            # Kolom indikator utama
            required_cols = [
                "bb_lower",
                "bb_middle",
                "ema",
                "stoch_k",
                "stoch_d",
            ]
            for col in required_cols:
                if col not in df.columns or pd.isna(df[col].iloc[-1]):
                    logging.warning(
                        f"{col} not found or NaN in should_buy, "
                        f"fallback to close value"
                    )
                    df[col] = df["close"]
            current_price = df["close"].iloc[-1]
            bb_lower = df["bb_lower"].iloc[-1]
            # # bb_middle = df["bb_middle"].iloc[-1]  # Unused variable (F841)  # noqa: E501
            ema = df["ema"].iloc[-1]
            stoch_k = df["stoch_k"].iloc[-1]
            stoch_d = df["stoch_d"].iloc[-1]

            # Buy conditions
            conditions = [
                current_price < bb_lower,  # Price below lower BB
                # current_price < bb_middle,  # Price below BB middle
                current_price > ema,  # Price above EMA
                stoch_k < 20 and stoch_k < stoch_d,  # Stoch oversold cross
            ]

            confidence = sum(conditions) / len(conditions)

            if confidence >= 0.75:  # At least 3 out of 4 conditions
                # Calculate take profit and stop loss
                take_profit = current_price * (1 + self.min_profit)
                stop_loss = current_price * (1 - self.stop_loss)

                return True, confidence, {
                    "entry": current_price,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss
                }

            return False, confidence, {}

        except Exception as e:
            logging.error(f"Error in should_buy: {e}")
            return False, 0, {}

    def should_sell(
        self, df: pd.DataFrame, buy_price: float = None
    ) -> Tuple[bool, float]:
        """
        Check if we should sell based on our strategy. Safe with fallback for
        missing/NaN columns.
        Returns:
            (should_sell, confidence)
        """
        try:
            if len(df) < 2:
                return False, 0

            # Kolom indikator utama
            required_cols = [
                "bb_upper",
                "bb_middle",
                "ema",
                "stoch_k",
                "stoch_d",
            ]
            for col in required_cols:
                if col not in df.columns or pd.isna(df[col].iloc[-1]):
                    logging.warning(
                        f"{col} not found or NaN in should_sell, "
                        f"fallback to close value"
                    )
                    df[col] = df["close"]
            current_price = df["close"].iloc[-1]
            bb_upper = df["bb_upper"].iloc[-1]
            # # bb_middle = df["bb_middle"].iloc[-1]  # Unused variable (F841)  # noqa: E501
            ema = df["ema"].iloc[-1]
            stoch_k = df["stoch_k"].iloc[-1]
            stoch_d = df["stoch_d"].iloc[-1]

            # If we have a buy price, check stop loss and take profit
            if buy_price:
                profit_pct = (current_price - buy_price) / buy_price
                if profit_pct <= -self.stop_loss:
                    return True, 1.0

                # Take profit hit
                if profit_pct >= self.min_profit:
                    return True, 1.0

            # Regular sell conditions
            conditions = [
                current_price > bb_upper,  # Price above upper BB
                current_price < ema,  # Price below EMA
                stoch_k > 80,  # Overbought
                stoch_k < stoch_d,  # Stoch crossunder
            ]

            confidence = sum(conditions) / len(conditions)

            return confidence >= 0.75, confidence

        except Exception as e:
            logging.error(f"Error in should_sell: {e}")
            return False, 0

    def calculate_position_size(
        self, balance: float, current_price: float, symbol: str
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate the position size based on available balance
        with smart allocation"""
        try:
            # Maximum allocation per trade based on total balance
            if balance < 100:  # Less than 100 USDT
                max_allocation = 0.3  # 30% max per trade
                max_positions = 1
                min_profit = 0.03  # 3% min profit
                stop_loss = 0.02  # 2% stop loss
            elif balance < 500:  # 100-500 USDT
                max_allocation = 0.25  # 25% max per trade
                max_positions = 2
                min_profit = 0.025  # 2.5% min profit
                stop_loss = 0.018  # 1.8% stop loss
            elif balance < 1000:  # 500-1000 USDT
                max_allocation = 0.2  # 20% max per trade
                max_positions = 2
                min_profit = 0.02  # 2% min profit
                stop_loss = 0.015  # 1.5% stop loss
            else:  # 1000+ USDT
                max_allocation = 0.15  # 15% max per trade
                max_positions = 3
                min_profit = 0.018  # 1.8% min profit
                stop_loss = 0.012  # 1.2% stop loss

            # Never exceed configured maximum allocation
            max_allocation = min(max_allocation, self.max_allocation_pct)

            # Calculate maximum USDT amount for this trade
            max_usdt = balance * max_allocation

            # More conservative fee buffer (0.3% total for potential slippage)
            usable_usdt = max_usdt * 0.997

            # Minimum trade size in USDT
            if usable_usdt < 15:  # Minimum 15 USDT per trade
                return 0.0, {
                    'max_positions': max_positions,
                    'usdt_value': 0,
                    'allocation_percent': 0,
                    'min_profit': 0,
                    'stop_loss': 0
                }

            # Calculate quantity
            quantity = usable_usdt / current_price

            # Round to appropriate decimals based on symbol
            if 'BTC' in symbol:
                quantity = round(quantity, 5)  # 0.00001 BTC precision
            elif 'ETH' in symbol:
                quantity = round(quantity, 4)  # 0.0001 ETH precision
            else:
                quantity = round(quantity, 2)  # 0.01 precision for others

            # Log the position size
            logging.info(
                (
                    f"[SPOT] {symbol} | Buy | Price: {current_price:.2f} | "
                    f"Qty: {quantity:.4f}"
                )
            )

            return quantity, {
                'max_positions': max_positions,
                'usdt_value': usable_usdt,
                'allocation_percent': max_allocation * 100,
                'min_profit': min_profit * 100,
                'stop_loss': stop_loss * 100
            }

        except Exception as e:
            logging.error(f"Error calculating position size: {e}")
            return 0.0, {}
