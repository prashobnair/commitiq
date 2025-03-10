#!/bin/bash
# Script to migrate data from SQLite to PostgreSQL

# Exit on error
set -e

# Default values
SQLITE_DB="data/metrics_analysis.db"
PG_HOST="github-db.cdoa6qiyakw1.ap-south-1.rds.amazonaws.com"
PG_PORT=5432
PG_USER="commitiq_github"
PG_PASSWORD="6LH9GHzQfw3UDaoSBTNa"
PG_DB="github_data"
BATCH_SIZE=1000
DEBUG=false

# Display usage information
function show_usage {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --sqlite-db PATH      Path to SQLite database (default: $SQLITE_DB)"
    echo "  --pg-host HOST        PostgreSQL host (default: $PG_HOST)"
    echo "  --pg-port PORT        PostgreSQL port (default: $PG_PORT)"
    echo "  --pg-user USER        PostgreSQL username (default: $PG_USER)"
    echo "  --pg-password PASS    PostgreSQL password"
    echo "  --pg-db DB            PostgreSQL database name (default: $PG_DB)"
    echo "  --batch-size NUM      Batch size for data transfer (default: $BATCH_SIZE)"
    echo "  --debug               Enable debug mode"
    echo "  --help                Show this help message"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sqlite-db)
            SQLITE_DB="$2"
            shift 2
            ;;
        --pg-host)
            PG_HOST="$2"
            shift 2
            ;;
        --pg-port)
            PG_PORT="$2"
            shift 2
            ;;
        --pg-user)
            PG_USER="$2"
            shift 2
            ;;
        --pg-password)
            PG_PASSWORD="$2"
            shift 2
            ;;
        --pg-db)
            PG_DB="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Validate SQLite database exists
if [ ! -f "$SQLITE_DB" ]; then
    echo "Error: SQLite database not found at $SQLITE_DB"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Build the command
CMD="python migrate_to_rds.py --sqlite-db $SQLITE_DB --pg-host $PG_HOST --pg-port $PG_PORT --pg-user $PG_USER --pg-db $PG_DB --batch-size $BATCH_SIZE"

# Add debug flag if needed
if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

# Add password if provided
if [ -n "$PG_PASSWORD" ]; then
    CMD="$CMD --pg-password $PG_PASSWORD"
fi

# Run the migration script
echo "Starting migration from SQLite to PostgreSQL..."
echo "SQLite database: $SQLITE_DB"
echo "PostgreSQL host: $PG_HOST"
echo "PostgreSQL port: $PG_PORT"
echo "PostgreSQL user: $PG_USER"
echo "PostgreSQL database: $PG_DB"
echo "Batch size: $BATCH_SIZE"
echo "Debug: $DEBUG"
echo

echo "Running command: $CMD"
echo

# Run the command
$CMD

# Check if the command was successful
if [ $? -ne 0 ]; then
    echo "Migration failed with exit code $?"
    exit 1
fi

echo "Migration completed successfully" 