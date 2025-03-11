#!/bin/bash

# Check if the PID file exists
if [ -f logs/collector.pid ]; then
    # Read the PID from the file
    PID=$(cat logs/collector.pid)
    
    # Check if the process is running
    if ps -p $PID > /dev/null; then
        echo "Stopping collector process with PID ${PID}..."
        kill $PID
        
        # Wait for the process to terminate
        for i in {1..10}; do
            if ! ps -p $PID > /dev/null; then
                echo "Collector process stopped successfully."
                rm logs/collector.pid
                exit 0
            fi
            echo "Waiting for process to terminate... ($i/10)"
            sleep 1
        done
        
        # If the process is still running after 10 seconds, force kill it
        echo "Process still running after 10 seconds. Force killing..."
        kill -9 $PID
        if ! ps -p $PID > /dev/null; then
            echo "Collector process force killed."
            rm logs/collector.pid
            exit 0
        else
            echo "Failed to kill process. Please check manually."
            exit 1
        fi
    else
        echo "No collector process running with PID ${PID}."
        rm logs/collector.pid
        exit 0
    fi
else
    # If PID file doesn't exist, try to find the process by name
    PID=$(ps aux | grep "python3 new_collector.py" | grep -v grep | awk '{print $2}')
    
    if [ -n "$PID" ]; then
        echo "Found collector process with PID ${PID}..."
        kill $PID
        echo "Collector process stopped."
        exit 0
    else
        echo "No collector process found."
        exit 0
    fi
fi 