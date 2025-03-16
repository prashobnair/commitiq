"""
Utility script to inspect the PostgreSQL database schema.
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

def list_tables():
    """
    List all tables in the database.
    
    Returns:
        list: List of table names
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query to get all tables in the current schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return tables
    except Exception as e:
        print(f"Error listing tables: {str(e)}")
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

def main():
    """Main function to run the database inspection."""
    print("Inspecting database schema...")
    
    # List all tables
    tables = list_tables()
    print(f"\nFound {len(tables)} tables in the database:")
    for table in tables:
        print(f"  - {table}")
    
    # Describe each table
    for table in tables:
        print(f"\nTable: {table}")
        print("Columns:")
        columns = describe_table(table)
        print(columns)
        
        # Get sample data
        print("\nSample data:")
        sample = get_table_sample(table)
        print(sample)
        print("-" * 80)

if __name__ == "__main__":
    main() 