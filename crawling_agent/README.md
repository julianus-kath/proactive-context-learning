# Crawling Agent System

This project implements a flexible agent that can reason across multiple data sources using the Model-Context Protocol (MCP). The system consists of MCP servers that expose different data sources, connectors that provide client interfaces, and a multi-source reasoning agent that integrates data from these sources.

## Architecture

The system consists of three main components:

1. **MCP Servers**: Expose different data sources as services that can be queried over MCP.
   - ERP Server: Exposes SQL query tools over MCP, connected to a SQLite database.
   - Document Storage Server: Exposes MongoDB-style query tools over MCP, sourcing from a JSON file.
   - Knowledge Graph Server: Exposes graph query tools over MCP.

2. **MCP Connectors**: Provide client interfaces to interact with the MCP servers.
   - ERP Connector: Connects to the ERP Server.
   - Document Storage Connector: Connects to the Document Storage Server.
   - Knowledge Graph Connector: Connects to the Knowledge Graph Server.

3. **Multi-Source Agent**: Integrates data from the different sources using a reasoning loop.
   - Uses a modular LLM client that can be easily switched between different models.
   - Implements a reasoning loop to handle complex queries.
   - Provides debugging output to monitor the agent's thought process.

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the System

### Option 1: Run both servers and agent with run_all.py

The easiest way to run the entire system is to use the `run_all.py` script:

```bash
# Run all servers and the agent
python -m crawling_agent.run_all

# Run with debug mode
python -m crawling_agent.run_all --debug

# Run with specific LLM settings
python -m crawling_agent.run_all --llm-type openai --llm-model gpt-4o
```

### Option 2: Run servers and agent separately

You can also run the servers and agent separately:

```bash
# First, run the servers
python -m crawling_agent.run_servers

# Then, in a separate terminal, run the agent
python -m crawling_agent.run_agent
```

### Option 3: Run individual servers directly

You can run each server individually:

```bash
# Run the ERP Server
python -m crawling_agent.servers.erp_server

# Run the Document Storage Server
python -m crawling_agent.servers.document_storage_server

# Run the Knowledge Graph Server
python -m crawling_agent.servers.knowledge_graph_server
```

### Option 4: Run with Docker Compose

You can use Docker Compose to run all servers in containers:

```bash
# Build and start all servers
docker-compose up

# Build and start specific servers
docker-compose up erp-server document-storage-server
```

## Using the Connectors

The connectors provide a client interface to interact with the servers. Here's an example of how to use the ERP connector:

```python
import asyncio
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector

async def main():
    async with MCPERPConnector() as connector:
        # List all tables
        tables = await connector.list_tables()
        print("Tables:", tables)
        
        if tables:
            # Get the schema for the first table
            schema = await connector.get_table_schema(tables[0])
            print(f"Schema for {tables[0]}:", schema)
            
            # Execute a simple query
            query = f"SELECT * FROM {tables[0]} LIMIT 5"
            results = await connector.execute_sql_query(query)
            print(f"Query results for '{query}':", results)

if __name__ == "__main__":
    asyncio.run(main())
```

Similar examples are available for the Document Storage and Knowledge Graph connectors.

## LLM Integration

The agent uses a modular LLM client that can be easily switched between different models. Currently, it supports OpenAI's API, but it can be extended to support other LLM providers.

To use a different LLM provider, implement a new client class that extends `BaseLLMClient` and register it with the `LLMClientFactory`.

## Reasoning Loop

The agent implements a reasoning loop that:

1. Analyzes the user query to determine what information is needed.
2. Identifies which data sources are relevant.
3. Queries the appropriate data sources using tool calls.
4. Integrates the information from different sources.
5. Provides a comprehensive answer.

The reasoning loop is implemented in the `_reasoning_loop` method of the `MultiSourceAgent` class.

## Debugging

The agent provides extensive debugging output to monitor its thought process. To enable debug mode, use the `--debug` flag when running the agent:

```bash
python -m crawling_agent.run_agent --debug
```

## Running Tests

To run the tests:

```bash
# Run all tests
pytest tests/

# Run specific tests
pytest tests/test_mcp_servers.py
```

## Documentation

For more detailed information about the MCP implementation, see the [MCP_IMPLEMENTATION.md](MCP_IMPLEMENTATION.md) file.