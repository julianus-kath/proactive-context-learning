# Architecture Decision Record: MCP Implementation

## Status

Accepted

## Date

2024-05-27

## Context

The crawling agent system needs to interact with multiple data sources, including a relational database (SQLite), a document store (JSON-based), and a knowledge graph. These data sources need to be exposed in a way that allows AI agents to query them efficiently and consistently.

The Model-Context Protocol (MCP) is a standardized protocol for AI agents to interact with external tools and resources. It provides a structured way to expose functionality and data to AI models, making it an ideal choice for our use case.

## Decision

We have decided to implement MCP servers for each data source in the crawling agent system. Each server will expose a set of tools that allow AI agents to query the corresponding data source. The servers will use the Server-Sent Events (SSE) transport to communicate with clients.

### Architecture Overview

The architecture consists of three main components:

1. **MCP Servers**: Each server exposes a specific data source through MCP tools.
2. **MCP Connectors**: Each connector provides a client interface to interact with a specific server.
3. **Base Classes**: Common functionality is extracted into base classes to promote code reuse.

### Project Structure

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
├─ example_client.py
```

### MCP Servers

1. **ERP Server**: Connects to a SQLite database and provides tools to execute SQL queries, get table schemas, and list tables.
2. **Document Storage Server**: Loads documents from a JSON file and provides tools to find documents, list collections, and get collection information.
3. **Knowledge Graph Server**: Maintains a knowledge graph in memory and provides tools to query nodes and relationships, and get node and relationship types.

### MCP Connectors

Each connector provides a client interface to interact with a specific server:

1. **ERP Connector**: Provides methods to execute SQL queries, get table schemas, and list tables.
2. **Document Storage Connector**: Provides methods to find documents, list collections, and get collection information.
3. **Knowledge Graph Connector**: Provides methods to query nodes and relationships, and get node and relationship types.

### Base Classes

1. **BaseMCPServer**: Provides common functionality for all MCP servers, including initialization and running the server.
2. **BaseMCPConnector**: Provides common functionality for all MCP connectors, including connecting to a server, listing tools, and calling tools.

### Deployment

The servers can be deployed in multiple ways:

1. **Direct Execution**: Run the servers directly using Python.
2. **Docker Containers**: Run the servers in Docker containers using the provided Dockerfiles.
3. **Docker Compose**: Run all servers together using Docker Compose.

## Consequences

### Advantages

1. **Standardized Protocol**: MCP provides a standardized way for AI agents to interact with external tools and resources.
2. **Modularity**: Each data source is exposed through a separate server, promoting modularity and separation of concerns.
3. **Extensibility**: New data sources can be added by creating new MCP servers and connectors.
4. **Reusability**: Common functionality is extracted into base classes, promoting code reuse.
5. **Flexibility**: The servers can be deployed in multiple ways, providing flexibility in deployment options.
6. **Testability**: The modular architecture makes it easier to test individual components.

### Challenges

1. **Complexity**: The architecture introduces additional complexity compared to direct database access.
2. **Performance**: The use of MCP and HTTP introduces additional overhead compared to direct database access.
3. **Deployment**: Running multiple servers requires more resources and coordination.
4. **Error Handling**: Error handling across multiple servers and connectors requires careful consideration.
5. **Security**: Exposing data sources through HTTP requires careful security considerations.

### Mitigations

1. **Base Classes**: Common functionality is extracted into base classes to reduce complexity and promote code reuse.
2. **Docker Compose**: Docker Compose is used to simplify deployment and coordination of multiple servers.
3. **Error Handling**: Error handling is implemented at both the server and connector levels.
4. **Security**: The servers are configured to listen only on localhost by default, reducing security risks.

## Alternatives Considered

1. **Direct Database Access**: AI agents could access the data sources directly, but this would require embedding database access code in the agents, making them less portable and more complex.
2. **Single MCP Server**: All data sources could be exposed through a single MCP server, but this would reduce modularity and make the server more complex.
3. **REST API**: Data sources could be exposed through a REST API, but this would require implementing a custom protocol for AI agents to interact with the API.
4. **GraphQL**: Data sources could be exposed through a GraphQL API, but this would require implementing a custom protocol for AI agents to interact with the API.

## Decision Outcome

The decision to implement MCP servers for each data source provides a standardized, modular, and extensible way for AI agents to interact with the data sources in the crawling agent system. The architecture promotes code reuse, testability, and flexibility in deployment options.

The additional complexity and performance overhead are acceptable trade-offs for the benefits of standardization, modularity, and extensibility. The challenges related to deployment, error handling, and security are mitigated through the use of base classes, Docker Compose, and careful configuration.