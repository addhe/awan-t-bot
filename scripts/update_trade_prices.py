#!/usr/bin/env python
"""
Script untuk memperbarui current_price dan pnl di Redis untuk posisi aktif
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime

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
from src.utils.status_monitor import BotStatusMonitor
from src.utils.telegram_utils import send_telegram_message
from config.settings import EXCHANGE_CONFIG, SYSTEM_CONFIG

async def update_trade_prices():
    """Update current_price and pnl for active trades in Redis"""
    try:
        # Initialize components
        exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
        redis_manager = RedisManager()
        status_monitor = BotStatusMonitor()
        
        # Get active trades from status monitor
        active_trades = status_monitor.get_active_trades()
        if not active_trades:
            logger.info("No active trades found")
            return
        
        logger.info(f"Found {len(active_trades)} active trades")
        
        # Update current prices and PnL for active trades
        updated_trades = {}
        for symbol, trade_data in active_trades.items():
            try:
                # Get current price from exchange
                current_price = await exchange.get_current_price(symbol)
                entry_price = float(trade_data.get('entry_price', 0))
                
                # Calculate PnL
                if entry_price > 0 and current_price > 0:
                    pnl = round(((current_price - entry_price) / entry_price) * 100, 2)
                else:
                    pnl = 0
                    
                # Update trade data
                updated_trade = trade_data.copy()
                updated_trade['current_price'] = current_price
                updated_trade['pnl'] = pnl
                updated_trades[symbol] = updated_trade
                
                # Also save the trade info to Redis for quick access
                try:
                    redis_key = f"active_trade:{symbol}"
                    redis_manager.redis.hset(redis_key, mapping={
                        "symbol": symbol,
                        "entry_price": str(entry_price),
                        "current_price": str(current_price),
                        "quantity": str(trade_data.get("quantity", 0)),
                        "pnl": str(pnl),
                        "updated_at": datetime.now().isoformat()
                    })
                    # Set expiration to 1 day
                    redis_manager.redis.expire(redis_key, 60 * 60 * 24)
                    logger.info(f"Updated {symbol} in Redis: Current Price={current_price}, PnL={pnl}%")
                except Exception as e:
                    logger.error(f"Error saving trade to Redis for {symbol}: {e}")
                    
            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                updated_trades[symbol] = trade_data  # Keep original data
        
        # Update active trades in status monitor
        if updated_trades:
            status_monitor.update_active_trades(updated_trades)
            logger.info(f"Updated {len(updated_trades)} active trades in status monitor")
            
            # Also save all active trades to Redis
            try:
                redis_manager.redis.set("active_trades", json.dumps([
                    {**trade_data, "symbol": symbol} 
                    for symbol, trade_data in updated_trades.items()
                ]))
                redis_manager.redis.expire("active_trades", 60 * 60 * 24)  # 1 day expiration
                logger.info(f"Saved {len(updated_trades)} active trades to Redis")
            except Exception as e:
                logger.error(f"Error saving active trades to Redis: {e}")
        
        # Send status update via Telegram
        status_message = status_monitor.format_status_message()
        await send_telegram_message(status_message)
        logger.info("Sent updated status to Telegram")
        
        return True
    
    except Exception as e:
        logger.error(f"Error updating trade prices: {e}", exc_info=True)
        return False

async def main():
    """Main function"""
    logger.info("Starting trade price update")
    success = await update_trade_prices()
    if success:
        logger.info("Trade price update completed successfully")
    else:
        logger.error("Trade price update failed")

if __name__ == "__main__":
    asyncio.run(main())
