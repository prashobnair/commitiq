# backend/app/api/analysis.py
from flask import Blueprint, jsonify
from ..services import aggregate_user_data, fetch_all_data, calculate_impact_score
import logging

# Get module logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analyze/<username>', methods=['GET'])
def analyze_user(username):
    logger.info(f"Analyzing user: {username}")  # Log entry point
    try:
        
        github_data = fetch_all_data(username)
        logger.debug(f"Github data fetched: {github_data}")
        
        # Check for errors in github_data
        if 'error' in github_data:
            logger.error(f"Error during github data fetching: {github_data['error']}")
            return jsonify({'error': github_data['error']}), 500
            
        # Process the github data using aggregate_user_data
        aggregated_data = aggregate_user_data(username, github_data)
        logger.debug(f"Aggregated data: {aggregated_data}")

        # Check for errors returned by aggregate_user_data
        if 'error' in aggregated_data:
            if isinstance(aggregated_data['error'], dict):
                # If it is a dict, it is the github api error
                return jsonify(aggregated_data['error']), 404
            # else, return with status code 500
            logger.error(f"Error during aggregation: {aggregated_data['error']}")
            return jsonify({'error': aggregated_data['error']}), 500

        
        impact_score = calculate_impact_score(aggregated_data)
        
        
        logger.debug(f"Impact score calculated: {impact_score}")

        result = {
            'impact_score': impact_score,
            'analysis': aggregated_data
        }
        logger.debug(f"Returning result: {result}")
        return jsonify(result)  # Consistent return type
    except Exception as e:
        logger.exception("Exception in analyze_user:")
        return jsonify({'error': 'An internal server error occurred'}), 500