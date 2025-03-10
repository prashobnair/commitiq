#!/usr/bin/env python3
"""
Script to check the PostgreSQL database.
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

def check_database():
    """Check the PostgreSQL database."""
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
            # Check score_users table
            cursor.execute("SELECT COUNT(*) FROM score_users")
            count = cursor.fetchone()[0]
            logger.info(f"Total users in database: {count}")
            
            # Check score_metrics table
            cursor.execute("SELECT COUNT(*) FROM score_metrics")
            count = cursor.fetchone()[0]
            logger.info(f"Total metrics in database: {count}")
            
            # Check score_repositories table
            cursor.execute("SELECT COUNT(*) FROM score_repositories")
            count = cursor.fetchone()[0]
            logger.info(f"Total repositories in database: {count}")
            
            # Check top users by impact score
            cursor.execute("""
            SELECT username, impact_score 
            FROM score_users 
            ORDER BY impact_score DESC 
            LIMIT 10
            """)
            logger.info("Top 10 users by impact score:")
            logger.info(f"{'Username':<20} {'Impact Score':<15}")
            logger.info("-" * 35)
            for row in cursor.fetchall():
                logger.info(f"{row[0]:<20} {row[1]:<15.2f}")
        
    except Exception as e:
        logger.error(f"Error checking database: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_database() 