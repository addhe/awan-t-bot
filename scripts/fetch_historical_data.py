#!/usr/bin/env python
"""
Script untuk mengambil dan menyimpan data OHLCV historis dari Binance API ke PostgreSQL dan Redis
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime, timedelta
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from src.exchange.connector import ExchangeConnector
from src.utils.redis_manager import RedisManager
from src.utils.postgres_manager import PostgresManager
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG, TRADING_PAIRS

async def fetch_and_store_historical_data(days=30):
    """Fetch and store historical OHLCV data for all trading pairs"""
    try:
        # Initialize components
        exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
        redis_manager = RedisManager()
        postgres_manager = PostgresManager()
        
        # Timeframes to fetch
        timeframes = ['15m', '1h', '4h']
        
        # Calculate start time (days ago from now)
        start_time = datetime.now() - timedelta(days=days)
        
        for pair_config in TRADING_PAIRS:
            symbol = pair_config['symbol']
            logger.info(f"Fetching historical data for {symbol}")
            
            for timeframe in timeframes:
                logger.info(f"Fetching {timeframe} data for {symbol}")
                
                # Calculate number of candles needed
                if timeframe == '15m':
                    # 4 candles per hour * 24 hours * days
                    limit = min(4 * 24 * days, 1000)  # Binance limit is 1000
                elif timeframe == '1h':
                    # 24 candles per day * days
                    limit = min(24 * days, 1000)
                elif timeframe == '4h':
                    # 6 candles per day * days
                    limit = min(6 * days, 1000)
                else:
                    limit = 500
                
                # Fetch OHLCV data
                try:
                    ohlcv_data = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                    
                    if not ohlcv_data or len(ohlcv_data) == 0:
                        logger.warning(f"No data returned for {symbol} {timeframe}")
                        continue
                    
                    logger.info(f"Fetched {len(ohlcv_data)} candles for {symbol} {timeframe}")
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    # Store in Redis
                    redis_key = f"ohlcv:{symbol}:{timeframe}"
                    try:
                        # Convert DataFrame to JSON
                        json_data = df.to_json(orient='records', date_format='iso')
                        redis_manager.redis.set(redis_key, json_data)
                        redis_manager.redis.expire(redis_key, 60 * 60 * 24 * 7)  # 7 days expiration
                        logger.info(f"Stored {len(df)} candles in Redis for {symbol} {timeframe}")
                    except Exception as e:
                        logger.error(f"Error storing data in Redis for {symbol} {timeframe}: {e}")
                    
                    # Store in PostgreSQL
                    try:
                        # Prepare data for PostgreSQL
                        for _, row in df.iterrows():
                            postgres_manager.insert_market_data(
                                symbol=symbol,
                                timeframe=timeframe,
                                open_price=float(row['open']),
                                high_price=float(row['high']),
                                low_price=float(row['low']),
                                close_price=float(row['close']),
                                volume=float(row['volume']),
                                timestamp=row['timestamp'].isoformat()
                            )
                        logger.info(f"Stored {len(df)} candles in PostgreSQL for {symbol} {timeframe}")
                    except Exception as e:
                        logger.error(f"Error storing data in PostgreSQL for {symbol} {timeframe}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error fetching data for {symbol} {timeframe}: {e}")
                
                # Sleep to avoid rate limiting
                await asyncio.sleep(1)
        
        logger.info("Historical data fetch and store completed")
        return True
    
    except Exception as e:
        logger.error(f"Error fetching and storing historical data: {e}", exc_info=True)
        return False

async def main():
    """Main function"""
    logger.info("Starting historical data fetch")
    days = 30  # Default to 30 days
    
    # Check if days argument is provided
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
            logger.info(f"Will fetch data for the last {days} days")
        except ValueError:
            logger.warning(f"Invalid days argument: {sys.argv[1]}, using default of 30 days")
    
    success = await fetch_and_store_historical_data(days=days)
    if success:
        logger.info("Historical data fetch completed successfully")
    else:
        logger.error("Historical data fetch failed")

if __name__ == "__main__":
    asyncio.run(main())
