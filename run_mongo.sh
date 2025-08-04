#!/bin/bash

# Generate MongoDB data if it doesn't exist
if [ ! -f "mongodb_data.json" ]; then
  echo "MongoDB data file not found. Generating it now..."
  python scripts/generate_simple_mongodb_data.py
fi

# Print MongoDB data info
echo "Using MongoDB data file: mongodb_data.json"
echo "MongoDB data file size: $(du -h mongodb_data.json | cut -f1)"

# Stop any running MongoDB container
echo "Stopping any running MongoDB container..."
docker-compose down mongo

# Start the MongoDB container
echo "Starting MongoDB container..."
docker-compose up -d mongo

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
sleep 10

# Load the pre-generated MongoDB data
echo "Loading pre-generated MongoDB data..."
# Copy the data file into the container
docker cp mongodb_data.json $(docker-compose ps -q mongo):/mongodb_data.json || echo "Failed to copy MongoDB data file"
# Copy the load script into the container
docker cp scripts/load_mongodb_data.sh $(docker-compose ps -q mongo):/load_mongodb_data.sh || echo "Failed to copy MongoDB load script"
# Run the load script
docker-compose exec -T mongo bash -c "chmod +x /load_mongodb_data.sh && /load_mongodb_data.sh"

echo "MongoDB is ready with pre-loaded data!"
echo "To stop MongoDB, run: docker-compose down mongo"