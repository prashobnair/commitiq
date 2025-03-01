from .api.github import get_user_pulls, get_user_issues, get_user_reviews, get_user_repos, get_repo_commits
from flask import jsonify
import os
import requests
from datetime import datetime

def aggregate_user_data(username):
    """
    Aggregates data from multiple GitHub API endpoints for a given user.
    """
    try:
        # Fetch data using the API functions (adapt to use Flask's `make_response` if needed)
        pulls = get_user_pulls(username).get_json()
        issues = get_user_issues(username).get_json()
        reviews = get_user_reviews(username).get_json()
        repos = get_user_repos(username).get_json()

        # Error Handling
        if isinstance(pulls, tuple) and 'error' in pulls[0]:
            return {'error': f"Error fetching pulls: {pulls[0]['error']}"}, pulls[1]
        if isinstance(issues, tuple) and 'error' in issues[0]:
              return {'error': f"Error fetching issues: {issues[0]['error']}"}, issues[1]
        if isinstance(reviews, tuple) and 'error' in reviews[0]:
              return {'error': f"Error fetching reviews: {reviews[0]['error']}"}, reviews[1]
        if isinstance(repos, tuple) and 'error' in repos[0]:
            return {'error': f"Error fetching repos: {repos[0]['error']}"}, repos[1]


        # Aggregate data
        num_merged_prs = sum(1 for pull in pulls if pull['merged'])
        num_issues_created = len(issues) #Just count all issues
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

         # Aggregate commit counts and other repo-level metrics
        for repo in repos:
                repo_name = repo['name']
                commits = get_repo_commits(username, repo_name)
                if(not isinstance(commits, tuple)):
                    commits = commits.get_json()
                else:
                    return{'error': f"Error fetching commits: {commits[0]['error']}"}, commits[1]
                num_commits = len(commits)
                aggregated_data['total_commits'] += num_commits

                repo_data = {
                'name': repo_name,
                'url': repo['html_url'],
                'stars': repo['stargazers_count'],
                'forks': repo['forks_count'],
                'num_contributors': len(requests.get(repo['contributors_url'], headers={'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}).json()),
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