import pandas as pd
import numpy as np
import logging
from typing import Dict, Any

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    try:
        # Calculate various technical indicators
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['rsi'] = calculate_rsi(df['close'])
        df['volatility'] = df['close'].rolling(window=20).std()
        df['atr'] = calculate_atr(df)
        df['macd'], df['macd_signal'] = calculate_macd(df['close'])

        return df
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
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def check_market_conditions(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        current_idx = len(df) - 1

        # Calculate trend direction
        trend_direction = 'up' if df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1] else 'down'

        # Calculate volatility state
        volatility = df['volatility'].iloc[-1]
        volatility_state = 'high' if volatility > df['volatility'].mean() * 1.5 else 'normal'

        # Check momentum using RSI
        rsi = df['rsi'].iloc[-1]
        momentum = 'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'

        # MACD signal
        macd_signal = 'buy' if df['macd'].iloc[-1] > df['macd_signal'].iloc[-1] else 'sell'

        return {
            'trend': trend_direction,
            'volatility': volatility_state,
            'momentum': momentum,
            'macd_signal': macd_signal,
            'rsi': rsi
        }
    except Exception as e:
        logging.error(f"Error checking market conditions: {e}")
        raise

def analyze_market_depth(exchange, symbol: str, side: str) -> Dict[str, float]:
    try:
        orderbook = exchange.fetch_order_book(symbol)

        if side == 'buy':
            relevant_side = orderbook['asks'][:5]  # Top 5 ask prices
        else:
            relevant_side = orderbook['bids'][:5]  # Top 5 bid prices

        total_volume = sum(order[1] for order in relevant_side)
        weighted_price = sum(order[0] * order[1] for order in relevant_side) / total_volume

        return {
            'weighted_price': weighted_price,
            'total_volume': total_volume,
            'spread': orderbook['asks'][0][0] - orderbook['bids'][0][0]
        }
    except Exception as e:
        logging.error(f"Error analyzing market depth: {e}")
        raise

def check_trend_strength(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        # Calculate ADX for trend strength
        tr = df['high'] - df['low']
        tr = tr.rolling(window=14).mean()

        # Calculate directional movement
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()

        plus_dm = plus_dm.where(plus_dm > 0, 0)
        minus_dm = minus_dm.where(minus_dm < 0, 0).abs()

        # Smooth the directional movement
        plus_di = (plus_dm.rolling(window=14).mean() / tr) * 100
        minus_di = (minus_dm.rolling(window=14).mean() / tr) * 100

        # Calculate ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        adx = dx.rolling(window=14).mean()

        return {
            'trend_strength': adx.iloc[-1],
            'trend_direction': 'bullish' if plus_di.iloc[-1] > minus_di.iloc[-1] else 'bearish',
            'adx': adx.iloc[-1],
            'plus_di': plus_di.iloc[-1],
            'minus_di': minus_di.iloc[-1]
        }
    except Exception as e:
        logging.error(f"Error checking trend strength: {e}")
        raise
