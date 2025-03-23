"""
Production-aware logging configuration for CommitIQ.

This module configures logging behavior based on the current environment:
- In production: Console logs are suppressed and important messages are redirected to files and services
- In development/other environments: Console logging works normally

Usage:
    from app.utils.logger_config import configure_app_logging
    configure_app_logging(app)
"""

import os
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from logging.config import dictConfig
from functools import wraps
import traceback

# Optional imports for external logging services
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

class LoggerManager:
    """Centralized logging management for the application."""
    
    def __init__(self):
        self.environment = os.environ.get('FLASK_ENV', 'development')
        self.is_production = self.environment == 'production'
        self.log_level = self._get_log_level()
        self.configured = False
    
    def _get_log_level(self):
        """Get the log level from environment variables or use a default."""
        log_level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
        return getattr(logging, log_level_name, logging.INFO)
    
    def get_logging_config(self):
        """Generate logging configuration based on environment."""
        # Define base logging configuration
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'detailed': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'detailed',
                    'filename': self._get_log_file_path('app.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 10,
                },
                'error_file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'ERROR',
                    'formatter': 'detailed',
                    'filename': self._get_log_file_path('error.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 10,
                }
            },
            'loggers': {
                '': {  # Root logger
                    'handlers': ['file', 'error_file'],
                    'level': self._get_log_level(),
                    'propagate': True
                },
                'werkzeug': {
                    'level': 'WARNING',
                    'propagate': True
                },
                'urllib3': {
                    'level': 'WARNING',
                    'propagate': True
                },
                'requests': {
                    'level': 'WARNING',
                    'propagate': True
                }
            }
        }
        
        # Add console handler only for non-production environments
        if not self.is_production:
            logging_config['handlers']['console'] = {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            }
            logging_config['loggers']['']['handlers'].append('console')
            
        return logging_config
    
    def _get_log_file_path(self, filename):
        """Get the path to the log file, creating the directory if needed."""
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, filename)
    
    def configure(self):
        """Apply logging configuration based on environment."""
        if self.configured:
            return
            
        try:
            # Apply configuration
            config = self.get_logging_config()
            dictConfig(config)
            
            # Configure Sentry if available and in production
            if SENTRY_AVAILABLE and self.is_production and os.environ.get('SENTRY_DSN'):
                sentry_sdk.init(
                    dsn=os.environ.get('SENTRY_DSN'),
                    environment=self.environment,
                    traces_sample_rate=0.2
                )
            
            # Log environment info
            logger = logging.getLogger(__name__)
            
            if self.is_production:
                logger.info(f"Application running in PRODUCTION mode - console logs disabled")
            else:
                logger.info(f"Application running in {self.environment.upper()} mode - console logs enabled")
                
            self.configured = True
            
        except Exception as e:
            # Fallback logging in case configuration fails
            print(f"Error configuring logging: {str(e)}")
            traceback.print_exc()
            
            # Set up basic console logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def log_to_service(self, message, level='info', extra=None):
        """Log to external service in production, fallback to file in other environments."""
        logger = logging.getLogger('app.service')
        
        if extra is None:
            extra = {}
            
        # Map level string to logging method
        log_method = getattr(logger, level.lower(), logger.info)
        
        # Log the message
        log_method(message, extra=extra)
        
        # Additional logging to external service if in production
        if self.is_production and SENTRY_AVAILABLE:
            with sentry_sdk.push_scope() as scope:
                for key, value in extra.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_message(message, level=level.upper())


# Global logger manager instance
logger_manager = LoggerManager()

def configure_app_logging(app=None):
    """
    Configure application logging based on environment.
    
    Args:
        app (Flask, optional): Flask application instance
    """
    # Configure logging
    logger_manager.configure()
    
    # Update app config if provided
    if app:
        app.logger.handlers = []  # Remove default handlers
        app.logger.propagate = True  # Propagate to root logger
        
        # Make flask use the correct log level
        app.logger.setLevel(logger_manager.log_level)
        
    return logger_manager

def log_to_file(message, level='info', extra=None):
    """
    Log a message to file regardless of environment.
    
    Args:
        message (str): Log message
        level (str): Log level (debug, info, warning, error, critical)
        extra (dict): Extra information to include in the log
    """
    # Ensure logger is configured
    if not logger_manager.configured:
        logger_manager.configure()
    
    # Log the message
    logger = logging.getLogger('app.file')
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra)

def log_error(error, context=None):
    """
    Log an error to the appropriate location based on environment.
    
    Args:
        error (Exception): The error to log
        context (dict): Additional context for the error
    """
    # Ensure logger is configured
    if not logger_manager.configured:
        logger_manager.configure()
    
    # Format error with stack trace
    error_message = f"{str(error)}\n{traceback.format_exc()}"
    
    # Log error
    log_extra = {'context': context} if context else {}
    logger = logging.getLogger('app.error')
    logger.error(error_message, extra=log_extra)
    
    # In production, also log to service if available
    if logger_manager.is_production and SENTRY_AVAILABLE:
        logger_manager.log_to_service(str(error), level='error', extra=log_extra)

def with_error_logging(func):
    """
    Decorator to log exceptions in function calls.
    
    Args:
        func: The function to wrap with error logging
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_error(e, context={
                'function': func.__name__,
                'module': func.__module__,
                'args': str(args),
                'kwargs': str(kwargs)
            })
            raise
    return wrapper

def test_logging_behavior():
    """
    Test function to demonstrate environment-based logging behavior.
    
    This function logs messages at different levels and can be used to verify
    that logging behavior changes appropriately based on the FLASK_ENV setting.
    
    Example usage:
        # In development mode
        FLASK_ENV=development python -c "from app.utils.logger_config import test_logging_behavior; test_logging_behavior()"
        
        # In production mode
        FLASK_ENV=production python -c "from app.utils.logger_config import test_logging_behavior; test_logging_behavior()"
    """
    # Configure logging if not already done
    if not logger_manager.configured:
        logger_manager.configure()
    
    # Get a logger instance
    logger = logging.getLogger("test.logging")
    
    # Display environment information
    environment = os.environ.get('FLASK_ENV', 'development')
    print(f"Current environment: {environment}")
    print(f"Console logging is {'disabled' if environment == 'production' else 'enabled'}")
    print("The following log messages should be written to file (in both environments)")
    print("But console output should only appear in non-production environments:")
    
    # Log messages at different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Force an error for demonstration
    try:
        result = 1 / 0
    except Exception as e:
        log_error(e, context={"test": True})
        print("An error was logged to the appropriate destination based on environment")
    
    # Show log file paths
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    print(f"Log files are located in: {os.path.abspath(logs_dir)}")
    print(f"Check 'app.log' for regular logs and 'error.log' for error logs") 