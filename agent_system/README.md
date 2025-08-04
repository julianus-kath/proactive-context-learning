# Multi-Agent System with MCP Database Integration

A sophisticated multi-agent system built with LangGraph and LangChain that provides intelligent access to your ERP database through the Model Context Protocol (MCP) server.

## 🎯 **What This System Does**

This multi-agent system provides:
- **Intelligent Database Querying**: Natural language interface to your ERP database
- **Secure Access**: All database operations go through the MCP server with authentication
- **Specialized Agents**: Supervisor coordinates specialized worker agents for different tasks
- **Extensible Architecture**: Easy to add new agents for different data sources
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 📁 **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Input    │───▶│  Supervisor     │───▶│   SQL Agent     │
│                 │    │     Agent       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Future Agents  │    │   MCP Client    │
                       │ (Document, etc) │    │                 │
                       └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   MCP Server    │
                                              │                 │
                                              └─────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  PostgreSQL     │
                                              │   Database      │
                                              └─────────────────┘
```

## 🚀 **Quick Start**

### **Prerequisites**
1. **OpenAI API Key**: Set your OpenAI API key
2. **MCP Server**: Running MCP database server
3. **Python 3.8+**: With required dependencies

### **Installation**
```bash
# Clone and navigate to the project
cd /path/to/your/project

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your OpenAI API key
```

### **Option 1: Quick Start with Docker (Recommended)**
```bash
# Start everything with Docker
python agent_system/startup.py --mode docker --interactive

# This will:
# 1. Start PostgreSQL database
# 2. Start MCP server
# 3. Initialize agent system
# 4. Launch interactive mode
```

### **Option 2: Manual Setup**
```bash
# 1. Start MCP server manually
cd mcp_server
python start_server.py

# 2. In another terminal, start agent system
cd agent_system
python startup.py --interactive
```

### **Option 3: Development Mode**
```bash
# Check environment first
python agent_system/startup.py --check-only

# Start in development mode
python agent_system/startup.py --mode development --interactive
```

## 🧪 **Testing**

### **Quick Test**
```bash
# Test MCP connection
python agent_system/mcp_sql_agent.py

# Comprehensive integration test
python agent_system/test_mcp_integration.py
```

### **Detailed Testing**
```bash
# Test specific components
python agent_system/test_mcp_integration.py --category client
python agent_system/test_mcp_integration.py --category agent
python agent_system/test_mcp_integration.py --category system

# Save test results
python agent_system/test_mcp_integration.py --json-output test_results.json
```

## 💬 **Usage Examples**

Once the system is running in interactive mode:

```
User: What tables are available in the database?
Agent: The database contains the following tables:
- customers: Information about clients
- products: Details about products in inventory
- sales: Transaction records
- suppliers: Information about vendors
- employees: Staff member records
- warehouse: Inventory stock information

User: How many customers do we have?
Agent: Let me query the database for you...
[Executes: SELECT COUNT(*) FROM customers]
We have 1,000 customers in the database.

User: Show me the top 5 customers by total sales
Agent: I'll find the top customers by their total sales amount...
[Executes complex query joining customers and sales tables]
Here are the top 5 customers by total sales:
1. Customer A: $15,420.50
2. Customer B: $12,890.25
...
```

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Core Configuration
OPENAI_API_KEY=your_api_key_here
MCP_SERVER_URL=http://localhost:8000
MCP_API_KEY=supersecretapikey

# Agent Behavior
AGENT_MODEL=gpt-4o
AGENT_TEMPERATURE=0.0
AGENT_VERBOSE=false

# System Settings
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### **Programmatic Configuration**
```python
from agent_system.config import get_config_manager

# Update MCP settings
config_manager = get_config_manager()
config_manager.update_mcp_config(
    url="http://localhost:9000",
    timeout=60
)

# Update agent settings
config_manager.update_agent_config(
    model="gpt-4",
    temperature=0.1
)
```

## 🏗️ **Architecture Details**

### **Core Components**

#### **1. Supervisor Agent** (`agent_supervisor.py`)
- **Purpose**: Coordinates worker agents and handles user interactions
- **Responsibilities**:
  - Understands user requests
  - Delegates to appropriate specialized agents
  - Summarizes results for users
  - Manages conversation flow

#### **2. SQL Agent** (`mcp_sql_agent.py`)
- **Purpose**: Specialized for database operations via MCP server
- **Tools Available**:
  - `run_sql_query`: Execute SELECT queries
  - `get_database_schema`: Get complete database structure
  - `get_table_info`: Get detailed table information
  - `get_sample_data`: Retrieve sample data from tables
  - `check_mcp_server_health`: Monitor server status

#### **3. MCP Client** (`mcp_client.py`)
- **Purpose**: Handles communication with MCP server
- **Features**:
  - Async and sync interfaces
  - Automatic retry logic
  - Error handling and recovery
  - Connection pooling
  - Request/response validation

#### **4. Configuration Manager** (`config.py`)
- **Purpose**: Centralized configuration management
- **Features**:
  - Environment variable loading
  - Runtime configuration updates
  - Validation and defaults
  - Logging setup

### **Data Flow**

1. **User Input** → Supervisor Agent
2. **Supervisor** → Determines appropriate worker agent
3. **SQL Agent** → Uses MCP Client to communicate with MCP Server
4. **MCP Server** → Executes database operations securely
5. **Results** → Flow back through the chain to the user

## 🔒 **Security Features**

### **MCP Server Security**
- **API Key Authentication**: All requests require valid API key
- **Read-Only Access**: Only SELECT queries allowed
- **Query Limits**: Maximum 1000 rows per query
- **Timeout Protection**: 30-second query timeout
- **Input Validation**: SQL injection prevention

### **Agent System Security**
- **Secure Communication**: HTTPS support for MCP server
- **Error Sanitization**: Sensitive information filtered from errors
- **Access Control**: Agent-level permissions
- **Audit Logging**: All operations logged

## 📊 **Monitoring & Troubleshooting**

### **Health Checks**
```bash
# Check MCP server health
curl http://localhost:8000/health

# Check agent system health
python agent_system/startup.py --check-only
```

### **Common Issues**

#### **❌ "MCP server not available"**
```bash
# Check if MCP server is running
curl http://localhost:8000/health

# Start MCP server
cd mcp_server && python start_server.py

# Or use Docker
python agent_system/startup.py --mode docker
```

#### **❌ "OpenAI API key not set"**
```bash
# Set environment variable
export OPENAI_API_KEY=your_api_key_here

# Or add to .env file
echo "OPENAI_API_KEY=your_api_key_here" >> .env
```

#### **❌ "Database connection failed"**
```bash
# Check PostgreSQL is running
psql -l

# Check database exists
psql -d synthetic_erp_data -c "SELECT 1;"

# Verify MCP server database connection
cd mcp_server && python validate_setup.py
```

### **Logging**
```python
# Enable debug logging
import logging
logging.getLogger('agent_system').setLevel(logging.DEBUG)

# Or set environment variable
export LOG_LEVEL=DEBUG
```

## 🚀 **Extending the System**

### **Adding New Agents**

1. **Create Agent Module**:
```python
# agent_system/document_agent.py
def search_documents(query: str) -> str:
    # Implementation for document search
    pass

def get_document_info(doc_id: str) -> str:
    # Implementation for document info
    pass
```

2. **Update Supervisor**:
```python
# In agent_supervisor.py
from agent_system.document_agent import search_documents, get_document_info

# Add handoff tool
assign_to_document_agent = create_handoff_tool(
    agent_name="document_agent",
    description="Assign task to document agent for searching documents."
)

# Create document agent
document_agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o", temperature=0),
    tools=[
        Tool.from_function(func=search_documents, name="search_documents"),
        Tool.from_function(func=get_document_info, name="get_document_info")
    ],
    prompt="You are a document search expert...",
    name="document_agent"
)
```

3. **Update Graph**:
```python
# Add to workflow
workflow = (
    StateGraph(MessagesState)
    .add_node(supervisor_agent, destinations=["sql_agent", "document_agent", END])
    .add_node(sql_agent)
    .add_node(document_agent)  # New agent
    .add_edge(START, "supervisor")
    .add_edge("sql_agent", "supervisor")
    .add_edge("document_agent", "supervisor")  # New edge
    .compile()
)
```

### **Adding New MCP Tools**

1. **Extend MCP Client**:
```python
# In mcp_client.py
async def custom_operation(self, param: str) -> MCPResponse:
    return await self._make_request("call_tool", {
        "name": "custom_tool",
        "arguments": {"param": param}
    })
```

2. **Update SQL Agent**:
```python
# In mcp_sql_agent.py
def custom_operation(param: str) -> str:
    agent = get_mcp_sql_agent()
    response = agent.client.custom_operation(param)
    return agent._format_mcp_response(response, "custom operation")
```

## 📈 **Performance Optimization**

### **Connection Pooling**
- MCP client uses connection pooling for efficiency
- Configurable pool size and timeout settings
- Automatic connection cleanup

### **Caching**
```python
# Add caching for frequently accessed data
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_schema():
    return get_database_schema()
```

### **Async Operations**
- Use async MCP client for better performance
- Parallel query execution where possible
- Non-blocking I/O operations

## 🐳 **Docker Deployment**

### **Development**
```bash
# Start with Docker Compose
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs mcp_server
```

### **Production**
```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale mcp_server=3
```

## 🤝 **Contributing**

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-agent`
3. **Add tests**: Ensure new functionality is tested
4. **Update documentation**: Keep README and docstrings current
5. **Submit pull request**: With clear description of changes

## 📚 **API Reference**

### **MCPClient**
```python
async with MCPClient() as client:
    # Health check
    health = await client.health_check()
    
    # Get schema
    schema = await client.get_schema()
    
    # Execute query
    result = await client.query("SELECT * FROM customers LIMIT 10")
    
    # Get table info
    info = await client.get_table_info("customers")
    
    # Get sample data
    sample = await client.get_sample_data("customers", 5)
```

### **MCPSQLAgent**
```python
agent = MCPSQLAgent()

# Execute query
result = agent.run_sql_query("SELECT COUNT(*) FROM customers")

# Get schema
schema = agent.get_database_schema()

# Get table info
info = agent.get_table_info("customers")

# Health check
health = agent.health_check()
```

### **Agent System**
```python
agent_system = create_multi_agent_system()

# Process user input
result = agent_system.invoke({
    "messages": [{"role": "user", "content": "How many customers do we have?"}]
})

# Get response
response = result["messages"][-1]["content"]
```

## 🔗 **Related Documentation**

- [MCP Server Implementation Guide](../mcp_server/IMPLEMENTATION_GUIDE.md)
- [ADR-0007: MCP Database Server Implementation](../adrs/0007-mcp-database-server-implementation.md)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)

---

## 🎉 **Success Indicators**

Your multi-agent system is working correctly when:
- ✅ `python agent_system/startup.py --check-only` shows all green checkmarks
- ✅ `python agent_system/test_mcp_integration.py` passes all tests
- ✅ Interactive mode responds to natural language queries
- ✅ MCP server health check returns healthy status
- ✅ Database queries execute successfully through the agent system

**You now have a production-ready multi-agent system with secure database access!** 🚀