# backend/app/api/__init__.py
from flask import Blueprint

# Import the individual blueprints
from .github import github_bp
from .analysis import analysis_bp  # Import the new blueprint

# Create a master blueprint (optional, but good for organization)
api_bp = Blueprint('api', __name__)

# Register the individual blueprints with the master blueprint
api_bp.register_blueprint(github_bp, url_prefix='/github')
api_bp.register_blueprint(analysis_bp)