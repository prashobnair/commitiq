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
from .models import db  # Import the SQLAlchemy db instance
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
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    if test_config:
        # Override with test config if provided
        app.config.from_mapping(test_config)
        
    # Initialize database
    db.init_app(app)
    
    # Register CLI commands
    register_commands(app)
    
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

def get_database_uri():
    """
    Construct database URI from environment variables.
    Fallback to SQLite for local development if PostgreSQL settings not available.
    """
    db_host = os.environ.get("DB_HOST")
    db_port = os.environ.get("DB_PORT")
    db_name = os.environ.get("DB_NAME")
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    
    # If PostgreSQL environment variables are set, use PostgreSQL
    if db_host and db_port and db_name and db_user and db_password:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Otherwise, fall back to SQLite for local development/testing
    app_root = os.path.dirname(os.path.abspath(__file__))
    instance_path = os.path.join(app_root, '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    logger.warning("PostgreSQL configuration not found. Using SQLite for local development.")
    return f"sqlite:///{os.path.join(instance_path, 'commitiq.sqlite')}"

def register_commands(app):
    """Register CLI commands with the application."""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Clear existing data and create new tables."""
        logger.info("Initializing database...")
        with app.app_context():
            db.create_all()
        logger.info("Database initialized successfully.")
    
    @app.cli.command('seed-db')
    def seed_db_command():
        """Seed the database with sample data."""
        logger.info("Seeding database with sample data...")
        # Add seeding logic here if needed
        logger.info("Database seeded successfully.")