#!/bin/bash

# Setup script for n8n with SQLite database
# This script stops any running n8n instances, generates synthetic data, and prepares the environment for n8n

echo "Checking for running n8n instances..."
# Find and kill any running n8n processes
n8n_pid=$(ps aux | grep "n8n start" | grep -v grep | awk '{print $2}')
if [ ! -z "$n8n_pid" ]; then
    echo "Found running n8n instance with PID $n8n_pid. Stopping it..."
    kill $n8n_pid
    sleep 2
    # Check if it's still running and force kill if necessary
    if ps -p $n8n_pid > /dev/null; then
        echo "Process still running, force killing..."
        kill -9 $n8n_pid
    fi
    echo "n8n process stopped."
else
    echo "No running n8n instances found."
fi

# Check if port 5678 is still in use
port_check=$(lsof -i :5678 | grep LISTEN)
if [ ! -z "$port_check" ]; then
    echo "⚠️ Port 5678 is still in use by another process. Please stop it manually."
    echo "$port_check"
    exit 1
fi

# Stop any running Docker containers
echo "Stopping any running Docker containers..."
docker-compose down 2>/dev/null

# Create directories for n8n data if they don't exist
mkdir -p n8n-data

# Set environment variables for the synthetic data service
export DB_TYPE=sqlite
export DB_NAME=synthetic_data.db

echo "Generating synthetic data..."
# Run the synthetic data generator to create the SQLite database
python -m synthetic_data_service.main --customers 50 --products 100 --suppliers 20 --employees 30 --sales 200 --drop-tables

# Check if the database was created successfully
if [ -f "synthetic_data.db" ]; then
    echo "✅ SQLite database created successfully at: $(pwd)/synthetic_data.db"
    # Make sure the database is readable by Docker
    chmod 644 synthetic_data.db
else
    echo "❌ Failed to create SQLite database"
    exit 1
fi

# Create a .env file for Docker Compose if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file for Docker Compose..."
    
    # Check if OPENAI_API_KEY is set
    if [ -z "$OPENAI_API_KEY" ]; then
        echo "⚠️ OPENAI_API_KEY environment variable is not set."
        echo "Please enter your OpenAI API key:"
        read -s api_key
        echo "OPENAI_API_KEY=$api_key" > .env
    else
        echo "OPENAI_API_KEY=$OPENAI_API_KEY" > .env
    fi
    
    echo "# Add other environment variables as needed" >> .env
    echo "✅ .env file created"
else
    echo "ℹ️ .env file already exists, skipping creation"
fi

echo ""
echo "Setup complete! You can now run: docker-compose up -d"
echo ""
echo "Access n8n at: http://localhost:5678"
echo "Access chatbot interface at: http://localhost:8080"
echo ""
echo "To test the webhook, use the following curl command:"
echo "curl -X POST -H \"Content-Type: application/json\" -d '{\"query\": \"Show me the top 5 customers\"}' http://localhost:5678/webhook-test/37694deb-f310-4a1e-b198-aaff97f28e8d"