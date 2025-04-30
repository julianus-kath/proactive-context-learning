# Model-Context Protocol (MCP) Implementation

This document provides an overview of the Model-Context Protocol (MCP) implementation for the crawling agent system.

## Overview

We've implemented the Model-Context Protocol (MCP) as a client-server architecture for the crawling agent system. This implementation allows the system to interact with multiple heterogeneous data sources in a consistent and maintainable way.

## Components

### MCP Servers

We've created three MCP servers:

1. **ERP Server**: Provides SQL query capabilities for ERP data
   - File: `crawling_agent/servers/erp_server.py`
   - Default Port: 8001

2. **Document Storage Server**: Provides MongoDB query capabilities for document data
   - File: `crawling_agent/servers/document_storage_server.py`
   - Default Port: 8002

3. **Knowledge Graph Server**: Provides SPARQL query capabilities for knowledge graph data
   - File: `crawling_agent/servers/knowledge_graph_server.py`
   - Default Port: 8003

Each server exposes a set of REST API endpoints that follow the MCP specification.

### MCP Clients

We've created three MCP clients (connectors):

1. **ERP Connector**: Client for the ERP server
   - File: `crawling_agent/connectors/mcp_erp_connector.py`

2. **Document Storage Connector**: Client for the Document Storage server
   - File: `crawling_agent/connectors/mcp_document_storage_connector.py`

3. **Knowledge Graph Connector**: Client for the Knowledge Graph server
   - File: `crawling_agent/connectors/mcp_knowledge_graph_connector.py`

Each client provides methods to interact with the corresponding server.

### Base Classes

We've created base classes for both servers and clients:

1. **BaseMCPServer**: Base class for all MCP servers
   - File: `crawling_agent/servers/base_server.py`

2. **BaseMCPConnector**: Base class for all MCP clients
   - File: `crawling_agent/connectors/base_connector.py`

### Utility Scripts

We've created utility scripts to run and test the MCP implementation:

1. **run_servers.py**: Script to run all MCP servers
   - File: `crawling_agent/servers/run_servers.py`

2. **test_mcp_servers.py**: Script to test the MCP implementation
   - File: `test_mcp_servers.py`

## API Documentation

We've created detailed API documentation for the MCP servers:

- File: `crawling_agent/servers/api_docs.md`

Each server also provides interactive API documentation at the `/docs` endpoint.

## Architecture Decision Record

We've updated the Architecture Decision Record (ADR) to reflect the MCP implementation:

- File: `adrs/0005-model-context-protocol.md`

## Running the Implementation

### Running the Servers

To run all MCP servers:

```bash
python -m crawling_agent.servers.run_servers --mock
```

### Testing the Implementation

To test the MCP implementation:

```bash
python test_mcp_servers.py --mock
```

## Next Steps

1. **Integration with Existing Code**: Integrate the MCP implementation with the existing crawling agent code
2. **Authentication and Security**: Add authentication and security features to the MCP servers
3. **Error Handling and Resilience**: Improve error handling and add resilience features
4. **Performance Optimization**: Optimize the performance of the MCP implementation
5. **Monitoring and Logging**: Add monitoring and logging features