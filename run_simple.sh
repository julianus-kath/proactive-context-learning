#!/bin/bash

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Start all services with environment variables from .env file
echo "Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
echo "This may take a minute or two..."
sleep 20

# Install MongoDB dependencies in the containers
echo "Installing MongoDB dependencies in the containers..."
docker-compose exec -T api pip install motor pymongo || echo "Failed to install dependencies in API container"
docker-compose exec -T docstore pip install motor pymongo || echo "Failed to install dependencies in docstore container"

# Populate the document store with synthetic data
echo "Populating the document store with synthetic data..."
docker-compose exec -T api python scripts/populate_document_store.py --erp-api-url http://erp:8001 --doc-api-url http://docstore:8002 || echo "Failed to populate document store"

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