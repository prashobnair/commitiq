#!/usr/bin/env python3
"""
Database initialization script for CommitIQ.
This script creates all required tables when deploying to Render.
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

def init_database():
    """Initialize the database by creating all required tables."""
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
            logger.error("Missing required database parameters in environment variables")
            logger.error("Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD")
            return False
            
        logger.info(f"Connecting to database at {db_host}:{db_port}/{db_name}")
        
        # Establish connection
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password,
            cursor_factory=RealDictCursor
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Create waitlist table
        logger.info("Creating waitlist table if it doesn't exist")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS waitlist (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            github_username TEXT,
            email_hash TEXT UNIQUE,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token TEXT,
            browser_info TEXT,
            ip_address TEXT,
            referral_source TEXT
        )
        ''')
        
        # Create github_analysis table
        logger.info("Creating github_analysis table if it doesn't exist")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS github_analysis (
            id SERIAL PRIMARY KEY,
            github_username TEXT NOT NULL,
            analyzer_email TEXT,
            impact_score NUMERIC(5,2),
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analyzed_from_ip TEXT,
            user_agent TEXT,
            is_successful BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
        ''')
        
        # Create index on github_username
        cur.execute('CREATE INDEX IF NOT EXISTS idx_github_analysis_username ON github_analysis(github_username)')
        
        # Create github_analysis_details table
        logger.info("Creating github_analysis_details table if it doesn't exist")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS github_analysis_details (
            id SERIAL PRIMARY KEY,
            analysis_id INTEGER NOT NULL REFERENCES github_analysis(id) ON DELETE CASCADE,
            total_commits INTEGER,
            pull_requests INTEGER,
            issues_raised INTEGER,
            code_reviews INTEGER,
            consistency_score NUMERIC(5,2),
            project_impact_score NUMERIC(5,2),
            strengths JSONB,
            considerations JSONB,
            top_languages JSONB,
            top_repositories JSONB,
            full_analysis_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create shared_analysis table
        logger.info("Creating shared_analysis table if it doesn't exist")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS shared_analysis (
            id SERIAL PRIMARY KEY,
            share_id TEXT UNIQUE NOT NULL,
            github_username TEXT NOT NULL,
            analysis_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_public BOOLEAN DEFAULT TRUE,
            password_hash TEXT,
            creator_ip TEXT,
            view_count INTEGER DEFAULT 0
        )
        ''')
        
        # Create analysis_downloads table
        logger.info("Creating analysis_downloads table if it doesn't exist")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS analysis_downloads (
            id SERIAL PRIMARY KEY,
            download_id TEXT UNIQUE NOT NULL,
            github_username TEXT NOT NULL,
            analysis_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            download_format TEXT NOT NULL,
            is_downloaded BOOLEAN DEFAULT FALSE,
            downloaded_at TIMESTAMP,
            creator_ip TEXT
        )
        ''')
        
        # Commit the transaction
        conn.commit()
        logger.info("Database initialization completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    success = init_database()
    if success:
        logger.info("Database initialization completed successfully!")
        sys.exit(0)
    else:
        logger.error("Database initialization failed")
        sys.exit(1) 