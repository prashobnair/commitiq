#!/usr/bin/env python3
"""
GitHub Test User Collector for RDS PostgreSQL

This script collects a sample of 10,000 recent GitHub users for benchmarking purposes.
It uses parallel processing and stores data in a test_github_users table.
"""

import argparse
import logging
import time
import sys
import os
import atexit
from datetime import datetime
from dotenv import load_dotenv

from github_api import fetch_users_parallel
from db_postgres import init_db_pool, close_db_pool, get_db_connection, release_connection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('github_test_collection.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
START_USER_ID = 202327550  # 500k before reference recent user
TARGET_SAMPLE_SIZE = 10000
DEFAULT_BATCH_SIZE = 100
DEFAULT_WORKERS = 5

def init_test_db():
    """Initialize the test database schema."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_github_users (
            id INTEGER PRIMARY KEY,
            login VARCHAR(255) NOT NULL,
            type VARCHAR(50),
            site_admin BOOLEAN,
            name VARCHAR(255),
            company VARCHAR(255),
            blog VARCHAR(255),
            location VARCHAR(255),
            email VARCHAR(255),
            hireable BOOLEAN,
            bio TEXT,
            twitter_username VARCHAR(255),
            public_repos INTEGER,
            public_gists INTEGER,
            followers INTEGER,
            following INTEGER,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("Test database schema initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing test database schema: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            release_connection(conn)

def insert_test_users(users):
    """Insert users into the test database."""
    from psycopg2.extras import execute_values
    
    if not users:
        return 0
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data for batch insert
        values = [(
            user['id'], user['login'], user['type'], user['site_admin'],
            user.get('name'), user.get('company'), user.get('blog'),
            user.get('location'), user.get('email'), user.get('hireable'),
            user.get('bio'), user.get('twitter_username'),
            user.get('public_repos'), user.get('public_gists'),
            user.get('followers'), user.get('following'),
            user.get('created_at'), user.get('updated_at')
        ) for user in users]
        
        # Use execute_values for efficient batch insert
        execute_values(
            cursor,
            '''
            INSERT INTO test_github_users 
            (id, login, type, site_admin, name, company, blog, location, email,
             hireable, bio, twitter_username, public_repos, public_gists,
             followers, following, created_at, updated_at) 
            VALUES %s
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            ''',
            values,
            template='(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        )
        
        # Get number of inserted rows
        inserted_rows = cursor.fetchall()
        inserted_count = len(inserted_rows)
        
        conn.commit()
        return inserted_count
    except Exception as e:
        logger.error(f"Error inserting test users: {e}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            release_connection(conn)

def get_test_user_count():
    """Get the current count of test users."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM test_github_users')
        result = cursor.fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting test user count: {e}")
        return 0
    finally:
        if conn:
            release_connection(conn)

def main():
    """Main function to collect test sample of GitHub users."""
    # Initialize the database connection pool
    try:
        init_db_pool(min_conn=1, max_conn=DEFAULT_WORKERS)
        atexit.register(close_db_pool)
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        sys.exit(1)
    
    # Initialize the test database schema
    try:
        init_test_db()
    except Exception as e:
        logger.error(f"Failed to initialize test database schema: {e}")
        sys.exit(1)
    
    logger.info(f"Starting GitHub test user collection from ID: {START_USER_ID}")
    logger.info(f"Target sample size: {TARGET_SAMPLE_SIZE} users")
    
    # Track progress
    start_time = time.time()
    last_report_time = start_time
    total_users_fetched = 0
    total_users_inserted = 0
    total_batches_processed = 0
    
    try:
        # Fetch users in parallel
        for batch in fetch_users_parallel(
            since_id=START_USER_ID,
            max_workers=DEFAULT_WORKERS,
            batch_size=DEFAULT_BATCH_SIZE,
            max_batches=None  # Will stop based on user count instead
        ):
            # Check if we've reached our target
            if total_users_inserted >= TARGET_SAMPLE_SIZE:
                break
                
            # Insert users into the database
            batch_size = len(batch)
            total_users_fetched += batch_size
            inserted = insert_test_users(batch)
            total_users_inserted += inserted
            total_batches_processed += 1
            
            # Report progress every 5 seconds
            current_time = time.time()
            if current_time - last_report_time >= 5:
                elapsed = current_time - start_time
                users_per_second = total_users_fetched / elapsed if elapsed > 0 else 0
                
                logger.info(
                    f"Progress: {total_users_inserted}/{TARGET_SAMPLE_SIZE} users collected "
                    f"({(total_users_inserted/TARGET_SAMPLE_SIZE*100):.1f}%), "
                    f"{users_per_second:.2f} users/sec"
                )
                last_report_time = current_time
                
            # Break if we've reached our target
            if total_users_inserted >= TARGET_SAMPLE_SIZE:
                break
                
    except KeyboardInterrupt:
        logger.info("Test user collection interrupted by user")
    except Exception as e:
        logger.error(f"Error during test user collection: {e}", exc_info=True)
    finally:
        # Final report
        end_time = time.time()
        elapsed = end_time - start_time
        final_user_count = get_test_user_count()
        
        logger.info(f"GitHub test user collection completed in {elapsed:.2f} seconds")
        logger.info(f"Total batches processed: {total_batches_processed}")
        logger.info(f"Total users fetched: {total_users_fetched}")
        logger.info(f"Final test database size: {final_user_count} users")
        
        if elapsed > 0:
            logger.info(f"Average processing rate: {total_users_fetched / elapsed:.2f} users/sec")

if __name__ == "__main__":
    main() 