"""
Utility functions for the CommitIQ backend application.
"""
import re
import logging
from urllib.parse import urlparse, parse_qs

# Configure logger
logger = logging.getLogger(__name__)

def normalize_github_username(input_string):
    """
    Normalize a GitHub username from various input formats.
    
    This function accepts:
    - GitHub usernames (octocat)
    - GitHub profile URLs (github.com/octocat, https://github.com/octocat)
    - GitHub URLs with parameters (https://github.com/octocat?tab=repositories)
    - GitHub handles (@octocat)
    
    Args:
        input_string (str): GitHub username in any format
        
    Returns:
        str: Normalized GitHub username or None if the input is invalid
    """
    if not input_string:
        return None
    
    # Trim whitespace
    cleaned_input = input_string.strip()
    
    # If it's empty after trimming, return None
    if not cleaned_input:
        return None
    
    # Handle GitHub handle format (@username)
    if cleaned_input.startswith('@'):
        return cleaned_input[1:].lower()
    
    # Check if it's a URL
    if '/' in cleaned_input or '.' in cleaned_input:
        # Try to parse as URL
        try:
            # Add scheme if missing
            if not cleaned_input.startswith(('http://', 'https://')):
                cleaned_input = 'https://' + cleaned_input
            
            # Parse URL
            parsed_url = urlparse(cleaned_input)
            
            # Check if it's a GitHub URL
            if parsed_url.netloc in ('github.com', 'www.github.com'):
                # Extract username from path
                path_parts = [p for p in parsed_url.path.split('/') if p]
                if path_parts:
                    return path_parts[0].lower()  # First component after domain is the username
        except Exception as e:
            logger.debug(f"Error parsing URL {cleaned_input}: {e}")
            # If URL parsing fails, continue with other methods
    
    # If it wasn't a URL or URL parsing failed, treat as a raw username
    # Remove any invalid characters (only allow letters, numbers, hyphens, and underscores)
    username_pattern = re.compile(r'^[a-zA-Z0-9-]+$')
    if username_pattern.match(cleaned_input):
        return cleaned_input.lower()
    
    # If we've made it here, the input format wasn't recognized
    logger.debug(f"Could not normalize GitHub username from input: {input_string}")
    return cleaned_input.lower()
