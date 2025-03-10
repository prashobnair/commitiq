#!/usr/bin/env python3
"""
GitHub User Metrics Database Storage

This script stores the collected GitHub user metrics in a database for further analysis.
"""

import os
import sys
import json
import logging
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "db_storage.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
METRICS_FILE = Path(__file__).parent / "data" / "user_metrics.json"
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "metrics_analysis.db"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Store GitHub user metrics in a database.')
    parser.add_argument('--input', type=str, default=str(METRICS_FILE),
                        help=f'Input metrics JSON file (default: {METRICS_FILE})')
    parser.add_argument('--db', type=str, default=str(DB_PATH),
                        help=f'Output database file (default: {DB_PATH})')
    parser.add_argument('--overwrite', action='store_true',
                        help='Overwrite existing database')
    return parser.parse_args()

def init_db(db_path, overwrite=False):
    """
    Initialize the SQLite database with the required tables.
    
    Args:
        db_path: Path to the database file
        overwrite: If True, overwrite existing database
        
    Returns:
        Connection to the database
    """
    # Create parent directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Check if database exists
    if os.path.exists(db_path) and overwrite:
        logger.info(f"Overwriting existing database at {db_path}")
        os.remove(db_path)
    
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
    logger.info(f"Database initialized at {db_path}")
    return conn

def load_metrics_data(input_file):
    """
    Load the collected metrics data.
    
    Args:
        input_file: Path to the metrics JSON file
        
    Returns:
        List of user metrics dictionaries
    """
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"Metrics file not found at {input_path}")
        sys.exit(1)
    
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        # Filter out error results
        successful_data = [d for d in data if d.get('status') == 'success']
        
        logger.info(f"Loaded {len(successful_data)} successful results out of {len(data)} total")
        return successful_data
    
    except Exception as e:
        logger.error(f"Error loading metrics data: {str(e)}")
        sys.exit(1)

def store_user_data(conn, user_data):
    """
    Store user data in the database.
    
    Args:
        conn: Database connection
        user_data: User metrics dictionary
        
    Returns:
        User ID in the database
    """
    cursor = conn.cursor()
    
    # Extract user info
    username = user_data.get('username')
    github_id = user_data.get('user_id')
    name = user_data.get('name')
    email = user_data.get('email')
    company = user_data.get('company')
    location = user_data.get('location')
    bio = user_data.get('bio')
    followers = user_data.get('followers', 0)
    following = user_data.get('following', 0)
    impact_score = user_data.get('impact_score', 0)
    
    # Insert user
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (username, github_id, name, email, company, location, bio, followers, following, impact_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, github_id, name, email, company, location, bio, followers, following, impact_score))
        
        # Get user ID
        user_id = cursor.lastrowid
        
        return user_id
    
    except sqlite3.Error as e:
        logger.error(f"Error inserting user {username}: {str(e)}")
        return None

def store_metrics(conn, user_id, user_data):
    """
    Store metrics data in the database.
    
    Args:
        conn: Database connection
        user_id: User ID in the database
        user_data: User metrics dictionary
    """
    cursor = conn.cursor()
    
    # Extract metrics
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
    
    # Insert metrics
    try:
        cursor.execute('''
        INSERT INTO metrics 
        (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count))
    
    except sqlite3.Error as e:
        logger.error(f"Error inserting metrics for user ID {user_id}: {str(e)}")

def store_repositories(conn, user_id, user_data):
    """
    Store repository data in the database.
    
    Args:
        conn: Database connection
        user_id: User ID in the database
        user_data: User metrics dictionary
    """
    cursor = conn.cursor()
    
    # Extract repositories
    metrics = user_data.get('metrics', {})
    repositories = metrics.get('repositories', [])
    
    # Insert each repository
    for repo in repositories:
        try:
            name = repo.get('name', '')
            stars = repo.get('stars', 0)
            forks = repo.get('forks', 0)
            primary_language = repo.get('primary_language', '')
            technical_impact = repo.get('technical_impact', 0)
            ecosystem_impact = repo.get('ecosystem_impact', 0)
            total_impact = repo.get('impact', 0)
            
            cursor.execute('''
            INSERT INTO repositories 
            (user_id, name, stars, forks, primary_language, technical_impact, ecosystem_impact, total_impact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, stars, forks, primary_language, technical_impact, ecosystem_impact, total_impact))
        
        except sqlite3.Error as e:
            logger.error(f"Error inserting repository {name} for user ID {user_id}: {str(e)}")

def main():
    """Main function to store metrics in a database."""
    args = parse_args()
    
    # Initialize database
    conn = init_db(args.db, args.overwrite)
    
    # Load metrics data
    data = load_metrics_data(args.input)
    
    # Store data in database
    total_users = len(data)
    success_count = 0
    
    for i, user_data in enumerate(data):
        try:
            # Begin transaction
            conn.execute('BEGIN TRANSACTION')
            
            # Store user data
            user_id = store_user_data(conn, user_data)
            
            if user_id:
                # Store metrics
                store_metrics(conn, user_id, user_data)
                
                # Store repositories
                store_repositories(conn, user_id, user_data)
                
                # Commit transaction
                conn.commit()
                success_count += 1
            else:
                # Rollback transaction
                conn.rollback()
            
            # Log progress
            if (i + 1) % 100 == 0 or (i + 1) == total_users:
                logger.info(f"Progress: {i + 1}/{total_users} users processed ({(i + 1) / total_users * 100:.1f}%)")
        
        except Exception as e:
            # Rollback transaction
            conn.rollback()
            logger.error(f"Error processing user {user_data.get('username')}: {str(e)}")
    
    # Close database connection
    conn.close()
    
    logger.info(f"Database storage completed: {success_count}/{total_users} users successfully stored")
    logger.info(f"Database saved to {args.db}")

if __name__ == "__main__":
    main() 