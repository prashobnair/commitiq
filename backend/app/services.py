import requests
from datetime import datetime, timedelta
import os
from flask import jsonify
import time
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import logging

# --- Existing API functions (get_user_pulls, get_user_issues, get_user_reviews) remain unchanged ---
# ... (paste your existing get_user_pulls, get_user_issues, get_user_reviews here) ...
def get_user_pulls(username):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/search/issues?q=is:pr+author:{username}+created:>={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)

    all_pulls = []
    while 'next' in response.links.keys():
        response = requests.get(response.links['next']['url'], headers=headers)
        all_pulls.extend(response.json()['items'])
    all_pulls.extend(response.json()['items'])

    if response.status_code == 200:
        # Further processing to extract relevant PR data (e.g., merged status)
        processed_pulls = []
        for pull in all_pulls:
            processed_pulls.append({
                'id': pull['id'],
                'title': pull['title'],
                'created_at': pull['created_at'],
                'closed_at': pull['closed_at'],
                'merged': pull.get('pull_request', {}).get('merged_at') is not None,  # Check if merged
                'url': pull['html_url'],
                'repo_url': pull['repository_url'] # Get repo URL
            })
        return processed_pulls
    else:
        return {'error': 'Could not fetch pull requests'}, response.status_code


def get_user_issues(username):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/search/issues?q=is:issue+author:{username}+created:>={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)

    all_issues = []
    while 'next' in response.links.keys():
        response = requests.get(response.links['next']['url'], headers=headers)
        all_issues.extend(response.json()['items'])
    all_issues.extend(response.json()['items'])

    if response.status_code == 200:
        #Further processing of issues
        processed_issues = []
        for issue in all_issues:
            processed_issues.append({
                'id': issue['id'],
                'title': issue['title'],
                'created_at': issue['created_at'],
                'closed_at': issue['closed_at'],
                'state': issue['state'], # Open or closed
                'url': issue['html_url'],
                'repo_url': issue['repository_url'] #Get repo URL
            })

        return processed_issues
    else:
        return {'error': 'Could not fetch issues'}, response.status_code

#retry decorator
@retry(
  stop=stop_after_attempt(3),  # Stop after 3 attempts
  wait=wait_fixed(2),        # Wait 2 seconds between retries
  retry=retry_if_exception_type((ConnectionError, Timeout, RequestException)) #Retry only for these
  )
def get_user_reviews(username):
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

def get_user_repos(username):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/users/{username}/repos?since={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)

    all_repos = []
    while 'next' in response.links.keys():
          response = requests.get(response.links['next']['url'], headers=headers)
          all_repos.extend(response.json())
    all_repos.extend(response.json())

    if response.status_code == 200:
        return all_repos
    else:
        return {'error': 'Could not fetch repositories'}, response.status_code
def get_repo_commits(username, repo_name):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        all_commits = []
        while 'next' in response.links.keys():
            response = requests.get(response.links['next']['url'], headers=headers)
            if response.status_code == 200:
               all_commits.extend(response.json())
            else:
               return {'error': f'Could not fetch commits for {repo_name}'}, response.status_code
        all_commits.extend(response.json())
        return all_commits
    else:
        # Handle the 409 Conflict (likely empty repo) gracefully.  Return empty commit in this case.
        if response.status_code == 409:
            return []
        else:
          return {'error': f'Could not fetch commits for {repo_name}'}, response.status_code
        
def aggregate_user_data(username):
        try:
            # Fetch data using the API functions (adapt to use Flask's `make_response` if needed)
            pulls = get_user_pulls(username)
            if isinstance(pulls, tuple) and 'error' in pulls[0]:
                return {'error': f"Error fetching pulls: {pulls[0]['error']}"}

            issues = get_user_issues(username)
            if isinstance(issues, tuple) and 'error' in issues[0]:
                return {'error': f"Error fetching issues: {issues[0]['error']}"}

            reviews = get_user_reviews(username)
            if isinstance(reviews, dict) and 'error' in reviews: #Added check for dict
                return {'error': f"Error fetching reviews: {reviews['error']}"}
            repos = get_user_repos(username)
            if isinstance(repos, tuple) and 'error' in repos[0]:
                return {'error': f"Error fetching repos: {repos[0]['error']}"}
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
                'project_impact': 0 # Initialize project impact score
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

                # Add 'fork' and 'created_at' here!
                repo_data = {
                    'name': repo_name,
                    'url': repo['html_url'],
                    'stars': repo['stargazers_count'],
                    'forks': repo['forks_count'],
                    'num_contributors': num_contributors,
                    'commit_frequency': calculate_commit_frequency(commits),
                    'last_updated': repo['updated_at'],
                    'created_at': repo['created_at'],  # <--- ADD THIS
                    'num_commits': num_commits,
                    'original': not repo['fork'],      # <--- ADD THIS.  True if original, False if forked.
                    'fork': repo['fork']  # Add the 'fork' key here.
                }
                aggregated_data['repos'].append(repo_data)

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

def calculate_commit_frequency(commits):
    #Helper function to implement commit frequency calculation logic
    if not commits:
        return 0
    try:
      commit_dates = [datetime.strptime(commit['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ') for commit in commits]
      time_span = max(commit_dates) - min(commit_dates)
      days = time_span.days + (time_span.seconds / (24 * 60 * 60))  # Add fractional days
      return len(commits) / days if days > 0 else len(commits)
    except:
      return 0

def calculate_impact_score(aggregated_data):
    """
    Calculates the Impact Score based on the aggregated data.
    """
    merged_prs_weight = 0.30
    code_commits_weight = 0.25  # You'll need to calculate total commits
    project_impact_weight = 0.20
    code_reviews_weight = 0.15
    issues_weight = 0.10


    impact_score = (
        (aggregated_data['merged_prs'] * merged_prs_weight) +
        (aggregated_data['total_commits'] * code_commits_weight) +  # Use total_commits
        (aggregated_data['project_impact'] * project_impact_weight) + # Calculate the project impact before this.
        (aggregated_data['code_reviews'] * code_reviews_weight) +
        (aggregated_data['issues_resolved'] * issues_weight) # use issues_resolved
    )
    return impact_score

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
    total_impact = 0
    for repo in aggregated_data['repos']:
        is_original = not repo.get('fork', False)  # Use .get() with default False
        repo['impact_score'] = calculate_project_impact(repo, is_original)
        total_impact += repo['impact_score']
    return total_impact