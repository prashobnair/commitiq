"""
Module for sharing GitHub analysis profiles and generating shareable links.
This allows users to share their GitHub analysis results with others.
"""

from flask import Blueprint, request, jsonify, url_for, current_app, redirect, render_template
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import uuid
import json
import time
from datetime import datetime, timedelta
import jwt

# Get module logger
logger = logging.getLogger(__name__)

# Blueprint definition
share_bp = Blueprint('share', __name__)

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

def init_share_tables():
    """Create the necessary tables for sharing GitHub analysis data if they don't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create shared_profiles table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS shared_profiles (
            id SERIAL PRIMARY KEY,
            share_id TEXT NOT NULL UNIQUE,
            analysis_id INTEGER NOT NULL REFERENCES github_analysis(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            access_count INTEGER DEFAULT 0,
            is_public BOOLEAN DEFAULT TRUE,
            requires_passcode BOOLEAN DEFAULT FALSE,
            passcode TEXT,
            created_by TEXT
        )
        ''')
        
        # Create index on share_id for faster lookups
        cur.execute('CREATE INDEX IF NOT EXISTS idx_shared_profiles_share_id ON shared_profiles(share_id)')
        
        conn.commit()
        logger.info("Share tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing share tables: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

@share_bp.route('/create', methods=['POST'])
def create_share():
    """Create a shareable link for a GitHub analysis."""
    data = request.get_json()
    if not data or 'analysis_id' not in data:
        return jsonify({'error': 'Analysis ID is required'}), 400
    
    analysis_id = data.get('analysis_id')
    expires_in_days = data.get('expires_in_days', 30)  # Default 30 days
    is_public = data.get('is_public', True)
    requires_passcode = data.get('requires_passcode', False)
    passcode = data.get('passcode') if requires_passcode else None
    created_by = data.get('email')  # Optional creator email
    
    # Generate a unique share ID
    share_id = str(uuid.uuid4())
    
    # Calculate expiration date
    expires_at = datetime.now() + timedelta(days=expires_in_days)
    
    conn = None
    try:
        # First check if the analysis exists
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('SELECT id FROM github_analysis WHERE id = %s', (analysis_id,))
        if not cur.fetchone():
            return jsonify({'error': 'Analysis not found'}), 404
        
        # Check if a share already exists for this analysis
        cur.execute('SELECT share_id FROM shared_profiles WHERE analysis_id = %s', (analysis_id,))
        existing_share = cur.fetchone()
        
        if existing_share:
            # Update existing share
            share_id = existing_share['share_id']
            cur.execute('''
            UPDATE shared_profiles 
            SET expires_at = %s, is_public = %s, requires_passcode = %s, passcode = %s
            WHERE share_id = %s
            ''', (expires_at, is_public, requires_passcode, passcode, share_id))
            logger.info(f"Updated existing share {share_id} for analysis {analysis_id}")
        else:
            # Create new share
            cur.execute('''
            INSERT INTO shared_profiles
            (share_id, analysis_id, expires_at, is_public, requires_passcode, passcode, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (share_id, analysis_id, expires_at, is_public, requires_passcode, passcode, created_by))
            logger.info(f"Created new share {share_id} for analysis {analysis_id}")
        
        conn.commit()
        
        # Construct the shareable URL
        share_url = url_for('share.view_shared_profile', share_id=share_id, _external=True)
        
        return jsonify({
            'share_id': share_id,
            'share_url': share_url,
            'expires_at': expires_at.isoformat(),
            'requires_passcode': requires_passcode
        })
        
    except Exception as e:
        logger.error(f"Error creating share: {e}")
        if conn:
            conn.rollback()
        return jsonify({'error': 'Failed to create share'}), 500
    finally:
        if conn:
            conn.close()

@share_bp.route('/view/<share_id>', methods=['GET'])
def view_shared_profile(share_id):
    """View a shared GitHub analysis profile."""
    passcode = request.args.get('passcode')
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the shared profile
        cur.execute('''
        SELECT sp.*, ga.github_username, ga.impact_score
        FROM shared_profiles sp
        JOIN github_analysis ga ON sp.analysis_id = ga.id
        WHERE sp.share_id = %s
        ''', (share_id,))
        
        shared_profile = cur.fetchone()
        
        if not shared_profile:
            return jsonify({'error': 'Shared profile not found'}), 404
        
        # Check if expired
        if shared_profile['expires_at'] and shared_profile['expires_at'] < datetime.now():
            return jsonify({'error': 'Shared profile has expired'}), 403
        
        # Check if passcode is required
        if shared_profile['requires_passcode']:
            if not passcode or passcode != shared_profile['passcode']:
                return jsonify({'error': 'Invalid passcode', 'requires_passcode': True}), 403
        
        # Increment access count
        cur.execute('UPDATE shared_profiles SET access_count = access_count + 1 WHERE share_id = %s', (share_id,))
        conn.commit()
        
        # Get the full analysis data
        cur.execute('''
        SELECT ga.*, gad.full_analysis_data
        FROM github_analysis ga
        LEFT JOIN github_analysis_details gad ON ga.id = gad.analysis_id
        WHERE ga.id = %s
        ''', (shared_profile['analysis_id'],))
        
        analysis = cur.fetchone()
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
        
        # Prepare the response
        full_data = analysis['full_analysis_data'] if analysis['full_analysis_data'] else {}
        
        response = {
            'github_username': analysis['github_username'],
            'impact_score': analysis['impact_score'],
            'analyzed_at': analysis['analyzed_at'].isoformat() if analysis['analyzed_at'] else None,
            'analysis': full_data.get('analysis', {}),
            'share_info': {
                'share_id': shared_profile['share_id'],
                'created_at': shared_profile['created_at'].isoformat() if shared_profile['created_at'] else None,
                'expires_at': shared_profile['expires_at'].isoformat() if shared_profile['expires_at'] else None,
                'view_count': shared_profile['access_count']
            }
        }
        
        # In a real application, we would render a template here
        # For simplicity, we'll just return the JSON data
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error viewing shared profile: {e}")
        return jsonify({'error': 'Failed to retrieve shared profile'}), 500
    finally:
        if conn:
            conn.close()

# Initialize tables when this module is imported
try:
    init_share_tables()
except Exception as e:
    logger.error(f"Failed to initialize share tables: {e}") 