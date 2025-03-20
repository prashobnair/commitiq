"""
Error tracking utility for CommitIQ application.

This module provides functions for consistent error logging throughout the application.
It ensures that all errors are logged with sufficient context for debugging and analysis.
"""

import logging
import traceback
import time
import inspect
import os
import sys
from functools import wraps

# Get logger for this module
logger = logging.getLogger(__name__)

class ErrorTracker:
    """Error tracking utility for CommitIQ application."""
    
    @staticmethod
    def log_error(error, context=None, user_info=None, module_name=None, log_traceback=True):
        """
        Log an error with consistent format and context.
        
        Args:
            error (Exception or str): The error to log
            context (dict, optional): Additional context data
            user_info (dict, optional): User information (username, email, IP)
            module_name (str, optional): Module where the error occurred
            log_traceback (bool): Whether to log traceback for exceptions
        """
        if module_name is None:
            # Try to automatically determine the calling module
            frame = inspect.currentframe().f_back
            module_name = frame.f_globals['__name__'] if frame else 'unknown'
            
        # Create logger for the specific module
        log = logging.getLogger(module_name)
        
        # Format the error message
        error_msg = str(error)
        
        # Add user info if available
        user_context = ""
        if user_info:
            if 'username' in user_info:
                user_context += f" - Username: {user_info['username']}"
            if 'email' in user_info:
                user_context += f" - Email: {user_info['email']}"
            if 'ip' in user_info:
                user_context += f" - IP: {user_info['ip']}"
        
        # Add context data if available
        context_str = ""
        if context:
            context_str = " - Context: " + ", ".join(f"{k}={v}" for k, v in context.items())
        
        # Log the error
        log.error(f"Error: {error_msg}{user_context}{context_str}")
        
        # Log traceback for exceptions if requested
        if log_traceback and isinstance(error, Exception):
            log.error("Traceback:\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__)))
    
    @staticmethod
    def track_errors(func=None, with_context=True, module_name=None):
        """
        Decorator to track errors in a function.
        
        Args:
            func (callable): The function to decorate
            with_context (bool): Whether to include function arguments in error context
            module_name (str, optional): Module name to use for logging
        
        Returns:
            callable: Decorated function with error tracking
        """
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    # Determine module name if not provided
                    mod_name = module_name or fn.__module__
                    
                    # Extract context from function arguments if requested
                    context = {}
                    if with_context:
                        # Extract non-self arguments
                        sig = inspect.signature(fn)
                        param_names = list(sig.parameters.keys())
                        
                        # Skip 'self' for class methods
                        if param_names and param_names[0] == 'self' and len(args) > 0:
                            param_values = dict(zip(param_names[1:], args[1:]))
                        else:
                            param_values = dict(zip(param_names, args))
                            
                        # Add keyword arguments
                        param_values.update(kwargs)
                        
                        # Clean sensitive data
                        for k in list(param_values.keys()):
                            if k in ['password', 'token', 'secret', 'key']:
                                param_values[k] = '[REDACTED]'
                        
                        context = {
                            'function': fn.__name__,
                            'args': str(param_values)
                        }
                    
                    # Extract user info if 'username' or 'user' is in kwargs
                    user_info = {}
                    for key, value in kwargs.items():
                        if key in ['username', 'user'] and isinstance(value, str):
                            user_info['username'] = value
                        elif key == 'email' and isinstance(value, str):
                            user_info['email'] = value
                        elif key == 'request' and hasattr(value, 'remote_addr'):
                            user_info['ip'] = value.remote_addr
                    
                    # Log the error
                    ErrorTracker.log_error(e, context, user_info, mod_name)
                    
                    # Re-raise the exception
                    raise
            
            return wrapper
        
        # Support both @track_errors and @track_errors()
        if func is None:
            return decorator
        return decorator(func)
    
    @staticmethod
    def handle_errors(default_return=None, log_as_exception=True, module_name=None):
        """
        Decorator to handle errors and return a default value instead of raising exceptions.
        
        Args:
            default_return: Value to return if an exception occurs
            log_as_exception (bool): Whether to log as exception or error
            module_name (str, optional): Module name to use for logging
        
        Returns:
            callable: Decorated function with error handling
        """
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    # Determine module name if not provided
                    mod_name = module_name or fn.__module__
                    
                    # Extract context from function arguments
                    context = {
                        'function': fn.__name__
                    }
                    
                    # Extract user info if available
                    user_info = {}
                    for key, value in kwargs.items():
                        if key in ['username', 'user'] and isinstance(value, str):
                            user_info['username'] = value
                        elif key == 'email' and isinstance(value, str):
                            user_info['email'] = value
                        elif key == 'request' and hasattr(value, 'remote_addr'):
                            user_info['ip'] = value.remote_addr
                    
                    # Log the error
                    if log_as_exception:
                        logger = logging.getLogger(mod_name)
                        logger.exception(f"Exception in {fn.__name__} - User: {user_info}")
                    else:
                        ErrorTracker.log_error(e, context, user_info, mod_name)
                    
                    # Return the default value
                    return default_return
            
            return wrapper
        
        return decorator

# Create a singleton instance
error_tracker = ErrorTracker()

# Export decorators as top-level functions for convenience
track_errors = error_tracker.track_errors
handle_errors = error_tracker.handle_errors
log_error = error_tracker.log_error 