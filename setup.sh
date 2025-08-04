#!/bin/bash

# Create directories for n8n data if they don't exist
mkdir -p n8n-data

# Set environment variables for the synthetic data service
export DB_TYPE=sqlite
export DB_NAME=synthetic_data.db
export DB_PATH="$(pwd)/synthetic_data.db"

echo "Generating synthetic data..."
# Run the synthetic data generator to create the SQLite database
python -m synthetic_data_service.main --customers 50 --products 100 --suppliers 20 --employees 30 --sales 200 --drop-tables

# Check if the database was created successfully
if [ -f "synthetic_data.db" ]; then
    echo "✅ SQLite database created successfully at: $(pwd)/synthetic_data.db"
else
    echo "❌ Failed to create SQLite database"
    exit 1
fi

echo "Setting up Docker environment..."
# Create a .env file for Docker Compose if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file for Docker Compose..."
    echo "# Environment variables for Docker Compose" > .env
    echo "OPENAI_API_KEY=${OPENAI_API_KEY}" >> .env
    echo "# Add other environment variables as needed" >> .env
fi

echo "Setup complete! You can now run: docker-compose up"
echo ""
echo "Access n8n at: http://localhost:5678"
echo "Access chatbot interface at: http://localhost:8080"