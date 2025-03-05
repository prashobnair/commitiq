# backend/app/api/analysis.py
from flask import Blueprint, jsonify
from ..services import aggregate_user_data, calculate_impact_score_graphql, calculate_overall_project_impact, fetch_all_data
import logging
import asyncio
import time

# Get module logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analyze/<username>', methods=['GET'])
def analyze_user(username):
    logger.info(f"TEST: Analyzing user: {username} at {time.time()}")  # Log with timestamp
    logger.debug(f"Analyzing user: {username}")  # Log entry point
    try:
        # Use asyncio.run to call the async function from synchronous code
        async_data = asyncio.run(fetch_all_data(username))
        logger.debug(f"Async data fetched: {async_data}")
        
        # Check for errors in async_data
        if 'error' in async_data:
            logger.error(f"Error during async data fetching: {async_data['error']}")
            return jsonify({'error': async_data['error']}), 500
            
        # Process the async data using aggregate_user_data
        aggregated_data = aggregate_user_data(username, async_data)
        logger.debug(f"Aggregated data: {aggregated_data}")

        # Check for errors returned by aggregate_user_data
        if 'error' in aggregated_data:
            if isinstance(aggregated_data['error'], dict):
                # If it is a dict, it is the github api error
                return jsonify(aggregated_data['error']), 404
            # else, return with status code 500
            logger.error(f"Error during aggregation: {aggregated_data['error']}")
            return jsonify({'error': aggregated_data['error']}), 500

        aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)
        logger.debug(f"Project impact calculated: {aggregated_data['project_impact']}")
        impact_score = calculate_impact_score_graphql(aggregated_data)
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