# backend/app/api/waitlist.py
from flask import Blueprint, request, jsonify
import logging
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import secrets
import hashlib
import base64
import html
from datetime import datetime

# Load environment variables
load_dotenv()

# Get module logger
logger = logging.getLogger(__name__)

# Blueprint definition
waitlist_bp = Blueprint('waitlist', __name__)

# Database connection function
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

# Function to initialize the waitlist table
def init_waitlist_table():
    """Create the waitlist table if it doesn't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create waitlist table with necessary fields
        cur.execute('''
        CREATE TABLE IF NOT EXISTS waitlist (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            email_hash TEXT NOT NULL,  -- Hashed email for lookup without exposing raw email
            company TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create index on email_hash for faster lookups
        cur.execute('CREATE INDEX IF NOT EXISTS idx_email_hash ON waitlist(email_hash)')
        
        conn.commit()
        logger.info("Waitlist table initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing waitlist table: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

# Helper function to hash email addresses
def hash_email(email):
    """Create a secure hash of an email address for database lookup."""
    # Use a pepper (server-side secret) with the hash to prevent rainbow table attacks
    # IMPORTANT: We use a default fixed value if EMAIL_HASH_PEPPER isn't set to avoid 
    # generating a new pepper on every run, which would break existing hashes
    pepper = os.getenv('EMAIL_HASH_PEPPER', 'commitiq_default_hash_pepper')
    return hashlib.sha256((email.lower() + pepper).encode()).hexdigest()

# Email validation function
def is_valid_email(email):
    """Validate an email address format."""
    # Simple regex pattern for basic email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Sanitize input
def sanitize_input(text):
    """Sanitize user input to prevent XSS."""
    if text is None:
        return None
    return html.escape(text.strip())

# API Routes
@waitlist_bp.route('/join', methods=['POST'])
def join_waitlist():
    """Handle waiting list sign-ups and feedback."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract and validate email
        email = data.get('email', '').strip().lower()
        if not email or not is_valid_email(email):
            return jsonify({'error': 'Valid email address is required'}), 400
        
        # Sanitize inputs
        company = sanitize_input(data.get('company', ''))
        feedback = sanitize_input(data.get('feedback', ''))
        
        # Hash email for secure lookup
        email_hash = hash_email(email)
        
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if email already exists - first try the hash lookup
            cur.execute('SELECT id, feedback FROM waitlist WHERE email_hash = %s', (email_hash,))
            existing_user = cur.fetchone()
            
            # If not found by hash, try direct email lookup as a fallback
            if not existing_user:
                cur.execute('SELECT id, feedback FROM waitlist WHERE email = %s', (email,))
                existing_user = cur.fetchone()
                
                # If found by email but hash didn't match, update the hash
                if existing_user:
                    cur.execute(
                        'UPDATE waitlist SET email_hash = %s WHERE id = %s',
                        (email_hash, existing_user['id'])
                    )
                    logger.info(f"Updated email hash for user ID {existing_user['id']}")
                    conn.commit()
            
            if existing_user:
                # User already in waitlist, determine what needs to be updated
                updates_needed = []
                update_params = []
                
                # Handle feedback update
                if feedback:
                    # Concatenate new feedback with existing feedback
                    # Handle None feedback safely
                    current_feedback = existing_user['feedback'] or ""
                    
                    if current_feedback:
                        updated_feedback = f"{current_feedback}\n\nAdditional feedback ({datetime.now().strftime('%Y-%m-%d')}): {feedback}"
                    else:
                        updated_feedback = feedback
                    
                    updates_needed.append("feedback = %s")
                    update_params.append(updated_feedback)
                
                # Only perform update if there are changes
                if updates_needed:
                    update_query = f"UPDATE waitlist SET {', '.join(updates_needed)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                    update_params.append(existing_user['id'])
                    
                    cur.execute(update_query, tuple(update_params))
                    conn.commit()
                    
                    return jsonify({
                        'status': 'already_joined',
                        'message': 'You are already on our waiting list. Your information has been updated. Thank you!'
                    })
                else:
                    return jsonify({
                        'status': 'already_joined',
                        'message': 'You are already on our waiting list. We\'ll notify you when we\'re ready!'
                    })
            else:
                # New user, add to waitlist
                cur.execute(
                    'INSERT INTO waitlist (email, email_hash, company, feedback) VALUES (%s, %s, %s, %s)',
                    (email, email_hash, company, feedback)
                )
                conn.commit()
                return jsonify({
                    'status': 'success',
                    'message': 'Successfully joined the waiting list!'
                })
                
        except Exception as e:
            logger.error(f"Database error in join_waitlist: {e}")
            if conn:
                conn.rollback()
            return jsonify({'error': 'An error occurred while processing your request'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        logger.exception(f"Exception in join_waitlist: {e}")
        return jsonify({'error': 'An internal server error occurred'}), 500

@waitlist_bp.route('/count', methods=['GET'])
def get_waitlist_count():
    """Get the current number of people on the waiting list."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get total count of users in the waitlist
        cur.execute('SELECT COUNT(*) as count FROM waitlist')
        result = cur.fetchone()
        
        if result:
            return jsonify({
                'count': result['count'],
                'message': f"Join {result['count']} others waiting for CommitIQ!"
            })
        else:
            return jsonify({
                'count': 0,
                'message': "Be the first to join our waiting list!"
            })
    except Exception as e:
        logger.error(f"Error getting waitlist count: {e}")
        return jsonify({'error': 'Failed to get waiting list count'}), 500
    finally:
        if conn:
            conn.close()

# Initialize the waitlist table when the module is imported
try:
    init_waitlist_table()
except Exception as e:
    logger.error(f"Failed to initialize waitlist table: {e}") 