#!/usr/bin/env python3
"""
Test script to verify the GitHub username normalization in the API endpoint.
"""
import requests
import time
import sys

BASE_URL = "http://localhost:5000/api"

def test_username_format(username):
    """Test the API endpoint with a specific username format."""
    print(f"\nTesting username format: {username}")
    response = requests.get(f"{BASE_URL}/analyze/{username}")
    
    if response.status_code == 200:
        print(f"SUCCESS: User was analyzed successfully")
        return True
    else:
        print(f"ERROR ({response.status_code}): {response.json().get('error', 'Unknown error')}")
        return False

def run_tests():
    """Run tests with various username formats."""
    test_cases = [
        "octocat",                                # Plain username
        "@octocat",                               # GitHub handle
        "OcToCaT",                                # Mixed case
        "github.com/octocat",                     # GitHub URL without scheme
        "https://github.com/octocat",             # Full GitHub URL
        "https://github.com/octocat/",            # URL with trailing slash
        "https://github.com/octocat?tab=repositories"  # URL with query params
    ]
    
    success_count = 0
    
    for username in test_cases:
        success = test_username_format(username)
        if success:
            success_count += 1
        time.sleep(1)  # Add a small delay to avoid rate limiting
    
    print(f"\nTest results: {success_count}/{len(test_cases)} successful")
    
    return success_count == len(test_cases)

if __name__ == "__main__":
    print("Testing GitHub username normalization in API endpoint...")
    print(f"Base URL: {BASE_URL}")
    
    try:
        success = run_tests()
        if success:
            print("\nAll tests passed successfully!")
            sys.exit(0)
        else:
            print("\nSome tests failed. See above for details.")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to the API server. Make sure it's running.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1) 