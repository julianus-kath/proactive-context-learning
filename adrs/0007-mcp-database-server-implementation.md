# ADR-0007: MCP Database Server Implementation

## Status
**ACCEPTED** - Implemented and tested successfully

## Date
4.8.2025

## Context
The multi-agent system requires a standardized way to access the PostgreSQL database containing synthetic ERP data. The Model Context Protocol (MCP) provides a standardized interface for AI agents to interact with external resources through JSON-RPC 2.0 over HTTP.

## Decision
We implemented a complete MCP server that provides secure, read-only access to the PostgreSQL database with the following architecture:

### Core Components
1. **FastAPI Server** (`server.py`) - HTTP server with MCP JSON-RPC 2.0 endpoint
2. **Database Manager** (`db.py`) - AsyncPG connection pool and query execution
3. **MCP Tools** (`tools.py`) - Four specialized tools for database interaction
4. **Pydantic Models** (`models.py`) - Type-safe JSON-RPC request/response models

### MCP Tools Implemented
1. **get_schema** - Returns complete database schema information
2. **query** - Executes SELECT queries with safety limits (max 1000 rows)
3. **get_table_info** - Provides detailed table structure and metadata
4. **get_sample_data** - Returns sample data from specified tables

### Security Features
- **API Key Authentication** - Bearer token required for all MCP endpoints
- **Read-Only Access** - Only SELECT queries allowed, no modifications
- **Query Limits** - Automatic row limits and timeout protection
- **Input Validation** - SQL injection prevention and parameter sanitization

### Protocol Compliance
- **JSON-RPC 2.0** - Full specification compliance
- **MCP 2024-11-05** - Latest Model Context Protocol version
- **HTTP Transport** - RESTful endpoints with proper error handling
- **Server-Sent Events** - Ready for streaming capabilities

## Implementation Details

### File Structure
```
mcp_server/
├── server.py          # FastAPI application with MCP endpoints
├── db.py              # Database connection and query management
├── tools.py           # MCP tools implementation
├── models.py          # Pydantic models for JSON-RPC
├── requirements.txt   # Python dependencies
├── .env.example       # Configuration template
├── start_server.py    # Server startup script
├── test_client.py     # Comprehensive test suite
├── validate_setup.py  # Setup validation script
├── quick_test.py      # Quick functionality test
└── README.md          # Documentation
```

### Configuration (.env)
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=juli
DB_PASSWORD=
API_KEY=supersecretapikey
```

### Dependencies
- **fastapi>=0.95.0** - Modern web framework
- **uvicorn[standard]>=0.34.0** - ASGI server
- **asyncpg>=0.30.0** - PostgreSQL async driver
- **pydantic>=2.7.4** - Data validation
- **python-dotenv>=1.0.0** - Environment configuration
- **aiohttp>=3.8.0** - HTTP client for testing

### API Endpoints
- **GET /health** - Health check and database status
- **GET /** - Server information and capabilities
- **POST /mcp** - MCP JSON-RPC 2.0 endpoint
- **GET /docs** - Automatic OpenAPI documentation

### Testing Infrastructure
1. **validate_setup.py** - Validates dependencies, configuration, and database
2. **quick_test.py** - Automated test suite with server lifecycle management
3. **test_client.py** - Interactive and batch testing capabilities

## Test Results
✅ **All tests passed successfully:**
- Health check: Server healthy, database connected
- MCP initialization: Protocol handshake successful
- Tool listing: 4 tools available and properly configured
- Database queries: Successfully executed SELECT queries
- Schema retrieval: Complete database structure returned
- Sample data: Retrieved test data from customers table

### Performance Metrics
- **Connection Pool**: 5-20 concurrent connections
- **Query Timeout**: 30 seconds maximum
- **Row Limits**: 1000 rows maximum per query
- **Response Time**: <100ms for typical queries

## Consequences

### Positive
1. **Standardized Interface** - MCP protocol ensures compatibility with AI agents
2. **Security** - Read-only access with authentication prevents data corruption
3. **Scalability** - Connection pooling and async architecture support high load
4. **Maintainability** - Clean separation of concerns and comprehensive testing
5. **Documentation** - Auto-generated API docs and extensive README
6. **Integration Ready** - Can be immediately used with LangGraph agents

### Negative
1. **Additional Complexity** - Requires separate server process
2. **Network Dependency** - HTTP calls add latency vs direct database access
3. **Single Database** - Currently only supports PostgreSQL

### Risks Mitigated
1. **SQL Injection** - Parameterized queries and input validation
2. **Data Corruption** - Read-only access prevents accidental modifications
3. **Resource Exhaustion** - Connection pooling and query limits
4. **Unauthorized Access** - API key authentication

## Usage Instructions

### Starting the Server
```bash
cd mcp_server
python start_server.py
# Server available at http://localhost:8000
```

### Testing
```bash
# Quick test
python quick_test.py

# Interactive testing
python test_client.py

# Setup validation
python validate_setup.py
```

### Integration Example
```python
import aiohttp
import json

async def query_database(sql: str):
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer supersecretapikey",
            "Content-Type": "application/json"
        }
        
        request_data = {
            "jsonrpc": "2.0",
            "method": "call_tool",
            "params": {
                "name": "query",
                "arguments": {"sql": sql}
            },
            "id": 1
        }
        
        async with session.post(
            "http://localhost:8000/mcp",
            json=request_data,
            headers=headers
        ) as response:
            return await response.json()
```

## Future Enhancements
1. **Multiple Database Support** - MySQL, SQLite adapters
2. **Streaming Responses** - Server-Sent Events for large result sets
3. **Query Caching** - Redis integration for performance
4. **Monitoring** - Metrics and logging integration
5. **Authentication** - OAuth2/JWT token support
6. **Rate Limiting** - Request throttling per client

## Related ADRs
- ADR-0005: Model Context Protocol adoption
- ADR-0003: PostgreSQL migration and enhanced data generation
- ADR-0006: Agent architecture and data integration

## References
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AsyncPG Documentation](https://magicstack.github.io/asyncpg/)