#!/usr/bin/env python3
"""
GitHub User Metrics Collection System

This script collects GitHub metrics for a sample of users from the database,
processes them in parallel, and stores the results for normalization analysis.
"""

import os
import sys
import time
import json
import logging
import sqlite3
import random
import argparse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import numpy as np

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.app.services import aggregate_user_data, fetch_all_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "metrics_collection.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_SAMPLE_SIZE = 10000
MAX_WORKERS = min(32, os.cpu_count() * 2)  # Optimal number of workers
RESULTS_FILE = Path(__file__).parent / "data" / "user_metrics.json"
PROGRESS_FILE = Path(__file__).parent / "data" / "collection_progress.json"
DB_DIR = Path(__file__).parent.parent / "github_user_db" / "data"
DB_PATH = DB_DIR / "github_users.db"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Collect GitHub user metrics for normalization analysis.')
    parser.add_argument('--sample-size', type=int, default=DEFAULT_SAMPLE_SIZE, 
                        help=f'Number of users to sample (default: {DEFAULT_SAMPLE_SIZE})')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help=f'Number of parallel workers (default: {MAX_WORKERS})')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from the last checkpoint')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode with a small sample')
    return parser.parse_args()

def get_db_connection():
    """Get a connection to the SQLite database."""
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}. Please ensure the GitHub user database exists.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def get_user_count():
    """Get the total number of GitHub users in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM github_users')
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else 0

def sample_users(sample_size, test_mode=False):
    """
    Sample users from the database with a distribution favoring later users.
    
    Args:
        sample_size: Number of users to sample
        test_mode: If True, just get the first few users for testing
        
    Returns:
        List of user dictionaries with 'id' and 'login' keys
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total user count and ID range
    cursor.execute('SELECT COUNT(*), MIN(id), MAX(id) FROM github_users')
    total_count, min_id, max_id = cursor.fetchone()
    
    logger.info(f"Database contains {total_count:,} users with IDs from {min_id:,} to {max_id:,}")
    
    if test_mode:
        # For testing, just get the first few users
        cursor.execute('SELECT id, login FROM github_users LIMIT ?', (min(sample_size, 10),))
        users = [{'id': row[0], 'login': row[1]} for row in cursor.fetchall()]
        conn.close()
        return users
    
    # Create a weighted distribution favoring later users
    # We'll divide the range into segments and sample more from later segments
    segments = 10
    segment_size = (max_id - min_id) // segments
    
    # Weights for each segment (increasing weights for later segments)
    # This creates a distribution where later segments have higher probability
    weights = np.linspace(1, 5, segments)
    weights = weights / weights.sum()  # Normalize to sum to 1
    
    # Calculate how many users to sample from each segment
    segment_samples = np.round(weights * sample_size).astype(int)
    
    # Adjust to ensure we get exactly sample_size users
    while segment_samples.sum() < sample_size:
        segment_samples[-1] += 1
    while segment_samples.sum() > sample_size:
        if segment_samples[-1] > 0:
            segment_samples[-1] -= 1
        else:
            segment_samples[segment_samples > 0][-1] -= 1
    
    users = []
    for i in range(segments):
        segment_start = min_id + i * segment_size
        segment_end = segment_start + segment_size - 1 if i < segments - 1 else max_id
        segment_count = segment_samples[i]
        
        if segment_count > 0:
            # Get random users from this segment
            cursor.execute('''
                SELECT id, login FROM github_users 
                WHERE id BETWEEN ? AND ?
                ORDER BY RANDOM() 
                LIMIT ?
            ''', (segment_start, segment_end, segment_count))
            
            segment_users = [{'id': row[0], 'login': row[1]} for row in cursor.fetchall()]
            users.extend(segment_users)
            
            logger.info(f"Sampled {len(segment_users)} users from segment {i+1} (IDs {segment_start:,}-{segment_end:,})")
    
    conn.close()
    
    # Shuffle the final list to mix users from different segments
    random.shuffle(users)
    
    return users

def process_user(username, user_id):
    """
    Process a single GitHub user to collect metrics.
    
    Args:
        username: GitHub username
        user_id: User ID in the database
        
    Returns:
        Dictionary with user metrics or error information
    """
    try:
        start_time = time.time()
        logger.info(f"Processing user {username} (ID: {user_id})")
        
        # Fetch GitHub data
        github_data = fetch_all_data(username)
        
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
        result = aggregate_user_data(username, github_data)
        
        # Add user ID and timestamp
        result['user_id'] = user_id
        result['status'] = 'success'
        result['processing_time'] = time.time() - start_time
        result['timestamp'] = datetime.now().isoformat()
        
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

def save_progress(processed_users, results):
    """Save progress to allow resuming later."""
    progress_data = {
        'processed_users': processed_users,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save progress
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress_data, f)
    
    # Save results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Progress saved: {len(processed_users)} users processed")

def load_progress():
    """Load progress from previous run."""
    if not PROGRESS_FILE.exists() or not RESULTS_FILE.exists():
        logger.info("No previous progress found")
        return set(), []
    
    try:
        with open(PROGRESS_FILE, 'r') as f:
            progress_data = json.load(f)
        
        with open(RESULTS_FILE, 'r') as f:
            results = json.load(f)
        
        processed_users = set(progress_data.get('processed_users', []))
        logger.info(f"Loaded previous progress: {len(processed_users)} users processed")
        
        return processed_users, results
    
    except Exception as e:
        logger.error(f"Error loading progress: {str(e)}")
        return set(), []

def main():
    """Main function to collect GitHub user metrics."""
    args = parse_args()
    
    # Create data directory if it doesn't exist
    os.makedirs(Path(__file__).parent / "data", exist_ok=True)
    os.makedirs(Path(__file__).parent / "logs", exist_ok=True)
    
    # Initialize or load progress
    if args.resume:
        processed_users, results = load_progress()
    else:
        processed_users = set()
        results = []
    
    # Sample users
    sample_size = 10 if args.test else args.sample_size
    all_users = sample_users(sample_size, args.test)
    
    # Filter out already processed users if resuming
    users_to_process = [user for user in all_users if user['login'] not in processed_users]
    
    logger.info(f"Starting collection for {len(users_to_process)} users (out of {sample_size} total)")
    
    # Process users in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Create a list to store futures
        futures = []
        
        # Submit tasks
        for user in users_to_process:
            future = executor.submit(process_user, user['login'], user['id'])
            futures.append(future)
        
        # Process results as they complete
        try:
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                processed_users.add(result['username'])
                
                # Save progress periodically (every 10 users or 5%)
                if (i + 1) % max(10, sample_size // 20) == 0:
                    save_progress(list(processed_users), results)
                    logger.info(f"Progress: {i + 1}/{len(users_to_process)} users processed ({(i + 1) / len(users_to_process) * 100:.1f}%)")
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user. Saving progress...")
            executor.shutdown(wait=False)
            save_progress(list(processed_users), results)
            sys.exit(1)
    
    # Final save
    save_progress(list(processed_users), results)
    
    # Generate summary statistics
    successful_results = [r for r in results if r.get('status') == 'success']
    error_count = len(results) - len(successful_results)
    
    logger.info(f"Collection completed: {len(results)} users processed, {error_count} errors")
    logger.info(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main() 