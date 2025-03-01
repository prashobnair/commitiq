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
            # Create a cache key based on function name and arguments
            key = f"github:{func.__name__}:{username}"
            
            # If Redis is available, use it for caching
            if redis_available and r:
                try:
                    cached = r.get(key)
                    if cached:
                        logger.info(f"Cache hit for {key}")
                        return json.loads(cached)
                    
                    result = func(username, *args, **kwargs)
                    # Only cache successful results (not error responses)
                    if not (isinstance(result, dict) and 'error' in result):
                        r.setex(key, ttl, json.dumps(result))
                    return result
                except Exception as e:
                    logger.error(f"Redis error: {str(e)}")
                    # Fall back to direct function call if Redis fails
                    return func(username, *args, **kwargs)
            else:
                # If Redis is not available, fall back to direct function call
                return func(username, *args, **kwargs)
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
def is_bot(user_login: any) -> bool:
    """Check if user is a bot account"""
    if not user_login:
        return False
        
    # Check if it's a string or a dictionary
    if isinstance(user_login, dict):
        # If it's a user object, extract the login
        user_login = user_login.get('login', '')
        
        # Also check the 'type' field if available
        if user_login.get('type') == 'Bot':
            return True
    
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
    
    return any(bot_id in user_login.lower() for bot_id in bot_identifiers)

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

def calculate_code_survival(commits):
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

def calculate_code_quality(commits):
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

def calculate_consistency(contributions):
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
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    # Use the Search API to find PRs *reviewed by* the user
    url = f'https://api.github.com/search/issues?q=is:pr+reviewed-by:{username}+created:>={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)
    print(response.url)

    if response.status_code != 200:
        return {'error': f'Could not fetch reviews: {response.status_code} - {response.text}'}

    all_reviews = []
    review_data = response.json().get('items', []) # Default to empty list if 'items' is missing
    for review in review_data:
        review_comments_url = review['url'] + '/reviews' # Construct URL for *review* comments
        review_comments_response = requests.get(review_comments_url, headers=headers)
        comments_list = []  # Initialize *before* the if statement
        if review_comments_response.status_code == 200:
            review_comments = review_comments_response.json()
            # Process the review comments
            for comment in review_comments:
                if comment['user']['login'] == username: # Check if comment is from the target user
                    # Extract relevant data from the comment:
                    comment_data = {
                        'comment_id': comment['id'],
                        'comment_body': comment['body'],
                        'comment_created_at': comment['submitted_at'], # Use 'submitted_at' for reviews
                        'state': comment['state']  # IMPORTANT: 'APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', etc.
                    }
                    comments_list.append(comment_data)
                    # You might also want to track:
                    # - Number of approved reviews
                    # - Number of reviews requesting changes
        # No 'elif' needed here.  If it's not 200, we just move on with an empty comments_list.
        # elif review_comments_response.status_code != 404:  # 404 means no reviews, which is fine
        #      return {'error': f'Could not fetch review comments: {response.status_code} - {response.text}'}

        time.sleep(1)  # Sleep for a second to avoid secondary rate limits
        #add all the details to final output
        all_reviews.append({
            'pr_id': review.get('number'), # Use .get() for safety
            'pr_title': review.get('title'),
            'pr_url': review.get('html_url'),
            'repo_url': review.get('repository_url'),
            'comments': comments_list
            #  You might still need to fetch individual *review* comments.
        })
    while 'next' in response.links.keys():
        response = requests.get(response.links['next']['url'], headers=headers)
        if response.status_code != 200:
            return {'error': f'Could not fetch reviews: {response.status_code} - {response.text}'}
        review_data = response.json().get('items', [])
        for review in review_data:
          review_comments_url = review['url'] + '/reviews' # Construct URL for *review* comments
          review_comments_response = requests.get(review_comments_url, headers=headers)
          comments_list = []  # Initialize *before* the if statement
          if review_comments_response.status_code == 200:
              review_comments = review_comments_response.json()
              # Process the review comments
              for comment in review_comments:
                  if comment['user']['login'] == username: # Check if comment is from the target user
                      # Extract relevant data from the comment:
                      comment_data = {
                          'comment_id': comment['id'],
                          'comment_body': comment['body'],
                          'comment_created_at': comment['submitted_at'], # Use 'submitted_at' for reviews
                          'state': comment['state']  # IMPORTANT: 'APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', etc.
                      }
                      comments_list.append(comment_data)
                      # You might also want to track:
                      # - Number of approved reviews
                      # - Number of reviews requesting changes
          # No 'elif' needed here.  If it's not 200, we just move on with an empty comments_list.
          #elif review_comments_response.status_code != 404:  # 404 means no reviews, which is fine
              #return {'error': f'Could not fetch review comments: {response.status_code} - {response.text}'}

          time.sleep(1)  # Sleep for a second to avoid secondary rate limits
          #add all the details to final output
          all_reviews.append({
              'pr_id': review.get('number'), # Use .get() for safety
              'pr_title': review.get('title'),
              'pr_url': review.get('html_url'),
              'repo_url': review.get('repository_url'),
              'comments': comments_list
              #  You might still need to fetch individual *review* comments.
          })
    return all_reviews


@cache_response()
def get_user_repos(username):
    """Fetch user repositories, handling pagination."""
    url_template = f'https://api.github.com/users/{{username}}/repos?per_page=100'
    return get_user_contributions(url_template, username, "repositories")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)))
@cache_response()
def get_repo_commits(username, repo_name):
    """Fetch commits for a specific repository, handling pagination and errors."""
    headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={two_years_ago}&per_page=100'

    all_commits = []
    while True:
        response = requests.get(url, headers=headers)
        logging.debug(f"Fetching commits for repo: {repo_name}, URL: {url}, Status: {response.status_code}")  # Debugging line

        if response.status_code == 200:
            all_commits.extend(response.json())
            if 'next' in response.links:
                url = response.links['next']['url']
                time.sleep(1)  # Respect GitHub's rate limits
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
def aggregate_user_data(username):
        try:
            # Fetch data using the API functions
            pulls = get_user_pulls(username)
            if isinstance(pulls, dict) and 'error' in pulls:
                return {'error': f"Error fetching pulls: {pulls['error']}"}

            issues = get_user_issues(username)
            if isinstance(issues, dict) and 'error' in issues:
                return {'error': f"Error fetching issues: {issues['error']}"}

            reviews = get_user_reviews(username)
            if isinstance(reviews, dict) and 'error' in reviews: #Added check for dict
                return {'error': f"Error fetching reviews: {reviews['error']}"}
            repos = get_user_repos(username)
            if isinstance(repos, dict) and 'error' in repos:
                return {'error': f"Error fetching repos: {repos['error']}"}
            # Aggregate data
            num_merged_prs = sum(1 for pull in pulls if pull['merged'])
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
                'code_quality': 0 # Initialize code quality score
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

             # Aggregate commit counts and other repo-level metrics
            for repo in repos:
                    repo_name = repo['name']
                    commits_response = get_repo_commits(username, repo_name)
                    
                    # Handle error responses from get_repo_commits
                    if isinstance(commits_response, tuple) and len(commits_response) > 0 and isinstance(commits_response[0], dict) and 'error' in commits_response[0]:
                        logging.warning(f"Error fetching commits for {repo_name}: {commits_response[0]['error']}")
                        commits = []  # Use empty list instead of returning error
                    else:
                        commits = commits_response
                        
                    num_commits = len(commits)
                    aggregated_data['total_commits'] += num_commits

                    # Get contributors with proper error handling
                    contributors_response = requests.get(repo['contributors_url'], headers={'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'})
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
                    'fork' : repo['fork']
                     }
                    aggregated_data['repos'].append(repo_data)

            # Collect all commits for code quality calculation
            all_commits = []
            for repo in aggregated_data['repos']:
                repo_name = repo['name']
                commits = get_repo_commits(username, repo_name)
                if not isinstance(commits, dict):  # Check it's not an error response
                    all_commits.extend(commits)
            
            # Calculate code quality
            aggregated_data['code_quality'] = calculate_code_quality(all_commits)
            
            # Calculate consistency (using all contributions)
            all_contributions = pulls + issues + reviews
            aggregated_data['consistency'] = calculate_consistency(all_contributions)
            
            # Calculate overall project impact - THIS LINE WAS MISSING!
            aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)

            return aggregated_data

        except ConnectionError as e:
            return {'error': f"Network connection error: {str(e)}"}
        except Timeout as e:
            return {'error': f"Request timed out: {str(e)}"}
        except TooManyRedirects as e:
            return {'error': f"Too many redirects: {str(e)}"}
        except RequestException as e:  # Catch-all for other request exceptions
            return {'error': f"Request error: {str(e)}"}
        except Exception as e:
            logging.exception(f"Unexpected error in aggregate_user_data: {str(e)}")
            return {'error': f"An unexpected error occurred: {str(e)}"}, 500

# Async version for parallel data fetching
async def fetch_all_data(username):
    """Parallel data fetching using asyncio"""
    try:
        import asyncio
        import aiohttp
        from aiohttp import ClientSession
        
        async def fetch_data(session, url, headers):
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return {'error': f'Error: {response.status}'}
        
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
        
        headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
        
        async with ClientSession() as session:
            pulls_task = get_pulls_async(session, headers)
            issues_task = get_issues_async(session, headers)
            repos_task = get_repos_async(session, headers)
            reviews_task = get_reviews_async(session, headers)
            
            pulls_data, issues_data, repos_data, reviews_data = await asyncio.gather(
                pulls_task, issues_task, repos_task, reviews_task
            )
            
            return {
                'pulls': pulls_data,
                'issues': issues_data,
                'repos': repos_data,
                'reviews': reviews_data
            }
    except ImportError:
        logger.warning("aiohttp not installed, falling back to synchronous fetching")
        # Fall back to synchronous fetching
        return {
            'pulls': get_user_pulls(username),
            'issues': get_user_issues(username),
            'repos': get_user_repos(username),
            'reviews': get_user_reviews(username)
        }
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
    # New weights based on industry research
    weights = {
        'merged_prs': 0.25,
        'code_quality': 0.20,  # New metric
        'project_impact': 0.30,
        'review_quality': 0.15,  # Changed from code_reviews
        'consistency': 0.10
    }
    
    # Calculate code quality score
    # Get all commits from all repos
    all_commits = []
    for repo in aggregated_data.get('repos', []):
        repo_name = repo.get('name')
        username = aggregated_data.get('username')
        if repo_name and username:
            commits = get_repo_commits(username, repo_name)
            if not isinstance(commits, dict):  # Check it's not an error response
                all_commits.extend(commits)
    
    code_survival = calculate_code_survival(all_commits)
    
    # Calculate review quality score
    total_reviews = aggregated_data.get('total_review_comments', 0) or 1  # Avoid division by zero
    approved_ratio = aggregated_data.get('total_approved_reviews', 0) / total_reviews
    
    # Calculate consistency score (placeholder - will be implemented in a separate function)
    consistency_score = 0.5  # Default value until we implement the full calculation
    
    # Calculate the final impact score
    impact_score = (
        weights['merged_prs'] * normalize_metric(aggregated_data.get('merged_prs', 0), MAX_PRS) +
        weights['code_quality'] * (code_survival / 100) +
        weights['project_impact'] * (aggregated_data.get('project_impact', 0) / 100) +
        weights['review_quality'] * approved_ratio +
        weights['consistency'] * consistency_score
    ) * 100

    return min(impact_score, 100)  # Convert to percentage and cap at 100

def calculate_project_impact(repo_data, is_original): # Add is_original parameter
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

def calculate_overall_project_impact(aggregated_data):
      # Calculate overall project impact based on individual repo impacts
    total_impact = 0
    for repo in aggregated_data['repos']:
        is_original = not repo.get('fork',False) #check if the repo is forked.
        repo['impact_score'] = calculate_project_impact(repo, is_original)  # Calculate individual repo impact and pass is_original
        total_impact += repo['impact_score']
    return total_impact