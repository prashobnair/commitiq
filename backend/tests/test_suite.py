#!/usr/bin/env python3
"""
CommitIQ Comprehensive Test Suite

This test suite covers all major functionality in the CommitIQ application:
- GitHub username analysis
- Database capture of analysis data
- Waitlist functionality
- Download and share features
- Analytics tracking

Usage:
    python test_suite.py [options]

Options:
    --verbose, -v     Show detailed test output
    --module=NAME     Run only tests for the specified module
                      (analysis, waitlist, share, tracking)
    --list, -l        List all available tests
    --help, -h        Display this help message
"""

import sys
import os
import unittest
import json
import time
import random
import string
import psycopg2
import requests
from datetime import datetime, timedelta
import argparse
from contextlib import contextmanager
from urllib.parse import urlparse

# Add the project root to the Python path to allow importing app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Constants
API_BASE_URL = os.getenv('TEST_API_URL', 'http://localhost:5000/api')
TEST_USERNAME = 'octocat'  # GitHub test account
TEST_EMAIL = 'test@commitiq.com'
VERBOSE = False
SAMPLE_GITHUB_USERNAMES = [
    'octocat',            # GitHub's demo account
    'defunkt',            # GitHub co-founder
    'torvalds',           # Linus Torvalds
    'gvanrossum',         # Guido van Rossum (Python creator)
    'kentcdodds',         # Popular JavaScript developer
    'sindresorhus',       # Prolific open source contributor
]


# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'commitiq'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# Utility functions
def log(message, level='INFO'):
    """Print message if verbose output is enabled."""
    if VERBOSE or level == 'ERROR':
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")

def random_string(length=10):
    """Generate random string for unique test data."""
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))

@contextmanager
def db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
    except Exception as e:
        log(f"Database connection error: {e}", 'ERROR')
        raise
    finally:
        if conn:
            conn.close()

def clear_test_data():
    """Remove test data from the database."""
    with db_connection() as conn:
        cur = conn.cursor()
        # Delete test data - cascade will remove related records
        cur.execute("DELETE FROM waitlist WHERE email LIKE %s", (f"%{TEST_EMAIL}%",))
        cur.execute("DELETE FROM github_analysis WHERE analyzer_email LIKE %s", (f"%{TEST_EMAIL}%",))
        conn.commit()

def check_server_status():
    """Check if the server is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

class TestAnalysis(unittest.TestCase):
    """Test cases for the GitHub username analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.base_url = f"{API_BASE_URL}/analyze"
    
    def test_analyze_valid_username(self):
        """Test analyzing a valid GitHub username."""
        # Use the POST endpoint
        response = requests.post(self.base_url, json={'username': TEST_USERNAME, 'email': TEST_EMAIL})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        log(f"Analysis response: {data}")
        
        # Verify response structure
        self.assertIn('analysis', data)
        self.assertIn('impact_score', data)
        self.assertIn('id', data, "Analysis ID should be returned")
        self.assertIn('github_username', data, "GitHub username should be returned")
        
        # Verify GitHub username is extracted correctly
        self.assertEqual(data['analysis'].get('username', '').lower(), TEST_USERNAME.lower())
        
        # Verify analysis data
        analysis = data['analysis']
        self.assertIsNotNone(analysis.get('total_commits'))
        self.assertIsNotNone(analysis.get('contributions'))
    
    def test_analyze_invalid_username(self):
        """Test analyzing an invalid GitHub username."""
        invalid_username = 'thisisnotavalidgithubusername' + random_string(10)
        response = requests.post(self.base_url, json={'username': invalid_username, 'email': TEST_EMAIL})
        
        # API should return a status code indicating an error
        self.assertIn(response.status_code, [400, 404])
        data = response.json()
        
        log(f"Invalid username response: {data}")
        
        # Verify error message
        self.assertIn('error', data)
    
    def test_analyze_github_url(self):
        """Test analyzing a GitHub URL instead of just username."""
        github_url = f"https://github.com/{TEST_USERNAME}"
        response = requests.post(self.base_url, json={'username': github_url, 'email': TEST_EMAIL})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify GitHub username is extracted correctly from URL
        self.assertEqual(data['analysis'].get('username', '').lower(), TEST_USERNAME.lower())
    
    def test_analyze_mixed_case_username(self):
        """Test analyzing a username with mixed case."""
        mixed_case = ''.join([c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(TEST_USERNAME)])
        response = requests.post(self.base_url, json={'username': mixed_case, 'email': TEST_EMAIL})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Username should be normalized
        self.assertEqual(data['analysis'].get('username', '').lower(), TEST_USERNAME.lower())

class TestDatabaseCapture(unittest.TestCase):
    """Test cases for database capture of analysis data."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.username = TEST_USERNAME
        self.email = f"db_test_{random_string()}@{TEST_EMAIL.split('@')[1]}"
        
    def test_analysis_captured_in_database(self):
        """Test that GitHub analysis is captured in the database."""
        # First, analyze a profile
        response = requests.post(f"{API_BASE_URL}/analyze", json={'username': self.username, 'email': self.email})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Wait briefly for database operations to complete
        time.sleep(1)
        
        # Check database for the record
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, github_username, impact_score FROM github_analysis WHERE analyzer_email = %s",
                (self.email,)
            )
            result = cur.fetchone()
            
            self.assertIsNotNone(result, "Analysis record not found in database")
            db_id, db_username, db_impact_score = result
            
            log(f"Database record: ID={db_id}, Username={db_username}, Impact Score={db_impact_score}")
            
            # Verify the Github username matches
            self.assertEqual(db_username.lower(), self.username.lower())
            
            # Verify impact_score matches API response
            self.assertAlmostEqual(db_impact_score, data['impact_score'], delta=0.01)
            
            # Verify details were captured
            cur.execute(
                "SELECT analysis_id FROM github_analysis_details WHERE analysis_id = %s",
                (db_id,)
            )
            detail_result = cur.fetchone()
            self.assertIsNotNone(detail_result, "Analysis details not found in database")

class TestWaitlist(unittest.TestCase):
    """Test cases for waitlist functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.base_url = f"{API_BASE_URL}/waitlist"
        self.email = f"waitlist_test_{random_string()}@{TEST_EMAIL.split('@')[1]}"
        self.name = f"Test User {random_string(5)}"
        
    def test_join_waitlist(self):
        """Test joining the waitlist."""
        response = requests.post(self.base_url, json={
            'email': self.email,
            'name': self.name,
            'company': 'Test Company',
            'feedback': 'This is test feedback'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        log(f"Join waitlist response: {data}")
        
        # Verify response
        self.assertIn('message', data)
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        
        # Verify database entry
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT email, name, feedback FROM waitlist WHERE email = %s",
                (self.email,)
            )
            result = cur.fetchone()
            
            self.assertIsNotNone(result, "Waitlist record not found in database")
            db_email, db_name, db_feedback = result
            
            self.assertEqual(db_email, self.email)
            self.assertEqual(db_name, self.name)
            self.assertEqual(db_feedback, 'This is test feedback')
    
    def test_join_waitlist_duplicate(self):
        """Test joining the waitlist with duplicate email."""
        # First join
        requests.post(self.base_url, json={
            'email': self.email,
            'name': self.name,
            'feedback': 'Initial feedback'
        })
        
        # Second join with same email
        response = requests.post(self.base_url, json={
            'email': self.email,
            'name': f"Updated {self.name}",
            'feedback': 'Updated feedback'
        })
        
        data = response.json()
        log(f"Duplicate waitlist response: {data}")
        
        # Verify database has updated entry
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name, feedback FROM waitlist WHERE email = %s",
                (self.email,)
            )
            result = cur.fetchone()
            
            self.assertIsNotNone(result, "Waitlist record not found in database")
            db_name, db_feedback = result
            
            # Name should be updated
            self.assertEqual(db_name, f"Updated {self.name}")
            # Feedback should be updated
            self.assertEqual(db_feedback, 'Updated feedback')
            
            # There should only be one record
            cur.execute("SELECT COUNT(*) FROM waitlist WHERE email = %s", (self.email,))
            count = cur.fetchone()[0]
            self.assertEqual(count, 1, "Multiple waitlist records found for the same email")

class TestShare(unittest.TestCase):
    """Test cases for sharing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.email = f"share_test_{random_string()}@{TEST_EMAIL.split('@')[1]}"
        # Analyze a profile first to get an analysis ID
        response = requests.post(f"{API_BASE_URL}/analyze", json={
            'username': TEST_USERNAME,
            'email': self.email
        })
        self.assertEqual(response.status_code, 200)
        
        # Get analysis ID from the response
        data = response.json()
        self.analysis_id = data.get('id')
        self.assertIsNotNone(self.analysis_id, "Analysis ID not returned in response")
        log(f"Using analysis ID {self.analysis_id} for share tests")
    
    def test_create_share_link(self):
        """Test creating a share link."""
        response = requests.post(
            f"{API_BASE_URL}/share/create/{self.analysis_id}",
            json={'email': self.email, 'days_valid': 30, 'is_public': True}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        log(f"Share link response: {data}")
        
        # Verify response structure
        self.assertIn('share_id', data)
        self.assertIn('share_url', data)
        self.assertIn('expires_at', data)
        
        # Verify database entry
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT share_id, created_by, analysis_id FROM shared_analysis WHERE share_id = %s",
                (data['share_id'],)
            )
            result = cur.fetchone()
            
            self.assertIsNotNone(result, "Share record not found in database")
            db_share_id, db_created_by, db_analysis_id = result
            
            self.assertEqual(db_share_id, data['share_id'])
            self.assertEqual(db_created_by, self.email)
            self.assertEqual(db_analysis_id, self.analysis_id)
        
        # Save share info for view test
        self.share_id = data['share_id']
        self.share_url = data['share_url']
    
    def test_view_shared_analysis(self):
        """Test viewing a shared analysis."""
        # First create a share
        self.test_create_share_link()
        
        # Now view the share
        response = requests.get(f"{API_BASE_URL}/share/view/{self.share_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        log(f"View shared analysis response keys: {data.keys()}")
        
        # Verify response structure
        self.assertIn('share_info', data)
        self.assertIn('analysis', data)
        
        # Verify analysis data
        self.assertEqual(data['analysis']['id'], self.analysis_id)
        
        # Verify access count incremented
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT access_count FROM shared_analysis WHERE share_id = %s",
                (self.share_id,)
            )
            result = cur.fetchone()
            self.assertIsNotNone(result)
            self.assertGreaterEqual(result[0], 1, "Access count not incremented")
    
    def test_download_analysis_report(self):
        """Test downloading an analysis report."""
        # Test JSON format (simpler to verify)
        response = requests.get(f"{API_BASE_URL}/share/download/{self.analysis_id}?format=json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify data structure
        self.assertEqual(data['id'], self.analysis_id)
        self.assertIn('github_username', data)
        
        # Test PDF format - just verify content type
        response = requests.get(f"{API_BASE_URL}/share/download/{self.analysis_id}?format=pdf", stream=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        
        # Verify Content-Disposition header suggests a filename
        self.assertIn('attachment; filename=', response.headers.get('Content-Disposition', ''))

class TestTracking(unittest.TestCase):
    """Test cases for analytics tracking functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.email = f"tracking_test_{random_string()}@{TEST_EMAIL.split('@')[1]}"
        
    def test_analysis_tracking(self):
        """Test that analysis requests are tracked."""
        # Analyze multiple profiles
        usernames = SAMPLE_GITHUB_USERNAMES[:3]  # Use first 3 sample usernames
        analysis_ids = []
        
        for username in usernames:
            response = requests.post(f"{API_BASE_URL}/analyze", json={
                'username': username,
                'email': self.email
            })
            self.assertEqual(response.status_code, 200)
            
            # Get analysis ID from response
            data = response.json()
            analysis_id = data.get('id')
            self.assertIsNotNone(analysis_id, f"Analysis ID not returned for username {username}")
            analysis_ids.append(analysis_id)
            
            # Wait briefly for tracking to complete
            time.sleep(1)
        
        # Verify records exist in tracking tables
        with db_connection() as conn:
            cur = conn.cursor()
            
            # Check if all usernames were tracked
            cur.execute(
                """
                SELECT github_username FROM github_analysis 
                WHERE analyzer_email = %s
                ORDER BY analyzed_at DESC
                LIMIT 3
                """,
                (self.email,)
            )
            results = cur.fetchall()
            tracked_usernames = [row[0] for row in results]
            
            # Verify all usernames are tracked (in any order)
            for username in usernames:
                self.assertTrue(
                    any(tracked.lower() == username.lower() for tracked in tracked_usernames),
                    f"Username {username} not found in tracking data"
                )
            
            # Verify details exist for all analyses
            for analysis_id in analysis_ids:
                cur.execute(
                    "SELECT analysis_id FROM github_analysis_details WHERE analysis_id = %s",
                    (analysis_id,)
                )
                self.assertIsNotNone(cur.fetchone(), f"No details found for analysis ID {analysis_id}")
                
    def test_share_tracking(self):
        """Test that share activities are tracked."""
        # First analyze a profile
        response = requests.post(f"{API_BASE_URL}/analyze", json={
            'username': TEST_USERNAME,
            'email': self.email
        })
        self.assertEqual(response.status_code, 200)
        
        # Get analysis ID from response
        data = response.json()
        analysis_id = data.get('id')
        self.assertIsNotNone(analysis_id, "Analysis ID not returned in response")
        
        # Create multiple shares
        share_ids = []
        for days_valid in [7, 30, 90]:
            response = requests.post(
                f"{API_BASE_URL}/share/create/{analysis_id}",
                json={'email': self.email, 'days_valid': days_valid}
            )
            self.assertEqual(response.status_code, 200)
            share_ids.append(response.json()['share_id'])
        
        # Verify user shares endpoint
        response = requests.get(f"{API_BASE_URL}/share/user-shares?email={self.email}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify all shares are listed
        self.assertIn('shares', data)
        self.assertIn('count', data)
        self.assertEqual(data['count'], len(share_ids))
        
        # Verify each share ID is in the response
        response_share_ids = [share['share_id'] for share in data['shares']]
        for share_id in share_ids:
            self.assertIn(share_id, response_share_ids)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='CommitIQ Test Suite')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed test output')
    parser.add_argument('--module', type=str, help='Run only tests for the specified module')
    parser.add_argument('--list', '-l', action='store_true', help='List all available tests')
    
    return parser.parse_args()

def list_tests():
    """List all available tests."""
    test_classes = [
        (TestAnalysis, "GitHub username analysis tests"),
        (TestDatabaseCapture, "Database capture tests"),
        (TestWaitlist, "Waitlist functionality tests"),
        (TestShare, "Share and download tests"),
        (TestTracking, "Analytics tracking tests"),
    ]
    
    print("\nAvailable test modules:")
    for test_class, description in test_classes:
        print(f"  - {test_class.__name__.lower()[4:]:10} : {description}")
        for name in dir(test_class):
            if name.startswith('test_'):
                test_method = getattr(test_class, name)
                if callable(test_method):
                    doc = test_method.__doc__ or "No description"
                    print(f"      - {name[5:]:25} : {doc.strip()}")
    print("\nUsage: python test_suite.py [--verbose] [--module=NAME]")
    print("       python test_suite.py --list")
    
def main():
    """Main entry point for the test suite."""
    args = parse_args()
    global VERBOSE
    
    if args.list:
        list_tests()
        return 0
    
    VERBOSE = args.verbose
    
    # Check if the server is running
    if not check_server_status():
        print("\nERROR: CommitIQ server is not running!")
        print(f"Make sure the server is running at {API_BASE_URL}")
        return 1
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes based on module argument
    if args.module:
        module_map = {
            'analysis': [TestAnalysis],
            'database': [TestDatabaseCapture],
            'waitlist': [TestWaitlist],
            'share': [TestShare],
            'tracking': [TestTracking],
        }
        
        if args.module not in module_map:
            print(f"Unknown module: {args.module}")
            print("Available modules: analysis, database, waitlist, share, tracking")
            return 1
        
        for test_class in module_map[args.module]:
            suite.addTests(loader.loadTestsFromTestCase(test_class))
    else:
        # Add all test classes
        suite.addTests(loader.loadTestsFromTestCase(TestAnalysis))
        suite.addTests(loader.loadTestsFromTestCase(TestDatabaseCapture))
        suite.addTests(loader.loadTestsFromTestCase(TestWaitlist))
        suite.addTests(loader.loadTestsFromTestCase(TestShare))
        suite.addTests(loader.loadTestsFromTestCase(TestTracking))
    
    # Run tests
    print("\n========== CommitIQ Test Suite ==========")
    print(f"Running tests against API at: {API_BASE_URL}")
    print(f"Test mode: {'Verbose' if VERBOSE else 'Standard'}")
    if args.module:
        print(f"Testing module: {args.module}")
    print("==========================================\n")
    
    # Create test runner
    runner = unittest.TextTestRunner(verbosity=2 if VERBOSE else 1)
    result = runner.run(suite)
    
    # Print summary
    print("\n========== Test Summary ==========")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("==================================\n")
    
    # Clean up test data
    try:
        clear_test_data()
        log("Test data cleaned up successfully")
    except Exception as e:
        log(f"Error cleaning up test data: {e}", 'ERROR')
    
    # Return non-zero exit code if any tests failed
    return 1 if result.failures or result.errors else 0

if __name__ == '__main__':
    sys.exit(main()) 