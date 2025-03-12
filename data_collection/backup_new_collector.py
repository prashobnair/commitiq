#!/usr/bin/env python3
"""
New Data Collection Module for GitHub Metrics Analysis

This script fetches GitHub users from the PostgreSQL database, processes their data
using the backend services, and stores the results in PostgreSQL. Designed to run
continuously on AWS EC2 until reaching 10,000 processed users.

Features:
- Continuous batch processing with configurable worker count
- Rate limit handling for GitHub API
- Progress tracking and resumability
- Detailed logging and error handling
"""

import os
import sys
import json
import logging
import argparse
import time
import random
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import psycopg2
from psycopg2.extras import DictCursor, execute_values
from dotenv import load_dotenv
from multiprocessing import Pool

# Load environment variables from .env
load_dotenv('../.env')

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.app.services import (
    aggregate_user_data, calculate_impact_score, 
    GitHubGraphQL, fetch_all_data
)
from db_utils import (
    DEFAULT_PG_HOST, DEFAULT_PG_PORT, DEFAULT_PG_USER, 
    DEFAULT_PG_PASSWORD, DEFAULT_PG_DB
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/collector.log")
    ]
)
logger = logging.getLogger(__name__)

# Create a GitHubGraphQL instance for rate limit checking
github_client = GitHubGraphQL()

def check_rate_limits():
    """
    Check GitHub API rate limits and wait if close to the limit.
    
    Returns:
        bool: True if we can proceed, False if we should stop collection
    """
    try:
        # Get the current token
        token = github_client.get_token()
        
        # Get rate limit info for the token
        remaining = github_client.token_rate_limits[token]['remaining']
        reset_time = github_client.token_rate_limits[token]['reset_time']
        
        # If we have multiple tokens, check if any have sufficient rate limit
        if len(github_client.tokens) > 1:
            # Check if any token has sufficient remaining calls
            for t in github_client.tokens:
                if github_client.token_rate_limits[t]['remaining'] > 100:
                    logger.info(f"Using token with {github_client.token_rate_limits[t]['remaining']} remaining calls")
                    return True
            
            # If all tokens are close to rate limit, find the one with earliest reset time
            earliest_token = min(github_client.tokens, key=lambda t: github_client.token_rate_limits[t]['reset_time'])
            earliest_reset = github_client.token_rate_limits[earliest_token]['reset_time']
            wait_time = max(earliest_reset - time.time(), 10)
            
            if wait_time > 0:
                logger.warning(f"All tokens close to rate limit. Waiting for {wait_time:.1f} seconds until reset")
                time.sleep(wait_time)
                return True
        else:
            # Single token case
            if remaining < 100:
                wait_time = max(reset_time - time.time(), 10)
                logger.warning(f"Rate limit low ({remaining} remaining). Waiting for {wait_time:.1f} seconds until reset")
                time.sleep(wait_time)
            
        return True
    except Exception as e:
        logger.error(f"Error checking rate limits: {e}")
        return True  # Continue anyway, the GitHub client will handle rate limits internally

# Constants
OUTPUT_DIR = Path(__file__).parent / "data"
BATCH_SIZE = 100
MAX_WORKERS = 3  # Fixed at 3 workers for EC2
TARGET_USERS = 100000
PROGRESS_FILE = OUTPUT_DIR / "collection_progress.json"

# PostgreSQL connection parameters from environment variables
PG_HOST = os.getenv('DB_HOST')
PG_PORT = int(os.getenv('DB_PORT', '5432'))
PG_USER = os.getenv('DB_USER')
PG_PASSWORD = os.getenv('DB_PASSWORD')
PG_DB = os.getenv('DB_NAME')

# GitHub API token from environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def get_db_connection():
    """Get a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB
    )

def init_metrics_tables():
    """Initialize the metrics tables in PostgreSQL if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users_github (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            github_id INTEGER,
            name VARCHAR(255),
            email VARCHAR(255),
            company VARCHAR(255),
            location VARCHAR(255),
            bio TEXT,
            followers INTEGER,
            following INTEGER,
            impact_score REAL,
            has_activity BOOLEAN DEFAULT TRUE,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users_metrics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users_github(id),
            pulls INTEGER,
            commits INTEGER,
            issues INTEGER,
            reviews INTEGER,
            repos_impact REAL,
            consistency REAL,
            repo_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create repositories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users_repositories (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users_github(id),
            name VARCHAR(255),
            stars INTEGER,
            forks INTEGER,
            primary_language VARCHAR(100),
            technical_impact REAL,
            ecosystem_impact REAL,
            total_impact REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create repository_metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users_repository_metrics (
            id SERIAL PRIMARY KEY,
            repository_id INTEGER NOT NULL REFERENCES users_repositories(id),
            collaborators INTEGER,
            collab_factor REAL,
            developer_commits INTEGER,
            total_commits INTEGER,
            contribution_ratio REAL,
            merged_pull_requests INTEGER,
            closed_pull_requests INTEGER,
            total_pull_requests INTEGER,
            pr_acceptance REAL,
            review_comments INTEGER,
            code_quality REAL,
            popularity REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON users_github(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_github_id ON users_github(github_id)')
        
        conn.commit()
        logger.info("Metrics tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing metrics tables: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()
        conn.close()

def get_existing_users():
    """
    Get list of usernames already in the metrics database.
    
    Returns:
        list: List of usernames already processed
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get usernames from users_github table
        cursor.execute("SELECT username FROM users_github")
        existing_users = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return existing_users
    except Exception as e:
        logger.error(f"Error getting existing users: {e}")
        return []

def sample_users_postgres(host, port, user, password, dbname, batch_size, existing_users, user_type='User', min_followers=0):
    """
    Sample users from PostgreSQL GitHub database.
    
    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        dbname: Database name
        batch_size: Number of users to sample
        existing_users: List of usernames already processed
        user_type: Type of user to sample (default: 'User')
        min_followers: Minimum number of followers (default: 0)
        
    Returns:
        list: List of usernames to process
    """
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # Get total number of users
        cursor.execute(f"SELECT COUNT(*), MIN(id), MAX(id) FROM github_users WHERE type = '{user_type}'")
        total_users, min_id, max_id = cursor.fetchone()
        logger.info(f"GitHub database contains {total_users:,} {user_type}s with IDs from {min_id:,} to {max_id:,}")
        
        # Calculate segment size for stratified sampling
        num_segments = 10
        segment_size = (max_id - min_id + 1) // num_segments
        
        # Sample users from each segment
        users_per_segment = batch_size // num_segments
        if users_per_segment == 0:
            users_per_segment = 1
        
        sampled_users = []
        for i in range(num_segments):
            segment_start = min_id + i * segment_size
            segment_end = segment_start + segment_size - 1 if i < num_segments - 1 else max_id
            
            # Query for users in this segment
            query = f"""
                SELECT login 
                FROM github_users 
                WHERE type = '{user_type}' 
                AND id BETWEEN {segment_start} AND {segment_end}
                ORDER BY RANDOM() 
                LIMIT {users_per_segment * 3}
            """
            cursor.execute(query)
            segment_users = [row[0] for row in cursor.fetchall()]
            
            # Filter out existing users
            segment_users = [u for u in segment_users if u not in existing_users]
            
            # Take the required number of users from this segment
            segment_users = segment_users[:users_per_segment]
            logger.info(f"Sampled {len(segment_users)} users from segment {i+1} (IDs {segment_start:,}-{segment_end:,})")
            
            sampled_users.extend(segment_users)
        
        # Close connection
        cursor.close()
        conn.close()
        
        return sampled_users
    except Exception as e:
        logger.error(f"Error sampling users from PostgreSQL: {e}")
        return []

def fetch_github_data(username):
    """
    Fetch GitHub data for a user.
    
    Args:
        username: GitHub username
        
    Returns:
        Dictionary with GitHub data or None if error
    """
    try:
        logger.info(f"Fetching GitHub data for {username}")
        
        # Check rate limits before making API calls
        if not check_rate_limits():
            logger.warning("Rate limit check failed, skipping this user")
            return None
        
        # Use the fetch_all_data function from backend services
        # It will create its own GitHubGraphQL instance
        github_data = fetch_all_data(username)
        
        if 'error' in github_data:
            logger.error(f"Error fetching data for {username}: {github_data['error']}")
            return None
        
        return github_data
    
    except Exception as e:
        logger.error(f"Exception fetching data for {username}: {e}")
        return None

def collect_user_data(username):
    """
    Collect and process GitHub data for a user.
    
    Args:
        username: GitHub username
        
    Returns:
        Dictionary with processed user data or None if error
    """
    try:
        # Fetch GitHub data
        github_data = fetch_github_data(username)
        if not github_data:
            return None
        
        # Process the data using backend services
        user_data = aggregate_user_data(username, github_data)
        
        if 'error' in user_data:
            logger.error(f"Error processing data for {username}: {user_data['error']}")
            return None
        
        # Calculate impact score
        impact_score = calculate_impact_score(user_data)
        user_data['impact_score'] = impact_score
        
        # Add contribution metrics to the top level for easier access
        user_data['pulls'] = user_data['contributions']['pulls']
        user_data['commits'] = user_data['contributions']['commits']
        user_data['reviews'] = user_data['contributions']['reviews']
        user_data['issues'] = user_data['contributions']['issues']
        user_data['repos_impact'] = user_data['contributions']['repos_impact']
        user_data['consistency'] = user_data['contributions']['consistency']
        
        # Ensure username is included
        if 'username' not in user_data:
            user_data['username'] = username
        
        # Debug log the repository data structure
        if logger.isEnabledFor(logging.DEBUG) and 'metrics' in user_data and 'repositories' in user_data['metrics']:
            logger.debug(f"Repository data structure for {username}: {json.dumps(user_data['metrics']['repositories'][:1], indent=2)}")
        
        return user_data
    
    except Exception as e:
        logger.error(f"Exception processing data for {username}: {e}")
        return None

def store_user_data(user_data):
    """Store user data in PostgreSQL."""
    if not user_data:
        return False
    
    try:
        username = user_data.get('username')
        if not username:
            logger.error("Missing username in user data")
            return False
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Convert any NumPy values to Python native types
            impact_score = float(user_data.get('impact_score', 0.0))
            repos_impact = float(user_data.get('repos_impact', 0.0))
            consistency = float(user_data.get('consistency', 0.0))
            
            # Insert user data
            cursor.execute('''
            INSERT INTO users_github (
                username, github_id, name, email, company, location, bio,
                followers, following, impact_score
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            ''', (
                username,
                user_data.get('id'),
                user_data.get('name'),
                user_data.get('email'),
                user_data.get('company'),
                user_data.get('location'),
                user_data.get('bio'),
                user_data.get('followers', 0),
                user_data.get('following', 0),
                impact_score
            ))
            
            user_id = cursor.fetchone()[0]
            
            # Insert metrics data
            cursor.execute('''
            INSERT INTO users_metrics (
                user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                user_id,
                user_data.get('pulls', 0),
                user_data.get('commits', 0),
                user_data.get('issues', 0),
                user_data.get('reviews', 0),
                repos_impact,
                consistency,
                len(user_data.get('metrics', {}).get('repositories', []))
            ))
            
            # Batch insert repositories
            repos = user_data.get('metrics', {}).get('repositories', [])
            if repos:
                repo_values = []
                
                for repo in repos:
                    # Get repository impact values
                    # First try to get them from the repo_impact fields
                    technical_impact = repo.get('repo_tech_impact')
                    if technical_impact is None:
                        technical_impact = repo.get('technical_impact', 0.0)
                    
                    ecosystem_impact = repo.get('repo_eco_impact')
                    if ecosystem_impact is None:
                        ecosystem_impact = repo.get('ecosystem_impact', 0.0)
                    
                    total_impact = repo.get('repo_impact')
                    if total_impact is None:
                        total_impact = repo.get('total_impact', 0.0)
                    
                    # Convert to Python float
                    technical_impact = float(technical_impact)
                    ecosystem_impact = float(ecosystem_impact)
                    total_impact = float(total_impact)
                    
                    # Log the impact values for debugging
                    logger.debug(f"Repository {repo.get('name')}: tech={technical_impact}, eco={ecosystem_impact}, total={total_impact}")
                    
                    # Extract repository data
                    repo_values.append((
                        user_id,
                        repo.get('name', ''),
                        repo.get('stars', 0),
                        repo.get('forks', 0),
                        repo.get('primary_language', ''),
                        technical_impact,
                        ecosystem_impact,
                        total_impact
                    ))
                
                # Batch insert repositories
                repo_ids = []
                for repo_value in repo_values:
                    cursor.execute('''
                    INSERT INTO users_repositories (
                        user_id, name, stars, forks, primary_language,
                        technical_impact, ecosystem_impact, total_impact
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    ''', repo_value)
                    repo_ids.append(cursor.fetchone()[0])
                
                # Prepare repository metrics for batch insert
                for repo_id, repo in zip(repo_ids, repos):
                    tech_components = repo.get('technical_impact_components', {})
                    eco_components = repo.get('ecosystem_impact_components', {})
                    
                    # Convert any NumPy values to Python native types
                    collab_factor = float(tech_components.get('collab_factor', repo.get('collab_factor', 1.0)))
                    contribution_ratio = float(eco_components.get('contribution_ratio', repo.get('contribution_ratio', 0.0)))
                    pr_acceptance = float(repo.get('pr_acceptance', 0.0))
                    code_quality = float(repo.get('code_quality', 0.3))
                    popularity = float(eco_components.get('popularity', repo.get('popularity', 0.0)))
                    
                    cursor.execute('''
                    INSERT INTO users_repository_metrics (
                        repository_id, collaborators, collab_factor, developer_commits,
                        total_commits, contribution_ratio, merged_pull_requests,
                        closed_pull_requests, total_pull_requests, pr_acceptance,
                        review_comments, code_quality, popularity
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        repo_id,
                        repo.get('collaborators', 0),
                        collab_factor,
                        tech_components.get('developer_commits', repo.get('developer_commits', 0)),
                        tech_components.get('total_commits', repo.get('total_commits', 0)),
                        contribution_ratio,
                        repo.get('merged_pull_requests', 0),
                        repo.get('closed_pull_requests', 0),
                        repo.get('total_pull_requests', 0),
                        pr_acceptance,
                        repo.get('review_comments', 0),
                        code_quality,
                        popularity
                    ))
            
            conn.commit()
            logger.info(f"Successfully stored data for user {username}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing data for {username}: {e}")
            conn.rollback()
            return False
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False

def process_user(username):
    """
    Process a single user: fetch data, calculate metrics, and store in database.
    
    Args:
        username: GitHub username
        
    Returns:
        dict: User data with metrics or None if processing failed
    """
    try:
        logger.info(f"Processing user {username}")
        
        # Collect user data
        user_data = collect_user_data(username)
        if not user_data:
            logger.error(f"Failed to collect data for user {username}")
            return None
        
        # Store user data in database
        store_user_data(user_data)
        
        return user_data
    except Exception as e:
        logger.error(f"Error processing user {username}: {e}")
        return None

def generate_summary(results):
    """
    Generate summary statistics from processing results.
    
    Args:
        results: List of user data dictionaries or None values
        
    Returns:
        dict: Summary statistics
    """
    total_users = len(results)
    successful_users = sum(1 for r in results if r is not None)
    failed_users = total_users - successful_users
    
    # Skip users with no contributions
    valid_results = [r for r in results if r is not None]
    zero_contribution_users = sum(1 for r in valid_results if r.get('impact_score', 0) == 0)
    
    # Calculate averages
    if successful_users > 0:
        avg_pulls = sum(r.get('pulls', 0) for r in valid_results) / successful_users
        avg_commits = sum(r.get('commits', 0) for r in valid_results) / successful_users
        avg_issues = sum(r.get('issues', 0) for r in valid_results) / successful_users
        avg_reviews = sum(r.get('reviews', 0) for r in valid_results) / successful_users
        avg_repos = sum(len(r.get('metrics', {}).get('repositories', [])) for r in valid_results) / successful_users
        avg_impact = sum(r.get('impact_score', 0) for r in valid_results) / successful_users
    else:
        avg_pulls = avg_commits = avg_issues = avg_reviews = avg_repos = avg_impact = 0
    
    # Find top users by impact score
    top_users = []
    for result in valid_results:
        if result is None or 'impact_score' not in result:
            continue
            
        top_users.append({
            'username': result.get('username', 'unknown'),
            'impact_score': result.get('impact_score', 0),
            'pulls': result.get('pulls', 0),
            'commits': result.get('commits', 0),
            'issues': result.get('issues', 0),
            'reviews': result.get('reviews', 0),
            'repos': len(result.get('metrics', {}).get('repositories', []))
        })
    
    # Sort by impact score
    top_users.sort(key=lambda x: x['impact_score'], reverse=True)
    top_users = top_users[:10]  # Keep only top 10
    
    return {
        'timestamp': datetime.now().isoformat(),
        'total_users': total_users,
        'successful_users': successful_users,
        'failed_users': failed_users,
        'zero_contribution_users': zero_contribution_users,
        'averages': {
            'pulls': avg_pulls,
            'commits': avg_commits,
            'issues': avg_issues,
            'reviews': avg_reviews,
            'repos': avg_repos,
            'impact_score': avg_impact
        },
        'top_users': top_users
    }

def save_summary(summary, output_path):
    """
    Save summary to a JSON file.
    
    Args:
        summary: Dictionary with summary statistics
        output_path: Path to save the summary
    """
    try:
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved summary to {output_path}")
    
    except Exception as e:
        logger.error(f"Error saving summary: {e}")

def main():
    """
    Main function to collect GitHub user data.
    """
    parser = argparse.ArgumentParser(description='Collect GitHub user data')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of users to process in each batch')
    parser.add_argument('--workers', type=int, default=8, help='Number of worker processes')
    parser.add_argument('--target-count', type=int, default=10000, help='Target number of users to collect')
    parser.add_argument('--db-host', type=str, default=None, help='Database host')
    parser.add_argument('--db-port', type=str, default=None, help='Database port')
    parser.add_argument('--db-name', type=str, default=None, help='Database name')
    parser.add_argument('--db-user', type=str, default=None, help='Database user')
    parser.add_argument('--db-password', type=str, default=None, help='Database password')
    parser.add_argument('--github-token', type=str, default=None, help='GitHub API token')
    args = parser.parse_args()
    
    # Set environment variables if provided
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
    if args.github_token:
        os.environ['GITHUB_TOKEN'] = args.github_token
    
    # Initialize metrics tables
    init_metrics_tables()
    
    # Get existing users
    existing_users = get_existing_users()
    logger.info(f"Found {len(existing_users)} existing users in metrics database")
    
    # Process users in batches until we reach the target count
    batch_num = len(existing_users)
    while len(existing_users) < args.target_count:
        logger.info(f"Processing batch of {args.batch_size} users. Progress: {len(existing_users)}/{args.target_count}")
        
        # Check rate limits before processing a new batch
        logger.info("Checking GitHub API rate limits before processing batch...")
        if not check_rate_limits():
            logger.warning("Rate limit check failed. Waiting before continuing...")
            time.sleep(60)  # Wait a minute and try again
            continue
        
        # Sample users from GitHub database
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        
        new_users = sample_users_postgres(
            db_host, db_port, db_user, db_password, db_name,
            args.batch_size, existing_users
        )
        
        if not new_users:
            logger.error("Failed to sample new users. Exiting.")
            break
        
        # Process users in parallel
        with Pool(args.workers) as pool:
            results = pool.map(process_user, new_users)
        
        # Generate summary
        summary = generate_summary(results)
        
        # Save summary
        os.makedirs('data', exist_ok=True)
        save_summary(summary, f'data/batch_summary_{batch_num}.json')
        
        # Log summary
        logger.info(f"Batch completed: {summary['successful_users']} successful, {summary['failed_users']} failed")
        logger.info(f"Average impact score: {summary['averages']['impact_score']:.2f}")
        
        # Update existing users
        existing_users = get_existing_users()
        batch_num += 1

if __name__ == "__main__":
    main() 