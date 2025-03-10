#!/bin/bash
# Script to run batch data collection for GitHub users

# Exit on error
set -e

# Default values
BATCH_SIZE=100
WORKERS=16
GITHUB_DB="../github_user_db/data/github_users.db"
METRICS_DB="data/metrics_analysis.db"
RESUME=false
DEBUG=false
DELAY=10  # Default delay between batches in seconds
USE_POSTGRES=false
PG_HOST="localhost"
PG_PORT=5432
PG_USER="postgres"
PG_PASSWORD=""
PG_DB="github_data"

# Display usage information
function show_usage {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --batch-size NUM      Number of users to process (default: $BATCH_SIZE)"
    echo "  --workers NUM         Number of parallel workers (default: $WORKERS)"
    echo "  --github-db PATH      Path to GitHub users database (default: $GITHUB_DB)"
    echo "  --metrics-db PATH     Path to metrics database (default: $METRICS_DB)"
    echo "  --resume              Resume from the last checkpoint"
    echo "  --debug               Enable debug mode"
    echo "  --delay SECONDS       Delay in seconds between batches (default: $DELAY)"
    echo "  --use-postgres        Use PostgreSQL instead of SQLite"
    echo "  --pg-host HOST        PostgreSQL host (default: $PG_HOST)"
    echo "  --pg-port PORT        PostgreSQL port (default: $PG_PORT)"
    echo "  --pg-user USER        PostgreSQL username (default: $PG_USER)"
    echo "  --pg-password PASS    PostgreSQL password"
    echo "  --pg-db DB            PostgreSQL database name (default: $PG_DB)"
    echo "  --help                Show this help message"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --github-db)
            GITHUB_DB="$2"
            shift 2
            ;;
        --metrics-db)
            METRICS_DB="$2"
            shift 2
            ;;
        --resume)
            RESUME=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --delay)
            DELAY="$2"
            shift 2
            ;;
        --use-postgres)
            USE_POSTGRES=true
            shift
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
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Validate GitHub database exists if not using PostgreSQL
if [ "$USE_POSTGRES" = false ] && [ ! -f "$GITHUB_DB" ]; then
    echo "Error: GitHub database not found at $GITHUB_DB"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data
mkdir -p logs

# Build the command
CMD="python collect_batch.py --batch-size $BATCH_SIZE --workers $WORKERS --github-db $GITHUB_DB --metrics-db $METRICS_DB"

# Add resume flag if needed
if [ "$RESUME" = true ]; then
    CMD="$CMD --resume"
fi

# Add debug flag if needed
if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

# Add PostgreSQL flags if needed
if [ "$USE_POSTGRES" = true ]; then
    CMD="$CMD --use-postgres --pg-host $PG_HOST --pg-port $PG_PORT --pg-user $PG_USER --pg-db $PG_DB"
    
    # Add password if provided
    if [ -n "$PG_PASSWORD" ]; then
        CMD="$CMD --pg-password $PG_PASSWORD"
    fi
fi

# Run the collection script
echo "Starting batch collection of GitHub user metrics..."
echo "Batch size: $BATCH_SIZE"
echo "Workers: $WORKERS"
echo "GitHub database: $GITHUB_DB"
echo "Metrics database: $METRICS_DB"
echo "Resume: $RESUME"
echo "Debug: $DEBUG"
echo "Delay between batches: $DELAY seconds"
echo "Use PostgreSQL: $USE_POSTGRES"
if [ "$USE_POSTGRES" = true ]; then
    echo "PostgreSQL host: $PG_HOST"
    echo "PostgreSQL port: $PG_PORT"
    echo "PostgreSQL user: $PG_USER"
    echo "PostgreSQL database: $PG_DB"
fi
echo

echo "Running command: $CMD"
echo

# Run the command in a loop with delay between batches
while true; do
    echo "Starting batch collection at $(date)"
    $CMD
    
    # Check if the command was successful
    if [ $? -ne 0 ]; then
        echo "Batch collection failed with exit code $?"
        exit 1
    fi
    
    echo "Batch completed. Waiting $DELAY seconds before starting next batch..."
    sleep $DELAY
done 