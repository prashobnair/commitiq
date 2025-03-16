import requests
from datetime import datetime, timedelta
import os
from flask import jsonify
import time
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, wait_exponential
import logging
from functools import lru_cache, wraps
import json
import aiohttp
import asyncio
import random
import zlib
import sys
import math
import numpy as np
# Get logger for this module
logger = logging.getLogger(__name__)

# Try to import Redis, but make it optional
try:
    import redis
    
    r = redis.Redis(host='localhost', port=6379, db=0)
    # Test Redis connection
    r.ping()
    redis_available = True
    logger.info("Redis cache available")
except (ImportError, redis.exceptions.ConnectionError) as e:
    redis_available = False
    r = None
    logger.warning(f"Redis not available: {str(e)}. Using in-memory cache.")

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

# --- Constants ---
TIME_WINDOW_DAYS = 365  # Analyze 1 year of history instead of 2 for better performance

# Normalization thresholds (min, max) for percentile-based normalization
NORMALIZATION_THRESHOLDS = {
    'pulls': (0, 1.0),
    'commits': (0, 12.0),
    'reviews': (0, 1.0),
    'issues': (0, 1.0),
    'repos_impact': (0, 0.02),
    'consistency': (0, 0.28),
    'technical_impact': (0.0, 0.015),
    'ecosystem_impact': (0.0, 0.005)
}

# Weights for repository impact calculation
REPO_IMPACT_WEIGHTS = {
    'technical': 0.65,
    'ecosystem': 0.35
}

# Weights for technical impact sub-components
TECHNICAL_IMPACT_WEIGHTS = {
    'pr_acceptance': 0.85,
    'review_activity': 0.15
}

# Weights for final impact score components
IMPACT_SCORE_WEIGHTS = {
    'pulls': 0.35,
    'commits': 0.30,
    'reviews': 0.10,
    'issues': 0.10,
    'repos_impact': 0.10,
    'consistency': 0.05
}

# Collaboration factor calculation constants
COLLAB_FACTOR = {
    'base': 1.0,
    'log_factor': 0.4,
    'max_value': 2
}

# Review activity normalization
REVIEW_ACTIVITY = {
    'normalization_factor': 1.0  # Normalize review comments per 100
}

# Contribution ratio exponent (diminishing returns for higher contribution percentages)
CONTRIBUTION_RATIO_EXPONENT = 1.0

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

class GitHubGraphQL:
    """GraphQL client for GitHub API"""
    
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
        self.timeout = 25  # Keep under GitHub's 30s timeout threshold
    
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
    
    @retry(
        stop=stop_after_attempt(3),  # Increase to 3
        wait=wait_exponential(multiplier=1, min=2, max=10),  # conservative backoff
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError, RequestException)),
        reraise=False  # Don't reraise the exception after all retries
    )
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
                timeout=self.timeout
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
                if response.status_code >= 500:
                    # Any server error should trigger a retry
                    logger.warning(f"GitHub server error ({response.status_code}) - triggering retry")
                    raise RequestException(f"Server error: {response.status_code}")
                else:
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
            # Re-raise to trigger retry decorator
            raise
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
def aggregate_user_data(username, github_data):
    """Aggregate GitHub user data 
    
    Args:
        username (str): GitHub username
        graphql_data (dict): pre-fetched GraphQL data from fetch_all_data
        
    Returns:
        dict: Aggregated user data with metrics
    """
    try:
        # Initialize results dictionary
        result = {
            'username': username,
            'contributions': {
                'pulls': 0,
                'commits': 0,
                'issues': 0,
                'reviews': 0,
                'repos_impact': 0,
                'consistency': 0,
                'top_repositories': []
            }
        }
        
        # Create temporary storage for detailed metrics (not returned to frontend)
        temp_metrics = {
            'repositories': [],  # Detailed repository metrics
            'repos_impact': {},  # Repository impact calculations
            'consistency': {}    # Consistency metrics
        }

        # Extract user information
        user_data = github_data.get('user', {})
        
        if not user_data:
            logger.error(f"User data not found in GraphQL response for {username}")
            return {'error': f'User not found'}
        
        # Basic user info - always store this even if user has zero activity
        result.update({k: user_data.get(k) for k in ['name', 'email', 'url', 'company', 'location', 'bio', 'avatarUrl']})
        result['followers'] = user_data.get('followers', {}).get('totalCount', 0) if user_data.get('followers') is not None else 0
        result['following'] = user_data.get('following', {}).get('totalCount', 0) if user_data.get('following') is not None else 0
        
        # Get contribution metrics
        result['contributions']['pulls'] = user_data.get('contributionsCollection', {}).get('totalPullRequestContributions', 0)
        result['contributions']['commits'] = user_data.get('contributionsCollection', {}).get('totalCommitContributions', 0)
        result['contributions']['reviews'] = user_data.get('contributionsCollection', {}).get('totalPullRequestReviewContributions', 0)
        result['contributions']['issues'] = user_data.get('contributionsCollection', {}).get('totalIssueContributions', 0)
        
        # Get weighted repository metrics
        repos = user_data.get('repositories', {}).get('nodes', [])
        repo_impacts = []
        
        # Calculate top languages used by the developer using actual language statistics
        language_usage = {}
        
        for repo in repos:
            if repo.get('isPrivate', False):
                continue
            
            # Get repository metrics
            stars = repo.get('stargazerCount', 0)
            forks = repo.get('forkCount', 0)
            
            # Get collaborators
            collaborators = repo.get('collaborators').get('totalCount', 0) if repo.get('collaborators') is not None else 0
            collab_factor = min(COLLAB_FACTOR['base'] + math.log(collaborators + 1) * COLLAB_FACTOR['log_factor'], 
                               COLLAB_FACTOR['max_value'])
            
            # Get developer's relative commits in this repo
            developer_commits = 0
            contrib_repos = user_data.get('contributionsCollection', {}).get('commitContributionsByRepository', [])
            for contrib in contrib_repos:
                if contrib.get('repository', {}).get('name') == repo.get('name'):
                    developer_commits = contrib.get('contributions', {}).get('totalCount', 0)
            
            total_commits = repo.get('defaultBranchRef', {}).get('target', {}).get('history', {}).get('totalCount', 0) if repo.get('defaultBranchRef', {}) is not None else 0
            
            contribution_ratio = developer_commits / total_commits if total_commits > 0 else 0
            
            # Get language statistics for this repository
            languages_data = repo.get('languages', {})
            language_edges = languages_data.get('edges', [])
            
            for edge in language_edges:
                language_name = edge.get('node', {}).get('name')
                language_size = edge.get('size', 0)
                
                if not language_name or language_size <= 0:
                    continue
                
                # Skip blacklisted languages
                if language_name in LANGUAGE_BLACKLIST:
                    continue
                
                # Weight language usage by code size and contribution ratio
                weighted_size = language_size * contribution_ratio
                
                # Only add languages with non-zero weighted size
                if weighted_size > 0:
                    # Accumulate language usage
                    if language_name in language_usage:
                        language_usage[language_name] += weighted_size
                    else:
                        language_usage[language_name] = weighted_size
            
            # Pull Request stats
            merged_pull_requests = repo.get('mergedPullRequests', {}).get('totalCount', 0)
            closed_pull_requests = repo.get('closedPullRequests', {}).get('totalCount', 0)
            total_pull_requests = merged_pull_requests + closed_pull_requests
            pr_acceptance = merged_pull_requests / total_pull_requests if total_pull_requests > 0 else 0.5
            
            # Review stats
            pull_request_nodes = repo.get('pullRequests', {}).get('nodes', [])
            review_comments = sum(
                pr.get('reviews', {}).get('totalCount', 0) + pr.get('comments', {}).get('totalCount', 0)
                for pr in pull_request_nodes
            )
            
            # Calculate technical impact
            code_quality = (
                TECHNICAL_IMPACT_WEIGHTS['pr_acceptance'] * pr_acceptance +
                TECHNICAL_IMPACT_WEIGHTS['review_activity'] * min(review_comments / REVIEW_ACTIVITY['normalization_factor'], 1.0) 
            )
            repo_tech_impact = (contribution_ratio ** CONTRIBUTION_RATIO_EXPONENT) * collab_factor * code_quality
            
            # Calculate ecosystem impact
            popularity = (stars + 0.1 * forks) ** 0.5
            repo_eco_impact = popularity * contribution_ratio
            
            repo_impact = (
                REPO_IMPACT_WEIGHTS['technical'] * repo_tech_impact +
                REPO_IMPACT_WEIGHTS['ecosystem'] * repo_eco_impact
            )

            repo_impacts.append(repo_impact)
            
            # Store repository sub-metrics - now including all technical and ecosystem impact metrics
            repo_metrics = {
                'name': repo.get('name'),
                'stars': stars,
                'forks': forks,
                'homepageUrl': repo.get('homepageUrl'),
                'collaborators': collaborators,
                'collab_factor': collab_factor,
                'developer_commits': developer_commits,
                'total_commits': total_commits,
                'contribution_ratio': contribution_ratio,
                'merged_pull_requests': merged_pull_requests,
                'closed_pull_requests': closed_pull_requests,
                'total_pull_requests': total_pull_requests,
                'pr_acceptance': pr_acceptance,
                'review_comments': review_comments,
                'code_quality': code_quality,
                'repo_tech_impact': repo_tech_impact,
                'popularity': popularity,
                'repo_eco_impact': repo_eco_impact,
                'repo_impact': repo_impact,
                # Store the component metrics used in calculations
                'technical_impact_components': {
                    'contribution_ratio': contribution_ratio,
                    'contribution_ratio_exponent': CONTRIBUTION_RATIO_EXPONENT,
                    'collab_factor': collab_factor,
                    'code_quality': code_quality,
                    'pr_acceptance_weight': TECHNICAL_IMPACT_WEIGHTS['pr_acceptance'],
                    'review_activity_weight': TECHNICAL_IMPACT_WEIGHTS['review_activity'],
                    'review_activity_normalization': REVIEW_ACTIVITY['normalization_factor']
                },
                'ecosystem_impact_components': {
                    'stars': stars,
                    'forks': forks,
                    'popularity_formula': f"({stars} + 0.1 * {forks})^0.5 = {popularity}",
                    'contribution_ratio': contribution_ratio
                }
            }
            
            temp_metrics['repositories'].append(repo_metrics)
            
        

        # Calculate repos_impact even if repo_impacts is empty (will be 0)
        result['contributions']['repos_impact'] = np.mean(repo_impacts) if repo_impacts else 0
        
        # Add top 4 repositories with highest repo_impact
        if temp_metrics['repositories']:
            # Sort repositories by repo_impact in descending order
            sorted_repos = sorted(temp_metrics['repositories'], key=lambda x: x['repo_impact'], reverse=True)
            # Take top 4 (or fewer if less than 4 exist)
            top_repos = sorted_repos[:4]
            
            # Extract required information for each top repository
            result['contributions']['top_repositories'] = []
            for repo in top_repos:
                # Find the original repository data to get primary language and last commit date
                original_repo = next((r for r in repos if r.get('name') == repo['name']), {})
                
                # Get primary language
                primary_language = original_repo.get('primaryLanguage', {})
                language_name = primary_language.get('name') if primary_language else None
                
                # Get last commit date
                last_commit_date = None
                if original_repo.get('defaultBranchRef'):
                    last_commit = original_repo.get('defaultBranchRef', {}).get('target', {}).get('lastCommit', {}).get('nodes', [])
                    if last_commit and len(last_commit) > 0:
                        last_commit_date = last_commit[0].get('committedDate')
                
                # Create repository summary with required fields
                repo_summary = {
                    'name': repo['name'],
                    'stars': repo['stars'],
                    'forks': repo['forks'],
                    'homepageUrl': repo['homepageUrl'],
                    'collaborators': repo['collaborators'],
                    'contribution_ratio': repo['contribution_ratio'],
                    'primary_language': language_name,
                    'last_commit_date': last_commit_date,
                    'repo_impact': repo['repo_impact']
                }
                
                result['contributions']['top_repositories'].append(repo_summary)
        else:
            result['contributions']['top_repositories'] = []
        
        # Sort languages by usage and take top 5
        top_languages = sorted(
            [{'name': lang, 'usage': size} for lang, size in language_usage.items()],
            key=lambda x: x['usage'],
            reverse=True
        )[:5]
        
        # Calculate percentages for visualization
        total_usage = sum(lang['usage'] for lang in top_languages) if top_languages else 1
        for lang in top_languages:
            lang['percentage'] = round((lang['usage'] / total_usage) * 100, 1)
            # Remove the raw usage value as it's not meaningful to display
            del lang['usage']
            
        result['contributions']['top_languages'] = top_languages
        
        
        # Consistency calculation
        weeks = user_data.get('contributionsCollection', {}).get('contributionCalendar', {}).get('weeks', [])
        active_weeks = sum(1 for week in weeks if any(
            day.get('contributionCount', 0) > 0 
            for day in week.get('contributionDays', [])
        ))
        result['contributions']['consistency'] = active_weeks / len(weeks) if weeks else 0    
        
        # Store consistency sub-metrics
        total_days = sum(len(week.get('contributionDays', [])) for week in weeks)
        active_days = sum(1 for week in weeks for day in week.get('contributionDays', []) 
                         if day.get('contributionCount', 0) > 0)
        total_contributions = sum(day.get('contributionCount', 0) 
                                 for week in weeks 
                                 for day in week.get('contributionDays', []))
        
        
        # Add a flag to indicate if this is a user with zero activity
        result['has_activity'] = (
            result['contributions']['pulls'] > 0 or
            result['contributions']['commits'] > 0 or
            result['contributions']['reviews'] > 0 or
            result['contributions']['issues'] > 0
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in aggregate_user_data_graphql: {str(e)}")
        return {'error': f"Error aggregating user data: {str(e)}"}

def percentile_normalize(value, lower_bound, upper_bound):
    """
    Normalize a value based on percentile bounds.
    If value <= lower_bound, return 0; if value >= upper_bound, return 100.
    Otherwise, linearly scale the value between lower_bound and upper_bound.
    """
    if value <= lower_bound:
        return 0
    if value >= upper_bound:
        return 100
    return ((value - lower_bound) / (upper_bound - lower_bound)) * 100

def fetch_all_data(username):
    """Fetch all GitHub data for a user asynchronously using GraphQL."""
    try:
        # Calculate the date for the time window
        since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        graphql = GitHubGraphQL()  # Instantiate the GraphQL client
        
        # Define the GraphQL query
        query = """
        query ($login: String!, $since: DateTime!) {
          user(login: $login) {
            name
            email
            location
            company
            bio
            avatarUrl
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
                weeks {
                  contributionDays {
                    contributionCount
                  }
                }
              }
              commitContributionsByRepository(maxRepositories: 20) {
                repository {
                  name
                }
                contributions(first: 100) {
                  totalCount
                }
              }
            }
            repositories(first: 20, orderBy: {field: STARGAZERS, direction: DESC}) {
              totalCount
              nodes {
                name
                stargazerCount
                forkCount
                isPrivate
                homepageUrl
                collaborators(first: 1) {
                  totalCount
                }
                mergedPullRequests: pullRequests(states: MERGED) {
                    totalCount
                }
                closedPullRequests: pullRequests(states: CLOSED) {
                    totalCount
                }
                pullRequests(first: 10) {
                    totalCount
                    nodes {
                        reviews {
                            totalCount
                        }
                        comments {
                            totalCount
                        }
                    }
                }
                primaryLanguage {
                  name
                }
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                    totalCount
                    edges {
                        size
                        node {
                            name
                        }
                    }
                }
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(first: 0) {
                                totalCount
                            }
                            lastCommit: history(first: 1) {
                                nodes {
                                    committedDate
                                }
                            }
                        }
                    }
                }
              }
            }
          }
        }
        """
        
        variables = {
                "login": username,
                "since": since_date
            }

        try:
            graphql_response = graphql.execute_query(query, variables)
        except Exception as e:
            # Handle the case where all retries are exhausted
            logger.error(f"All retry attempts failed for GitHub API: {str(e)}")
            return {'error': f"GitHub API is currently unavailable. Please try again later."}
        
        if 'data' in graphql_response:
            return graphql_response['data']
        
        return {'error': 'Invalid GraphQL response format.  graphql_response: ' + str(graphql_response)}
        
    except Exception as e:
        logger.error(f"Error in GraphQL data fetching: {str(e)}")
        return {'error': f"Error in data fetching: {str(e)}"}
    
def calculate_impact_score(data):
    """Calculate final impact score using percentile-based normalization"""
    try:
        contributions = data.get('contributions', {})
        
        # Normalize metrics
        pulls = percentile_normalize(
            contributions.get('pulls', 0),
            *NORMALIZATION_THRESHOLDS['pulls']
        )
        commits = percentile_normalize(
            contributions.get('commits', 0),
            *NORMALIZATION_THRESHOLDS['commits']
        )
        reviews = percentile_normalize(
            contributions.get('reviews', 0),
            *NORMALIZATION_THRESHOLDS['reviews']
        )
        issues = percentile_normalize(
            contributions.get('issues', 0),
            *NORMALIZATION_THRESHOLDS['issues']
        )
        repos_impact = percentile_normalize(
            contributions.get('repos_impact', 0),
            *NORMALIZATION_THRESHOLDS['repos_impact']
        )
        consistency = contributions.get('consistency', 0) * 100

        # Weighted sum using defined weights
        impact_score = (
            IMPACT_SCORE_WEIGHTS['pulls'] * pulls +
            IMPACT_SCORE_WEIGHTS['commits'] * commits +
            IMPACT_SCORE_WEIGHTS['reviews'] * reviews +
            IMPACT_SCORE_WEIGHTS['issues'] * issues +
            IMPACT_SCORE_WEIGHTS['repos_impact'] * repos_impact +
            IMPACT_SCORE_WEIGHTS['consistency'] * consistency
        )

        return min(max(impact_score, 0), 100)

    except Exception as e:
        logger.error(f"Scoring error: {str(e)}")
        return 0

# Add this constant at the top of the file with other constants
LANGUAGE_BLACKLIST = {
    # Markup Languages
    'HTML',
    'XML',
    'Markdown',
    'TeX',
    'Roff',
    'Adblock Filter List',
    'Rich Text Format',
    
    # Stylesheet Languages
    'CSS',
    'SCSS',
    'Less',
    
    # Data Formats / Configuration
    'JSON',
    'YAML',
    'INI',
    'Properties',
    'EditorConfig',
    'TOML',
    'CSV',
    'TSV',
    
    # Shell Scripting
    'Shell',
    'PowerShell',
    'Batchfile',
    
    # Build/Deployment/Infrastructure
    'Dockerfile',
    'Makefile',
    'CMake',
    'HCL',
    'Nix',
    'ApacheConf',
    'QML',
    'XSLT',
    
    # Editor/IDE Specific
    'Vim Script',
    'VimL',
    'Emacs Lisp',
    
    # Specialized/Less Common
    'Prolog',
    'Mathematica',
    'AutoHotkey',
    'SourcePawn',
    'Web Ontology Language',
    'SQF',
    'IDL',
    'PostScript',
    'M4',
    'Coq',
    'Standard ML',
    'Gherkin',
    'AutoIt',
    'TSQL',
    'PLSQL',
    'OpenSCAD',
    'BlitzBasic',
    'xBase',
    'FreeMarker',
    'WebAssembly',
    'Groff',
    'Xtend',
    'Max',
    'Logos',
    'Modelica'
}