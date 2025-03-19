#!/usr/bin/env python3
"""
Test the GitHub username normalization functionality.
"""
import sys
import os
import unittest

# Add the parent directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils import normalize_github_username

class TestUsernameNormalization(unittest.TestCase):
    """Test case for GitHub username normalization."""

    def test_plain_username(self):
        """Test with a plain username."""
        self.assertEqual(normalize_github_username('octocat'), 'octocat')
    
    def test_leading_trailing_whitespace(self):
        """Test with leading and trailing whitespace."""
        self.assertEqual(normalize_github_username('  octocat  '), 'octocat')
    
    def test_mixed_case(self):
        """Test with mixed case."""
        self.assertEqual(normalize_github_username('OcToCaT'), 'octocat')
    
    def test_at_username(self):
        """Test with @username format."""
        self.assertEqual(normalize_github_username('@octocat'), 'octocat')
    
    def test_github_url(self):
        """Test with github.com URL."""
        self.assertEqual(normalize_github_username('github.com/octocat'), 'octocat')
    
    def test_https_github_url(self):
        """Test with https://github.com URL."""
        self.assertEqual(normalize_github_username('https://github.com/octocat'), 'octocat')
    
    def test_http_github_url(self):
        """Test with http://github.com URL."""
        self.assertEqual(normalize_github_username('http://github.com/octocat'), 'octocat')
    
    def test_www_github_url(self):
        """Test with www.github.com URL."""
        self.assertEqual(normalize_github_username('www.github.com/octocat'), 'octocat')
    
    def test_github_url_with_trailing_slash(self):
        """Test with trailing slash."""
        self.assertEqual(normalize_github_username('https://github.com/octocat/'), 'octocat')
    
    def test_github_url_with_query_params(self):
        """Test with query parameters."""
        self.assertEqual(
            normalize_github_username('https://github.com/octocat?tab=repositories'),
            'octocat'
        )
    
    def test_github_url_with_repo(self):
        """Test with repository path."""
        self.assertEqual(
            normalize_github_username('https://github.com/octocat/hello-world'),
            'octocat'
        )
    
    def test_empty_input(self):
        """Test with empty input."""
        self.assertIsNone(normalize_github_username(''))
    
    def test_none_input(self):
        """Test with None input."""
        self.assertIsNone(normalize_github_username(None))
    
    def test_only_whitespace(self):
        """Test with only whitespace."""
        self.assertIsNone(normalize_github_username('   '))
    
    def test_invalid_characters(self):
        """Test with invalid characters."""
        # Should still return the lowercased string even with invalid chars
        self.assertEqual(normalize_github_username('octo$cat'), 'octo$cat')
    
    def test_github_enterprise_url(self):
        """Test with GitHub Enterprise URL."""
        # Should not extract username from non-github.com domains
        self.assertEqual(
            normalize_github_username('https://github.mycompany.com/octocat'),
            'https://github.mycompany.com/octocat'
        )

if __name__ == '__main__':
    unittest.main() 