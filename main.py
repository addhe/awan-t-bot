import ccxt
import os
import logging
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pandas as pd

from config import CONFIG
from src.system_monitor import SystemMonitor, send_telegram_notification
from src.exchange_manager import initialize_exchange

# Import refactored modules
from src.market_analysis import (
    calculate_indicators,
    check_market_conditions,
    analyze_market_depth,
    check_trend_strength
)
from src.risk_management import (
    calculate_position_size,
    validate_position_size,
    calculate_dynamic_stop_loss,
    manage_position_risk,
    assess_risk_conditions
)
from src.order_manager import (
    place_order_with_sl_tp,
    set_leverage,
    check_funding_rate,
    close_position,
    cleanup_old_orders
)
from src.performance_tracker import (
    PerformanceMetrics,
    analyze_trading_performance,
    check_risk_limits
)
from src.system_health_monitor import (
    check_system_health,
    recover_from_error,
    handle_exchange_error,
    log_market_conditions
)
from src.utils import (
    fetch_ohlcv,
    calculate_min_order_size,
    check_existing_position,
    update_market_data,
    validate_config
)

# Logging setup
os.makedirs('logs', exist_ok=True)
log_handler = RotatingFileHandler('logs/trade_log.log', maxBytes=5*1024*1024, backupCount=2)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API Configuration
API_KEY = os.environ.get('API_KEY_BINANCE')
API_SECRET = os.environ.get('API_SECRET_BINANCE')

if API_KEY is None or API_SECRET is None:
    logging.error('API credentials not found in environment variables')
    exit(1)

def monitor_positions(exchange: ccxt.Exchange) -> None:
    """Monitor and manage open positions."""
    try:
        positions = exchange.fetch_positions([CONFIG['symbol']])
        for position in positions:
            if float(position['contracts']) > 0:
                # Check if we need to adjust stop loss
                current_price = float(position['markPrice'])
                entry_price = float(position['entryPrice'])
                side = position['side']

                # Calculate current profit
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                if side == 'short':
                    profit_pct = -profit_pct

                # Adjust stop loss if in profit
                if profit_pct > CONFIG['initial_profit_for_trailing_stop']:
                    new_sl = calculate_dynamic_stop_loss(None, side, current_price)
                    manage_position_risk(exchange, position, new_sl)

                # Log position status
                logging.info(f"Position {side} - Entry: {entry_price}, Current: {current_price}, Profit: {profit_pct}%")

    except Exception as e:
        logging.error(f"Error monitoring positions: {e}")

def emergency_stop(performance: PerformanceMetrics) -> bool:
    """Check if emergency stop conditions are met."""
    try:
        # Check daily loss limit
        if performance.daily_loss_percentage() >= CONFIG['max_daily_loss_percent']:
            logging.warning(f"Daily loss limit reached: {performance.daily_loss_percentage()}%")
            send_telegram_notification("🚨 Emergency Stop: Daily loss limit reached")
            return True

        # Check drawdown limit
        if performance.max_drawdown() >= CONFIG['max_drawdown_percent']:
            logging.warning(f"Max drawdown limit reached: {performance.max_drawdown()}%")
            send_telegram_notification("🚨 Emergency Stop: Max drawdown limit reached")
            return True

        # Check consecutive losses
        if performance.consecutive_losses >= 3:
            logging.warning("Emergency Stop: Too many consecutive losses")
            send_telegram_notification("🚨 Emergency Stop: Too many consecutive losses")
            return True

        return False

    except Exception as e:
        logging.error(f"Error in emergency stop check: {e}")
        return True

def main(performance: PerformanceMetrics) -> None:
    try:
        # Initialize exchange
        exchange = initialize_exchange()
        if not exchange:
            raise Exception("Failed to initialize exchange")

        # Initialize system monitor
        system_monitor = SystemMonitor(exchange, CONFIG)

        # Send startup notification
        send_telegram_notification("🟢 Trading bot started")

        # Validate configuration
        if not validate_config():
            raise Exception("Invalid configuration")

        # Check system health
        system_health = check_system_health()
        if not system_health['overall_healthy']:
            logging.warning("System health issues detected")
            system_monitor.send_notification("⚠️ System health issues detected")

        # Set leverage
        if not set_leverage(exchange):
            raise Exception("Failed to set leverage")

        # Check exchange health
        if not system_monitor.check_exchange_health():
            raise Exception("Exchange health check failed")

        # Main trading loop
        while True:
            try:
                # Fetch market data
                df = fetch_ohlcv(exchange, CONFIG['symbol'])
                df = calculate_indicators(df)

                # Update market data
                market_data = update_market_data(df)

                # Check market conditions
                market_conditions = check_market_conditions(df)
                trend_strength = check_trend_strength(df)

                # Log market conditions
                log_market_conditions(df, market_conditions, market_data)

                # Check if we can trade
                if not performance.can_trade():
                    logging.info("Trading limits reached, skipping trade")
                    time.sleep(60)
                    continue

                # Check if we're in excluded hours
                current_hour = datetime.utcnow().hour
                if current_hour in CONFIG['excluded_hours']:
                    logging.info(f"Current hour {current_hour} is excluded from trading")
                    time.sleep(300)  # Sleep for 5 minutes
                    continue

                # Check funding rate
                funding_info = check_funding_rate(exchange)
                if funding_info['should_wait']:
                    logging.info("Unfavorable funding rate, waiting...")
                    time.sleep(60)
                    continue

                # Analyze market depth
                depth_analysis = analyze_market_depth(exchange, CONFIG['symbol'], 'buy')

                # Determine trading decision based on conditions
                if market_conditions['trend'] == 'up' and trend_strength['trend_strength'] > 25:
                    # Calculate position size
                    balance = exchange.fetch_balance()['total']['USDT']
                    position_size = calculate_position_size(
                        balance,
                        market_data['current_price'],
                        calculate_dynamic_stop_loss(df, 'buy', market_data['current_price']),
                        exchange,
                        df['volatility'].iloc[-1]
                    )

                    # Validate position size
                    min_order_size = calculate_min_order_size(exchange, CONFIG['symbol'], market_data['current_price'])
                    is_valid, validation_message = validate_position_size(position_size, market_data['current_price'], balance, min_order_size)

                    if not is_valid:
                        logging.warning(f"Invalid position size: {validation_message}")
                        continue

                    # Check existing position
                    existing_position = check_existing_position(exchange, 'buy')
                    if existing_position['exists']:
                        logging.info("Position already exists, skipping trade")
                        continue

                    # Place orders
                    stop_loss_price = calculate_dynamic_stop_loss(df, 'buy', market_data['current_price'])
                    take_profit_price = market_data['current_price'] * (1 + CONFIG['tp1_target'])

                    orders = place_order_with_sl_tp(
                        exchange,
                        'buy',
                        position_size,
                        market_data['current_price'],
                        stop_loss_price,
                        take_profit_price
                    )

                    if orders['success']:
                        send_telegram_notification(
                            f"🟢 New LONG position opened\n"
                            f"Price: {market_data['current_price']}\n"
                            f"Size: {position_size}\n"
                            f"SL: {stop_loss_price}\n"
                            f"TP: {take_profit_price}"
                        )

                    # Update performance metrics
                    performance.update_trade(0, False)  # Initial trade entry

                # Monitor existing positions
                monitor_positions(exchange)

                # Cleanup old orders
                cleanup_old_orders(exchange)

                # Emergency stop check
                if emergency_stop(performance):
                    logging.warning("Emergency stop triggered")
                    break

                time.sleep(60)  # Wait for 1 minute before next iteration

            except Exception as e:
                logging.error(f"Error in trading loop: {e}")
                success, message = handle_exchange_error(e)
                if not success:
                    raise Exception(f"Unrecoverable error: {message}")
                time.sleep(60)

    except Exception as e:
        logging.error(f"Critical error: {e}")
        send_telegram_notification(f"🔴 Bot stopped due to critical error: {e}")
        raise

if __name__ == '__main__':
    consecutive_errors = 0
    last_performance_analysis = datetime.now()
    performance = PerformanceMetrics()

    while True:
        try:
            main(performance)
            consecutive_errors = 0  # Reset error count on successful run
        except Exception as e:
            consecutive_errors += 1
            logging.error(f"Bot error (attempt {consecutive_errors}): {e}")

            if consecutive_errors >= 3:
                send_telegram_notification(
                    f"🔴 Bot stopped after {consecutive_errors} consecutive errors\n"
                    f"Last error: {str(e)}"
                )
                break

            # Wait before retrying, with exponential backoff
            wait_time = min(300 * (2 ** (consecutive_errors - 1)), 3600)  # Max 1 hour
            logging.info(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
