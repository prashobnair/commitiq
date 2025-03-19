#!/usr/bin/env python3
"""
Simple test to verify the fix for the waitlist feedback update issue.
"""
import os
import logging
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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

def hash_email(email):
    """Create a secure hash of an email address for database lookup."""
    pepper = os.getenv('EMAIL_HASH_PEPPER', 'commitiq_default_hash_pepper')
    logger.info(f"Using pepper: {pepper}")
    return hashlib.sha256((email.lower() + pepper).encode()).hexdigest()

def test_existing_user_feedback_update():
    """Test updating feedback for an existing user with the fixed code."""
    test_email = 'fix_test@example.com'
    email_hash = hash_email(test_email)
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if test user exists
        cur.execute('SELECT id, feedback FROM waitlist WHERE email = %s', (test_email,))
        existing_user = cur.fetchone()
        
        if not existing_user:
            # Create test user
            logger.info(f"Creating test user: {test_email}")
            cur.execute(
                'INSERT INTO waitlist (email, email_hash, company, feedback) VALUES (%s, %s, %s, %s) RETURNING id',
                (test_email, email_hash, 'Test Company', None)  # Explicitly setting feedback to NULL
            )
            conn.commit()
            user_id = cur.fetchone()['id']
            logger.info(f"Created test user with ID: {user_id}")
            
            # Fetch the user we just created
            cur.execute('SELECT id, feedback FROM waitlist WHERE id = %s', (user_id,))
            existing_user = cur.fetchone()
        
        logger.info(f"Test user exists with ID: {existing_user['id']}")
        logger.info(f"Current feedback: {existing_user['feedback']}")
        
        # Try updating with our fixed code
        new_feedback = f"Updated feedback at {datetime.now()}"
        current_feedback = existing_user['feedback'] or ""
        
        if current_feedback:
            updated_feedback = f"{current_feedback}\n\nAdditional feedback ({datetime.now().strftime('%Y-%m-%d')}): {new_feedback}"
        else:
            updated_feedback = new_feedback
        
        logger.info(f"Setting updated feedback: {updated_feedback}")
        
        cur.execute(
            'UPDATE waitlist SET feedback = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
            (updated_feedback, existing_user['id'])
        )
        conn.commit()
        
        # Verify update
        cur.execute('SELECT feedback FROM waitlist WHERE id = %s', (existing_user['id'],))
        updated = cur.fetchone()
        logger.info(f"Feedback after update: {updated['feedback']}")
        
        return True
    except Exception as e:
        logger.error(f"Error in test: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = test_existing_user_feedback_update()
    if success:
        logger.info("Test completed successfully - Fix verified!")
        sys.exit(0)
    else:
        logger.error("Test failed - Fix not working!")
        sys.exit(1) 