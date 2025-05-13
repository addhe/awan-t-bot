"""
Data Synchronization Utility
Syncs data between Redis (short-term cache) and PostgreSQL (long-term storage)
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

from src.utils.redis_manager import RedisManager
from src.utils.postgres_manager import PostgresManager
from src.utils.status_monitor import BotStatusMonitor

logger = logging.getLogger(__name__)

class DataSyncManager:
    """
    Manages synchronization of data between Redis and PostgreSQL
    Ensures that short-term cache data is properly stored for long-term analysis
    """
    def __init__(self):
        """Initialize Redis and PostgreSQL connections"""
        self.redis = RedisManager()
        self.postgres = PostgresManager()
        self.monitor = BotStatusMonitor()
        self.last_sync = datetime.now()
    
    async def sync_active_trades(self) -> bool:
        """
        Sync active trades from Redis to PostgreSQL
        
        Returns:
            bool: Success status
        """
        if not self.redis.is_connected() or not self.postgres.is_connected():
            logger.error("Cannot sync trades: Database connections not available")
            return False
        
        try:
            # Get active trades from Redis
            redis_trades_data = self.redis.redis.get("active_trades")
            if not redis_trades_data:
                logger.info("No active trades found in Redis to sync")
                return True
            
            try:
                active_trades = json.loads(redis_trades_data)
                if not active_trades:
                    return True
                    
                # Check if active_trades is a dictionary or a list
                if isinstance(active_trades, dict):
                    # Convert dictionary to list format
                    trades_list = []
                    for symbol, trade_data in active_trades.items():
                        if isinstance(trade_data, dict):
                            trade_info = trade_data.copy()  # Make a copy to avoid modifying original
                            trade_info["symbol"] = symbol  # Add symbol to the trade info
                            trades_list.append(trade_info)
                    active_trades = trades_list
            except json.JSONDecodeError:
                logger.error(f"Error decoding active trades JSON from Redis: {redis_trades_data}")
                return False
            
            # Get existing trades from PostgreSQL to avoid duplicates
            existing_trades = self.postgres.get_trades(status="open")
            existing_symbols = {t['symbol']: t['id'] for t in existing_trades}
            
            synced_count = 0
            for trade in active_trades:
                symbol = trade.get('symbol')
                if not symbol:
                    continue
                
                # Prepare trade data for PostgreSQL
                trade_data = {
                    'symbol': symbol,
                    'entry_price': float(trade.get('entry_price', 0)),
                    'quantity': float(trade.get('quantity', 0)),
                    'entry_time': trade.get('entry_time', datetime.now().isoformat()),
                    'stop_loss': float(trade.get('stop_loss', 0)),
                    'take_profit': float(trade.get('take_profit', 0)),
                    'status': 'open',
                    'strategy': trade.get('strategy', 'default'),
                    'timeframe': trade.get('timeframe', '1h'),
                    'confidence': float(trade.get('confidence', 0))
                }
                
                # Update or insert trade
                if symbol in existing_symbols:
                    # Update existing trade
                    trade_id = existing_symbols[symbol]
                    update_data = {
                        'current_price': float(trade.get('current_price', 0)),
                        'pnl': float(trade.get('pnl', 0))
                    }
                    self.postgres.update_trade(trade_id, update_data)
                else:
                    # Insert new trade
                    self.postgres.save_trade(trade_data)
                
                synced_count += 1
            
            logger.info(f"Synced {synced_count} active trades from Redis to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error syncing active trades: {e}")
            return False
    
    async def sync_signals(self) -> bool:
        """
        Sync trading signals from Redis to PostgreSQL
        
        Returns:
            bool: Success status
        """
        if not self.redis.is_connected() or not self.postgres.is_connected():
            logger.error("Cannot sync signals: Database connections not available")
            return False
        
        try:
            # Get all signal keys from Redis
            signal_keys = self.redis.redis.keys("signal:*")
            if not signal_keys:
                logger.info("No signals found in Redis to sync")
                return True
            
            synced_count = 0
            for key in signal_keys:
                signal_data = self.redis.redis.get(key)
                if not signal_data:
                    continue
                
                signal_dict = json.loads(signal_data)
                symbol = signal_dict.get("symbol")
                if not symbol:
                    continue
                
                # Prepare signal data for PostgreSQL
                pg_signal_data = {
                    'symbol': symbol,
                    'signal_type': signal_dict.get('signal', 'neutral'),
                    'confidence': float(signal_dict.get('confidence', 0)),
                    'price': float(signal_dict.get('price', 0)),
                    'timeframes': signal_dict.get('timeframes', []),
                    'indicators': signal_dict.get('indicators', {}),
                    'timestamp': signal_dict.get('timestamp', datetime.now().isoformat())
                }
                
                # Save signal to PostgreSQL
                self.postgres.save_signal(pg_signal_data)
                synced_count += 1
            
            logger.info(f"Synced {synced_count} signals from Redis to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error syncing signals: {e}")
            return False
    
    async def sync_market_data(self) -> bool:
        """
        Sync OHLCV market data from Redis to PostgreSQL
        
        Returns:
            bool: Success status
        """
        if not self.redis.is_connected() or not self.postgres.is_connected():
            logger.error("Cannot sync market data: Database connections not available")
            return False
        
        try:
            # Get all OHLCV keys from Redis
            ohlcv_keys = self.redis.redis.keys("ohlcv:*")
            if not ohlcv_keys:
                logger.info("No OHLCV data found in Redis to sync")
                return True
            
            synced_count = 0
            for key in ohlcv_keys:
                # Parse key to get symbol and timeframe
                # Format: ohlcv:{symbol}:{timeframe}
                parts = key.decode('utf-8').split(':')
                if len(parts) < 3:
                    continue
                
                symbol = parts[1]
                timeframe = parts[2]
                
                # Get OHLCV data from Redis
                ohlcv_data = self.redis.redis.get(key)
                if not ohlcv_data:
                    continue
                
                # Parse OHLCV data
                ohlcv_list = json.loads(ohlcv_data)
                if not ohlcv_list:
                    continue
                
                # Save to PostgreSQL
                self.postgres.save_market_data(symbol, timeframe, ohlcv_list)
                synced_count += 1
            
            logger.info(f"Synced {synced_count} OHLCV datasets from Redis to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error syncing market data: {e}")
            return False
    
    async def sync_confidence_levels(self) -> bool:
        """
        Sync confidence levels from Redis to PostgreSQL as signals
        
        Returns:
            bool: Success status
        """
        if not self.redis.is_connected() or not self.postgres.is_connected():
            logger.error("Cannot sync confidence levels: Database connections not available")
            return False
        
        try:
            # Get confidence levels from Redis
            redis_conf_data = self.redis.redis.get("confidence_levels")
            if not redis_conf_data:
                logger.info("No confidence levels found in Redis to sync")
                return True
            
            confidence_data = json.loads(redis_conf_data)
            synced_count = 0
            
            for symbol, data in confidence_data.items():
                if symbol == "last_updated" or not isinstance(data, dict):
                    continue
                
                confidence = data.get("confidence", 0)
                timestamp = data.get("timestamp", datetime.now().isoformat())
                timeframes = data.get("analyzed_timeframes", [])
                
                # Determine signal type based on confidence
                signal_type = "buy" if confidence >= 0.7 else "neutral"
                
                # Prepare signal data for PostgreSQL
                pg_signal_data = {
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'confidence': float(confidence),
                    'timeframes': timeframes,
                    'timestamp': timestamp
                }
                
                # Save as signal to PostgreSQL
                self.postgres.save_signal(pg_signal_data)
                synced_count += 1
            
            logger.info(f"Synced {synced_count} confidence levels from Redis to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error syncing confidence levels: {e}")
            return False
    
    async def sync_closed_trades(self) -> bool:
        """
        Sync closed trades from status file to PostgreSQL
        
        Returns:
            bool: Success status
        """
        try:
            # Get closed trades from status file
            closed_trades = self.monitor.get_closed_trades()
            if not closed_trades:
                logger.info("No closed trades found in status file to sync")
                return True
            
            # Get existing trades from PostgreSQL to avoid duplicates
            existing_trades = self.postgres.get_trades(status="closed")
            existing_entries = {
                f"{t['symbol']}_{t['entry_time'].isoformat()}": t['id'] 
                for t in existing_trades
            }
            
            synced_count = 0
            for trade in closed_trades:
                symbol = trade.get('symbol')
                entry_time = trade.get('entry_time')
                if not symbol or not entry_time:
                    continue
                
                # Create a unique key for this trade
                if isinstance(entry_time, str):
                    entry_time_str = entry_time
                else:
                    entry_time_str = entry_time.isoformat()
                
                trade_key = f"{symbol}_{entry_time_str}"
                
                # Prepare trade data for PostgreSQL
                trade_data = {
                    'symbol': symbol,
                    'entry_price': float(trade.get('entry_price', 0)),
                    'exit_price': float(trade.get('exit_price', 0)),
                    'quantity': float(trade.get('quantity', 0)),
                    'entry_time': entry_time_str,
                    'exit_time': trade.get('exit_time', datetime.now().isoformat()),
                    'profit_pct': float(trade.get('profit_pct', 0)),
                    'stop_loss': float(trade.get('stop_loss', 0)),
                    'take_profit': float(trade.get('take_profit', 0)),
                    'status': 'closed',
                    'strategy': trade.get('strategy', 'default'),
                    'timeframe': trade.get('timeframe', '1h')
                }
                
                # Update or insert trade
                if trade_key in existing_entries:
                    # Update existing trade
                    trade_id = existing_entries[trade_key]
                    self.postgres.update_trade(trade_id, trade_data)
                else:
                    # Insert new trade
                    self.postgres.save_trade(trade_data)
                
                synced_count += 1
            
            logger.info(f"Synced {synced_count} closed trades from status file to PostgreSQL")
            return True
        
        except Exception as e:
            logger.error(f"Error syncing closed trades: {e}")
            return False
    
    async def sync_all(self) -> Dict[str, bool]:
        """
        Sync all data between Redis and PostgreSQL
        
        Returns:
            Dict[str, bool]: Results of each sync operation
        """
        results = {
            "active_trades": await self.sync_active_trades(),
            "signals": await self.sync_signals(),
            "market_data": await self.sync_market_data(),
            "confidence_levels": await self.sync_confidence_levels(),
            "closed_trades": await self.sync_closed_trades()
        }
        
        self.last_sync = datetime.now()
        logger.info(f"Completed full data sync at {self.last_sync.isoformat()}")
        
        return results


async def run_sync():
    """Run a full data sync as a standalone script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    sync_manager = DataSyncManager()
    results = await sync_manager.sync_all()
    
    # Print results
    print("\n📊 Data Sync Results:")
    for operation, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        print(f"  - {operation}: {status}")


if __name__ == "__main__":
    # Run sync as standalone script
    asyncio.run(run_sync())
