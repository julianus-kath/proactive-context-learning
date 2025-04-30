#!/bin/bash

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Start the services with OpenAI configuration
echo "Starting services with OpenAI configuration..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Print the URLs for the API documentation
echo ""
echo "API Documentation URLs:"
echo "Crawling Agent API: http://localhost:8000/docs"
echo "ERP Server: http://localhost:8001/docs"
echo "Document Storage Server: http://localhost:8002/docs"
echo "Knowledge Graph Server: http://localhost:8003/docs"
echo ""

# Run the test script
echo "Running test script..."
python test_openai_agent.py

echo ""
echo "To stop the services, run: docker-compose down"