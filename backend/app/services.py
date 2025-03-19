"""
Legacy service module that redirects to new modular services.

This file is kept for backward compatibility and redirects to the appropriate service in the utils package.
All new code should use the specific service modules directly.
"""

# Import and re-export the service functions from modular services
from .utils.cache_service import cache_service, cache_response
from .utils.github_api import github_api
from .utils.analysis_service import analysis_service
from .utils.pdf_service import pdf_service
from .utils import normalize_github_username

# Re-export the main functions to maintain backward compatibility
fetch_all_data = analysis_service.fetch_all_data
aggregate_user_data = analysis_service.aggregate_user_data
calculate_impact_score = analysis_service.calculate_impact_score

# Log a deprecation warning
import logging
logger = logging.getLogger(__name__)
logger.warning("The services.py module is deprecated. Please use the specific service modules directly.")