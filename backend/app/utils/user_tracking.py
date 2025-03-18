"""
Utility functions for tracking user activity across the application.

This module provides functions to link waitlist user information with
their GitHub analysis activities, allowing for better insights into 
user engagement patterns.
"""

import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)

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

def link_waitlist_user_to_analysis(email, github_username):
    """
    Create a link between a waitlist user and GitHub analysis activities.
    
    This is used when a user who is on the waitlist performs GitHub username analysis,
    allowing us to track which recruiters are analyzing which profiles.
    
    Args:
        email: The email address of the waitlist user
        github_username: The GitHub username they analyzed
        
    Returns:
        bool: True if the link was created successfully, False otherwise
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Update all analyses with this user's email where the IP/session matches
        # This is just a simple approach - in a production system you would use
        # proper session tracking and authentication instead
        
        # Find waitlist user by email
        cur.execute('SELECT id FROM waitlist WHERE email = %s', (email,))
        user = cur.fetchone()
        
        if not user:
            logger.warning(f"No waitlist user found with email {email}")
            return False
            
        # Update recent analyses where the analyzer_email is null
        # This is a conservative approach to not overwrite existing attributions
        cur.execute('''
            UPDATE github_analysis
            SET analyzer_email = %s
            WHERE github_username = %s
              AND analyzer_email IS NULL
              AND analyzed_at >= NOW() - INTERVAL '1 hour'
            RETURNING id
        ''', (email, github_username))
        
        updated_rows = cur.fetchall()
        conn.commit()
        
        if updated_rows:
            logger.info(f"Linked waitlist user {email} to {len(updated_rows)} analyses of {github_username}")
            return True
        else:
            logger.info(f"No recent analyses found to link for {email} and {github_username}")
            return False
            
    except Exception as e:
        logger.error(f"Error linking waitlist user to analysis: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_user_analysis_history(email, limit=20):
    """
    Get the GitHub analysis history for a specific waitlist user.
    
    Args:
        email: The email address of the waitlist user
        limit: Maximum number of results to return
        
    Returns:
        list: List of analysis records for this user
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get analyses where this user's email is the analyzer
        cur.execute('''
            SELECT a.id, a.github_username, a.impact_score, a.analyzed_at, a.is_successful,
                  d.total_commits, d.pull_requests, d.issues_raised, d.code_reviews
            FROM github_analysis a
            LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
            WHERE a.analyzer_email = %s
            ORDER BY a.analyzed_at DESC
            LIMIT %s
        ''', (email, limit))
        
        analyses = cur.fetchall()
        return analyses
        
    except Exception as e:
        logger.error(f"Error getting user analysis history: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_top_analyzed_profiles():
    """
    Get the most frequently analyzed GitHub profiles.
    
    Returns:
        list: List of dictionaries with github_username and count fields
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the most frequently analyzed GitHub profiles
        cur.execute('''
            SELECT github_username, 
                   COUNT(*) as count,
                   AVG(impact_score) as avg_impact_score,
                   COUNT(DISTINCT analyzer_email) as unique_analyzers
            FROM github_analysis
            WHERE is_successful = TRUE
            GROUP BY github_username
            ORDER BY count DESC
            LIMIT 20
        ''')
        
        profiles = cur.fetchall()
        return profiles
        
    except Exception as e:
        logger.error(f"Error getting top analyzed profiles: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_waitlist_user_engagement_metrics():
    """
    Get metrics on waitlist user engagement with the analysis feature.
    
    Returns:
        dict: Dictionary with engagement metrics
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get total waitlist users
        cur.execute('SELECT COUNT(*) as total FROM waitlist')
        total_users = cur.fetchone()['total']
        
        # Get users who have performed analyses
        cur.execute('''
            SELECT COUNT(DISTINCT analyzer_email) as active_users
            FROM github_analysis
            WHERE analyzer_email IS NOT NULL
        ''')
        active_users = cur.fetchone()['active_users']
        
        # Get average analyses per active user
        cur.execute('''
            SELECT analyzer_email, COUNT(*) as analysis_count
            FROM github_analysis
            WHERE analyzer_email IS NOT NULL
            GROUP BY analyzer_email
        ''')
        
        user_counts = cur.fetchall()
        if user_counts:
            avg_analyses = sum(row['analysis_count'] for row in user_counts) / len(user_counts)
        else:
            avg_analyses = 0
        
        # Get most active waitlist users
        cur.execute('''
            SELECT analyzer_email, COUNT(*) as analysis_count
            FROM github_analysis
            WHERE analyzer_email IS NOT NULL
            GROUP BY analyzer_email
            ORDER BY analysis_count DESC
            LIMIT 10
        ''')
        
        most_active_users = cur.fetchall()
        
        return {
            "total_waitlist_users": total_users,
            "active_users": active_users,
            "engagement_rate": (active_users / total_users) if total_users > 0 else 0,
            "avg_analyses_per_user": avg_analyses,
            "most_active_users": most_active_users
        }
        
    except Exception as e:
        logger.error(f"Error getting waitlist user engagement metrics: {e}")
        return {}
    finally:
        if conn:
            conn.close() 