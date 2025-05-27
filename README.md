# Crawling Agent with Proactive Context Learning

This repository contains an implementation of a Crawling Agent with Proactive Context Learning capabilities, using the Model-Context Protocol (MCP) for structured interactions.

## Overview

The system consists of:

1. **API / Tool Layer**: Clean, typed, easily extensible
   - SQLTool for database queries
   - Placeholder implementations for DocTool and KGTool

2. **Crawling Agent**: Re-implemented to use real tools only (no mocks)
   - Uses the Model-Context Protocol (MCP)
   - Generates SQL queries from natural language
   - Provides detailed logging of each step

3. **Fusion Agent (stub)**: Minimal, transparent passthrough
   - Simple implementation that will be enhanced in future sprints

4. **Demo SQL DB service**: Hardened REST endpoint
   - Provides metadata about the database
   - Executes SQL queries
   - Returns results in a structured format

## Quick Start

The easiest way to run the system is using the provided script:

```bash
./run.sh
```

This script will:
1. Stop any running services
2. Rebuild the services to apply code changes
3. Verify the database file exists
4. Start all services
5. Wait for them to be ready
6. Print the URLs for the API documentation and chat interface

## Running with Docker

If you prefer to run the Docker commands manually:

```bash
# Stop any running services
docker-compose down

# Rebuild the services
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

Once the services are running, you can access:
- The chat interface at: http://localhost:8080
- The API documentation at: http://localhost:8000/docs

## LLM Integration

The system supports different LLM providers through a modular interface:

- **OpenAI**: Uses the OpenAI API (GPT-4, GPT-3.5, etc.)

To use the OpenAI provider:

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file to set your OpenAI API key:
   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4
   ```

3. Start the services with the environment variables:
   ```bash
   ./run.sh
   ```

## Testing the Implementation

You can test the implementation by:

1. Running the system with the `run.sh` script
2. Using the web interface at http://localhost:8080
3. Using the API directly at http://localhost:8000/query
4. Using the interactive API documentation at http://localhost:8000/docs

## API Documentation

The system provides interactive API documentation at the `/docs` endpoint for each service:

- Crawling Agent API: http://localhost:8000/docs
- ERP API: http://localhost:8001/docs

## Using the Natural Language Query API

You can use the Crawling Agent API to execute natural language queries:

```bash
curl -X 'POST' \
  'http://localhost:8000/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "How many customers do we have?",
  "query_id": "550e8400-e29b-41d4-a716-446655440000"
}'
```

Or use the interactive API documentation at http://localhost:8000/docs to try out queries.

Example queries:
- "How many customers do we have?"
- "Find all expensive products"
- "Show me all employees in the sales department"
- "List all completed orders"
- "What is the total revenue from orders this month?"

## Web Interface

The system includes a simple web interface for interacting with the agent:

- Web UI: http://localhost:8080

## Architecture

The system follows the Model-Context Protocol (MCP) architecture:

1. **Planning Phase**: Translating natural language queries into structured plans and actions
2. **Acting Phase**: Executing the planned actions against data sources
3. **Observing Phase**: Collecting and processing the results of actions

## Logs

The system logs all operations to the `logs` directory. Each query execution creates a new log file with detailed information about the process.

## Stopping the Services

To stop all services:

```bash
docker-compose down
```