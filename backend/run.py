# backend/run.py
from app import create_app
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure environment variables for development
if not os.environ.get('FLASK_ENV'):
    os.environ['FLASK_ENV'] = 'development'
    
# Create flask application
app = create_app()

# Setup logging for the main process
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Log application startup
    logger.info(f"Starting CommitIQ server on port {port}")
    
    # Run the application with optimized settings for development
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=port,
        debug=os.environ.get('FLASK_ENV') == 'development',
        use_reloader=os.environ.get('FLASK_ENV') == 'development',
        threaded=True  # Use threading for better concurrency
    )