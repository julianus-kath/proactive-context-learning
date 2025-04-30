#!/bin/bash
docker-compose down
# Start the MCP servers
echo "Starting MCP servers..."
docker-compose up -d

# Wait for servers to be ready
echo "Waiting for servers to be ready..."
sleep 5

# Run the test script
echo "Running test script..."
docker-compose exec erp-server python test_mcp_servers.py --mock

# Print the URLs for the API documentation
echo ""
echo "API Documentation URLs:"
echo "Crawling Agent API: http://localhost:8000/docs"
echo "ERP Server: http://localhost:8001/docs"
echo "Document Storage Server: http://localhost:8002/docs"
echo "Knowledge Graph Server: http://localhost:8003/docs"
echo ""
echo "To stop the servers, run: docker-compose down"