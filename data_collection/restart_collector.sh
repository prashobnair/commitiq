#!/bin/bash

# Stop any running collector
echo "Stopping any running collector..."
./stop_collector.sh

# Wait a moment to ensure processes are stopped
sleep 5

# Create logs directory if it doesn't exist
mkdir -p logs

# Get the current date and time for the log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/collector_10k_${TIMESTAMP}.log"

# Run the collector with 100,000 users target, reduced batch size and workers
echo "Starting collector with target of 100,000 users..."
echo "Rate limit handling is enabled with improved handling"
echo "Using very conservative batch size and worker count to avoid rate limit issues"
echo "Logs will be written to ${LOG_FILE}"

# Run the collector in the background with very conservative settings
# Reduced batch size to 20 and workers to 2 to minimize rate limit issues
# Added --sleep parameter to add delay between API calls
# Added --batch-pause parameter to add delay between batches
nohup python3 new_collector.py --target-count 100000 --batch-size 100 --workers 2 --sleep 2 --batch-pause 20 > "${LOG_FILE}" 2>&1 &

# Get the process ID
PID=$!
echo "Collector started with PID ${PID}"
echo "${PID}" > logs/collector.pid

# Print environment information
echo "Database Host: ${DB_HOST}"
echo "Database Port: ${DB_PORT}"
echo "Database Name: ${DB_NAME}"
echo "Database User: ${DB_USER}"
echo "GitHub Token: ${GITHUB_TOKEN:0:10}..."

echo "Collector is running in the background with improved rate limit handling."
echo "To monitor progress, use: tail -f ${LOG_FILE}"
echo "To check rate limits, use: python3 check_rate_limits.py" 