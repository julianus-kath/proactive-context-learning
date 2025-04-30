#!/bin/bash

# Start the frontend server
echo "Starting frontend server..."
python frontend/server.py --port 8080

# The server will run in the foreground
# Press Ctrl+C to stop