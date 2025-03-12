#!/usr/bin/env python3
"""
Test script for GitHub API rate limit handling.
This script makes multiple API calls in quick succession to test rate limit handling.
"""

import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv('../.env')

# Add the parent directory to the path to import from backend
sys.path.append(str(Path(__file__).parent.parent))
from backend.app.services import GitHubGraphQL, fetch_all_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_rate_limit_handling():
    """
    Test rate limit handling by making multiple API calls in quick succession.
    """
    # Create a GitHubGraphQL instance
    github_client = GitHubGraphQL()
    
    # Print current rate limit status
    token = github_client.get_token()
    remaining = github_client.token_rate_limits[token]['remaining']
    reset_time = github_client.token_rate_limits[token]['reset_time']
    wait_time = max(reset_time - time.time(), 0)
    
    logger.info(f"Current rate limit status: {remaining} remaining, reset in {wait_time:.1f} seconds")
    
    # Test usernames
    test_users = [
        "torvalds",
        "gvanrossum",
        "dhh",
        "jeresig",
        "wycats",
        "defunkt",
        "mojombo",
        "matz",
        "pjhyett",
        "igrigorik"
    ]
    
    # Make API calls until we hit the rate limit
    for i, username in enumerate(test_users * 10):  # Repeat the list to ensure we hit the limit
        logger.info(f"Test {i+1}: Fetching data for {username}")
        
        try:
            # Fetch data
            github_data = fetch_all_data(username)
            
            # Check for rate limit errors
            if isinstance(github_data, dict) and 'errors' in github_data:
                for error in github_data.get('errors', []):
                    if isinstance(error, dict) and error.get('type') == 'RATE_LIMITED':
                        logger.warning(f"Rate limit hit! Error: {error}")
                        # Wait for a short time to see if our rate limit handling kicks in
                        logger.info("Waiting 10 seconds to see if rate limit handling works...")
                        time.sleep(10)
                        continue
            
            # Print some basic info from the response
            if isinstance(github_data, dict) and 'user' in github_data:
                user_info = github_data['user']
                logger.info(f"Successfully fetched data for {username}: {user_info.get('name')}, {user_info.get('followers', {}).get('totalCount')} followers")
            else:
                logger.warning(f"Unexpected response format: {github_data}")
            
            # Sleep briefly between requests to avoid hitting secondary rate limits
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error fetching data for {username}: {e}")
            if 'rate limit' in str(e).lower():
                logger.warning("Rate limit exception detected!")
                # Wait for a short time to see if our rate limit handling kicks in
                logger.info("Waiting 10 seconds to see if rate limit handling works...")
                time.sleep(10)
            
    logger.info("Test completed")

if __name__ == "__main__":
    test_rate_limit_handling() 