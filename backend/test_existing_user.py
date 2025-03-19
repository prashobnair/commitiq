#!/usr/bin/env python3
"""
Test script to debug the issue with existing users submitting waitlist requests again.
This script simulates what happens in the waitlist join endpoint when an existing user submits.
"""
import os
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import secrets
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def hash_email(email):
    """Create a secure hash of an email address for database lookup."""
    # Use a pepper (server-side secret) with the hash to prevent rainbow table attacks
    pepper = os.getenv('EMAIL_HASH_PEPPER', secrets.token_hex(16))
    hashed = hashlib.sha256((email.lower() + pepper).encode()).hexdigest()
    logger.info(f"Email: {email}, Pepper: {pepper}, Hash: {hashed}")
    return hashed

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

def test_with_existing_user(test_email, new_feedback=None):
    """Test what happens when an existing user submits again."""
    email_hash = hash_email(test_email)
    
    logger.info(f"Testing with existing user: {test_email}")
    logger.info(f"New feedback: {new_feedback}")
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email already exists
        cur.execute('SELECT id, feedback FROM waitlist WHERE email_hash = %s', (email_hash,))
        existing_user = cur.fetchone()
        
        if existing_user:
            logger.info(f"User found with ID: {existing_user['id']}")
            logger.info(f"Current feedback type: {type(existing_user['feedback'])}")
            logger.info(f"Current feedback value: {existing_user['feedback']}")
            
            # User already in waitlist, update feedback if provided
            if new_feedback:
                logger.info(f"Attempting to update with new feedback: {new_feedback}")
                try:
                    # Here's where the issue might be - we need to handle None feedback
                    if existing_user['feedback'] is None:
                        updated_feedback = new_feedback
                    else:
                        updated_feedback = f"{existing_user['feedback']}\n\nAdditional feedback ({datetime.now().strftime('%Y-%m-%d')}): {new_feedback}"
                    
                    logger.info(f"Updated feedback to set: {updated_feedback}")
                    
                    cur.execute(
                        'UPDATE waitlist SET feedback = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
                        (updated_feedback, existing_user['id'])
                    )
                    conn.commit()
                    return {
                        'status': 'already_joined',
                        'message': 'You are already on our waiting list. Thank you for your additional feedback!'
                    }
                except Exception as e:
                    logger.error(f"Error updating feedback: {e}")
                    conn.rollback()
                    return {
                        'error': 'An error occurred while processing your request'
                    }
            else:
                logger.info("No new feedback provided")
                return {
                    'status': 'already_joined',
                    'message': 'You are already on our waiting list. We\'ll notify you when we\'re ready!'
                }
        else:
            logger.info(f"User not found in the database with hash: {email_hash}")
            
            # Debug: Check if the email exists with any hash
            cur.execute('SELECT id, email, email_hash FROM waitlist WHERE email = %s', (test_email,))
            direct_match = cur.fetchone()
            
            if direct_match:
                logger.info(f"User found by direct email match. ID: {direct_match['id']}")
                logger.info(f"Stored hash: {direct_match['email_hash']}")
                logger.info(f"Current hash: {email_hash}")
                logger.info(f"Hashes match: {direct_match['email_hash'] == email_hash}")
            else:
                logger.info(f"No direct email match found for: {test_email}")
            
            return {
                'error': 'User not found'
            }
                
    except Exception as e:
        logger.error(f"Exception in test: {e}")
        if conn:
            conn.rollback()
        return {
            'error': f'An internal server error occurred: {str(e)}'
        }
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

def create_test_user(email, company=None, feedback=None):
    """Create a test user for testing."""
    email_hash = hash_email(email)
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if the user already exists
        cur.execute('SELECT id FROM waitlist WHERE email_hash = %s', (email_hash,))
        existing = cur.fetchone()
        
        if existing:
            logger.info(f"Test user {email} already exists with ID: {existing['id']}")
            
            # Update user with specified values
            if company is not None or feedback is not None:
                update_fields = []
                update_values = []
                
                if company is not None:
                    update_fields.append("company = %s")
                    update_values.append(company)
                    
                if feedback is not None:
                    update_fields.append("feedback = %s")
                    update_values.append(feedback)
                
                update_values.append(existing['id'])
                
                sql = f"UPDATE waitlist SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                cur.execute(sql, update_values)
                conn.commit()
                logger.info("Updated existing test user")
            
            return existing['id']
        else:
            # Insert the test user
            cur.execute(
                'INSERT INTO waitlist (email, email_hash, company, feedback) VALUES (%s, %s, %s, %s) RETURNING id',
                (email, email_hash, company, feedback)
            )
            conn.commit()
            user_id = cur.fetchone()['id']
            logger.info(f"Created test user {email} with ID: {user_id}")
            
            # Verify the insert by retrieving the record
            cur.execute('SELECT id, email, email_hash FROM waitlist WHERE id = %s', (user_id,))
            verification = cur.fetchone()
            logger.info(f"Verification - ID: {verification['id']}, Email: {verification['email']}, Hash: {verification['email_hash']}")
            
            return user_id
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def modify_waitlist_bp():
    """Test the actual code from the waitlist_bp route with a fixed version."""
    # Simulate a request with an existing user
    email = 'test@example.com'
    new_feedback = "New feedback from modified test"
    
    # Hash email for secure lookup
    email_hash = hash_email(email)
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email already exists
        cur.execute('SELECT id, feedback FROM waitlist WHERE email_hash = %s', (email_hash,))
        existing_user = cur.fetchone()
        
        if existing_user:
            # User already in waitlist, update feedback if provided
            if new_feedback:
                # Concatenate new feedback with existing feedback
                # The issue might be here - ensure existing_user['feedback'] is properly handled
                current_feedback = existing_user['feedback'] or ""  # Convert None to empty string
                
                if current_feedback:
                    updated_feedback = f"{current_feedback}\n\nAdditional feedback ({datetime.now().strftime('%Y-%m-%d')}): {new_feedback}"
                else:
                    updated_feedback = new_feedback
                
                cur.execute(
                    'UPDATE waitlist SET feedback = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
                    (updated_feedback, existing_user['id'])
                )
                conn.commit()
                logger.info("Successfully updated user feedback with modified code")
                return True
    except Exception as e:
        logger.error(f"Error in modified test: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    
    return False

def test_existing_user_with_null_feedback():
    """Test the specific case of an existing user with NULL feedback."""
    # Create a user with explicit NULL feedback
    test_email = 'null_feedback@example.com'
    user_id = create_test_user(test_email, 'Test Company', None)
    
    if not user_id:
        logger.error("Failed to create/update test user")
        return False
    
    # Now simulate the user submitting again with new feedback
    result = test_with_existing_user(test_email, "New feedback for previously NULL feedback user")
    
    logger.info(f"Result of test: {result}")
    return 'error' not in result

def test_existing_user_with_empty_feedback():
    """Test the specific case of an existing user with empty string feedback."""
    # Create a user with empty string feedback
    test_email = 'empty_feedback@example.com'
    user_id = create_test_user(test_email, 'Test Company', '')
    
    if not user_id:
        logger.error("Failed to create/update test user")
        return False
    
    # Now simulate the user submitting again with new feedback
    result = test_with_existing_user(test_email, "New feedback for previously empty feedback user")
    
    logger.info(f"Result of test: {result}")
    return 'error' not in result

def test_existing_user_with_feedback():
    """Test the case of an existing user with previous feedback."""
    # Create a user with existing feedback
    test_email = 'has_feedback@example.com'
    user_id = create_test_user(test_email, 'Test Company', 'Existing feedback')
    
    if not user_id:
        logger.error("Failed to create/update test user")
        return False
    
    # Now simulate the user submitting again with new feedback
    result = test_with_existing_user(test_email, "Additional feedback from user with existing feedback")
    
    logger.info(f"Result of test: {result}")
    return 'error' not in result

if __name__ == "__main__":
    logger.info("=== TESTING EXISTING USER WITH NULL FEEDBACK ===")
    null_feedback_success = test_existing_user_with_null_feedback()
    
    logger.info("\n=== TESTING EXISTING USER WITH EMPTY FEEDBACK ===")
    empty_feedback_success = test_existing_user_with_empty_feedback()
    
    logger.info("\n=== TESTING EXISTING USER WITH EXISTING FEEDBACK ===")
    has_feedback_success = test_existing_user_with_feedback()
    
    logger.info("\n=== TESTING THE MODIFIED WAITLIST CODE ===")
    modified_code_success = modify_waitlist_bp()
    
    if null_feedback_success and empty_feedback_success and has_feedback_success and modified_code_success:
        logger.info("\nAll tests completed successfully")
        sys.exit(0)
    else:
        logger.error("\nSome tests failed:")
        logger.error(f"  - NULL feedback test: {'PASSED' if null_feedback_success else 'FAILED'}")
        logger.error(f"  - Empty feedback test: {'PASSED' if empty_feedback_success else 'FAILED'}")
        logger.error(f"  - Existing feedback test: {'PASSED' if has_feedback_success else 'FAILED'}")
        logger.error(f"  - Modified code test: {'PASSED' if modified_code_success else 'FAILED'}")
        sys.exit(1) 