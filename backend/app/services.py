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

# Try to import Redis, but make it optional
try:
    import redis
    redis_available = True
    r = redis.Redis(host='localhost', port=6379, db=0)
except ImportError:
    redis_available = False
    r = None

# Define constants
BOT_IDENTIFIERS = ['bot', 'actions', '-ci-', 'automation', 'dependabot']

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Caching decorator
def cache_response(ttl=3600):
    """Cache API responses using Redis if available, otherwise use lru_cache"""
    def decorator(func):
        @wraps(func)
        def wrapper(username, *args, **kwargs):
            global redis_available  # Move global declaration to the beginning
            
            # Create a cache key based on function name and arguments
            key = f"github:{func.__name__}:{username}"
            
            # If Redis is available, try to get from cache
            if redis_available and r:
                try:
                    # Add connection check
                    r.ping()
                    cached = r.get(key)
                    if cached:
                        logger.info(f"Cache hit for {key}")
                        return json.loads(cached)
                except (redis.ConnectionError, redis.RedisError) as e:
                    logger.error(f"Redis error: {str(e)}")
                    # Mark Redis as unavailable if connection fails
                    redis_available = False
            
            # Execute the function if not in cache or Redis unavailable
            result = func(username, *args, **kwargs)
            
            # Try to cache the result if Redis is available
            if redis_available and r:
                try:
                    # Only cache successful results (not error responses)
                    if not (isinstance(result, dict) and 'error' in result):
                        r.setex(key, ttl, json.dumps(result))
                except (redis.ConnectionError, redis.RedisError) as e:
                    logger.error(f"Redis caching error: {str(e)}")
                    # Mark Redis as unavailable if connection fails
                    redis_available = False
            
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
    """Calculates the commit frequency over a specified time window."""
    if not commits:
        return 0

    commit_dates = []
    for commit in commits:
        try:
            # Correctly handle potential missing 'commit' or 'author' keys
            commit_date_str = commit.get('commit', {}).get('author', {}).get('date')
            if commit_date_str:
                commit_dates.append(datetime.strptime(commit_date_str, '%Y-%m-%dT%H:%M:%SZ'))
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing commit date: {e}, commit: {commit}")
            # Could choose to skip this commit, or re-raise the exception
            continue  # Skip this commit and continue with the next

    if not commit_dates:
        return 0

    # Calculate commits within the time window
    two_years_ago = datetime.now() - timedelta(days=time_window_days)
    commits_in_window = [date for date in commit_dates if date >= two_years_ago]

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

def calculate_consistency(contributions: list) -> float:
    """Calculate contribution consistency over time (active months)."""
    if not contributions:
        return 0

    months_active = set()
    for contrib in contributions:
        # Handle different date keys for different contribution types
        date_key = 'created_at' if 'created_at' in contrib else 'submitted_at' if 'submitted_at' in contrib else None
        if date_key and contrib.get(date_key):
          try:
            dt = datetime.strptime(contrib[date_key], '%Y-%m-%dT%H:%M:%SZ')
            months_active.add((dt.year, dt.month)) # year, month tuple
          except:
            # if any error in parsing, move on
            continue

    return len(months_active) / 24.0  # 24 months in 2 years (maximum)

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
    """Fetch user repositories, handling pagination."""
    url_template = f'https://api.github.com/users/{{username}}/repos?per_page=100'
    return get_user_contributions(url_template, username, "repositories")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_repo_commits(username, repo_name):
    """Fetch commits for a specific repository."""
    api = GitHubAPI()
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={since_date}&per_page=100'

    all_commits = []
    while True:
        response = api.make_request(url)  # Use the rate-limited request method
        logging.debug(f"Fetching commits for repo: {repo_name}, URL: {url}, Status: {response.status_code}")

        if response.status_code == 200:
            all_commits.extend(response.json())
            if 'next' in response.links:
                url = response.links['next']['url']
                # No need for sleep here as GitHubAPI.make_request handles rate limiting
            else:
                break
        elif response.status_code == 409:
            logging.debug(f"Empty repository detected for {repo_name} (409 Conflict)")
            return []
        else:
            logging.error(f"Error fetching commits for {repo_name}: Status {response.status_code} - {response.text}")
            return {'error': f'Commit fetch failed: {response.status_code}'}
    
    return all_commits

# --- Aggregation and Calculation Functions ---
@cache_response()
def aggregate_user_data(username, async_data=None):
    """
    Aggregates all GitHub data for a user.
    Can use pre-fetched async data (more efficient) or fetch synchronously.
    
    Returns a comprehensive object with metrics, scores, and raw data.
    """
    start_time = time.time()
    logging.info(f"Starting aggregation for {username}")
    
    # Use async data if provided, otherwise fetch synchronously
    if async_data:
        pulls_data = async_data.get('pulls', [])
        issues_data = async_data.get('issues', [])
        repos_data = async_data.get('repos', [])
        reviews_data = async_data.get('reviews', [])
        discussions_data = async_data.get('discussions', [])
    else:
        # Fetch data synchronously (slower)
        pulls_data = get_user_pulls(username)
        issues_data = get_user_issues(username)
        repos_data = get_user_repos(username)
        reviews_data = get_user_reviews(username)
        discussions_data = get_discussions(username)
    
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
        'impact_score': 0
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
                # Remove file_impact calculation as it's not part of our key metrics
                
                # Remove review turnaround calculation as it's not part of our key metrics
                
                # Calculate test coverage
                repo_data['test_coverage'] = calculate_test_coverage(commits_data)
                
            # Add repo to aggregated data
            aggregated_data['repos'].append(repo_data)
    
    # Calculate overall metrics that matter for our 5 key metrics
    aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)
    aggregated_data['impact_score'] = calculate_impact_score(aggregated_data)
    
    logging.info(f"Aggregation completed in {time.time() - start_time:.2f} seconds")
    return aggregated_data

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
    url_template = (
        'https://api.github.com/search/issues?'
        'q=author:{username}+label:security+created:>={date}&per_page=100'
    )
    since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "security_advisories", date=since_date)

def calculate_security_impact(commits: list, advisories: list) -> float:
    """Calculate security impact score based on commits and advisories"""
    if not commits and not advisories:
        return 0
        
    # Security-related keywords in commit messages
    security_keywords = [
        'security', 'vulnerability', 'cve', 'exploit', 'attack', 
        'auth', 'authentication', 'authorization', 'encrypt', 'decrypt',
        'ssl', 'tls', 'https', 'firewall', 'injection', 'xss', 'csrf',
        'sanitize', 'validate', 'permission', 'access control'
    ]
    
    # Count security-related commits
    security_commits = 0
    for commit in commits:
        message = commit.get('commit', {}).get('message', '').lower()
        if any(kw in message for kw in security_keywords):
            security_commits += 1
    
    # Calculate security commit ratio
    security_commit_ratio = security_commits / len(commits) if commits else 0
    
    # Calculate advisory impact
    advisory_impact = 0
    if advisories:
        # Impact weights for different security severity levels
        impact_weights = {
            'critical': 2.0,
            'high': 1.5,
            'medium': 1.2,
            'low': 0.8,
            'security': 1.0  # Default for general security label
        }
        
        for advisory in advisories:
            # Extract labels
            labels = []
            for label in advisory.get('labels', []):
                if isinstance(label, dict):
                    labels.append(label.get('name', '').lower())
                elif isinstance(label, str):
                    labels.append(label.lower())
            
            # Calculate impact based on labels
            max_weight = 0.5  # Default weight
            for label in labels:
                for key, weight in impact_weights.items():
                    if key in label:
                        max_weight = max(max_weight, weight)
            
            advisory_impact += max_weight
    
    # Normalize advisory impact
    normalized_advisory_impact = min(advisory_impact / 10, 1.0) if advisories else 0
    
    # Combine metrics (weighted average)
    return (0.7 * security_commit_ratio + 0.3 * normalized_advisory_impact) * 100  # Convert to percentage

# --- Maintenance Metrics ---
def analyze_dependency_updates(commits: list) -> dict:
    """Detect and analyze dependency updates in commits"""
    if not commits:
        return {'total_dep_updates': 0, 'update_frequency': 0}
    
    # Keywords and patterns for dependency updates
    dep_keywords = {
        'dependabot': 1.0,
        'dependency': 0.8,
        'bump': 0.7,
        'update': 0.6,
        'upgrade': 0.9,
        'package': 0.7,
        'requirements': 0.8,
        'npm': 0.7,
        'pip': 0.7,
        'gem': 0.7,
        'cargo': 0.7
    }
    
    # Dependency files
    dep_files = [
        'package.json',
        'requirements.txt',
        'Gemfile',
        'Cargo.toml',
        'go.mod',
        'build.gradle',
        'pom.xml',
        'composer.json',
        'yarn.lock',
        'package-lock.json'
    ]
    
    # Count dependency update commits
    dep_commits = 0
    dep_files_updated = 0
    
    for commit in commits:
        # Check commit message
        message = commit.get('commit', {}).get('message', '').lower()
        is_dep_commit = False
        
        # Check for dependency keywords in commit message
        for kw, weight in dep_keywords.items():
            if kw in message:
                is_dep_commit = True
                break
        
        # Check for dependency file updates
        for file_info in commit.get('files', []):
            filename = file_info.get('filename', '')
            if any(dep_file in filename for dep_file in dep_files):
                is_dep_commit = True
                dep_files_updated += 1
                break
        
        if is_dep_commit:
            dep_commits += 1
    
    # Calculate metrics
    update_frequency = dep_commits / len(commits)
    
    return {
        'total_dep_updates': dep_commits,
        'update_frequency': update_frequency,
        'dep_files_updated': dep_files_updated
    }

def get_release_impact(repo_owner: str, repo_name: str) -> dict:
    """Analyze release history and impact"""
    api = GitHubAPI()
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    
    try:
        response = api.make_request(url)
        
        if response.status_code != 200:
            return {
                'total_releases': 0,
                'release_frequency': 0,
                'latest_release_age': None
            }
        
        releases = response.json()
        
        if not releases:
            return {
                'total_releases': 0,
                'release_frequency': 0,
                'latest_release_age': None
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
            'total_releases': total_releases,
            'release_frequency': release_frequency,
            'latest_release_age': latest_release_age,
            'total_downloads': total_downloads
        }
        
    except Exception as e:
        logging.error(f"Error fetching release data: {str(e)}")
        return {
            'total_releases': 0,
            'release_frequency': 0,
            'latest_release_age': None,
            'error': str(e)
        }

# --- Community Engagement Metrics ---
def get_discussions(username: str) -> list:
    """Fetch GitHub discussions created by the user"""
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
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"GraphQL request error: {str(e)}")
            raise
    
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
def aggregate_user_data_graphql(username):
    """Aggregate GitHub user data using the more efficient GraphQL API
    
    This function replaces multiple separate REST API calls with a single
    GraphQL query, which is much more efficient. The time window is also
    reduced from 2 years to 1 year for better performance.
    """
    try:
        # Get all data with a single GraphQL query
        graphql_data = get_user_contributions_graphql(username)
        
        # Check if there was an error
        if isinstance(graphql_data, dict) and 'error' in graphql_data:
            return graphql_data
        
        # Initialize results dictionary
        result = {
            'username': username,
            'raw_graphql_data': graphql_data,  # Store the raw data for potential reuse
            'metrics': {},
            'repositories': {},
            'activity': {
                'commits': 0,
                'pulls': 0,
                'issues': 0,
                'reviews': 0
            }
        }
        
        # Extract user information
        user_data = graphql_data.get('user', {})
        if not user_data:
            return {'error': 'User not found'}
        
        # Basic user info
        result['name'] = user_data.get('name')
        result['email'] = user_data.get('email')
        result['avatar_url'] = user_data.get('avatarUrl')
        result['url'] = user_data.get('url')
        result['company'] = user_data.get('company')
        result['location'] = user_data.get('location')
        result['bio'] = user_data.get('bio')
        result['followers'] = user_data.get('followers', {}).get('totalCount', 0)
        result['following'] = user_data.get('following', {}).get('totalCount', 0)
        
        # Get contributions collection data
        contrib_data = user_data.get('contributionsCollection', {})
        
        # Count metrics
        result['activity']['commits'] = contrib_data.get('totalCommitContributions', 0)
        result['activity']['pulls'] = contrib_data.get('totalPullRequestContributions', 0)
        result['activity']['reviews'] = contrib_data.get('totalPullRequestReviewContributions', 0)
        result['activity']['issues'] = contrib_data.get('totalIssueContributions', 0)
        
        # Get calendar data for consistency calculation
        calendar = contrib_data.get('contributionCalendar', {})
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
        
        # Extract commit data by repository
        commit_contribs = contrib_data.get('commitContributionsByRepository', [])
        repo_commits = {}
        
        for repo_contrib in commit_contribs:
            repo = repo_contrib.get('repository', {})
            repo_name = repo.get('name', '')
            if not repo_name:
                continue
                
            commit_count = repo_contrib.get('contributions', {}).get('totalCount', 0)
            
            # Store repository data
            repo_commits[repo_name] = {
                'name': repo_name,
                'owner': repo.get('owner', {}).get('login', ''),
                'commit_count': commit_count,
                'stars': repo.get('stargazerCount', 0),
                'forks': repo.get('forkCount', 0),
                'is_fork': repo.get('isFork', False),
                'primary_language': repo.get('primaryLanguage', {}).get('name', ''),
                'languages': [lang.get('name', '') for lang in repo.get('languages', {}).get('nodes', [])]
            }
        
        result['repositories'] = repo_commits
        
        # Extract pull request data
        pull_requests = []
        pr_contribs = contrib_data.get('pullRequestContributions', {}).get('nodes', [])
        
        for pr_contrib in pr_contribs:
            pr = pr_contrib.get('pullRequest', {})
            pr_data = {
                'title': pr.get('title', ''),
                'created_at': pr.get('createdAt'),
                'merged': pr.get('merged', False),
                'merged_at': pr.get('mergedAt'),
                'repository': pr.get('repository', {}).get('name', ''),
                'changed_files': pr.get('changedFiles', 0),
                'additions': pr.get('additions', 0),
                'deletions': pr.get('deletions', 0)
            }
            pull_requests.append(pr_data)
        
        result['pull_requests'] = pull_requests
        
        # Calculate PR metrics
        merged_prs = sum(1 for pr in pull_requests if pr.get('merged', False))
        result['metrics']['pr_acceptance_rate'] = merged_prs / len(pull_requests) if pull_requests else 0
        
        # Calculate average PR size
        if pull_requests:
            avg_changed_files = sum(pr.get('changed_files', 0) for pr in pull_requests) / len(pull_requests)
            avg_additions = sum(pr.get('additions', 0) for pr in pull_requests) / len(pull_requests)
            avg_deletions = sum(pr.get('deletions', 0) for pr in pull_requests) / len(pull_requests)
            
            result['metrics']['avg_pr_size'] = {
                'files': avg_changed_files,
                'additions': avg_additions,
                'deletions': avg_deletions
            }
        
        # Extract review data
        reviews = []
        review_contribs = contrib_data.get('pullRequestReviewContributions', {}).get('nodes', [])
        
        for review_contrib in review_contribs:
            review = review_contrib.get('pullRequestReview', {})
            review_data = {
                'state': review.get('state', ''),
                'created_at': review.get('createdAt'),
                'repository': review.get('repository', {}).get('name', ''),
                'comment_count': review.get('comments', {}).get('totalCount', 0)
            }
            reviews.append(review_data)
            
        result['reviews'] = reviews
        
        # Calculate review metrics
        review_with_comments = sum(1 for r in reviews if r.get('comment_count', 0) > 0)
        result['metrics']['review_comment_rate'] = review_with_comments / len(reviews) if reviews else 0
        
        # Calculate approved vs requested changes ratio
        approvals = sum(1 for r in reviews if r.get('state') == 'APPROVED')
        changes_requested = sum(1 for r in reviews if r.get('state') == 'CHANGES_REQUESTED')
        result['metrics']['review_approval_rate'] = approvals / (approvals + changes_requested) if (approvals + changes_requested) > 0 else 0
        
        # Get total repositories
        repos_data = user_data.get('repositories', {})
        result['metrics']['total_repos'] = repos_data.get('totalCount', 0)
        
        # Extract repositories data
        repositories = []
        for repo_node in repos_data.get('nodes', []):
            repo_data = {
                'name': repo_node.get('name', ''),
                'stars': repo_node.get('stargazerCount', 0),
                'forks': repo_node.get('forkCount', 0),
                'is_fork': repo_node.get('isFork', False),
                'primary_language': repo_node.get('primaryLanguage', {}).get('name', ''),
                'languages': [lang.get('name', '') for lang in repo_node.get('languages', {}).get('nodes', [])]
            }
            repositories.append(repo_data)
            
        # Calculate repository metrics
        non_forked_repos = sum(1 for r in repositories if not r.get('is_fork', False))
        result['metrics']['original_repo_ratio'] = non_forked_repos / len(repositories) if repositories else 0
        
        total_stars = sum(r.get('stars', 0) for r in repositories)
        result['metrics']['total_stars'] = total_stars
        
        # Calculate language diversity
        language_set = set()
        for repo in repositories:
            lang = repo.get('primary_language')
            if lang:
                language_set.add(lang)
            for additional_lang in repo.get('languages', []):
                if additional_lang:
                    language_set.add(additional_lang)
                    
        result['metrics']['language_diversity'] = len(language_set)
        
        # Calculate impact score based on GraphQL data
        result['impact_score'] = calculate_impact_score_graphql(result)
        
        return result
    except Exception as e:
        logger.error(f"Error in aggregate_user_data_graphql: {str(e)}")
        return {'error': f"Error aggregating user data: {str(e)}"}


def calculate_impact_score_graphql(data):
    """Calculate impact score based on GraphQL data and hiring manager survey data
    
    This function prioritizes metrics based on hiring manager survey data:
    - Merged PRs to active repos (32% weight)
    - Code review depth (28% weight)
    - Maintenance burden (19% weight)
    - Project popularity (15% weight)
    - Documentation (6% weight)
    """
    try:
        metrics = {}
        
        # 1. Merged PRs to active repos (32%)
        pull_requests = data.get('pull_requests', [])
        merged_prs = sum(1 for pr in pull_requests if pr.get('merged', False))
        # Normalize merged PRs (cap at 50)
        merged_pr_score = min(merged_prs / 50, 1.0)
        metrics['merged_prs'] = merged_pr_score * 32  # 32% weight
        
        # 2. Code review depth (28%)
        reviews = data.get('reviews', [])
        # Calculate weighted review score
        if reviews:
            # Count comments to measure depth
            total_comments = sum(r.get('comment_count', 0) for r in reviews)
            avg_comments = total_comments / len(reviews) if reviews else 0
            # Normalize (4+ comments per review is considered good depth)
            review_depth_score = min(avg_comments / 4, 1.0)
            # Add weight for approval/changes requested ratio
            approvals = sum(1 for r in reviews if r.get('state') == 'APPROVED')
            changes_requested = sum(1 for r in reviews if r.get('state') == 'CHANGES_REQUESTED')
            approval_ratio = approvals / (approvals + changes_requested) if (approvals + changes_requested) > 0 else 0
            # Combined review score
            review_score = (0.7 * review_depth_score) + (0.3 * approval_ratio)
        else:
            review_score = 0
        metrics['code_review'] = review_score * 28  # 28% weight
        
        # 3. Maintenance burden (19%)
        # Calculate activity consistency as a proxy for maintenance
        consistency = data.get('metrics', {}).get('consistency', 0)
        # Mix PR size into maintenance burden (smaller PRs are better for maintenance)
        avg_pr_size = data.get('metrics', {}).get('avg_pr_size', {})
        if avg_pr_size:
            # Normalize PR size (smaller is better, ideal is <5 files)
            avg_files = avg_pr_size.get('files', 0)
            size_score = max(0, 1 - (avg_files / 20))  # Cap at 20 files
        else:
            size_score = 0.5  # Default if no data
        
        maintenance_score = (0.6 * consistency) + (0.4 * size_score)
        metrics['maintenance'] = maintenance_score * 19  # 19% weight
        
        # 4. Project popularity (15%)
        repositories = data.get('repositories', {})
        if repositories:
            # Calculate average stars per repository
            repo_list = [repo for repo in repositories.values()]
            total_stars = sum(repo.get('stars', 0) for repo in repo_list)
            # Normalize stars (cap at 1000 total)
            popularity_score = min(total_stars / 1000, 1.0)
        else:
            popularity_score = 0
        metrics['popularity'] = popularity_score * 15  # 15% weight
        
        # 5. Documentation (6%)
        # Proxy for documentation: presence of README, markdown files, and comments in code
        # Since we don't have direct access to file content via GraphQL,
        # use review comment rate as a proxy for documentation mindset
        review_comment_rate = data.get('metrics', {}).get('review_comment_rate', 0)
        documentation_score = review_comment_rate
        metrics['documentation'] = documentation_score * 6  # 6% weight
        
        # Calculate final score (sum of weighted components)
        total_score = sum(metrics.values())
        
        # Return both the total score and component metrics for transparency
        return {
            'total': round(total_score, 2),
            'components': metrics
        }
    except Exception as e:
        logger.error(f"Error calculating impact score: {str(e)}")
        return {
            'total': 0,
            'error': str(e)
        }

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
    if isinstance(result, dict) and 'total' in result:
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
        logging.error(f"Expected repos to be a list, got {type(repos)}: {repos}")
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
    """Fetch all GitHub data for a user asynchronously."""
    try:
        from aiohttp import ClientSession, ClientError
        import asyncio
        
        async def fetch_data(session, url, headers):
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    return {'error': f'Error: {response.status} - {await response.text()}'}
            except ClientError as e:
                logger.error(f"Client error for {url}: {str(e)}")
                return {'error': f'Client error: {str(e)}'}
            except asyncio.TimeoutError:
                logger.error(f"Timeout for {url}")
                return {'error': 'Request timed out'}
        
        async def get_pulls_async(session, headers):
            since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:pr+author:{username}+created:>={since_date}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_issues_async(session, headers):
            since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:issue+author:{username}+created:>={since_date}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_repos_async(session, headers):
            url = f'https://api.github.com/users/{username}/repos?per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_reviews_async(session, headers):
            since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:pr+reviewed-by:{username}+created:>={since_date}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_discussions_async(session, headers):
            since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/discussions?q=author:{username}+created:>={since_date}&per_page=100'
            return await fetch_data(session, url, headers)
        
        async def process_repo(session, repo, headers):
            """Process a single repository to get its commits."""
            if isinstance(repo, dict) and 'name' in repo:
                repo_name = repo['name']
                return await get_repo_commits_async(session, username, repo_name, headers)
            return None
        
        headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
        
        # Configure timeout and other session parameters
        timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds timeout
        
        async with ClientSession(timeout=timeout) as session:
            # Fetch basic data
            pulls_task = get_pulls_async(session, headers)
            issues_task = get_issues_async(session, headers)
            repos_task = get_repos_async(session, headers)
            reviews_task = get_reviews_async(session, headers)
            discussions_task = get_discussions_async(session, headers)
            
            pulls_data, issues_data, repos_data, reviews_data, discussions_data = await asyncio.gather(
                pulls_task, issues_task, repos_task, reviews_task, discussions_task,
                return_exceptions=True  # Don't let one failure stop everything
            )
            
            # Handle any exceptions from the tasks
            result = {}
            
            if isinstance(pulls_data, Exception):
                logger.error(f"Error fetching pulls: {str(pulls_data)}")
                result['pulls'] = {'error': f'Error fetching pulls: {str(pulls_data)}'}
            else:
                result['pulls'] = pulls_data
                
            if isinstance(issues_data, Exception):
                logger.error(f"Error fetching issues: {str(issues_data)}")
                result['issues'] = {'error': f'Error fetching issues: {str(issues_data)}'}
            else:
                result['issues'] = issues_data
                
            if isinstance(repos_data, Exception):
                logger.error(f"Error fetching repos: {str(repos_data)}")
                result['repos'] = {'error': f'Error fetching repos: {str(repos_data)}'}
            else:
                result['repos'] = repos_data
                
                # Process repositories in parallel if repos data is valid
                if not isinstance(repos_data, dict) or 'error' not in repos_data:
                    # Extract repository list from the response
                    repos_list = repos_data.get('items', []) if isinstance(repos_data, dict) and 'items' in repos_data else repos_data
                    
                    if repos_list and isinstance(repos_list, list):
                        # Process all repositories in parallel
                        repo_tasks = [process_repo(session, repo, headers) for repo in repos_list]
                        repo_results = await asyncio.gather(*repo_tasks, return_exceptions=True)
                        
                        # Store repository commit data
                        result['repo_commits'] = []
                        for repo_result in repo_results:
                            if isinstance(repo_result, Exception):
                                logger.error(f"Error processing repo: {str(repo_result)}")
                            elif repo_result:  # Skip None results
                                result['repo_commits'].append(repo_result)
                
            if isinstance(reviews_data, Exception):
                logger.error(f"Error fetching reviews: {str(reviews_data)}")
                result['reviews'] = {'error': f'Error fetching reviews: {str(reviews_data)}'}
            else:
                result['reviews'] = reviews_data
                
            if isinstance(discussions_data, Exception):
                logger.error(f"Error fetching discussions: {str(discussions_data)}")
                result['discussions'] = {'error': f'Error fetching discussions: {str(discussions_data)}'}
            else:
                result['discussions'] = discussions_data
            
            return result
            
    except ImportError:
        logger.warning("aiohttp not installed, falling back to synchronous fetching")
        # Fall back to synchronous fetching
        return {
            'pulls': get_user_pulls(username),
            'issues': get_user_issues(username),
            'repos': get_user_repos(username),
            'reviews': get_user_reviews(username),
            'discussions': get_discussions(username)
        }
    except Exception as e:
        logger.error(f"Error in async data fetching: {str(e)}")
        return {'error': f"Error in async data fetching: {str(e)}"}