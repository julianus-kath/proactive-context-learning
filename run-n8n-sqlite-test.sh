#!/bin/bash

# First, make sure no n8n instances are running
echo "Checking for running n8n instances..."
n8n_pid=$(ps aux | grep "n8n start" | grep -v grep | awk '{print $2}')
if [ ! -z "$n8n_pid" ]; then
    echo "Found running n8n instance with PID $n8n_pid. Stopping it..."
    kill $n8n_pid
    sleep 2
    if ps -p $n8n_pid > /dev/null; then
        echo "Process still running, force killing..."
        kill -9 $n8n_pid
    fi
fi

# Check if port 5678 is in use
port_check=$(lsof -i :5678 | grep LISTEN)
if [ ! -z "$port_check" ]; then
    echo "Port 5678 is in use. Attempting to free it..."
    port_pid=$(echo "$port_check" | awk '{print $2}')
    if [ ! -z "$port_pid" ]; then
        kill -9 $port_pid
        sleep 1
    fi
fi

# Stop any existing Docker containers
echo "Stopping any existing Docker containers..."
docker stop n8n-sqlite-test 2>/dev/null
docker rm n8n-sqlite-test 2>/dev/null

# Create data directory
mkdir -p n8n-test-data

# Start the container
echo "Starting n8n with SQLite support..."
docker-compose -f n8n-sqlite-test.yml up -d

# Wait for container to start
echo "Waiting for container to start..."
sleep 5

# Check container status
echo "Container status:"
docker ps | grep n8n-sqlite-test

# Show logs
echo "Container logs:"
docker logs n8n-sqlite-test

echo ""
echo "If n8n started successfully, you can access it at: http://localhost:5678"
echo ""
echo "To test SQLite with the test database:"
echo "1. Create a workflow with a SQLite node"
echo "2. Configure it with database path: /home/node/test.db"
echo "3. Use this query: SELECT * FROM test"
echo ""
echo "To test SQLite with your synthetic data:"
echo "1. Create a workflow with a SQLite node"
echo "2. Configure it with database path: /home/node/synthetic_data.db"
echo "3. Use this query: SELECT name FROM sqlite_master WHERE type='table'"
echo ""
echo "To view logs: docker logs -f n8n-sqlite-test"