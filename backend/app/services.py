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

# Try to import Redis, but make it optional
try:
    import redis
    redis_available = True
    r = redis.Redis(host='localhost', port=6379, db=0)
except ImportError:
    redis_available = False
    r = None

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
        self.last_call = 0
        self.headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
        
    def make_request(self, url: str) -> requests.Response:
        """Make a rate-limited request to the GitHub API"""
        now = time.time()
        if now - self.last_call < 1.1:  # Respect GitHub's rate limits
            time.sleep(1.1 - (now - self.last_call))
        
        response = requests.get(url, headers=self.headers)
        self.last_call = time.time()
        
        # Check rate limits
        self.handle_rate_limits(response)
        
        return response
    
    def handle_rate_limits(self, response: requests.Response) -> None:
        """Handle GitHub API rate limits"""
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        if remaining < 10:
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            sleep_duration = max(reset_time - time.time(), 10)
            logging.warning(f"Rate limit almost reached. Sleeping for {sleep_duration} seconds")
            time.sleep(sleep_duration)

# --- Constants ---
MAX_STARS = 10000  # Normalization baseline for stars
MAX_FORKS = 50000 # Example
MAX_CONTRIBUTORS = 100  # Normalization baseline for contributors
MAX_COMMITS = 2000
MAX_PRS = 500
MAX_ISSUES = 500
MAX_REVIEWS = 500

BOT_IDENTIFIERS = ["[bot]", "dependabot"] # Used to filter the commits from bots

# --- Helper Functions ---
def is_bot(user_data: any) -> bool:
    """Check if user is a bot account"""
    # Handle empty input
    if not user_data:
        return False
    
    # Handle nested user objects
    if isinstance(user_data, dict):
        login = user_data.get('login', '')
        user_type = user_data.get('type', '')
        
        # Direct check for Bot type
        if user_type == 'Bot':
            return True
    else:
        # If it's a string (username), use it directly
        login = str(user_data)
    
    # List of common bot identifiers
    bot_identifiers = [
        "[bot]", 
        "dependabot", 
        "renovate", 
        "github-actions", 
        "codecov", 
        "stale", 
        "greenkeeper",
        "snyk",
        "imgbot",
        "whitesource",
        "codebot",
        "travis",
        "jenkins",
        "circleci"
    ]
    
    # Check if any bot identifier is in the login
    return any(bot_id in login.lower() for bot_id in bot_identifiers)

def calculate_commit_frequency(commits, time_window_days=730):
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

    total_additions = 0
    total_deletions = 0

    for commit in commits:
      if not commit.get('stats'):
          #If stats are not present, skip
          continue
      total_additions += commit['stats']['additions']
      total_deletions += commit['stats']['deletions']

    if total_additions == 0:
        return 0 # Handle cases where additions might be zero.

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
    """Fetch pull requests with improved pagination"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=is:pr+author:{username}+created:>={date}&per_page=100'
    )
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    raw_pulls =  get_user_contributions(url_template, username, "pulls", date=two_years_ago)
    # Check for error response
    if isinstance(raw_pulls, dict) and 'error' in raw_pulls:
        return raw_pulls
    processed_pulls = []
    for pull in raw_pulls:
      if is_bot(pull.get('user', {}).get('login', '')): # check and skip bots
        continue
      processed_pulls.append({
          'id': pull.get('id'), # Use get to avoid key errors
          'title': pull.get('title'),
          'created_at': pull.get('created_at'),
          'closed_at': pull.get('closed_at'),
          'merged': pull.get('pull_request', {}).get('merged_at') is not None,
          'url': pull.get('html_url'),
          'repo_url': pull.get('repository_url')
      })
    return processed_pulls


@cache_response()
def get_user_issues(username):
    """Fetch issues created by user"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=is:issue+author:{username}+created:>={date}&per_page=100'
    )
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    raw_issues = get_user_contributions(url_template, username, "issues", date=two_years_ago)
    if isinstance(raw_issues, dict) and 'error' in raw_issues:  # Check for error
      return raw_issues
    processed_issues = []
    for issue in raw_issues:
        if is_bot(issue.get('user', {}).get('login', '')):
            continue
        processed_issues.append({
            'id': issue.get('id'),
            'title': issue.get('title'),
            'created_at': issue.get('created_at'),
            'closed_at': issue.get('closed_at'),
            'state': issue.get('state'),
            'url': issue.get('html_url'),
            'repo_url': issue.get('repository_url')
        })
    return processed_issues

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_user_reviews(username):
    """Fetch pull requests reviewed by user, including review comments."""
    api = GitHubAPI()  # Use the GitHubAPI class
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Use the Search API to find PRs *reviewed by* the user
    url = f'https://api.github.com/search/issues?q=is:pr+reviewed-by:{username}+created:>={two_years_ago}&per_page=100'
    
    try:
        response = api.make_request(url)  # Use the rate-limited request method
        logger.debug(f"Fetching reviews from: {response.url}")  # Instead of print()
        
        if response.status_code != 200:
            return {'error': f'Could not fetch reviews: {response.status_code} - {response.text}'}
        
        all_reviews = []
        review_data = response.json().get('items', [])  # Default to empty list if 'items' is missing
        
        for review in review_data:
            review_comments_url = review['url'] + '/reviews'  # Construct URL for *review* comments
            review_comments_response = api.make_request(review_comments_url)  # Use GitHubAPI here too
            
            comments_list = []  # Initialize *before* the if statement
            if review_comments_response.status_code == 200:
                review_comments = review_comments_response.json()
                # Process the review comments
                for comment in review_comments:
                    if comment['user']['login'] == username:  # Check if comment is from the target user
                        # Extract relevant data from the comment:
                        comment_data = {
                            'comment_id': comment['id'],
                            'comment_body': comment['body'],
                            'comment_created_at': comment['submitted_at'],  # Use 'submitted_at' for reviews
                            'state': comment['state']  # IMPORTANT: 'APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', etc.
                        }
                        comments_list.append(comment_data)
            
            # Add all the details to final output
            all_reviews.append({
                'pr_id': review.get('number'),  # Use .get() for safety
                'pr_title': review.get('title'),
                'pr_url': review.get('html_url'),
                'repo_url': review.get('repository_url'),
                'comments': comments_list
            })
        
        # Handle pagination
        while 'next' in response.links:
            response = api.make_request(response.links['next']['url'])  # Use GitHubAPI for pagination
            
            if response.status_code != 200:
                return {'error': f'Could not fetch reviews: {response.status_code} - {response.text}'}
            
            review_data = response.json().get('items', [])
            for review in review_data:
                review_comments_url = review['url'] + '/reviews'
                review_comments_response = api.make_request(review_comments_url)
                
                comments_list = []
                if review_comments_response.status_code == 200:
                    review_comments = review_comments_response.json()
                    for comment in review_comments:
                        if comment['user']['login'] == username:
                            comment_data = {
                                'comment_id': comment['id'],
                                'comment_body': comment['body'],
                                'comment_created_at': comment['submitted_at'],
                                'state': comment['state']
                            }
                            comments_list.append(comment_data)
                
                all_reviews.append({
                    'pr_id': review.get('number'),
                    'pr_title': review.get('title'),
                    'pr_url': review.get('html_url'),
                    'repo_url': review.get('repository_url'),
                    'comments': comments_list
                })
        
        return all_reviews
    
    except Exception as e:
        logger.error(f"Error fetching reviews: {str(e)}")
        return {'error': f'Error fetching reviews: {str(e)}'}


@cache_response()
def get_user_repos(username):
    """Fetch user repositories, handling pagination."""
    url_template = f'https://api.github.com/users/{{username}}/repos?per_page=100'
    return get_user_contributions(url_template, username, "repositories")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_repo_commits(username, repo_name):
    """Fetch commits for a specific repository, handling pagination and errors."""
    api = GitHubAPI()  # Use the GitHubAPI class
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={two_years_ago}&per_page=100'

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
        try:
            # Fetch data using the API functions
            if async_data is None:
                # If async data is not present, use the sync functions
                pulls = get_user_pulls(username)
                issues = get_user_issues(username)
                reviews = get_user_reviews(username)
                repos = get_user_repos(username)
                security_advisories = get_security_advisories(username)
                discussions = get_discussions(username)
            else:
                # If async_data is passed, unpack data
                pulls = async_data.get('pulls', [])
                if isinstance(pulls, dict) and 'items' in pulls:
                    pulls = pulls.get('items', [])
                
                issues = async_data.get('issues', [])
                if isinstance(issues, dict) and 'items' in issues:
                    issues = issues.get('items', [])
                
                reviews = async_data.get('reviews', [])
                if isinstance(reviews, dict) and 'items' in reviews:
                    reviews = reviews.get('items', [])
                
                repos = async_data.get('repos', [])
                
                security_advisories = async_data.get('security_advisories', [])
                if isinstance(security_advisories, dict) and 'items' in security_advisories:
                    security_advisories = security_advisories.get('items', [])
                
                discussions = async_data.get('discussions', [])
                if isinstance(discussions, dict) and 'items' in discussions:
                    discussions = discussions.get('items', [])

            # Check for errors
            if isinstance(pulls, dict) and 'error' in pulls:
                return {'error': f"Error fetching pulls: {pulls['error']}"}

            if isinstance(issues, dict) and 'error' in issues:
                return {'error': f"Error fetching issues: {issues['error']}"}

            if isinstance(reviews, dict) and 'error' in reviews:  # Added check for dict
                return {'error': f"Error fetching reviews: {reviews['error']}"}

            if isinstance(repos, dict) and 'error' in repos:
                return {'error': f"Error fetching repos: {repos['error']}"}
                
            # Add logging for debugging data structures
            logging.debug(f"Pulls data type: {type(pulls)}, length: {len(pulls)}")
            if pulls and len(pulls) > 0:
                logging.debug(f"First pull request keys: {pulls[0].keys() if isinstance(pulls[0], dict) else 'not a dict'}")
                
            logging.debug(f"Repos data type: {type(repos)}, length: {len(repos)}")
            if repos and len(repos) > 0:
                logging.debug(f"First repo keys: {repos[0].keys() if isinstance(repos[0], dict) else 'not a dict'}")

            if isinstance(security_advisories, dict) and 'error' in security_advisories:
                logging.warning(f"Error fetching security advisories: {security_advisories['error']}")
                security_advisories = []  # Continue with empty list instead of failing
                
            if isinstance(discussions, dict) and 'error' in discussions:
                logging.warning(f"Error fetching discussions: {discussions['error']}")
                discussions = []  # Continue with empty list instead of failing

            # Process the data as before
            # ... existing code ...

            # Aggregate data
            num_merged_prs = sum(1 for pull in pulls if pull.get('merged', False))
            num_issues_created = len(issues)
            num_issues_resolved =  sum(1 for issue in issues if issue['state'] == 'closed')# Count all closed ones
            num_code_reviews = len(reviews)

             # Initialize aggregated data with repo information
            aggregated_data = {
                'username': username,
                'merged_prs': num_merged_prs,
                'issues_created': num_issues_created,
                'issues_resolved':num_issues_resolved,
                'code_reviews': num_code_reviews,
                'repos': [],  # Initialize an empty list for repo data
                'total_commits': 0, #Initialize total commits
                'project_impact': 0, # Initialize project impact score
                'consistency': 0, # Initialize consistency score
                'code_quality': 0, # Initialize code quality score
                # New metrics
                'file_impact': 0,
                'code_survival_rate': 0,
                'security_impact': 0,
                'review_turnaround': calculate_review_turnaround(reviews),
                'discussion_engagement': analyze_discussion_quality(discussions),
                'dependency_health': {'total_dep_updates': 0, 'update_frequency': 0, 'dep_files_updated': 0},
                'ci_cd_usage': {'score': 0}
            }
            # Add review details (NEW)
            total_approved = 0
            total_changes_requested = 0
            total_comments = 0

            for review in reviews:  # Iterate through the reviews (each review is a PR)
              if 'comments' in review: # Check if comments key is present.
                for comment in review['comments']: #Iterate through comments
                  if comment['state'] == 'APPROVED':
                      total_approved += 1
                  elif comment['state'] == 'CHANGES_REQUESTED':
                      total_changes_requested += 1
                  elif comment['state'] == 'COMMENTED':
                      total_comments += 1

            aggregated_data['total_approved_reviews'] = total_approved
            aggregated_data['total_changes_requested'] = total_changes_requested
            aggregated_data['total_review_comments'] = total_comments #number of comments

            # Collect all commits for analysis
            all_commits = []
            
             # Aggregate commit counts and other repo-level metrics
            for repo in repos:
                    repo_name = repo['name']
                    repo_owner = repo['owner']['login'] if 'owner' in repo and 'login' in repo['owner'] else username
                    commits_response = get_repo_commits(username, repo_name)
                    
                    # Handle error responses from get_repo_commits
                    if isinstance(commits_response, tuple) and len(commits_response) > 0 and isinstance(commits_response[0], dict) and 'error' in commits_response[0]:
                        logging.warning(f"Error fetching commits for {repo_name}: {commits_response[0]['error']}")
                        commits = []  # Use empty list instead of returning error
                    else:
                        commits = commits_response
                        
                    num_commits = len(commits)
                    aggregated_data['total_commits'] += num_commits
                    
                    # Add commits to all_commits for later analysis
                    all_commits.extend(commits)

                    # Get contributors with proper error handling
                    api = GitHubAPI()  # Use the GitHubAPI class
                    contributors_response = api.make_request(repo['contributors_url'])
                    logging.debug(f"Contributors response for {repo_name}: Status {contributors_response.status_code}, Content-Type: {contributors_response.headers.get('Content-Type')}")
                    
                    # Handle different response types for contributors
                    if contributors_response.status_code == 204:  # No Content
                        num_contributors = 0
                    elif contributors_response.status_code == 200:
                        try:
                            contributors_data = contributors_response.json()
                            num_contributors = len(contributors_data)
                        except Exception as e:
                            logging.error(f"Error parsing contributors JSON for {repo_name}: {str(e)}")
                            num_contributors = 0
                    else:
                        logging.warning(f"Unexpected status code for contributors: {contributors_response.status_code}")
                        num_contributors = 0
                        
                    # Get CI/CD usage
                    ci_cd_data = detect_ci_cd(repo_owner, repo_name)
                    
                    # Get release impact
                    release_data = get_release_impact(repo_owner, repo_name)
                    
                    # Calculate test coverage
                    test_coverage = calculate_test_coverage(commits)
                    
                    # Calculate dependency health
                    dependency_data = analyze_dependency_updates(commits)
                    
                    is_original = not repo['fork']
                    repo_data = {
                    'name': repo_name,
                    'url': repo['html_url'],
                    'stars': repo['stargazers_count'],
                    'forks': repo['forks_count'],
                    'num_contributors': num_contributors,
                    'commit_frequency': calculate_commit_frequency(commits),  # Implement this helper function
                    'last_updated': repo['updated_at'],
                    'created_at': repo['created_at'],  # <--- ADD THIS
                    'num_commits': num_commits, # Add commit count for this repo
                    'original': is_original,
                    'fork' : repo['fork'],
                    'commits': commits,  # Store commits for later use
                    'ci_cd_usage': ci_cd_data,
                    'release_impact': release_data,
                    'test_coverage': test_coverage,
                    'dependency_health': dependency_data
                     }
                    aggregated_data['repos'].append(repo_data)
                    
                    # Update aggregated CI/CD score
                    aggregated_data['ci_cd_usage']['score'] = max(
                        aggregated_data['ci_cd_usage']['score'],
                        ci_cd_data.get('score', 0)
                    )
                    
                    # Update aggregated dependency health
                    aggregated_data['dependency_health']['total_dep_updates'] += dependency_data.get('total_dep_updates', 0)
                    aggregated_data['dependency_health']['dep_files_updated'] += dependency_data.get('dep_files_updated', 0)
            
            # Calculate aggregated dependency update frequency
            if aggregated_data['total_commits'] > 0:
                aggregated_data['dependency_health']['update_frequency'] = (
                    aggregated_data['dependency_health']['total_dep_updates'] / 
                    aggregated_data['total_commits']
                )
            
            # Calculate code quality
            aggregated_data['code_quality'] = calculate_code_quality(all_commits)
            
            # Calculate file impact and survival
            aggregated_data['file_impact'] = calculate_file_impact(all_commits)
            aggregated_data['code_survival_rate'] = calculate_file_survival(all_commits)
            
            # Calculate security impact
            aggregated_data['security_impact'] = calculate_security_impact(all_commits, security_advisories)
            
            # Calculate consistency (using all contributions)
            all_contributions = pulls + issues + reviews
            aggregated_data['consistency'] = calculate_consistency(all_contributions)
            
            # Calculate overall project impact
            aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)
            
            # Calculate final impact score with new metrics
            aggregated_data['impact_score'] = calculate_impact_score(aggregated_data)

            return aggregated_data

        except ConnectionError as e:
            return {'error': f"Network connection error: {str(e)}"}
        except Timeout as e:
            return {'error': f"Request timed out: {str(e)}"}
        except TooManyRedirects as e:
            return {'error': f"Too many redirects: {str(e)}"}
        except RequestException as e:  # Catch-all for other request exceptions
            logger.error(f"Request error: {str(e)}")
            return {'error': f"Request error: {str(e)}"}
        except Exception as e:
            logging.exception(f"Unexpected error in aggregate_user_data: {str(e)}")
            return {'error': f"An unexpected error occurred: {str(e)}"}

# Async version for parallel data fetching
async def fetch_all_data(username):
    """Parallel data fetching using asyncio"""
    try:
        import asyncio
        import aiohttp
        from aiohttp import ClientSession, ClientError
        
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
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:pr+author:{username}+created:>={two_years_ago}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_issues_async(session, headers):
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:issue+author:{username}+created:>={two_years_ago}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_repos_async(session, headers):
            url = f'https://api.github.com/users/{username}/repos?per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_reviews_async(session, headers):
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=is:pr+reviewed-by:{username}+created:>={two_years_ago}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_security_advisories_async(session, headers):
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=author:{username}+label:security+created:>={two_years_ago}&per_page=100'
            return await fetch_data(session, url, headers)
            
        async def get_discussions_async(session, headers):
            two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
            url = f'https://api.github.com/search/issues?q=author:{username}+is:discussion+created:>={two_years_ago}&per_page=100'
            return await fetch_data(session, url, headers)
        
        headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
        
        # Configure timeout and other session parameters
        timeout = aiohttp.ClientTimeout(total=60)  # 60 seconds timeout
        
        async with ClientSession(timeout=timeout) as session:
            pulls_task = get_pulls_async(session, headers)
            issues_task = get_issues_async(session, headers)
            repos_task = get_repos_async(session, headers)
            reviews_task = get_reviews_async(session, headers)
            security_task = get_security_advisories_async(session, headers)
            discussions_task = get_discussions_async(session, headers)
            
            pulls_data, issues_data, repos_data, reviews_data, security_data, discussions_data = await asyncio.gather(
                pulls_task, issues_task, repos_task, reviews_task, security_task, discussions_task,
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
                
            if isinstance(reviews_data, Exception):
                logger.error(f"Error fetching reviews: {str(reviews_data)}")
                result['reviews'] = {'error': f'Error fetching reviews: {str(reviews_data)}'}
            else:
                result['reviews'] = reviews_data
                
            if isinstance(security_data, Exception):
                logger.error(f"Error fetching security advisories: {str(security_data)}")
                result['security_advisories'] = {'error': f'Error fetching security advisories: {str(security_data)}'}
            else:
                result['security_advisories'] = security_data
                
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
            'security_advisories': get_security_advisories(username),
            'discussions': get_discussions(username)
        }
    except ClientError as e:
        logger.error(f"Network error in async operation: {str(e)}")
        return {'error': f"Network error: {str(e)}"}
    except asyncio.TimeoutError:
        logger.error("Async operation timed out")
        return {'error': "Operation timed out"}
    except Exception as e:
        logger.error(f"Error in async data fetching: {str(e)}")
        return {'error': f"Error in async data fetching: {str(e)}"}

def calculate_commit_frequency(commits, time_window_days=730):
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

def normalize_metric(value, max_value):
    """Normalizes a metric to a 0-1 range."""
    if value is None:
        return 0
    return min(value / max_value, 1.0)


def calculate_impact_score(aggregated_data: dict) -> float:
    """Calculates the Impact Score based on the aggregated data (normalized)."""
    # Enhanced weights based on industry research and new metrics
    weights = {
        # Core contribution metrics
        'merged_prs': 0.15,
        'code_quality': 0.12,
        'project_impact': 0.15,
        
        # New code evolution metrics
        'file_impact': 0.08,
        'code_survival_rate': 0.05,
        
        # Collaboration metrics
        'review_quality': 0.10,
        'review_turnaround': 0.05,
        
        # Project health metrics
        'ci_cd_usage': 0.06,
        'test_coverage': 0.06,
        
        # Security metrics
        'security_impact': 0.08,
        
        # Maintenance metrics
        'dependency_health': 0.05,
        
        # Community engagement
        'discussion_engagement': 0.05,
        
        # Consistency over time
        'consistency': 0.05
    }
    
    # Calculate review quality score
    total_reviews = aggregated_data.get('total_review_comments', 0) or 1  # Avoid division by zero
    approved_ratio = aggregated_data.get('total_approved_reviews', 0) / total_reviews
    
    # Normalize review turnaround (lower is better)
    # Assume 48 hours is the maximum reasonable turnaround time
    turnaround_hours = aggregated_data.get('review_turnaround', 48)
    normalized_turnaround = 1.0 - min(turnaround_hours / 48.0, 1.0)
    
    # Get CI/CD usage score
    ci_cd_score = aggregated_data.get('ci_cd_usage', {}).get('score', 0)
    
    # Get dependency health score
    dep_update_frequency = aggregated_data.get('dependency_health', {}).get('update_frequency', 0)
    normalized_dep_health = min(dep_update_frequency * 5, 1.0)  # Normalize: 20% updates is considered good
    
    # Get discussion engagement score
    discussion_score = aggregated_data.get('discussion_engagement', {}).get('engagement_score', 0) / 100.0
    
    # Calculate the final impact score
    impact_score = (
        # Core contribution metrics
        weights['merged_prs'] * normalize_metric(aggregated_data.get('merged_prs', 0), MAX_PRS) +
        weights['code_quality'] * (aggregated_data.get('code_quality', 0) / 100) +
        weights['project_impact'] * (aggregated_data.get('project_impact', 0) / 100) +
        
        # New code evolution metrics
        weights['file_impact'] * aggregated_data.get('file_impact', 0) +
        weights['code_survival_rate'] * (aggregated_data.get('code_survival_rate', 0) / 100) +
        
        # Collaboration metrics
        weights['review_quality'] * approved_ratio +
        weights['review_turnaround'] * normalized_turnaround +
        
        # Project health metrics
        weights['ci_cd_usage'] * ci_cd_score +
        weights['test_coverage'] * (aggregated_data.get('test_coverage', 0) / 100) +
        
        # Security metrics
        weights['security_impact'] * (aggregated_data.get('security_impact', 0) / 100) +
        
        # Maintenance metrics
        weights['dependency_health'] * normalized_dep_health +
        
        # Community engagement
        weights['discussion_engagement'] * discussion_score +
        
        # Consistency over time
        weights['consistency'] * aggregated_data.get('consistency', 0)
    ) * 100

    return min(impact_score, 100)  # Convert to percentage and cap at 100

def calculate_project_impact(repo_data: dict, is_original: bool) -> float:
    """Calculate impact score for a single repository"""
    if is_original:
        originality_weight = 0.7  # High weight for original repos
    else:
        originality_weight = 0.1  # Low weight for forked repos

    stars_weight = 0.15
    forks_weight = 0.05  # Significantly reduced
    contributors_weight = 0.1

    # Normalize stars/forks (example - adjust as needed)
    max_stars = 10000  # Example maximum - could be based on data analysis
    max_forks = 50000  # Example maximum
    max_contributors = 100 # Example

    normalized_stars = min(repo_data['stars'] / max_stars, 1.0)  # Cap at 1.0
    normalized_forks = min(repo_data['forks'] / max_forks, 1.0)
    normalized_contributors = min(repo_data['num_contributors'] / max_contributors, 1.0)

    # Age Factor (example - adjust as needed)
    # You'll need to get the repo creation date and calculate the age
    repo_created_at = datetime.strptime(repo_data['created_at'], '%Y-%m-%dT%H:%M:%SZ') # Add created_at to your repo data
    repo_age_years = (datetime.now() - repo_created_at).days / 365.25
    age_factor = 1 / (1 + repo_age_years)  # Example: 1-year-old repo -> factor of 0.5, 5-year-old -> ~0.16

    #Combine
    project_impact_score = (
        originality_weight +
        (1-originality_weight)* (stars_weight * normalized_stars +
        forks_weight * normalized_forks +
        contributors_weight * normalized_contributors)
        ) * age_factor

    return project_impact_score

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
        is_original = not repo.get('fork',False) #check if the repo is forked.
        repo['impact_score'] = calculate_project_impact(repo, is_original)  # Calculate individual repo impact and pass is_original
        total_impact += repo['impact_score']
    return total_impact

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

# --- New Code Evolution Metrics ---
def calculate_file_survival(commits: list) -> float:
    """Calculate percentage of files still present in latest commit"""
    if not commits:
        return 0
        
    surviving_files = set()
    all_files = set()
    
    # Process commits in reverse chronological order (newest first)
    sorted_commits = sorted(commits, key=lambda c: c.get('commit', {}).get('author', {}).get('date', ''), reverse=True)
    
    for commit in sorted_commits:
        files = commit.get('files', [])
        if not files:
            continue
            
        for file_info in files:
            filename = file_info.get('filename')
            if not filename:
                continue
                
            status = file_info.get('status')
            
            if status == 'removed':
                surviving_files.discard(filename)
            else:  # added or modified
                surviving_files.add(filename)
                
            all_files.add(filename)
    
    return len(surviving_files) / len(all_files) if all_files else 0

def calculate_file_impact(commits: list) -> float:
    """Calculate file impact based on file types and paths"""
    if not commits:
        return 0
        
    # Extract all files from commits
    all_files = []
    for commit in commits:
        files = commit.get('files', [])
        if files:
            all_files.extend([f.get('filename') for f in files if f.get('filename')])
    
    if not all_files:
        return 0
    
    # Define weights for different file types and paths
    # These weights can be adjusted based on the specific project
    weights = {
        # Core code files by extension
        '.py': 1.5,
        '.js': 1.5,
        '.ts': 1.5,
        '.java': 1.5,
        '.c': 1.5,
        '.cpp': 1.5,
        '.go': 1.5,
        '.rs': 1.5,
        
        # Test files
        'test': 1.2,
        'spec': 1.2,
        
        # Documentation
        '.md': 0.7,
        '.rst': 0.7,
        'docs/': 0.7,
        
        # Configuration
        '.json': 0.8,
        '.yml': 0.8,
        '.yaml': 0.8,
        '.toml': 0.8,
        '.ini': 0.8,
        
        # Build and deployment
        'Dockerfile': 1.0,
        '.github/workflows/': 1.0,
        'ci/': 1.0,
        
        # Examples and scripts
        'examples/': 0.6,
        'scripts/': 0.8
    }
    
    # Calculate impact score
    total_impact = 0
    for file_path in all_files:
        file_weight = 0.5  # Default weight
        
        # Check for matches in our weights dictionary
        for pattern, weight in weights.items():
            if pattern in file_path.lower():
                file_weight = max(file_weight, weight)  # Use the highest matching weight
        
        total_impact += file_weight
    
    # Normalize by number of files
    return total_impact / len(all_files)

# --- Collaboration Metrics ---
def calculate_review_turnaround(reviews: list) -> float:
    """Calculate average PR review turnaround time in hours"""
    if not reviews:
        return 0
        
    total_time = 0
    valid_reviews = 0
    
    for review in reviews:
        # Skip reviews without necessary data
        if not review.get('comments'):
            continue
            
        for comment in review.get('comments', []):
            # Skip comments without necessary timestamps
            if not comment.get('comment_created_at'):
                continue
                
            try:
                # Get PR creation time from the review object
                pr_url = review.get('pr_url', '')
                if not pr_url:
                    continue
                    
                # Extract PR number and repo from URL
                parts = pr_url.split('/')
                if len(parts) < 7:
                    continue
                    
                repo_owner = parts[3]
                repo_name = parts[4]
                pr_number = parts[6]
                
                # Fetch PR details to get creation time
                api = GitHubAPI()
                pr_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}'
                pr_response = api.make_request(pr_url)
                
                if pr_response.status_code != 200:
                    continue
                    
                pr_data = pr_response.json()
                pr_created_at = pr_data.get('created_at')
                
                if not pr_created_at:
                    continue
                
                # Calculate time difference
                pr_created = datetime.strptime(pr_created_at, '%Y-%m-%dT%H:%M:%SZ')
                review_time = datetime.strptime(comment['comment_created_at'], '%Y-%m-%dT%H:%M:%SZ')
                
                # Only count if review is after PR creation
                if review_time > pr_created:
                    time_diff = (review_time - pr_created).total_seconds() / 3600  # Convert to hours
                    total_time += time_diff
                    valid_reviews += 1
                    
            except (KeyError, ValueError, Exception) as e:
                logging.error(f"Error calculating review turnaround: {str(e)}")
                continue
    
    return total_time / valid_reviews if valid_reviews else 0

# --- Project Health Metrics ---
def detect_ci_cd(repo_owner: str, repo_name: str) -> dict:
    """Detect CI/CD usage in repository"""
    api = GitHubAPI()
    
    # Common CI/CD configuration paths
    paths = [
        '.github/workflows',           # GitHub Actions
        '.circleci/config.yml',        # CircleCI
        '.travis.yml',                 # Travis CI
        'azure-pipelines.yml',         # Azure Pipelines
        'Jenkinsfile',                 # Jenkins
        '.gitlab-ci.yml',              # GitLab CI
        'bitbucket-pipelines.yml',     # Bitbucket Pipelines
        '.drone.yml',                  # Drone CI
        'appveyor.yml',                # AppVeyor
        'cloudbuild.yaml',             # Google Cloud Build
        'buildspec.yml',               # AWS CodeBuild
        '.teamcity/'                   # TeamCity
    ]
    
    ci_cd_results = {}
    
    for path in paths:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"
        try:
            response = api.make_request(url)
            ci_cd_results[path] = response.status_code == 200
        except Exception as e:
            logging.error(f"Error checking CI/CD path {path}: {str(e)}")
            ci_cd_results[path] = False
    
    # Calculate overall CI/CD score (percentage of detected CI/CD systems)
    ci_cd_results['score'] = sum(1 for v in ci_cd_results.values() if v) / len(paths)
    
    return ci_cd_results

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
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "security_advisories", date=two_years_ago)

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
    """Fetch user's discussion participation"""
    url_template = (
        'https://api.github.com/search/issues?'
        'q=author:{username}+is:discussion+created:>={date}&per_page=100'
    )
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return get_user_contributions(url_template, username, "discussions", date=two_years_ago)

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