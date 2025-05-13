"""
PostgreSQL Manager for Trading Bot
Handles database connections and operations for storing trading data
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from config.settings import POSTGRES_CONFIG

logger = logging.getLogger(__name__)

class PostgresManager:
    """
    Manages PostgreSQL database connections and operations
    for storing trading data for long-term analysis
    """
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize PostgreSQL connection"""
        self.config = config or POSTGRES_CONFIG
        self.conn = None
        self.cursor = None
        self._initialize_connection()
        self._setup_tables()
    
    def _initialize_connection(self) -> None:
        """Establish connection to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 5432),
                database=self.config.get('database', 'trading_bot'),
                user=self.config.get('user', 'postgres'),
                password=self.config.get('password', '')
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self.conn = None
            self.cursor = None
    
    def is_connected(self) -> bool:
        """Check if connection to PostgreSQL is active"""
        if self.conn is None:
            return False
        try:
            # Try a simple query to check connection
            self.cursor.execute("SELECT 1")
            return True
        except Exception:
            self._initialize_connection()
            return self.conn is not None
    
    def _setup_tables(self) -> None:
        """Create necessary tables if they don't exist"""
        if not self.is_connected():
            logger.error("Cannot set up tables: No database connection")
            return
        
        try:
            # Create trades table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    entry_price NUMERIC NOT NULL,
                    exit_price NUMERIC,
                    current_price NUMERIC,
                    quantity NUMERIC NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    profit_pct NUMERIC,
                    pnl NUMERIC,
                    stop_loss NUMERIC,
                    take_profit NUMERIC,
                    status VARCHAR(20) NOT NULL,
                    strategy VARCHAR(50),
                    timeframe VARCHAR(10),
                    confidence NUMERIC,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create signals table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    signal_type VARCHAR(10) NOT NULL,
                    confidence NUMERIC NOT NULL,
                    price NUMERIC,
                    timeframes JSONB,
                    indicators JSONB,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create market_data table for storing OHLCV
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(20) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    open NUMERIC NOT NULL,
                    high NUMERIC NOT NULL,
                    low NUMERIC NOT NULL,
                    close NUMERIC NOT NULL,
                    volume NUMERIC NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, timestamp)
                )
            """)
            
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error setting up database tables: {e}")
    
    def save_trade(self, trade_data: Dict[str, Any]) -> int:
        """
        Save trade data to PostgreSQL
        
        Args:
            trade_data: Dictionary containing trade information
            
        Returns:
            int: ID of the inserted trade record
        """
        if not self.is_connected():
            logger.error("Cannot save trade: No database connection")
            return -1
        
        try:
            # Prepare data for insertion
            columns = [
                'symbol', 'entry_price', 'exit_price', 'quantity', 
                'entry_time', 'exit_time', 'profit_pct', 'stop_loss', 
                'take_profit', 'status', 'strategy', 'timeframe', 'confidence'
            ]
            
            # Ensure datetime objects for timestamps
            if 'entry_time' in trade_data and isinstance(trade_data['entry_time'], str):
                trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
            
            if 'exit_time' in trade_data and isinstance(trade_data['exit_time'], str):
                trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
            
            # Build query
            values = [trade_data.get(col) for col in columns]
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join(columns)
            
            query = f"""
                INSERT INTO trades ({columns_str})
                VALUES ({placeholders})
                RETURNING id
            """
            
            self.cursor.execute(query, values)
            trade_id = self.cursor.fetchone()['id']
            logger.info(f"Saved trade to PostgreSQL with ID: {trade_id}")
            return trade_id
        
        except Exception as e:
            logger.error(f"Error saving trade to PostgreSQL: {e}")
            return -1
    
    def update_trade(self, trade_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing trade record
        
        Args:
            trade_id: ID of the trade to update
            update_data: Dictionary containing fields to update
            
        Returns:
            bool: Success status
        """
        if not self.is_connected():
            logger.error("Cannot update trade: No database connection")
            return False
        
        try:
            # Build SET clause
            set_clause = ', '.join([f"{key} = %s" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(trade_id)  # For WHERE clause
            
            query = f"""
                UPDATE trades
                SET {set_clause}
                WHERE id = %s
            """
            
            self.cursor.execute(query, values)
            affected_rows = self.cursor.rowcount
            logger.info(f"Updated trade {trade_id} in PostgreSQL, {affected_rows} rows affected")
            return affected_rows > 0
        
        except Exception as e:
            logger.error(f"Error updating trade in PostgreSQL: {e}")
            return False
    
    def save_signal(self, signal_data: Dict[str, Any]) -> int:
        """
        Save trading signal to PostgreSQL
        
        Args:
            signal_data: Dictionary containing signal information
            
        Returns:
            int: ID of the inserted signal record
        """
        if not self.is_connected():
            logger.error("Cannot save signal: No database connection")
            return -1
        
        try:
            # Prepare data for insertion
            columns = [
                'symbol', 'signal_type', 'confidence', 'price',
                'timeframes', 'indicators', 'timestamp'
            ]
            
            # Convert lists/dicts to JSON for JSONB fields
            if 'timeframes' in signal_data and not isinstance(signal_data['timeframes'], str):
                signal_data['timeframes'] = json.dumps(signal_data['timeframes'])
            
            if 'indicators' in signal_data and not isinstance(signal_data['indicators'], str):
                signal_data['indicators'] = json.dumps(signal_data['indicators'])
            
            # Ensure timestamp is a datetime object
            if 'timestamp' in signal_data and isinstance(signal_data['timestamp'], str):
                signal_data['timestamp'] = datetime.fromisoformat(signal_data['timestamp'])
            elif 'timestamp' not in signal_data:
                signal_data['timestamp'] = datetime.now()
            
            # Build query
            values = [signal_data.get(col) for col in columns]
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join(columns)
            
            query = f"""
                INSERT INTO signals ({columns_str})
                VALUES ({placeholders})
                RETURNING id
            """
            
            self.cursor.execute(query, values)
            signal_id = self.cursor.fetchone()['id']
            logger.info(f"Saved signal to PostgreSQL with ID: {signal_id}")
            return signal_id
        
        except Exception as e:
            logger.error(f"Error saving signal to PostgreSQL: {e}")
            return -1
    
    def save_market_data(self, symbol: str, timeframe: str, ohlcv_data: List[List[Any]]) -> bool:
        """
        Save OHLCV market data to PostgreSQL
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe of the data
            ohlcv_data: List of OHLCV data points [timestamp, open, high, low, close, volume]
            
        Returns:
            bool: Success status
        """
        if not self.is_connected():
            logger.error("Cannot save market data: No database connection")
            return False
        
        try:
            # Prepare data for batch insertion
            values = []
            for candle in ohlcv_data:
                # Standard OHLCV format: [timestamp, open, high, low, close, volume]
                timestamp = datetime.fromtimestamp(candle[0] / 1000)  # Convert from milliseconds
                values.append((
                    symbol,
                    timeframe,
                    float(candle[1]),  # open
                    float(candle[2]),  # high
                    float(candle[3]),  # low
                    float(candle[4]),  # close
                    float(candle[5]),  # volume
                    timestamp
                ))
            
            # Use execute_values for efficient batch insert
            execute_values(
                self.cursor,
                """
                INSERT INTO market_data 
                (symbol, timeframe, open, high, low, close, volume, timestamp)
                VALUES %s
                ON CONFLICT (symbol, timeframe, timestamp) 
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """,
                values
            )
            
            logger.info(f"Saved {len(values)} OHLCV records for {symbol} {timeframe} to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error saving market data to PostgreSQL: {e}")
            return False
    
    def get_trades(self, 
                  symbol: Optional[str] = None, 
                  status: Optional[str] = None,
                  limit: int = 100, 
                  offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get trades from PostgreSQL with optional filtering
        
        Args:
            symbol: Filter by trading pair symbol
            status: Filter by trade status (open, closed)
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of trade records
        """
        if not self.is_connected():
            logger.error("Cannot get trades: No database connection")
            return []
        
        try:
            conditions = []
            params = []
            
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)
            
            if status:
                conditions.append("status = %s")
                params.append(status)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
                SELECT * FROM trades
                {where_clause}
                ORDER BY entry_time DESC
                LIMIT %s OFFSET %s
            """
            
            params.extend([limit, offset])
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        
        except Exception as e:
            logger.error(f"Error getting trades from PostgreSQL: {e}")
            return []
    
    def get_signals(self, 
                   symbol: Optional[str] = None,
                   signal_type: Optional[str] = None,
                   min_confidence: float = 0.0,
                   days: int = 7,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get signals from PostgreSQL with optional filtering
        
        Args:
            symbol: Filter by trading pair symbol
            signal_type: Filter by signal type (buy, sell, neutral)
            min_confidence: Minimum confidence threshold
            days: Number of days to look back
            limit: Maximum number of records to return
            
        Returns:
            List of signal records
        """
        if not self.is_connected():
            logger.error("Cannot get signals: No database connection")
            return []
        
        try:
            conditions = ["timestamp > NOW() - INTERVAL '%s days'"]
            params = [days]
            
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)
            
            if signal_type:
                conditions.append("signal_type = %s")
                params.append(signal_type)
            
            if min_confidence > 0:
                conditions.append("confidence >= %s")
                params.append(min_confidence)
            
            where_clause = " WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT * FROM signals
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s
            """
            
            params.append(limit)
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        
        except Exception as e:
            logger.error(f"Error getting signals from PostgreSQL: {e}")
            return []
    
    def get_market_data(self,
                       symbol: str,
                       timeframe: str,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get OHLCV market data from PostgreSQL
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe of the data
            limit: Maximum number of records to return
            
        Returns:
            List of OHLCV records
        """
        if not self.is_connected():
            logger.error("Cannot get market data: No database connection")
            return []
        
        try:
            query = """
                SELECT * FROM market_data
                WHERE symbol = %s AND timeframe = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            
            self.cursor.execute(query, [symbol, timeframe, limit])
            return self.cursor.fetchall()
        
        except Exception as e:
            logger.error(f"Error getting market data from PostgreSQL: {e}")
            return []
    
    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            try:
                if self.cursor:
                    self.cursor.close()
                self.conn.close()
                logger.info("PostgreSQL connection closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL connection: {e}")
            finally:
                self.conn = None
                self.cursor = None
