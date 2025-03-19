"""
Admin dashboard for viewing GitHub Analysis tracking data.
"""
from flask import Blueprint, render_template, request, jsonify, abort
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import json

# Get module logger
logger = logging.getLogger(__name__)

# Blueprint definition
tracking_dashboard_bp = Blueprint('tracking_dashboard', __name__)

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

@tracking_dashboard_bp.route('/', methods=['GET'])
def dashboard_home():
    """Dashboard homepage with summary statistics."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get total analysis count
        cur.execute('SELECT COUNT(*) as total FROM github_analysis')
        total_count = cur.fetchone()['total']
        
        # Get successful analysis count
        cur.execute('SELECT COUNT(*) as success_count FROM github_analysis WHERE is_successful = TRUE')
        success_count = cur.fetchone()['success_count']
        
        # Get failed analysis count
        cur.execute('SELECT COUNT(*) as failed_count FROM github_analysis WHERE is_successful = FALSE')
        failed_count = cur.fetchone()['failed_count']
        
        # Get average impact score
        cur.execute('''
            SELECT AVG(impact_score) as avg_score 
            FROM github_analysis 
            WHERE is_successful = TRUE AND impact_score IS NOT NULL
        ''')
        avg_score = cur.fetchone()['avg_score'] or 0
        
        # Get top analyzed usernames
        cur.execute('''
            SELECT github_username, COUNT(*) as count
            FROM github_analysis
            GROUP BY github_username
            ORDER BY count DESC
            LIMIT 10
        ''')
        top_usernames = cur.fetchall()
        
        # Get recent analyses (limit 20)
        cur.execute('''
            SELECT a.id, a.github_username, a.impact_score, a.analyzed_at, a.is_successful,
                   d.total_commits, d.pull_requests, d.issues_raised, d.code_reviews
            FROM github_analysis a
            LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
            ORDER BY a.analyzed_at DESC
            LIMIT 20
        ''')
        recent_analyses = cur.fetchall()
        
        # Format data for the template
        dashboard_data = {
            "total_count": total_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "avg_score": round(avg_score, 2),
            "top_usernames": top_usernames,
            "recent_analyses": recent_analyses
        }
        
        return jsonify(dashboard_data)
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({'error': 'Failed to generate dashboard data'}), 500
    finally:
        if conn:
            conn.close()

@tracking_dashboard_bp.route('/analysis/<int:analysis_id>', methods=['GET'])
def view_analysis_details(analysis_id):
    """View detailed information for a specific analysis."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get analysis data
        cur.execute('''
            SELECT a.*, d.*
            FROM github_analysis a
            LEFT JOIN github_analysis_details d ON a.id = d.analysis_id
            WHERE a.id = %s
        ''', (analysis_id,))
        
        analysis = cur.fetchone()
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
            
        # Format JSON fields
        for field in ['strengths', 'considerations', 'top_languages', 'top_repositories', 'full_analysis_data']:
            if field in analysis and analysis[field]:
                # Already a dict if using psycopg2 with RealDictCursor
                pass
                
        return jsonify(analysis)
        
    except Exception as e:
        logger.error(f"Error fetching analysis details: {e}")
        return jsonify({'error': 'Failed to retrieve analysis details'}), 500
    finally:
        if conn:
            conn.close()

@tracking_dashboard_bp.route('/stats', methods=['GET'])
def get_analysis_statistics():
    """Get statistics about GitHub analyses."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get analysis counts by day for the past 30 days
        cur.execute('''
            SELECT 
                DATE(analyzed_at) as date,
                COUNT(*) as total,
                SUM(CASE WHEN is_successful THEN 1 ELSE 0 END) as successful
            FROM github_analysis
            WHERE analyzed_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(analyzed_at)
            ORDER BY date
        ''')
        
        daily_counts = cur.fetchall()
        
        # Get average metrics for successful analyses
        cur.execute('''
            SELECT 
                AVG(d.total_commits) as avg_commits,
                AVG(d.pull_requests) as avg_pull_requests,
                AVG(d.issues_raised) as avg_issues,
                AVG(d.code_reviews) as avg_code_reviews,
                AVG(d.consistency_score) as avg_consistency,
                AVG(d.project_impact_score) as avg_project_impact,
                AVG(a.impact_score) as avg_impact_score
            FROM github_analysis a
            JOIN github_analysis_details d ON a.id = d.analysis_id
            WHERE a.is_successful = TRUE
        ''')
        
        avg_metrics = cur.fetchone()
        
        # Get impact score distribution
        cur.execute('''
            SELECT 
                CASE
                    WHEN impact_score < 10 THEN '0-10'
                    WHEN impact_score < 20 THEN '10-20'
                    WHEN impact_score < 30 THEN '20-30'
                    WHEN impact_score < 40 THEN '30-40'
                    WHEN impact_score < 50 THEN '40-50'
                    WHEN impact_score < 60 THEN '50-60'
                    WHEN impact_score < 70 THEN '60-70'
                    WHEN impact_score < 80 THEN '70-80'
                    WHEN impact_score < 90 THEN '80-90'
                    ELSE '90-100'
                END as score_range,
                COUNT(*) as count
            FROM github_analysis
            WHERE is_successful = TRUE AND impact_score IS NOT NULL
            GROUP BY score_range
            ORDER BY score_range
        ''')
        
        score_distribution = cur.fetchall()
        
        return jsonify({
            'daily_counts': daily_counts,
            'avg_metrics': avg_metrics,
            'score_distribution': score_distribution
        })
        
    except Exception as e:
        logger.error(f"Error generating statistics: {e}")
        return jsonify({'error': 'Failed to generate statistics'}), 500
    finally:
        if conn:
            conn.close() 