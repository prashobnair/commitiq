#!/usr/bin/env python3
"""
Script to reset PostgreSQL sequences to avoid primary key conflicts.
"""

import psycopg2
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# PostgreSQL connection parameters
PG_HOST = "github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT = 5432
PG_USER = "commitiq_github"
PG_PASSWORD = "6LH9GHzQfw3UDaoSBTNa"
PG_DB = "github_data"

def reset_sequences():
    """Reset PostgreSQL sequences for all tables."""
    try:
        # Connect to PostgreSQL
        logger.info(f"Connecting to PostgreSQL database at {PG_HOST}:{PG_PORT}/{PG_DB}")
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DB
        )
        
        with conn.cursor() as cursor:
            # Reset score_users sequence
            cursor.execute("""
            SELECT setval(pg_get_serial_sequence('score_users', 'id'), 
                         (SELECT COALESCE(MAX(id), 0) + 1 FROM score_users), 
                         false)
            """)
            result = cursor.fetchone()
            logger.info(f"Users sequence reset to: {result[0]}")
            
            # Reset score_metrics sequence
            cursor.execute("""
            SELECT setval(pg_get_serial_sequence('score_metrics', 'id'), 
                         (SELECT COALESCE(MAX(id), 0) + 1 FROM score_metrics), 
                         false)
            """)
            result = cursor.fetchone()
            logger.info(f"Metrics sequence reset to: {result[0]}")
            
            # Reset score_repositories sequence
            cursor.execute("""
            SELECT setval(pg_get_serial_sequence('score_repositories', 'id'), 
                         (SELECT COALESCE(MAX(id), 0) + 1 FROM score_repositories), 
                         false)
            """)
            result = cursor.fetchone()
            logger.info(f"Repositories sequence reset to: {result[0]}")
        
        conn.commit()
        logger.info("All sequences reset successfully")
        
    except Exception as e:
        logger.error(f"Error resetting sequences: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    reset_sequences() 