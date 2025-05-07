#!/bin/bash

# Stop any running services
echo "Stopping any running services..."
docker-compose down

# Remove all images to force a complete rebuild
echo "Removing Docker images to force rebuild..."
docker-compose rm -f

# Rebuild the services with no cache
echo "Rebuilding services with no cache..."
docker-compose build --no-cache

echo "Build completed. Run ./run.sh to start the services."