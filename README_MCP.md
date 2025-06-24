# MCP Servers for Crawling Agent

This project implements Model-Context Protocol (MCP) servers for the crawling agent system. The servers expose data sources as services that can be queried by AI agents.

## Installation

1. Install the required dependencies:

```bash
uv pip install fastmcp pandas nest-asyncio pytest pytest-asyncio
```

Note: This implementation uses a custom resource class (`CustomResource`) that extends the abstract `Resource` class from fastmcp to implement the required `read` method.

## Running the Servers

### Option 1: Run all servers with the run_servers.py script

The easiest way to run all servers is to use the `run_servers.py` script:

```bash
# Run all servers
python -m crawling_agent.run_servers

# Run specific servers
python -m crawling_agent.run_servers --servers erp document
```

This will start the servers with the following endpoints:
- ERP Server: http://localhost:8001/sse
- Document Storage Server: http://localhost:8002/sse
- Knowledge Graph Server: http://localhost:8003/sse

### Option 2: Run individual servers directly

You can also run each server individually:

```bash
# Run the ERP Server
python -m crawling_agent.servers.erp_server

# Run the Document Storage Server
python -m crawling_agent.servers.document_storage_server

# Run the Knowledge Graph Server
python -m crawling_agent.servers.knowledge_graph_server
```

## Testing the Servers

Once the servers are running, you can test them using the provided test scripts:

```bash
# Test the ERP server
python test_erp_server.py

# Run the example client to test all servers
python run_example_client.py
```

## Project Structure

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
├─ connectors/
│  ├─ mcp_erp_connector.py
│  ├─ mcp_document_storage_connector.py
│  ├─ mcp_knowledge_graph_connector.py
├─ base_server.py
├─ base_connector.py
├─ custom_resource.py
├─ run_servers.py
├─ example_client.py
```

## Architecture

The architecture consists of three main components:

1. **MCP Servers**: Each server exposes a specific data source through MCP tools.
2. **MCP Connectors**: Each connector provides a client interface to interact with a specific server.
3. **Base Classes**: Common functionality is extracted into base classes to promote code reuse.

For more detailed information about the implementation, see the [MCP_IMPLEMENTATION.md](crawling_agent/MCP_IMPLEMENTATION.md) file and the [Architecture Decision Record](docs/adr/0001-mcp-implementation.md).