# MCP Servers API Documentation

This document provides detailed information about the API endpoints exposed by the MCP servers.

## Overview

The Model-Context Protocol (MCP) implementation consists of three servers:

1. **ERP Server**: Provides SQL query capabilities for ERP data
2. **Document Storage Server**: Provides MongoDB query capabilities for document data
3. **Knowledge Graph Server**: Provides SPARQL query capabilities for knowledge graph data

Each server exposes a set of REST API endpoints that follow the MCP specification.

## Common Endpoints

All MCP servers expose the following common endpoints:

### Root Endpoint

```
GET /
```

Returns basic server information.

**Response Example:**
```json
{
  "server": "MCP ERP Server",
  "version": "1.0.0",
  "status": "online"
}
```

### Server Information

```
GET /info
```

Returns detailed server information.

**Response Example:**
```json
{
  "server_type": "ERP",
  "version": "1.0.0",
  "capabilities": ["query", "schema", "tables"],
  "query_types": ["SQL"],
  "status": "online"
}
```

### Query Execution

```
POST /query
```

Executes a query against the data source.

**Request Body:**
```json
{
  "query": "SELECT * FROM products WHERE price > 100",
  "query_type": "SQL",
  "parameters": {},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Example:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": [
    {
      "id": 1,
      "name": "Expensive Product 1",
      "price": 150.0,
      "category": "Electronics"
    },
    {
      "id": 2,
      "name": "Expensive Product 2",
      "price": 200.0,
      "category": "Electronics"
    }
  ],
  "metadata": {
    "row_count": 2,
    "columns": ["id", "name", "price", "category"],
    "execution_time_ms": 42.5
  },
  "status": "success"
}
```

### Health Check

```
GET /health
```

Checks if the server is healthy.

**Response Example:**
```json
{
  "status": "healthy"
}
```

## ERP Server Endpoints

The ERP server exposes the following additional endpoints:

### Get Tables

```
GET /tables
```

Returns a list of tables in the ERP database.

**Response Example:**
```json
{
  "tables": ["products", "employees", "orders", "order_items"]
}
```

### Get Table Schema

```
GET /schema/{table_name}
```

Returns the schema for a specific table.

**Response Example:**
```json
{
  "table": "products",
  "schema": [
    {
      "cid": 0,
      "name": "id",
      "type": "INTEGER",
      "notnull": 0,
      "default_value": null,
      "pk": 1
    },
    {
      "cid": 1,
      "name": "name",
      "type": "TEXT",
      "notnull": 1,
      "default_value": null,
      "pk": 0
    },
    {
      "cid": 2,
      "name": "price",
      "type": "REAL",
      "notnull": 1,
      "default_value": null,
      "pk": 0
    }
  ]
}
```

## Document Storage Server Endpoints

The Document Storage server exposes the following additional endpoints:

### Get Collections

```
GET /collections
```

Returns a list of collections in the document database.

**Response Example:**
```json
{
  "collections": ["products", "orders", "customers"]
}
```

### Get Collection Schema

```
GET /schema/{collection_name}
```

Returns the schema for a specific collection.

**Response Example:**
```json
{
  "collection": "products",
  "schema": {
    "type": "object",
    "properties": {
      "_id": {"type": "string"},
      "name": {"type": "string"},
      "description": {"type": "string"},
      "price": {"type": "number"},
      "category": {"type": "string"},
      "tags": {"type": "array", "items": {"type": "string"}},
      "specifications": {"type": "object"}
    }
  }
}
```

## Knowledge Graph Server Endpoints

The Knowledge Graph server exposes the following additional endpoints:

### Get Namespaces

```
GET /namespaces
```

Returns a list of namespaces in the knowledge graph.

**Response Example:**
```json
{
  "namespaces": {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "product": "http://example.org/product#",
    "employee": "http://example.org/employee#",
    "company": "http://example.org/company#"
  }
}
```

### Get Classes

```
GET /classes
```

Returns a list of classes in the knowledge graph.

**Response Example:**
```json
{
  "classes": [
    {"class": "http://example.org/product#Product", "count": 5},
    {"class": "http://example.org/employee#Employee", "count": 5},
    {"class": "http://example.org/company#Department", "count": 3}
  ]
}
```

### Get Properties

```
GET /properties/{class_uri}
```

Returns the properties for a specific class.

**Response Example:**
```json
{
  "class": "http://example.org/product#Product",
  "properties": [
    {"property": "http://example.org/product#name", "type": "http://www.w3.org/2001/XMLSchema#string"},
    {"property": "http://example.org/product#price", "type": "http://www.w3.org/2001/XMLSchema#decimal"},
    {"property": "http://example.org/product#category", "type": "http://www.w3.org/2001/XMLSchema#string"}
  ]
}
```

## Running the Servers

To run all MCP servers:

```bash
python -m crawling_agent.servers.run_servers --mock
```

This will start the following servers:
- ERP Server: http://localhost:8001
- Document Storage Server: http://localhost:8002
- Knowledge Graph Server: http://localhost:8003

Each server provides interactive API documentation at the `/docs` endpoint:
- ERP Server API Docs: http://localhost:8001/docs
- Document Storage Server API Docs: http://localhost:8002/docs
- Knowledge Graph Server API Docs: http://localhost:8003/docs

## Testing the Servers

To test the MCP implementation:

```bash
python test_mcp_servers.py --mock
```

This script will test all three connectors and their interactions with the servers.