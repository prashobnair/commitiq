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

# --- Constants ---
#Prashob: @todo Need to review these constans
MAX_STARS = 10000  # Normalization baseline for stars
MAX_FORKS = 50000 # Example
MAX_CONTRIBUTORS = 100  # Normalization baseline for contributors

TIME_WINDOW_DAYS = 365  # Analyze 1 year of history instead of 2 for better performance

def normalize_metric(value: float, max_value: float) -> float:
    """Normalizes a metric to a 0-1 range."""
    if value is None:
        return 0
    return min(value / max_value, 1.0)

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
        user_data = github_data.get('user', {})
        
        if not user_data:
            logger.error(f"User data not found in GraphQL response for {username}")
            return {'error': f'User not found'}
        
        # Basic user info
        result['name'] = user_data.get('name')
        result['email'] = user_data.get('email')
        result['url'] = user_data.get('url')
        result['company'] = user_data.get('company')
        result['location'] = user_data.get('location')
        result['bio'] = user_data.get('bio')
        result['followers'] = user_data.get('followers', {}).get('totalCount', 0) if user_data.get('followers') is not None else 0
        result['following'] = user_data.get('following', {}).get('totalCount', 0) if user_data.get('following') is not None else 0
        
        # Get contributions collection data
        contrib_data = user_data.get('contributionsCollection', {})
        
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
        repos = user_data.get('repositories', {})
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
        
        result['project_impact'] = calculate_overall_project_impact(result['repositories'])
        
        return result
    except Exception as e:
        logger.error(f"Error in aggregate_user_data_graphql: {str(e)}")
        return {'error': f"Error aggregating user data: {str(e)}"}

def calculate_impact_score(data):
    """Calculate the impact score based on GraphQL data
    
    This optimized version uses parallel processing for large datasets.
    """
    try:
        # Extract key metrics from the data
        metrics = data.get('metrics', {})
        
        # Determine if the dataset is large enough to benefit from parallelization
        repos = data.get('repositories', {})
        pull_requests = data.get('pull_requests', [])
        reviews = data.get('reviews', [])
        
        is_large_dataset = (
            len(repos) > 10 or 
            len(pull_requests) > 50 or 
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
        
        # Add in followers contribution
        followers = data.get('followers', 0)
        community += normalize_metric(followers, 1000) * 1.0
        
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
        # Default to a moderate security score since we removed the security advisories functionality
        security_score = 0.5
            
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
        
        # Extract key metrics from the data
        metrics = data.get('metrics', {})
        
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
            community += normalize_metric(followers, 1000) * 1.0
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
            # Default to a moderate security score since we removed the security advisories functionality
            return 0.5
        
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
        
        # Execute tasks in parallel
        with ThreadPoolExecutor(max_workers=min(7, os.cpu_count() or 4)) as executor:
            futures = [
                executor.submit(func, *args) 
                for func, args in tasks
            ]
            
            # Collect results and apply weights
            result = sum(
                future.result() * weight 
                for future, weight in zip(futures, weights)
            )
        
        # Scale to 0-100 range
        return result * 100
    except Exception as e:
        logger.error(f"Error in parallel impact score calculation: {str(e)}")
        raise  # Re-raise to fall back to sequential processing

def calculate_overall_project_impact(repos: dict) -> float:
    """Calculate overall project impact using weighted average"""
    if not repos:
        return 0
        
    # Use diminishing returns for repository count
    # First 5 repos count fully, additional repos have diminishing impact
    effective_repo_count = min(5, len(repos)) + max(0, (len(repos) - 5) * 0.5)
    
    if effective_repo_count == 0:
        return 0
        
    total_impact = 0
    valid_repos = 0
    
    for repo_name, repo_data in repos.items():
        # Skip invalid data
        if not isinstance(repo_data, dict) or 'is_fork' not in repo_data:
            continue
            
        is_original = not repo_data.get('is_fork', False)
        project_impact_score = calculate_project_impact(repo_data, is_original)
        total_impact += project_impact_score
        valid_repos += 1
    
    # Calculate average impact and scale to 100
    if valid_repos == 0:
        return 0
        
    avg_impact = total_impact / valid_repos
    
    # Scale average impact (typical range 0-0.7) to 0-100
    # 0.7 is approximately the max score for a single high-quality repository
    normalized_score = (avg_impact / 0.7) * 100
    
    # Apply a bonus for having multiple quality repositories
    # This rewards both quality (high avg_impact) and quantity (multiple repos)
    quantity_bonus = min(20, (effective_repo_count - 1) * 5)  # Up to 20% bonus
    
    return min(normalized_score + quantity_bonus, 100)

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

    normalized_stars = min(repo_data.get('stars', 0) / MAX_STARS, 1.0)  # Cap at 1.0
    normalized_forks = min(repo_data.get('forks', 0) / MAX_FORKS, 1.0)
    normalized_contributors = min(repo_data.get('num_contributors', 1) / MAX_CONTRIBUTORS, 1.0)

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

def fetch_all_data(username):
    """Fetch all GitHub data for a user asynchronously using GraphQL."""
    try:
        # Calculate the date for the time window
        since_date = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Define the GraphQL query
        query = """
        query ($login: String!, $since: DateTime!) {
          user(login: $login) {
            name
            email
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
              }
            }
          }
        }
        """
        
        variables = {
                "login": username,
                "since": since_date
            }
        
        graphql = GitHubGraphQL()  # Instantiate the GraphQL client
        graphql_response = graphql.execute_query(query, variables) 

        if 'data' in graphql_response:
            return graphql_response['data']
        
        return {'error': 'Invalid GraphQL response format.'}
        
    except Exception as e:
        logger.error(f"Error in GraphQL data fetching: {str(e)}")
        return {'error': f"Error in data fetching: {str(e)}"}