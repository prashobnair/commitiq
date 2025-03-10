#!/usr/bin/env python3
"""
Batch Data Collection Script for GitHub User Metrics

This script collects GitHub metrics for a batch of users from the database,
skipping users that already have data.
"""

import os
import sys
import json
import logging
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
import random

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.app.services import aggregate_user_data, calculate_impact_score, GitHubGraphQL, fetch_all_data
from db_utils import (
    sqlite_connection, postgres_connection, 
    get_existing_users_sqlite, get_existing_users_postgres,
    sample_users_sqlite, sample_users_postgres,
    DEFAULT_PG_HOST, DEFAULT_PG_PORT, DEFAULT_PG_USER, 
    DEFAULT_PG_PASSWORD, DEFAULT_PG_DB
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "batch_collection.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path(__file__).parent / "data"
METRICS_DB = OUTPUT_DIR / "metrics_analysis.db"
GITHUB_DB = Path(__file__).parent.parent / "github_user_db" / "data" / "github_users.db"
BATCH_SIZE = 1000
MAX_WORKERS = 16
PROGRESS_FILE = OUTPUT_DIR / "batch_progress.json"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Collect GitHub metrics for a batch of users.')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'Number of users to process (default: {BATCH_SIZE})')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help=f'Number of parallel workers (default: {MAX_WORKERS})')
    parser.add_argument('--github-db', type=str, default=str(GITHUB_DB),
                        help=f'Path to GitHub users database (default: {GITHUB_DB})')
    parser.add_argument('--metrics-db', type=str, default=str(METRICS_DB),
                        help=f'Path to metrics database (default: {METRICS_DB})')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from the last checkpoint')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--use-postgres', action='store_true',
                        help='Use PostgreSQL instead of SQLite')
    parser.add_argument('--pg-host', type=str, default=DEFAULT_PG_HOST,
                        help=f'PostgreSQL host (default: {DEFAULT_PG_HOST})')
    parser.add_argument('--pg-port', type=int, default=DEFAULT_PG_PORT,
                        help=f'PostgreSQL port (default: {DEFAULT_PG_PORT})')
    parser.add_argument('--pg-user', type=str, default=DEFAULT_PG_USER,
                        help=f'PostgreSQL username (default: {DEFAULT_PG_USER})')
    parser.add_argument('--pg-password', type=str, default=DEFAULT_PG_PASSWORD,
                        help=f'PostgreSQL password (default: {DEFAULT_PG_PASSWORD})')
    parser.add_argument('--pg-db', type=str, default=DEFAULT_PG_DB,
                        help=f'PostgreSQL database name (default: {DEFAULT_PG_DB})')
    return parser.parse_args()

def init_metrics_db(db_path):
    """
    Initialize the metrics database if it doesn't exist.
    
    Args:
        db_path: Path to metrics database
    """
    if os.path.exists(db_path):
        logger.info(f"Metrics database already exists at {db_path}")
        return
    
    logger.info(f"Creating metrics database at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        github_id INTEGER,
        name TEXT,
        email TEXT,
        company TEXT,
        location TEXT,
        bio TEXT,
        followers INTEGER,
        following INTEGER,
        impact_score REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create metrics table
    cursor.execute('''
    CREATE TABLE metrics (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        pulls INTEGER,
        commits INTEGER,
        issues INTEGER,
        reviews INTEGER,
        repos_impact REAL,
        consistency REAL,
        repo_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create repositories table
    cursor.execute('''
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT,
        stars INTEGER,
        forks INTEGER,
        primary_language TEXT,
        technical_impact REAL,
        ecosystem_impact REAL,
        total_impact REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create index on username
    cursor.execute('CREATE INDEX idx_username ON users(username)')
    
    conn.commit()
    conn.close()
    
    logger.info("Metrics database initialized successfully")

def get_existing_users(metrics_db_path, use_postgres=False, pg_params=None):
    """
    Get set of usernames that already have data in the metrics database.
    
    Args:
        metrics_db_path: Path to metrics database
        use_postgres: Whether to use PostgreSQL
        pg_params: PostgreSQL connection parameters
        
    Returns:
        Set of usernames
    """
    if use_postgres:
        if pg_params is None:
            pg_params = {}
        return get_existing_users_postgres(**pg_params)
    else:
        return get_existing_users_sqlite(metrics_db_path)

def sample_users(github_db_path, batch_size, existing_users=None, use_postgres=False, pg_params=None):
    """
    Sample users from the GitHub database with a distribution favoring later users,
    skipping users that already have data.
    
    Args:
        github_db_path: Path to GitHub users database
        batch_size: Number of users to sample
        existing_users: Set of usernames to skip
        use_postgres: Whether to use PostgreSQL
        pg_params: PostgreSQL connection parameters
        
    Returns:
        List of user dictionaries with 'id' and 'login' keys
    """
    if use_postgres:
        if pg_params is None:
            pg_params = {}
        return sample_users_postgres(batch_size=batch_size, existing_users=existing_users, **pg_params)
    else:
        return sample_users_sqlite(github_db_path, batch_size, existing_users)

def fetch_github_data(username, github_id=None):
    """
    Fetch GitHub data for a user with exponential backoff for rate limits.
    
    Args:
        username: GitHub username
        github_id: GitHub user ID
        
    Returns:
        Dictionary with user data or None if failed
    """
    max_retries = 5
    base_delay = 2  # seconds
    
    github_client = GitHubGraphQL()
    
    for attempt in range(1, max_retries + 1):
        try:
            # Fetch user data from GitHub API
            user_data = github_client.get_user_data(username)
            
            if user_data:
                # Add GitHub ID if available
                if github_id:
                    user_data['github_id'] = github_id
                
                # Add username to ensure it's in the result
                user_data['username'] = username
                
                return user_data
            else:
                logger.warning(f"No data returned for user {username} (attempt {attempt}/{max_retries})")
        except Exception as e:
            if "rate limit" in str(e).lower():
                # Handle rate limit with exponential backoff
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.warning(f"Rate limit hit for {username}, retrying in {delay:.2f}s (attempt {attempt}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"Error fetching data for {username}: {e}")
                # For non-rate-limit errors, we might still want to retry
                delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.warning(f"Retrying in {delay:.2f}s (attempt {attempt}/{max_retries})")
                time.sleep(delay)
    
    logger.error(f"Failed to fetch data for {username} after {max_retries} attempts")
    return None

def collect_user_data(username, user_id):
    """
    Collect GitHub metrics for a user.
    
    Args:
        username: GitHub username
        user_id: GitHub user ID
        
    Returns:
        Dictionary with user metrics or None if failed
    """
    logger.info(f"Collecting data for user {username} (ID: {user_id})")
    
    try:
        # Fetch raw data from GitHub API
        user_data = fetch_github_data(username, user_id)
        
        if not user_data:
            logger.error(f"Failed to fetch data for user {username}")
            return None
        
        # Save raw data to JSON file
        output_file = OUTPUT_DIR / f"{username}_metrics.json"
        with open(output_file, 'w') as f:
            json.dump(user_data, f, indent=2)
        
        logger.debug(f"Saved raw data for {username} to {output_file}")
        
        # Process the data
        processed_data = aggregate_user_data(user_data)
        
        # Calculate impact score
        impact_score = calculate_impact_score(processed_data)
        
        # Add impact score to processed data
        processed_data['impact_score'] = impact_score
        
        # Add username to ensure it's in the result
        if 'username' not in processed_data:
            processed_data['username'] = username
        
        # Add GitHub ID if available
        if user_id and 'github_id' not in processed_data:
            processed_data['github_id'] = user_id
        
        logger.info(f"Collected data for {username} with impact score {impact_score:.2f}")
        
        return processed_data
    
    except Exception as e:
        logger.error(f"Error collecting data for {username}: {e}", exc_info=True)
        return None

def store_user_data_sqlite(conn, user_data):
    """
    Store user data in SQLite database.
    
    Args:
        conn: SQLite connection
        user_data: User data dictionary
        
    Returns:
        User ID in the database
    """
    if 'username' not in user_data:
        logger.error(f"Missing username in user data: {user_data}")
        return None
    
    username = user_data['username']
    logger.debug(f"Storing data for user {username} in SQLite database")
    
    cursor = conn.cursor()
    
    try:
        # Insert user data
        cursor.execute('''
        INSERT INTO users (
            username, github_id, name, email, company, location, bio, 
            followers, following, impact_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username,
            user_data.get('github_id'),
            user_data.get('name'),
            user_data.get('email'),
            user_data.get('company'),
            user_data.get('location'),
            user_data.get('bio'),
            user_data.get('followers', 0),
            user_data.get('following', 0),
            user_data.get('impact_score', 0.0)
        ))
        
        user_id = cursor.lastrowid
        logger.debug(f"Inserted user {username} with ID {user_id}")
        
        # Insert metrics data
        cursor.execute('''
        INSERT INTO metrics (
            user_id, pulls, commits, issues, reviews, repos_impact, 
            consistency, repo_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            user_data.get('pulls', 0),
            user_data.get('commits', 0),
            user_data.get('issues', 0),
            user_data.get('reviews', 0),
            user_data.get('repos_impact', 0.0),
            user_data.get('consistency', 0.0),
            len(user_data.get('repositories', []))
        ))
        
        logger.debug(f"Inserted metrics for user {username}")
        
        # Insert repository data
        for repo in user_data.get('repositories', []):
            cursor.execute('''
            INSERT INTO repositories (
                user_id, name, stars, forks, primary_language, 
                technical_impact, ecosystem_impact, total_impact
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                repo.get('name'),
                repo.get('stars', 0),
                repo.get('forks', 0),
                repo.get('primary_language'),
                repo.get('technical_impact', 0.0),
                repo.get('ecosystem_impact', 0.0),
                repo.get('total_impact', 0.0)
            ))
        
        logger.debug(f"Inserted {len(user_data.get('repositories', []))} repositories for user {username}")
        
        conn.commit()
        logger.info(f"Stored data for user {username} in database")
        
        return user_id
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing data for user {username}: {e}", exc_info=True)
        return None

def store_user_data_postgres(conn, user_data):
    """
    Store user data in PostgreSQL database.
    
    Args:
        conn: PostgreSQL connection
        user_data: User data dictionary
        
    Returns:
        User ID in the database
    """
    if 'username' not in user_data:
        logger.error(f"Missing username in user data: {user_data}")
        return None
    
    username = user_data['username']
    logger.debug(f"Storing data for user {username} in PostgreSQL database")
    
    try:
        with conn.cursor() as cursor:
            # Insert user data
            cursor.execute('''
            INSERT INTO score_users (
                username, github_id, name, email, company, location, bio, 
                followers, following, impact_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (
                username,
                user_data.get('github_id'),
                user_data.get('name'),
                user_data.get('email'),
                user_data.get('company'),
                user_data.get('location'),
                user_data.get('bio'),
                user_data.get('followers', 0),
                user_data.get('following', 0),
                user_data.get('impact_score', 0.0)
            ))
            
            user_id = cursor.fetchone()[0]
            logger.debug(f"Inserted user {username} with ID {user_id}")
            
            # Insert metrics data
            cursor.execute('''
            INSERT INTO score_metrics (
                user_id, pulls, commits, issues, reviews, repos_impact, 
                consistency, repo_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                user_id,
                user_data.get('pulls', 0),
                user_data.get('commits', 0),
                user_data.get('issues', 0),
                user_data.get('reviews', 0),
                user_data.get('repos_impact', 0.0),
                user_data.get('consistency', 0.0),
                len(user_data.get('repositories', []))
            ))
            
            logger.debug(f"Inserted metrics for user {username}")
            
            # Insert repository data
            for repo in user_data.get('repositories', []):
                cursor.execute('''
                INSERT INTO score_repositories (
                    user_id, name, stars, forks, primary_language, 
                    technical_impact, ecosystem_impact, total_impact
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    user_id,
                    repo.get('name'),
                    repo.get('stars', 0),
                    repo.get('forks', 0),
                    repo.get('primary_language'),
                    repo.get('technical_impact', 0.0),
                    repo.get('ecosystem_impact', 0.0),
                    repo.get('total_impact', 0.0)
                ))
            
            logger.debug(f"Inserted {len(user_data.get('repositories', []))} repositories for user {username}")
            
            conn.commit()
            logger.info(f"Stored data for user {username} in database")
            
            return user_id
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing data for user {username}: {e}", exc_info=True)
        return None

def store_user_data(conn, user_data, use_postgres=False):
    """
    Store user data in database.
    
    Args:
        conn: Database connection
        user_data: User data dictionary
        use_postgres: Whether to use PostgreSQL
        
    Returns:
        User ID in the database
    """
    if use_postgres:
        return store_user_data_postgres(conn, user_data)
    else:
        return store_user_data_sqlite(conn, user_data)

def save_progress(processed_users, results):
    """
    Save progress to a file.
    
    Args:
        processed_users: List of processed usernames
        results: Dictionary of results by username
    """
    progress = {
        'timestamp': datetime.now().isoformat(),
        'processed_users': processed_users,
        'results': results
    }
    
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)
    
    logger.info(f"Saved progress to {PROGRESS_FILE}")

def load_progress():
    """
    Load progress from a file.
    
    Returns:
        Tuple of (processed_users, results)
    """
    if not os.path.exists(PROGRESS_FILE):
        logger.info(f"No progress file found at {PROGRESS_FILE}")
        return [], {}
    
    try:
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
        
        processed_users = progress.get('processed_users', [])
        results = progress.get('results', {})
        
        logger.info(f"Loaded progress for {len(processed_users)} users from {PROGRESS_FILE}")
        
        return processed_users, results
    
    except Exception as e:
        logger.error(f"Error loading progress: {e}")
        return [], {}

def generate_summary(results):
    """
    Generate a summary of the batch results.
    
    Args:
        results: Dictionary of results by username
        
    Returns:
        Dictionary with summary statistics
    """
    total_users = len(results)
    successful_users = sum(1 for r in results.values() if r is not None)
    failed_users = total_users - successful_users
    
    # Calculate average metrics for successful users
    avg_pulls = 0
    avg_commits = 0
    avg_issues = 0
    avg_reviews = 0
    avg_repos = 0
    avg_impact = 0.0
    
    if successful_users > 0:
        successful_results = [r for r in results.values() if r is not None]
        
        avg_pulls = sum(r.get('pulls', 0) for r in successful_results) / successful_users
        avg_commits = sum(r.get('commits', 0) for r in successful_results) / successful_users
        avg_issues = sum(r.get('issues', 0) for r in successful_results) / successful_users
        avg_reviews = sum(r.get('reviews', 0) for r in successful_results) / successful_users
        avg_repos = sum(len(r.get('repositories', [])) for r in successful_results) / successful_users
        avg_impact = sum(r.get('impact_score', 0.0) for r in successful_results) / successful_users
    
    # Get top users by impact score
    top_users = []
    for username, result in results.items():
        if result is not None:
            top_users.append({
                'username': username,
                'impact_score': result.get('impact_score', 0.0),
                'pulls': result.get('pulls', 0),
                'commits': result.get('commits', 0),
                'issues': result.get('issues', 0),
                'reviews': result.get('reviews', 0),
                'repos': len(result.get('repositories', []))
            })
    
    top_users.sort(key=lambda x: x['impact_score'], reverse=True)
    top_users = top_users[:15]  # Keep top 15
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_users': total_users,
        'successful_users': successful_users,
        'failed_users': failed_users,
        'success_rate': successful_users / total_users if total_users > 0 else 0,
        'average_metrics': {
            'pulls': avg_pulls,
            'commits': avg_commits,
            'issues': avg_issues,
            'reviews': avg_reviews,
            'repositories': avg_repos,
            'impact_score': avg_impact
        },
        'top_users': top_users
    }
    
    # Save summary to file
    summary_file = OUTPUT_DIR / "batch_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Saved batch summary to {summary_file}")
    
    # Print summary table
    logger.info(f"\nBatch Summary:")
    logger.info(f"Total users: {total_users}")
    logger.info(f"Successful: {successful_users} ({summary['success_rate']:.1%})")
    logger.info(f"Failed: {failed_users}")
    logger.info(f"\nAverage Metrics:")
    logger.info(f"Pulls: {avg_pulls:.1f}")
    logger.info(f"Commits: {avg_commits:.1f}")
    logger.info(f"Issues: {avg_issues:.1f}")
    logger.info(f"Reviews: {avg_reviews:.1f}")
    logger.info(f"Repositories: {avg_repos:.1f}")
    logger.info(f"Impact Score: {avg_impact:.2f}")
    
    if top_users:
        logger.info(f"\nTop Users by Impact Score:")
        logger.info(f"{'Username':<20} {'Impact':<8} {'Pulls':<8} {'Commits':<8} {'Issues':<8} {'Reviews':<8} {'Repos':<8}")
        logger.info(f"{'-'*70}")
        
        for user in top_users:
            logger.info(f"{user['username']:<20} {user['impact_score']:<8.2f} {user['pulls']:<8} {user['commits']:<8} "
                       f"{user['issues']:<8} {user['reviews']:<8} {user['repos']:<8}")
    
    return summary

def main():
    """Main function to collect GitHub metrics for a batch of users."""
    args = parse_args()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR.parent / "logs", exist_ok=True)
    
    # Initialize metrics database if using SQLite
    if not args.use_postgres:
        init_metrics_db(args.metrics_db)
    
    # PostgreSQL connection parameters
    pg_params = {
        'host': args.pg_host,
        'port': args.pg_port,
        'user': args.pg_user,
        'password': args.pg_password,
        'dbname': args.pg_db
    }
    
    # Verify database connection
    try:
        if args.use_postgres:
            with postgres_connection(**pg_params) as conn:
                logger.info("Successfully connected to PostgreSQL database")
        else:
            with sqlite_connection(args.metrics_db) as conn:
                logger.info("Successfully connected to SQLite database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    # Get existing users
    existing_users = get_existing_users(args.metrics_db, args.use_postgres, pg_params)
    logger.info(f"Found {len(existing_users)} existing users in the metrics database")
    
    # Load progress if resuming
    processed_users = []
    results = {}
    
    if args.resume:
        processed_users, results = load_progress()
        
        # Add processed users to existing users to skip them
        for username in processed_users:
            existing_users.add(username)
    
    # Sample users from GitHub database
    users = sample_users(args.github_db, args.batch_size, existing_users, args.use_postgres, pg_params)
    
    if not users:
        logger.error("No users to process")
        sys.exit(1)
    
    logger.info(f"Starting collection for {len(users)} users with {args.workers} workers")
    
    # Process users in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit tasks
        future_to_user = {
            executor.submit(collect_user_data, user['login'], user['id']): user['login']
            for user in users
        }
        
        # Process results as they complete
        for future in as_completed(future_to_user):
            username = future_to_user[future]
            
            try:
                result = future.result()
                results[username] = result
                processed_users.append(username)
                
                # Save progress periodically
                if len(processed_users) % 10 == 0:
                    save_progress(processed_users, results)
                
            except Exception as e:
                logger.error(f"Error processing user {username}: {e}")
                results[username] = None
                processed_users.append(username)
    
    # Save final progress
    save_progress(processed_users, results)
    
    # Store results in database
    if args.use_postgres:
        with postgres_connection(**pg_params) as conn:
            for username, result in results.items():
                if result is not None:
                    store_user_data(conn, result, True)
    else:
        with sqlite_connection(args.metrics_db) as conn:
            for username, result in results.items():
                if result is not None:
                    store_user_data(conn, result, False)
    
    # Generate summary
    summary = generate_summary(results)
    
    # Get final count of users in database
    if args.use_postgres:
        with postgres_connection(**pg_params) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM score_users')
                db_user_count = cursor.fetchone()[0]
    else:
        with sqlite_connection(args.metrics_db) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            db_user_count = cursor.fetchone()[0]
    
    logger.info(f"Final database user count: {db_user_count}")
    
    return summary

if __name__ == "__main__":
    main() 