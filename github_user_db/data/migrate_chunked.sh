#!/bin/bash
set -e

# Configuration
PG_HOST="github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT="5432"
PG_USER="commitiq_github"
PG_PASSWORD="6LH9GHzQfw3UDaoSBTNa"
PG_DB="github_data"
SQLITE_DB="github_users.db"
CHUNK_SIZE=10000  # Number of rows per chunk
TOTAL_ROWS=$(sqlite3 $SQLITE_DB "SELECT COUNT(*) FROM github_users;")

echo "Total rows to import: $TOTAL_ROWS"

# Create tables in PostgreSQL
echo "Creating tables in PostgreSQL..."
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -f create_tables.sql

# Process data in chunks
echo "Processing data in chunks of $CHUNK_SIZE rows..."
for ((i=0; i<$TOTAL_ROWS; i+=$CHUNK_SIZE)); do
    echo "Processing chunk $((i/$CHUNK_SIZE + 1)) of $(($TOTAL_ROWS/$CHUNK_SIZE + 1))..."
    
    # Export chunk from SQLite to CSV
    echo "Exporting chunk from SQLite to CSV..."
    sqlite3 -csv $SQLITE_DB "SELECT * FROM github_users LIMIT $CHUNK_SIZE OFFSET $i;" > chunk_$i.csv
    
    # Import chunk to PostgreSQL
    echo "Importing chunk to PostgreSQL..."
    PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy github_users FROM 'chunk_$i.csv' WITH CSV"
    
    # Clean up chunk file
    rm chunk_$i.csv
    
    # Check progress
    IMPORTED_ROWS=$(PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -t -c "SELECT COUNT(*) FROM github_users;")
    echo "Progress: $IMPORTED_ROWS of $TOTAL_ROWS rows imported ($(($IMPORTED_ROWS*100/$TOTAL_ROWS))%)"
done

# Export and import sync_status
echo "Exporting sync_status from SQLite to CSV..."
sqlite3 -csv $SQLITE_DB "SELECT * FROM sync_status;" > sync_status.csv

echo "Importing sync_status to PostgreSQL..."
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy sync_status FROM 'sync_status.csv' WITH CSV"

# Clean up
rm -f sync_status.csv

echo "Migration completed successfully!" 