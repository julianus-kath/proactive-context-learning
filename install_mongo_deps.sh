#!/bin/bash

# Install MongoDB dependencies in the API container
echo "Installing MongoDB dependencies in the API container..."
docker-compose exec api pip install motor pymongo

# Install MongoDB dependencies in the docstore container
echo "Installing MongoDB dependencies in the docstore container..."
docker-compose exec docstore pip install motor pymongo

echo "MongoDB dependencies installed."