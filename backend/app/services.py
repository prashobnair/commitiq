from flask import jsonify
import os
import requests
from datetime import datetime

def make_github_request(endpoint, headers=None):
    """
    Helper function to make GitHub API requests
    """
    if headers is None:
        headers = {
            'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
        }
    response = requests.get(endpoint, headers=headers)
    return response.json() if response.status_code == 200 else {'error': f'API error: {response.status_code}'}, response.status_code

def aggregate_user_data(username):
    """
    Aggregates data from multiple GitHub API endpoints for a given user.
    """
    try:
        # Base headers for GitHub API requests
        headers = {
            'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'
        }
        
        # Fetch data directly using requests instead of importing from github.py
        pulls_url = f'https://api.github.com/search/issues?q=author:{username}+type:pr'
        pulls_response = requests.get(pulls_url, headers=headers)
        pulls = pulls_response.json() if pulls_response.status_code == 200 else {'error': f'API error: {pulls_response.status_code}'}
        
        issues_url = f'https://api.github.com/search/issues?q=author:{username}+type:issue'
        issues_response = requests.get(issues_url, headers=headers)
        issues = issues_response.json() if issues_response.status_code == 200 else {'error': f'API error: {issues_response.status_code}'}
        
        reviews_url = f'https://api.github.com/search/issues?q=reviewed-by:{username}+type:pr'
        reviews_response = requests.get(reviews_url, headers=headers)
        reviews = reviews_response.json() if reviews_response.status_code == 200 else {'error': f'API error: {reviews_response.status_code}'}
        
        repos_url = f'https://api.github.com/users/{username}/repos'
        repos_response = requests.get(repos_url, headers=headers)
        repos = repos_response.json() if repos_response.status_code == 200 else {'error': f'API error: {repos_response.status_code}'}

        # Error Handling
        if isinstance(pulls, dict) and 'error' in pulls:
            return {'error': f"Error fetching pulls: {pulls['error']}"}, 500
        if isinstance(issues, dict) and 'error' in issues:
              return {'error': f"Error fetching issues: {issues['error']}"}, 500
        if isinstance(reviews, dict) and 'error' in reviews:
              return {'error': f"Error fetching reviews: {reviews['error']}"}, 500
        if isinstance(repos, dict) and 'error' in repos:
            return {'error': f"Error fetching repos: {repos['error']}"}, 500

        # Aggregate data
        num_merged_prs = sum(1 for pull in pulls['items'] if pull['state'] == 'closed')
        num_issues_created = len(issues['items']) #Just count all issues
        num_issues_resolved =  sum(1 for issue in issues['items'] if issue['state'] == 'closed')# Count all closed ones
        num_code_reviews = len(reviews['items'])

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

         # Aggregate commit counts and other repo-level metrics
        for repo in repos:
                repo_name = repo['name']
                commits_url = f'https://api.github.com/repos/{username}/{repo_name}/commits'
                commits_response = requests.get(commits_url, headers=headers)
                commits = commits_response.json() if commits_response.status_code == 200 else {'error': f'API error: {commits_response.status_code}'}
                num_commits = len(commits)
                aggregated_data['total_commits'] += num_commits

                repo_data = {
                'name': repo_name,
                'url': repo['html_url'],
                'stars': repo['stargazers_count'],
                'forks': repo['forks_count'],
                'num_contributors': len(requests.get(repo['contributors_url'], headers=headers).json()),
                'commit_frequency': calculate_commit_frequency(commits),  # Implement this helper function
                'last_updated': repo['updated_at'],
                'num_commits': num_commits # Add commit count for this repo

                 }
                aggregated_data['repos'].append(repo_data)

        return aggregated_data

    except Exception as e:
        return {'error': f"An unexpected error occurred: {str(e)}"}, 500

def calculate_commit_frequency(commits):
    #Helper function to implement commit frequency calculation logic
    if not commits:
        return 0

    # Extract commit dates and convert them to datetime objects
    commit_dates = [datetime.strptime(commit['commit']['author']['date'], '%Y-%m-%dT%H:%M:%SZ') for commit in commits]

    # Calculate the time difference between the first and last commit
    time_span = max(commit_dates) - min(commit_dates)

    # Calculate the number of days
    days = time_span.days + (time_span.seconds / (24 * 60 * 60))  # Add fractional days

    if days == 0:
        return len(commits) # If all commits are on the same day, return the commit count
    else:
        return len(commits) / days # commits per day



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

def calculate_project_impact(repo_data):
     # Calculate a project impact score for a single repo
     #Simple example:
     return (repo_data['stars'] * 0.5) + (repo_data['forks'] * 0.3) + (repo_data['num_contributors'] * 0.2)

def calculate_overall_project_impact(aggregated_data):
      # Calculate overall project impact based on individual repo impacts
    total_impact = 0
    for repo in aggregated_data['repos']:
        repo['impact_score'] = calculate_project_impact(repo)  # Calculate individual repo impact
        total_impact += repo['impact_score']
    return total_impact