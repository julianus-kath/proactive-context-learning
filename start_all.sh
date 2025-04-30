#!/bin/bash

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Rebuild the services to apply code changes
echo "Rebuilding services..."
docker-compose build

# Start all services with environment variables from .env file
echo "Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Print the URLs and provider info
echo ""
echo "Services are ready! You can access:"
echo "- Chat Interface: http://localhost:8080"
echo "- API Documentation: http://localhost:8000/docs"
echo ""

# Get the LLM provider from .env file
LLM_PROVIDER=$(grep "LLM_PROVIDER" .env | cut -d '=' -f2)
echo "Using LLM provider: $LLM_PROVIDER"

if [ "$LLM_PROVIDER" = "openai" ]; then
  echo "OpenAI API key is configured in .env file."
  echo "OpenAI model: $(grep "OPENAI_MODEL" .env | cut -d '=' -f2)"
fi

echo ""
echo "To view logs, run: docker-compose logs -f"
echo "To stop all services, run: docker-compose down"

# Show logs for debugging
echo ""
echo "Showing logs for debugging (press Ctrl+C to stop)..."
docker-compose logs -f