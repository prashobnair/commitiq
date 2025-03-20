import requests
import logging
import asyncio
import aiohttp
import os
import json
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects, RequestException

from .cache_service import cache_response

# Get logger for this module
logger = logging.getLogger(__name__)

# --- GitHub API Constants ---
GITHUB_API_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

class GitHubAPIService:
    """
    Service for interacting with GitHub API.
    Provides methods for making REST and GraphQL requests to GitHub API.
    """
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, Timeout, TooManyRedirects))
    )
    def make_github_request(endpoint, params=None):
        """
        Make a request to GitHub REST API with retry logic
        
        Args:
            endpoint (str): API endpoint (without base URL)
            params (dict): Query parameters
            
        Returns:
            dict: API response or error details
        """
        url = f"{GITHUB_API_URL}/{endpoint}"
        logger.debug(f"Making GitHub API request to: {url}")
        
        try:
            response = requests.get(
                url,
                headers=GITHUB_HEADERS,
                params=params,
                timeout=10
            )
            
            # Check for rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            if remaining < 10:
                reset_datetime = datetime.fromtimestamp(reset_time)
                logger.warning(f"GitHub API rate limit low: {remaining} remaining, resets at {reset_datetime} for endpoint {endpoint}")
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                reset_datetime = datetime.fromtimestamp(reset_time)
                now = datetime.now()
                wait_time = (reset_datetime - now).total_seconds() + 10  # Add buffer
                
                error_msg = f"GitHub API rate limit exceeded. Resets in {wait_time:.0f} seconds."
                logger.error(f"{error_msg} - Endpoint: {endpoint} - Params: {params}")
                return {"error": "Rate limit reached. Please try again later."}
            
            if response.status_code == 404:
                logger.warning(f"GitHub resource not found: {url} - Endpoint: {endpoint} - Params: {params}")
                return {"error": "Username not found"}
            
            # Log all non-2xx responses with more context
            if response.status_code < 200 or response.status_code >= 300:
                logger.error(f"GitHub API non-2xx response: {response.status_code} - URL: {url} - Response: {response.text[:500]}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"GitHub API HTTP error: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Unable to access profile data"}
        except (ConnectionError, Timeout) as e:
            logger.error(f"GitHub API connection error: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Connection issue. Please try again"}
        except Exception as e:
            logger.exception(f"Unexpected error in GitHub API request: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Unable to analyze profile at this time"}
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, Timeout, TooManyRedirects))
    )
    def make_graphql_request(query, variables=None):
        """
        Make a request to GitHub GraphQL API with retry logic
        
        Args:
            query (str): GraphQL query
            variables (dict): Query variables
            
        Returns:
            dict: API response or error details
        """
        if variables is None:
            variables = {}
            
        # Log a sanitized version of the query (first 200 chars)
        sanitized_query = query.replace('\n', ' ').replace('  ', ' ')[:200] + '...' if len(query) > 200 else query
        logger.debug(f"Making GitHub GraphQL request: {sanitized_query}")
        logger.debug(f"Variables: {variables}")
        
        try:
            response = requests.post(
                GITHUB_GRAPHQL_URL,
                headers=GITHUB_HEADERS,
                json={"query": query, "variables": variables},
                timeout=15  # Longer timeout for GraphQL
            )
            
            # Check for rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            
            if remaining < 10:
                reset_datetime = datetime.fromtimestamp(reset_time)
                logger.warning(f"GitHub GraphQL API rate limit low: {remaining} remaining, resets at {reset_datetime}")
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                reset_datetime = datetime.fromtimestamp(reset_time)
                now = datetime.now()
                wait_time = (reset_datetime - now).total_seconds() + 10  # Add buffer
                
                error_msg = f"GitHub GraphQL API rate limit exceeded. Resets in {wait_time:.0f} seconds."
                logger.error(f"{error_msg} - Variables: {variables}")
                return {"errors": [{"message": "Rate limit reached. Please try again later."}]}
            
            # Log all non-2xx responses
            if response.status_code < 200 or response.status_code >= 300:
                logger.error(f"GitHub GraphQL API non-2xx response: {response.status_code} - Response: {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            
            # Check for GraphQL errors
            if "errors" in data:
                error_msg = data["errors"][0]["message"]
                logger.error(f"GitHub GraphQL error: {error_msg} - Variables: {variables} - Query: {sanitized_query}")
                
                # Map common errors to user-friendly messages
                if "Could not resolve to a User" in error_msg:
                    logger.error(f"User not found in GitHub - Variables: {variables}")
                    data["errors"][0]["message"] = "Username not found"
                elif "API rate limit exceeded" in error_msg:
                    data["errors"][0]["message"] = "Rate limit reached. Please try again later"
                else:
                    data["errors"][0]["message"] = "Unable to analyze profile at this time"
                
                return data  # Return the modified error response
                
            return data
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"GitHub GraphQL API HTTP error: {str(e)} - Variables: {variables}")
            return {"errors": [{"message": "Unable to access profile data"}]}
        except (ConnectionError, Timeout) as e:
            logger.error(f"GitHub GraphQL API connection error: {str(e)} - Variables: {variables}")
            return {"errors": [{"message": "Connection issue. Please try again"}]}
        except Exception as e:
            logger.exception(f"Unexpected error in GitHub GraphQL API request: {str(e)} - Variables: {variables}")
            return {"errors": [{"message": "Unable to analyze profile at this time"}]}
    
    @staticmethod
    async def async_github_request(session, endpoint, params=None):
        """
        Make an async request to GitHub REST API
        
        Args:
            session (aiohttp.ClientSession): Async session
            endpoint (str): API endpoint (without base URL)
            params (dict): Query parameters
            
        Returns:
            dict: API response or error details
        """
        url = f"{GITHUB_API_URL}/{endpoint}"
        
        try:
            async with session.get(url, params=params) as response:
                # Check for rate limit
                remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                
                if remaining < 10:
                    reset_datetime = datetime.fromtimestamp(reset_time)
                    logger.warning(f"GitHub API rate limit low: {remaining} remaining, resets at {reset_datetime} - Endpoint: {endpoint}")
                
                # Handle rate limiting
                if response.status == 403 and 'rate limit exceeded' in await response.text():
                    reset_datetime = datetime.fromtimestamp(reset_time)
                    now = datetime.now()
                    wait_time = (reset_datetime - now).total_seconds() + 10  # Add buffer
                    
                    error_msg = f"GitHub API rate limit exceeded. Resets in {wait_time:.0f} seconds."
                    logger.error(f"{error_msg} - Endpoint: {endpoint} - Params: {params}")
                    return {"error": "Rate limit reached. Please try again later."}
                
                if response.status == 404:
                    logger.warning(f"GitHub resource not found: {url} - Endpoint: {endpoint} - Params: {params}")
                    return {"error": "Username not found"}
                
                # Log all non-2xx responses
                if response.status < 200 or response.status >= 300:
                    response_text = await response.text()
                    logger.error(f"GitHub API non-2xx response: {response.status} - URL: {url} - Response: {response_text[:500]}")
                
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"GitHub API HTTP error: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Unable to access profile data"}
        except aiohttp.ClientConnectionError as e:
            logger.error(f"GitHub API connection error: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Connection issue. Please try again"}
        except Exception as e:
            logger.exception(f"Unexpected error in async GitHub API request: {str(e)} - Endpoint: {endpoint} - Params: {params}")
            return {"error": "Unable to analyze profile at this time"}
    
    @staticmethod
    async def fetch_multiple_endpoints(endpoints, params_list=None):
        """
        Fetch multiple GitHub API endpoints in parallel
        
        Args:
            endpoints (list): List of API endpoints
            params_list (list): List of query parameters for each endpoint
            
        Returns:
            list: List of API responses
        """
        if params_list is None:
            params_list = [None] * len(endpoints)
        
        async with aiohttp.ClientSession(headers=GITHUB_HEADERS) as session:
            tasks = []
            for i, endpoint in enumerate(endpoints):
                params = params_list[i] if i < len(params_list) else None
                task = GitHubAPIService.async_github_request(session, endpoint, params)
                tasks.append(task)
            
            return await asyncio.gather(*tasks)
    
    @staticmethod
    @cache_response(ttl=3600)  # Cache for 1 hour
    def fetch_user_profile(username):
        """
        Fetch GitHub user profile information
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict: User profile data or error details
        """
        logger.info(f"Fetching user profile for: {username}")
        return GitHubAPIService.make_github_request(f"users/{username}")
    
    @staticmethod
    @cache_response(ttl=3600)  # Cache for 1 hour
    def fetch_user_repositories(username):
        """
        Fetch GitHub user repositories
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict: User repositories data or error details
        """
        logger.info(f"Fetching repositories for: {username}")
        
        # Use GraphQL for more efficient repository fetching
        query = """
        query($username: String!, $cursor: String) {
            user(login: $username) {
                repositories(first: 50, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
                    totalCount
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        name
                        description
                        url
                        isPrivate
                        isArchived
                        isFork
                        stargazerCount
                        forkCount
                        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                            totalCount
                            edges {
                                node {
                                    name
                                }
                                size
                            }
                        }
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history(first: 1) {
                                        totalCount
                                    }
                                }
                            }
                        }
                        createdAt
                        updatedAt
                        primaryLanguage {
                            name
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "username": username,
            "cursor": None
        }
        
        return GitHubAPIService.make_graphql_request(query, variables)
    
    @staticmethod
    @cache_response(ttl=3600)  # Cache for 1 hour
    def fetch_user_contributions(username):
        """
        Fetch GitHub user contributions
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict: User contributions data or error details
        """
        logger.info(f"Fetching contributions for: {username}")
        
        # Calculate date range for last year
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Format dates for GitHub API
        from_date = start_date.strftime("%Y-%m-%dT00:00:00")
        to_date = end_date.strftime("%Y-%m-%dT23:59:59")
        
        # Use GraphQL for more efficient contribution fetching
        query = """
        query($username: String!, $from: DateTime!, $to: DateTime!) {
            user(login: $username) {
                contributionsCollection(from: $from, to: $to) {
                    contributionCalendar {
                        totalContributions
                        weeks {
                            contributionDays {
                                date
                                contributionCount
                            }
                        }
                    }
                    totalIssueContributions
                    totalCommitContributions
                    totalPullRequestContributions
                    totalPullRequestReviewContributions
                    totalRepositoriesWithContributedCommits
                    totalRepositoriesWithContributedIssues
                    totalRepositoriesWithContributedPullRequests
                    totalRepositoriesWithContributedPullRequestReviews
                }
            }
        }
        """
        
        variables = {
            "username": username,
            "from": from_date,
            "to": to_date
        }
        
        return GitHubAPIService.make_graphql_request(query, variables)
    
    @staticmethod
    @cache_response(ttl=3600)  # Cache for 1 hour
    def fetch_all_data_with_single_query(username):
        """
        Fetch all GitHub data for a user using a single efficient GraphQL query.
        This uses the original optimized query approach from the services_backup_new.py file.
        
        Args:
            username (str): GitHub username
            
        Returns:
            dict: All data for the GitHub user in a single response
        """
        logger.info(f"Fetching all data with single query for user: {username}")
        
        # Calculate the date for the time window (365 days)
        since_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Define the comprehensive GraphQL query that gets everything we need in one call
        query = """
        query ($login: String!, $since: DateTime!) {
          user(login: $login) {
            name
            email
            location
            company
            bio
            avatarUrl
            url
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
                weeks {
                  contributionDays {
                    contributionCount
                  }
                }
              }
              commitContributionsByRepository(maxRepositories: 20) {
                repository {
                  name
                }
                contributions(first: 100) {
                  totalCount
                }
              }
            }
            repositories(first: 20, orderBy: {field: STARGAZERS, direction: DESC}) {
              totalCount
              nodes {
                name
                stargazerCount
                forkCount
                isPrivate
                homepageUrl
                collaborators(first: 1) {
                  totalCount
                }
                mergedPullRequests: pullRequests(states: MERGED) {
                    totalCount
                }
                closedPullRequests: pullRequests(states: CLOSED) {
                    totalCount
                }
                pullRequests(first: 10) {
                    totalCount
                    nodes {
                        reviews {
                            totalCount
                        }
                        comments {
                            totalCount
                        }
                    }
                }
                primaryLanguage {
                  name
                }
                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                    totalCount
                    edges {
                        size
                        node {
                            name
                        }
                    }
                }
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(first: 0) {
                                totalCount
                            }
                            lastCommit: history(first: 1) {
                                nodes {
                                    committedDate
                                }
                            }
                        }
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
        
        try:
            graphql_response = GitHubAPIService.make_graphql_request(query, variables)
            
            if 'data' in graphql_response:
                return graphql_response['data']
            
            error_msg = "Invalid GraphQL response format"
            if 'errors' in graphql_response:
                error_msg = graphql_response['errors'][0]['message']
                
            logger.error(f"Error fetching GitHub data: {error_msg} - Username: {username} - Response structure: {list(graphql_response.keys())}")
            return {'error': "Unable to analyze profile at this time"}
            
        except Exception as e:
            logger.exception(f"Error in GraphQL data fetching: {str(e)} - Username: {username}")
            return {'error': "Unable to analyze profile at this time"}

# Create a singleton instance
github_api = GitHubAPIService() 