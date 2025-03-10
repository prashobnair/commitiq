#!/usr/bin/env python3
"""
Database utilities for connecting to SQLite and PostgreSQL databases.
"""

import os
import logging
import sqlite3
from pathlib import Path
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

# Default connection parameters
DEFAULT_PG_HOST = os.environ.get("PG_HOST", "localhost")
DEFAULT_PG_PORT = int(os.environ.get("PG_PORT", "5432"))
DEFAULT_PG_USER = os.environ.get("PG_USER", "postgres")
DEFAULT_PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
DEFAULT_PG_DB = os.environ.get("PG_DB", "github_data")

# SQLite database paths
METRICS_DB_PATH = Path(__file__).parent / "data" / "metrics_analysis.db"
GITHUB_DB_PATH = Path(__file__).parent.parent / "github_user_db" / "data" / "github_users.db"

@contextmanager
def sqlite_connection(db_path):
    """
    Context manager for SQLite database connections.
    
    Args:
        db_path: Path to SQLite database
        
    Yields:
        SQLite connection object
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database not found at {db_path}")
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()

@contextmanager
def postgres_connection(host=DEFAULT_PG_HOST, port=DEFAULT_PG_PORT, 
                        user=DEFAULT_PG_USER, password=DEFAULT_PG_PASSWORD, 
                        dbname=DEFAULT_PG_DB):
    """
    Context manager for PostgreSQL database connections.
    
    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL username
        password: PostgreSQL password
        dbname: PostgreSQL database name
        
    Yields:
        PostgreSQL connection object
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_existing_users_sqlite(db_path=METRICS_DB_PATH):
    """
    Get set of usernames that already have data in the SQLite metrics database.
    
    Args:
        db_path: Path to SQLite metrics database
        
    Returns:
        Set of usernames
    """
    with sqlite_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users')
        return {row[0] for row in cursor.fetchall()}

def get_existing_users_postgres(host=DEFAULT_PG_HOST, port=DEFAULT_PG_PORT, 
                               user=DEFAULT_PG_USER, password=DEFAULT_PG_PASSWORD, 
                               dbname=DEFAULT_PG_DB):
    """
    Get set of usernames that already have data in the PostgreSQL metrics database.
    
    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL username
        password: PostgreSQL password
        dbname: PostgreSQL database name
        
    Returns:
        Set of usernames
    """
    with postgres_connection(host, port, user, password, dbname) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT username FROM score_users')
            return {row[0] for row in cursor.fetchall()}

def sample_users_sqlite(github_db_path, batch_size, existing_users=None):
    """
    Sample users from the SQLite GitHub database.
    
    Args:
        github_db_path: Path to GitHub users database
        batch_size: Number of users to sample
        existing_users: Set of usernames to skip
        
    Returns:
        List of user dictionaries with 'id' and 'login' keys
    """
    if existing_users is None:
        existing_users = set()
    
    with sqlite_connection(github_db_path) as conn:
        cursor = conn.cursor()
        
        # Get total user count and ID range
        cursor.execute('SELECT COUNT(*), MIN(id), MAX(id) FROM github_users')
        total_count, min_id, max_id = cursor.fetchone()
        
        logger.info(f"GitHub database contains {total_count:,} users with IDs from {min_id:,} to {max_id:,}")
        
        # Create a weighted distribution favoring later users
        segments = 10
        segment_size = (max_id - min_id) // segments
        
        # Weights for each segment (increasing weights for later segments)
        weights = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5]
        total_weight = sum(weights)
        
        # Calculate how many users to sample from each segment
        segment_samples = []
        for weight in weights:
            segment_samples.append(int(batch_size * weight / total_weight))
        
        # Adjust to ensure we get exactly batch_size users
        while sum(segment_samples) < batch_size:
            segment_samples[-1] += 1
        
        users = []
        skipped_count = 0
        
        # Sample users from each segment
        for i in range(segments):
            segment_start = min_id + i * segment_size
            segment_end = segment_start + segment_size - 1 if i < segments - 1 else max_id
            segment_count = segment_samples[i]
            
            if segment_count > 0:
                # Get more users than needed to account for skipping existing users
                extra_factor = 2  # Get 2x more users than needed
                
                # Get random users from this segment
                cursor.execute('''
                    SELECT id, login FROM github_users 
                    WHERE id BETWEEN ? AND ?
                    ORDER BY RANDOM() 
                    LIMIT ?
                ''', (segment_start, segment_end, segment_count * extra_factor))
                
                segment_users = []
                for row in cursor.fetchall():
                    user_id, username = row
                    
                    # Skip users that already have data
                    if username in existing_users:
                        skipped_count += 1
                        continue
                    
                    segment_users.append({'id': user_id, 'login': username})
                    
                    # Stop once we have enough users for this segment
                    if len(segment_users) >= segment_count:
                        break
                
                users.extend(segment_users)
                
                logger.info(f"Sampled {len(segment_users)} users from segment {i+1} (IDs {segment_start:,}-{segment_end:,})")
    
    logger.info(f"Sampled {len(users)} users, skipped {skipped_count} existing users")
    
    # If we couldn't get enough users, log a warning
    if len(users) < batch_size:
        logger.warning(f"Could only sample {len(users)} users, fewer than requested {batch_size}")
    
    return users

def sample_users_postgres(host=DEFAULT_PG_HOST, port=DEFAULT_PG_PORT, 
                         user=DEFAULT_PG_USER, password=DEFAULT_PG_PASSWORD, 
                         dbname=DEFAULT_PG_DB, batch_size=100, existing_users=None):
    """
    Sample users from the PostgreSQL GitHub database.
    
    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL username
        password: PostgreSQL password
        dbname: PostgreSQL database name
        batch_size: Number of users to sample
        existing_users: Set of usernames to skip
        
    Returns:
        List of user dictionaries with 'id' and 'login' keys
    """
    if existing_users is None:
        existing_users = set()
    
    with postgres_connection(host, port, user, password, dbname) as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Get total user count and ID range
            cursor.execute('SELECT COUNT(*), MIN(id), MAX(id) FROM github_users')
            total_count, min_id, max_id = cursor.fetchone()
            
            logger.info(f"GitHub database contains {total_count:,} users with IDs from {min_id:,} to {max_id:,}")
            
            # Create a weighted distribution favoring later users
            segments = 10
            segment_size = (max_id - min_id) // segments
            
            # Weights for each segment (increasing weights for later segments)
            weights = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5]
            total_weight = sum(weights)
            
            # Calculate how many users to sample from each segment
            segment_samples = []
            for weight in weights:
                segment_samples.append(int(batch_size * weight / total_weight))
            
            # Adjust to ensure we get exactly batch_size users
            while sum(segment_samples) < batch_size:
                segment_samples[-1] += 1
            
            users = []
            skipped_count = 0
            
            # Sample users from each segment
            for i in range(segments):
                segment_start = min_id + i * segment_size
                segment_end = segment_start + segment_size - 1 if i < segments - 1 else max_id
                segment_count = segment_samples[i]
                
                if segment_count > 0:
                    # Get more users than needed to account for skipping existing users
                    extra_factor = 2  # Get 2x more users than needed
                    
                    # Get random users from this segment
                    cursor.execute('''
                        SELECT id, login FROM github_users 
                        WHERE id BETWEEN %s AND %s
                        ORDER BY RANDOM() 
                        LIMIT %s
                    ''', (segment_start, segment_end, segment_count * extra_factor))
                    
                    segment_users = []
                    for row in cursor:
                        user_id, username = row['id'], row['login']
                        
                        # Skip users that already have data
                        if username in existing_users:
                            skipped_count += 1
                            continue
                        
                        segment_users.append({'id': user_id, 'login': username})
                        
                        # Stop once we have enough users for this segment
                        if len(segment_users) >= segment_count:
                            break
                    
                    users.extend(segment_users)
                    
                    logger.info(f"Sampled {len(segment_users)} users from segment {i+1} (IDs {segment_start:,}-{segment_end:,})")
    
    logger.info(f"Sampled {len(users)} users, skipped {skipped_count} existing users")
    
    # If we couldn't get enough users, log a warning
    if len(users) < batch_size:
        logger.warning(f"Could only sample {len(users)} users, fewer than requested {batch_size}")
    
    return users 