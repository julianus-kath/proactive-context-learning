#!/bin/bash
# Script to load MongoDB data directly using a JavaScript file

echo "Loading MongoDB data directly..."

# Copy the JavaScript file to the MongoDB container
docker cp scripts/generate_simple_mongodb_data.js $(docker-compose ps -q mongo):/generate_data.js

# Run the JavaScript file in the MongoDB shell
docker-compose exec -T mongo mongosh --file /generate_data.js

echo "MongoDB data loaded successfully!"