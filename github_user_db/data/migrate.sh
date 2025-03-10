#!/bin/bash
set -e

# Configuration
PG_HOST="github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT="5432"
PG_USER="commitiq_github"
PG_PASSWORD="6LH9GHzQfw3UDaoSBTNa"
PG_DB="github_data"
SQLITE_DB="github_users.db"

# Export data from SQLite to CSV
echo "Exporting data from SQLite to CSV..."
sqlite3 $SQLITE_DB < export_to_csv.sql

# Create tables in PostgreSQL
echo "Creating tables in PostgreSQL..."
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -f create_tables.sql

# Import data from CSV to PostgreSQL using \copy
echo "Importing data from CSV to PostgreSQL..."
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy github_users FROM 'github_users.csv' WITH CSV HEADER"
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy sync_status FROM 'sync_status.csv' WITH CSV HEADER"

# Clean up
echo "Cleaning up..."
rm -f github_users.csv sync_status.csv

echo "Migration completed successfully!" 