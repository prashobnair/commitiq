# backend/app/api/__init__.py
from flask import Blueprint

# Import the individual blueprints
from .analysis import analysis_bp  # Import the analysis blueprint
from .waitlist import waitlist_bp  # Import the waitlist blueprint

# Create a master blueprint (optional, but good for organization)
api_bp = Blueprint('api', __name__)

# Register the individual blueprints with the master blueprint
api_bp.register_blueprint(analysis_bp)
api_bp.register_blueprint(waitlist_bp, url_prefix='/waitlist')