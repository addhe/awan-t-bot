"""
Main bot implementation for spot trading
"""
import os
import time
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import ccxt
import pandas as pd
from typing import Dict, Any, Optional

from config.settings import (
    TRADING_PAIRS,
    STRATEGY_CONFIG,
    TRADING_CONFIG,
    SYSTEM_CONFIG,
    LOG_CONFIG,
    TELEGRAM_CONFIG,
    EXCHANGE_CONFIG
)
from src.strategies.spot_strategy import SpotStrategy
from src.utils import setup_telegram, send_telegram_message, BotStatusMonitor, rate_limited_api

# Setup logging
os.makedirs('logs', exist_ok=True)
handler = RotatingFileHandler(
    LOG_CONFIG['log_file'],
    maxBytes=LOG_CONFIG['max_file_size'],
    backupCount=LOG_CONFIG['backup_count']
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logging.basicConfig(
    handlers=[handler, console_handler],
    level=LOG_CONFIG['log_level'],
    format=LOG_CONFIG['log_format']
)
logger = logging.getLogger(__name__)

class SpotTradingBot:
    def __init__(self):
        """Initialize basic bot attributes"""
        self.exchange = None
        self.strategy = None
        self.active_trades = {}
        self.start_time = datetime.now()
        self.monitor = BotStatusMonitor()
        self.last_status_update = 0  # timestamp of last status update
        self.last_health_check = datetime.now()

    async def initialize(self):
        """Async initialization of bot components"""
        self.exchange = self._initialize_exchange()
        self.strategy = SpotStrategy(**STRATEGY_CONFIG)

        # Initialize Telegram if enabled
        if TELEGRAM_CONFIG['enabled']:
            await setup_telegram(
                TELEGRAM_CONFIG['bot_token'],
                TELEGRAM_CONFIG['chat_id']
            )
        return self

    def _initialize_exchange(self) -> ccxt.Exchange:
        """Initialize the exchange connection"""
        try:
            exchange_class = getattr(ccxt, EXCHANGE_CONFIG['name'])
            exchange = exchange_class({
                'apiKey': EXCHANGE_CONFIG['api_key'],
                'secret': EXCHANGE_CONFIG['api_secret'],
                'enableRateLimit': True
            })

            if EXCHANGE_CONFIG['testnet']:
                exchange.set_sandbox_mode(True)

            return exchange

        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise

    @rate_limited_api()
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data from exchange with rate limiting"""
        try:
            # Configure timeouts
            self.exchange.options['timeout'] = SYSTEM_CONFIG['connection_timeout'] * 1000
            self.exchange.options['recvWindow'] = SYSTEM_CONFIG['read_timeout'] * 1000

            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                logger.warning(f"No OHLCV data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV data for {symbol}: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Network error: {str(e)}")
            return pd.DataFrame()

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV data for {symbol}: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Exchange error: {str(e)}")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Unexpected error fetching OHLCV data for {symbol}: {e}")
            return pd.DataFrame()

    @rate_limited_api()
    def get_all_balances(self) -> Dict[str, float]:
        """Get available balances for all assets with rate limiting"""
        try:
            # Configure timeouts
            self.exchange.options['timeout'] = SYSTEM_CONFIG['connection_timeout'] * 1000

            balance = self.exchange.fetch_balance()
            if not balance:
                logger.warning("No balance data returned")
                return {}

            # Get total balance data
            total = balance.get('total', {})
            return {asset: float(amount)
                    for asset, amount in total.items()
                    if float(amount) > 0}

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching balances: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Network error checking balances: {str(e)}")
            return {}

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching balances: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Exchange error checking balances: {str(e)}")
            return {}

        except Exception as e:
            logger.error(f"Unexpected error fetching balances: {e}")
            return {}

    def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            # Fetch latest OHLCV data
            df = self.fetch_ohlcv(symbol, timeframe='1m', limit=1)
            if df.empty:
                raise Exception(f"No price data available for {symbol}")
            return float(df['close'].iloc[-1])
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None

    def convert_to_usdt(self, asset: str, amount: float) -> bool:
        """Convert an asset to USDT using market order"""
        try:
            if asset == 'USDT':
                return True

            symbol = f"{asset}/USDT"

            # Check if trading pair exists
            try:
                self.exchange.load_markets()
                market = self.exchange.market(symbol)
            except Exception:
                logger.error(f"Trading pair {symbol} not available")
                return False

            # Place market sell order
            order = self.exchange.create_market_sell_order(
                symbol,
                amount,
                {'type': 'market'}
            )

            logger.info(f"Converted {amount} {asset} to USDT: {order}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(
                    f"💱 Converted {amount} {asset} to USDT\n" \
                    f"Order: {order['id']}"
                )
            return True

        except Exception as e:
            logger.error(f"Error converting {asset} to USDT: {e}")
            return False

    def ensure_usdt_balance(self) -> float:
        """Check balances and convert to USDT if needed"""
        try:
            balances = self.get_all_balances()
            usdt_balance = balances.get('USDT', 0)

            if usdt_balance >= 10:  # Minimum USDT for trading
                return usdt_balance

            # Try to convert other assets to USDT
            for asset, amount in balances.items():
                if asset in ['BTC', 'BNB'] and amount > 0:
                    # Calculate minimum trade amount
                    min_amount = 0.0001 if asset == 'BTC' else 0.01  # BNB

                    if amount > min_amount:
                        logger.info(f"Found {amount} {asset}, converting to USDT")
                        if self.convert_to_usdt(asset, amount):
                            # Wait for order to settle
                            time.sleep(2)
                            return self.get_all_balances().get('USDT', 0)

            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(
                    "⚠️ Insufficient USDT balance and no convertible assets found"
                )
            return 0

        except Exception as e:
            logger.error(f"Error ensuring USDT balance: {e}")
            return 0

    @rate_limited_api(is_order=True)
    def place_market_buy(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place a market buy order with rate limiting"""
        try:
            # Configure timeouts
            self.exchange.options['timeout'] = SYSTEM_CONFIG['connection_timeout'] * 1000

            order = self.exchange.create_market_buy_order(symbol, quantity)
            if not order:
                logger.error(f"No order data returned for market buy {symbol}")
                return {}

            logger.info(f"Placed market buy order: {order}")
            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for market buy {symbol}: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Insufficient funds: {str(e)}")
            return {}

        except ccxt.NetworkError as e:
            logger.error(f"Network error placing market buy for {symbol}: {e}")
            if TELEGRAM_CONFIG['enabled']:
                send_telegram_message(f"🔴 Network error placing order: {str(e)}")
            return {}

        except Exception as e:
            logger.error(f"Unexpected error placing market buy for {symbol}: {e}")
            return {}

    def place_market_sell(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Place a market sell order"""
        try:
            order = self.exchange.create_market_sell_order(symbol, quantity)
            logger.info(f"Placed market sell order: {order}")
            return order

        except Exception as e:
            logger.error(f"Error placing market sell for {symbol}: {e}")
            return {}

    async def check_health(self) -> bool:
        """Check system and exchange health"""
        try:
            # Check if exchange is initialized
            if not self.exchange:
                logger.error("Exchange not initialized")
                return False

            # Check API connection
            try:
                self.exchange.fetch_balance()
            except Exception as e:
                logger.error(f"API connection error: {e}")
                if TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🔴 Error: Health check failed - {str(e)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            if TELEGRAM_CONFIG['enabled']:
                await send_telegram_message(f"🔴 Error: Health check failed - {str(e)}")
            return False

    async def process_pair(self, pair_config: Dict[str, Any]):
        """Process a single trading pair"""
        try:
            symbol = pair_config['symbol']

            # Skip if we already have an active trade for this pair
            if symbol in self.active_trades:
                return

            # Get market data
            df = self.fetch_ohlcv(symbol)
            if df.empty:
                return

            # Calculate indicators
            df = self.strategy.calculate_indicators(df)

            # Check buy signal
            should_buy, confidence, levels = self.strategy.should_buy(df)

            if should_buy and confidence >= 0.75:
                # Calculate position size with smart allocation
                balance = self.ensure_usdt_balance()
                quantity, allocation_info = self.strategy.calculate_position_size(
                    balance,
                    levels['entry'],
                    pair_config['symbol']
                )

                # Check if we can open more positions
                if len(self.active_trades) >= allocation_info['max_positions']:
                    logger.info(f"Maximum positions ({allocation_info['max_positions']}) reached")
                    return

                # Adjust quantity to meet minimum requirements
                min_quantity = pair_config['min_quantity']
                if quantity < min_quantity:
                    logger.info(
                        f"Calculated quantity {quantity} below minimum {min_quantity}\n" \
                        f"Balance: {balance} USDT\n" \
                        f"Max allocation: {allocation_info['allocation_percent']}%"
                    )
                    return

                # Round quantity to required precision
                quantity = round(quantity, pair_config['quantity_precision'])

                # Place buy order
                order = self.place_market_buy(symbol, quantity)
                if order:
                    self.active_trades[symbol] = {
                        'entry_price': levels['entry'],
                        'quantity': quantity,
                        'stop_loss': levels['stop_loss'],
                        'take_profit': levels['take_profit'],
                        'entry_time': datetime.now()
                    }

                    if TELEGRAM_CONFIG['enabled']:
                        await send_telegram_message(
                            f"🟢 New {symbol} position opened\n"
                            f"Price: {levels['entry']}\n"
                            f"Quantity: {quantity}\n"
                            f"Value: {allocation_info['usdt_value']:.2f} USDT\n"
                            f"Allocation: {allocation_info['allocation_percent']:.1f}%\n"
                            f"Target Profit: {allocation_info['min_profit']:.1f}%\n"
                            f"Stop Loss: {allocation_info['stop_loss']:.1f}%\n"
                            f"Risk/Reward: {(allocation_info['min_profit']/allocation_info['stop_loss']):.2f}"
                        )

        except Exception as e:
            logger.error(f"Error processing {pair_config['symbol']}: {e}")

    async def check_active_trades(self):
        """Check and manage active trades"""
        try:
            for symbol, trade in list(self.active_trades.items()):
                # Get current market data
                df = self.fetch_ohlcv(symbol, timeframe='15m', limit=10)
                if df.empty:
                    continue

                current_price = df['close'].iloc[-1]

                # Check if we should sell
                should_sell, confidence = self.strategy.should_sell(
                    df,
                    buy_price=trade['entry_price']
                )

                if should_sell:
                    # Place sell order
                    order = self.place_market_sell(symbol, trade['quantity'])
                    if order:
                        profit = (current_price - trade['entry_price']) / trade['entry_price']
                        del self.active_trades[symbol]

                        if TELEGRAM_CONFIG['enabled']:
                            emoji = "🟢" if profit > 0 else "🔴"
                            await send_telegram_message(
                                f"{emoji} Closed {symbol} position\n"
                                f"Entry: {trade['entry_price']}\n"
                                f"Exit: {current_price}\n"
                                f"Profit: {profit:.2%}"
                            )

        except Exception as e:
            logger.error(f"Error checking active trades: {e}")

    def _graceful_shutdown(self):
        """Handle graceful shutdown of the bot"""
        try:
            # Cancel any pending orders
            for symbol in [pair['symbol'] for pair in TRADING_PAIRS]:
                try:
                    open_orders = self.exchange.fetch_open_orders(symbol)
                    for order in open_orders:
                        self.exchange.cancel_order(order['id'], symbol)
                        logger.info(f"Cancelled order {order['id']} for {symbol}")
                except Exception as e:
                    logger.error(f"Error cancelling orders for {symbol}: {e}")

            # Log active trades
            if self.active_trades:
                msg = "⚠️ Active trades at shutdown:\n"
                for symbol, trade in self.active_trades.items():
                    msg += f"- {symbol}: Entry at {trade['entry_price']}\n"
                logger.warning(msg)
                if TELEGRAM_CONFIG['enabled']:
                    send_telegram_message(msg)

        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")

    async def update_status(self):
        """Update bot status and active trades"""
        try:
            # Get current balance
            balances = self.get_all_balances()

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
                    'errors_24h': self._rate_manager.circuit_breaker.errors
                },
                'balance': balances,
                'performance': performance
            }

            # Update status files
            self.monitor.update_bot_status(status)
            self.monitor.update_trades([
                {
                    'symbol': symbol,
                    'entry_price': trade['entry_price'],
                    'current_price': self._get_current_price(symbol),
                    'quantity': trade['quantity'],
                    'pnl': self._calculate_pnl(trade)
                } for symbol, trade in self.active_trades.items()
            ])

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
                'win_rate': (winning_trades / len(trades)) * 100,
                'total_profit': total_profit
            }

        except Exception as e:
            logger.error(f"Error calculating performance: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_profit': 0.0
            }

    async def run(self):
        """Main bot loop"""
        logger.info("Starting bot...")

        try:
            if TELEGRAM_CONFIG['enabled']:
                await send_telegram_message("🤖 Trading bot started")

            # Register signal handlers
            import signal
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
                    await self.check_active_trades()

                    # Process each trading pair
                    for pair_config in TRADING_PAIRS:
                        if len(self.active_trades) >= TRADING_CONFIG['max_open_trades']:
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

if __name__ == '__main__':
    import asyncio
    async def main():
        bot = SpotTradingBot()
        await bot.initialize()
        await bot.run()
    asyncio.run(main())
