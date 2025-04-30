# Crawling Agent with LLM-Powered Agent and MCP Implementation

This repository contains an implementation of the Model-Context Protocol (MCP) for the crawling agent system, along with an LLM-powered agent for natural language query processing.

## Overview

The system consists of:

1. **MCP Servers**: Provide standardized access to different data sources
   - ERP Server (SQL)
   - Document Storage Server (MongoDB)
   - Knowledge Graph Server (SPARQL)

2. **Crawling Agent API**: Provides a natural language interface to the MCP servers
   - LLM-powered agent for query understanding and translation
   - Tool-based architecture for interacting with data sources
   - Modular LLM provider interface supporting different backends

## Running with Docker

The easiest way to run the system is using Docker Compose:

```bash
# Start all services
docker-compose up -d

# Check the status of the services
docker-compose ps

# View logs
docker-compose logs -f
```

Once the services are running, you can access:
- The chat interface at: http://localhost:8080
- The API documentation at: http://localhost:8000/docs

## LLM Integration

The system supports different LLM providers through a modular interface:

- **OpenAI**: Uses the OpenAI API (GPT-4, GPT-3.5, etc.)
- **Mock**: A mock provider for testing purposes (default)

To use the OpenAI provider:

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file to set your OpenAI API key:
   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Start the services with the environment variables:
   ```bash
   docker-compose up -d
   ```

## Testing the Implementation

To test the implementation, you can use the provided test script:

```bash
# Run the test script
./docker-test.sh
```

This script will:
1. Start all services
2. Wait for them to be ready
3. Run the test script
4. Print the URLs for the API documentation

## API Documentation

The system provides interactive API documentation at the `/docs` endpoint for each service:

- Crawling Agent API: http://localhost:8000/docs
- ERP Server: http://localhost:8001/docs
- Document Storage Server: http://localhost:8002/docs
- Knowledge Graph Server: http://localhost:8003/docs

## Using the Natural Language Query API

You can use the Crawling Agent API to execute natural language queries:

```bash
curl -X 'POST' \
  'http://localhost:8000/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "How many customers do we have?",
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {}
}'
```

Or use the interactive API documentation at http://localhost:8000/docs to try out queries.

Example queries:
- "How many customers do we have?"
- "Find all expensive products"
- "Show me all employees in the sales department"
- "List all completed orders"
- "What is the total revenue from orders this month?"

## Implementation Details

For more information about the implementation, see:

- [MCP_IMPLEMENTATION.md](MCP_IMPLEMENTATION.md): Overview of the MCP implementation
- [adrs/0005-model-context-protocol.md](adrs/0005-model-context-protocol.md): Architecture Decision Record
- [crawling_agent/servers/api_docs.md](crawling_agent/servers/api_docs.md): MCP servers API documentation
- [crawling_agent/api/README.md](crawling_agent/api/README.md): Crawling Agent API documentation
- [crawling_agent/agent/README.md](crawling_agent/agent/README.md): Agent implementation details
- [crawling_agent/llm/provider.py](crawling_agent/llm/provider.py): LLM provider interface and implementations

## Stopping the Services

To stop all services:

```bash
docker-compose down
```