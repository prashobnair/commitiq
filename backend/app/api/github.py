from flask import Blueprint, request, jsonify
import requests
import os
from datetime import datetime, timedelta

# Remove the circular import
# from ..services import aggregate_user_data, calculate_impact_score, calculate_overall_project_impact

github_bp = Blueprint('github', __name__)

@github_bp.route('/user-info/<username>', methods=['GET'])
def get_user_info(username):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    url = f'https://api.github.com/users/{username}'
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'User not found or API error'}), response.status_code

@github_bp.route('/user-repos/<username>', methods=['GET'])
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
        return jsonify(all_repos)
    else:
        return jsonify({'error': 'Could not fetch repositories'}), response.status_code

@github_bp.route('/repo-commits/<username>/<repo_name>', methods=['GET'])
def get_repo_commits(username, repo_name):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&since={two_years_ago}&per_page=100'
    response = requests.get(url, headers=headers)

    all_commits = []
    while 'next' in response.links.keys():
        response = requests.get(response.links['next']['url'], headers=headers)
        all_commits.extend(response.json())
    all_commits.extend(response.json())


    if response.status_code == 200:
       return jsonify(all_commits)
    else:
      return jsonify({'error': 'Could not fetch commits'}), response.status_code

@github_bp.route('/user-pulls/<username>', methods=['GET'])
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
        return jsonify(processed_pulls)
    else:
        return jsonify({'error': 'Could not fetch pull requests'}), response.status_code


@github_bp.route('/user-issues/<username>', methods=['GET'])
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

        return jsonify(processed_issues)
    else:
        return jsonify({'error': 'Could not fetch issues'}), response.status_code

@github_bp.route('/user-reviews/<username>', methods=['GET'])
def get_user_reviews(username):
    headers = {
        'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
    }
    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Step 1: Get all PRs in the time frame (not authored by the user)
    url = f'https://api.github.com/search/issues?q=is:pr+created:>={two_years_ago}&per_page=100' # Increased page size
    response = requests.get(url, headers=headers)
    all_pulls = []

    while 'next' in response.links.keys():
          response = requests.get(response.links['next']['url'], headers=headers)
          all_pulls.extend(response.json()['items'])
    all_pulls.extend(response.json()['items'])


    review_data = []

    # Step 2: Iterate through PRs and check for comments by the target user
    for pull in all_pulls:
        if pull['user']['login'] != username:  # Exclude PRs authored by the target user
            comments_url = pull['comments_url']
            comments_response = requests.get(comments_url, headers=headers)
            if comments_response.status_code == 200:
                comments = comments_response.json()
                for comment in comments:
                    if comment['user']['login'] == username:
                        review_data.append({
                            'pr_id': pull['id'],
                            'pr_title': pull['title'],
                            'comment_id': comment['id'],
                            'comment_body': comment['body'],
                            'comment_created_at': comment['created_at'],
                            'pr_url': pull['html_url'],
                            'repo_url': pull['repository_url']
                        })

    return jsonify(review_data)

@github_bp.route('/analyze/<username>', methods=['GET'])
def analyze_user(username):
    """
    Analyze a GitHub user's contributions and calculate impact scores.
    """
    # Import here to avoid circular imports
    from ..services import aggregate_user_data, calculate_impact_score, calculate_overall_project_impact
    
    try:
        # Get aggregated user data
        aggregated_data = aggregate_user_data(username)
        
        # Check if there was an error
        if isinstance(aggregated_data, tuple) and isinstance(aggregated_data[0], dict) and 'error' in aggregated_data[0]:
            return jsonify(aggregated_data[0]), aggregated_data[1]
        
        # Calculate impact scores
        impact_score = calculate_impact_score(aggregated_data)
        
        # Update project_impact in aggregated_data
        aggregated_data['project_impact'] = calculate_overall_project_impact(aggregated_data)
        
        # Structure the response to match what the frontend expects
        result = {
            'impact_score': impact_score,
            'analysis': aggregated_data
        }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500