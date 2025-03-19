import logging
import math
import numpy as np
from datetime import datetime, timedelta
from .github_api import github_api
from .cache_service import cache_response

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
                    logger.error(f"Error in GitHub data: {github_data['error']}")
                    return {'error': github_data['error']}
            else:
                logger.error(f"GitHub data is not a dictionary, it's a {type(github_data)}")
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
            logger.info(f"User data exists: {user_data is not None}")
            if user_data is None:
                logger.error(f"User data is None. GitHub data: {github_data}")
                return {'error': f'User not found or GraphQL response format incorrect'}
                
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
            
            # Calculate consistency score
            contribution_days = []
            weeks = user_data.get('contributionsCollection', {}).get('contributionCalendar', {}).get('weeks', [])
            for week in weeks:
                for day in week.get('contributionDays', []):
                    contribution_days.append(day.get('contributionCount', 0))
            
            # Convert to numpy array for calculations
            contribution_days_array = np.array(contribution_days)
            active_days = np.sum(contribution_days_array > 0)
            total_days = len(contribution_days)
            
            # Calculate activity consistency (days active / total days)
            activity_ratio = active_days / total_days if total_days > 0 else 0
            
            # Calculate variance in contribution amounts (lower is more consistent)
            nonzero_contribs = contribution_days_array[contribution_days_array > 0]
            contrib_variance = np.var(nonzero_contribs) / (np.mean(nonzero_contribs) + 0.01) if len(nonzero_contribs) > 0 else 0
            contrib_variance_factor = max(0, 1 - min(contrib_variance / 10, 1))  # Normalize and invert
            
            # Calculate streaks (consecutive days with contributions)
            streaks = []
            current_streak = 0
            
            for contribs in contribution_days:
                if contribs > 0:
                    current_streak += 1
                else:
                    if current_streak > 0:
                        streaks.append(current_streak)
                    current_streak = 0
            
            if current_streak > 0:
                streaks.append(current_streak)
            
            max_streak = max(streaks) if streaks else 0
            avg_streak = np.mean(streaks) if streaks else 0
            
            # Calculate weighted consistency score
            consistency_score = (
                0.4 * activity_ratio +
                0.3 * min(max_streak / 14, 1) +  # Cap max streak factor at 14 days
                0.2 * min(avg_streak / 5, 1) +   # Cap avg streak factor at 5 days
                0.1 * contrib_variance_factor
            )
            
            result['contributions']['consistency'] = consistency_score
            
            # Get weighted repository metrics
            repos = user_data.get('repositories', {}).get('nodes', [])
            repo_impacts = []
            
            # Calculate top languages used by the developer
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
                
                # Calculate PR acceptance rate
                merged_prs = repo.get('mergedPullRequests', {}).get('totalCount', 0)
                closed_prs = repo.get('closedPullRequests', {}).get('totalCount', 0)
                pr_acceptance = merged_prs / (merged_prs + closed_prs) if (merged_prs + closed_prs) > 0 else 0
                
                # Calculate technical impact
                technical_impact = (
                    TECHNICAL_IMPACT_WEIGHTS['pr_acceptance'] * pr_acceptance +
                    TECHNICAL_IMPACT_WEIGHTS['review_activity'] * collab_factor
                ) * math.log1p(stars + 1) * 0.01
                
                # Calculate ecosystem impact
                ecosystem_impact = math.log1p(forks + 1) * contribution_ratio ** CONTRIBUTION_RATIO_EXPONENT * 0.005
                
                # Calculate weighted repository impact
                repo_impact = (
                    REPO_IMPACT_WEIGHTS['technical'] * technical_impact +
                    REPO_IMPACT_WEIGHTS['ecosystem'] * ecosystem_impact
                )
                
                repo_impacts.append(repo_impact)
                
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
                
                # Add to top repositories if it has impact
                if repo_impact > 0:
                    # Handle case where primaryLanguage is None
                    primary_language_name = 'Unknown'
                    if repo.get('primaryLanguage') is not None:
                        primary_language_name = repo.get('primaryLanguage', {}).get('name', 'Unknown')
                    
                    result['contributions']['top_repositories'].append({
                        'name': repo.get('name', ''),
                        'url': f"https://github.com/{username}/{repo.get('name', '')}",
                        'stars': stars,
                        'forks': forks,
                        'primaryLanguage': primary_language_name,
                        'contributionRatio': round(contribution_ratio * 100),
                        'impactScore': round(repo_impact * 5000)  # Scale for readability
                    })
            
            # Sort and limit top repositories
            result['contributions']['top_repositories'] = sorted(
                result['contributions']['top_repositories'],
                key=lambda x: x['impactScore'],
                reverse=True
            )[:5]  # Limit to top 5
            
            # Calculate top languages (normalized)
            # Filter out blacklisted languages
            filtered_languages = {lang: weight for lang, weight in language_usage.items() if lang not in LANGUAGE_BLACKLIST}
            
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
            
            # Add top languages to contributions - convert to format expected by frontend
            result['contributions']['top_languages'] = [
                {'language': lang['name'], 'percentage': lang['weight']} 
                for lang in top_languages
            ]
            
            # Calculate overall repository impact
            result['contributions']['repos_impact'] = np.mean(repo_impacts) if repo_impacts else 0
            
            return result
            
        except Exception as e:
            logger.exception(f"Error aggregating user data: {str(e)}")
            return {'error': f"Failed to process GitHub data: {str(e)}"}
    
    @staticmethod
    def calculate_impact_score(data):
        """
        Calculate final impact score using percentile-based normalization.
        
        Args:
            data (dict): Aggregated GitHub metrics
            
        Returns:
            float: Overall impact score between 0 and 100
        """
        if not data or 'error' in data:
            return 0
            
        try:
            contributions = data.get('contributions', {})
            
            # Normalize metrics
            pulls = AnalysisService.percentile_normalize(
                contributions.get('pulls', 0),
                *NORMALIZATION_THRESHOLDS['pulls']
            )
            commits = AnalysisService.percentile_normalize(
                contributions.get('commits', 0),
                *NORMALIZATION_THRESHOLDS['commits']
            )
            reviews = AnalysisService.percentile_normalize(
                contributions.get('reviews', 0),
                *NORMALIZATION_THRESHOLDS['reviews']
            )
            issues = AnalysisService.percentile_normalize(
                contributions.get('issues', 0),
                *NORMALIZATION_THRESHOLDS['issues']
            )
            repos_impact = AnalysisService.percentile_normalize(
                contributions.get('repos_impact', 0),
                *NORMALIZATION_THRESHOLDS['repos_impact']
            )
            consistency = AnalysisService.percentile_normalize(
                contributions.get('consistency', 0),
                *NORMALIZATION_THRESHOLDS['consistency']
            )
            
            # Calculate weighted score
            impact_score = (
                IMPACT_SCORE_WEIGHTS['pulls'] * pulls +
                IMPACT_SCORE_WEIGHTS['commits'] * commits +
                IMPACT_SCORE_WEIGHTS['reviews'] * reviews +
                IMPACT_SCORE_WEIGHTS['issues'] * issues +
                IMPACT_SCORE_WEIGHTS['repos_impact'] * repos_impact +
                IMPACT_SCORE_WEIGHTS['consistency'] * consistency
            )
            
            # Add the scores to the data for transparency
            data['scores'] = {
                'pulls': round(pulls),
                'commits': round(commits),
                'reviews': round(reviews),
                'issues': round(issues),
                'repos_impact': round(repos_impact),
                'consistency': round(consistency),
                'impact_score': round(impact_score)
            }
            
            return round(impact_score)
            
        except Exception as e:
            logger.exception(f"Error calculating impact score: {str(e)}")
            return 0

# Create a singleton instance
analysis_service = AnalysisService() 