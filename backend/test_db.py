#!/usr/bin/env python3
"""
Test script to verify database connectivity and table creation.
Run this script to ensure the database connection is working properly before starting the application.
"""
import os
import logging
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_db_connection():
    """Test connection to the PostgreSQL database."""
    conn = None
    try:
        # Get database connection parameters from environment variables
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        
        # Check if all required parameters are set
        if not all([db_host, db_name, db_user, db_password]):
            logger.error("Missing required database parameters in .env file")
            logger.error("Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD")
            return False
            
        logger.info(f"Attempting to connect to database at {db_host}:{db_port}/{db_name}")
        
        # Try to establish connection
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            cursor_factory=RealDictCursor
        )
        
        # Test creating a cursor
        cur = conn.cursor()
        
        # Test executing a simple query
        cur.execute("SELECT version()")
        version = cur.fetchone()
        
        logger.info(f"Connected to PostgreSQL server:")
        logger.info(f"Version: {version['version']}")
        
        # Test if waitlist table exists, create it if it doesn't
        cur.execute("SELECT to_regclass('public.waitlist') IS NOT NULL AS exists")
        table_exists = cur.fetchone()['exists']
        
        if table_exists:
            logger.info("Waitlist table already exists in the database")
            
            # Get count of records in waitlist table
            cur.execute("SELECT COUNT(*) AS count FROM waitlist")
            count = cur.fetchone()['count']
            logger.info(f"Current waitlist count: {count}")
        else:
            logger.info("Waitlist table does not exist, attempting to create it")
            
            # Create waitlist table
            cur.execute('''
            CREATE TABLE IF NOT EXISTS waitlist (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                email_hash TEXT NOT NULL,
                company TEXT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create index on email_hash for faster lookups
            cur.execute('CREATE INDEX IF NOT EXISTS idx_email_hash ON waitlist(email_hash)')
            
            conn.commit()
            logger.info("Waitlist table created successfully")
        
        return True
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    success = test_db_connection()
    if success:
        logger.info("Database connection test completed successfully")
        sys.exit(0)
    else:
        logger.error("Database connection test failed")
        sys.exit(1) 