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

# Get current progress
CURRENT_ROWS=$(PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -t -c "SELECT COUNT(*) FROM github_users;" | tr -d '[:space:]')
if [ -z "$CURRENT_ROWS" ]; then
    CURRENT_ROWS=0
fi

# Calculate starting chunk
START_CHUNK=$((CURRENT_ROWS / CHUNK_SIZE))
START_OFFSET=$((START_CHUNK * CHUNK_SIZE))

echo "Total rows to import: $TOTAL_ROWS"
echo "Current progress: $CURRENT_ROWS rows already imported"
echo "Resuming from chunk $((START_CHUNK + 1)) (offset $START_OFFSET)"

# Process data in chunks, starting from where we left off
echo "Processing data in chunks of $CHUNK_SIZE rows..."
for ((i=START_OFFSET; i<$TOTAL_ROWS; i+=$CHUNK_SIZE)); do
    CHUNK_NUM=$((i / CHUNK_SIZE + 1))
    TOTAL_CHUNKS=$((TOTAL_ROWS / CHUNK_SIZE + 1))
    
    echo "Processing chunk $CHUNK_NUM of $TOTAL_CHUNKS..."
    
    # Export chunk from SQLite to CSV
    echo "Exporting chunk from SQLite to CSV..."
    sqlite3 -csv $SQLITE_DB "SELECT * FROM github_users LIMIT $CHUNK_SIZE OFFSET $i;" > chunk_$i.csv
    
    # Import chunk to PostgreSQL with retry logic
    MAX_RETRIES=3
    RETRY_COUNT=0
    IMPORT_SUCCESS=false
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$IMPORT_SUCCESS" = false ]; do
        echo "Importing chunk to PostgreSQL (attempt $((RETRY_COUNT + 1)) of $MAX_RETRIES)..."
        if PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy github_users FROM 'chunk_$i.csv' WITH CSV" 2>/dev/null; then
            IMPORT_SUCCESS=true
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Import failed. Retrying in 5 seconds..."
                sleep 5
            else
                echo "Import failed after $MAX_RETRIES attempts. Exiting."
                exit 1
            fi
        fi
    done
    
    # Clean up chunk file
    rm chunk_$i.csv
    
    # Check progress
    IMPORTED_ROWS=$(PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -t -c "SELECT COUNT(*) FROM github_users;" | tr -d '[:space:]')
    PERCENTAGE=$((IMPORTED_ROWS * 100 / TOTAL_ROWS))
    echo "Progress: $IMPORTED_ROWS of $TOTAL_ROWS rows imported ($PERCENTAGE%)"
done

# Check if sync_status has already been imported
SYNC_COUNT=$(PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -t -c "SELECT COUNT(*) FROM sync_status;" | tr -d '[:space:]')
if [ "$SYNC_COUNT" -eq "0" ]; then
    # Export and import sync_status
    echo "Exporting sync_status from SQLite to CSV..."
    sqlite3 -csv $SQLITE_DB "SELECT * FROM sync_status;" > sync_status.csv

    echo "Importing sync_status to PostgreSQL..."
    PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy sync_status FROM 'sync_status.csv' WITH CSV"

    # Clean up
    rm -f sync_status.csv
else
    echo "sync_status table already has data, skipping import."
fi

echo "Migration completed successfully!" 