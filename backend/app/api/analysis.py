# backend/app/api/analysis.py
from flask import Blueprint, jsonify, request
from ..utils.analysis_service import analysis_service
from ..utils import normalize_github_username
from .analysis_tracking import store_analysis_result
import logging
import threading
import time

# Get module logger
logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)

def _async_store_analysis(github_username, analysis_result, analyzer_email=None, request_info=None):
    """
    Asynchronous wrapper for storing analysis results in the database.
    
    This function runs in a background thread to prevent blocking the main response.
    Any exceptions are caught and logged, preventing impact on the user experience.
    """
    try:
        analysis_id = store_analysis_result(
            github_username=github_username,
            analysis_result=analysis_result,
            analyzer_email=analyzer_email,
            request_info=request_info
        )
        
        if analysis_id:
            logger.info(f"Analysis stored asynchronously with ID: {analysis_id} for {github_username}")
        else:
            logger.warning(f"Async analysis storage failed for {github_username}")
    except Exception as e:
        logger.exception(f"Async analysis storage error for {github_username}: {str(e)}")

@analysis_bp.route('/analyze', methods=['POST'])
def analyze_user_post():
    """Analyze a GitHub user profile - POST endpoint for frontend compatibility.
    
    Accepts a JSON payload with 'username' and optional 'email' fields.
    """
    data = request.get_json()
    if not data or 'username' not in data:
        error_response = {'error': 'Username is required'}
        logger.error(f"Missing username in request: {data}")
        return jsonify(error_response), 400
    
    username = data.get('username')
    email = data.get('email')  # Optional email for tracking
    
    logger.info(f"Analyzing user from POST request: {username}, email: {email}, IP: {request.remote_addr}")
    
    # Normalize the GitHub username
    normalized_username = normalize_github_username(username)
    
    if not normalized_username:
        logger.error(f"Invalid GitHub username format: {username} from IP: {request.remote_addr}")
        error_response = {'error': 'Invalid username format'}
        
        # Track failed analysis attempt due to invalid format - still synchronous for errors
        # since these are fast operations and error tracking is important
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
        logger.info(f"Normalized username: {username} -> {normalized_username}")
    
    try:
        # Use the analysis service to fetch and process data
        logger.info(f"Fetching GitHub data for {normalized_username}")
        github_data = analysis_service.fetch_all_data(normalized_username)
        logger.debug(f"Github data fetched for {normalized_username}, data type: {type(github_data)}")
        
        # Check for errors in github_data
        if 'error' in github_data:
            logger.error(f"Error during github data fetching for {normalized_username}: {github_data['error']} from IP: {request.remote_addr}")
            error_response = {'error': github_data['error']}
            
            # Track failed analysis attempt - still synchronous for errors
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
            
        # Process the github data using analysis service
        logger.info(f"Aggregating data for {normalized_username}")
        aggregated_data = analysis_service.aggregate_user_data(normalized_username, github_data)
        logger.debug(f"Data aggregated for {normalized_username}, data keys: {list(aggregated_data.keys()) if isinstance(aggregated_data, dict) else 'not a dict'}")

        # Check for errors returned by aggregate_user_data
        if 'error' in aggregated_data:
            if isinstance(aggregated_data['error'], dict):
                # If it is a dict, it is the github api error
                error_response = aggregated_data['error']
                status_code = 404
                logger.error(f"GitHub API error during aggregation for {normalized_username}: {error_response}")
            else:
                # else, return with status code 500
                logger.error(f"Error during aggregation for {normalized_username}: {aggregated_data['error']} from IP: {request.remote_addr}")
                error_response = {'error': aggregated_data['error']}
                status_code = 500
                
            # Track failed analysis attempt - still synchronous for errors
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
        impact_score = analysis_service.calculate_impact_score(aggregated_data)
        logger.debug(f"Impact score calculated for {normalized_username}: {impact_score} from IP: {request.remote_addr}")

        # Prepare final result
        result = {
            'impact_score': impact_score,
            'analysis': aggregated_data,
            'github_username': normalized_username
        }
        
        # Generate a placeholder ID to use until the real one is saved in the database
        # This allows the frontend to reference the analysis while the database operation completes asynchronously
        placeholder_id = hash(f"{normalized_username}:{int(time.time())}")
        result['id'] = placeholder_id
        
        # Start a background thread to store the analysis result
        # This prevents blocking the response while database operations complete
        threading.Thread(
            target=_async_store_analysis,
            args=(normalized_username, result, email, {
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent')
            }),
            daemon=True
        ).start()
        
        logger.info(f"Analysis complete for {normalized_username}, impact score: {impact_score}, from IP: {request.remote_addr}")
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Exception in analyze_user_post for {normalized_username} from IP: {request.remote_addr}: {str(e)}")
        error_response = {'error': 'Unable to analyze profile at this time'}
        
        # Track failed analysis attempt - still synchronous for errors
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
            logger.error(f"Failed to track analysis error for {normalized_username}: {track_err}")
            
        return jsonify(error_response), 500

@analysis_bp.route('/analyze/<username>', methods=['GET'])
def analyze_user(username):
    """Analyze a GitHub user profile - GET endpoint.
    
    Accepts username as a URL parameter and optional email as a query param.
    """
    logger.info(f"Analyzing user input: {username} from IP: {request.remote_addr}")  # Log the original input
    
    # Get optional email from query param
    email = request.args.get('email')
    
    # Normalize the GitHub username
    normalized_username = normalize_github_username(username)
    
    if not normalized_username:
        logger.error(f"Invalid GitHub username format: {username} from IP: {request.remote_addr}")
        error_response = {'error': 'Invalid username format'}
        
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
    
    # Redirect to the POST method implementation to avoid code duplication
    # Create a mock request body
    mock_data = {
        'username': normalized_username,
        'email': email
    }
    request.get_json = lambda: mock_data
    
    return analyze_user_post()