#!/usr/bin/env python3
"""
Test script for collecting metrics for a single GitHub user.

This script collects metrics for a specific GitHub user and compares the results
with the API endpoint.
"""

import os
import sys
import json
import logging
import requests
import sqlite3
from pathlib import Path
from datetime import datetime

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.app.services import fetch_all_data, aggregate_user_data, calculate_impact_score

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path(__file__).parent / "data"
API_URL = "http://localhost:5000/api/analyze/{username}"
DB_PATH = OUTPUT_DIR / "single_user_test.db"

def collect_user_data(username):
    """Collect data for a specific GitHub user."""
    logger.info(f"Collecting data for GitHub user: {username}")
    
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Fetch GitHub data
    start_time = datetime.now()
    logger.info(f"Fetching GitHub data for {username}...")
    github_data = fetch_all_data(username)
    
    if 'error' in github_data:
        logger.error(f"Error fetching data for {username}: {github_data['error']}")
        return None
    
    # Aggregate user data and calculate metrics
    logger.info(f"Aggregating data for {username}...")
    result = aggregate_user_data(username, github_data)
    
    # Calculate impact score
    impact_score = calculate_impact_score(result)
    result['impact_score'] = impact_score
    
    # Add timestamp and processing time
    result['timestamp'] = datetime.now().isoformat()
    result['processing_time'] = (datetime.now() - start_time).total_seconds()
    result['status'] = 'success'
    
    # Save the result to a JSON file
    output_file = OUTPUT_DIR / f"{username}_metrics.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Data for {username} saved to {output_file}")
    return result

def fetch_api_data(username):
    """Fetch data from the API endpoint."""
    logger.info(f"Fetching data from API for {username}...")
    
    try:
        response = requests.get(API_URL.format(username=username), timeout=60)
        response.raise_for_status()
        api_data = response.json()
        
        # Save the API result to a JSON file
        output_file = OUTPUT_DIR / f"{username}_api.json"
        with open(output_file, 'w') as f:
            json.dump(api_data, f, indent=2)
        
        logger.info(f"API data for {username} saved to {output_file}")
        return api_data
    
    except requests.RequestException as e:
        logger.error(f"Error fetching API data for {username}: {str(e)}")
        return None

def compare_results(direct_result, api_result):
    """Compare the direct result with the API result."""
    if not direct_result or not api_result:
        logger.error("Cannot compare results: one or both results are missing")
        return
    
    logger.info("Comparing direct result with API result...")
    
    # Check if the core metrics match
    direct_contributions = direct_result.get('contributions', {})
    api_contributions = api_result.get('contributions', {})
    
    metrics = ['pulls', 'commits', 'reviews', 'issues', 'repos_impact', 'consistency']
    
    print("\n=== Metrics Comparison ===\n")
    print(f"{'Metric':<15} {'Direct':<10} {'API':<10} {'Match':<10}")
    print("-" * 45)
    
    all_match = True
    for metric in metrics:
        direct_value = direct_contributions.get(metric, 0)
        api_value = api_contributions.get(metric, 0)
        match = "✓" if abs(direct_value - api_value) < 0.01 else "✗"
        
        if abs(direct_value - api_value) >= 0.01:
            all_match = False
            
        print(f"{metric:<15} {direct_value:<10.2f} {api_value:<10.2f} {match:<10}")
    
    # Check impact score
    direct_score = direct_result.get('impact_score', 0)
    api_score = api_result.get('impact_score', 0)
    score_match = "✓" if abs(direct_score - api_score) < 0.01 else "✗"
    
    if abs(direct_score - api_score) >= 0.01:
        all_match = False
        
    print(f"{'impact_score':<15} {direct_score:<10.2f} {api_score:<10.2f} {score_match:<10}")
    
    print("\n=== Overall Result ===\n")
    if all_match:
        print("All metrics match! The data collection system is working correctly.")
    else:
        print("Some metrics don't match. Check the logs for details.")
    
    # Save the comparison to a file
    comparison = {
        'direct': direct_contributions,
        'api': api_contributions,
        'direct_score': direct_score,
        'api_score': api_score,
        'all_match': all_match
    }
    
    output_file = OUTPUT_DIR / f"{direct_result['username']}_comparison.json"
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    logger.info(f"Comparison saved to {output_file}")
    return comparison

def init_db():
    """Initialize the database for storing user metrics."""
    logger.info(f"Initializing database at {DB_PATH}")
    
    # Create parent directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
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
    
    conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")
    return conn

def store_user_data(user_data):
    """Store user data in the database."""
    logger.info(f"Storing data for {user_data['username']} in database")
    
    # Initialize database
    conn = init_db()
    cursor = conn.cursor()
    
    try:
        # Begin transaction
        conn.execute('BEGIN TRANSACTION')
        
        # Insert user
        username = user_data.get('username')
        name = user_data.get('name')
        email = user_data.get('email')
        company = user_data.get('company')
        location = user_data.get('location')
        bio = user_data.get('bio')
        followers = user_data.get('followers', 0)
        following = user_data.get('following', 0)
        impact_score = user_data.get('impact_score', 0)
        
        cursor.execute('''
        INSERT OR REPLACE INTO users 
        (username, name, email, company, location, bio, followers, following, impact_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, name, email, company, location, bio, followers, following, impact_score))
        
        user_id = cursor.lastrowid
        
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
        
        cursor.execute('''
        INSERT INTO metrics 
        (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, pulls, commits, issues, reviews, repos_impact, consistency, repo_count))
        
        # Insert repositories
        repositories = metrics.get('repositories', [])
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
        
    except Exception as e:
        # Rollback transaction
        conn.rollback()
        logger.error(f"Error storing data for {user_data.get('username')}: {str(e)}")
    
    finally:
        # Close database connection
        conn.close()

def main():
    """Main function to test data collection for a single user."""
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = "dfleischer"  # Default username
    
    logger.info(f"Testing data collection for GitHub user: {username}")
    
    # Collect data directly
    direct_result = collect_user_data(username)
    
    if direct_result:
        # Store data in database
        store_user_data(direct_result)
        
        # Fetch data from API (if available)
        try:
            api_result = fetch_api_data(username)
            
            # Compare results
            if api_result:
                comparison = compare_results(direct_result, api_result)
                
                # Print repository metrics
                print("\n=== Repository Metrics ===\n")
                repos = direct_result.get('metrics', {}).get('repositories', [])
                if repos:
                    print(f"Found {len(repos)} repositories")
                    print(f"{'Repository':<30} {'Stars':<8} {'Forks':<8} {'Impact':<10}")
                    print("-" * 60)
                    for repo in repos[:5]:  # Show top 5 repos
                        name = repo.get('name', '')
                        stars = repo.get('stars', 0)
                        forks = repo.get('forks', 0)
                        impact = repo.get('repo_impact', 0)
                        print(f"{name:<30} {stars:<8} {forks:<8} {impact:<10.2f}")
                    
                    if len(repos) > 5:
                        print(f"... and {len(repos) - 5} more repositories")
                else:
                    print("No repository data found")
            else:
                print("\nAPI comparison not available. Check if the Flask backend is running.")
        
        except Exception as e:
            logger.error(f"Error in API comparison: {str(e)}")
            print("\nAPI comparison failed. Check if the Flask backend is running.")
    else:
        print(f"\nFailed to collect data for {username}")

if __name__ == "__main__":
    main() 