# MCP Servers

This directory contains the Model-Context Protocol (MCP) server implementations for the crawling agent system.

## Overview

The MCP servers provide standardized access to different data sources:

1. **ERP Server**: Provides SQL query capabilities for ERP data
2. **Document Storage Server**: Provides MongoDB query capabilities for document data
3. **Knowledge Graph Server**: Provides SPARQL query capabilities for knowledge graph data

Each server exposes a set of REST API endpoints that follow the MCP specification.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the Servers

To run all MCP servers:

```bash
python run_servers.py --mock
```

This will start the following servers:
- ERP Server: http://localhost:8001
- Document Storage Server: http://localhost:8002
- Knowledge Graph Server: http://localhost:8003

### Command-line Options

- `--host`: Host to bind the servers to (default: localhost)
- `--erp-port`: Port for the ERP server (default: 8001)
- `--doc-port`: Port for the Document Storage server (default: 8002)
- `--kg-port`: Port for the Knowledge Graph server (default: 8003)
- `--config`: Path to the configuration file
- `--mock`: Run in mock mode (no actual database connections)

## API Documentation

Each server provides interactive API documentation at the `/docs` endpoint:
- ERP Server API Docs: http://localhost:8001/docs
- Document Storage Server API Docs: http://localhost:8002/docs
- Knowledge Graph Server API Docs: http://localhost:8003/docs

For detailed API documentation, see [api_docs.md](api_docs.md).

## Testing

To test the MCP implementation:

```bash
python ../../test_mcp_servers.py --mock
```

This script will test all three connectors and their interactions with the servers.

## Configuration

The servers can be configured using a YAML configuration file. By default, they look for a configuration file at `../config/config.yaml`.

Example configuration:

```yaml
data_sources:
  erp:
    host: localhost
    port: 8001
    uri: sqlite:///path/to/erp.db
  
  document_storage:
    host: localhost
    port: 8002
    uri: mongodb://localhost:27017
    database: document_storage
  
  knowledge_graph:
    host: localhost
    port: 8003
    endpoint: http://localhost:3030/kg/sparql
```

## Architecture

The MCP servers follow a client-server architecture:

1. **MCP Servers**: Lightweight servers that expose data source capabilities
2. **MCP Clients**: Connectors that communicate with the servers
3. **Host Application**: The crawling agent that orchestrates the entire process

For more information about the architecture, see the [Model-Context Protocol ADR](../../adrs/0005-model-context-protocol.md).