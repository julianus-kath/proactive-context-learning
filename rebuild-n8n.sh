#!/bin/bash

# Script to rebuild and restart the n8n Docker container

echo "Stopping all n8n instances..."
./stop-n8n.sh

echo "Rebuilding and restarting Docker containers..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "Waiting for containers to start..."
sleep 5

echo "Checking container status..."
docker-compose ps

echo "Checking n8n logs..."
docker-compose logs n8n | tail -n 20

echo ""
echo "If n8n started successfully, you can access it at: http://localhost:5678"
echo "If there are still issues, check the full logs with: docker-compose logs n8n"