import logging
import psutil
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime


def check_system_health() -> Dict[str, Any]:
    """
    Check overall system health including CPU, memory, and disk usage.

    Returns:
        Dict containing health check results
    """
    try:
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Check memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Check disk usage
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent

        # Define thresholds
        cpu_threshold = 80
        memory_threshold = 85
        disk_threshold = 90

        # Check if any metric exceeds threshold
        cpu_healthy = cpu_percent < cpu_threshold
        memory_healthy = memory_percent < memory_threshold
        disk_healthy = disk_percent < disk_threshold

        # Overall health status
        overall_healthy = all([cpu_healthy, memory_healthy, disk_healthy])

        return {
            "overall_healthy": overall_healthy,
            "cpu": {"usage_percent": cpu_percent, "healthy": cpu_healthy},
            "memory": {
                "usage_percent": memory_percent,
                "healthy": memory_healthy,
            },
            "disk": {"usage_percent": disk_percent, "healthy": disk_healthy},
        }

    except Exception as e:
        logging.error(f"Error checking system health: {e}")
        return {"overall_healthy": False, "error": str(e)}


def recover_from_error(
    exchange: Optional[Any], error: Exception
) -> tuple[bool, str]:
    """
    Attempt to recover from common errors.

    Args:
        exchange: Exchange instance (optional)
        error: The error to recover from

    Returns:
        Tuple of (success, message)
    """
    try:
        error_str = str(error).lower()

        # Handle rate limit errors
        if "rate limit" in error_str:
            logging.warning("Rate limit hit, waiting 60 seconds")
            return True, "Rate limit error - waiting"

        # Handle network errors
        elif any(x in error_str for x in ["network", "timeout", "connection"]):
            logging.warning("Network error detected, will retry")
            return True, "Network error - will retry"

        # Handle exchange maintenance
        elif "maintenance" in error_str:
            logging.warning("Exchange maintenance, waiting 5 minutes")
            return True, "Exchange maintenance - waiting"

        # Handle insufficient funds
        elif "insufficient" in error_str:
            logging.error("Insufficient funds")
            return False, "Insufficient funds - cannot continue"

        # Handle invalid API keys
        elif "key" in error_str and (
            "invalid" in error_str or "expired" in error_str
        ):
            logging.error("Invalid API credentials")
            return False, "Invalid API credentials - cannot continue"

        # Unknown errors
        else:
            logging.error(f"Unknown error: {error}")
            return False, f"Unknown error - {str(error)}"

    except Exception as e:
        logging.error(f"Error in recovery function: {e}")
        return False, f"Recovery error - {str(e)}"


def handle_exchange_error(error: Exception) -> tuple[bool, str]:
    """
    Handle exchange-specific errors.

    Args:
        error: The error to handle

    Returns:
        Tuple of (success, message)
    """
    try:
        error_str = str(error).lower()

        # Handle order errors
        if "order" in error_str:
            if "not found" in error_str:
                return True, "Order not found - will retry"
            elif "canceled" in error_str:
                return True, "Order was canceled - will retry"
            else:
                return False, f"Order error - {error}"

        # Handle position errors
        elif "position" in error_str:
            if "not found" in error_str:
                return True, "Position not found - will retry"
            else:
                return False, f"Position error - {error}"

        # Handle balance errors
        elif "balance" in error_str:
            return False, f"Balance error - {error}"

        # Other exchange errors
        else:
            return True, "Exchange error - will retry"

    except Exception as e:
        logging.error(f"Error handling exchange error: {e}")
        return False, f"Error handler failed - {str(e)}"


def log_market_conditions(
    df: pd.DataFrame, conditions: Dict[str, Any], market_data: Dict[str, Any]
) -> None:
    """
    Log current market conditions and indicators.

    Args:
        df: DataFrame with market data
        conditions: Dictionary of market conditions
        market_data: Dictionary of current market data
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logging.info(
            f"""
Market Update [{current_time}]
Price: {market_data['current_price']:.2f}
Trend: {conditions['trend']}
RSI: {df['rsi'].iloc[-1]:.2f}
Volatility: {df['volatility'].iloc[-1]:.4f}
Volume: {df['volume'].iloc[-1]:.2f}
MACD: {df['macd'].iloc[-1]:.4f}
Signal: {df['macd_signal'].iloc[-1]:.4f}
        """.strip()
        )

    except Exception as e:
        logging.error(f"Error logging market conditions: {e}")
