# backend/app/config.py
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Debug mode - set to True for development, False for production
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

# Set default logging level
DEFAULT_LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

# Configure logging
def configure_logging():
    """Configure logging for the application."""
    log_level = os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
    numeric_level = getattr(logging, log_level.upper(), DEFAULT_LOG_LEVEL)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Set more specific logger levels if needed
    logging.getLogger('app.api.analysis_tracking').setLevel(logging.DEBUG)  # Always debug for tracking
    
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