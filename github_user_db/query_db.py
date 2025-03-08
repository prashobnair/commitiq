#!/usr/bin/env python3
"""
GitHub User Database Query Tool

This script provides utilities to query the GitHub user database and display statistics.
"""

import argparse
import logging
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database constants
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "github_users.db"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Query the GitHub user database.')
    parser.add_argument('--stats', action='store_true', help='Display database statistics')
    parser.add_argument('--search', type=str, help='Search for users by login (supports SQL LIKE patterns)')
    parser.add_argument('--limit', type=int, default=10, help='Limit the number of results (default: 10)')
    parser.add_argument('--export', type=str, help='Export users to CSV file')
    parser.add_argument('--type', type=str, help='Filter by user type (User, Organization)')
    return parser.parse_args()

def get_db_connection():
    """Get a connection to the SQLite database."""
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}. Run collect_users.py first.")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def display_stats():
    """Display database statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute('SELECT COUNT(*) FROM github_users')
    total_count = cursor.fetchone()[0]
    
    # Get count by type
    cursor.execute('SELECT type, COUNT(*) FROM github_users GROUP BY type')
    type_counts = cursor.fetchall()
    
    # Get last sync info
    cursor.execute('SELECT last_user_id, last_sync FROM sync_status WHERE id = 1')
    last_user_id, last_sync = cursor.fetchone()
    
    # Get first and last user IDs
    cursor.execute('SELECT MIN(id), MAX(id) FROM github_users')
    min_id, max_id = cursor.fetchone()
    
    # Get recently added users
    cursor.execute('SELECT id, login, type FROM github_users ORDER BY created_at DESC LIMIT 5')
    recent_users = cursor.fetchall()
    
    conn.close()
    
    # Display statistics
    print("\n=== GitHub User Database Statistics ===\n")
    print(f"Total users: {total_count:,}")
    print("\nUser types:")
    for user_type, count in type_counts:
        print(f"  - {user_type}: {count:,} ({count/total_count*100:.1f}%)")
    
    print(f"\nID range: {min_id:,} to {max_id:,}")
    print(f"Last sync: {last_sync} (up to user ID: {last_user_id:,})")
    
    print("\nRecently added users:")
    for user_id, login, user_type in recent_users:
        print(f"  - {login} (ID: {user_id}, Type: {user_type})")

def search_users(search_term, limit=10, user_type=None):
    """Search for users by login."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT id, login, type, site_admin, created_at FROM github_users WHERE login LIKE ?'
    params = [f'%{search_term}%']
    
    if user_type:
        query += ' AND type = ?'
        params.append(user_type)
    
    query += ' ORDER BY id LIMIT ?'
    params.append(limit)
    
    cursor.execute(query, params)
    users = cursor.fetchall()
    
    conn.close()
    
    if not users:
        print(f"No users found matching '{search_term}'")
        return
    
    print(f"\n=== Users matching '{search_term}' ===\n")
    print(f"{'ID':<10} {'Login':<30} {'Type':<15} {'Admin':<6} {'Created At'}")
    print("-" * 70)
    
    for user_id, login, user_type, is_admin, created_at in users:
        admin_str = "Yes" if is_admin else "No"
        print(f"{user_id:<10} {login:<30} {user_type:<15} {admin_str:<6} {created_at}")
    
    print(f"\nShowing {len(users)} of {limit} requested results.")

def export_users(filename, user_type=None, limit=None):
    """Export users to a CSV file."""
    import csv
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT id, login, node_id, type, site_admin, created_at FROM github_users'
    params = []
    
    if user_type:
        query += ' WHERE type = ?'
        params.append(user_type)
    
    query += ' ORDER BY id'
    
    if limit:
        query += ' LIMIT ?'
        params.append(limit)
    
    cursor.execute(query, params)
    users = cursor.fetchall()
    
    if not users:
        print("No users to export")
        return
    
    # Ensure filename has .csv extension
    if not filename.endswith('.csv'):
        filename += '.csv'
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(['id', 'login', 'node_id', 'type', 'site_admin', 'created_at'])
        # Write data
        writer.writerows(users)
    
    conn.close()
    
    print(f"Exported {len(users):,} users to {filename}")

def main():
    """Main function."""
    args = parse_args()
    
    if args.stats:
        display_stats()
    elif args.search:
        search_users(args.search, args.limit, args.type)
    elif args.export:
        export_users(args.export, args.type, args.limit)
    else:
        print("No action specified. Use --stats, --search, or --export.")
        print("Run with --help for more information.")

if __name__ == "__main__":
    main() 