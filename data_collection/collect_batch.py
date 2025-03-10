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
    parser.add_argument('--resume', action='store_true',
                        help='Resume from the last checkpoint')
    parser.add_argument('--github-db', type=str, default=str(GITHUB_DB),
                        help=f'Path to GitHub users database (default: {GITHUB_DB})')
    parser.add_argument('--metrics-db', type=str, default=str(METRICS_DB),
                        help=f'Path to metrics database (default: {METRICS_DB})')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='Skip users that already have data (default: True)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    return parser.parse_args()

def init_metrics_db(db_path):
    """Initialize the metrics database."""
    # Create parent directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
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
    CREATE TABLE IF NOT EXISTS metrics (
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
    CREATE TABLE IF NOT EXISTS repositories (
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
    
    # Create index on username for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON users(username)')
    
    conn.commit()
    logger.info(f"Metrics database initialized at {db_path}")
    return conn

def get_existing_users(metrics_db_path):
    """Get a set of usernames that already have data in the metrics database."""
    if not os.path.exists(metrics_db_path):
        return set()
    
    conn = sqlite3.connect(metrics_db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT username FROM users")
    existing_users = {row[0] for row in cursor.fetchall()}
    
    conn.close()
    
    logger.info(f"Found {len(existing_users)} existing users in metrics database")
    return existing_users

def sample_users(github_db_path, batch_size, existing_users=None):
    """
    Sample users from the GitHub database with a distribution favoring later users,
    skipping users that already have data.
    
    Args:
        github_db_path: Path to GitHub users database
        batch_size: Number of users to sample
        existing_users: Set of usernames to skip
        
    Returns:
        List of user dictionaries with 'id' and 'login' keys
    """
    if existing_users is None:
        existing_users = set()
    
    conn = sqlite3.connect(github_db_path)
    cursor = conn.cursor()
    
    # Get total user count and ID range
    cursor.execute('SELECT COUNT(*), MIN(id), MAX(id) FROM github_users')
    total_count, min_id, max_id = cursor.fetchone()
    
    logger.info(f"GitHub database contains {total_count:,} users with IDs from {min_id:,} to {max_id:,}")
    
    # Create a weighted distribution favoring later users
    # We'll divide the range into segments and sample more from later segments
    segments = 10
    segment_size = (max_id - min_id) // segments
    
    # Weights for each segment (increasing weights for later segments)
    # Later segments have higher probability
    weights = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5]
    total_weight = sum(weights)
    
    # Calculate how many users to sample from each segment
    segment_samples = []
    for weight in weights:
        segment_samples.append(int(batch_size * weight / total_weight))
    
    # Adjust to ensure we get exactly batch_size users
    while sum(segment_samples) < batch_size:
        segment_samples[-1] += 1
    
    users = []
    skipped_count = 0
    
    # Sample users from each segment
    for i in range(segments):
        segment_start = min_id + i * segment_size
        segment_end = segment_start + segment_size - 1 if i < segments - 1 else max_id
        segment_count = segment_samples[i]
        
        if segment_count > 0:
            # Get more users than needed to account for skipping existing users
            extra_factor = 2  # Get 2x more users than needed
            
            # Get random users from this segment
            cursor.execute('''
                SELECT id, login FROM github_users 
                WHERE id BETWEEN ? AND ?
                ORDER BY RANDOM() 
                LIMIT ?
            ''', (segment_start, segment_end, segment_count * extra_factor))
            
            segment_users = []
            for row in cursor.fetchall():
                user_id, username = row
                
                # Skip users that already have data
                if username in existing_users:
                    skipped_count += 1
                    continue
                
                segment_users.append({'id': user_id, 'login': username})
                
                # Stop once we have enough users for this segment
                if len(segment_users) >= segment_count:
                    break
            
            users.extend(segment_users)
            
            logger.info(f"Sampled {len(segment_users)} users from segment {i+1} (IDs {segment_start:,}-{segment_end:,})")
    
    conn.close()
    
    logger.info(f"Sampled {len(users)} users, skipped {skipped_count} existing users")
    
    # If we couldn't get enough users, log a warning
    if len(users) < batch_size:
        logger.warning(f"Could only sample {len(users)} users, fewer than requested {batch_size}")
    
    return users

def fetch_github_data(username, github_id=None):
    """Fetch GitHub data for a user."""
    logger.info(f"Fetching GitHub data for {username}...")
    
    max_retries = 5
    base_delay = 2  # Base delay in seconds
    
    for attempt in range(max_retries):
        try:
            # Call the GitHub API service
            response = fetch_all_data(username)
            
            # Check if the response contains errors related to rate limiting
            if isinstance(response, dict) and 'error' in response:
                error_msg = response['error']
                if 'rate limit' in error_msg.lower() or 'exceeded a secondary rate limit' in error_msg.lower():
                    # Calculate exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Rate limit exceeded. Retrying in {delay:.2f} seconds (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
            
            # Process the response
            if response and isinstance(response, dict) and not response.get('error'):
                return response
            else:
                error_msg = "Invalid response format. "
                if isinstance(response, dict) and response.get('error'):
                    error_msg += f" error: {response['error']}"
                raise ValueError(error_msg)
                
        except Exception as e:
            # If this is the last attempt, raise the exception
            if attempt == max_retries - 1:
                logger.error(f"Failed to fetch data for {username} after {max_retries} attempts: {str(e)}")
                raise
            
            # Otherwise, retry with exponential backoff
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Error fetching data for {username}, retrying in {delay:.2f} seconds: {str(e)}")
            time.sleep(delay)
    
    # This should not be reached due to the exception in the last attempt
    raise ValueError(f"Failed to fetch data for {username} after {max_retries} attempts")

def collect_user_data(username, user_id):
    """
    Collect data for a specific GitHub user.
    
    Args:
        username: GitHub username
        user_id: User ID in the database
        
    Returns:
        Dictionary with user metrics or error information
    """
    try:
        start_time = datetime.now()
        logger.info(f"Collecting data for GitHub user: {username} (ID: {user_id})")
        
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Fetch GitHub data
        logger.info(f"Fetching GitHub data for {username}...")
        github_data = fetch_github_data(username)
        
        if 'error' in github_data:
            logger.warning(f"Error fetching data for {username}: {github_data['error']}")
            return {
                'username': username,
                'user_id': user_id,
                'status': 'error',
                'error': github_data['error'],
                'timestamp': datetime.now().isoformat()
            }
        
        # Aggregate user data and calculate metrics
        logger.info(f"Aggregating data for {username}...")
        result = aggregate_user_data(username, github_data)
        
        # Calculate impact score
        impact_score = calculate_impact_score(result)
        result['impact_score'] = impact_score
        
        # Add user ID, timestamp and processing time
        result['user_id'] = user_id
        result['timestamp'] = datetime.now().isoformat()
        result['processing_time'] = (datetime.now() - start_time).total_seconds()
        result['status'] = 'success'
        
        # Ensure username is in the result
        if 'username' not in result:
            result['username'] = username
        
        # Save the result to a JSON file
        output_file = OUTPUT_DIR / f"{username}_metrics.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Successfully processed {username} in {result['processing_time']:.2f}s")
        return result
    
    except Exception as e:
        logger.error(f"Exception processing {username}: {str(e)}", exc_info=True)
        return {
            'username': username,
            'user_id': user_id,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def store_user_data(conn, user_data):
    """
    Store user data in the metrics database.
    
    Args:
        conn: Database connection
        user_data: User metrics dictionary
        
    Returns:
        User ID in the database
    """
    cursor = conn.cursor()
    
    try:
        # Begin transaction
        conn.execute('BEGIN TRANSACTION')
        
        # Extract user info
        username = user_data.get('username')
        if not username:
            logger.error("Missing username in user data")
            return None
            
        github_id = user_data.get('user_id')
        name = user_data.get('name')
        email = user_data.get('email')
        company = user_data.get('company')
        location = user_data.get('location')
        bio = user_data.get('bio')
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)
        impact_score = user_data.get('impact_score', 0)
        
        # Debug log
        logger.debug(f"Storing user data for {username} (GitHub ID: {github_id})")
        logger.debug(f"User info: name={name}, email={email}, company={company}, location={location}")
        logger.debug(f"Followers: {followers}, Following: {following}, Impact Score: {impact_score}")
        
        # Insert user
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (username, github_id, name, email, company, location, bio, followers, following, impact_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, github_id, name, email, company, location, bio, followers, following, impact_score))
        
        user_id = cursor.lastrowid
        logger.debug(f"Inserted user {username} with database ID: {user_id}")
        
        # Insert metrics
        contributions = user_data.get('contributions', {})
        pulls = contributions.get('pulls', 0)
        commits = contributions.get('commits', 0)
        issues = contributions.get('issues', 0)
        reviews = contributions.get('reviews', 0)
        repos_impact = contributions.get('repos_impact', 0)
        consistency = contributions.get('consistency', 0)
        
        # Extract repository count
        metrics = user_data.get('metrics', {})
        repo_count = len(metrics.get('repositories', []))
        
        logger.debug(f"Metrics for {username}: pulls={pulls}, commits={commits}, issues={issues}, reviews={reviews}")
        logger.debug(f"Repos impact: {repos_impact}, Consistency: {consistency}, Repo count: {repo_count}")
        
        cursor.execute('''
        INSERT INTO metrics 
        (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count))
        
        # Insert repositories
        repositories = metrics.get('repositories', [])
        logger.debug(f"Storing {len(repositories)} repositories for {username}")
        
        for repo in repositories:
            name = repo.get('name', '')
            stars = repo.get('stars', 0)
            forks = repo.get('forks', 0)
            primary_language = repo.get('primary_language', '')
            technical_impact = repo.get('repo_tech_impact', 0)
            ecosystem_impact = repo.get('repo_eco_impact', 0)
            total_impact = repo.get('repo_impact', 0)
            
            cursor.execute('''
            INSERT INTO repositories 
            (user_id, name, stars, forks, primary_language, technical_impact, ecosystem_impact, total_impact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, stars, forks, primary_language, technical_impact, ecosystem_impact, total_impact))
        
        # Commit transaction
        conn.commit()
        logger.info(f"Data for {username} stored in database")
        
        # Verify data was stored
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        if result:
            logger.debug(f"Verified user {username} was stored with ID {result[0]}")
        else:
            logger.warning(f"Failed to verify user {username} was stored")
        
        return user_id
    
    except Exception as e:
        # Rollback transaction
        conn.rollback()
        logger.error(f"Error storing data for {user_data.get('username')}: {str(e)}", exc_info=True)
        return None

def save_progress(processed_users, results):
    """Save progress to allow resuming later."""
    progress_data = {
        'processed_users': processed_users,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save progress
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress_data, f)
    
    # Save results summary
    results_file = OUTPUT_DIR / "batch_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Progress saved: {len(processed_users)} users processed")

def load_progress():
    """Load progress from previous run."""
    if not PROGRESS_FILE.exists():
        logger.info("No previous progress found")
        return set(), []
    
    try:
        with open(PROGRESS_FILE, 'r') as f:
            progress_data = json.load(f)
        
        results_file = OUTPUT_DIR / "batch_results.json"
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
        else:
            results = []
        
        processed_users = set(progress_data.get('processed_users', []))
        logger.info(f"Loaded previous progress: {len(processed_users)} users processed")
        
        return processed_users, results
    
    except Exception as e:
        logger.error(f"Error loading progress: {str(e)}")
        return set(), []

def generate_summary(results):
    """Generate a summary of the results."""
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'error']
    
    print("\n=== Batch Collection Summary ===\n")
    print(f"Total users processed: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        # Sort by impact score
        successful.sort(key=lambda x: x.get('impact_score', 0), reverse=True)
        
        print("\n=== Top 10 Users by Impact Score ===\n")
        print(f"{'Username':<20} {'Impact Score':<15} {'Pulls':<8} {'Commits':<8} {'Reviews':<8} {'Issues':<8} {'Repos':<8} {'Consistency':<12}")
        print("-" * 90)
        
        for user in successful[:10]:
            username = user.get('username', '')
            impact_score = user.get('impact_score', 0)
            contributions = user.get('contributions', {})
            pulls = contributions.get('pulls', 0)
            commits = contributions.get('commits', 0)
            reviews = contributions.get('reviews', 0)
            issues = contributions.get('issues', 0)
            repos_impact = contributions.get('repos_impact', 0)
            consistency = contributions.get('consistency', 0)
            
            print(f"{username:<20} {impact_score:<15.2f} {pulls:<8} {commits:<8} {reviews:<8} {issues:<8} {repos_impact:<8.2f} {consistency:<12.2f}")
    
    if failed:
        print("\n=== Failed Users (Sample) ===\n")
        for user in failed[:10]:  # Show only first 10 failures
            print(f"{user.get('username')}: {user.get('error')}")
        
        if len(failed) > 10:
            print(f"... and {len(failed) - 10} more failures")
    
    # Save summary to file
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'top_users': [
            {
                'username': user.get('username'),
                'impact_score': user.get('impact_score', 0),
                'contributions': user.get('contributions', {})
            }
            for user in successful[:20]  # Top 20 users
        ],
        'error_summary': {}
    }
    
    # Count error types
    for user in failed:
        error = user.get('error', '')
        error_type = error[:50] if error else 'Unknown error'  # Use first 50 chars as error type
        summary['error_summary'][error_type] = summary['error_summary'].get(error_type, 0) + 1
    
    summary_file = OUTPUT_DIR / "batch_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Summary saved to {summary_file}")

def main():
    """Main function to collect GitHub metrics for a batch of users."""
    args = parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Create data directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(Path(__file__).parent / "logs", exist_ok=True)
    
    # Initialize metrics database
    metrics_conn = init_metrics_db(args.metrics_db)
    
    # Verify database connection
    try:
        cursor = metrics_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        logger.debug(f"Database connection verified. Current user count: {count}")
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}", exc_info=True)
        sys.exit(1)
    
    # Get existing users to skip
    existing_users = set()
    if args.skip_existing:
        existing_users = get_existing_users(args.metrics_db)
    
    # Initialize or load progress
    if args.resume:
        processed_users, results = load_progress()
        existing_users.update(processed_users)
    else:
        processed_users = set()
        results = []
    
    # Sample users
    users_to_process = sample_users(args.github_db, args.batch_size, existing_users)
    
    logger.info(f"Starting collection for {len(users_to_process)} users")
    
    # Process users in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit tasks
        futures = []
        
        for user in users_to_process:
            future = executor.submit(collect_user_data, user['login'], user['id'])
            futures.append(future)
        
        # Process results as they complete
        try:
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                
                # Ensure result has username
                if 'username' not in result:
                    logger.warning(f"Result missing username: {result}")
                    if 'error' in result:
                        # Try to find the original user
                        for user in users_to_process:
                            if user['id'] == result.get('user_id'):
                                result['username'] = user['login']
                                break
                
                # Skip results without username
                if 'username' not in result:
                    logger.error(f"Skipping result without username: {result}")
                    continue
                
                results.append(result)
                processed_users.add(result['username'])
                
                # Store successful results in the database
                if result.get('status') == 'success':
                    user_id = store_user_data(metrics_conn, result)
                    if user_id:
                        logger.debug(f"Successfully stored {result['username']} with ID {user_id}")
                    else:
                        logger.warning(f"Failed to store {result['username']} in database")
                
                # Save progress periodically (every 10 users or 5%)
                if (i + 1) % max(10, args.batch_size // 20) == 0:
                    save_progress(list(processed_users), results)
                    logger.info(f"Progress: {i + 1}/{len(users_to_process)} users processed ({(i + 1) / len(users_to_process) * 100:.1f}%)")
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user. Saving progress...")
            executor.shutdown(wait=False)
            save_progress(list(processed_users), results)
            metrics_conn.close()
            sys.exit(1)
    
    # Final save
    save_progress(list(processed_users), results)
    
    # Verify final database state
    cursor = metrics_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    final_count = cursor.fetchone()[0]
    logger.info(f"Final database user count: {final_count}")
    
    # Close database connection
    metrics_conn.close()
    
    # Generate summary
    generate_summary(results)
    
    logger.info(f"Batch collection completed: {len(results)} users processed")

if __name__ == "__main__":
    main() 