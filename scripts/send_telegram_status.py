#!/usr/bin/env python
"""
Script untuk mengirim status terbaru ke Telegram dengan current price dan P/L yang akurat
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

async def send_telegram_status():
    """Send updated status to Telegram with current prices and P/L"""
    try:
        # Initialize components
        exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
        redis_manager = RedisManager()
        status_monitor = BotStatusMonitor()
        
        # Get bot status
        status = status_monitor.get_bot_status()
        if not status:
            logger.error("Could not get bot status")
            return False
        
        # Get active trades
        active_trades = status_monitor.get_active_trades()
        if not active_trades:
            logger.warning("No active trades found")
            # Continue anyway to show bot status
        
        # Update current prices and P/L for active trades
        updated_trades = []
        for trade in active_trades:
            symbol = trade.get('symbol')
            if not symbol:
                logger.error(f"Missing symbol in trade data: {trade}")
                continue
                
            try:
                # First try to get from Redis for speed
                redis_key = f"active_trade:{symbol}"
                redis_data = redis_manager.redis.hgetall(redis_key)
                
                if redis_data and 'current_price' in redis_data and 'pnl' in redis_data:
                    # Use data from Redis
                    current_price = float(redis_data['current_price'])
                    pnl = float(redis_data['pnl'])
                    logger.info(f"Using Redis data for {symbol}: price={current_price}, pnl={pnl}")
                else:
                    # Fetch from exchange if not in Redis
                    current_price = await exchange.get_current_price(symbol)
                    entry_price = float(trade.get('entry_price', 0))
                    
                    # Calculate P/L
                    if entry_price > 0 and current_price > 0:
                        pnl = round(((current_price - entry_price) / entry_price) * 100, 2)
                    else:
                        pnl = 0
                    
                    logger.info(f"Fetched from exchange for {symbol}: price={current_price}, pnl={pnl}")
                    
                    # Save to Redis for future use
                    try:
                        redis_manager.redis.hset(redis_key, mapping={
                            "current_price": str(current_price),
                            "pnl": str(pnl),
                            "updated_at": datetime.now().isoformat()
                        })
                    except Exception as e:
                        logger.error(f"Error saving to Redis: {e}")
                
                # Update trade data
                updated_trade = trade.copy()
                updated_trade['current_price'] = current_price
                updated_trade['pnl'] = pnl
                updated_trades.append(updated_trade)
                
            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                updated_trades.append(trade)  # Keep original data
        
        # Format status message
        msg = "🤖 Bot Status Report\n\n"
        
        # Add health status
        health = status.get("health", {})
        if health.get("status") == "ok":
            msg += "Status: 🟢 Running\n"
        else:
            msg += "Status: 🔴 Issues Detected\n"
        
        # Add uptime
        uptime = status.get("uptime_hours", 0)
        msg += f"Uptime: {uptime:.1f} hours\n"
        
        # Add last check time
        last_check = status.get("last_updated", datetime.now().isoformat())
        msg += f"Last Check: {last_check}\n\n"
        
        # Add balance
        balance = status.get("balance", {})
        if balance:
            msg += "💰 Balance:\n"
            for asset, amount in balance.items():
                msg += f"{asset}: {amount}\n"
            msg += "\n"
        
        # Add active trades
        if updated_trades:
            msg += f"📊 Active Trades ({len(updated_trades)}):\n"
            for trade in updated_trades:
                msg += f"\n{trade['symbol']}:\n"
                msg += f"Entry: {trade.get('entry_price', 0):.8f}\n"
                
                # Add current price
                current_price = trade.get('current_price')
                if current_price is not None:
                    msg += f"Current: {current_price:.8f}\n"
                else:
                    msg += "Current: None\n"
                
                # Add P/L
                pnl = trade.get('pnl')
                if pnl is not None:
                    msg += f"P/L: {pnl:.2f}%\n"
                else:
                    msg += "P/L: 0.00%\n"
                
                # Add confidence if available
                confidence = trade.get('confidence', 0.5)
                msg += f"Confidence: {confidence:.2f}\n"
        
        # Add performance
        perf = status.get("performance", {})
        msg += "\n📈 Performance (24h):\n"
        msg += f"Trades: {perf.get('trades', 0)}\n"
        msg += f"Win Rate: {perf.get('win_rate', 0.0):.1f}%\n"
        msg += f"Profit: {perf.get('profit', 0.0):.2f}%\n"
        
        # Add confidence levels
        confidence_levels = status_monitor.get_confidence_levels() or {}
        if confidence_levels and any(k != "last_updated" for k in confidence_levels.keys()):
            msg += "\n🎯 Current Confidence Levels:\n"
            for symbol, data in confidence_levels.items():
                if symbol != "last_updated" and isinstance(data, dict) and "confidence" in data:
                    confidence = data.get("confidence", 0)
                    updated = data.get("timestamp", "").split("T")[1][:8] if "timestamp" in data else "unknown"
                    msg += f"{symbol}: {confidence:.2f} (updated: {updated})\n"
        
        # Send message to Telegram
        await send_telegram_message(msg)
        logger.info("Sent updated status to Telegram")
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending Telegram status: {e}", exc_info=True)
        return False

async def main():
    """Main function"""
    logger.info("Starting Telegram status update")
    success = await send_telegram_status()
    if success:
        logger.info("Telegram status update completed successfully")
    else:
        logger.error("Telegram status update failed")

if __name__ == "__main__":
    asyncio.run(main())
