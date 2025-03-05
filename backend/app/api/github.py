# backend/app/api/github.py (ONLY GitHub API interaction)
from flask import Blueprint, request, jsonify
import requests
import os
from datetime import datetime, timedelta
import logging
from ..services import get_user_repos, get_user_pulls, get_user_issues, get_user_reviews, get_repo_commits, get_user_info

# Get module logger
logger = logging.getLogger(__name__)

github_bp = Blueprint('github', __name__)

@github_bp.route('/user-info/<username>', methods=['GET'])
def user_info(username):
    user_info = get_user_info(username)
    if isinstance(user_info, dict) and 'error' in user_info:
        logger.error(f"Failed to fetch user info for {username}: {user_info['error']}")
        return jsonify(user_info), 404
    return jsonify(user_info)

@github_bp.route('/user-repos/<username>', methods=['GET'])
def user_repos(username):
    repos = get_user_repos(username)
    if isinstance(repos, dict) and 'error' in repos:
        logger.error(f"Failed to fetch repos for {username}: {repos['error']}")
        return jsonify(repos), 500 if repos['error'].startswith("Error") else 404
    return jsonify(repos)

@github_bp.route('/repo-commits/<username>/<repo_name>', methods=['GET'])
def repo_commits(username, repo_name):
    commits = get_repo_commits(username, repo_name)
    if isinstance(commits, dict) and 'error' in commits:
        logger.error(f"Failed to fetch commits for {username}/{repo_name}: {commits['error']}")
        return jsonify(commits), 500 if commits['error'].startswith("Error") else 404
    return jsonify(commits)

@github_bp.route('/user-pulls/<username>', methods=['GET'])
def user_pulls(username):
    pulls = get_user_pulls(username)
    if isinstance(pulls, dict) and 'error' in pulls:
        logger.error(f"Failed to fetch pulls for {username}: {pulls['error']}")
        return jsonify(pulls), 500 if pulls['error'].startswith("Error") else 404
    return jsonify(pulls)

@github_bp.route('/user-issues/<username>', methods=['GET'])
def user_issues(username):
    issues = get_user_issues(username)
    if isinstance(issues, dict) and 'error' in issues:
        logger.error(f"Failed to fetch issues for {username}: {issues['error']}")
        return jsonify(issues), 500 if issues['error'].startswith("Error") else 404
    return jsonify(issues)

@github_bp.route('/user-reviews/<username>', methods=['GET'])
def user_reviews(username):
    reviews = get_user_reviews(username)
    if isinstance(reviews, dict) and 'error' in reviews:
        logger.error(f"Failed to fetch reviews for {username}: {reviews['error']}")
        return jsonify(reviews), 500 if reviews['error'].startswith("Error") else 404
    return jsonify(reviews)