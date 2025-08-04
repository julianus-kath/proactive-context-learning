#!/bin/bash

# Script to test the SQLite database connection in n8n

echo "Testing SQLite database connection in n8n..."

# Check if the database file exists
if [ ! -f "synthetic_data.db" ]; then
    echo "❌ SQLite database file not found. Please run setup-n8n.sh first."
    exit 1
fi

echo "✅ SQLite database file exists: $(pwd)/synthetic_data.db"

# Check if n8n is running in Docker
if ! docker ps | grep n8n > /dev/null; then
    echo "❌ n8n Docker container is not running. Please start it with: docker-compose up -d"
    exit 1
fi

echo "✅ n8n Docker container is running"

# Check if the SQLite database is mounted in the container
if ! docker exec $(docker ps -q -f name=n8n) ls -la /home/node/synthetic_data.db > /dev/null; then
    echo "❌ SQLite database is not properly mounted in the container."
    exit 1
fi

echo "✅ SQLite database is properly mounted in the container"

# Check if the SQLite3 node is installed
if ! docker exec $(docker ps -q -f name=n8n) npm list -g n8n-nodes-sqlite3 | grep n8n-nodes-sqlite3 > /dev/null; then
    echo "❌ SQLite3 node is not installed in the container."
    exit 1
fi

echo "✅ SQLite3 node is installed in the container"

echo ""
echo "All checks passed! Your n8n instance should be able to connect to the SQLite database."
echo ""
echo "To test the connection in n8n:"
echo "1. Create a new workflow"
echo "2. Add a SQLite node"
echo "3. Configure it with database path: /home/node/synthetic_data.db"
echo "4. Use this test query: SELECT name FROM sqlite_master WHERE type='table';"
echo "5. Execute the node to see the tables in your database"
echo ""
echo "If you encounter any issues, run the stop-n8n.sh script and then setup-n8n.sh again."