#!/bin/bash

# Build just the docstore image
echo "Building docstore image..."
docker build -t mcp-docstore:latest -f Dockerfile.docstore .

echo "Docstore image built successfully!"