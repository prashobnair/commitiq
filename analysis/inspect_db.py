#!/usr/bin/env python3
"""
Script to inspect the database schema and save the results to a file.
"""
import os
import sys
import json
from datetime import datetime

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from db_inspector import list_tables, describe_table, get_table_sample

def main():
    """Main function to run the database inspection and save results."""
    print("Inspecting database schema...")
    
    # Create results directory if it doesn't exist
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    # Create a timestamp for the output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(results_dir, f'db_schema_{timestamp}.txt')
    
    # List all tables
    tables = list_tables()
    
    # Open the output file
    with open(output_file, 'w') as f:
        f.write(f"Database Schema Inspection - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Found {len(tables)} tables in the database:\n")
        for table in tables:
            f.write(f"  - {table}\n")
        
        # Describe each table
        for table in tables:
            f.write(f"\n\nTable: {table}\n")
            f.write("-" * 80 + "\n")
            
            f.write("Columns:\n")
            columns = describe_table(table)
            f.write(columns.to_string() + "\n\n")
            
            # Get sample data
            f.write("Sample data:\n")
            try:
                sample = get_table_sample(table)
                f.write(sample.to_string() + "\n")
            except Exception as e:
                f.write(f"Error getting sample: {str(e)}\n")
    
    print(f"Database schema inspection complete. Results saved to: {output_file}")
    
    # Also print the tables to the console
    print(f"\nFound {len(tables)} tables in the database:")
    for table in tables:
        print(f"  - {table}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 