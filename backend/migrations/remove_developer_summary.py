"""
Migration script to remove the developer_summary column from the github_analysis table.
"""

import os
import psycopg2
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migration():
    """Execute the migration to remove developer_summary column."""
    # Get database connection parameters from environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    # Check if all required environment variables are set
    if not all([db_host, db_name, db_user, db_password]):
        logger.error("Missing required database connection environment variables.")
        logger.error("Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD")
        return False
    
    conn = None
    try:
        # Connect to the database
        logger.info(f"Connecting to database {db_host}:{db_port}/{db_name} as {db_user}")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Check if the developer_summary column exists
        logger.info("Checking if developer_summary column exists in github_analysis table")
        cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'github_analysis' 
        AND column_name = 'developer_summary'
        """)
        
        if cur.fetchone():
            # Column exists, so remove it
            logger.info("Removing developer_summary column from github_analysis table")
            cur.execute("ALTER TABLE github_analysis DROP COLUMN developer_summary")
            conn.commit()
            logger.info("Successfully removed developer_summary column")
        else:
            logger.info("developer_summary column does not exist, no action needed")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    logger.info("Starting migration to remove developer_summary column")
    success = run_migration()
    if success:
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed") 