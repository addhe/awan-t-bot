"""
Core trading bot implementation
"""

import time
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, Any
from config.settings import (
    TRADING_PAIRS,
    STRATEGY_CONFIG,
    TRADING_CONFIG,
    SYSTEM_CONFIG,
    TELEGRAM_CONFIG,
    EXCHANGE_CONFIG,
    REDIS_CONFIG,
    POSTGRES_CONFIG,
)
from src.strategies.boll_stoch_strategy import BollStochStrategy
from src.exchange.connector import ExchangeConnector
from src.core.position_manager import PositionManager
from src.utils.status_monitor import BotStatusMonitor
from src.utils.telegram_utils import setup_telegram, send_telegram_message
from src.utils.error_handlers import (
    handle_exchange_errors,
    handle_strategy_errors,
)
from src.utils.structured_logger import get_logger
from src.utils.redis_manager import RedisManager
from src.utils.postgres_manager import PostgresManager
from src.utils.data_sync import DataSyncManager

logger = get_logger(__name__)


class TradingBot:
    """Core trading bot implementation with modular components"""

    def __init__(self):
        """Initialize trading bot components"""
        self.exchange = None
        self.strategy = None
        self.position_manager = None
        self.monitor = BotStatusMonitor()
        self.redis = None
        self.postgres = None
        self.data_sync = None
        self.start_time = datetime.now()
        self.last_status_update = time.time()  # timestamp of last status update (epoch time)
        self.last_health_check = datetime.now()
        self.last_data_sync = datetime.now() - timedelta(hours=1)  # Force sync on startup

    @handle_exchange_errors(notify=True)
    async def initialize(self):
        """Async initialization of bot components"""
        logger.info(
            "Initializing trading bot...",
            config={"trading_pairs": len(TRADING_PAIRS)},
        )

        # Initialize exchange connector
        self.exchange = ExchangeConnector(EXCHANGE_CONFIG, SYSTEM_CONFIG)

        # Initialize strategy
        self.strategy = BollStochStrategy(
            **STRATEGY_CONFIG
        )

        # Initialize Redis and PostgreSQL connections
        self.redis = RedisManager(REDIS_CONFIG)
        self.postgres = PostgresManager(POSTGRES_CONFIG)
        self.data_sync = DataSyncManager()
        
        # Log connection status
        redis_status = "connected" if self.redis.is_connected() else "disconnected"
        postgres_status = "connected" if self.postgres.is_connected() else "disconnected"
        logger.info(
            "Database connections initialized",
            redis_status=redis_status,
            postgres_status=postgres_status
        )

        # Initialize position manager
        self.position_manager = PositionManager(
            self.exchange, TRADING_CONFIG, self.monitor
        )

        # Initialize Telegram if enabled
        if TELEGRAM_CONFIG["enabled"]:
            await setup_telegram(
                TELEGRAM_CONFIG["bot_token"], TELEGRAM_CONFIG["chat_id"]
            )

        logger.info(
            "Trading bot initialized successfully",
            pairs=[pair["symbol"] for pair in TRADING_PAIRS],
        )
        return self

    @handle_exchange_errors(notify=True)
    async def check_health(self) -> bool:
        """Check system and exchange health

        Returns:
            True if system is healthy, False otherwise
        """
        # Get exchange status
        balances = await self.exchange.get_all_balances()

        # Check if we have at least one balance
        if not balances:
            logger.warning(
                "No balances returned from exchange",
                timestamp=datetime.now().isoformat(),
            )
            return False

        # Check rate limiter health
        # TODO: Add rate limiter health check

        # Update last health check time
        self.last_health_check = datetime.now()
        uptime = (
            self.last_health_check - self.start_time
        ).total_seconds() / 60  # minutes

        logger.info(
            "System health check passed",
            uptime_minutes=round(uptime, 2),
            balance_assets=len(balances),
        )

        return True

    @handle_strategy_errors(notify=True)
    async def process_pair(self, pair_config: Dict[str, Any]) -> bool:
        """Process a single trading pair for signals

        Args:
            pair_config: Trading pair configuration

        Returns:
            True if a trade was executed, False otherwise
        """
        symbol = pair_config["symbol"]

        # Skip if we're already in a position for this symbol
        if symbol in self.position_manager.active_trades:
            # Periksa apakah posisi sedang dalam proses penutupan (pending_close)
            if self.position_manager.active_trades[symbol].get("pending_close", False):
                logger.warning(
                    f"Skipping {symbol} - position is pending close due to previous error",
                    symbol=symbol,
                )
            else:
                logger.debug(
                    f"Skipping {symbol} - already in position",
                    symbol=symbol,
                    entry_price=self.position_manager.active_trades[symbol].get(
                        "entry_price", 0
                    ),
                )
            return False

        # Get market data
        try:
            logger.debug(f"Analyzing {symbol} for trading signals", symbol=symbol)
            
            # Get OHLCV data from Redis first if available
            ohlcv_data = None
            if self.redis and self.redis.is_connected():
                try:
                    # Try to get from Redis first
                    for timeframe in STRATEGY_CONFIG.get("timeframes", ["1h"]):
                        ohlcv_data = self.redis.get_ohlcv(symbol, timeframe)
                        if ohlcv_data is not None and not ohlcv_data.empty:
                            logger.debug(f"Using cached OHLCV data for {symbol} {timeframe} from Redis")
                            break
                except Exception as e:
                    logger.error(f"Error getting OHLCV data from Redis: {e}")
                    ohlcv_data = None
            
            # If not in Redis, get from exchange
            if ohlcv_data is None:
                ohlcv_data = await self.exchange.get_ohlcv(
                    symbol, STRATEGY_CONFIG.get("timeframes", ["1h"])
                )
                
                # Cache in Redis for future use
                if self.redis and self.redis.is_connected():
                    try:
                        for timeframe, df in ohlcv_data.items():
                            self.redis.save_ohlcv(symbol, timeframe, df)
                            logger.debug(f"Cached OHLCV data for {symbol} {timeframe} in Redis")
                    except Exception as e:
                        logger.error(f"Error caching OHLCV data in Redis: {e}")

            # Get current price
            current_price = await self.exchange.get_current_price(symbol)

            # Analyze for signals
            signal, confidence, indicators = self.strategy.analyze(
                symbol, ohlcv_data, current_price
            )

            # Save signal to Redis
            if self.redis and self.redis.is_connected():
                try:
                    self.redis.save_signal(
                        symbol=symbol,
                        signal=signal,
                        confidence=confidence,
                        price=current_price,
                        timeframes=list(ohlcv_data.keys()),
                        indicators=indicators
                    )
                    logger.debug(f"Saved signal for {symbol} to Redis: {signal} with confidence {confidence:.2f}")
                except Exception as e:
                    logger.error(f"Error saving signal to Redis: {e}")

            # Log signal
            logger.info(
                f"Signal analysis for {symbol}: {signal}",
                symbol=symbol,
                signal=signal,
                confidence=f"{confidence:.2f}",
                price=current_price,
                timeframe_conditions={
                    tf: indicators.get(tf, {}) for tf in ohlcv_data.keys()
                },
            )

            # Execute trade if signal is buy
            if signal == "buy" and confidence >= STRATEGY_CONFIG.get("min_confidence", 0.7):
                # Check if we have enough balance
                available_balance = await self.exchange.get_available_balance(
                    TRADING_CONFIG.get("quote_currency", "USDT")
                )
                
                # Calculate position size
                position_size = self.position_manager.calculate_position_size(
                    symbol, current_price
                )
                
                if position_size * current_price > available_balance:
                    logger.warning(
                        f"Insufficient balance for {symbol}",
                        symbol=symbol,
                        required=position_size * current_price,
                        available=available_balance,
                    )
                    return False
                
                # Execute buy order
                trade_result = await self.position_manager.open_position(
                    symbol=symbol,
                    entry_price=current_price,
                    quantity=position_size,
                    confidence=confidence,
                )
                
                if trade_result:
                    logger.info(
                        f"Opened position for {symbol}",
                        symbol=symbol,
                        entry_price=current_price,
                        quantity=position_size,
                        confidence=f"{confidence:.2f}",
                    )
                    
                    # Send Telegram notification
                    if TELEGRAM_CONFIG["enabled"]:
                        await send_telegram_message(
                            f"🟢 Opened position for {symbol}\n"
                            f"Entry price: {current_price}\n"
                            f"Quantity: {position_size}\n"
                            f"Confidence: {confidence:.2f}"
                        )
                    
                    return True
                else:
                    logger.warning(
                        f"Failed to open position for {symbol}",
                        symbol=symbol,
                        entry_price=current_price,
                    )
            
            return False
            
        except Exception as e:
            logger.error(
                f"Error processing {symbol}: {e}",
                symbol=symbol,
                error=str(e),
                exc_info=True,
            )
            return False

    async def update_status(self):
        """Update bot status and performance metrics"""
        current_time = time.time()
        
        # Only update every 5 minutes to avoid too frequent updates
        if current_time - self.last_status_update < SYSTEM_CONFIG.get("status_update_interval", 300):
            return
            
        self.last_status_update = current_time
        
        # Get active trades
        active_trades = self.position_manager.active_trades
        
        # Update status file
        self.monitor.update_active_trades(active_trades)
        
        # Also save active trades to Redis for quick access
        if self.redis and self.redis.is_connected():
            try:
                import json
                self.redis.redis.set("active_trades", json.dumps(active_trades))
                self.redis.redis.expire("active_trades", 60 * 60 * 24)  # 1 day expiration
                logger.debug("Saved active trades to Redis")
            except Exception as e:
                logger.error(f"Error saving active trades to Redis: {e}")
        
        # Calculate uptime
        uptime = datetime.now() - self.start_time
        uptime_hours = uptime.total_seconds() / 3600
        
        # Get balance
        try:
            balances = await self.exchange.get_all_balances()
            total_balance = sum(float(balance) for balance in balances.values())
        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            total_balance = 0
            
        # Update status metrics
        self.monitor.update_status_metrics({
            "uptime_hours": round(uptime_hours, 2),
            "active_trades": len(active_trades),
            "total_balance": round(total_balance, 2),
            "last_updated": datetime.now().isoformat(),
        })
        
        # Log status update
        logger.info(
            "Status updated",
            active_trades=len(active_trades),
            uptime_hours=round(uptime_hours, 2),
        )
        
        # Sync data between Redis and PostgreSQL every hour
        sync_interval = SYSTEM_CONFIG.get("data_sync_interval", 3600)  # Default: 1 hour
        time_since_last_sync = (datetime.now() - self.last_data_sync).total_seconds()
        
        if time_since_last_sync >= sync_interval:
            try:
                logger.info("Starting data synchronization between Redis and PostgreSQL")
                sync_results = await self.data_sync.sync_all()
                
                # Log sync results
                success_count = sum(1 for result in sync_results.values() if result)
                logger.info(
                    f"Data sync completed: {success_count}/{len(sync_results)} operations successful",
                    sync_results=sync_results
                )
                
                self.last_data_sync = datetime.now()
            except Exception as e:
                logger.error(f"Error during data synchronization: {e}")
                
        # Send status update via Telegram if enabled
        if TELEGRAM_CONFIG["enabled"] and TELEGRAM_CONFIG.get("send_status_updates", True):
            now = datetime.now()
            # Only send status updates during trading hours (9 AM - 10 PM)
            if 9 <= now.hour < 22:
                # Ensure we have the latest data before sending the message
                # First update the status metrics with latest data
                self.monitor.update_status_metrics({
                    "uptime_hours": round((datetime.now() - self.start_time).total_seconds() / 3600, 2),
                    "active_trades": len(active_trades),
                    "last_updated": datetime.now().isoformat(),
                })
                
                # Make sure active trades are updated with latest prices
                active_trades_with_prices = {}
                for symbol, trade_data in active_trades.items():
                    # Get the latest price from position manager
                    current_price = trade_data.get('current_price')
                    entry_price = trade_data.get('entry_price')
                    
                    # Calculate PnL if we have both prices
                    pnl = 0.0
                    if current_price and entry_price:
                        try:
                            pnl = round(((float(current_price) - float(entry_price)) / float(entry_price)) * 100, 2)
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            logger.error(f"Error calculating PnL for {symbol}: {e}")
                    
                    # Create updated trade data
                    active_trades_with_prices[symbol] = {
                        **trade_data,
                        'current_price': current_price,
                        'pnl': pnl
                    }
                
                # Update active trades with latest prices
                self.monitor.update_active_trades(active_trades_with_prices)
                
                # Now send the message with updated data
                await send_telegram_message(
                    self.monitor.format_status_message()
                )
                self.last_status_update = time.time()  # Use epoch time for consistency
                logger.info("Sent status update to Telegram")

    def _calculate_performance(self) -> Dict[str, float]:
        """Calculate 24h performance metrics"""
        # Get trades from the last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        trades = self.monitor.get_completed_trades(since=yesterday)

        if not trades:
            logger.debug("No completed trades in the last 24 hours")
            return {"total_trades": 0, "win_rate": 0.0, "total_profit": 0.0}

        # Calculate metrics
        winning_trades = sum(1 for t in trades if t["profit"] > 0)
        total_profit = sum(t["profit"] for t in trades)
        win_rate = (winning_trades / len(trades)) * 100 if trades else 0

        logger.info(
            "Performance metrics calculated",
            trade_count=len(trades),
            winning_trades=winning_trades,
            win_rate=f"{win_rate:.1f}%",
            total_profit=f"{total_profit:.2f}%",
        )

        return {
            "total_trades": len(trades),
            "win_rate": win_rate,
            "total_profit": total_profit,
        }

    async def _graceful_shutdown(self):
        """Handle graceful shutdown of the bot"""
        logger.info("Graceful shutdown initiated")
        
        # Close any open positions if configured to do so
        if TRADING_CONFIG.get("close_positions_on_shutdown", False):
            logger.info("Closing all positions on shutdown")
            try:
                # TODO: Implement position closing logic
                pass
            except Exception as e:
                logger.error(f"Error closing positions: {e}")
        
        # Update final status
        try:
            await self.update_status()
        except Exception as e:
            logger.error(f"Error updating final status: {e}")
        
        # Perform final data sync
        try:
            logger.info("Performing final data sync before shutdown")
            await self.data_sync.sync_all()
        except Exception as e:
            logger.error(f"Error during final data sync: {e}")
        
        # Close database connections
        try:
            if self.redis:
                self.redis.close()
            if self.postgres:
                self.postgres.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
            
        # Log final message
        logger.info(
            "Trading bot shutdown complete",
            uptime_hours=round((datetime.now() - self.start_time).total_seconds() / 3600, 2),
        )
        
        # Send shutdown notification
        if TELEGRAM_CONFIG["enabled"]:
            try:
                await send_telegram_message("🔴 Trading bot shutdown")
            except Exception as e:
                logger.error(f"Error sending shutdown notification: {e}")

    @handle_exchange_errors(notify=True)
    async def run(self) -> None:
        """Main bot loop"""
        logger.info(
            "Starting trading bot...",
            time=datetime.now().isoformat(),
            trading_pairs=[pair["symbol"] for pair in TRADING_PAIRS],
        )

        if TELEGRAM_CONFIG["enabled"]:
            await send_telegram_message("🤖 Trading bot started")

        # Get check interval from config
        check_interval = SYSTEM_CONFIG.get("check_interval", 60)  # Default: 60 seconds

        # Set up event loop and signal handlers
        loop = asyncio.get_event_loop()

        def signal_handler(signum, frame):
            """Handle termination signals"""
            logger.info(f"Received signal {signum}, shutting down...")
            
            # Cancel all tasks
            for task in asyncio.all_tasks(loop):
                task.cancel()
            
            # Run the shutdown process
            loop.run_until_complete(self._graceful_shutdown())
            loop.close()
            exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        cycle_count = 0

        while True:
            cycle_start = time.time()
            cycle_count += 1

            try:
                logger.debug(f"Starting cycle {cycle_count}")

                # Check system health
                if not await self.check_health():
                    logger.warning(
                        "Health check failed, waiting before retry",
                        retry_wait=SYSTEM_CONFIG["retry_wait"],
                    )
                    await asyncio.sleep(SYSTEM_CONFIG["retry_wait"])
                    continue

                # Check active trades
                closed_positions = await self.position_manager.check_positions(
                    self.strategy
                )

                # Send notifications for closed positions
                if closed_positions and TELEGRAM_CONFIG["enabled"]:
                    for closed_position in closed_positions:
                        emoji = (
                            "🟢" if closed_position.get("profit", 0) > 0 else "🔴"
                        )
                        await send_telegram_message(
                            f"{emoji} Closed {closed_position['symbol']} position\n"
                            f"Entry: {closed_position['entry_price']}\n"
                            f"Exit: {closed_position['exit_price']}\n"
                            f"Profit: {closed_position.get('profit', 0):.2f}%"
                        )

                # Process each trading pair
                active_trade_count = len(self.position_manager.active_trades)
                max_trades = TRADING_CONFIG["max_open_trades"]

                if active_trade_count >= max_trades:
                    logger.debug(
                        f"Skipping pair processing - reached max open trades ({max_trades})",
                        active_trades=active_trade_count,
                        max_trades=max_trades,
                    )
                else:
                    open_slots = max_trades - active_trade_count
                    logger.debug(
                        f"Processing pairs with {open_slots} available trade slots",
                        active_trades=active_trade_count,
                        max_trades=max_trades,
                    )
                    
                    # Check Redis for cached signals first
                    prioritized_pairs = []
                    regular_pairs = []
                    
                    if self.redis and self.redis.is_connected():
                        try:
                            # Get buy signals from Redis
                            for pair_config in TRADING_PAIRS:
                                symbol = pair_config["symbol"]
                                signal_data = self.redis.get_signal(symbol)
                                
                                if signal_data and signal_data.get("signal") == "buy" and signal_data.get("confidence", 0) >= STRATEGY_CONFIG.get("min_confidence", 0.7):
                                    # Add to prioritized pairs if we have a recent buy signal
                                    prioritized_pairs.append(pair_config)
                                else:
                                    # Otherwise add to regular pairs
                                    regular_pairs.append(pair_config)
                        except Exception as e:
                            logger.error(f"Error getting signals from Redis: {e}")
                            # Fall back to regular processing
                            regular_pairs = TRADING_PAIRS
                    else:
                        # No Redis connection, use regular processing
                        regular_pairs = TRADING_PAIRS
                    
                    # Process prioritized pairs first, then regular pairs
                    for pair_config in prioritized_pairs + regular_pairs:
                        # Skip if we've reached max open trades
                        if (
                            len(self.position_manager.active_trades)
                            >= max_trades
                        ):
                            break

                        await self.process_pair(pair_config)

                # Update status
                await self.update_status()

                # Calculate cycle time
                cycle_time = time.time() - cycle_start
                sleep_time = max(
                    0, check_interval - cycle_time
                )

                logger.debug(
                    f"Cycle {cycle_count} completed",
                    cycle_time=round(cycle_time, 2),
                    sleep_time=round(sleep_time, 2),
                    active_trades=len(self.position_manager.active_trades),
                )

                # Sleep for the check interval
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(
                    f"Error in main loop: {e}",
                    cycle=cycle_count,
                    error=str(e),
                    exc_info=True,
                )
                if TELEGRAM_CONFIG["enabled"]:
                    await send_telegram_message(
                        f"🔴 Error in main loop: {e}"
                    )
                await asyncio.sleep(SYSTEM_CONFIG["retry_wait"])
