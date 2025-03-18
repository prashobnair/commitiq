"""
Module for tracking GitHub analysis data in the database.
This allows CommitIQ to gather insights about which profiles are being analyzed
and what results are being generated.
"""

from flask import Blueprint, request, jsonify, current_app
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
from datetime import datetime
import json

# Get module logger
logger = logging.getLogger(__name__)

# Blueprint definition
analysis_tracking_bp = Blueprint('analysis_tracking', __name__)

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT', '5432'),
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def init_analysis_tracking_tables():
    """Create the necessary tables for tracking GitHub analysis data if they don't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create github_analysis table - main analysis records
        cur.execute('''
        CREATE TABLE IF NOT EXISTS github_analysis (
            id SERIAL PRIMARY KEY,
            github_username TEXT NOT NULL,
            analyzer_email TEXT,       -- Optional link to the user who performed the analysis
            impact_score NUMERIC(5,2), -- Overall impact score (e.g., 78.5)
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Additional metadata
            analyzed_from_ip TEXT,     -- IP address of the analyzer (hashed for privacy)
            user_agent TEXT,           -- User agent information
            
            -- Flags for analysis
            is_successful BOOLEAN DEFAULT TRUE,
            error_message TEXT         -- If analysis failed, store error message
        )
        ''')
        
        # Create index on github_username for faster lookups
        cur.execute('CREATE INDEX IF NOT EXISTS idx_github_analysis_username ON github_analysis(github_username)')
        
        # Create github_analysis_details table - detailed metrics
        cur.execute('''
        CREATE TABLE IF NOT EXISTS github_analysis_details (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER NOT NULL REFERENCES github_analysis(id) ON DELETE CASCADE,
            
            -- Main metrics (numeric)
            total_commits INTEGER,
            pull_requests INTEGER,
            issues_raised INTEGER,
            code_reviews INTEGER,
            consistency_score NUMERIC(5,2),
            project_impact_score NUMERIC(5,2),
            
            -- JSON fields for more complex data
            strengths JSONB,           -- Array of strength descriptions
            considerations JSONB,      -- Array of considerations/limitations
            top_languages JSONB,       -- Language usage statistics
            top_repositories JSONB,    -- Top repository data
            
            -- Raw data storage (optional, for future reference)
            full_analysis_data JSONB,  -- Complete analysis results JSON
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        logger.info("GitHub analysis tracking tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing analysis tracking tables: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def store_analysis_result(github_username, analysis_result, analyzer_email=None, request_info=None):
    """
    Store a GitHub analysis result in the database.
    
    Args:
        github_username: The GitHub username that was analyzed
        analysis_result: The result dictionary from the analysis
        analyzer_email: Optional email of the user who performed the analysis
        request_info: Optional dictionary with request information (IP, user agent)
    
    Returns:
        The ID of the created analysis record
    """
    logger.info(f"Attempting to store analysis result for {github_username}")
    logger.debug(f"Analysis result type: {type(analysis_result)}")
    logger.debug(f"Analysis result value: {analysis_result}")
    logger.debug(f"Analyzer email: {analyzer_email}")
    logger.debug(f"Request info: {request_info}")
    
    conn = None
    try:
        # Validate inputs
        if not github_username:
            logger.error("Cannot store analysis: github_username is empty")
            return None
            
        if not analysis_result:
            logger.error("Cannot store analysis: analysis_result is empty")
            return None
            
        # Convert non-dict analysis_result to dict if needed (e.g., if it's a float)
        if not isinstance(analysis_result, dict):
            logger.warning(f"Converting non-dict analysis_result of type {type(analysis_result)} to dict")
            if isinstance(analysis_result, (int, float)):
                # If it's just a score (e.g., impact_score as float), wrap it
                analysis_result = {'impact_score': analysis_result}
            else:
                # Try to convert to string and wrap as error
                try:
                    error_str = str(analysis_result)
                    analysis_result = {'error': error_str}
                except:
                    analysis_result = {'error': 'Unknown error format'}
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if analysis was successful
        is_successful = True
        error_message = None
        
        if 'error' in analysis_result:
            is_successful = False
            # Get error message, handling various formats
            if isinstance(analysis_result['error'], (str, int, float)):
                error_message = str(analysis_result['error'])
            elif isinstance(analysis_result['error'], dict):
                # Try to extract message from error dict
                error_message = json.dumps(analysis_result['error'])
            else:
                error_message = "Unknown error format"
                
            logger.warning(f"Storing failed analysis for {github_username}: {error_message}")
            
            # Insert basic error record
            try:
                cur.execute('''
                INSERT INTO github_analysis 
                (github_username, analyzer_email, analyzed_from_ip, user_agent, is_successful, error_message)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                ''', (
                    github_username,
                    analyzer_email,
                    request_info.get('ip') if request_info else None,
                    request_info.get('user_agent') if request_info else None,
                    is_successful,
                    error_message
                ))
                
                analysis_id = cur.fetchone()['id']
                conn.commit()
                logger.info(f"Stored failed analysis (ID: {analysis_id})")
                return analysis_id
            except Exception as e:
                logger.error(f"Database error storing failed analysis: {e}")
                if conn:
                    conn.rollback()
                return None
        
        # For successful analysis, extract and store data
        # Safely extract impact_score (could be direct or nested)
        impact_score = None
        if 'impact_score' in analysis_result:
            impact_score = analysis_result.get('impact_score')
        
        # Extract analysis data for detailed metrics
        analysis_data = {}
        if 'analysis' in analysis_result and isinstance(analysis_result['analysis'], dict):
            analysis_data = analysis_result['analysis']
        
        logger.info(f"Storing successful analysis for {github_username} with impact score {impact_score}")
            
        # Insert main analysis record
        try:
            cur.execute('''
            INSERT INTO github_analysis 
            (github_username, analyzer_email, impact_score, 
             analyzed_from_ip, user_agent, is_successful)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (
                github_username,
                analyzer_email,
                impact_score,
                request_info.get('ip') if request_info else None,
                request_info.get('user_agent') if request_info else None,
                is_successful
            ))
            
            analysis_id = cur.fetchone()['id']
            logger.info(f"Successfully inserted main analysis record with ID: {analysis_id}")
        except Exception as e:
            logger.error(f"Database error storing main analysis record: {e}")
            if conn:
                conn.rollback()
            return None
        
        # Extract detailed metrics from the analysis result - safely with defaults
        contributions = {}
        if isinstance(analysis_data.get('contributions'), dict):
            contributions = analysis_data.get('contributions', {})
        
        logger.debug(f"Extracted contributions data type: {type(contributions)}")
        logger.debug(f"Contributions data: {contributions}")
        
        # Safely extract lists with type checking
        strengths = []
        if isinstance(analysis_data.get('strengths'), list):
            strengths = analysis_data.get('strengths', [])
            
        considerations = []
        if isinstance(analysis_data.get('considerations'), list):
            considerations = analysis_data.get('considerations', [])
        
        # Extract the main metrics with safe defaults - using the CORRECT contribution field names
        total_commits = contributions.get('commits', 0) if isinstance(contributions, dict) else 0
        pull_requests = contributions.get('pulls', 0) if isinstance(contributions, dict) else 0
        issues_raised = contributions.get('issues', 0) if isinstance(contributions, dict) else 0
        code_reviews = contributions.get('reviews', 0) if isinstance(contributions, dict) else 0
        
        # Ensure we get numeric values even if they are strings
        try:
            total_commits = int(total_commits) if total_commits is not None else 0
            pull_requests = int(pull_requests) if pull_requests is not None else 0
            issues_raised = int(issues_raised) if issues_raised is not None else 0
            code_reviews = int(code_reviews) if code_reviews is not None else 0
        except (ValueError, TypeError):
            logger.warning("Failed to convert some metrics to integers, using defaults")
            total_commits = 0
            pull_requests = 0
            issues_raised = 0
            code_reviews = 0
            
        # Safely extract nested values
        consistency_score = None
        if isinstance(contributions.get('consistency'), dict):
            consistency_score = contributions.get('consistency', {}).get('score')
        else:
            # Sometimes consistency is a direct value, not a nested object
            consistency_score = contributions.get('consistency')
            
        project_impact_score = None
        if isinstance(contributions.get('project_impact'), dict):
            project_impact_score = contributions.get('project_impact', {}).get('score')
        else:
            # Sometimes repos_impact is used instead of project_impact
            project_impact_score = contributions.get('repos_impact')
        
        # Convert score values to numeric if possible
        try:
            if consistency_score is not None:
                consistency_score = float(consistency_score)
            if project_impact_score is not None:
                project_impact_score = float(project_impact_score)
        except (ValueError, TypeError):
            logger.warning("Failed to convert some scores to floats, using None")
            
        # Extract language and repository data
        top_languages = contributions.get('top_languages') if isinstance(contributions, dict) else None
        top_repositories = contributions.get('top_repositories') if isinstance(contributions, dict) else None
        
        logger.debug(f"Extracted metrics - commits: {total_commits}, PRs: {pull_requests}, issues: {issues_raised}, reviews: {code_reviews}")
        logger.debug(f"Extracted scores - consistency: {consistency_score}, project_impact: {project_impact_score}")
        
        # Insert detailed metrics
        try:
            cur.execute('''
            INSERT INTO github_analysis_details
            (analysis_id, total_commits, pull_requests, issues_raised, code_reviews,
             consistency_score, project_impact_score, strengths, considerations,
             top_languages, top_repositories, full_analysis_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                analysis_id,
                total_commits,
                pull_requests,
                issues_raised,
                code_reviews,
                consistency_score,
                project_impact_score,
                Json(strengths) if strengths else None,
                Json(considerations) if considerations else None,
                Json(top_languages) if top_languages else None,
                Json(top_repositories) if top_repositories else None,
                Json(analysis_result) if analysis_result else None
            ))
            
            conn.commit()
            logger.info(f"Successfully stored complete analysis for {github_username} (ID: {analysis_id})")
            return analysis_id
        except Exception as e:
            logger.error(f"Database error storing analysis details: {e}")
            if conn:
                conn.rollback()
            return None
            
    except Exception as e:
        logger.error(f"Unexpected error storing analysis result: {e}")
        if conn:
            conn.rollback()
        # Don't re-raise the exception - we don't want to break the main app flow
        # if tracking fails
        return None
    finally:
        if conn:
            conn.close()

@analysis_tracking_bp.route('/recent', methods=['GET'])
def get_recent_analyses():
    """API endpoint to get recent analyses (for admin/dashboard use)."""
    conn = None
    try:
        # TODO: Add proper authentication for this endpoint
        # This should only be accessible to admins
        
        limit = min(int(request.args.get('limit', 10)), 100)  # Cap at 100 records
        offset = int(request.args.get('offset', 0))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
        SELECT a.id, a.github_username, a.impact_score, a.analyzed_at, a.is_successful,
               d.total_commits, d.pull_requests, d.issues_raised, d.code_reviews
        FROM github_analysis a
        LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
        ORDER BY a.analyzed_at DESC
        LIMIT %s OFFSET %s
        ''', (limit, offset))
        
        results = cur.fetchall()
        
        return jsonify({
            'analyses': [dict(r) for r in results],
            'count': len(results),
            'limit': limit,
            'offset': offset
        })
    
    except Exception as e:
        logger.error(f"Error fetching recent analyses: {e}")
        return jsonify({'error': 'Failed to retrieve recent analyses'}), 500
    finally:
        if conn:
            conn.close()

# Initialize tables when this module is imported
def initialize_tracking_tables():
    """Initialize the tracking tables and verify database connection."""
    try:
        # Test database connection first
        logger.info("Testing database connection...")
        conn = get_db_connection()
        conn.close()
        logger.info("Database connection successful, initializing tracking tables...")
        
        # Initialize the tables
        init_analysis_tracking_tables()
        
        # Verify tables were created by counting records
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM github_analysis")
            count = cur.fetchone()['count']
            logger.info(f"GitHub analysis table verified. Current record count: {count}")
            
            cur.execute("SELECT COUNT(*) FROM github_analysis_details")
            details_count = cur.fetchone()['count']
            logger.info(f"GitHub analysis details table verified. Current record count: {details_count}")
            
            logger.info("GitHub analysis tracking initialized successfully.")
        except Exception as e:
            logger.error(f"Table verification failed: {e}")
            logger.error("Database tables might not be properly initialized!")
        finally:
            cur.close()
            conn.close()
            
    except psycopg2.Error as db_error:
        logger.error(f"Database connection or initialization error: {db_error}")
        logger.error(f"Connection parameters: host={os.getenv('DB_HOST')}, dbname={os.getenv('DB_NAME')}, user={os.getenv('DB_USER')}")
        logger.error("Analysis tracking will be disabled!")
    except Exception as e:
        logger.error(f"Failed to initialize analysis tracking tables: {e}")
        logger.error("Check that PostgreSQL is running and credentials are correct.")
        logger.error("Analysis tracking will be disabled!")
        
# Run initialization
try:
    initialize_tracking_tables()
except Exception as e:
    logger.error(f"Unexpected error during tracking initialization: {e}")
    logger.error("Analysis tracking will be disabled!") 