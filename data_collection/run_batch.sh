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
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Validate GitHub database exists
if [ ! -f "$GITHUB_DB" ]; then
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

# Run the collection script
echo "Starting batch collection of GitHub user metrics..."
echo "Batch size: $BATCH_SIZE"
echo "Workers: $WORKERS"
echo "GitHub database: $GITHUB_DB"
echo "Metrics database: $METRICS_DB"
echo "Resume: $RESUME"
echo "Debug: $DEBUG"
echo "Delay between batches: $DELAY seconds"
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