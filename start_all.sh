#!/bin/bash

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Start all services
echo "Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Print the URLs
echo ""
echo "Services are ready! You can access:"
echo "- Chat Interface: http://localhost:8080"
echo "- API Documentation: http://localhost:8000/docs"
echo ""
echo "To view logs, run: docker-compose logs -f"
echo "To stop all services, run: docker-compose down"