# backend/app/api/__init__.py
from flask import Blueprint, jsonify

# Import the individual blueprints
from .analysis import analysis_bp  # Import the analysis blueprint
from .waitlist import waitlist_bp  # Import the waitlist blueprint
from .analysis_tracking import analysis_tracking_bp  # Import the analysis tracking blueprint
from .analysis_tracking_dashboard import tracking_dashboard_bp  # Import the tracking dashboard blueprint
from .share import share_bp  # Import the share blueprint
from .download import download_bp  # Import the download blueprint

# Create a master blueprint (optional, but good for organization)
api_bp = Blueprint('api', __name__)

# Add health check endpoint
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'message': 'API is up and running'
    })

# Register the individual blueprints with the master blueprint
api_bp.register_blueprint(analysis_bp)
api_bp.register_blueprint(waitlist_bp, url_prefix='/waitlist')
api_bp.register_blueprint(analysis_tracking_bp, url_prefix='/tracking')
api_bp.register_blueprint(tracking_dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(share_bp, url_prefix='/share')  # Register the share blueprint
api_bp.register_blueprint(download_bp, url_prefix='/download')  # Register the download blueprint