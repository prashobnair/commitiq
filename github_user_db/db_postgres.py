import os
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Connection pool
connection_pool = None

def init_db_pool(min_conn=1, max_conn=10):
    """Initialize the PostgreSQL connection pool."""
    global connection_pool
    
    # Get database connection parameters from environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    # Validate required parameters
    if not all([db_host, db_name, db_user, db_password]):
        raise ValueError("Missing required database connection parameters. "
                         "Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables.")
    
    try:
        # Create connection pool
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        logger.info(f"PostgreSQL connection pool initialized with {min_conn}-{max_conn} connections")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        raise

def get_db_connection():
    """Get a connection from the pool."""
    global connection_pool
    
    if connection_pool is None:
        init_db_pool()
    
    return connection_pool.getconn()

def release_connection(conn):
    """Return a connection to the pool."""
    global connection_pool
    
    if connection_pool is not None and conn is not None:
        connection_pool.putconn(conn)

def init_db():
    """Initialize the PostgreSQL database with the required tables."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table with minimal required fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS github_users (
            id INTEGER PRIMARY KEY,
            login TEXT NOT NULL UNIQUE,
            node_id TEXT,
            type TEXT,
            site_admin BOOLEAN,
            created_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create index on login for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_login ON github_users(login)')
        
        # Create a table to track progress
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_status (
            id INTEGER PRIMARY KEY,
            last_user_id INTEGER DEFAULT 0,
            last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert initial sync status if not exists
        cursor.execute('''
        INSERT INTO sync_status (id, last_user_id)
        VALUES (1, 0)
        ON CONFLICT (id) DO NOTHING
        ''')
        
        conn.commit()
        logger.info("PostgreSQL database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL database: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            release_connection(conn)

def insert_users(users):
    """
    Insert multiple GitHub users into the database.
    
    Args:
        users (list): List of user dictionaries with at least 'id' and 'login' keys
    
    Returns:
        int: Number of users inserted
    """
    if not users:
        return 0
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data for batch insert
        user_data = [(
            user.get('id'),
            user.get('login'),
            user.get('node_id'),
            user.get('type'),
            user.get('site_admin', False),
            'NOW()'  # current timestamp for created_at
        ) for user in users]
        
        # Use execute_values for efficient batch insert
        execute_values(
            cursor,
            '''
            INSERT INTO github_users 
            (id, login, node_id, type, site_admin, created_at) 
            VALUES %s
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            ''',
            user_data,
            template='(%s, %s, %s, %s, %s, %s)'
        )
        
        # Get the number of inserted rows
        inserted_rows = cursor.fetchall()
        inserted_count = len(inserted_rows)
        
        # Update the last synced user ID if we inserted any users
        if inserted_count > 0:
            max_id = max(user.get('id', 0) for user in users)
            update_last_user_id(max_id, cursor)
        
        conn.commit()
        return inserted_count
    except Exception as e:
        logger.error(f"Error inserting users: {e}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            release_connection(conn)

def update_last_user_id(user_id, cursor=None):
    """Update the last synced user ID in the sync_status table."""
    conn = None
    close_conn = False
    
    try:
        if cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()
            close_conn = True
        
        cursor.execute('''
        UPDATE sync_status 
        SET last_user_id = GREATEST(last_user_id, %s), last_sync = CURRENT_TIMESTAMP 
        WHERE id = 1
        ''', (user_id,))
        
        if close_conn and conn:
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating last user ID: {e}")
        if close_conn and conn:
            conn.rollback()
    finally:
        if close_conn and conn:
            release_connection(conn)

def get_last_user_id():
    """Get the ID of the last synced GitHub user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_user_id FROM sync_status WHERE id = 1')
        result = cursor.fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting last user ID: {e}")
        return 0
    finally:
        if conn:
            release_connection(conn)

def get_user_count():
    """Get the total number of GitHub users in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM github_users')
        result = cursor.fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting user count: {e}")
        return 0
    finally:
        if conn:
            release_connection(conn)

def close_db_pool():
    """Close the database connection pool."""
    global connection_pool
    
    if connection_pool is not None:
        connection_pool.closeall()
        logger.info("PostgreSQL connection pool closed")
        connection_pool = None 