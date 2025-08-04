# MCP Database Server

A Model Context Protocol (MCP) server implementation that provides secure access to a PostgreSQL database through JSON-RPC 2.0 over HTTP with Server-Sent Events support.

## Features

### 🔐 Security
- API Key authentication via Bearer token
- Read-only database access (SELECT queries only)
- Query result limits (max 1000 rows)
- Input validation and sanitization

### 🛠️ MCP Tools
- **get_schema**: Get complete database schema information
- **query**: Execute SELECT queries with safety limits
- **get_table_info**: Get detailed information about specific tables
- **get_sample_data**: Retrieve sample data from tables

### 🌐 HTTP API
- JSON-RPC 2.0 protocol compliance
- FastAPI with automatic OpenAPI documentation
- Server-Sent Events for streaming (future use)
- CORS support for web clients

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your database credentials and API key
```

### 3. Start the Server
```bash
python start_server.py
```

The server will be available at:
- **Main Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **MCP Endpoint**: http://localhost:8000/mcp

### 4. Test the Server
```bash
python test_client.py
```

## Configuration

### Environment Variables (.env)
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=postgres
DB_PASSWORD=postgres
API_KEY=supersecretapikey
```

## API Usage

### Authentication
All requests require an API key in the Authorization header:
```
Authorization: Bearer supersecretapikey
```

### MCP JSON-RPC Requests

**Initialize Session:**
```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "my-client",
      "version": "1.0.0"
    }
  },
  "id": 1
}
```

**List Available Tools:**
```json
{
  "jsonrpc": "2.0",
  "method": "list_tools",
  "id": 2
}
```

**Execute SQL Query:**
```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT COUNT(*) FROM customers WHERE is_active = true",
      "limit": 100
    }
  },
  "id": 3
}
```

**Get Database Schema:**
```json
{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "get_schema"
  },
  "id": 4
}
```

## Testing

### Automated Tests
```bash
python test_client.py
```

This runs a comprehensive test suite including:
- Health check
- MCP session initialization
- Tool listing
- Schema retrieval
- Table information queries
- Sample data retrieval
- SQL query execution

### Interactive Testing
The test client also provides an interactive mode:
```bash
python test_client.py
# Choose 'y' when prompted for interactive mode
```

Available interactive commands:
- `help` - Show available commands
- `health` - Check server health
- `tools` - List available tools
- `schema` - Get database schema
- `table <name>` - Get table information
- `sample <name> [limit]` - Get sample data
- `query <sql>` - Execute SQL query

### Example Queries

**Customer Analysis:**
```sql
SELECT 
    industry,
    company_size,
    COUNT(*) as customer_count,
    AVG(annual_revenue) as avg_revenue
FROM customers 
WHERE is_active = true
GROUP BY industry, company_size
ORDER BY customer_count DESC
LIMIT 10;
```

**Sales Performance:**
```sql
SELECT 
    c.name as customer_name,
    COUNT(s.sale_id) as total_orders,
    SUM(s.total_amount) as total_revenue
FROM customers c
JOIN sales s ON c.customer_id = s.customer_id
WHERE s.status = 'Completed'
GROUP BY c.customer_id, c.name
ORDER BY total_revenue DESC
LIMIT 10;
```

**Product Inventory:**
```sql
SELECT 
    p.product_name,
    p.category,
    w.warehouse_name,
    w.stock_quantity,
    CASE 
        WHEN w.stock_quantity <= w.reorder_level THEN 'REORDER'
        WHEN w.stock_quantity = 0 THEN 'OUT_OF_STOCK'
        ELSE 'IN_STOCK'
    END as stock_status
FROM products p
JOIN warehouse w ON p.product_id = w.product_id
WHERE p.is_active = true
ORDER BY w.stock_quantity ASC
LIMIT 20;
```

## Security Features

### Query Safety
- Only SELECT queries are allowed
- Automatic LIMIT clause addition if not present
- Maximum row limit enforcement (1000 rows)
- Query timeout protection (30 seconds)

### Authentication
- API key validation on all endpoints
- Bearer token format required
- Configurable API key via environment variable

### Database Security
- Read-only database access
- Connection pooling with limits
- Prepared statement support
- Input sanitization

## Error Handling

The server returns standard JSON-RPC 2.0 error responses:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": {"method": "unknown_method"}
  },
  "id": 1
}
```

Common error codes:
- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32002`: Server not initialized

## Development

### Project Structure
```
mcp_server/
├── server.py          # FastAPI server with MCP protocol
├── tools.py           # MCP tools implementation
├── db.py              # Database connection and operations
├── models.py          # Pydantic models for JSON-RPC
├── requirements.txt   # Python dependencies
├── .env.example       # Environment configuration template
├── start_server.py    # Server startup script
├── test_client.py     # Test client and examples
└── README.md          # This file
```

### Adding New Tools
1. Add tool definition to `MCPTools.get_available_tools()` in `tools.py`
2. Implement tool logic in `MCPTools.execute_tool()`
3. Add corresponding method in `MCPTools` class

### Database Operations
All database operations go through the `DatabaseManager` class in `db.py`:
- `fetch()` - Execute SELECT queries
- `fetch_schema()` - Get database schema
- `get_table_count()` - Get row counts
- `get_sample_data()` - Get sample data

## Integration with LangGraph

This MCP server is designed to work with LangGraph agents:

```python
import aiohttp
import json

class DatabaseAgent:
    def __init__(self, mcp_url: str, api_key: str):
        self.mcp_url = mcp_url
        self.api_key = api_key
    
    async def query_database(self, sql: str):
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
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
                f"{self.mcp_url}/mcp",
                json=request_data,
                headers=headers
            ) as response:
                return await response.json()
```

## Troubleshooting

### Common Issues

**Server won't start:**
- Check if PostgreSQL is running
- Verify database credentials in `.env`
- Ensure port 8000 is available

**Database connection failed:**
- Verify database exists and is accessible
- Check network connectivity
- Validate credentials

**API key errors:**
- Ensure API key is set in `.env`
- Use correct Bearer token format
- Check Authorization header

### Debug Mode
Enable debug logging by setting log level:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance

### Optimizations
- Connection pooling (5-20 connections)
- Query result limits
- Async/await throughout
- Efficient JSON serialization

### Monitoring
- Health check endpoint
- Request/response logging
- Database connection status
- Error tracking

The MCP server is production-ready and optimized for AI agent integration! 🚀