#!/bin/bash

# This script rebuilds and restarts the services

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Remove any existing containers
echo "Removing existing containers..."
docker-compose rm -f

# Rebuild the services
echo "Rebuilding services..."
docker-compose build --no-cache

# Start all services
echo "Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
echo "This may take a minute or two..."
sleep 20

# Load MongoDB data directly
echo "Loading MongoDB data directly..."
# Copy the JavaScript file to the MongoDB container
docker cp scripts/generate_simple_mongodb_data.js $(docker-compose ps -q mongo):/generate_data.js || echo "Failed to copy MongoDB data script"
# Run the JavaScript file in the MongoDB shell
docker-compose exec -T mongo mongosh --file /generate_data.js || echo "Failed to load MongoDB data"

# Print the URLs and provider info
echo ""
echo "Services are ready! You can access:"
echo "- Chat Interface: http://localhost:8080"
echo "- API Documentation: http://localhost:8000/docs"
echo ""

# Show logs for debugging
echo ""
echo "Showing logs for debugging (press Ctrl+C to stop)..."
docker-compose logs -f