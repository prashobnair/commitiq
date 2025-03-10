#!/usr/bin/env python3
"""
Script to check a specific user's metrics in the PostgreSQL database.
"""

import psycopg2
import logging
import sys
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# PostgreSQL connection parameters
PG_HOST = "github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT = 5432
PG_USER = "commitiq_github"
PG_PASSWORD = "6LH9GHzQfw3UDaoSBTNa"
PG_DB = "github_data"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Check a specific user's metrics in the PostgreSQL database.")
    parser.add_argument("username", type=str, help="GitHub username to check")
    return parser.parse_args()

def check_user(username):
    """Check a specific user's metrics in the PostgreSQL database."""
    try:
        # Connect to PostgreSQL
        logger.info(f"Connecting to PostgreSQL database at {PG_HOST}:{PG_PORT}/{PG_DB}")
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DB
        )
        
        with conn.cursor() as cursor:
            # Check if user exists
            cursor.execute("SELECT id, impact_score FROM score_users WHERE username = %s", (username,))
            user = cursor.fetchone()
            
            if not user:
                logger.error(f"User {username} not found in database")
                return
            
            user_id, impact_score = user
            logger.info(f"User {username} found with ID {user_id} and impact score {impact_score:.2f}")
            
            # Get user metrics
            cursor.execute("""
            SELECT pulls, commits, issues, reviews, repos_impact, consistency, repo_count
            FROM score_metrics
            WHERE user_id = %s
            """, (user_id,))
            metrics = cursor.fetchone()
            
            if metrics:
                pulls, commits, issues, reviews, repos_impact, consistency, repo_count = metrics
                logger.info(f"Metrics for {username}:")
                logger.info(f"Pulls: {pulls}")
                logger.info(f"Commits: {commits}")
                logger.info(f"Issues: {issues}")
                logger.info(f"Reviews: {reviews}")
                logger.info(f"Repos Impact: {repos_impact:.2f}")
                logger.info(f"Consistency: {consistency:.2f}")
                logger.info(f"Repo Count: {repo_count}")
            else:
                logger.error(f"No metrics found for user {username}")
            
            # Get user repositories
            cursor.execute("""
            SELECT name, stars, forks, primary_language, technical_impact, ecosystem_impact, total_impact
            FROM score_repositories
            WHERE user_id = %s
            ORDER BY total_impact DESC
            LIMIT 10
            """, (user_id,))
            repos = cursor.fetchall()
            
            if repos:
                logger.info(f"Top 10 repositories for {username}:")
                logger.info(f"{'Name':<30} {'Stars':<8} {'Forks':<8} {'Language':<15} {'Tech Impact':<15} {'Eco Impact':<15} {'Total Impact':<15}")
                logger.info("-" * 110)
                for repo in repos:
                    name, stars, forks, language, tech_impact, eco_impact, total_impact = repo
                    logger.info(f"{name:<30} {stars:<8} {forks:<8} {language or 'N/A':<15} {tech_impact or 0.0:<15.2f} {eco_impact or 0.0:<15.2f} {total_impact or 0.0:<15.2f}")
            else:
                logger.error(f"No repositories found for user {username}")
        
    except Exception as e:
        logger.error(f"Error checking user: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    args = parse_args()
    check_user(args.username) 