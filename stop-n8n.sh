#!/bin/bash

# Script to stop all n8n instances (both Docker and standalone)

echo "Stopping all n8n instances..."

# Stop Docker containers
echo "Stopping Docker containers..."
docker-compose down 2>/dev/null

# Find and kill any standalone n8n processes
echo "Checking for standalone n8n processes..."
n8n_pids=$(ps aux | grep "n8n start" | grep -v grep | awk '{print $2}')

if [ ! -z "$n8n_pids" ]; then
    echo "Found running n8n instances with PIDs: $n8n_pids"
    
    for pid in $n8n_pids; do
        echo "Stopping n8n process with PID $pid..."
        kill $pid
        sleep 1
        
        # Check if it's still running and force kill if necessary
        if ps -p $pid > /dev/null; then
            echo "Process still running, force killing..."
            kill -9 $pid
            sleep 1
        fi
    done
    
    echo "All n8n processes stopped."
else
    echo "No standalone n8n processes found."
fi

# Check if port 5678 is still in use
port_check=$(lsof -i :5678 | grep LISTEN)
if [ ! -z "$port_check" ]; then
    echo "⚠️ Port 5678 is still in use by another process:"
    echo "$port_check"
    
    # Try to identify and kill the process
    port_pid=$(echo "$port_check" | awk '{print $2}')
    if [ ! -z "$port_pid" ]; then
        echo "Attempting to kill process with PID $port_pid..."
        kill $port_pid
        sleep 1
        
        # Check if it's still running and force kill if necessary
        if ps -p $port_pid > /dev/null; then
            echo "Process still running, force killing..."
            kill -9 $port_pid
            sleep 1
        fi
        
        # Check if port is now free
        if lsof -i :5678 | grep LISTEN > /dev/null; then
            echo "⚠️ Port 5678 is still in use. Please investigate manually."
        else
            echo "✅ Port 5678 is now free."
        fi
    fi
else
    echo "✅ Port 5678 is free."
fi

echo "Done."