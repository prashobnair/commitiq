import logging
import math
import numpy as np
from datetime import datetime, timedelta
from .github_api import github_api
from .cache_service import cache_response, cache_service

# Get logger for this module
logger = logging.getLogger(__name__)

# --- Constants ---
TIME_WINDOW_DAYS = 365  # Analyze 1 year of history

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

# Languages to exclude from top languages calculation
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


class AnalysisService:
    """
    Service for calculating GitHub user impact scores and analytics.
    """
    
    @staticmethod
    def normalize_value(value, min_threshold, max_threshold):
        """
        Normalize a value between 0 and 1 using min/max thresholds.
        
        Args:
            value (float): Value to normalize
            min_threshold (float): Minimum threshold (maps to 0)
            max_threshold (float): Maximum threshold (maps to 1)
            
        Returns:
            float: Normalized value between 0 and 1
        """
        if value <= min_threshold:
            return 0.0
        elif value >= max_threshold:
            return 1.0
        else:
            # Linear normalization
            return (value - min_threshold) / (max_threshold - min_threshold)
    
    @staticmethod
    def percentile_normalize(value, lower_bound, upper_bound):
        """
        Normalize a value to a percentage score (0-100) using min/max bounds.
        
        Args:
            value (float): Value to normalize
            lower_bound (float): Lower bound for normalization (maps to 0)
            upper_bound (float): Upper bound for normalization (maps to 100)
            
        Returns:
            float: Normalized value as a percentage (0-100)
        """
        if value <= lower_bound:
            return 0
        if value >= upper_bound:
            return 100
        return ((value - lower_bound) / (upper_bound - lower_bound)) * 100
    
    @staticmethod
    @cache_response(ttl=3600)
    def fetch_all_data(username):
        """
        Fetch all necessary data for a GitHub user using a single GraphQL query.
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict: All GitHub data for the user
        """
        logger.info(f"Fetching all data for user: {username}")
        
        # Use the optimized single query approach
        return github_api.fetch_all_data_with_single_query(username)
    
    @staticmethod
    @cache_response(ttl=3600)
    def aggregate_user_data(username, github_data):
        """
        Aggregate GitHub user data into meaningful metrics.
        
        Args:
            username (str): GitHub username
            github_data (dict): Raw GitHub data from single query
            
        Returns:
            dict: Aggregated analytics data
        """
        try:
            # Print debug information
            logger.info(f"Aggregating data for user: {username}")
            logger.info(f"GitHub data structure: {type(github_data)}")
            
            if isinstance(github_data, dict):
                logger.info(f"GitHub data keys: {list(github_data.keys())}")
                if 'error' in github_data:
                    logger.error(f"Error in GitHub data: {github_data['error']} for username: {username}")
                    return {'error': github_data['error']}
            else:
                logger.error(f"GitHub data is not a dictionary, it's a {type(github_data)} for username: {username}")
                return {'error': 'Invalid GitHub API response format'}
                
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
            
            # Create temporary storage for detailed metrics
            temp_metrics = {
                'repositories': [],  # Detailed repository metrics
                'repos_impact': {},  # Repository impact calculations
                'consistency': {}    # Consistency metrics
            }

            # Extract user information
            user_data = github_data.get('user', {})
            
            # More detailed debugging
            logger.info(f"User data exists: {user_data is not None} for username: {username}")
            if user_data is None:
                logger.error(f"User data is None for username: {username}. GitHub data structure: {list(github_data.keys()) if isinstance(github_data, dict) else type(github_data)}")
                return {'error': 'No user found for username: ' + username}
                
            if not user_data:
                logger.error(f"User data is empty for username: {username}")
                return {'error': 'Unable to analyze profile at this time'}
            
            # Basic user info - always store this even if user has zero activity
            basic_keys = ['name', 'email', 'url', 'company', 'location', 'bio', 'avatarUrl']
            missing_keys = [k for k in basic_keys if k not in user_data]
            if missing_keys:
                logger.warning(f"Missing basic user data keys: {missing_keys} for username: {username}")
            
            result.update({k: user_data.get(k) for k in basic_keys})
            
            # Check for missing follower/following data
            if user_data.get('followers') is None:
                logger.warning(f"Missing followers data for username: {username}")
            if user_data.get('following') is None:
                logger.warning(f"Missing following data for username: {username}")
                
            result['followers'] = user_data.get('followers', {}).get('totalCount', 0) if user_data.get('followers') is not None else 0
            result['following'] = user_data.get('following', {}).get('totalCount', 0) if user_data.get('following') is not None else 0
            
            # Get contribution metrics
            contributions_collection = user_data.get('contributionsCollection', {})
            if not contributions_collection:
                logger.warning(f"Empty contributions collection for username: {username}")
            
            result['contributions']['pulls'] = contributions_collection.get('totalPullRequestContributions', 0)
            result['contributions']['commits'] = contributions_collection.get('totalCommitContributions', 0)
            result['contributions']['reviews'] = contributions_collection.get('totalPullRequestReviewContributions', 0)
            result['contributions']['issues'] = contributions_collection.get('totalIssueContributions', 0)
            
            logger.debug(f"Contribution metrics for {username} - Pulls: {result['contributions']['pulls']}, Commits: {result['contributions']['commits']}, Reviews: {result['contributions']['reviews']}, Issues: {result['contributions']['issues']}")
            
            # Calculate consistency score
            contribution_days = []
            weeks = contributions_collection.get('contributionCalendar', {}).get('weeks', [])
            
            if not weeks:
                logger.warning(f"No contribution calendar weeks data for username: {username}")
                
            # Calculate active weeks (weeks with at least one contribution)
            active_weeks = sum(1 for week in weeks if any(
                day.get('contributionCount', 0) > 0 
                for day in week.get('contributionDays', [])
            ))
            total_weeks = len(weeks)
            
            # Original consistency score calculation: active_weeks / total_weeks
            consistency_score = active_weeks / total_weeks if total_weeks > 0 else 0
            logger.debug(f"Consistency score for {username}: {consistency_score} ({active_weeks}/{total_weeks} active weeks)")
            
            result['contributions']['consistency'] = consistency_score
            
            # Get weighted repository metrics
            repos = user_data.get('repositories', {}).get('nodes', [])
            if not repos:
                logger.warning(f"No repository data for username: {username}")
                
            repo_impacts = []
            
            # Calculate top languages used by the developer
            language_usage = {}
            
            for repo in repos:
                if repo.get('isPrivate', False):
                    continue
                
                repo_name = repo.get('name', 'unnamed-repo')
                
                try:
                    # Get repository metrics
                    stars = repo.get('stargazerCount', 0)
                    forks = repo.get('forkCount', 0)
                    
                    # Check for missing data
                    if repo.get('collaborators') is None:
                        logger.warning(f"Missing collaborators data for repo {repo_name} of user {username}")
                        
                    # Get collaborators
                    collaborators = repo.get('collaborators', {}).get('totalCount', 0) if repo.get('collaborators') is not None else 0
                    collab_factor = min(COLLAB_FACTOR['base'] + math.log(collaborators + 1) * COLLAB_FACTOR['log_factor'], 
                                       COLLAB_FACTOR['max_value'])
                    
                    # Get developer's relative commits in this repo
                    developer_commits = 0
                    contrib_repos = user_data.get('contributionsCollection', {}).get('commitContributionsByRepository', [])
                    for contrib in contrib_repos:
                        if contrib.get('repository', {}).get('name') == repo_name:
                            developer_commits = contrib.get('contributions', {}).get('totalCount', 0)
                    
                    # Check for missing data
                    if repo.get('defaultBranchRef') is None:
                        logger.warning(f"Missing defaultBranchRef for repo {repo_name} of user {username}")
                        
                    total_commits = repo.get('defaultBranchRef', {}).get('target', {}).get('history', {}).get('totalCount', 0) if repo.get('defaultBranchRef', {}) is not None else 0
                    
                    contribution_ratio = developer_commits / total_commits if total_commits > 0 else 0
                    
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
                    
                    # Calculate final repository impact
                    repo_impact = (
                        REPO_IMPACT_WEIGHTS['technical'] * repo_tech_impact +
                        REPO_IMPACT_WEIGHTS['ecosystem'] * repo_eco_impact
                    )
                    
                    repo_impacts.append(repo_impact)
                    
                    # Store repository sub-metrics for debugging and reference
                    repo_metrics = {
                        'name': repo_name,
                        'stars': stars,
                        'forks': forks,
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
                        'repo_impact': repo_impact
                    }
                    
                    temp_metrics['repositories'].append(repo_metrics)
                    
                    # Track repository languages
                    langs = repo.get('languages', {}).get('edges', [])
                    total_size = sum(lang.get('size', 0) for lang in langs)
                    
                    for lang in langs:
                        lang_name = lang.get('node', {}).get('name')
                        if lang_name:
                            # Skip blacklisted languages
                            if lang_name in LANGUAGE_BLACKLIST:
                                continue
                                
                            lang_size = lang.get('size', 0)
                            lang_ratio = lang_size / total_size if total_size > 0 else 0
                            weighted_contribution = lang_ratio * contribution_ratio * repo_impact
                            
                            if lang_name in language_usage:
                                language_usage[lang_name] += weighted_contribution
                            else:
                                language_usage[lang_name] = weighted_contribution
                except Exception as repo_error:
                    # Log error but continue processing other repos
                    logger.error(f"Error processing repo {repo_name} for user {username}: {str(repo_error)}")
                    continue
            
            # Sort repositories by repo_impact in descending order
            sorted_repos = sorted(temp_metrics['repositories'], key=lambda x: x['repo_impact'], reverse=True)
            # Take top 4 (or fewer if less than 4 exist)
            top_repos = sorted_repos[:4]
            
            if not top_repos and repos:
                logger.warning(f"No top repositories calculated for username: {username} despite having {len(repos)} repos")
            
            # Format repositories for the response
            result['contributions']['top_repositories'] = []
            for repo in top_repos:
                try:
                    # Find the original repository data to get primary language
                    original_repo = next((r for r in repos if r.get('name') == repo['name']), {})
                    
                    # Get primary language
                    primary_language_name = 'N/A'
                    primary_language = original_repo.get('primaryLanguage', {})
                    if primary_language and primary_language is not None:
                        primary_language_name = primary_language.get('name', 'N/A')
                    
                    # Format the contribution ratio as a percentage (0-100%)
                    contribution_ratio_pct = round(repo['contribution_ratio'] * 100, 1)
                    
                    # Set the impact score without scaling - use the raw value
                    impact_score = repo['repo_impact']
                    
                    # Get last commit date if available
                    last_commit_date = 'N/A'
                    if original_repo.get('defaultBranchRef') is not None:
                        target = original_repo.get('defaultBranchRef', {}).get('target', {})
                        if 'lastCommit' in target and 'nodes' in target['lastCommit'] and len(target['lastCommit']['nodes']) > 0:
                            last_commit_date = target['lastCommit']['nodes'][0].get('committedDate', 'N/A')
                    
                    # Get collaborators count
                    collaborators = original_repo.get('collaborators', {}).get('totalCount', 0) if original_repo.get('collaborators') is not None else 0
                    
                    result['contributions']['top_repositories'].append({
                        'name': repo['name'],
                        'url': f"https://github.com/{username}/{repo['name']}",
                        'stars': repo['stars'],
                        'forks': repo['forks'],
                        'primaryLanguage': primary_language_name,
                        'contributionRatio': contribution_ratio_pct,
                        'impactScore': impact_score,  # Use raw value as in the original
                        'last_commit_date': last_commit_date,
                        'collaborators': collaborators,
                        'commit_frequency': f"{repo['developer_commits']} / {repo['total_commits']}"
                    })
                except Exception as repo_format_error:
                    # Log error but continue processing other repos
                    logger.error(f"Error formatting repo {repo.get('name', 'unknown')} for user {username}: {str(repo_format_error)}")
                    continue
            
            # Sort and limit top repositories
            result['contributions']['top_repositories'] = sorted(
                result['contributions']['top_repositories'],
                key=lambda x: x['impactScore'],
                reverse=True
            )
            
            # Calculate top languages (normalized)
            # Filter out blacklisted languages
            filtered_languages = {lang: weight for lang, weight in language_usage.items() if lang not in LANGUAGE_BLACKLIST}
            
            if not filtered_languages and language_usage:
                logger.warning(f"All languages were filtered out for user {username}. Original languages: {list(language_usage.keys())}")
            
            # Sort and limit to top 4 languages
            top_languages = sorted(
                [{'name': lang, 'weight': weight} for lang, weight in filtered_languages.items()],
                key=lambda x: x['weight'],
                reverse=True
            )[:4]  # Limit to top 4
            
            # Normalize language weights to percentages
            total_weight = sum(lang['weight'] for lang in top_languages)
            if total_weight > 0:
                for lang in top_languages:
                    lang['weight'] = round(lang['weight'] / total_weight * 100)
            else:
                logger.warning(f"Total language weight is zero for username: {username}")
            
            # Filter out languages with 0% usage
            top_languages = [lang for lang in top_languages if lang['weight'] > 0]
            
            # Add top languages to contributions - convert to format expected by frontend
            result['contributions']['top_languages'] = [
                {'language': lang['name'], 'percentage': lang['weight']} 
                for lang in top_languages
            ]
            
            # Calculate overall repository impact
            result['contributions']['repos_impact'] = np.mean(repo_impacts) if repo_impacts else 0
            
            # Calculate the overall impact score as per original implementation
            # Only calculate if we have all necessary data
            if (all(key in result['contributions'] for key in ['pulls', 'commits', 'consistency', 'repos_impact'])):
                # Get individual component scores
                pulls_score = AnalysisService.percentile_normalize(
                    result['contributions']['pulls'],
                    *NORMALIZATION_THRESHOLDS['pulls']
                )
                commits_score = AnalysisService.percentile_normalize(
                    result['contributions']['commits'],
                    *NORMALIZATION_THRESHOLDS['commits']
                )
                reviews_score = AnalysisService.percentile_normalize(
                    result['contributions']['reviews'],
                    *NORMALIZATION_THRESHOLDS['reviews']
                )
                issues_score = AnalysisService.percentile_normalize(
                    result['contributions']['issues'],
                    *NORMALIZATION_THRESHOLDS['issues']
                )
                repos_impact_score = AnalysisService.percentile_normalize(
                    result['contributions']['repos_impact'],
                    *NORMALIZATION_THRESHOLDS['repos_impact']
                )
                # Consistency is treated differently - multiply by 100 directly
                consistency_score = result['contributions']['consistency'] * 100
                
                # Apply weights
                weights = {
                    'pulls': 0.35,
                    'commits': 0.30,
                    'reviews': 0.10,
                    'issues': 0.10,
                    'repos_impact': 0.10,
                    'consistency': 0.05
                }
                
                # Calculate the weighted average
                impact_score = (
                    weights['pulls'] * pulls_score +
                    weights['commits'] * commits_score +
                    weights['reviews'] * reviews_score +
                    weights['issues'] * issues_score +
                    weights['repos_impact'] * repos_impact_score +
                    weights['consistency'] * consistency_score
                )
                
                # Apply min/max bounds as in original implementation
                impact_score = min(max(impact_score, 0), 100)
                
                logger.debug(f"Calculated impact score components for {username} - Pulls: {pulls_score}, Commits: {commits_score}, Reviews: {reviews_score}, Issues: {issues_score}, Repos: {repos_impact_score}, Consistency: {consistency_score}")
                logger.info(f"Final impact score for {username}: {impact_score}")
                
                # Set the impact score in the result - don't round to get exact values
                result['impact_score'] = impact_score
            else:
                missing_keys = [key for key in ['pulls', 'commits', 'consistency', 'repos_impact'] if key not in result['contributions']]
                logger.warning(f"Missing required data for impact score calculation for username: {username}. Missing keys: {missing_keys}")
                result['impact_score'] = 0
                
            return result
            
        except Exception as e:
            logger.exception(f"Error aggregating user data for {username}: {str(e)}")
            return {'error': f"Failed to process GitHub data: {str(e)}"}
    
    @staticmethod
    def calculate_impact_score(data):
        """
        Get the impact score that was calculated during data aggregation.
        
        Args:
            data (dict): Aggregated GitHub metrics
            
        Returns:
            float: Overall impact score between 0 and 100
        """
        if not data or 'error' in data:
            return 0
            
        # If the impact score is already calculated in aggregate_user_data,
        # simply return it
        if 'impact_score' in data:
            return data['impact_score']
        
        # If not, return a default of 0
        return 0

    def cache_analysis_result(self, username, result, ttl=3600):
        """
        Cache the final analysis result for quick retrieval.
        
        This avoids recomputing the entire analysis for repeated lookups of the
        same username within the TTL period. The cache key is specific to the username
        and independent from the lower-level caching of GitHub API data and aggregation.
        
        Args:
            username (str): GitHub username
            result (dict): Complete analysis result with impact score
            ttl (int): Time-to-live for cache in seconds. Default 1 hour.
            
        Returns:
            bool: True if successfully cached
        """
        if not username or not result:
            return False
            
        try:
            # Create a cache key specific to this operation and username
            cache_key = f"analysis_result:{username}"
            
            # Store in cache
            cache_service.set(cache_key, result, ttl)
            logger.info(f"Cached complete analysis result for {username} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error caching analysis result for {username}: {str(e)}")
            return False
    
    def get_cached_analysis_result(self, username):
        """
        Retrieve a cached analysis result for a username if available.
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict|None: The cached analysis result or None if not found/expired
        """
        if not username:
            return None
            
        try:
            # Get from cache using the same key format as in cache_analysis_result
            cache_key = f"analysis_result:{username}"
            result = cache_service.get(cache_key)
            
            if result:
                logger.info(f"Retrieved cached analysis result for {username}")
            else:
                logger.debug(f"No cached analysis result found for {username}")
                
            return result
        except Exception as e:
            logger.error(f"Error retrieving cached analysis result for {username}: {str(e)}")
            return None

# Create a singleton instance
analysis_service = AnalysisService() 