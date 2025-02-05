import logging
from typing import Dict, Any, Optional
import ccxt
import pandas as pd
from datetime import datetime

def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str,
                limit: int = 50, timeframe: str = '1m') -> pd.DataFrame:
    try:
        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        return df
    except Exception as e:
        logging.error(f"Error fetching OHLCV data: {e}")
        raise

def calculate_min_order_size(exchange: ccxt.Exchange, symbol: str,
                           market_price: float) -> float:
    try:
        market = exchange.market(symbol)

        # Get minimum amount from market limits
        min_amount = market['limits']['amount']['min']

        # Calculate minimum order size in quote currency
        min_order_size = min_amount * market_price

        # Apply a small buffer to ensure we're above minimum
        return min_order_size * 1.01
    except Exception as e:
        logging.error(f"Error calculating minimum order size: {e}")
        raise

def check_existing_position(exchange: ccxt.Exchange, side: str) -> Dict[str, Any]:
    try:
        positions = exchange.fetch_positions()

        for position in positions:
            if position['symbol'] == exchange.symbol:
                position_side = 'buy' if float(position['contracts']) > 0 else 'sell'

                if position_side == side:
                    return {
                        'exists': True,
                        'size': abs(float(position['contracts'])),
                        'entry_price': float(position['entryPrice']),
                        'unrealized_pnl': float(position['unrealizedPnl'])
                    }

        return {
            'exists': False,
            'size': 0,
            'entry_price': 0,
            'unrealized_pnl': 0
        }
    except Exception as e:
        logging.error(f"Error checking existing position: {e}")
        raise

def update_market_data(df: pd.DataFrame) -> Dict[str, Any]:
    try:
        current_price = df['close'].iloc[-1]
        current_volume = df['volume'].iloc[-1]

        # Calculate price change
        price_change = (current_price - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100

        # Calculate volume change
        volume_change = (current_volume - df['volume'].iloc[-2]) / df['volume'].iloc[-2] * 100

        return {
            'current_price': current_price,
            'current_volume': current_volume,
            'price_change_percent': price_change,
            'volume_change_percent': volume_change,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error updating market data: {e}")
        raise

def validate_config() -> bool:
    """
    Validate the configuration settings
    """
    from config.config import CONFIG

    required_fields = [
        'max_daily_trades',
        'max_daily_loss_percent',
        'max_drawdown_percent',
        'leverage',
        'symbol',
        'timeframe'
    ]

    try:
        # Check for required fields
        for field in required_fields:
            if field not in CONFIG:
                logging.error(f"Missing required config field: {field}")
                return False

        # Validate specific fields
        if CONFIG['max_daily_trades'] < 1:
            logging.error("max_daily_trades must be at least 1")
            return False

        if not (0 < CONFIG['max_daily_loss_percent'] <= 100):
            logging.error("max_daily_loss_percent must be between 0 and 100")
            return False

        if not (0 < CONFIG['max_drawdown_percent'] <= 100):
            logging.error("max_drawdown_percent must be between 0 and 100")
            return False

        if not (1 <= CONFIG['leverage'] <= 125):
            logging.error("leverage must be between 1 and 125")
            return False

        return True

    except Exception as e:
        logging.error(f"Error validating config: {e}")
        return False
