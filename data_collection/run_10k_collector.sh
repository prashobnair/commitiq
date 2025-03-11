#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Get the current date and time for the log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/collector_10k_${TIMESTAMP}.log"

# Run the collector with 10,000 users target, 100 batch size, and 8 workers
echo "Starting collector with target of 10,000 users..."
echo "Rate limit handling is enabled - collector will pause when approaching GitHub API limits"
echo "Logs will be written to ${LOG_FILE}"

# Run the collector in the background
nohup python3 new_collector.py --target-count 10000 --batch-size 100 --workers 8 > "${LOG_FILE}" 2>&1 &

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

echo "Collector is running in the background. Use ./stop_collector.sh to stop it."
echo "To monitor progress, use: tail -f ${LOG_FILE}" 