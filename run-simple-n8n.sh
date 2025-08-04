#!/bin/bash

# Script to run n8n using the simple Docker Compose file

echo "Stopping all n8n instances..."
./stop-n8n.sh

echo "Starting n8n with the simple Docker Compose file..."
docker-compose -f docker-compose-simple.yml down
docker-compose -f docker-compose-simple.yml up -d

echo "Waiting for containers to start..."
sleep 5

echo "Checking container status..."
docker-compose -f docker-compose-simple.yml ps

echo "Installing SQLite node in n8n container..."
docker-compose -f docker-compose-simple.yml exec n8n npm install -g n8n-nodes-sqlite3

echo "Restarting n8n container to apply changes..."
docker-compose -f docker-compose-simple.yml restart n8n

echo "Waiting for n8n to restart..."
sleep 5

echo "Checking n8n logs..."
docker-compose -f docker-compose-simple.yml logs n8n | tail -n 20

echo ""
echo "If n8n started successfully, you can access it at: http://localhost:5678"
echo "If there are still issues, check the full logs with: docker-compose -f docker-compose-simple.yml logs n8n"