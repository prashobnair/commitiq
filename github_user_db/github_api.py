import requests
import time
import logging
import os
from urllib.parse import parse_qs, urlparse
from concurrent.futures import ThreadPoolExecutor
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# GitHub API constants
GITHUB_API_URL = "https://api.github.com"
USERS_ENDPOINT = f"{GITHUB_API_URL}/users"
DEFAULT_PER_PAGE = 100  # Maximum allowed by GitHub API
DEFAULT_TIMEOUT = 10  # seconds

# Rate limiting
DEFAULT_RATE_LIMIT = 5000  # Default GitHub API rate limit per hour
RATE_LIMIT_RESET_PERIOD = 3600  # 1 hour in seconds
RATE_LIMIT_BUFFER = 100  # Buffer to avoid hitting the limit exactly
MIN_REQUESTS_INTERVAL = 0.1  # Minimum time between requests in seconds

# Thread-safe rate limit tracking
class RateLimiter:
    def __init__(self, limit=DEFAULT_RATE_LIMIT, period=RATE_LIMIT_RESET_PERIOD):
        self.limit = limit
        self.period = period
        self.remaining = limit
        self.reset_time = time.time() + period
        self.lock = threading.RLock()
        
    def update_from_headers(self, headers):
        """Update rate limit info from GitHub API response headers."""
        with self.lock:
            if 'X-RateLimit-Remaining' in headers:
                self.remaining = int(headers['X-RateLimit-Remaining'])
            
            if 'X-RateLimit-Reset' in headers:
                self.reset_time = int(headers['X-RateLimit-Reset'])
            
            if 'X-RateLimit-Limit' in headers:
                self.limit = int(headers['X-RateLimit-Limit'])
                
            logger.debug(f"Rate limit updated: {self.remaining}/{self.limit}, resets at {self.reset_time}")
    
    def wait_if_needed(self):
        """Wait if we're close to hitting the rate limit."""
        with self.lock:
            # If we're below the buffer threshold
            if self.remaining < RATE_LIMIT_BUFFER:
                current_time = time.time()
                
                # If reset time is in the future, wait until then
                if current_time < self.reset_time:
                    wait_time = self.reset_time - current_time + 1  # Add 1 second buffer
                    logger.warning(f"Rate limit nearly exhausted ({self.remaining}/{self.limit}). Waiting {wait_time:.2f}s for reset.")
                    time.sleep(wait_time)
                    self.remaining = self.limit  # Reset after waiting
                    self.reset_time = time.time() + self.period
            
            # Always wait a minimum time between requests to be polite
            time.sleep(MIN_REQUESTS_INTERVAL)

class GitHubClient:
    def __init__(self, token=None):
        """
        Initialize the GitHub API client.
        
        Args:
            token (str, optional): GitHub API token for authentication
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = requests.Session()
        self.rate_limiter = RateLimiter()
        
        # Set up headers
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CommitIQ-GitHub-User-Collector"
        })
        
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})
            logger.info("GitHub API client initialized with authentication token")
        else:
            logger.warning("GitHub API client initialized without authentication token. Rate limits will be lower.")
    
    def get_users(self, since_id=0, per_page=DEFAULT_PER_PAGE):
        """
        Get a page of GitHub users.
        
        Args:
            since_id (int): User ID to start listing from
            per_page (int): Number of users per page (max 100)
            
        Returns:
            tuple: (list of users, next_since_id or None if no more pages)
        """
        # Wait if we're close to rate limit
        self.rate_limiter.wait_if_needed()
        
        params = {
            "since": since_id,
            "per_page": min(per_page, DEFAULT_PER_PAGE)  # Ensure we don't exceed GitHub's max
        }
        
        try:
            response = self.session.get(
                USERS_ENDPOINT, 
                params=params,
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            
            # Update rate limit info
            self.rate_limiter.update_from_headers(response.headers)
            
            # Parse users from response
            users = response.json()
            
            # Get next page info from Link header
            next_since_id = None
            if 'Link' in response.headers:
                links = self._parse_link_header(response.headers['Link'])
                if 'next' in links:
                    next_url = links['next']
                    query_params = parse_qs(urlparse(next_url).query)
                    if 'since' in query_params:
                        next_since_id = int(query_params['since'][0])
            
            return users, next_since_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GitHub users: {e}")
            # If we hit rate limit, wait and retry
            if hasattr(e.response, 'status_code') and e.response.status_code == 403:
                if 'X-RateLimit-Remaining' in e.response.headers and int(e.response.headers['X-RateLimit-Remaining']) == 0:
                    self.rate_limiter.update_from_headers(e.response.headers)
                    self.rate_limiter.wait_if_needed()
                    return self.get_users(since_id, per_page)
            return [], since_id
    
    def _parse_link_header(self, link_header):
        """Parse GitHub's Link header for pagination."""
        links = {}
        for link in link_header.split(','):
            url, rel = link.split(';')
            url = url.strip('<>')
            rel = rel.split('=')[1].strip('"')
            links[rel] = url
        return links

def fetch_users_parallel(since_id=0, max_workers=5, batch_size=100, max_batches=None):
    """
    Fetch GitHub users in parallel while respecting rate limits.
    
    Args:
        since_id (int): User ID to start from
        max_workers (int): Maximum number of parallel workers
        batch_size (int): Number of users per API request (max 100)
        max_batches (int, optional): Maximum number of batches to fetch
        
    Yields:
        list: Batches of GitHub users
    """
    client = GitHubClient()
    next_ids = [since_id]
    batches_fetched = 0
    
    # Create a shared rate limiter for all threads
    rate_limiter = client.rate_limiter
    
    def fetch_batch(batch_since_id):
        """Fetch a single batch of users."""
        # Create a new client for each thread but share the rate limiter
        thread_client = GitHubClient()
        thread_client.rate_limiter = rate_limiter
        
        users, next_since_id = thread_client.get_users(batch_since_id, batch_size)
        return users, next_since_id
    
    while next_ids and (max_batches is None or batches_fetched < max_batches):
        # Get the next batch of since_ids to process
        current_batch_ids = next_ids[:max_workers]
        next_ids = next_ids[max_workers:]
        
        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=min(max_workers, len(current_batch_ids))) as executor:
            futures = [executor.submit(fetch_batch, since_id) for since_id in current_batch_ids]
            
            for future in futures:
                try:
                    users, next_since_id = future.result()
                    batches_fetched += 1
                    
                    if users:
                        yield users
                    
                    if next_since_id:
                        next_ids.append(next_since_id)
                        
                except Exception as e:
                    logger.error(f"Error in parallel fetch: {e}")
        
        # If we've run out of next_ids but still have more pages
        if not next_ids and next_since_id:
            next_ids.append(next_since_id) 