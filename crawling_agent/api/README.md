# Crawling Agent API

This directory contains the API implementation for the crawling agent.

## Overview

The Crawling Agent API provides a natural language interface to the MCP servers. It accepts natural language queries, translates them into structured queries for different data sources, executes these queries using the MCP clients, and returns the combined results.

## Components

1. **API Server**: The main FastAPI application that handles HTTP requests
2. **Query Translator**: Translates natural language queries into structured queries
3. **Result Processor**: Processes and combines results from different data sources
4. **Models**: Pydantic models for request and response validation

## API Endpoints

### Root Endpoint

```
GET /
```

Returns basic API information.

### Health Check

```
GET /health
```

Checks the health of the API and its dependencies.

### Query Execution

```
POST /query
```

Executes a natural language query.

**Request Body:**
```json
{
  "query": "Find all expensive products",
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {}
}
```

**Response Example:**
```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "thought_process": "Analyzing query: 'Find all expensive products'...",
  "structured_queries": [
    {
      "source_type": "erp",
      "query_type": "SQL",
      "query": "SELECT * FROM products WHERE price > 100 ORDER BY price DESC",
      "parameters": {}
    },
    {
      "source_type": "document_storage",
      "query_type": "MONGODB",
      "query": "{\"price\": {\"$gt\": 100}}",
      "parameters": {"collection": "products"}
    },
    {
      "source_type": "knowledge_graph",
      "query_type": "SPARQL",
      "query": "PREFIX product: <http://example.org/product#>\nSELECT ?product ?name ?price\nWHERE {\n    ?product product:price ?price .\n    ?product product:name ?name .\n    FILTER(?price > 100)\n}\nORDER BY DESC(?price)",
      "parameters": {}
    }
  ],
  "results": [
    {
      "id": 1,
      "name": "Expensive Product 1",
      "price": 150.0,
      "category": "Electronics",
      "source": "erp"
    },
    {
      "id": 2,
      "name": "Expensive Product 2",
      "price": 200.0,
      "category": "Electronics",
      "source": "erp"
    }
  ],
  "execution_time_ms": 42.5,
  "status": "success"
}
```

## Running the API

To run the API server:

```bash
python -m crawling_agent.api.api --host localhost --port 8000
```

Or using Docker Compose:

```bash
docker-compose up -d crawling-agent-api
```

The API will be available at http://localhost:8000, with interactive documentation at http://localhost:8000/docs.

## Query Translation

The Query Translator component translates natural language queries into structured queries for different data sources. It currently supports:

- Product-related queries (e.g., "Find all expensive products")
- Employee-related queries (e.g., "Show me all employees in the sales department")
- Order-related queries (e.g., "List all completed orders")

The translation is based on pattern matching and keyword detection. In a production system, this would be replaced with a more sophisticated natural language understanding component, possibly using a large language model.

## Result Processing

The Result Processor component combines and processes results from different data sources. It adds a "source" field to each result to indicate which data source it came from, and merges all results into a single list.

In a production system, this would be enhanced with more sophisticated result processing, such as deduplication, ranking, and formatting.