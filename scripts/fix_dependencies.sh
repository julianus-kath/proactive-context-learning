#!/bin/bash

# This script fixes the dependencies in the containers

# Install dependencies in the API container
echo "Installing dependencies in the API container..."
docker-compose exec -T api pip install aiohttp requests fastapi uvicorn pydantic python-dotenv openai motor pymongo faker

# Install dependencies in the docstore container
echo "Installing dependencies in the docstore container..."
docker-compose exec -T docstore pip install aiohttp requests fastapi uvicorn pydantic python-dotenv motor pymongo faker

echo "Dependencies installed successfully!"