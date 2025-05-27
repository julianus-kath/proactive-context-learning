#!/bin/bash

# This script builds Docker images directly using the Docker CLI
# instead of docker-compose, which might be hanging

echo "Building Docker images directly..."

# Build the MCP image
echo "Building MCP image..."
docker build -t mcp-api:latest -f Dockerfile.mcp .

# Build the docstore image
echo "Building docstore image..."
docker build -t mcp-docstore:latest -f Dockerfile.docstore .

# Build the frontend image
echo "Building frontend image..."
docker build -t mcp-frontend:latest -f Dockerfile.frontend .

echo "All images built successfully!"
echo "You can now run ./run_simple.sh to start the services."