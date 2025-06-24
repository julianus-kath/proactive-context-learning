# Model-Context Protocol (MCP) Implementation

This document describes the implementation of the Model-Context Protocol (MCP) in the crawling agent system.

## Overview

The crawling agent system uses MCP to expose data sources as services that can be queried by AI agents. The implementation follows the structure and patterns from Dave Ebbelaar's AI Cookbook "MCP Crash Course".

## Architecture

The system consists of three MCP servers:

1. **ERP Server**: Exposes SQL query tools over MCP, connected to a SQLite database.
2. **Document Storage Server**: Exposes MongoDB-style query tools over MCP, sourcing from a JSON file.
3. **Knowledge Graph Server**: Exposes graph query tools over MCP.

Each server has a corresponding connector that provides a client interface to interact with the server.

## Directory Structure

```
crawling_agent/
├─ servers/
│  ├─ resources/
│  │  ├─ erp_schema.json
│  │  ├─ document_storage_schema.json
│  │  ├─ knowledge_graph_schema.json
│  ├─ erp_server.py
│  ├─ document_storage_server.py
│  ├─ knowledge_graph_server.py
│  ├─ Dockerfile.erp
│  ├─ Dockerfile.document
│  ├─ Dockerfile.knowledge
├─ connectors/
│  ├─ mcp_erp_connector.py
│  ├─ mcp_document_storage_connector.py
│  ├─ mcp_knowledge_graph_connector.py
├─ base_server.py
├─ base_connector.py
├─ run_servers.py
```

## Servers

### Base MCP Server

The `BaseMCPServer` class provides common functionality for all MCP servers:

- Initialization with server name, host, and port
- Running the server with a specified transport

### ERP Server

The `ERPServer` class:

- Connects to a SQLite database
- Exposes SQL query tools over MCP
- Provides tools for executing SQL queries, getting table schemas, and listing tables

### Document Storage Server

The `DocumentStorageServer` class:

- Loads documents from a JSON file
- Exposes MongoDB-style query tools over MCP
- Provides tools for finding documents, listing collections, and getting collection info

### Knowledge Graph Server

The `KnowledgeGraphServer` class:

- Maintains a knowledge graph in memory
- Exposes graph query tools over MCP
- Provides tools for querying nodes and relationships, and getting node and relationship types

## Connectors

### Base MCP Connector

The `BaseMCPConnector` class provides common functionality for all MCP connectors:

- Connecting to an MCP server
- Listing available tools
- Calling tools on the server

### ERP Connector

The `MCPERPConnector` class:

- Connects to the ERP Server
- Provides methods for executing SQL queries, getting table schemas, and listing tables

### Document Storage Connector

The `MCPDocumentStorageConnector` class:

- Connects to the Document Storage Server
- Provides methods for finding documents, listing collections, and getting collection info

### Knowledge Graph Connector

The `MCPKnowledgeGraphConnector` class:

- Connects to the Knowledge Graph Server
- Provides methods for querying nodes and relationships, and getting node and relationship types

## Running the Servers

The `run_servers.py` script provides a command-line interface for running one or more servers:

```bash
# Run all servers
python -m crawling_agent.run_servers

# Run specific servers
python -m crawling_agent.run_servers --servers erp document
```

## Docker Support

Each server has a corresponding Dockerfile that can be used to build a Docker image. The `docker-compose.yml` file can be used to run all three servers in containers:

```bash
docker-compose up
```

## Testing

The `tests/test_mcp_servers.py` file contains unit and integration tests for the servers and connectors.