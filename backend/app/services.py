import requests
from datetime import datetime, timedelta
import os
from flask import jsonify
import time
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import logging
from functools import lru_cache, wraps
import json
import aiohttp
import asyncio
import random
import zlib
import sys

# Get logger for this module
logger = logging.getLogger(__name__)

# Try to import Redis, but make it optional
try:
    import redis
    redis_available = True
    r = redis.Redis(host='localhost', port=6379, db=0)
    # Test Redis connection
    r.ping()
    logger.info("Redis cache available")
except (ImportError, redis.exceptions.ConnectionError) as e:
    redis_available = False
    r = None
    logger.warning(f"Redis not available: {str(e)}. Using in-memory cache.")


# Initialize Redis client for caching if available
redis_available = False
r = None

try:
    import redis
    # Connect to Redis - preferring environment variable config
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    r = redis.from_url(redis_url)
    r.ping()  # Test connection
    redis_available = True
    logging.info("Redis cache available")
except (ImportError, redis.ConnectionError, redis.RedisError) as e:
    logging.warning(f"Redis not available: {str(e)}. Using in-memory cache.")
    # Fall back to lru_cache

# Simple in-memory cache for fallback when Redis is not available
memory_cache = {}

def get_cache_instance():
    """Returns the appropriate cache instance (Redis or in-memory)"""
    global redis_available
    
    if redis_available and r:
        try:
            # Verify Redis is still connected
            r.ping()
            
            # Return a Redis cache adapter
            class RedisCache:
                def get(self, key):
                    value = r.get(key)
                    return json.loads(value) if value else None
                
                def set(self, key, value, ttl):
                    if isinstance(value, bytes):
                        # Store binary data directly
                        r.setex(key, ttl, value)
                    else:
                        # Convert to JSON for regular data
                        r.setex(key, ttl, json.dumps(value))
            
            return RedisCache()
        except (redis.ConnectionError, redis.RedisError) as e:
            logger.error(f"Redis error: {str(e)}")
            redis_available = False
    
    # Fall back to memory cache
    class MemoryCache:
        def get(self, key):
            # Check if the entry exists and is not expired
            entry = memory_cache.get(key)
            if entry and entry['expiry'] > time.time():
                return entry['data']
            return None
        
        def set(self, key, value, ttl):
            memory_cache[key] = {
                'data': value,
                'expiry': time.time() + ttl
            }
            
            # Garbage collection for memory cache (random probability to avoid overhead)
            if random.random() < 0.01:  # 1% chance on each cache set
                self._cleanup()
        
        def _cleanup(self):
            """Remove expired items from memory cache"""
            now = time.time()
            expired_keys = [k for k, v in memory_cache.items() if v['expiry'] < now]
            for k in expired_keys:
                del memory_cache[k]
    
    return MemoryCache()

# Define constants
BOT_IDENTIFIERS = ['bot', 'actions', '-ci-', 'automation', 'dependabot']



# Caching decorator
def cache_response(ttl=3600):
    """Decorator to cache API responses
    
    Args:
        ttl (int): Time-to-live for cache in seconds. Default 1 hour.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(username, *args, **kwargs):
            # Check if we should disable caching
            is_dev_mode = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('DISABLE_CACHE') == 'true'
            
            if is_dev_mode:
                # In development mode, skip caching and call the function directly
                logger.info(f"Caching disabled in development mode for {func.__name__}")
                return func(username, *args, **kwargs)
            
            cache_key = f"{func.__name__}:{username}:{json.dumps(args)}:{json.dumps(kwargs, sort_keys=True)}"
            cache = get_cache_instance()
            
            # Check if result is in cache
            cached_result = cache.get(cache_key)
            
            if cached_result:
                # Check if it's a compressed result (for GraphQL responses)
                if isinstance(cached_result, bytes):
                    try:
                        decompressed = zlib.decompress(cached_result)
                        return json.loads(decompressed)
                    except (ImportError, zlib.error, json.JSONDecodeError) as e:
                        logger.error(f"Error decompressing cached result: {str(e)}")
                        # Fall through to re-fetch the data
                        cached_result = None
                else:
                    # Regular cached result
                    return cached_result
            
            # Cache miss or compression error, call the function
            result = func(username, *args, **kwargs)
            
            # Only cache successful results
            if result and not (isinstance(result, dict) and 'error' in result):
                # Check if this is a GraphQL response (large)
                is_large_response = (
                    'graphql' in func.__name__.lower() or 
                    (isinstance(result, dict) and any(k in str(result).lower() for k in ['user', 'repository', 'contribution']))
                ) and len(json.dumps(result)) > 10000  # Only compress responses over 10KB
                
                if is_large_response:
                    try:
                        # Compress the result to save memory in cache
                        compressed = zlib.compress(json.dumps(result).encode('utf-8'))
                        cache.set(cache_key, compressed, ttl)
                    except (ImportError, TypeError, json.JSONEncodeError) as e:
                        logger.error(f"Error compressing result for cache: {str(e)}")
                        # Fall back to regular caching
                        cache.set(cache_key, result, ttl)
                else:
                    # Regular caching for smaller responses
                    cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator

# GitHub API class for rate limit handling
class GitHubAPI:
    def __init__(self):
        # Get tokens from environment variable (comma-separated list)
        tokens_str = os.environ.get("GITHUB_TOKENS", os.environ.get("GITHUB_TOKEN", ""))
        self.tokens = [t.strip() for t in tokens_str.split(',') if t.strip()]
        
        # Fallback to single token if no tokens list is provided
        if not self.tokens:
            logger.warning("No GitHub tokens found in environment variables")
            self.tokens = [""]  # Empty token as fallback
            
        self.current_token_index = 0
        self.last_call = 0
        self.token_rate_limits = {token: {'remaining': 5000, 'reset_time': 0} for token in self.tokens}
        
    def get_token(self):
        """Get the next available token using round-robin rotation"""
        # If we only have one token, just return it
        if len(self.tokens) == 1:
            return self.tokens[0]
            
        # Try to find a token with remaining rate limit
        start_index = self.current_token_index
        while True:
            token = self.tokens[self.current_token_index]
            
            # Check if this token has remaining rate limit
            if self.token_rate_limits[token]['remaining'] > 10:
                return token
                
            # Check if reset time has passed
            if time.time() > self.token_rate_limits[token]['reset_time']:
                # Reset the remaining count since the reset time has passed
                self.token_rate_limits[token]['remaining'] = 5000
                return token
                
            # Move to the next token
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            
            # If we've checked all tokens and come back to the start, use the one with the earliest reset time
            if self.current_token_index == start_index:
                # Find token with earliest reset time
                token = min(self.tokens, key=lambda t: self.token_rate_limits[t]['reset_time'])
                
                # If all tokens are rate limited, sleep until the earliest reset time
                sleep_duration = max(self.token_rate_limits[token]['reset_time'] - time.time(), 10)
                if sleep_duration > 0:
                    logger.warning(f"All tokens rate limited. Sleeping for {sleep_duration} seconds")
                    time.sleep(sleep_duration)
                    
                return token
        
    def make_request(self, url: str) -> requests.Response:
        """Make a rate-limited request to the GitHub API using token rotation"""
        # Get the next available token
        token = self.get_token()
        headers = {'Authorization': f'token {token}'} if token else {}
        
        # Respect GitHub's rate limits with a small delay between requests
        now = time.time()
        if now - self.last_call < 1.1:
            time.sleep(1.1 - (now - self.last_call))
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            self.last_call = time.time()
            
            # Handle rate limiting response with status code 403
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and int(response.headers.get('X-RateLimit-Remaining', 0)) == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(reset_time - time.time(), 10)
                
                if len(self.tokens) > 1:
                    # If multiple tokens available, mark this one as rate-limited
                    self.token_rate_limits[token]['remaining'] = 0
                    self.token_rate_limits[token]['reset_time'] = reset_time
                    # Recursive call to retry with a different token
                    return self.make_request(url)
                else:
                    # Only one token available, need to wait
                    logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds")
                    time.sleep(wait_time)
                    return self.make_request(url)
            
            # Update rate limit information for this token
            self.handle_rate_limits(response, token)
            
            return response
        except requests.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            # Raise exception to be handled by caller
            raise
    
    def handle_rate_limits(self, response: requests.Response, token: str) -> None:
        """Handle GitHub API rate limits and update token status"""
        # Skip if no token or not a GitHub API response
        if not token or 'X-RateLimit-Remaining' not in response.headers:
            return
            
        # Update rate limit information for this token - use safer int conversion
        try:
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            self.token_rate_limits[token] = {
                'remaining': remaining,
                'reset_time': reset_time
            }
            
            # Log warning if rate limit is getting low
            if remaining < 10:
                sleep_duration = max(reset_time - time.time(), 10)
                logger.warning(f"Rate limit almost reached for token. Remaining: {remaining}. Reset in {sleep_duration} seconds")
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing rate limit headers: {e}")
            # Keep existing values if parsing fails
            pass

# --- Constants ---
MAX_STARS = 10000  # Normalization baseline for stars
MAX_FORKS = 50000 # Example
MAX_CONTRIBUTORS = 100  # Normalization baseline for contributors
MAX_COMMITS = 2000
MAX_PRS = 500
MAX_ISSUES = 500
MAX_REVIEWS = 500
TIME_WINDOW_DAYS = 365  # Analyze 1 year of history instead of 2 for better performance

# --- Helper Functions ---
def is_bot(user_data: any) -> bool:
    """Check if user is a bot account using GitHub's official bot detection"""
    # Handle empty input
    if not user_data:
        return False
    
    if isinstance(user_data, dict):
        return user_data.get('type') == 'Bot' or any(
            bot_id in user_data.get('login', '').lower() 
            for bot_id in BOT_IDENTIFIERS
        )
    else:
        # If it's a string (username), use it directly
        login = str(user_data)
        return any(bot_id in login.lower() for bot_id in BOT_IDENTIFIERS)

def calculate_commit_frequency(commits, time_window_days=TIME_WINDOW_DAYS):
    """
    Calculate the commit frequency as commits per day over a time window.
    """
    if not commits:
        return 0
    
    # Extract dates from commits and sort them
    dates = []
    for commit in commits:
        if isinstance(commit, dict) and 'commit' in commit:
            try:
                # Handle the case where commit date might be in different formats
                commit_date = commit.get('commit', {}).get('committer', {}).get('date')
                if commit_date:
                    if isinstance(commit_date, str):
                        date = datetime.strptime(commit_date, '%Y-%m-%dT%H:%M:%SZ')
                    elif isinstance(commit_date, datetime):
                        date = commit_date
                    else:
                        continue
                    dates.append(date)
            except Exception as e:
                logger.error(f"Error parsing commit date: {e}, commit: {commit}")
                continue
    
    if not dates:
        return 0

    # Calculate commits within the time window
    two_years_ago = datetime.now() - timedelta(days=time_window_days)
    commits_in_window = [date for date in dates if date >= two_years_ago]

    if not commits_in_window:
        return 0

    return len(commits_in_window) / time_window_days

def calculate_code_survival(commits: list) -> float:
    """Calculate percentage of code still present in latest commit (simplified)"""
    if not commits:
        return 100  # Default to max if no commits

    # Use sampling for large commit sets to avoid O(n²) complexity
    if len(commits) > 100:
        # Use either 10% of commits or 100 commits, whichever is larger
        sample_size = max(100, len(commits) // 10)
        # Ensure we include the most recent commits in our sample
        recent_commits = commits[:min(20, len(commits))]
        # Sample from the remaining commits
        if len(commits) > 20:
            remaining_sample = random.sample(commits[20:], min(sample_size - 20, len(commits) - 20))
            sample_commits = recent_commits + remaining_sample
        else:
            sample_commits = recent_commits
    else:
        sample_commits = commits

    total_additions = 0
    total_deletions = 0

    for commit in sample_commits:
        stats = commit.get('stats', {})
        total_additions += stats.get('additions', 0)
        total_deletions += stats.get('deletions', 0)

    if total_additions == 0:
        return 0  # Handle cases where additions might be zero.

    # Calculate the survival rate based on our sample
    return ((total_additions - total_deletions) / total_additions) * 100

def calculate_code_quality(commits: list) -> float:
    """Enhanced code quality analysis"""
    if not commits:
        return 0
        
    quality_score = 0
    for commit in commits:
        commit_message = commit.get('commit', {}).get('message', '').lower()
        
        # Award points for good practices based on commit message
        if 'test' in commit_message or 'spec' in commit_message:
            quality_score += 5  # Test files
        if 'fix' in commit_message or 'bug' in commit_message:
            quality_score += 2  # Bug fixes
        if 'refactor' in commit_message:
            quality_score += 3  # Refactoring
        if 'docs' in commit_message or 'documentation' in commit_message:
            quality_score += 2  # Documentation
        
        # Check files if available
        files = commit.get('files', [])
        if files:
            for file in files:
                filename = file.get('filename', '').lower()
                if filename.endswith(('.test.js', '.spec.js', '_test.py', '_spec.py', 'test_', 'spec_')):
                    quality_score += 3  # Test files
        
    # Normalize the score
    return min(quality_score / max(len(commits), 1), 100)

def calculate_consistency(pulls_data, reviews_data):
    """
    Calculate a consistency score based on the distribution of activity over time.
    
    A higher score indicates more consistent activity rather than bursts.
    Returns a value between 0 and 1.
    """
    # If no data, return 0 consistency
    if not pulls_data and not reviews_data:
        return 0
        
    # Collect all activity timestamps
    timestamps = []
    
    # Add PR timestamps
    for pr in pulls_data:
        if isinstance(pr, dict):
            created_at = pr.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        timestamps.append(datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ'))
                    elif isinstance(created_at, datetime):
                        timestamps.append(created_at)
                except (ValueError, TypeError):
                    pass  # Skip invalid timestamps
    
    # Add review timestamps
    for review in reviews_data:
        if isinstance(review, dict):
            submitted_at = review.get('submitted_at')
            if submitted_at:
                try:
                    if isinstance(submitted_at, str):
                        timestamps.append(datetime.strptime(submitted_at, '%Y-%m-%dT%H:%M:%SZ'))
                    elif isinstance(submitted_at, datetime):
                        timestamps.append(submitted_at)
                except (ValueError, TypeError):
                    pass  # Skip invalid timestamps
    
    # If no valid timestamps, return 0
    if not timestamps:
        return 0
        
    # Sort timestamps
    timestamps.sort()
    
    # Calculate time differences between consecutive activities
    time_diffs = []
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i-1]).total_seconds() / (60 * 60 * 24)  # Convert to days
        time_diffs.append(diff)
    
    # If only one activity, return minimum consistency
    if not time_diffs:
        return 0.1  # Some minimal consistency for having at least one activity
    
    # Calculate coefficient of variation (lower is more consistent)
    mean_diff = sum(time_diffs) / len(time_diffs)
    if mean_diff == 0:
        return 1.0  # Perfect consistency (all activities at the same time)
        
    variance = sum((diff - mean_diff) ** 2 for diff in time_diffs) / len(time_diffs)
    std_dev = variance ** 0.5
    cv = std_dev / mean_diff
    
    # Convert to a 0-1 score (lower CV means higher consistency)
    # Cap CV at 3 for normalization purposes
    capped_cv = min(cv, 3)
    consistency_score = 1 - (capped_cv / 3)
    
    return consistency_score

def normalize_metric(value: float, max_value: float) -> float:
    """Normalizes a metric to a 0-1 range."""
    if value is None:
        return 0
    return min(value / max_value, 1.0)


# --- Generic API Fetching Function ---
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
def get_user_contributions(url_template, username, contribution_type, **kwargs):
    """Generic pagination handler for GitHub API"""
    api = GitHubAPI()  # Use our new GitHubAPI class
    url = url_template.format(username=username, **kwargs)  # Pass additional params
    
    logger.debug(f"Fetching {contribution_type} for {username} from {url}")

    items = []
    next_url = url
    while next_url:
        try:
            response = api.make_request(next_url)  # Use the rate-limited request method
            response.raise_for_status()  # Raise HTTPError for bad requests (4XX, 5XX)
            data = response.json()

            # Handle different response structures
            if 'items' in data:  # Search API responses
                items.extend(data['items'])
            else:  # Direct list responses
                items.extend(data)

            # Handle pagination
            next_url = response.links.get('next', {}).get('url')
            # No need for sleep here as GitHubAPI.make_request handles rate limiting

        except RequestException as e:
            logger.error(f"Error fetching {contribution_type}: {str(e)}")
            return {'error': f"Error fetching {contribution_type}: {str(e)}"}
        except ValueError as e:
            logger.error(f"JSON parsing error for {contribution_type}: {str(e)}")
            return {'error': f"JSON parsing error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error fetching {contribution_type}: {str(e)}")
            return {'error': f"Unexpected error: {str(e)}"}

    return items

# --- Specific API Functions (using the generic function) ---

@cache_response()
def get_user_pulls(username):
    """Fetch user's pull requests from GitHub API"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=is:pr+author:{username}+created:>={date}&per_page=100'
    )
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "pull_requests", date=since_date)

@cache_response()
def get_user_issues(username):
    """Fetch user's issues from GitHub API"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=is:issue+author:{username}+created:>={date}&per_page=100'
    )
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "issues", date=since_date)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_user_reviews(username):
    """Fetch user's code reviews from GitHub API"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=is:pr+reviewed-by:{username}+created:>={date}&per_page=100'
    )
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "reviews", date=since_date)

@cache_response()
def get_user_repos(username):
    """Fetch user repositories, handling pagination.
    
    DEPRECATED: Use GraphQL data from get_user_contributions_graphql instead.
    This function is kept for backward compatibility and as a fallback.
    """
    logger.warning("get_user_repos is deprecated - use GraphQL data instead")
    url_template = f'https://api.github.com/users/{{username}}/repos?per_page=100'
    return get_user_contributions(url_template, username, "repositories")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_repo_commits(username, repo_name):
    """
    Get commits for a specific repository.
    
    DEPRECATED: Use GraphQL data from get_user_contributions_graphql instead.
    This function is kept for backward compatibility and as a fallback.
    The GraphQL query already fetches commit data through commitContributionsByRepository.
    """
    logger.warning("get_repo_commits is deprecated - use GraphQL data instead")
    github_api = GitHubAPI()
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=100"
    
    response = github_api.make_request(url)
    
    if response.status_code == 200:
        logger.debug(f"Fetching commits for repo: {repo_name}, URL: {url}, Status: {response.status_code}")
        return response.json()
    elif response.status_code == 409:  # Empty repository
        logger.debug(f"Empty repository detected for {repo_name} (409 Conflict)")
        return []
    else:
        logger.error(f"Error fetching commits for {repo_name}: Status {response.status_code} - {response.text}")
        return {"error": f"Failed to fetch commits: Status {response.status_code}"}

# --- Aggregation and Calculation Functions ---
@cache_response()
def aggregate_user_data(username, async_data=None):
    """Aggregate GitHub user data including repositories, commits, issues, and pull requests.
    
    This function has been updated to use GraphQL by default, and only falls back to
    REST API data when necessary. GraphQL provides more efficient data fetching.
    
    NOTE: The REST API fallback path is deprecated and will be removed in a future version.
    All new code should use the GraphQL API directly through aggregate_user_data_graphql.
    
    Args:
        username (str): GitHub username
        async_data (dict): Optional async data from fetch_all_data function
        
    Returns:
        dict: Aggregated user data with metrics
    """
    try:
        # First, try to use GraphQL as the primary data source
        if async_data and 'graphql_data' in async_data:
            # If we have GraphQL data from async fetching, use it directly
            graphql_result = {'data': async_data['graphql_data']}
            return aggregate_user_data_graphql(username, graphql_result)
        else:
            # Try to get data from GraphQL
            graphql_data = get_user_contributions_graphql(username)
            
            # If successful, use GraphQL data
            if not (isinstance(graphql_data, dict) and 'error' in graphql_data):
                return aggregate_user_data_graphql(username, {'data': graphql_data})
        
        # If GraphQL fails or is not available, fall back to REST API data
        logger.warning(f"Falling back to deprecated REST API data for {username}. This fallback will be removed in a future version.")
        
        # --- Original REST API processing code below ---
        
        # Get data from async_data if provided, or fetch directly
        if async_data:
            logger.info(f"Using async data for {username}")
            pulls_data = async_data.get('pulls', [])
            issues_data = async_data.get('issues', [])
            repos_data = async_data.get('repos', [])
            reviews_data = async_data.get('reviews', [])
            discussions_data = async_data.get('discussions', [])
            logger.info(f"Completed function")
        else:
            # Fetch data synchronously (slower)
            pulls_data = get_user_pulls(username)
            issues_data = get_user_issues(username)
            repos_data = get_user_repos(username)
            reviews_data = get_user_reviews(username)
            discussions_data = get_discussions(username)
        
        # Process the data to ensure it's in the right format
        if isinstance(pulls_data, dict) and 'items' in pulls_data:
            pulls_data = pulls_data.get('items', [])
        
        if isinstance(issues_data, dict) and 'items' in issues_data:
            issues_data = issues_data.get('items', [])
            
        if isinstance(reviews_data, dict) and 'items' in reviews_data:
            reviews_data = reviews_data.get('items', [])
            
        if isinstance(discussions_data, dict) and 'items' in discussions_data:
            discussions_data = discussions_data.get('items', [])
        
        # Initialize result structure
        aggregated_data = {
            'username': username,
            'total_contributions': 0,
            'total_commits': 0,
            'total_prs': 0,
            'merged_prs': 0,
            'total_issues': 0,
            'total_reviews': 0,
            'total_approved_reviews': 0,
            'total_review_comments': 0,
            'total_comments': 0,
            'code_quality': 0,
            'code_survival_rate': 0,
            'file_impact': 0,
            'consistency': 0,
            'project_impact': 0,
            'avg_pr_size': 0,
            'avg_issue_comments': 0,
            'repos': [],
            'top_languages': {},
            'impact_score': 0,
            # Add these keys explicitly for the impact score calculation
            'pull_requests': [],
            'reviews': [],
            'repositories': {},
            'metrics': {
                'consistency': 0,
                'avg_pr_size': {'files': 0},
                'review_comment_rate': 0
            }
        }
        
        # Process repositories and their commits
        all_commits = []
        for repo_data in repos_data:
            if isinstance(repo_data, dict) and 'error' in repo_data:
                continue  # Skip error repos
                
            repo_owner = repo_data.get('owner', {}).get('login', username)
            repo_name = repo_data.get('name', '')
            
            if not repo_name:
                continue
                
            # Get repository commits
            try:
                commits_data = get_repo_commits(username, repo_name)
            except Exception as e:
                logger.error(f"Error fetching commits for {repo_name}: {str(e)}")
                commits_data = {'error': str(e)}
                
            if isinstance(commits_data, dict) and 'error' in commits_data:
                # Log error but continue with next repo
                logger.warning(f"Error fetching commits for {repo_name}: {commits_data['error']}")
                repo_data['commits'] = []
            else:
                repo_data['commits'] = commits_data
                
                # Add to total commit count
                if commits_data and isinstance(commits_data, list):
                    aggregated_data['total_commits'] += len(commits_data)
                    all_commits.extend(commits_data)
                
                # Get contributor count for this repo
                try:
                    contributors_url = repo_data.get('contributors_url', '')
                    if contributors_url:
                        api = GitHubAPI()
                        contributors_response = api.make_request(contributors_url)
                        if contributors_response.status_code == 200:
                            contributors = contributors_response.json()
                            repo_data['num_contributors'] = len(contributors)
                        else:
                            repo_data['num_contributors'] = 1  # Default if can't fetch
                    else:
                        repo_data['num_contributors'] = 1  # Default
                except Exception as e:
                    logger.error(f"Error fetching contributors for {repo_name}: {str(e)}")
                    repo_data['num_contributors'] = 1  # Default
                    
                # Calculate code quality and survival for this repo
                if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
                    repo_data['code_quality'] = calculate_code_quality(commits_data)
                    repo_data['code_survival'] = calculate_code_survival(commits_data)
                    # Calculate test coverage
                    repo_data['test_coverage'] = calculate_test_coverage(commits_data)
                    
                # Add repo to aggregated data
                aggregated_data['repos'].append(repo_data)
        
        # Calculate overall metrics that matter for our 5 key metrics
        aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)
        
        # Prepare data for impact score calculation
        # 1. Transform pulls_data to pull_requests format
        for pr in pulls_data:
            if isinstance(pr, dict):
                # Extract the merged status
                merged = pr.get('merged', False) or pr.get('state') == 'closed'
                
                # Create a simplified PR object with required fields
                simplified_pr = {
                    'merged': merged,
                    'title': pr.get('title', ''),
                    'number': pr.get('number', 0),
                    'created_at': pr.get('created_at', ''),
                    'closed_at': pr.get('closed_at', '')
                }
                
                # Add to pull_requests list
                aggregated_data['pull_requests'].append(simplified_pr)
        
        # 2. Transform reviews_data to reviews format
        for review in reviews_data:
            if isinstance(review, dict):
                # Create a simplified review object with required fields
                simplified_review = {
                    'state': review.get('state', 'COMMENTED'),
                    'comment_count': review.get('comment_count', 0) or len(review.get('comments', [])),
                    'submitted_at': review.get('submitted_at', '')
                }
                
                # Add to reviews list
                aggregated_data['reviews'].append(simplified_review)
        
        # 3. Transform repos_data to repositories format
        for repo in aggregated_data['repos']:
            if isinstance(repo, dict) and 'name' in repo:
                # Create a simplified repo object with required fields
                repo_name = repo.get('name', '')
                simplified_repo = {
                    'stars': repo.get('stargazers_count', 0) or repo.get('stars', 0),
                    'forks': repo.get('forks_count', 0) or repo.get('forks', 0),
                    'is_fork': repo.get('fork', False)
                }
                
                # Add to repositories dict
                aggregated_data['repositories'][repo_name] = simplified_repo
        
        # 4. Update metrics
        aggregated_data['metrics']['consistency'] = calculate_consistency(pulls_data, reviews_data)
        
        # Calculate average PR size if we have PRs
        if aggregated_data['pull_requests']:
            total_files = 0
            pr_count = 0
            
            for pr in pulls_data:
                if isinstance(pr, dict) and 'files' in pr and isinstance(pr['files'], list):
                    total_files += len(pr['files'])
                    pr_count += 1
            
            if pr_count > 0:
                aggregated_data['metrics']['avg_pr_size'] = {'files': total_files / pr_count}
        
        # Calculate review comment rate
        if aggregated_data['reviews']:
            total_comments = sum(review.get('comment_count', 0) for review in aggregated_data['reviews'])
            aggregated_data['metrics']['review_comment_rate'] = total_comments / len(aggregated_data['reviews'])
        
        # Now calculate the impact score using the properly formatted data
        try:
            aggregated_data['impact_score'] = calculate_impact_score(aggregated_data)
        except ValueError as e:
            # If there's an error calculating the impact score, log it but don't fail
            logger.error(f"Error calculating impact score: {str(e)}")
            aggregated_data['impact_score'] = 0
        
        return aggregated_data
    except Exception as e:
        logger.error(f"Error in aggregate_user_data: {str(e)}")
        return {'error': f"Error aggregating user data: {str(e)}"}

def calculate_test_coverage(commits: list) -> float:
    """Estimate test coverage through commit patterns and file analysis"""
    if not commits:
        return 0
        
    # Keywords that indicate test-related activity
    test_keywords = [
        'test', 'spec', 'coverage', 'jest', 'pytest', 'unittest', 
        'mocha', 'jasmine', 'cypress', 'selenium', 'qunit', 'rspec'
    ]
    
    # Count test-related commits
    test_commits = 0
    test_files = set()
    code_files = set()
    
    for commit in commits:
        # Check commit message
        message = commit.get('commit', {}).get('message', '').lower()
        if any(kw in message for kw in test_keywords):
            test_commits += 1
        
        # Analyze files in the commit
        for file_info in commit.get('files', []):
            filename = file_info.get('filename', '').lower()
            
            # Skip if no filename
            if not filename:
                continue
                
            # Identify test files
            is_test_file = (
                'test' in filename or 
                'spec' in filename or 
                filename.endswith(('.test.js', '.spec.js', '_test.py', 'test_.py', '_spec.py', 'spec_.py'))
            )
            
            if is_test_file:
                test_files.add(filename)
            elif any(filename.endswith(ext) for ext in ['.py', '.js', '.ts', '.java', '.c', '.cpp', '.go', '.rs']):
                code_files.add(filename)
    
    # Calculate metrics
    test_commit_ratio = test_commits / len(commits) if commits else 0
    test_file_ratio = len(test_files) / max(len(code_files), 1) if code_files else 0
    
    # Combine metrics (weighted average)
    return (0.4 * test_commit_ratio + 0.6 * test_file_ratio) * 100  # Convert to percentage

# --- Security Metrics ---
def get_security_advisories(username: str) -> list:
    """Fetch security-related contributions"""
    logger.warning("get_security_advisories is deprecated - use GraphQL data instead")
    url_template = (
        'https://api.github.com/search/issues?'
        'q=author:{username}+label:security+created:>={date}&per_page=100'
    )
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "security_advisories", date=since_date)

def calculate_security_impact(commits: list, advisories: list) -> float:
    """Calculate security consciousness based on security-related commits and advisories"""
    if not commits:
        return 0.0
    
    # Extract security-related patterns from commit messages and file paths
    security_keywords = [
        'security', 'vulnerability', 'exploit', 'cve', 'patch',
        'auth', 'permission', 'access control', 'encrypt', 'decrypt',
        'sanitize', 'validate', 'xss', 'csrf', 'injection', 'malicious'
    ]
    
    # Count security-related commits
    security_commits = 0
    for commit in commits:
        msg = commit.get('commit', {}).get('message', '').lower()
        
        # Check if any security keyword is in the commit message
        if any(keyword in msg for keyword in security_keywords):
            security_commits += 1
            continue
            
        # Check modified files for security implications
        for file in commit.get('files', []):
            filename = file.get('filename', '').lower()
            
            # Check if the file path contains security-related terms
            if any(keyword in filename for keyword in security_keywords):
                security_commits += 1
                break
        
    # Calculate base score from commits
    security_commit_ratio = security_commits / len(commits)
    
    # Boost score if user has security advisories
    advisory_boost = min(len(advisories) * 0.05, 0.25)  # Cap the boost at 0.25
    
    # Combine for final score (0-1 range)
    return normalize_metric(security_commit_ratio + advisory_boost, 1.0)

# --- Release Impact Metrics ---
def get_release_impact(repo_owner: str, repo_name: str) -> dict:
    """
    DEPRECATED: Use GraphQL API instead. This function will be removed in a future version.
    
    Analyzes the impact of releases for a repository.
    Returns information about releases and their activity metrics.
    """
    logger.warning(f"get_release_impact() is deprecated. Use GraphQL API instead.")
    
    github_api = GitHubAPI()
    releases_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases?per_page=100"
    
    try:
        response = github_api.make_request(releases_url)
        
        if response.status_code != 200:
            return {
                "release_count": 0,
                "has_releases": False,
                "release_frequency": 0,
                "avg_comments": 0,
                "avg_reactions": 0
            }
        
        releases = response.json()
        
        if not releases:
            return {
                "release_count": 0,
                "has_releases": False,
                "release_frequency": 0,
                "avg_comments": 0,
                "avg_reactions": 0
            }
        
        # Calculate total releases
        total_releases = len(releases)
        
        # Calculate release frequency (releases per year)
        if total_releases >= 2:
            first_release = datetime.strptime(releases[-1]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            latest_release = datetime.strptime(releases[0]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            time_span_years = (latest_release - first_release).days / 365.25
            release_frequency = total_releases / max(time_span_years, 0.1)  # Avoid division by zero
        else:
            release_frequency = 0
        
        # Calculate latest release age in days
        latest_release_date = datetime.strptime(releases[0]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        latest_release_age = (datetime.now() - latest_release_date).days
        
        # Calculate total downloads if available
        total_downloads = 0
        for release in releases:
            for asset in release.get('assets', []):
                total_downloads += asset.get('download_count', 0)
        
        return {
            "release_count": total_releases,
            "release_frequency": release_frequency,
            "latest_release_age": latest_release_age,
            "total_downloads": total_downloads,
            "avg_comments": 0,
            "avg_reactions": 0
        }
        
    except Exception as e:
        logger.error(f"Error fetching release data: {str(e)}")
        return {
            "release_count": 0,
            "has_releases": False,
            "release_frequency": 0,
            "avg_comments": 0,
            "avg_reactions": 0
        }

# --- Community Engagement Metrics ---
def get_discussions(username: str) -> list:
    """Fetch GitHub discussions created by the user
    
    DEPRECATED: Use GraphQL data from get_user_contributions_graphql instead.
    This function is kept for backward compatibility and as a fallback.
    The GraphQL query already fetches discussion data through repositoryDiscussions.
    """
    logger.warning("get_discussions is deprecated - use GraphQL data instead")
    url_template = 'https://api.github.com/search/discussions?q=author:{username}+created:>={date}&per_page=100'
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "discussions", date=since_date)

def analyze_discussion_quality(discussions: list) -> dict:
    """Analyze discussion engagement quality"""
    if not discussions:
        return {
            'total': 0,
            'engagement_score': 0
        }
    
    # Words indicating positive engagement
    positive_words = {
        'thanks', 'thank', 'helpful', 'great', 'good', 'excellent', 
        'awesome', 'appreciate', 'useful', 'solved', 'solution', 
        'works', 'working', 'fixed', 'resolved'
    }
    
    # Words indicating negative engagement
    negative_words = {
        'issue', 'problem', 'bug', 'error', 'fail', 'failed', 
        'broken', 'doesn\'t work', 'not working', 'incorrect'
    }
    
    # Initialize stats
    stats = {
        'total': len(discussions),
        'positive_count': 0,
        'negative_count': 0,
        'solutions_count': 0,
        'accepted_answers': 0,
        'engagement_score': 0
    }
    
    # Analyze each discussion
    for discussion in discussions:
        body = discussion.get('body', '').lower() if discussion.get('body') else ''
        title = discussion.get('title', '').lower() if discussion.get('title') else ''
        combined_text = f"{title} {body}"
        
        # Count positive and negative words
        positive_count = sum(1 for word in positive_words if word in combined_text)
        negative_count = sum(1 for word in negative_words if word in combined_text)
        
        stats['positive_count'] += positive_count
        stats['negative_count'] += negative_count
        
        # Check for solutions
        if 'solution' in combined_text or 'answer' in combined_text or 'solved' in combined_text:
            stats['solutions_count'] += 1
        
        # Check for accepted answers
        if discussion.get('state') == 'closed' or discussion.get('answer_chosen_at'):
            stats['accepted_answers'] += 1
    
    # Calculate engagement score
    positive_ratio = stats['positive_count'] / stats['total'] if stats['total'] > 0 else 0
    solution_ratio = stats['solutions_count'] / stats['total'] if stats['total'] > 0 else 0
    accepted_ratio = stats['accepted_answers'] / stats['total'] if stats['total'] > 0 else 0
    
    # Weighted engagement score (0-100)
    stats['engagement_score'] = (
        0.4 * positive_ratio + 
        0.3 * solution_ratio + 
        0.3 * accepted_ratio
    ) * 100
    
    return stats

async def get_repo_commits_async(session, username, repo_name, headers):
    """Fetch commits for a specific repository asynchronously."""
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={since_date}&per_page=100'
    
    all_commits = []
    retries = 3
    retry_delay = 2  # Start with 2 seconds delay
    
    try:
        while True:
            try:
                async with session.get(url, headers=headers, timeout=30) as response:
                    # Handle rate limiting
                    if response.status == 403 and 'X-RateLimit-Remaining' in response.headers:
                        remaining = int(response.headers.get('X-RateLimit-Remaining', '0'))
                        if remaining == 0:
                            reset_time = int(response.headers.get('X-RateLimit-Reset', '0'))
                            wait_time = max(reset_time - time.time(), 10)
                            logger.warning(f"Rate limit exceeded in async request. Waiting for {wait_time} seconds")
                            await asyncio.sleep(wait_time)
                            continue  # Retry the request
                    
                    if response.status == 200:
                        commits_data = await response.json()
                        all_commits.extend(commits_data)
                        
                        # Check for pagination
                        link_header = response.headers.get('Link', '')
                        if 'rel="next"' in link_header:
                            # Extract next URL from Link header
                            next_url = None
                            for link in link_header.split(','):
                                if 'rel="next"' in link:
                                    next_url = link.split(';')[0].strip('<>')
                                    break
                            if next_url:
                                url = next_url
                            else:
                                break
                        else:
                            break
                    elif response.status == 409:
                        logger.debug(f"Empty repository detected for {repo_name} (409 Conflict)")
                        return {'repo_name': repo_name, 'commits': []}
                    elif response.status == 404:
                        logger.debug(f"Repository not found: {repo_name}")
                        return {'repo_name': repo_name, 'commits': []}
                    else:
                        error_text = await response.text()
                        logger.error(f"Error fetching commits for {repo_name}: Status {response.status} - {error_text}")
                        
                        if retries > 0 and 500 <= response.status < 600:  # Only retry for server errors
                            retries -= 1
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        
                        return {'repo_name': repo_name, 'error': f'Commit fetch failed: {response.status}'}
            except asyncio.TimeoutError:
                if retries > 0:
                    retries -= 1
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    logger.warning(f"Timeout fetching commits for {repo_name}. Retrying... ({retries} retries left)")
                    continue
                return {'repo_name': repo_name, 'error': 'Request timed out'}
        
        return {'repo_name': repo_name, 'commits': all_commits}
    except Exception as e:
        logger.error(f"Error in get_repo_commits_async for {repo_name}: {str(e)}")
        return {'repo_name': repo_name, 'error': str(e)}

class GitHubGraphQL:
    """GraphQL client for GitHub API - much more efficient than REST for bulk data"""
    
    def __init__(self):
        # Get tokens from environment variable (comma-separated list)
        tokens_str = os.environ.get("GITHUB_TOKENS", os.environ.get("GITHUB_TOKEN", ""))
        self.tokens = [t.strip() for t in tokens_str.split(',') if t.strip()]
        
        # Fallback to single token if no tokens list is provided
        if not self.tokens:
            logger.warning("No GitHub tokens found in environment variables")
            self.tokens = [""]  # Empty token as fallback
        
        # Token rotation and rate limit handling    
        self.current_token_index = 0
        self.last_call = 0
        self.token_rate_limits = {token: {'remaining': 5000, 'reset_time': 0} for token in self.tokens}
        
        # GraphQL endpoint
        self.endpoint = 'https://api.github.com/graphql'
    
    def get_token(self):
        """Get the next available token using round-robin rotation"""
        # If we only have one token, just return it
        if len(self.tokens) == 1:
            return self.tokens[0]
            
        # Try to find a token with remaining rate limit
        start_index = self.current_token_index
        while True:
            token = self.tokens[self.current_token_index]
            
            # Check if this token has remaining rate limit
            if self.token_rate_limits[token]['remaining'] > 10:
                return token
                
            # Check if reset time has passed
            if time.time() > self.token_rate_limits[token]['reset_time']:
                # Reset the remaining count since the reset time has passed
                self.token_rate_limits[token]['remaining'] = 5000
                return token
                
            # Move to the next token
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            
            # If we've checked all tokens and come back to the start, use the one with the earliest reset time
            if self.current_token_index == start_index:
                # Find token with earliest reset time
                token = min(self.tokens, key=lambda t: self.token_rate_limits[t]['reset_time'])
                
                # If all tokens are rate limited, sleep until the earliest reset time
                sleep_duration = max(self.token_rate_limits[token]['reset_time'] - time.time(), 10)
                if sleep_duration > 0:
                    logger.warning(f"All tokens rate limited. Sleeping for {sleep_duration} seconds")
                    time.sleep(sleep_duration)
                    
                return token
    
    def execute_query(self, query, variables=None):
        """Execute a GraphQL query with proper rate limit handling"""
        token = self.get_token()
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        
        # Respect GitHub's rate limits with a small delay between requests
        now = time.time()
        if now - self.last_call < 1.1:
            time.sleep(1.1 - (now - self.last_call))
        
        try:
            response = requests.post(
                self.endpoint,
                json={'query': query, 'variables': variables or {}},
                headers=headers,
                timeout=30
            )
            self.last_call = time.time()
            
            # Update rate limit information
            self.handle_rate_limits(response, token)
            
            # Handle rate limiting response with status code 403
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and int(response.headers.get('X-RateLimit-Remaining', 0)) == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(reset_time - time.time(), 10)
                
                if len(self.tokens) > 1:
                    # If multiple tokens available, mark this one as rate-limited
                    self.token_rate_limits[token]['remaining'] = 0
                    self.token_rate_limits[token]['reset_time'] = reset_time
                    # Recursive call to retry with a different token
                    return self.execute_query(query, variables)
                else:
                    # Only one token available, need to wait
                    logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds")
                    time.sleep(wait_time)
                    return self.execute_query(query, variables)
            
            # Check for other error status codes
            if response.status_code != 200:
                logger.error(f"GraphQL request failed with status code {response.status_code}: {response.text}")
                return {'errors': [{'message': f"GraphQL request failed with status code {response.status_code}"}]}
            
            # Parse the JSON response
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse GraphQL response as JSON: {str(e)}")
                return {'errors': [{'message': f"Failed to parse response as JSON: {str(e)}"}]}
                
        except requests.RequestException as e:
            logger.error(f"GraphQL request error: {str(e)}")
            return {'errors': [{'message': f"GraphQL request error: {str(e)}"}]}
        except Exception as e:
            logger.error(f"Unexpected error in GraphQL request: {str(e)}")
            return {'errors': [{'message': f"Unexpected error: {str(e)}"}]}
    
    def handle_rate_limits(self, response, token):
        """Handle GraphQL API rate limits and update token status"""
        # Skip if no token or not a GitHub API response
        if not token or 'X-RateLimit-Remaining' not in response.headers:
            return
            
        # Update rate limit information for this token - use safer int conversion
        try:
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            self.token_rate_limits[token] = {
                'remaining': remaining,
                'reset_time': reset_time
            }
            
            # Log warning if rate limit is getting low
            if remaining < 10:
                sleep_duration = max(reset_time - time.time(), 10)
                logger.warning(f"GraphQL rate limit almost reached. Remaining: {remaining}. Reset in {sleep_duration} seconds")
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing GraphQL rate limit headers: {e}")
            # Keep existing values if parsing fails
            pass

@cache_response()
def get_user_contributions_graphql(username, time_window_days=365):
    """Fetch user contributions using GitHub GraphQL API - much more efficient than REST
    
    This single request gets most of the data needed for analysis:
    - Commit contributions by repository
    - Pull request contributions
    - Issue contributions
    - Code review contributions
    - Discussion contributions
    
    Returns a comprehensive structure with all the data.
    """
    graphql = GitHubGraphQL()
    
    # Calculate the date for the time window
    since_date = (datetime.now() - timedelta(days=time_window_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Define the GraphQL query - this replaces many separate REST API calls
    query = """
    query ($login: String!, $since: DateTime!) {
      user(login: $login) {
        name
        email
        url
        avatarUrl
        createdAt
        location
        company
        bio
        followers {
          totalCount
        }
        following {
          totalCount
        }
        contributionsCollection(from: $since) {
          totalCommitContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalIssueContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
          commitContributionsByRepository(maxRepositories: 100) {
            repository {
              name
              owner {
                login
              }
              stargazerCount
              forkCount
              isPrivate
              isFork
              primaryLanguage {
                name
              }
              languages(first: 10) {
                nodes {
                  name
                }
              }
            }
            contributions(first: 100) {
              totalCount
              nodes {
                commitCount
                repository {
                  name
                }
                occurredAt
              }
            }
          }
          pullRequestContributions(first: 100) {
            totalCount
            nodes {
              pullRequest {
                title
                merged
                mergedAt
                createdAt
                repository {
                  name
                }
                changedFiles
                additions
                deletions
              }
            }
          }
          pullRequestReviewContributions(first: 100) {
            totalCount
            nodes {
              pullRequestReview {
                repository {
                  name
                }
                createdAt
                state
                comments {
                  totalCount
                }
              }
            }
          }
          issueContributions(first: 100) {
            totalCount
            nodes {
              issue {
                title
                createdAt
                repository {
                  name
                }
                state
                comments {
                  totalCount
                }
              }
            }
          }
        }
        repositories(first: 100, orderBy: {field: STARGAZERS, direction: DESC}) {
          totalCount
          nodes {
            name
            stargazerCount
            forkCount
            isFork
            isPrivate
            primaryLanguage {
              name
            }
            languages(first: 10) {
              nodes {
                name
              }
            }
            owner {
              login
            }
            # Added release data
            releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              nodes {
                name
                createdAt
                tagName
                isPrerelease
                isDraft
              }
            }
            # Added security data
            vulnerabilityAlerts(first: 10) {
              totalCount
              nodes {
                createdAt
                dismissedAt
                vulnerableManifestPath
                securityVulnerability {
                  severity
                  package {
                    name
                  }
                }
              }
            }
          }
        }
        # Added discussions data
        repositoryDiscussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
          totalCount
          nodes {
            title
            createdAt
            repository {
              name
            }
            comments {
              totalCount
            }
            upvoteCount
            category {
              name
            }
          }
        }
      }
    }
    """
    
    # Execute the query with variables
    variables = {
        "login": username,
        "since": since_date
    }
    
    try:
        # Execute the GraphQL query
        result = graphql.execute_query(query, variables)
        
        # Check if result is None
        if result is None:
            logger.error(f"GraphQL query returned None for {username}")
            return {'error': 'GraphQL query failed'}
        
        # Check for errors
        if 'errors' in result:
            logger.error(f"GraphQL errors for {username}: {result['errors']}")
            return {'error': result['errors']}
        
        # Return the data
        return result['data']
    except Exception as e:
        logger.error(f"Error fetching GraphQL data for {username}: {str(e)}")
        return {'error': f"Error fetching GraphQL data: {str(e)}"}

@cache_response()
def aggregate_user_data_graphql(username, graphql_data=None):
    """Aggregate GitHub user data using the more efficient GraphQL API
    
    This function replaces multiple separate REST API calls with a single
    GraphQL query, which is much more efficient. The time window is also
    reduced from 2 years to 1 year for better performance.
    
    Args:
        username (str): GitHub username
        graphql_data (dict): Optional pre-fetched GraphQL data from fetch_all_data
        
    Returns:
        dict: Aggregated user data with metrics
    """
    try:
        # Get GraphQL data - either from parameter or by fetching it
        if graphql_data is None:
            # Get all data with a single GraphQL query
            raw_data = get_user_contributions_graphql(username)
        else:
            # Use the provided data
            raw_data = graphql_data.get('data') if isinstance(graphql_data, dict) and 'data' in graphql_data else graphql_data
        
        # Check if there was an error or if raw_data is None
        if raw_data is None:
            logger.error(f"Raw GraphQL data is None for user {username}")
            return {'error': 'Failed to fetch GraphQL data'}
            
        if isinstance(raw_data, dict) and 'error' in raw_data:
            return raw_data
        
        # Initialize results dictionary
        result = {
            'username': username,
            'raw_graphql_data': raw_data,  # Store the raw data for potential reuse
            'metrics': {},
            'repositories': {},
            'activity': {
                'commits': 0,
                'pulls': 0,
                'issues': 0,
                'reviews': 0,
                'discussions': 0  # Added discussions count
            }
        }
        
        # Extract user information
        user_data = raw_data.get('user', {}) if isinstance(raw_data, dict) else {}
        if not user_data:
            logger.error(f"User data not found in GraphQL response for {username}")
            return {'error': 'User not found'}
        
        # Basic user info
        result['name'] = user_data.get('name')
        result['email'] = user_data.get('email')
        result['avatar_url'] = user_data.get('avatarUrl')
        result['url'] = user_data.get('url')
        result['company'] = user_data.get('company')
        result['location'] = user_data.get('location')
        result['bio'] = user_data.get('bio')
        result['followers'] = user_data.get('followers', {}).get('totalCount', 0) if user_data.get('followers') is not None else 0
        result['following'] = user_data.get('following', {}).get('totalCount', 0) if user_data.get('following') is not None else 0
        
        # Get contributions collection data
        contrib_data = user_data.get('contributionsCollection', {}) if user_data is not None else {}
        
        # Count metrics
        result['activity']['commits'] = contrib_data.get('totalCommitContributions', 0)
        result['activity']['pulls'] = contrib_data.get('totalPullRequestContributions', 0)
        result['activity']['reviews'] = contrib_data.get('totalPullRequestReviewContributions', 0)
        result['activity']['issues'] = contrib_data.get('totalIssueContributions', 0)
        
        # Get calendar data for consistency calculation
        calendar = contrib_data.get('contributionCalendar', {}) if contrib_data is not None else {}
        total_contributions = calendar.get('totalContributions', 0)
        result['metrics']['total_contributions'] = total_contributions
        
        # Active days calculation
        active_days = 0
        weeks = calendar.get('weeks', [])
        for week in weeks:
            for day in week.get('contributionDays', []):
                if day.get('contributionCount', 0) > 0:
                    active_days += 1
        
        # Calculate consistency (active days / total days in time window)
        days_in_period = TIME_WINDOW_DAYS
        result['metrics']['consistency'] = active_days / days_in_period if days_in_period > 0 else 0
        
        # Process repositories
        repos = user_data.get('repositories', {}) if user_data is not None else {}
        repo_nodes = repos.get('nodes', []) if repos is not None else []
        
        # Calculate repository metrics
        total_stars = 0
        total_forks = 0
        original_repos = 0
        languages = set()
        
        for repo in repo_nodes:
            if repo is None:
                continue
                
            repo_name = repo.get('name', '')
            if not repo_name:
                continue
                
            # Skip private repos
            if repo.get('isPrivate', False):
                continue
                
            # Get basic repo data
            stars = repo.get('stargazerCount', 0)
            forks = repo.get('forkCount', 0)
            is_fork = repo.get('isFork', False)
            
            # Add to totals
            total_stars += stars
            total_forks += forks
            if not is_fork:
                original_repos += 1
                
            # Track languages
            primary_lang = repo.get('primaryLanguage', {})
            if primary_lang and primary_lang.get('name'):
                languages.add(primary_lang.get('name'))
                
            # Add all languages
            repo_langs = repo.get('languages', {})
            if repo_langs:
                lang_nodes = repo_langs.get('nodes', [])
                for lang in lang_nodes:
                    if lang and lang.get('name'):
                        languages.add(lang.get('name'))
                        
            # Store repo data
            result['repositories'][repo_name] = {
                'stars': stars,
                'forks': forks,
                'is_fork': is_fork,
                'owner': repo.get('owner', {}).get('login') if repo.get('owner') is not None else '',
                'primary_language': primary_lang.get('name') if primary_lang is not None else None
            }
            
            # Process release data
            releases = repo.get('releases', {})
            if releases:
                release_count = releases.get('totalCount', 0)
                release_nodes = releases.get('nodes', [])
                
                # Store release data
                result['repositories'][repo_name]['releases'] = {
                    'count': release_count,
                    'releases': release_nodes
                }
                
            # Process security data
            security = repo.get('vulnerabilityAlerts', {})
            if security:
                alert_count = security.get('totalCount', 0)
                alert_nodes = security.get('nodes', [])
                
                # Store security data
                result['repositories'][repo_name]['security'] = {
                    'alert_count': alert_count,
                    'alerts': alert_nodes
                }
        
        # Extract pull request data
        pr_contribs = contrib_data.get('pullRequestContributions', {}) if contrib_data is not None else {}
        pr_nodes = pr_contribs.get('nodes', []) if pr_contribs is not None else []
        
        # PR metrics
        total_prs = 0
        merged_prs = 0
        total_pr_files = 0
        total_pr_additions = 0
        total_pr_deletions = 0
        
        # Store PRs for analysis
        result['pull_requests'] = []
        
        for pr_contrib in pr_nodes:
            if pr_contrib is None:
                continue
                
            pr = pr_contrib.get('pullRequest', {})
            if pr is None:
                continue
                
            total_prs += 1
            
            # Check if merged
            if pr.get('merged', False):
                merged_prs += 1
                
            # Get PR size metrics
            files_changed = pr.get('changedFiles', 0)
            additions = pr.get('additions', 0)
            deletions = pr.get('deletions', 0)
            
            total_pr_files += files_changed
            total_pr_additions += additions
            total_pr_deletions += deletions
            
            # Store PR data
            result['pull_requests'].append({
                'title': pr.get('title', ''),
                'merged': pr.get('merged', False),
                'created_at': pr.get('createdAt'),
                'merged_at': pr.get('mergedAt'),
                'repository': pr.get('repository', {}).get('name', '') if pr.get('repository') is not None else '',
                'files_changed': files_changed,
                'additions': additions,
                'deletions': deletions
            })
        
        # Calculate PR metrics
        result['metrics']['total_prs'] = total_prs
        result['metrics']['merged_prs'] = merged_prs
        result['metrics']['pr_acceptance_rate'] = merged_prs / total_prs if total_prs > 0 else 0
        
        # Calculate average PR size
        if total_prs > 0:
            result['metrics']['avg_pr_size'] = {
                'files': total_pr_files / total_prs,
                'additions': total_pr_additions / total_prs,
                'deletions': total_pr_deletions / total_prs
            }
        else:
            result['metrics']['avg_pr_size'] = {
                'files': 0,
                'additions': 0,
                'deletions': 0
            }
        
        # Extract review data
        reviews = []
        review_contribs = contrib_data.get('pullRequestReviewContributions', {}) if contrib_data is not None else {}
        review_nodes = review_contribs.get('nodes', []) if review_contribs is not None else []
        
        for review_contrib in review_nodes:
            if review_contrib is None:
                continue
                
            review = review_contrib.get('pullRequestReview', {})
            if review is None:
                continue
                
            comments = review.get('comments', {})
            comment_count = comments.get('totalCount', 0) if comments is not None else 0
            
            review_data = {
                'state': review.get('state', ''),
                'created_at': review.get('createdAt'),
                'repository': review.get('repository', {}).get('name', '') if review.get('repository') is not None else '',
                'comment_count': comment_count
            }
            reviews.append(review_data)
        
        result['reviews'] = reviews
        
        # Calculate review metrics
        approved_reviews = sum(1 for r in reviews if r.get('state') == 'APPROVED')
        total_review_comments = sum(r.get('comment_count', 0) for r in reviews)
        
        result['metrics']['review_approval_rate'] = approved_reviews / len(reviews) if reviews else 0
        result['metrics']['review_comment_rate'] = total_review_comments / len(reviews) if reviews else 0
        
        # Extract issue data
        issues = []
        issue_contribs = contrib_data.get('issueContributions', {}) if contrib_data is not None else {}
        issue_nodes = issue_contribs.get('nodes', []) if issue_contribs is not None else []
        
        for issue_contrib in issue_nodes:
            if issue_contrib is None:
                continue
                
            issue = issue_contrib.get('issue', {})
            if issue is None:
                continue
                
            comments = issue.get('comments', {})
            comment_count = comments.get('totalCount', 0) if comments is not None else 0
            
            issue_data = {
                'title': issue.get('title', ''),
                'created_at': issue.get('createdAt'),
                'state': issue.get('state', ''),
                'repository': issue.get('repository', {}).get('name', '') if issue.get('repository') is not None else '',
                'comment_count': comment_count
            }
            issues.append(issue_data)
        
        result['issues'] = issues
        
        # Calculate issue metrics
        total_issue_comments = sum(i.get('comment_count', 0) for i in issues)
        result['metrics']['avg_issue_comments'] = total_issue_comments / len(issues) if issues else 0
        
        # Extract discussion data
        discussions = []
        discussion_data = user_data.get('repositoryDiscussions', {}) if user_data is not None else {}
        discussion_nodes = discussion_data.get('nodes', []) if discussion_data is not None else []
        
        for discussion in discussion_nodes:
            if discussion is None:
                continue
                
            comments = discussion.get('comments', {})
            comment_count = comments.get('totalCount', 0) if comments is not None else 0
            
            discussion_info = {
                'title': discussion.get('title', ''),
                'created_at': discussion.get('createdAt'),
                'repository': discussion.get('repository', {}).get('name', '') if discussion.get('repository') is not None else '',
                'comment_count': comment_count,
                'upvote_count': discussion.get('upvoteCount', 0),
                'category': discussion.get('category', {}).get('name', '') if discussion.get('category') is not None else ''
            }
            discussions.append(discussion_info)
        
        result['discussions'] = discussions
        
        # Update activity count for discussions
        result['activity']['discussions'] = len(discussions)
        
        # Calculate discussion engagement metrics
        if discussions:
            avg_comments = sum(d.get('comment_count', 0) for d in discussions) / len(discussions)
            avg_upvotes = sum(d.get('upvote_count', 0) for d in discussions) / len(discussions)
            result['metrics']['discussion_engagement'] = {
                'avg_comments': avg_comments,
                'avg_upvotes': avg_upvotes
            }
        else:
            result['metrics']['discussion_engagement'] = {
                'avg_comments': 0,
                'avg_upvotes': 0
            }
        
        # Calculate repository metrics
        repo_count = len(result['repositories'])
        if repo_count > 0:
            # Calculate average stars and forks
            total_stars = sum(repo.get('stars', 0) for repo in result['repositories'].values())
            total_forks = sum(repo.get('forks', 0) for repo in result['repositories'].values())
            
            result['metrics']['avg_repo_stars'] = total_stars / repo_count
            result['metrics']['avg_repo_forks'] = total_forks / repo_count
            
            # Calculate original vs forked repo ratio
            original_repos = sum(1 for repo in result['repositories'].values() if not repo.get('is_fork', False))
            result['metrics']['original_repo_rate'] = original_repos / repo_count
            
            # Count unique languages
            languages = set()
            for repo in result['repositories'].values():
                if repo.get('primary_language'):
                    languages.add(repo.get('primary_language'))
            
            result['metrics']['language_count'] = len(languages)
            result['metrics']['languages'] = list(languages)
        else:
            result['metrics']['avg_repo_stars'] = 0
            result['metrics']['avg_repo_forks'] = 0
            result['metrics']['original_repo_rate'] = 0
            result['metrics']['language_count'] = 0
            result['metrics']['languages'] = []
        
        # Calculate release metrics
        release_counts = []
        release_dates = []
        
        for repo_data in result['repositories'].values():
            releases = repo_data.get('releases', {})
            if releases:
                release_count = releases.get('count', 0)
                release_counts.append(release_count)
                
                # Extract release dates for calculating frequency
                release_list = releases.get('releases', [])
                dates = []
                for release in release_list:
                    if release and release.get('createdAt'):
                        try:
                            date = datetime.fromisoformat(release.get('createdAt').replace('Z', '+00:00'))
                            dates.append(date)
                        except (ValueError, TypeError):
                            continue
                
                if len(dates) >= 2:
                    # Sort dates and calculate differences
                    dates.sort()
                    diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                    if diffs:
                        avg_days = sum(diffs) / len(diffs)
                        release_dates.append(avg_days)
        
        # Store release metrics
        if release_counts:
            result['metrics']['release_count'] = sum(release_counts) / len(release_counts)
        else:
            result['metrics']['release_count'] = 0
            
        if release_dates:
            result['metrics']['avg_days_between_releases'] = sum(release_dates) / len(release_dates)
        else:
            result['metrics']['avg_days_between_releases'] = 90  # Default value
        
        # Calculate security metrics
        security_alerts = 0
        response_times = []
        
        for repo_data in result['repositories'].values():
            security = repo_data.get('security', {})
            if security:
                alerts = security.get('alerts', [])
                security_alerts += len(alerts)
                
                # Calculate response times
                for alert in alerts:
                    if alert is None:
                        continue
                        
                    try:
                        created = datetime.fromisoformat(alert.get('createdAt', '').replace('Z', '+00:00'))
                        dismissed = datetime.fromisoformat(alert.get('dismissedAt', '').replace('Z', '+00:00')) if alert.get('dismissedAt') else None
                        
                        if dismissed:
                            response_time = (dismissed - created).days
                            if response_time >= 0:
                                response_times.append(response_time)
                    except (ValueError, TypeError):
                        continue
        
        # Store security metrics
        if security_alerts > 0:
            result['metrics']['security_response_rate'] = len(response_times) / security_alerts
        else:
            result['metrics']['security_response_rate'] = 1.0  # Default to perfect if no alerts
            
        if response_times:
            result['metrics']['avg_security_response_time_days'] = sum(response_times) / len(response_times)
        else:
            result['metrics']['avg_security_response_time_days'] = 0  # Default to 0 if no response times
        
        # Calculate overall impact score
        result['impact_score'] = calculate_impact_score_graphql(result)
        
        return result
    except Exception as e:
        logger.error(f"Error in aggregate_user_data_graphql: {str(e)}")
        return {'error': f"Error aggregating user data: {str(e)}"}


def calculate_impact_score_graphql(data):
    """Calculate the impact score based on GraphQL data
    
    This optimized version uses parallel processing for large datasets.
    """
    try:
        # Extract key metrics from the data
        metrics = data.get('metrics', {})
        
        # Determine if the dataset is large enough to benefit from parallelization
        repos = data.get('repositories', {})
        pull_requests = data.get('pull_requests', [])
        discussions = data.get('discussions', [])
        reviews = data.get('reviews', [])
        
        is_large_dataset = (
            len(repos) > 10 or 
            len(pull_requests) > 50 or 
            len(discussions) > 20 or 
            len(reviews) > 50
        )
        
        # Use parallel processing for large datasets
        if is_large_dataset:
            try:
                return _calculate_impact_score_parallel(data)
            except Exception as e:
                logger.warning(f"Parallel processing failed, falling back to sequential: {str(e)}")
                # Fall back to sequential processing
        
        # Weight factors for different metrics
        weights = {
            'repo_impact': 0.20,      # Impact of repositories (stars, forks)
            'code_quality': 0.15,     # Code quality metrics
            'consistency': 0.15,      # Consistency of contributions
            'collaboration': 0.20,    # Collaboration metrics (PRs, reviews)
            'community': 0.15,        # Community engagement 
            'releases': 0.10,         # Release management
            'security': 0.05          # Security consciousness
        }
        
        # 1. Repository Impact Score (stars, forks, variety of repos)
        repo_impact = 0
        if 'avg_repo_stars' in metrics:
            repo_impact += normalize_metric(metrics.get('avg_repo_stars', 0), 500) * 0.5
        if 'original_repo_rate' in metrics:
            repo_impact += metrics.get('original_repo_rate', 0) * 0.3
        if 'language_count' in metrics:
            repo_impact += normalize_metric(metrics.get('language_count', 0), 10) * 0.2
            
        # 2. Code Quality Score
        code_quality = 0
        if 'avg_pr_size' in metrics:
            avg_files_changed = metrics.get('avg_pr_size', {}).get('files', 0)
            # Smaller PRs are generally better (up to a point)
            code_quality += (1 - normalize_metric(min(avg_files_changed, 30), 30)) * 0.5
        if 'pr_acceptance_rate' in metrics:
            code_quality += metrics.get('pr_acceptance_rate', 0) * 0.5
            
        # 3. Consistency Score
        consistency = metrics.get('consistency', 0)
        
        # 4. Collaboration Score
        collaboration = 0
        if 'review_comment_rate' in metrics:
            collaboration += metrics.get('review_comment_rate', 0) * 0.5
        if 'review_approval_rate' in metrics:
            collaboration += metrics.get('review_approval_rate', 0) * 0.5
            
        # 5. Community Score
        community = 0
        if 'discussion_engagement' in metrics:
            community += normalize_metric(metrics.get('discussion_engagement', {}).get('avg_comments', 0), 10) * 0.4
            community += normalize_metric(metrics.get('discussion_engagement', {}).get('avg_upvotes', 0), 5) * 0.4
        
        # Add in followers contribution
        followers = data.get('followers', 0)
        community += normalize_metric(followers, 1000) * 0.2
        
        # 6. Release Management
        release_score = 0
        if 'release_count' in metrics:
            release_score += normalize_metric(metrics.get('release_count', 0), 20) * 0.5
        if 'avg_days_between_releases' in metrics:
            # Lower is better, but not too low
            avg_days = metrics.get('avg_days_between_releases', 90)
            ideal_days = 14  # Assuming bi-weekly releases are ideal
            release_frequency_score = 1 - abs(avg_days - ideal_days) / 100
            release_frequency_score = max(0, min(1, release_frequency_score))
            release_score += release_frequency_score * 0.5
        
        # 7. Security Score
        security_score = 0
        if 'security_response_rate' in metrics:
            security_score += metrics.get('security_response_rate', 0) * 0.7
        if 'avg_security_response_time_days' in metrics:
            # Lower is better
            avg_days = metrics.get('avg_security_response_time_days', 30)
            security_score += (1 - normalize_metric(min(avg_days, 30), 30)) * 0.3
            
        # Calculate the overall impact score (weighted average)
        impact_score = (
            weights['repo_impact'] * repo_impact +
            weights['code_quality'] * code_quality +
            weights['consistency'] * consistency +
            weights['collaboration'] * collaboration +
            weights['community'] * community +
            weights['releases'] * release_score +
            weights['security'] * security_score
        )
        
        # Scale to 0-100 range
        return impact_score * 100
    except Exception as e:
        logger.error(f"Error calculating impact score from GraphQL data: {str(e)}")
        return 0

def _calculate_impact_score_parallel(data):
    """Calculate impact score using parallel processing for large datasets"""
    try:
        from concurrent.futures import ThreadPoolExecutor
        import functools
        
        # Extract metrics once (shared across threads)
        metrics = data.get('metrics', {})
        
        # Define individual scoring functions
        def calc_repo_impact(metrics):
            repo_impact = 0
            if 'avg_repo_stars' in metrics:
                repo_impact += normalize_metric(metrics.get('avg_repo_stars', 0), 500) * 0.5
            if 'original_repo_rate' in metrics:
                repo_impact += metrics.get('original_repo_rate', 0) * 0.3
            if 'language_count' in metrics:
                repo_impact += normalize_metric(metrics.get('language_count', 0), 10) * 0.2
            return repo_impact
        
        def calc_code_quality(metrics):
            code_quality = 0
            if 'avg_pr_size' in metrics:
                avg_files_changed = metrics.get('avg_pr_size', {}).get('files', 0)
                code_quality += (1 - normalize_metric(min(avg_files_changed, 30), 30)) * 0.5
            if 'pr_acceptance_rate' in metrics:
                code_quality += metrics.get('pr_acceptance_rate', 0) * 0.5
            return code_quality
        
        def calc_collaboration(metrics):
            collaboration = 0
            if 'review_comment_rate' in metrics:
                collaboration += metrics.get('review_comment_rate', 0) * 0.5
            if 'review_approval_rate' in metrics:
                collaboration += metrics.get('review_approval_rate', 0) * 0.5
            return collaboration
        
        def calc_community(metrics, followers):
            community = 0
            if 'discussion_engagement' in metrics:
                community += normalize_metric(metrics.get('discussion_engagement', {}).get('avg_comments', 0), 10) * 0.4
                community += normalize_metric(metrics.get('discussion_engagement', {}).get('avg_upvotes', 0), 5) * 0.4
            community += normalize_metric(followers, 1000) * 0.2
            return community
        
        def calc_release_score(metrics):
            release_score = 0
            if 'release_count' in metrics:
                release_score += normalize_metric(metrics.get('release_count', 0), 20) * 0.5
            if 'avg_days_between_releases' in metrics:
                avg_days = metrics.get('avg_days_between_releases', 90)
                ideal_days = 14
                release_frequency_score = 1 - abs(avg_days - ideal_days) / 100
                release_frequency_score = max(0, min(1, release_frequency_score))
                release_score += release_frequency_score * 0.5
            return release_score
        
        def calc_security_score(metrics):
            security_score = 0
            if 'security_response_rate' in metrics:
                security_score += metrics.get('security_response_rate', 0) * 0.7
            if 'avg_security_response_time_days' in metrics:
                avg_days = metrics.get('avg_security_response_time_days', 30)
                security_score += (1 - normalize_metric(min(avg_days, 30), 30)) * 0.3
            return security_score
        
        # Define tasks to run in parallel
        tasks = [
            (calc_repo_impact, (metrics,)),
            (calc_code_quality, (metrics,)),
            (lambda m: m.get('consistency', 0), (metrics,)),  # Consistency score is direct
            (calc_collaboration, (metrics,)),
            (calc_community, (metrics, data.get('followers', 0))),
            (calc_release_score, (metrics,)),
            (calc_security_score, (metrics,))
        ]
        
        # Weight factors for different metrics
        weights = {
            'repo_impact': 0.20,      # Impact of repositories (stars, forks)
            'code_quality': 0.15,     # Code quality metrics
            'consistency': 0.15,      # Consistency of contributions
            'collaboration': 0.20,    # Collaboration metrics (PRs, reviews)
            'community': 0.15,        # Community engagement 
            'releases': 0.10,         # Release management
            'security': 0.05          # Security consciousness
        }
        
        # Create weighted tasks
        weighted_tasks = [
            (func, args, weight) 
            for (func, args), weight in zip(
                tasks, 
                [weights['repo_impact'], weights['code_quality'], weights['consistency'],
                 weights['collaboration'], weights['community'], weights['releases'], 
                 weights['security']]
            )
        ]
        
        # Execute tasks in parallel
        with ThreadPoolExecutor(max_workers=min(7, os.cpu_count() or 4)) as executor:
            futures = [
                executor.submit(func, *args) 
                for func, args, _ in weighted_tasks
            ]
            
            # Collect results and apply weights
            result = sum(
                future.result() * weight 
                for future, (_, _, weight) in zip(futures, weighted_tasks)
            )
        
        # Scale to 0-100 range
        return result * 100
    except Exception as e:
        logger.error(f"Error in parallel impact score calculation: {str(e)}")
        raise  # Re-raise to fall back to sequential processing

def calculate_impact_score(aggregated_data: dict) -> float:
    """A wrapper around calculate_impact_score_graphql for backward compatibility.
    
    This function prioritizes metrics based on hiring manager survey data:
    - Merged PRs to active repos (32% weight)
    - Code review depth (28% weight)
    - Maintenance burden (19% weight)
    - Project popularity (15% weight)
    - Documentation (6% weight)
    """
    # Simply call the GraphQL version now to ensure consistent scoring
    result = calculate_impact_score_graphql(aggregated_data)
    if isinstance(result, dict):
        if 'error' in result:
            # If there's an error, raise it to be handled by the caller
            raise ValueError(result['error'])
        elif 'total' in result:
            return result['total']
    return 0  # Default to 0 if there's an error

# Add this function after the other get_user_* functions
@cache_response()
def get_user_info(username):
    """Fetch user information from GitHub API"""
    api = GitHubAPI()
    url = f'https://api.github.com/users/{username}'
    try:
        response = api.make_request(url)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        logger.error(f"Error fetching user info: {str(e)}")
        return {'error': f"Error fetching user info: {str(e)}"}
    except ValueError as e:
        logger.error(f"JSON parsing error for user info: {str(e)}")
        return {'error': f"JSON parsing error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error fetching user info: {str(e)}")
        return {'error': f"Unexpected error: {str(e)}"}

def calculate_overall_project_impact(aggregated_data: dict) -> float:
    """Calculate overall project impact based on individual repo impacts"""
    # Calculate overall project impact based on individual repo impacts
    total_impact = 0
    
    # Check if repos is a list before iterating
    repos = aggregated_data.get('repos', [])
    if not isinstance(repos, list):
        logger.error(f"Expected repos to be a list, got {type(repos)}: {repos}")
        return 0
        
    for repo in repos:
        is_original = not repo.get('fork', False)  # check if the repo is forked
        repo['impact_score'] = calculate_project_impact(repo, is_original)  # Calculate individual repo impact
        total_impact += repo['impact_score']
    
    # Normalize to a 0-100 scale
    return min(total_impact * 100, 100)

def calculate_project_impact(repo_data: dict, is_original: bool) -> float:
    """Calculate impact score for a single repository"""
    if not isinstance(repo_data, dict):
        return 0
        
    # Higher weight for original repos vs forks
    if is_original:
        originality_weight = 0.7  # High weight for original repos
    else:
        originality_weight = 0.1  # Low weight for forked repos

    stars_weight = 0.15
    forks_weight = 0.05  # Significantly reduced
    contributors_weight = 0.1

    # Normalize stars/forks
    max_stars = 10000  # Maximum for normalization
    max_forks = 50000  # Maximum for normalization
    max_contributors = 100  # Maximum for normalization

    normalized_stars = min(repo_data.get('stars', 0) / max_stars, 1.0)  # Cap at 1.0
    normalized_forks = min(repo_data.get('forks', 0) / max_forks, 1.0)
    normalized_contributors = min(repo_data.get('num_contributors', 1) / max_contributors, 1.0)

    # Age Factor (newer repos get a boost)
    try:
        created_at = repo_data.get('created_at')
        if created_at:
            repo_created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
            repo_age_years = (datetime.now() - repo_created_at).days / 365.25
            age_factor = 1 / (1 + repo_age_years)  # Example: 1-year-old repo -> factor of 0.5
        else:
            age_factor = 0.5  # Default if created_at is missing
    except (ValueError, TypeError):
        age_factor = 0.5  # Default if there's an error parsing the date

    # Combine factors
    project_impact_score = (
        originality_weight +
        (1-originality_weight) * (
            stars_weight * normalized_stars +
            forks_weight * normalized_forks +
            contributors_weight * normalized_contributors
        )
    ) * age_factor

    return project_impact_score

# Async version for parallel data fetching
async def fetch_all_data(username):
    """Fetch all GitHub data for a user asynchronously using GraphQL.
    
    This function uses a single GraphQL query to fetch all the data needed for the impact score calculation,
    which is much more efficient than multiple REST API calls. The GraphQL query includes:
    
    - Repository data (stars, forks, languages)
    - Pull request data (merged, size, etc.)
    - Code review data (comments, approvals)
    - Issue data
    - Discussion data
    - Release data
    - Security vulnerability data
    
    The final scoring mechanism prioritizes:
    - Merged PRs to active repos (32% weight)
    - Code review depth (28% weight)
    - Maintenance burden (19% weight)
    - Project popularity (15% weight)
    - Documentation (6% weight)
    
    Args:
        username (str): GitHub username
        
    Returns:
        dict: All GitHub data for the user
    """
    try:
        from aiohttp import ClientSession, ClientError
        import asyncio
        
        async def fetch_graphql_data(session, query, variables, headers):
            """Execute a GraphQL query asynchronously"""
            try:
                async with session.post(
                    'https://api.github.com/graphql',
                    json={'query': query, 'variables': variables},
                    headers=headers,
                    timeout=60  # Longer timeout for the large GraphQL query
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return {'error': f'GraphQL Error: {response.status} - {await response.text()}'}
            except ClientError as e:
                logger.error(f"GraphQL client error: {str(e)}")
                return {'error': f'GraphQL client error: {str(e)}'}
            except asyncio.TimeoutError:
                logger.error(f"GraphQL request timed out")
                return {'error': 'GraphQL request timed out'}
        
        # Use an existing token
        token = os.environ.get("GITHUB_TOKEN", "")
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        
        # Calculate the date for the time window
        since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Define the GraphQL query - this single query replaces multiple REST API calls
        query = """
        query ($login: String!, $since: DateTime!) {
          user(login: $login) {
            name
            email
            url
            avatarUrl
            createdAt
            location
            company
            bio
            followers {
              totalCount
            }
            following {
              totalCount
            }
            contributionsCollection(from: $since) {
              totalCommitContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
              totalIssueContributions
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
              commitContributionsByRepository(maxRepositories: 100) {
                repository {
                  name
                  owner {
                    login
                  }
                  stargazerCount
                  forkCount
                  isPrivate
                  isFork
                  primaryLanguage {
                    name
                  }
                  languages(first: 10) {
                    nodes {
                      name
                    }
                  }
                }
                contributions(first: 100) {
                  totalCount
                  nodes {
                    commitCount
                    repository {
                      name
                    }
                    occurredAt
                  }
                }
              }
              pullRequestContributions(first: 100) {
                totalCount
                nodes {
                  pullRequest {
                    title
                    merged
                    mergedAt
                    createdAt
                    repository {
                      name
                    }
                    changedFiles
                    additions
                    deletions
                  }
                }
              }
              pullRequestReviewContributions(first: 100) {
                totalCount
                nodes {
                  pullRequestReview {
                    repository {
                      name
                    }
                    createdAt
                    state
                    comments {
                      totalCount
                    }
                  }
                }
              }
              issueContributions(first: 100) {
                totalCount
                nodes {
                  issue {
                    title
                    createdAt
                    repository {
                      name
                    }
                    state
                    comments {
                      totalCount
                    }
                  }
                }
              }
            }
            repositories(first: 100, orderBy: {field: STARGAZERS, direction: DESC}) {
              totalCount
              nodes {
                name
                stargazerCount
                forkCount
                isFork
                isPrivate
                primaryLanguage {
                  name
                }
                languages(first: 10) {
                  nodes {
                    name
                  }
                }
                owner {
                  login
                }
                releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
                  totalCount
                  nodes {
                    name
                    createdAt
                    tagName
                    isPrerelease
                    isDraft
                  }
                }
                vulnerabilityAlerts(first: 10) {
                  totalCount
                  nodes {
                    createdAt
                    dismissedAt
                    vulnerableManifestPath
                    securityVulnerability {
                      severity
                      package {
                        name
                      }
                    }
                  }
                }
              }
            }
            repositoryDiscussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
              totalCount
              nodes {
                title
                createdAt
                repository {
                  name
                }
                comments {
                  totalCount
                }
                upvoteCount
                category {
                  name
                }
              }
            }
          }
        }
        """
        
        # Configure timeout and other session parameters
        timeout = aiohttp.ClientTimeout(total=90)  # Longer timeout for the large GraphQL query
        
        async with ClientSession(timeout=timeout) as session:
            # Use only one GraphQL call instead of multiple REST calls
            variables = {
                "login": username,
                "since": since_date
            }
            
            graphql_result = await fetch_graphql_data(session, query, variables, headers)
            
            # Check for errors
            if isinstance(graphql_result, dict) and 'errors' in graphql_result:
                logger.error(f"GraphQL error for {username}: {graphql_result['errors']}")
                return {'error': f"GraphQL error: {graphql_result['errors']}"}
                
            # Process the result
            if 'data' in graphql_result:
                # Store the raw GraphQL data for processing by aggregate_user_data_graphql
                result = {
                    'graphql_data': graphql_result['data']
                }
                
                # Also extract the basic data for compatibility with existing code
                user_data = graphql_result['data'].get('user', {})
                if not user_data:
                    return {'error': 'User not found in GraphQL response'}
                    
                # Contributions collection
                contrib_data = user_data.get('contributionsCollection', {})
                
                # Extract pull request data
                pr_contribs = contrib_data.get('pullRequestContributions', {})
                result['pulls'] = {
                    'total_count': pr_contribs.get('totalCount', 0),
                    'items': [pr.get('pullRequest', {}) for pr in pr_contribs.get('nodes', [])]
                }
                
                # Extract issue data
                issue_contribs = contrib_data.get('issueContributions', {})
                result['issues'] = {
                    'total_count': issue_contribs.get('totalCount', 0),
                    'items': [ic.get('issue', {}) for ic in issue_contribs.get('nodes', [])]
                }
                
                # Extract repository data
                result['repos'] = {
                    'total_count': user_data.get('repositories', {}).get('totalCount', 0),
                    'items': user_data.get('repositories', {}).get('nodes', [])
                }
                
                # Extract reviews data
                review_contribs = contrib_data.get('pullRequestReviewContributions', {})
                result['reviews'] = {
                    'total_count': review_contribs.get('totalCount', 0),
                    'items': [rc.get('pullRequestReview', {}) for rc in review_contribs.get('nodes', [])]
                }
                
                # Extract discussions data
                discussions_data = user_data.get('repositoryDiscussions', {})
                result['discussions'] = {
                    'total_count': discussions_data.get('totalCount', 0),
                    'items': discussions_data.get('nodes', [])
                }
                
                # Extract commits by repository
                result['repo_commits'] = []
                for repo_contrib in contrib_data.get('commitContributionsByRepository', []):
                    repo = repo_contrib.get('repository', {})
                    repo_name = repo.get('name', '')
                    if repo_name:
                        result['repo_commits'].append({
                            'name': repo_name,
                            'owner': repo.get('owner', {}).get('login', ''),
                            'commit_count': repo_contrib.get('contributions', {}).get('totalCount', 0),
                            'commits': repo_contrib.get('contributions', {}).get('nodes', [])
                        })
                
                return result
            
            return {'error': 'Invalid GraphQL response format'}
            
    except ImportError:
        logger.warning("aiohttp not installed, falling back to GraphQL")
        # Fall back to synchronous GraphQL
        graphql_data = get_user_contributions_graphql(username)
        
        if isinstance(graphql_data, dict) and 'error' in graphql_data:
            return graphql_data
            
        # Process the result
        user_data = graphql_data.get('user', {})
        if not user_data:
            return {'error': 'User not found'}
            
        # Contributions collection
        contrib_data = user_data.get('contributionsCollection', {})
        
        # Extract data in the same format as the async version
        result = {
            'graphql_data': graphql_data,
            'pulls': {
                'total_count': contrib_data.get('pullRequestContributions', {}).get('totalCount', 0),
                'items': [pr.get('pullRequest', {}) for pr in contrib_data.get('pullRequestContributions', {}).get('nodes', [])]
            },
            'issues': {
                'total_count': contrib_data.get('issueContributions', {}).get('totalCount', 0),
                'items': [ic.get('issue', {}) for ic in contrib_data.get('issueContributions', {}).get('nodes', [])]
            },
            'repos': {
                'total_count': user_data.get('repositories', {}).get('totalCount', 0),
                'items': user_data.get('repositories', {}).get('nodes', [])
            },
            'reviews': {
                'total_count': contrib_data.get('pullRequestReviewContributions', {}).get('totalCount', 0),
                'items': [rc.get('pullRequestReview', {}) for rc in contrib_data.get('pullRequestReviewContributions', {}).get('nodes', [])]
            },
            'discussions': {
                'total_count': user_data.get('repositoryDiscussions', {}).get('totalCount', 0),
                'items': user_data.get('repositoryDiscussions', {}).get('nodes', [])
            }
        }
        
        # Add commit data
        result['repo_commits'] = []
        for repo_contrib in contrib_data.get('commitContributionsByRepository', []):
            repo = repo_contrib.get('repository', {})
            repo_name = repo.get('name', '')
            if repo_name:
                result['repo_commits'].append({
                    'name': repo_name,
                    'owner': repo.get('owner', {}).get('login', ''),
                    'commit_count': repo_contrib.get('contributions', {}).get('totalCount', 0),
                    'commits': repo_contrib.get('contributions', {}).get('nodes', [])
                })
        
        return result
    except Exception as e:
        logger.error(f"Error in async GraphQL data fetching: {str(e)}")
        return {'error': f"Error in async data fetching: {str(e)}"}

# --- Batch Processing ---
async def batch_process_users(usernames: list) -> dict:
    """Process multiple GitHub users in batch for organizational assessments.
    
    This is more efficient than processing users one by one as it manages rate
    limits better and can parallelize some operations.
    
    Args:
        usernames (list): List of GitHub usernames to analyze
        
    Returns:
        dict: Dictionary with username keys and analysis values
    """
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Check input
        if not usernames or not isinstance(usernames, list):
            return {'error': 'Invalid usernames list'}
            
        # Deduplicate and clean usernames
        unique_usernames = list(set(usernames))
        
        # Process in batches to be respectful of API limits
        # GitHub's rate limit is typically 5000 requests per hour with a token
        # We need to be conservative with the batch size to not hit limits
        MAX_BATCH_SIZE = 5  # Process 5 users at a time
        
        results = {}
        for i in range(0, len(unique_usernames), MAX_BATCH_SIZE):
            batch = unique_usernames[i:i+MAX_BATCH_SIZE]
            
            # Create tasks for each user
            tasks = [fetch_all_data(username) for username in batch]
            
            # Run tasks concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process each result
            for username, data in zip(batch, batch_results):
                if isinstance(data, Exception):
                    logger.error(f"Error processing {username}: {str(data)}")
                    results[username] = {'error': f"Error fetching data: {str(data)}"}
                elif isinstance(data, dict) and 'error' in data:
                    results[username] = data
                else:
                    # Successful data fetch, aggregate into metrics
                    # Use ThreadPoolExecutor for CPU-bound aggregation
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(aggregate_user_data, username, data)
                        try:
                            user_result = future.result(timeout=60)  # Timeout after 60 seconds
                            results[username] = user_result
                        except Exception as e:
                            logger.error(f"Error aggregating data for {username}: {str(e)}")
                            results[username] = {'error': f"Error aggregating data: {str(e)}"}
            
            # Pause between batches if more exist to avoid rate limiting
            if i + MAX_BATCH_SIZE < len(unique_usernames):
                await asyncio.sleep(2)  # 2 second pause between batches
        
        return results
    except ImportError:
        logger.error("Required libraries not available for batch processing")
        return {'error': "Required libraries not available for batch processing"}
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        return {'error': f"Error in batch processing: {str(e)}"}

def compare_users(usernames: list) -> dict:
    """Compare multiple GitHub users side by side.
    
    Args:
        usernames (list): List of GitHub usernames to compare
        
    Returns:
        dict: Dictionary with comparison metrics
    """
    try:
        import asyncio
        
        # Check input
        if not usernames or not isinstance(usernames, list) or len(usernames) < 2:
            return {'error': 'Need at least two valid usernames to compare'}
            
        # Get data for all users through batch processing
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(batch_process_users(usernames))
        
        # Extract key metrics for comparison
        metrics = ['impact_score', 'repo_impact', 'code_quality', 'consistency', 
                   'collaboration', 'community', 'security']
                   
        # Initialize comparison structure
        comparison = {
            'users': {},
            'highest_scores': {},
            'averages': {}
        }
        
        # Extract metrics from each user's results
        for username, data in results.items():
            if 'error' in data:
                comparison['users'][username] = {'error': data['error']}
                continue
                
            user_metrics = {}
            for metric in metrics:
                user_metrics[metric] = data.get(metric, 0)
                
            comparison['users'][username] = user_metrics
            
        # Calculate highest scores and averages
        valid_users = [u for u, d in comparison['users'].items() if 'error' not in d]
        
        if valid_users:
            # Calculate highest scores
            for metric in metrics:
                highest_score = max([comparison['users'][u][metric] for u in valid_users])
                highest_scorers = [u for u in valid_users if comparison['users'][u][metric] == highest_score]
                
                comparison['highest_scores'][metric] = {
                    'score': highest_score,
                    'users': highest_scorers
                }
                
            # Calculate averages
            for metric in metrics:
                avg_score = sum([comparison['users'][u][metric] for u in valid_users]) / len(valid_users)
                comparison['averages'][metric] = avg_score
                
        return comparison
    except ImportError:
        logger.error("Required libraries not available for user comparison")
        return {'error': "Required libraries not available for user comparison"}
    except Exception as e:
        logger.error(f"Error in user comparison: {str(e)}")
        return {'error': f"Error in user comparison: {str(e)}"}