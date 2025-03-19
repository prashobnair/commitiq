# backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
from .config import Config, configure_logging, APP_CONFIG
from .api import api_bp  # Import api_bp instead of github_bp
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
# from asgiref.wsgi import WsgiToAsgi  # Comment out for now

# Configure logging
log_level = configure_logging()
logger = logging.getLogger(__name__)

def setup_logging(app):
    """
    Configure comprehensive logging for the application.
    Sets up both console and file logging with appropriate formatting.
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(app.root_path, '..', 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Check if we're in Flask debug mode to avoid duplicate logs
    # When Flask runs in debug mode, it loads the app twice
    is_werkzeug_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    
    # Only set up handlers if we're in the main process or not in debug mode
    if not app.debug or is_werkzeug_reloader:
        # Log format with timestamps, logger name, and log level
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler - outputs to stderr for better compatibility with Flask
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_format)
        root_logger.addHandler(console_handler)
        
        # File handler - rotating log file with max size of 10MB, keeping 5 backups
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'commitiq.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)  # More detailed logs in the file
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
        
        # Set higher log levels for noisy third-party libraries
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Log application startup
    app_logger = logging.getLogger('app')
    
    # Only log startup messages when handlers are set up
    if not app.debug or is_werkzeug_reloader:
        app_logger.info(f"CommitIQ application starting at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        app_logger.info(f"Log files are located in: {logs_dir}")
    
    return app_logger

def create_app(test_config=None):
    """Create and configure the Flask application."""
    # Create the Flask app instance
    app = Flask(__name__, instance_relative_config=True)
    
    # Apply configuration
    app.config.from_mapping(**APP_CONFIG)
    
    if test_config:
        # Override with test config if provided
        app.config.from_mapping(test_config)
        
    # Set up CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Log application startup
    logger.info(f"CommitIQ application starting at {app.config.get('START_TIME', 'unknown time')}")
    logger.info(f"Log level set to {logging.getLevelName(log_level)}")
    
    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    logger.info(f"Instance path: {app.instance_path}")
    
    # Make sure log directory exists
    log_dir = os.path.join(os.path.dirname(__file__), '../logs')
    os.makedirs(log_dir, exist_ok=True)
    logger.info(f"Log files are located in: {os.path.abspath(log_dir)}")
    
    # Add a health check route
    @app.route('/health')
    def health_check():
        return {"status": "healthy"}
    
    return app
    
    # Comment out ASGI conversion for now
    # asgi_app = WsgiToAsgi(app)
    # return asgi_app