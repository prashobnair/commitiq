# backend/app/config.py
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import sys

# Load environment variables from the root directory .env file
root_dir = Path(__file__).resolve().parent.parent.parent
dotenv_path = os.path.join(root_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Debug mode - set to True for development, False for production
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'  # Set to true for debugging

# Set default logging level
DEFAULT_LOG_LEVEL = logging.INFO  # Set default to INFO for less verbose output

# Configure logging
def configure_logging():
    """Configure logging for the application."""
    log_level = os.getenv('LOG_LEVEL', 'INFO')  # Default to INFO
    numeric_level = getattr(logging, log_level.upper(), DEFAULT_LOG_LEVEL)
    
    # Configure root logger with more details
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(__file__), '../logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Set up file handlers
    debug_file = os.path.join(logs_dir, 'debug.log')
    file_handler = logging.FileHandler(debug_file)
    file_handler.setLevel(logging.DEBUG)  # Keep DEBUG level for file logs
    file_handler.setFormatter(log_format)
    
    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Set to INFO for console output
    console_handler.setFormatter(log_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear any existing handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set more specific logger levels
    logging.getLogger('app').setLevel(logging.INFO)
    logging.getLogger('app.api').setLevel(logging.INFO)
    logging.getLogger('app.utils').setLevel(logging.INFO)
    logging.getLogger('app.api.analysis_tracking').setLevel(logging.INFO)
    
    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return numeric_level

# Application configuration
APP_CONFIG = {
    'DEBUG': DEBUG,
    'SECRET_KEY': os.getenv('SECRET_KEY', 'dev_key_not_for_production'),
    'API_VERSION': 'v1',
    'API_PREFIX': '/api',
}

class Config:
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    # Add other configuration variables as needed