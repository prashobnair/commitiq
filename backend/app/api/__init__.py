# backend/app/api/__init__.py
from flask import Blueprint, jsonify

# Import the individual blueprints
from .analysis import analysis_bp  # Import the analysis blueprint
from .waitlist import waitlist_bp  # Import the waitlist blueprint

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