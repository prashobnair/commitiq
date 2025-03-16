"""
Database connection module for fetching GitHub user data from PostgreSQL.
"""
import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_db_connection():
    """
    Create a connection to the PostgreSQL database using credentials from .env file.
    
    Returns:
        connection: PostgreSQL database connection object
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        raise

def query_to_dataframe(query, params=None):
    """
    Execute a SQL query and return the results as a pandas DataFrame.
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the SQL query
        
    Returns:
        pd.DataFrame: Query results as a DataFrame
    """
    try:
        conn = get_db_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        print(f"Query execution error: {str(e)}")
        raise

def fetch_users_data():
    """
    Fetch basic GitHub user data.
    
    Returns:
        pd.DataFrame: GitHub users data
    """
    query = """
    SELECT * FROM users_github
    """
    return query_to_dataframe(query)

def fetch_users_metrics():
    """
    Fetch users metrics data.
    
    Returns:
        pd.DataFrame: Users metrics data
    """
    query = """
    SELECT * FROM users_metrics
    """
    return query_to_dataframe(query)

def fetch_users_repositories():
    """
    Fetch users repositories data.
    
    Returns:
        pd.DataFrame: Users repositories data
    """
    query = """
    SELECT * FROM users_repositories
    """
    return query_to_dataframe(query)

def fetch_users_repositories_metrics():
    """
    Fetch users repository metrics data.
    
    Returns:
        pd.DataFrame: Users repository metrics data
    """
    query = """
    SELECT * FROM users_repository_metrics
    """
    return query_to_dataframe(query)

def fetch_joined_user_data():
    """
    Fetch joined user data with metrics for comprehensive analysis.
    
    Returns:
        pd.DataFrame: Joined user data with metrics
    """
    query = """
    SELECT u.id, u.username, u.name, u.email, u.location, u.company, u.bio,
           u.followers, u.following, 
           0 as public_repos_count,
           m.pulls, m.commits, 
           m.reviews, m.issues,
           m.repos_impact, m.consistency, u.impact_score
    FROM users_github u
    JOIN users_metrics m ON u.id = m.user_id
    """
    return query_to_dataframe(query)

def fetch_repository_with_metrics():
    """
    Fetch repository data with their metrics.
    
    Returns:
        pd.DataFrame: Repository data with metrics
    """
    query = """
    SELECT r.id, r.user_id, r.name, r.stars, r.forks, 
           rm.collaborators, r.primary_language,
           rm.developer_commits, rm.total_commits, rm.contribution_ratio,
           rm.merged_pull_requests, rm.closed_pull_requests, 
           rm.total_pull_requests, rm.pr_acceptance,
           rm.review_comments, rm.code_quality,
           r.technical_impact as repo_tech_impact, rm.popularity, 
           r.ecosystem_impact as repo_eco_impact,
           r.total_impact as repo_impact
    FROM users_repositories r
    LEFT JOIN users_repository_metrics rm ON r.id = rm.repository_id
    """
    return query_to_dataframe(query) 