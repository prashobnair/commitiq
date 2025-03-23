#!/usr/bin/env python
"""
Test script for logging configuration in different environments.

This script demonstrates how the application's logging behavior changes
when FLASK_ENV is set to 'production' vs. other environments.

Usage:
    # Test in development mode
    python test_logging.py
    
    # Test in production mode
    FLASK_ENV=production python test_logging.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up the Python path to include the backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import Flask app and logging configuration
from app import create_app
from app.utils.logger_config import test_logging_behavior

def main():
    """Main function to test logging configuration."""
    # Get current environment
    environment = os.environ.get('FLASK_ENV', 'development')
    
    print("=" * 80)
    print(f"TESTING LOGGING IN {environment.upper()} ENVIRONMENT")
    print("=" * 80)
    
    # Create Flask app with the current environment
    app = create_app()
    
    # Check if console logging is enabled or disabled
    is_production = environment == 'production'
    if is_production:
        print("In PRODUCTION mode - console logs should be DISABLED")
        print("Log messages should only appear in log files, not in console")
    else:
        print(f"In {environment.upper()} mode - console logs should be ENABLED")
        print("Log messages should appear in both console and log files")
    
    print("\nRunning logging test...\n")
    
    # Create an application context to ensure everything works properly
    with app.app_context():
        # Test with application logger
        app.logger.debug("App Debug message (via app.logger)")
        app.logger.info("App Info message (via app.logger)")
        app.logger.warning("App Warning message (via app.logger)")
        app.logger.error("App Error message (via app.logger)")
        
        # Test with root logger
        root_logger = logging.getLogger()
        root_logger.debug("Debug message (via root logger)")
        root_logger.info("Info message (via root logger)")
        root_logger.warning("Warning message (via root logger)")
        root_logger.error("Error message (via root logger)")
        
        # Run the comprehensive test from logger_config
        test_logging_behavior()
    
    print("\nTest completed. Check log files to verify correct behavior.")
    print("=" * 80)

if __name__ == "__main__":
    main() 