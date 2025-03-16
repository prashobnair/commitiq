#!/usr/bin/env python3
"""
Script to inspect the schema of specific tables in the PostgreSQL database.
"""
import os
import sys
import pandas as pd
from dotenv import load_dotenv
import psycopg2

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

def describe_table(table_name):
    """
    Describe the structure of a table.
    
    Args:
        table_name (str): Name of the table to describe
        
    Returns:
        pd.DataFrame: DataFrame containing column information
    """
    try:
        conn = get_db_connection()
        
        # Query to get column information
        query = f"""
            SELECT 
                column_name, 
                data_type, 
                is_nullable,
                column_default
            FROM 
                information_schema.columns
            WHERE 
                table_schema = 'public' AND 
                table_name = '{table_name}'
            ORDER BY 
                ordinal_position
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        print(f"Error describing table {table_name}: {str(e)}")
        raise

def get_table_sample(table_name, limit=5):
    """
    Get a sample of data from a table.
    
    Args:
        table_name (str): Name of the table to sample
        limit (int): Maximum number of rows to return
        
    Returns:
        pd.DataFrame: DataFrame containing sample data
    """
    try:
        conn = get_db_connection()
        
        # Query to get sample data
        query = f"""
            SELECT * FROM {table_name} LIMIT {limit}
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        print(f"Error getting sample from table {table_name}: {str(e)}")
        raise

def check_table_exists(table_name):
    """
    Check if a table exists in the database.
    
    Args:
        table_name (str): Name of the table to check
        
    Returns:
        bool: True if the table exists, False otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query to check if table exists
        query = f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = '{table_name}'
            )
        """
        
        cursor.execute(query)
        exists = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return exists
    except Exception as e:
        print(f"Error checking if table {table_name} exists: {str(e)}")
        raise

def main():
    """Main function to inspect the schema of specific tables."""
    tables_to_inspect = [
        'users_github',
        'users_metrics',
        'users_repositories',
        'users_repository_metrics'
    ]
    
    print("Inspecting specific tables in the database...")
    
    for table in tables_to_inspect:
        if check_table_exists(table):
            print(f"\nTable: {table}")
            print("=" * 80)
            
            print("Columns:")
            columns = describe_table(table)
            print(columns)
            
            print("\nSample data:")
            sample = get_table_sample(table)
            print(sample)
        else:
            print(f"\nTable {table} does not exist in the database.")
            
            # Check for similar table names
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name LIKE '%{table.split('_')[-1]}%'
                ORDER BY table_name
            """
            
            cursor.execute(query)
            similar_tables = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            if similar_tables:
                print(f"Similar tables found:")
                for similar_table in similar_tables:
                    print(f"  - {similar_table[0]}")

if __name__ == "__main__":
    main() 