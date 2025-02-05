import logging
import psutil
from typing import Dict, Any, Tuple
import time

def check_system_health() -> Dict[str, Any]:
    try:
        # Check disk space
        disk_usage = psutil.disk_usage('/')
        disk_warning = disk_usage.percent > 90

        # Check memory usage
        memory = psutil.virtual_memory()
        memory_warning = memory.percent > 90

        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_warning = cpu_percent > 90

        health_status = {
            'disk': {
                'usage_percent': disk_usage.percent,
                'warning': disk_warning
            },
            'memory': {
                'usage_percent': memory.percent,
                'warning': memory_warning
            },
            'cpu': {
                'usage_percent': cpu_percent,
                'warning': cpu_warning
            },
            'overall_healthy': not (disk_warning or memory_warning or cpu_warning)
        }

        if not health_status['overall_healthy']:
            logging.warning(f"System health issues detected: {health_status}")

        return health_status
    except Exception as e:
        logging.error(f"Error checking system health: {e}")
        return {
            'error': str(e),
            'overall_healthy': False
        }

def recover_from_error(exchange: Any, error: Exception) -> Tuple[bool, str]:
    try:
        error_type = type(error).__name__
        error_message = str(error)

        # Handle rate limit errors
        if 'rate limit' in error_message.lower():
            time.sleep(60)  # Wait for 1 minute
            return True, "Rate limit error recovered after waiting"

        # Handle connection errors
        if isinstance(error, (ConnectionError, TimeoutError)):
            time.sleep(5)  # Wait for 5 seconds
            return True, "Connection error recovered after waiting"

        # Handle authentication errors
        if 'authentication' in error_message.lower():
            # Attempt to reconnect
            exchange.close()
            time.sleep(1)
            exchange.load_markets()
            return True, "Authentication error recovered after reconnecting"

        # Handle insufficient funds
        if 'insufficient' in error_message.lower():
            return False, "Insufficient funds error - manual intervention required"

        # Handle unknown errors
        logging.error(f"Unhandled error: {error_type} - {error_message}")
        return False, f"Unhandled error: {error_type}"

    except Exception as e:
        logging.error(f"Error in recovery process: {e}")
        return False, f"Recovery process failed: {str(e)}"

def handle_exchange_error(e: Exception, retry_count: int = 0) -> Tuple[bool, str]:
    try:
        max_retries = 3
        error_message = str(e).lower()

        # Define retry delays based on error type
        retry_delays = {
            'rate limit': 60,
            'network': 5,
            'timeout': 5,
            'connection': 10
        }

        # Find matching error type
        delay = next((delay for error_type, delay in retry_delays.items()
                     if error_type in error_message), None)

        if delay and retry_count < max_retries:
            time.sleep(delay)
            return True, f"Retrying after {delay}s delay (attempt {retry_count + 1}/{max_retries})"

        return False, "Max retries exceeded or non-retriable error"

    except Exception as recovery_error:
        logging.error(f"Error in error handling: {recovery_error}")
        return False, f"Error handling failed: {str(recovery_error)}"

def log_market_conditions(df: Dict[str, Any], market_health: Dict[str, Any],
                         market_data: Dict[str, Any]) -> None:
    try:
        conditions = {
            'price': df['close'].iloc[-1],
            'volume': df['volume'].iloc[-1],
            'volatility': df['volatility'].iloc[-1],
            'market_health': market_health,
            'timestamp': time.time()
        }

        conditions.update(market_data)

        logging.info(f"Market Conditions: {conditions}")

    except Exception as e:
        logging.error(f"Error logging market conditions: {e}")
        raise
