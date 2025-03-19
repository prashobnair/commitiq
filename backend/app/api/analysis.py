# backend/app/api/analysis.py
from flask import Blueprint, jsonify, request
from ..services import aggregate_user_data, fetch_all_data, calculate_impact_score
from ..utils import normalize_github_username
from .analysis_tracking import store_analysis_result
import logging

# Get module logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analyze', methods=['POST'])
def analyze_user_post():
    """Analyze a GitHub user profile - POST endpoint for frontend compatibility.
    
    Accepts a JSON payload with 'username' and optional 'email' fields.
    """
    data = request.get_json()
    if not data or 'username' not in data:
        error_response = {'error': 'Username is required in the request body'}
        return jsonify(error_response), 400
    
    username = data.get('username')
    email = data.get('email')  # Optional email for tracking
    
    logger.info(f"Analyzing user from POST request: {username}, email: {email}")
    
    # Normalize the GitHub username
    normalized_username = normalize_github_username(username)
    
    if not normalized_username:
        logger.error(f"Invalid GitHub username format: {username}")
        error_response = {'error': 'Invalid GitHub username format'}
        
        # Track failed analysis attempt due to invalid format
        store_analysis_result(
            github_username=username,
            analysis_result=error_response,
            analyzer_email=email,
            request_info={
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }
        )
        
        return jsonify(error_response), 400
    
    # Log the normalized username if it's different
    if normalized_username != username:
        logger.info(f"Normalized username: {normalized_username}")
    
    try:
        github_data = fetch_all_data(normalized_username)
        logger.debug(f"Github data fetched: {github_data}")
        
        # Check for errors in github_data
        if 'error' in github_data:
            logger.error(f"Error during github data fetching: {github_data['error']}")
            error_response = {'error': github_data['error']}
            
            # Track failed analysis attempt
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
            
            return jsonify(error_response), 500
            
        # Process the github data using aggregate_user_data
        aggregated_data = aggregate_user_data(normalized_username, github_data)
        logger.debug(f"Aggregated data: {aggregated_data}")

        # Check for errors returned by aggregate_user_data
        if 'error' in aggregated_data:
            if isinstance(aggregated_data['error'], dict):
                # If it is a dict, it is the github api error
                error_response = aggregated_data['error']
                status_code = 404
            else:
                # else, return with status code 500
                logger.error(f"Error during aggregation: {aggregated_data['error']}")
                error_response = {'error': aggregated_data['error']}
                status_code = 500
                
            # Track failed analysis attempt
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
            
            return jsonify(error_response), status_code
        
        # Calculate impact score
        impact_score = calculate_impact_score(aggregated_data)
        logger.debug(f"Impact score calculated: {impact_score}")

        # Prepare final result
        result = {
            'impact_score': impact_score,
            'analysis': aggregated_data
        }
        
        # Track successful analysis
        analysis_id = store_analysis_result(
            github_username=normalized_username,
            analysis_result=result,
            analyzer_email=email,
            request_info={
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }
        )
        
        if analysis_id:
            # Add analysis ID to the result for reference
            result['id'] = analysis_id
            result['github_username'] = normalized_username
            logger.info(f"Analysis stored with ID: {analysis_id}")
        else:
            logger.warning("Analysis was not stored in the database")
        
        logger.debug(f"Returning result: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.exception("Exception in analyze_user_post:")
        error_response = {'error': 'An internal server error occurred'}
        
        # Track failed analysis attempt
        try:
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
        except Exception as track_err:
            logger.error(f"Failed to track analysis error: {track_err}")
            
        return jsonify(error_response), 500

@analysis_bp.route('/analyze/<username>', methods=['GET'])
def analyze_user(username):
    """Analyze a GitHub user profile - GET endpoint (legacy).
    
    Accepts username as a URL parameter and optional email as a query param.
    """
    logger.info(f"Analyzing user input: {username}")  # Log the original input
    
    # Get optional email from query param
    email = request.args.get('email')
    
    # Normalize the GitHub username
    normalized_username = normalize_github_username(username)
    
    if not normalized_username:
        logger.error(f"Invalid GitHub username format: {username}")
        error_response = {'error': 'Invalid GitHub username format'}
        
        # Track failed analysis attempt due to invalid format
        store_analysis_result(
            github_username=username,
            analysis_result=error_response,
            analyzer_email=email,
            request_info={
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }
        )
        
        return jsonify(error_response), 400
    
    # Log the normalized username if it's different
    if normalized_username != username:
        logger.info(f"Normalized username: {normalized_username}")
    
    try:
        github_data = fetch_all_data(normalized_username)
        logger.debug(f"Github data fetched: {github_data}")
        
        # Check for errors in github_data
        if 'error' in github_data:
            logger.error(f"Error during github data fetching: {github_data['error']}")
            error_response = {'error': github_data['error']}
            
            # Track failed analysis attempt
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
            
            return jsonify(error_response), 500
            
        # Process the github data using aggregate_user_data
        aggregated_data = aggregate_user_data(normalized_username, github_data)
        logger.debug(f"Aggregated data: {aggregated_data}")

        # Check for errors returned by aggregate_user_data
        if 'error' in aggregated_data:
            if isinstance(aggregated_data['error'], dict):
                # If it is a dict, it is the github api error
                error_response = aggregated_data['error']
                status_code = 404
            else:
                # else, return with status code 500
                logger.error(f"Error during aggregation: {aggregated_data['error']}")
                error_response = {'error': aggregated_data['error']}
                status_code = 500
                
            # Track failed analysis attempt
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
            
            return jsonify(error_response), status_code
        
        # Calculate impact score
        impact_score = calculate_impact_score(aggregated_data)
        logger.debug(f"Impact score calculated: {impact_score}")

        # Prepare final result
        result = {
            'impact_score': impact_score,
            'analysis': aggregated_data
        }
        
        # Track successful analysis
        analysis_id = store_analysis_result(
            github_username=normalized_username,
            analysis_result=result,
            analyzer_email=email,
            request_info={
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }
        )
        
        if analysis_id:
            # Add analysis ID to the result for reference
            result['id'] = analysis_id
            result['github_username'] = normalized_username
            logger.info(f"Analysis stored with ID: {analysis_id}")
        else:
            logger.warning("Analysis was not stored in the database")
        
        logger.debug(f"Returning result: {result}")
        return jsonify(result)  # Consistent return type
    except Exception as e:
        logger.exception("Exception in analyze_user:")
        error_response = {'error': 'An internal server error occurred'}
        
        # Track failed analysis attempt
        try:
            store_analysis_result(
                github_username=normalized_username,
                analysis_result=error_response,
                analyzer_email=email,
                request_info={
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent')
                }
            )
        except Exception as track_err:
            logger.error(f"Failed to track analysis error: {track_err}")
            
        return jsonify(error_response), 500