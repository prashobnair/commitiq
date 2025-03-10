#!/bin/bash
set -e

# Enable debugging
set -x

# Configuration
PG_HOST="github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT="5432"
PG_USER="commitiq_github"
PG_PASSWORD="6LH9GHzQfw3UDaoSBTNa"
PG_DB="github_data"
SQLITE_DB="github_users.db"
CHUNK_SIZE=10000  # Reduced chunk size for better reliability
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

# Track imported rows locally instead of querying the database each time
IMPORTED_ROWS=$CURRENT_ROWS

for ((i=START_OFFSET; i<$TOTAL_ROWS; i+=$CHUNK_SIZE)); do
    CHUNK_NUM=$((i / CHUNK_SIZE + 1))
    TOTAL_CHUNKS=$((TOTAL_ROWS / CHUNK_SIZE + 1))
    
    echo "Processing chunk $CHUNK_NUM of $TOTAL_CHUNKS..."
    
    # Export chunk from SQLite to CSV
    echo "Exporting chunk from SQLite to CSV..."
    sqlite3 -csv $SQLITE_DB "SELECT * FROM github_users LIMIT $CHUNK_SIZE OFFSET $i;" > chunk_$i.csv
    
    # Check if the CSV file was created successfully
    if [ ! -f "chunk_$i.csv" ]; then
        echo "Error: Failed to create CSV file for chunk $CHUNK_NUM"
        exit 1
    fi
    
    # Check the size of the CSV file
    CSV_SIZE=$(wc -c < "chunk_$i.csv")
    echo "CSV file size: $CSV_SIZE bytes"
    
    # Import chunk to PostgreSQL with minimal retry logic
    MAX_RETRIES=3
    RETRY_COUNT=0
    IMPORT_SUCCESS=false
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$IMPORT_SUCCESS" = false ]; do
        echo "Importing chunk to PostgreSQL (attempt $((RETRY_COUNT + 1)) of $MAX_RETRIES)..."
        if PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -c "\copy github_users FROM 'chunk_$i.csv' WITH CSV" 2>import_error.log; then
            IMPORT_SUCCESS=true
            # Update local counter instead of querying the database
            IMPORTED_ROWS=$((IMPORTED_ROWS + CHUNK_SIZE))
            if [ $IMPORTED_ROWS -gt $TOTAL_ROWS ]; then
                IMPORTED_ROWS=$TOTAL_ROWS
            fi
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo "Import error:"
            cat import_error.log
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Import failed. Retrying in 2 seconds..."
                sleep 2
            else
                echo "Import failed after $MAX_RETRIES attempts. Exiting."
                exit 1
            fi
        fi
    done
    
    # Clean up chunk file
    rm chunk_$i.csv
    
    # Report progress using local counter
    PERCENTAGE=$((IMPORTED_ROWS * 100 / TOTAL_ROWS))
    echo "Progress: $IMPORTED_ROWS of $TOTAL_ROWS rows imported ($PERCENTAGE%)"
    
done

# Final verification
FINAL_COUNT=$(PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -U $PG_USER -d $PG_DB -p $PG_PORT -t -c "SELECT COUNT(*) FROM github_users;" | tr -d '[:space:]')
echo "Final verification: $FINAL_COUNT rows imported"

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