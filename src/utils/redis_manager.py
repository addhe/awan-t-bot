"""
Redis manager for caching OHLCV data and indicators
"""

import os
import json
import pandas as pd
import redis
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.utils.structured_logger import get_logger

logger = get_logger(__name__)

class RedisManager:
    """Redis manager for caching OHLCV data and indicators"""

    def __init__(self, config=None):
        """Initialize Redis connection
        
        Args:
            config (dict, optional): Redis configuration dictionary. If None, use environment variables.
        """
        # Get Redis configuration from config or environment variables
        if config is None:
            # Fallback to environment variables
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_password = os.environ.get("REDIS_PASSWORD", "StrongRedisPassword")
            decode_responses = True
            socket_timeout = 5
            socket_connect_timeout = 5
            retry_on_timeout = True
            health_check_interval = 30
        else:
            # Use provided config
            redis_host = config.get("host", "localhost")
            redis_port = config.get("port", 6379)
            redis_password = config.get("password", "StrongRedisPassword")
            decode_responses = config.get("decode_responses", True)
            socket_timeout = config.get("socket_timeout", 5)
            socket_connect_timeout = config.get("socket_connect_timeout", 5)
            retry_on_timeout = config.get("retry_on_timeout", True)
            health_check_interval = config.get("health_check_interval", 30)
        
        # Initialize Redis client
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            retry_on_timeout=retry_on_timeout,
            health_check_interval=health_check_interval
        )
        
        # Test connection
        try:
            self.redis.ping()
            logger.info("Connected to Redis server", host=redis_host, port=redis_port)
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}", host=redis_host, port=redis_port)
            # Continue without Redis - fallback to direct API calls
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        try:
            return self.redis.ping()
        except:
            return False
    
    # OHLCV Data Methods
    def save_ohlcv(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Save OHLCV data to Redis
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '15m')
            df: DataFrame with OHLCV data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected() or df.empty:
            return False
        
        try:
            # Convert DataFrame to JSON
            json_data = df.reset_index().to_json(orient="records", date_format="iso")
            
            # Set key and save data
            key = f"ohlcv:{symbol}:{timeframe}"
            self.redis.set(key, json_data)
            
            # Set expiration (keep data for 7 days)
            self.redis.expire(key, 60 * 60 * 24 * 7)
            
            # Save last update timestamp
            update_key = f"ohlcv:{symbol}:{timeframe}:last_update"
            self.redis.set(update_key, datetime.now().isoformat())
            
            logger.debug(
                f"Saved OHLCV data to Redis",
                symbol=symbol,
                timeframe=timeframe,
                candles=len(df)
            )
            return True
        except Exception as e:
            logger.error(f"Error saving OHLCV data to Redis: {e}", symbol=symbol, timeframe=timeframe)
            return False
    
    def get_ohlcv(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get OHLCV data from Redis
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '15m')
            
        Returns:
            DataFrame with OHLCV data or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            # Get key
            key = f"ohlcv:{symbol}:{timeframe}"
            json_data = self.redis.get(key)
            
            if not json_data:
                return None
            
            # Convert JSON to DataFrame
            from io import StringIO
            df = pd.read_json(StringIO(json_data))
            
            # Set timestamp as index
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
            
            logger.debug(
                f"Retrieved OHLCV data from Redis",
                symbol=symbol,
                timeframe=timeframe,
                candles=len(df)
            )
            return df
        except Exception as e:
            logger.error(f"Error getting OHLCV data from Redis: {e}", symbol=symbol, timeframe=timeframe)
            return None
    
    # Indicator Methods
    def save_indicators(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """Save indicators to Redis
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '15m')
            df: DataFrame with indicators
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected() or df.empty:
            return False
        
        try:
            # Get indicator columns (all except OHLCV)
            indicator_columns = [col for col in df.columns if col not in ["open", "high", "low", "close", "volume"]]
            
            if not indicator_columns:
                return False
            
            # Create a DataFrame with only indicators
            indicators_df = df[indicator_columns].copy()
            
            # Convert DataFrame to JSON
            json_data = indicators_df.reset_index().to_json(orient="records", date_format="iso")
            
            # Set key and save data
            key = f"indicators:{symbol}:{timeframe}"
            self.redis.set(key, json_data)
            
            # Set expiration (keep data for 7 days)
            self.redis.expire(key, 60 * 60 * 24 * 7)
            
            # Save last update timestamp
            update_key = f"indicators:{symbol}:{timeframe}:last_update"
            self.redis.set(update_key, datetime.now().isoformat())
            
            logger.debug(
                f"Saved indicators to Redis",
                symbol=symbol,
                timeframe=timeframe,
                indicators=indicator_columns
            )
            return True
        except Exception as e:
            logger.error(f"Error saving indicators to Redis: {e}", symbol=symbol, timeframe=timeframe)
            return False
    
    def get_indicators(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Get indicators from Redis
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '15m')
            
        Returns:
            DataFrame with indicators or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            # Get key
            key = f"indicators:{symbol}:{timeframe}"
            json_data = self.redis.get(key)
            
            if not json_data:
                return None
            
            # Convert JSON to DataFrame
            from io import StringIO
            df = pd.read_json(StringIO(json_data))
            
            # Set timestamp as index
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
            
            logger.debug(
                f"Retrieved indicators from Redis",
                symbol=symbol,
                timeframe=timeframe,
                indicators=list(df.columns)
            )
            return df
        except Exception as e:
            logger.error(f"Error getting indicators from Redis: {e}", symbol=symbol, timeframe=timeframe)
            return None
    
    # Signal Methods
    def save_signal(self, symbol: str, signal: str, confidence: float, timeframes: List[str]) -> bool:
        """Save trading signal to Redis
        
        Args:
            symbol: Trading pair symbol
            signal: Signal type (buy, sell, neutral)
            confidence: Signal confidence (0-1)
            timeframes: List of timeframes that generated the signal
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            # Create signal data
            signal_data = {
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "timeframes": timeframes,
                "timestamp": datetime.now().isoformat()
            }
            
            # Set key and save data
            key = f"signal:{symbol}"
            self.redis.set(key, json.dumps(signal_data))
            
            # Set expiration (keep signal for 1 day)
            self.redis.expire(key, 60 * 60 * 24)
            
            # Add to signal history
            history_key = f"signal_history:{symbol}"
            self.redis.lpush(history_key, json.dumps(signal_data))
            self.redis.ltrim(history_key, 0, 99)  # Keep last 100 signals
            
            logger.debug(
                f"Saved signal to Redis",
                symbol=symbol,
                signal=signal,
                confidence=confidence
            )
            return True
        except Exception as e:
            logger.error(f"Error saving signal to Redis: {e}", symbol=symbol)
            return False
    
    def get_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest trading signal from Redis
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Signal data or None if not found
        """
        if not self.is_connected():
            return None
        
        try:
            # Get key
            key = f"signal:{symbol}"
            json_data = self.redis.get(key)
            
            if not json_data:
                return None
            
            # Convert JSON to dict
            signal_data = json.loads(json_data)
            
            logger.debug(
                f"Retrieved signal from Redis",
                symbol=symbol,
                signal=signal_data.get("signal"),
                confidence=signal_data.get("confidence")
            )
            return signal_data
        except Exception as e:
            logger.error(f"Error getting signal from Redis: {e}", symbol=symbol)
            return None
    
    def get_signal_history(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get signal history from Redis
        
        Args:
            symbol: Trading pair symbol
            limit: Maximum number of signals to return
            
        Returns:
            List of signal data
        """
        if not self.is_connected():
            return []
        
        try:
            # Get key
            key = f"signal_history:{symbol}"
            json_data_list = self.redis.lrange(key, 0, limit - 1)
            
            if not json_data_list:
                return []
            
            # Convert JSON to dict
            signal_history = [json.loads(json_data) for json_data in json_data_list]
            
            logger.debug(
                f"Retrieved signal history from Redis",
                symbol=symbol,
                count=len(signal_history)
            )
            return signal_history
        except Exception as e:
            logger.error(f"Error getting signal history from Redis: {e}", symbol=symbol)
            return []

# Create singleton instance
redis_manager = RedisManager()
