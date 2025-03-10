#!/usr/bin/env python3
"""
Script to migrate data from local SQLite database to AWS RDS PostgreSQL database.
"""

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-db", type=str, default="data/metrics_analysis.db",
                        help="Path to SQLite database")
    parser.add_argument("--pg-host", type=str, required=True,
                        help="PostgreSQL host")
    parser.add_argument("--pg-port", type=int, default=5432,
                        help="PostgreSQL port")
    parser.add_argument("--pg-user", type=str, required=True,
                        help="PostgreSQL username")
    parser.add_argument("--pg-password", type=str, required=True,
                        help="PostgreSQL password")
    parser.add_argument("--pg-db", type=str, default="github_data",
                        help="PostgreSQL database name")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Batch size for data transfer")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    return parser.parse_args()

def connect_sqlite(db_path):
    """Connect to SQLite database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite database not found at {db_path}")
    
    logger.info(f"Connecting to SQLite database at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def connect_postgres(host, port, user, password, dbname):
    """Connect to PostgreSQL database."""
    logger.info(f"Connecting to PostgreSQL database at {host}:{port}/{dbname}")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise

def create_postgres_tables(pg_conn):
    """Create tables in PostgreSQL if they don't exist."""
    logger.info("Creating PostgreSQL tables if they don't exist")
    
    with pg_conn.cursor() as cursor:
        # Create score_users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS score_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            github_id INTEGER,
            name TEXT,
            email TEXT,
            company TEXT,
            location TEXT,
            bio TEXT,
            followers INTEGER,
            following INTEGER,
            impact_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create score_metrics table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS score_metrics (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            pulls INTEGER,
            commits INTEGER,
            issues INTEGER,
            reviews INTEGER,
            repos_impact REAL,
            consistency REAL,
            repo_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES score_users (id)
        )
        """)
        
        # Create score_repositories table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS score_repositories (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT,
            stars INTEGER,
            forks INTEGER,
            primary_language TEXT,
            technical_impact REAL,
            ecosystem_impact REAL,
            total_impact REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES score_users (id)
        )
        """)
        
        # Create index on username
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_score_username ON score_users(username)
        """)
        
        pg_conn.commit()
        logger.info("PostgreSQL tables created successfully")

def get_table_count(conn, table_name, is_postgres=False):
    """Get the number of rows in a table."""
    if is_postgres:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
    else:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]

def migrate_users(sqlite_conn, pg_conn, batch_size):
    """Migrate users from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    
    # Get total count for progress bar
    total_users = get_table_count(sqlite_conn, "users")
    logger.info(f"Migrating {total_users} users from SQLite to PostgreSQL")
    
    # Get all users from SQLite
    sqlite_cursor.execute("""
    SELECT id, username, github_id, name, email, company, location, bio, 
           followers, following, impact_score, created_at
    FROM users
    """)
    
    # Process in batches
    batch_count = 0
    with pg_conn.cursor() as pg_cursor:
        batch = []
        
        for row in tqdm(sqlite_cursor, total=total_users, desc="Migrating users"):
            batch.append(dict(row))
            
            if len(batch) >= batch_size:
                # Insert batch into PostgreSQL
                columns = batch[0].keys()
                query = sql.SQL("INSERT INTO score_users ({}) VALUES %s ON CONFLICT (username) DO NOTHING").format(
                    sql.SQL(', ').join(map(sql.Identifier, columns))
                )
                
                values = [[row[column] for column in columns] for row in batch]
                execute_values(pg_cursor, query, values)
                
                pg_conn.commit()
                batch_count += 1
                logger.debug(f"Committed batch {batch_count} ({len(batch)} users)")
                batch = []
        
        # Insert any remaining users
        if batch:
            columns = batch[0].keys()
            query = sql.SQL("INSERT INTO score_users ({}) VALUES %s ON CONFLICT (username) DO NOTHING").format(
                sql.SQL(', ').join(map(sql.Identifier, columns))
            )
            
            values = [[row[column] for column in columns] for row in batch]
            execute_values(pg_cursor, query, values)
            
            pg_conn.commit()
            batch_count += 1
            logger.debug(f"Committed final batch {batch_count} ({len(batch)} users)")
    
    # Verify migration
    pg_users = get_table_count(pg_conn, "score_users", True)
    logger.info(f"Migrated users: {pg_users}/{total_users}")

def migrate_metrics(sqlite_conn, pg_conn, batch_size):
    """Migrate metrics from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    
    # Get total count for progress bar
    total_metrics = get_table_count(sqlite_conn, "metrics")
    logger.info(f"Migrating {total_metrics} metrics from SQLite to PostgreSQL")
    
    # Get all metrics from SQLite
    sqlite_cursor.execute("""
    SELECT id, user_id, pulls, commits, issues, reviews, repos_impact, 
           consistency, repo_count, created_at
    FROM metrics
    """)
    
    # Process in batches
    batch_count = 0
    with pg_conn.cursor() as pg_cursor:
        batch = []
        
        for row in tqdm(sqlite_cursor, total=total_metrics, desc="Migrating metrics"):
            batch.append(dict(row))
            
            if len(batch) >= batch_size:
                # Insert batch into PostgreSQL
                columns = batch[0].keys()
                query = sql.SQL("INSERT INTO score_metrics ({}) VALUES %s").format(
                    sql.SQL(', ').join(map(sql.Identifier, columns))
                )
                
                values = [[row[column] for column in columns] for row in batch]
                execute_values(pg_cursor, query, values)
                
                pg_conn.commit()
                batch_count += 1
                logger.debug(f"Committed batch {batch_count} ({len(batch)} metrics)")
                batch = []
        
        # Insert any remaining metrics
        if batch:
            columns = batch[0].keys()
            query = sql.SQL("INSERT INTO score_metrics ({}) VALUES %s").format(
                sql.SQL(', ').join(map(sql.Identifier, columns))
            )
            
            values = [[row[column] for column in columns] for row in batch]
            execute_values(pg_cursor, query, values)
            
            pg_conn.commit()
            batch_count += 1
            logger.debug(f"Committed final batch {batch_count} ({len(batch)} metrics)")
    
    # Verify migration
    pg_metrics = get_table_count(pg_conn, "score_metrics", True)
    logger.info(f"Migrated metrics: {pg_metrics}/{total_metrics}")

def migrate_repositories(sqlite_conn, pg_conn, batch_size):
    """Migrate repositories from SQLite to PostgreSQL."""
    sqlite_cursor = sqlite_conn.cursor()
    
    # Get total count for progress bar
    total_repos = get_table_count(sqlite_conn, "repositories")
    logger.info(f"Migrating {total_repos} repositories from SQLite to PostgreSQL")
    
    # Get all repositories from SQLite
    sqlite_cursor.execute("""
    SELECT id, user_id, name, stars, forks, primary_language, technical_impact, 
           ecosystem_impact, total_impact, created_at
    FROM repositories
    """)
    
    # Process in batches
    batch_count = 0
    with pg_conn.cursor() as pg_cursor:
        batch = []
        
        for row in tqdm(sqlite_cursor, total=total_repos, desc="Migrating repositories"):
            batch.append(dict(row))
            
            if len(batch) >= batch_size:
                # Insert batch into PostgreSQL
                columns = batch[0].keys()
                query = sql.SQL("INSERT INTO score_repositories ({}) VALUES %s").format(
                    sql.SQL(', ').join(map(sql.Identifier, columns))
                )
                
                values = [[row[column] for column in columns] for row in batch]
                execute_values(pg_cursor, query, values)
                
                pg_conn.commit()
                batch_count += 1
                logger.debug(f"Committed batch {batch_count} ({len(batch)} repositories)")
                batch = []
        
        # Insert any remaining repositories
        if batch:
            columns = batch[0].keys()
            query = sql.SQL("INSERT INTO score_repositories ({}) VALUES %s").format(
                sql.SQL(', ').join(map(sql.Identifier, columns))
            )
            
            values = [[row[column] for column in columns] for row in batch]
            execute_values(pg_cursor, query, values)
            
            pg_conn.commit()
            batch_count += 1
            logger.debug(f"Committed final batch {batch_count} ({len(batch)} repositories)")
    
    # Verify migration
    pg_repos = get_table_count(pg_conn, "score_repositories", True)
    logger.info(f"Migrated repositories: {pg_repos}/{total_repos}")

def main():
    """Main function to migrate data from SQLite to PostgreSQL."""
    args = parse_args()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Connect to databases
        sqlite_conn = connect_sqlite(args.sqlite_db)
        pg_conn = connect_postgres(
            args.pg_host, 
            args.pg_port, 
            args.pg_user, 
            args.pg_password, 
            args.pg_db
        )
        
        # Create PostgreSQL tables
        create_postgres_tables(pg_conn)
        
        # Migrate data
        migrate_users(sqlite_conn, pg_conn, args.batch_size)
        migrate_metrics(sqlite_conn, pg_conn, args.batch_size)
        migrate_repositories(sqlite_conn, pg_conn, args.batch_size)
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Close connections
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()

if __name__ == "__main__":
    main() 