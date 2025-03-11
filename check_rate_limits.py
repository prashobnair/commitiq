#!/usr/bin/env python3
import os
import sys
import time
from dotenv import load_dotenv

# Add the parent directory to the path to import from backend
sys.path.append('.')
from backend.app.services import GitHubGraphQL

# Load environment variables
load_dotenv()

# Create a GitHubGraphQL instance
github_client = GitHubGraphQL()

def check_rate_limits():
    """Check GitHub API rate limits and print status"""
    try:
        # Get the current token
        token = github_client.get_token()
        
        # Get rate limit info for the token
        remaining = github_client.token_rate_limits[token]['remaining']
        reset_time = github_client.token_rate_limits[token]['reset_time']
        
        # Calculate time until reset
        wait_time = max(reset_time - time.time(), 0)
        
        print("\nGitHub API Rate Limit Status:")
        print(f"Remaining API calls: {remaining}")
        print(f"Reset in: {wait_time:.1f} seconds ({wait_time/60:.1f} minutes)")
        
        # Check all tokens if multiple are available
        if len(github_client.tokens) > 1:
            print("\nAll tokens status:")
            for i, t in enumerate(github_client.tokens):
                r = github_client.token_rate_limits[t]['remaining']
                rt = github_client.token_rate_limits[t]['reset_time']
                wt = max(rt - time.time(), 0)
                print(f"Token {i+1}: {r} remaining, reset in {wt:.1f} seconds")
    
    except Exception as e:
        print(f"Error checking rate limits: {e}")

if __name__ == "__main__":
    check_rate_limits()
