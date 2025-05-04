"""
Error handling decorators and utilities for standardized error management
"""
import logging
import functools
import traceback
from typing import Callable, Any, Optional, Dict, Union
import ccxt
import asyncio

from config.settings import TELEGRAM_CONFIG
from src.utils.telegram_utils import send_telegram_message

logger = logging.getLogger(__name__)

class ExchangeError(Exception):
    """Base exception for all exchange-related errors"""
    def __init__(self, message: str, original_error: Optional[Exception] = None, details: Dict[str, Any] = None):
        self.message = message
        self.original_error = original_error
        self.details = details or {}
        super().__init__(self.message)
        
    def __str__(self):
        if self.original_error:
            return f"{self.message} (Original error: {str(self.original_error)})"
        return self.message

class NetworkError(ExchangeError):
    """Raised when network issues prevent communication with exchange"""
    pass

class OrderError(ExchangeError):
    """Raised when there's an issue with order placement or execution"""
    pass

class AccountError(ExchangeError):
    """Raised when there's an issue with account operations (balance, permissions)"""
    pass

class StrategyError(Exception):
    """Base exception for all strategy-related errors"""
    pass

def handle_exchange_errors(notify: bool = True):
    """
    Decorator for handling exchange-related errors in a consistent way
    
    Args:
        notify: Whether to send Telegram notification for errors
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ccxt.NetworkError as e:
                error_msg = f"Network error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🔴 {error_msg}")
                raise NetworkError(error_msg, e, {"function": func.__name__})
            except ccxt.ExchangeError as e:
                error_msg = f"Exchange error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🔴 {error_msg}")
                raise ExchangeError(error_msg, e, {"function": func.__name__})
            except ccxt.InvalidOrder as e:
                error_msg = f"Invalid order in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🔴 {error_msg}")
                raise OrderError(error_msg, e, {"function": func.__name__})
            except Exception as e:
                error_msg = f"Unexpected error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                if notify and TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🔴 {error_msg}")
                raise
                
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ccxt.NetworkError as e:
                error_msg = f"Network error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled'] and asyncio.get_event_loop().is_running():
                    asyncio.create_task(send_telegram_message(f"🔴 {error_msg}"))
                raise NetworkError(error_msg, e, {"function": func.__name__})
            except ccxt.ExchangeError as e:
                error_msg = f"Exchange error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled'] and asyncio.get_event_loop().is_running():
                    asyncio.create_task(send_telegram_message(f"🔴 {error_msg}"))
                raise ExchangeError(error_msg, e, {"function": func.__name__})
            except ccxt.InvalidOrder as e:
                error_msg = f"Invalid order in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                if notify and TELEGRAM_CONFIG['enabled'] and asyncio.get_event_loop().is_running():
                    asyncio.create_task(send_telegram_message(f"🔴 {error_msg}"))
                raise OrderError(error_msg, e, {"function": func.__name__})
            except Exception as e:
                error_msg = f"Unexpected error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                if notify and TELEGRAM_CONFIG['enabled'] and asyncio.get_event_loop().is_running():
                    asyncio.create_task(send_telegram_message(f"🔴 {error_msg}"))
                raise
        
        # Return appropriate wrapper based on whether the decorated function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

def handle_strategy_errors(notify: bool = False):
    """
    Decorator for handling strategy-related errors in a consistent way
    
    Args:
        notify: Whether to send Telegram notification for errors
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Strategy error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                if notify and TELEGRAM_CONFIG['enabled']:
                    await send_telegram_message(f"🟠 {error_msg}")
                raise StrategyError(error_msg)
                
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Strategy error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                if notify and TELEGRAM_CONFIG['enabled'] and asyncio.get_event_loop().is_running():
                    asyncio.create_task(send_telegram_message(f"🟠 {error_msg}"))
                raise StrategyError(error_msg)
        
        # Return appropriate wrapper based on whether the decorated function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

def retry_with_backoff(max_retries: int = 3, initial_backoff: float = 1.0, backoff_factor: float = 2.0, 
                      exceptions_to_retry=(NetworkError, ConnectionError)):
    """
    Decorator that retries a function with exponential backoff on specified exceptions
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        backoff_factor: Factor to increase backoff time with each retry
        exceptions_to_retry: Tuple of exceptions that should trigger a retry
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions_to_retry as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(f"Retrying {func.__name__} after {backoff}s (attempt {retries}/{max_retries})")
                    await asyncio.sleep(backoff)
                    backoff *= backoff_factor
                    
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions_to_retry as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    logger.warning(f"Retrying {func.__name__} after {backoff}s (attempt {retries}/{max_retries})")
                    time.sleep(backoff)
                    backoff *= backoff_factor
        
        # Return appropriate wrapper based on whether the decorated function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
