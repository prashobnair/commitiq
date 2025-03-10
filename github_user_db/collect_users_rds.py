#!/usr/bin/env python3
"""
GitHub User Collector for RDS PostgreSQL

This script collects basic information about GitHub users and stores it in a PostgreSQL database.
It respects GitHub API rate limits and supports parallel processing and resumable operations.
Designed to run on EC2 instances and store data in RDS PostgreSQL.
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
from db_postgres import (
    init_db_pool, init_db, insert_users, get_last_user_id, 
    get_user_count, close_db_pool
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('github_user_collection.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Collect GitHub users and store them in a PostgreSQL database.')
    
    # GitHub API parameters
    parser.add_argument('--since', type=int, default=None, 
                        help='User ID to start from (default: resume from last run)')
    parser.add_argument('--workers', type=int, default=5, 
                        help='Number of parallel workers (default: 5)')
    parser.add_argument('--batch-size', type=int, default=100, 
                        help='Number of users per API request (default: 100, max: 100)')
    parser.add_argument('--max-batches', type=int, default=None, 
                        help='Maximum number of batches to fetch (default: unlimited)')
    parser.add_argument('--report-interval', type=int, default=10, 
                        help='Interval in seconds to report progress (default: 10)')
    
    # Database connection parameters (can also be set via environment variables)
    parser.add_argument('--db-host', type=str, default=os.getenv('DB_HOST'),
                        help='PostgreSQL database host (default: from DB_HOST env var)')
    parser.add_argument('--db-port', type=str, default=os.getenv('DB_PORT', '5432'),
                        help='PostgreSQL database port (default: from DB_PORT env var or 5432)')
    parser.add_argument('--db-name', type=str, default=os.getenv('DB_NAME'),
                        help='PostgreSQL database name (default: from DB_NAME env var)')
    parser.add_argument('--db-user', type=str, default=os.getenv('DB_USER'),
                        help='PostgreSQL database user (default: from DB_USER env var)')
    parser.add_argument('--db-password', type=str, default=os.getenv('DB_PASSWORD'),
                        help='PostgreSQL database password (default: from DB_PASSWORD env var)')
    parser.add_argument('--min-conn', type=int, default=1,
                        help='Minimum number of database connections in the pool (default: 1)')
    parser.add_argument('--max-conn', type=int, default=10,
                        help='Maximum number of database connections in the pool (default: 10)')
    
    return parser.parse_args()

def setup_environment(args):
    """Set up environment variables for database connection."""
    if args.db_host:
        os.environ['DB_HOST'] = args.db_host
    if args.db_port:
        os.environ['DB_PORT'] = args.db_port
    if args.db_name:
        os.environ['DB_NAME'] = args.db_name
    if args.db_user:
        os.environ['DB_USER'] = args.db_user
    if args.db_password:
        os.environ['DB_PASSWORD'] = args.db_password

def main():
    """Main function to collect GitHub users."""
    args = parse_args()
    
    # Set up environment variables
    setup_environment(args)
    
    # Initialize the database connection pool
    try:
        init_db_pool(min_conn=args.min_conn, max_conn=args.max_conn)
        # Register cleanup function to close the connection pool
        atexit.register(close_db_pool)
    except ValueError as e:
        logger.error(f"Database configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        sys.exit(1)
    
    # Initialize the database schema
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        sys.exit(1)
    
    # Get the starting point
    since_id = args.since if args.since is not None else get_last_user_id()
    
    logger.info(f"Starting GitHub user collection from ID: {since_id}")
    logger.info(f"Using {args.workers} parallel workers with batch size {args.batch_size}")
    
    # Track progress
    start_time = time.time()
    last_report_time = start_time
    initial_user_count = get_user_count()
    total_users_fetched = 0
    total_users_inserted = 0
    total_batches_processed = 0
    
    try:
        # Fetch users in parallel
        for batch in fetch_users_parallel(
            since_id=since_id,
            max_workers=args.workers,
            batch_size=args.batch_size,
            max_batches=args.max_batches
        ):
            # Insert users into the database
            batch_size = len(batch)
            total_users_fetched += batch_size
            inserted = insert_users(batch)
            total_users_inserted += inserted
            total_batches_processed += 1
            
            # Report progress at intervals
            current_time = time.time()
            if current_time - last_report_time >= args.report_interval:
                elapsed = current_time - start_time
                users_per_second = total_users_fetched / elapsed if elapsed > 0 else 0
                
                logger.info(
                    f"Progress: {total_batches_processed} batches, "
                    f"{total_users_fetched} users fetched, "
                    f"{total_users_inserted} new users inserted, "
                    f"{users_per_second:.2f} users/sec"
                )
                last_report_time = current_time
                
    except KeyboardInterrupt:
        logger.info("User collection interrupted by user")
    except Exception as e:
        logger.error(f"Error during user collection: {e}", exc_info=True)
    finally:
        # Final report
        end_time = time.time()
        elapsed = end_time - start_time
        final_user_count = get_user_count()
        users_added = final_user_count - initial_user_count
        
        logger.info(f"GitHub user collection completed in {elapsed:.2f} seconds")
        logger.info(f"Total batches processed: {total_batches_processed}")
        logger.info(f"Total users fetched: {total_users_fetched}")
        logger.info(f"Total new users added to database: {users_added}")
        logger.info(f"Current database size: {final_user_count} users")
        
        if elapsed > 0:
            logger.info(f"Average processing rate: {total_users_fetched / elapsed:.2f} users/sec")

if __name__ == "__main__":
    main() 