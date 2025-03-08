import sqlite3
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database constants
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "github_users.db"

def init_db():
    """Initialize the SQLite database with the required tables."""
    # Create data directory if it doesn't exist
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
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
    INSERT OR IGNORE INTO sync_status (id, last_user_id) VALUES (1, 0)
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {DB_PATH}")
    return DB_PATH

def get_db_connection():
    """Get a connection to the SQLite database."""
    # Ensure DB exists
    if not DB_PATH.exists():
        init_db()
    return sqlite3.connect(DB_PATH)

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
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted_count = 0
    for user in users:
        try:
            cursor.execute('''
            INSERT OR IGNORE INTO github_users 
            (id, login, node_id, type, site_admin, created_at) 
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user.get('id'),
                user.get('login'),
                user.get('node_id'),
                user.get('type'),
                user.get('site_admin', False)
            ))
            if cursor.rowcount > 0:
                inserted_count += 1
        except sqlite3.Error as e:
            logger.error(f"Error inserting user {user.get('login')}: {e}")
    
    # Update the last synced user ID if we inserted any users
    if inserted_count > 0:
        max_id = max(user.get('id', 0) for user in users)
        update_last_user_id(max_id, cursor)
    
    conn.commit()
    conn.close()
    
    return inserted_count

def update_last_user_id(user_id, cursor=None):
    """Update the last synced user ID in the sync_status table."""
    close_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        close_conn = True
    
    cursor.execute('''
    UPDATE sync_status 
    SET last_user_id = MAX(last_user_id, ?), last_sync = CURRENT_TIMESTAMP 
    WHERE id = 1
    ''', (user_id,))
    
    if close_conn:
        conn.commit()
        conn.close()

def get_last_user_id():
    """Get the ID of the last synced GitHub user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT last_user_id FROM sync_status WHERE id = 1')
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else 0

def get_user_count():
    """Get the total number of GitHub users in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM github_users')
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] if result else 0 