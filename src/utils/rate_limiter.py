"""
Rate limiter and circuit breaker implementation
"""
import time
import logging
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Deque, Dict, Any

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests: Deque[float] = deque()

    def can_proceed(self) -> bool:
        now = time.time()

        # Remove old requests
        while self.requests and now - self.requests[0] >= self.time_window:
            self.requests.popleft()

        # Check if we can make a new request
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False

    def wait_if_needed(self):
        while not self.can_proceed():
            time.sleep(0.1)
        return True

class CircuitBreaker:
    def __init__(self, error_threshold: int, timeout: int):
        self.error_threshold = error_threshold
        self.timeout = timeout
        self.errors = 0
        self.last_error_time = None
        self.is_open = False

    def record_error(self):
        now = datetime.now()

        # Reset if we're past the timeout
        if self.last_error_time and (now - self.last_error_time).total_seconds() > self.timeout:
            self.errors = 0
            self.is_open = False

        self.errors += 1
        self.last_error_time = now

        if self.errors >= self.error_threshold:
            self.is_open = True

    def record_success(self):
        self.errors = 0
        self.is_open = False

    def can_proceed(self) -> bool:
        if not self.is_open:
            return True

        # Check if we can retry
        if self.last_error_time and \
           (datetime.now() - self.last_error_time).total_seconds() > self.timeout:
            self.is_open = False
            self.errors = 0
            return True

        return False

class APIRateManager:
    def __init__(self, config: Dict[str, Any]):
        # Rate limiters
        self.minute_limiter = RateLimiter(
            config['max_requests_per_minute'],
            60
        )
        self.order_limiter = RateLimiter(
            config['max_orders_per_second'],
            1
        )

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            config['error_threshold'],
            config['circuit_timeout']
        )

        # Backoff settings
        self.initial_backoff = config['initial_backoff']
        self.max_backoff = config['max_backoff']
        self.backoff_factor = config['backoff_factor']
        self.current_backoff = self.initial_backoff

    def reset_backoff(self):
        self.current_backoff = self.initial_backoff

    def increase_backoff(self):
        self.current_backoff = min(
            self.current_backoff * self.backoff_factor,
            self.max_backoff
        )

    def wait_backoff(self):
        if self.current_backoff > self.initial_backoff:
            logger.warning(f"Backing off for {self.current_backoff} seconds")
            time.sleep(self.current_backoff)

def rate_limited_api(is_order: bool = False):
    """Decorator for rate-limited API calls"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            from config.settings import SYSTEM_CONFIG, TELEGRAM_CONFIG
            from src.utils import send_telegram_message

            # Get rate manager instance
            if not hasattr(self, '_rate_manager'):
                self._rate_manager = APIRateManager(SYSTEM_CONFIG)

            manager = self._rate_manager

            # Check circuit breaker
            if not manager.circuit_breaker.can_proceed():
                msg = "Circuit breaker is open, waiting for timeout"
                logger.error(msg)
                if TELEGRAM_CONFIG['enabled']:
                    send_telegram_message(f"🔴 {msg}")
                time.sleep(1)
                return None

            # Apply rate limiting
            manager.minute_limiter.wait_if_needed()
            if is_order:
                manager.order_limiter.wait_if_needed()

            # Try the API call with backoff
            for attempt in range(SYSTEM_CONFIG['max_api_retries']):
                try:
                    result = func(self, *args, **kwargs)

                    # Success! Reset circuit breaker and backoff
                    manager.circuit_breaker.record_success()
                    manager.reset_backoff()
                    return result

                except Exception as e:
                    logger.error(f"API call failed: {str(e)}")
                    manager.circuit_breaker.record_error()

                    if attempt < SYSTEM_CONFIG['max_api_retries'] - 1:
                        manager.increase_backoff()
                        manager.wait_backoff()
                    else:
                        if TELEGRAM_CONFIG['enabled']:
                            send_telegram_message(
                                f"🔴 API call failed after {attempt + 1} attempts: {str(e)}"
                            )
                        raise

            return None

        return wrapper
    return decorator
