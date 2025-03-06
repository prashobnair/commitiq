# backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
from .config import Config
from .api import api_bp  # Import api_bp instead of github_bp
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
# from asgiref.wsgi import WsgiToAsgi  # Comment out for now

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

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Setup logging first, before anything else
    logger = setup_logging(app)
    
    CORS(app)  # Enable CORS for all routes
    
    # Load environment variables
    load_dotenv()
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')  # Register api_bp
    
    # Return the Flask app directly
    return app
    
    # Comment out ASGI conversion for now
    # asgi_app = WsgiToAsgi(app)
    # return asgi_app