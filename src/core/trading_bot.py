"""
Core trading bot implementation
"""
import os
import time
import asyncio
import logging
import signal
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Type

from config.settings import (
    TRADING_PAIRS,
    STRATEGY_CONFIG,
    TRADING_CONFIG,
    SYSTEM_CONFIG,
    LOG_CONFIG,
    TELEGRAM_CONFIG,
    EXCHANGE_CONFIG,
    TIMEFRAMES
)
from src.strategies.boll_stoch_strategy import BollStochStrategy
from src.exchange.connector import ExchangeConnector
from src.core.position_manager import PositionManager
from src.utils.status_monitor import BotStatusMonitor
from src.utils.telegram_utils import setup_telegram, send_telegram_message

logger = logging.getLogger(__name__)

class TradingBot:
    """Core trading bot implementation with modular components"""
    
    def __init__(self):
        """Initialize trading bot components"""
        self.exchange = None
        self.strategy = None
        self.position_manager = None
        self.monitor = BotStatusMonitor()
        self.start_time = datetime.now()
        self.last_status_update = 0  # timestamp of last status update
        self.last_health_check = datetime.now()
        
    async def initialize(self):
        """Async initialization of bot components"""
        logger.info("Initializing trading bot...")
        
        # Initialize exchange connector
        self.exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)
        
        # Initialize strategy
        self.strategy = BollStochStrategy(**STRATEGY_CONFIG, timeframes=TIMEFRAMES)
        
        # Initialize position manager
        self.position_manager = PositionManager(
            self.exchange, 
            TRADING_CONFIG,
            self.monitor
        )
        
        # Initialize Telegram if enabled
        if TELEGRAM_CONFIG['enabled']:
            await setup_telegram(
                TELEGRAM_CONFIG['bot_token'],
                TELEGRAM_CONFIG['chat_id']
            )
            
        logger.info("Trading bot initialized successfully")
        return self
        
    async def check_health(self) -> bool:
        """Check system and exchange health
        
        Returns:
            True if system is healthy, False otherwise
        """
        try:
            # Get exchange status
            balances = await self.exchange.get_all_balances()
            
            # Check if we have at least one balance
            if not balances:
                logger.warning("No balances returned from exchange")
                return False
                
            # Check rate limiter health
            # TODO: Add rate limiter health check
            
            # Update last health check time
            self.last_health_check = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            if TELEGRAM_CONFIG['enabled']:
                await send_telegram_message(f"🔴 Health check failed: {str(e)}")
            return False
            
    async def process_pair(self, pair_config: Dict[str, Any]) -> bool:
        """Process a single trading pair for signals
        
        Args:
            pair_config: Trading pair configuration
            
        Returns:
            True if a trade was executed, False otherwise
        """
        try:
            symbol = pair_config['symbol']
            
            # Skip if we're already in a position for this symbol
            if symbol in self.position_manager.active_trades:
                return False
                
            # Fetch data for multiple timeframes
            timeframe_data = {}
            for tf in TIMEFRAMES:
                df = await self.exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
                if not df.empty:
                    df = self.strategy.calculate_indicators(df)
                    timeframe_data[tf] = df
                    
            if not timeframe_data:
                logger.warning(f"Could not fetch data for {symbol} in any timeframe")
                return False
                
            # Analyze signals
            signal, confidence, risk_levels = self.strategy.analyze_signals(timeframe_data)
            
            # If we have a buy signal, execute trade
            if signal == "buy" and confidence > 0.5:
                # Get available balance
                balances = await self.exchange.get_all_balances()
                usdt_balance = balances.get('USDT', 0)
                
                # Get current price
                current_price = await self.exchange.get_current_price(symbol)
                if not current_price:
                    logger.warning(f"Could not get current price for {symbol}")
                    return False
                    
                # Calculate position size
                quantity, allocation_info = self.strategy.calculate_position_size(
                    usdt_balance,
                    current_price,
                    pair_config,
                    TRADING_CONFIG
                )
                
                # Adjust quantity to meet minimum requirements
                min_quantity = pair_config['min_quantity']
                if quantity < min_quantity:
                    logger.info(
                        f"Calculated quantity {quantity} below minimum {min_quantity}\n"
                        f"Balance: {usdt_balance} USDT\n"
                        f"Max allocation: {allocation_info.get('allocation_pct', 0)}%"
                    )
                    return False
                    
                # Round quantity to required precision
                quantity = round(quantity, pair_config['quantity_precision'])
                
                # Open position
                position = await self.position_manager.open_position(
                    symbol,
                    quantity,
                    current_price,
                    risk_levels,
                    confidence,
                    pair_config
                )
                
                # Send notification
                if TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(
                        f"🟢 New position: {symbol}\n"
                        f"Price: {current_price}\n"
                        f"Quantity: {quantity}\n"
                        f"Confidence: {confidence:.2f}"
                    )
                    
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error processing pair {pair_config['symbol']}: {e}")
            return False
            
    async def update_status(self) -> None:
        """Update bot status and performance metrics"""
        try:
            # Get current balance
            balances = await self.exchange.get_all_balances()
            
            # Calculate uptime
            uptime = datetime.now() - self.start_time
            hours = uptime.total_seconds() / 3600
            
            # Get performance metrics
            performance = self._calculate_performance()
            
            # Prepare status update
            status = {
                'health': {
                    'is_running': True,
                    'uptime': f"{hours:.1f} hours",
                    'last_check': datetime.now().isoformat(),
                    'errors_24h': 0  # TODO: Implement error tracking
                },
                'balance': balances,
                'performance': performance
            }
            
            # Update status files
            self.monitor.update_bot_status(status)
            
            # Send status to Telegram if enabled
            if TELEGRAM_CONFIG['enabled']:
                # Only send status update every hour
                now = time.time()
                if now - self.last_status_update >= 3600:  # 1 hour
                    await send_telegram_message(self.monitor.format_status_message())
                    self.last_status_update = now
                    
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            
    def _calculate_performance(self) -> Dict[str, float]:
        """Calculate 24h performance metrics"""
        try:
            # Get trades from the last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            trades = self.monitor.get_completed_trades(since=yesterday)
            
            if not trades:
                return {
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'total_profit': 0.0
                }
                
            # Calculate metrics
            winning_trades = sum(1 for t in trades if t['profit'] > 0)
            total_profit = sum(t['profit'] for t in trades)
            
            return {
                'total_trades': len(trades),
                'win_rate': (winning_trades / len(trades)) * 100 if trades else 0,
                'total_profit': total_profit
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_profit': 0.0
            }
            
    def _graceful_shutdown(self) -> None:
        """Handle graceful shutdown of the bot"""
        try:
            logger.info("Performing graceful shutdown...")
            
            # Cancel pending orders
            asyncio.run(self.position_manager.cancel_all_orders())
            
            # Save active trades
            self.position_manager.graceful_shutdown()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            
    async def run(self) -> None:
        """Main bot loop"""
        logger.info("Starting trading bot...")
        
        try:
            if TELEGRAM_CONFIG['enabled']:
                await send_telegram_message("🤖 Trading bot started")
                
            # Register signal handlers
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, shutting down...")
                self._graceful_shutdown()
                exit(0)
                
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            while True:
                try:
                    # Check system health
                    if not await self.check_health():
                        await asyncio.sleep(SYSTEM_CONFIG['retry_wait'])
                        continue
                        
                    # Check active trades
                    closed_positions = await self.position_manager.check_positions(self.strategy)
                    
                    # Send notifications for closed positions
                    if closed_positions and TELEGRAM_CONFIG['enabled']:
                        for position in closed_positions:
                            emoji = "🟢" if position.get('profit', 0) > 0 else "🔴"
                            await send_telegram_message(
                                f"{emoji} Closed {position['symbol']} position\n"
                                f"Entry: {position['entry_price']}\n"
                                f"Exit: {position['exit_price']}\n"
                                f"Profit: {position.get('profit', 0):.2f}%"
                            )
                            
                    # Process each trading pair
                    for pair_config in TRADING_PAIRS:
                        # Skip if we've reached max open trades
                        if (len(self.position_manager.active_trades) >= 
                                TRADING_CONFIG['max_open_trades']):
                            break
                            
                        await self.process_pair(pair_config)
                        
                    # Update status
                    await self.update_status()
                    
                    # Sleep for the check interval
                    await asyncio.sleep(SYSTEM_CONFIG['check_interval'])
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    if TELEGRAM_CONFIG['enabled']:
                        await send_telegram_message(f"🔴 Error in main loop: {str(e)}")
                    await asyncio.sleep(SYSTEM_CONFIG['retry_wait'])
                    
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            if TELEGRAM_CONFIG['enabled']:
                await send_telegram_message(f"🔴 Fatal error: {str(e)}")
            raise
