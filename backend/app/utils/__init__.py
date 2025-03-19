"""
Utility functions and services for the CommitIQ application.
"""
import re

def normalize_github_username(username):
    """
    Normalize a GitHub username by extracting it from various formats.
    
    Args:
        username (str): Input string that may contain a GitHub username
        
    Returns:
        str: Normalized GitHub username or None if invalid
    """
    if not username:
        return None
    
    # Remove whitespace
    username = username.strip()
    
    # Handle common formats
    
    # 1. Plain username
    if re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9]*$', username):
        return username
    
    # 2. @username format (from Twitter-style mentions)
    if username.startswith('@'):
        clean_username = username[1:]
        if re.match(r'^[a-zA-Z0-9][-a-zA-Z0-9]*$', clean_username):
            return clean_username
    
    # 3. github.com/username format
    github_url_pattern = r'(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9][-a-zA-Z0-9]*)'
    match = re.search(github_url_pattern, username)
    if match:
        return match.group(1)
    
    # If we couldn't extract a valid username, return None
    return None

# Import commonly used services to make them accessible from the utils package
from .cache_service import cache_service, cache_response
from .github_api import github_api
from .analysis_service import analysis_service
from .pdf_service import pdf_service 