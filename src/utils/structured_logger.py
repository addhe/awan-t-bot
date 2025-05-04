"""
Enhanced structured logging for better debugging and monitoring
"""
import logging
import json
import functools
import inspect
import traceback
import os
from datetime import datetime
from typing import Dict, Any, Optional, Union, Callable

class StructuredLogger:
    """
    Enhanced logger that provides structured logging for better debugging and monitoring
    """
    
    def __init__(self, name: str):
        """
        Initialize structured logger
        
        Args:
            name: Logger name (usually __name__)
        """
        self.logger = logging.getLogger(name)
        self.context = {}
        
    def with_context(self, **kwargs) -> 'StructuredLogger':
        """
        Return a new logger with additional context
        
        Args:
            **kwargs: Context key-value pairs
            
        Returns:
            New logger instance with merged context
        """
        new_logger = StructuredLogger(self.logger.name)
        new_logger.context = {**self.context, **kwargs}
        return new_logger
        
    def _format_message(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Format message with context and extra data"""
        if not extra and not self.context:
            return msg
            
        # Combine context and extra
        context_dict = {**self.context}
        if extra:
            context_dict.update(extra)
            
        # Format as JSON
        try:
            context_str = json.dumps(context_dict)
            return f"{msg} | {context_str}"
        except Exception:
            return f"{msg} | Context: {str(context_dict)}"
            
    def debug(self, msg: str, **kwargs):
        """Log debug message with structured context"""
        self.logger.debug(self._format_message(msg, kwargs))
        
    def info(self, msg: str, **kwargs):
        """Log info message with structured context"""
        self.logger.info(self._format_message(msg, kwargs))
        
    def warning(self, msg: str, **kwargs):
        """Log warning message with structured context"""
        self.logger.warning(self._format_message(msg, kwargs))
        
    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """Log error message with structured context"""
        if exc_info:
            kwargs['traceback'] = traceback.format_exc()
        self.logger.error(self._format_message(msg, kwargs))
        
    def critical(self, msg: str, exc_info: bool = False, **kwargs):
        """Log critical message with structured context"""
        if exc_info:
            kwargs['traceback'] = traceback.format_exc()
        self.logger.critical(self._format_message(msg, kwargs))
        
    def exception(self, msg: str, **kwargs):
        """Log exception message with structured context"""
        kwargs['traceback'] = traceback.format_exc()
        self.logger.exception(self._format_message(msg, kwargs))

def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)

def log_call(level: str = 'DEBUG'):
    """
    Decorator to log function calls with args and results
    
    Args:
        level: Logging level to use
    """
    def decorator(func):
        logger = get_logger(func.__module__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Log function call
            fn_name = func.__name__
            arg_values = inspect.getcallargs(func, *args, **kwargs)
            
            # Remove 'self' from logged arguments
            if 'self' in arg_values:
                del arg_values['self']
                
            # Log call
            getattr(logger, level.lower())(
                f"Calling {fn_name}",
                function=fn_name,
                arguments=str(arg_values)
            )
            
            # Call function
            try:
                result = func(*args, **kwargs)
                # Log result (only for non-large return values)
                if isinstance(result, (int, float, bool, str)) or result is None:
                    getattr(logger, level.lower())(
                        f"{fn_name} returned",
                        function=fn_name,
                        result=str(result)
                    )
                else:
                    getattr(logger, level.lower())(
                        f"{fn_name} returned",
                        function=fn_name,
                        result_type=type(result).__name__
                    )
                return result
            except Exception as e:
                logger.error(
                    f"{fn_name} raised exception",
                    exc_info=True,
                    function=fn_name,
                    exception=str(e)
                )
                raise
                
        return wrapper
    return decorator
