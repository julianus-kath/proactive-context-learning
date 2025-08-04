# MCP Server for PostgreSQL ERP Database

This MCP (Model Context Protocol) server provides AI agents with access to the synthetic PostgreSQL ERP database. It exposes database resources and tools through a standardized interface that can be used by LangGraph agents and other AI systems.

## Features

### 🗄️ Database Resources
- **Database Schema**: Complete schema information with table and column details
- **Table Data**: Access to individual tables with sample data
- **Relationships**: Foreign key relationships between tables

### 🔧 Available Tools
- **execute_sql_query**: Execute SQL queries with safety limits
- **get_table_info**: Get detailed information about specific tables
- **search_tables**: Search for tables by name
- **get_sample_data**: Retrieve sample data from tables
- **analyze_query_performance**: Analyze SQL query performance with EXPLAIN

### 🛡️ Safety Features
- Query result limits (default: 1000 rows)
- Query timeout protection
- Connection pooling for performance
- Error handling and logging

## Quick Start

### 1. Prerequisites
Ensure you have:
- PostgreSQL running with the synthetic ERP database
- Python 3.8+ with required dependencies

### 2. Install Dependencies
```bash
cd mcp_server
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### 4. Test the Server
```bash
python test_client.py
```

This will run a comprehensive test suite that:
- Lists available resources and tools
- Tests database connectivity
- Executes sample queries
- Provides an interactive SQL mode

## Usage Examples

### Starting the Server
```bash
python start_server.py
```

### Using the Test Client
```bash
python test_client.py
```

The test client provides:
- **Automated Tests**: Comprehensive test suite
- **Interactive Mode**: Manual SQL query execution
- **Special Commands**:
  - `\tables` - List all tables
  - `\desc <table>` - Describe table structure
  - `\sample <table>` - Show sample data

### Sample Queries

**Get customer statistics:**
```sql
SELECT 
    industry,
    company_size,
    COUNT(*) as customer_count,
    AVG(annual_revenue) as avg_revenue
FROM customers 
WHERE is_active = true
GROUP BY industry, company_size
ORDER BY customer_count DESC;
```

**Analyze sales performance:**
```sql
SELECT 
    c.name as customer_name,
    COUNT(s.sale_id) as total_orders,
    SUM(s.total_amount) as total_revenue,
    AVG(s.total_amount) as avg_order_value
FROM customers c
JOIN sales s ON c.customer_id = s.customer_id
WHERE s.status = 'Completed'
GROUP BY c.customer_id, c.name
ORDER BY total_revenue DESC
LIMIT 10;
```

**Product inventory analysis:**
```sql
SELECT 
    p.product_name,
    p.category,
    w.warehouse_name,
    w.stock_quantity,
    w.reorder_level,
    CASE 
        WHEN w.stock_quantity <= w.reorder_level THEN 'REORDER'
        WHEN w.stock_quantity = 0 THEN 'OUT_OF_STOCK'
        ELSE 'IN_STOCK'
    END as stock_status
FROM products p
JOIN warehouse w ON p.product_id = w.product_id
WHERE p.is_active = true
ORDER BY w.stock_quantity ASC;
```

## MCP Protocol Integration

### Resources
The server exposes these MCP resources:
- `schema://database` - Complete database schema
- `table://<table_name>` - Individual table information
- `relationships://database` - Table relationships

### Tools
All database operations are exposed as MCP tools with proper input validation and error handling.

### Client Integration
```python
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

# Connect to the server
read_stream, write_stream = stdio_client(server_process)
session = ClientSession(read_stream, write_stream)
await session.initialize()

# Execute a query
result = await session.call_tool("execute_sql_query", {
    "query": "SELECT COUNT(*) FROM customers"
})
```

## LangGraph Integration

This MCP server is designed to work seamlessly with LangGraph agents:

### Agent Specialization
- **Customer Agent**: Query customer-related tables
- **Product Agent**: Handle inventory and catalog queries
- **Sales Agent**: Process transaction and performance data
- **Analytics Agent**: Run complex analytical queries

### Example LangGraph Integration
```python
from langgraph import StateGraph
from mcp.client.session import ClientSession

class DatabaseAgent:
    def __init__(self, mcp_session: ClientSession):
        self.session = mcp_session
    
    async def query_database(self, query: str):
        return await self.session.call_tool("execute_sql_query", {
            "query": query
        })

# Use in LangGraph workflow
graph = StateGraph(AgentState)
graph.add_node("database_agent", DatabaseAgent(mcp_session))
```

## Configuration

### Environment Variables
```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=postgres
DB_PASSWORD=postgres

# Server Settings
MAX_QUERY_RESULTS=1000
QUERY_TIMEOUT=30
```

### Security Considerations
- Query result limits prevent memory exhaustion
- Timeout protection prevents long-running queries
- Connection pooling manages database resources
- Input validation prevents SQL injection

## Troubleshooting

### Common Issues

**Connection Refused:**
```bash
# Check if PostgreSQL is running
brew services list | grep postgresql
# or
sudo systemctl status postgresql
```

**Database Not Found:**
```bash
# Ensure the synthetic database exists
python ../synthetic_data_service/setup_postgres.py
```

**Permission Denied:**
```bash
# Check database credentials in .env file
# Ensure user has access to the database
```

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance

### Optimization Features
- Connection pooling (10 base connections, 20 overflow)
- Query result limits (configurable)
- Efficient JSON serialization
- Prepared statement support

### Monitoring
The server logs:
- Query execution times
- Connection pool status
- Error rates and types
- Resource usage

## Development

### Adding New Tools
```python
@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]):
    if name == "my_new_tool":
        # Implementation here
        pass
```

### Adding New Resources
```python
@server.list_resources()
async def list_resources():
    resources.append(Resource(
        uri="my://resource",
        name="My Resource",
        description="Description",
        mimeType="application/json"
    ))
```

## Next Steps

1. **LangGraph Integration**: Use this server in multi-agent workflows
2. **Advanced Analytics**: Add more sophisticated analytical tools
3. **Real-time Updates**: Implement database change notifications
4. **Caching**: Add query result caching for performance
5. **Monitoring**: Add comprehensive monitoring and metrics

The MCP server is now ready for immediate testing and integration with AI agent systems! 🚀