# Dynamic ERP Assistant - Complete System Architecture

**A Multi-Agent System for Natural Language Database Querying**

[![Status](https://img.shields.io/badge/Status-In%20Development-yellow)]()
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

---

## 📋 Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Core Components](#core-components)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Deployment Modes](#deployment-modes)
- [Security Architecture](#security-architecture)
- [API Documentation](#api-documentation)
- [Development Guide](#development-guide)
- [Troubleshooting](#troubleshooting)
- [Architecture Decision Records](#architecture-decision-records)

---

## 🎯 Overview

The **Dynamic ERP Assistant** is a sophisticated natural language interface for querying ERP databases. It enables non-technical users to interact with complex database systems using plain English, automatically converting natural language queries into SQL, executing them securely, and presenting results in a user-friendly format.

### Key Features

✅ **Natural Language Processing** - Query databases using plain English  
✅ **Multi-Database Support** - PostgreSQL, SQL Server, MongoDB, Neo4j  
✅ **Secure Proxy Architecture** - Safe access to production databases via VPN  
✅ **LangGraph Workflow** - Intelligent query processing and intent analysis  
✅ **MCP Protocol** - Standardized Model Context Protocol for AI agents  
✅ **Modern Web UI** - Professional chatbot interface with real-time responses  
✅ **Schema Discovery** - Automatic database structure detection  
✅ **Read-Only Safety** - Enforced read-only access with query validation  

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE LAYER                          │
│  ┌──────────────────────┐         ┌──────────────────────┐         │
│  │   Modern Web UI      │         │   Streamlit UI       │         │
│  │   (HTML/CSS/JS)      │         │   (Legacy)           │         │
│  │   Port 3000          │         │   Port 8501          │         │
│  └──────────┬───────────┘         └──────────┬───────────┘         │
└─────────────┼──────────────────────────────────┼───────────────────┘
              │                                  │
              └──────────────┬───────────────────┘
                             │ HTTP/REST
┌─────────────────────────────┼───────────────────────────────────────┐
│                    API GATEWAY LAYER                                 │
│                   ┌─────────┴─────────┐                             │
│                   │  LangGraph Service │                             │
│                   │  FastAPI - Port 5001│                            │
│                   └─────────┬─────────┘                             │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────┐
│              CORE PROCESSING LAYER (LangGraph)                       │
│  ┌───────────────────────────────────────────────────────┐          │
│  │           DatabaseWorkflow (State Graph)              │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │          │
│  │  │ Schema   │→ │ Intent   │→ │ SQL      │           │          │
│  │  │ Discovery│  │ Analysis │  │ Generator│           │          │
│  │  └──────────┘  └──────────┘  └──────────┘           │          │
│  │         ↓            ↓            ↓                   │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │          │
│  │  │ Query    │→ │ Result   │→ │ Response │           │          │
│  │  │ Executor │  │ Processor│  │ Formatter│           │          │
│  │  └──────────┘  └──────────┘  └──────────┘           │          │
│  └───────────────────────────────────────────────────────┘          │
│                              ↕                                       │
│                    ┌─────────────────┐                              │
│                    │  OpenAI GPT-4   │                              │
│                    │  Language Model │                              │
│                    └─────────────────┘                              │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────┐
│                  DATA ACCESS LAYER                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Database Adapter │  │  MCP Server      │  │ Database Client │  │
│  │ (Compatibility)  │  │  Port 8000       │  │ (Unified API)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬────────┘  │
│           │                     │                      │            │
│           └─────────────────────┴──────────────────────┘            │
│                                 │                                    │
│                    ┌────────────┴────────────┐                      │
│                    │                         │                      │
│              ┌─────▼──────┐          ┌──────▼──────┐               │
│              │ Direct Mode│          │ Proxy Mode  │               │
│              │ (asyncpg)  │          │ (HTTPS/TLS) │               │
│              └─────┬──────┘          └──────┬──────┘               │
└────────────────────┼─────────────────────────┼─────────────────────┘
                     │                         │
        ┌────────────┘                         └────────────┐
        │                                                   │
┌───────▼────────┐                              ┌──────────▼──────────┐
│ LOCAL DEV ENV  │                              │ NETWORK BOUNDARY    │
│ ┌────────────┐ │                              │ ┌─────────────────┐ │
│ │PostgreSQL  │ │                              │ │  HTTPS/TLS      │ │
│ │Port 5432   │ │                              │ │  Encrypted      │ │
│ │synthetic_  │ │                              │ └────────┬────────┘ │
│ │erp_data    │ │                              └──────────┼──────────┘
│ └────────────┘ │                                         │
└────────────────┘                              ┌──────────▼──────────┐
                                                │ WINDOWS PROXY ENV   │
                                                │ ┌─────────────────┐ │
                                                │ │ SQL Proxy       │ │
                                                │ │ Flask - Port 5000│ │
                                                │ │ API Auth        │ │
                                                │ └────────┬────────┘ │
                                                │          │          │
                                                │ ┌────────▼────────┐ │
                                                │ │ Corporate VPN   │ │
                                                │ │ Secure Tunnel   │ │
                                                │ └────────┬────────┘ │
                                                │          │          │
                                                │ ┌────────▼────────┐ │
                                                │ │ SQL Server      │ │
                                                │ │ Production ERP  │ │
                                                │ └─────────────────┘ │
                                                └─────────────────────┘
```

### Component Interaction Flow

```
User Query: "How many customers do we have?"
    ↓
[Web UI] → HTTP POST /process_query
    ↓
[LangGraph Service] → Validate & Route
    ↓
[DatabaseWorkflow] → Schema Discovery
    ↓
[Database Client] → get_schema()
    ↓
[OpenAI GPT-4] → Analyze Intent + Generate SQL
    ↓
[Database Client] → execute_query("SELECT COUNT(*) FROM customers")
    ↓
[Database Backend] → Execute & Return Results
    ↓
[OpenAI GPT-4] → Format Response
    ↓
[Web UI] → Display: "You have 1,247 customers in the database."
```

---

## 🔧 Core Components

### 1. **Chatbot UI** (Frontend)

**Location:** `chatbot_ui/`

Two interface options available:

#### Modern Web UI (Recommended)
- **Files:** `index.html`, `styles.css`, `script.js`, `web_app.py`
- **Port:** 3000
- **Features:**
  - Professional dark theme with blue accents
  - Real-time typing indicators
  - Conversation history
  - Responsive design (desktop & mobile)
  - Pure HTML/CSS/JS frontend

#### Streamlit UI (Legacy)
- **File:** `app.py`
- **Port:** 8501
- **Features:**
  - Python-based UI framework
  - Session state management
  - Built-in components
  - Full feature parity

**Key Features:**
- Natural language input
- Real-time query processing
- Chat history management
- Sample query suggestions
- Error handling with user-friendly messages
- Service health indicators

**Startup:**
```bash
# Modern Web UI
cd chatbot_ui
python start_web_ui.py

# Streamlit UI
cd chatbot_ui
python start_services.py
```

---

### 2. **LangGraph Integration** (Workflow Engine)

**Location:** `langgraph_integration/`

**Core Files:**
- `graph_definition.py` - LangGraph workflow state machine
- `mcp_client.py` - MCP protocol client
- `prompts.py` - LLM prompt templates
- `hybrid_db_client.py` - Unified database client
- `proxy_db_client.py` - Proxy mode handler
- `direct_db_client.py` - Direct mode handler

**Workflow Nodes:**
1. **Schema Discovery** - Retrieves database structure
2. **Intent Analysis** - Determines query type (QUERY, CLARIFY, ERROR)
3. **SQL Generation** - Converts natural language to SQL
4. **Query Execution** - Executes SQL safely
5. **Result Formatting** - Formats results for users
6. **Clarification Handling** - Requests additional information when needed

**State Graph:**
```python
START → get_schema → analyze_intent → [
    QUERY → execute_query → format_response → END
    CLARIFY → handle_clarification → END
    ERROR → format_response → END
]
```

**Key Features:**
- Stateful workflow management
- Automatic schema caching
- Intent-based routing
- Error recovery
- Context preservation
- Streaming support

---

### 3. **MCP Server** (Model Context Protocol)

**Location:** `mcp_server/`

**Core Files:**
- `server.py` - FastAPI application with MCP endpoints
- `db.py` - AsyncPG connection pool manager
- `tools.py` - MCP tool implementations
- `models.py` - Pydantic models for JSON-RPC
- `database_adapter.py` - Database abstraction layer

**MCP Tools:**
1. **get_schema** - Returns complete database schema
2. **query** - Executes SELECT queries (max 1000 rows)
3. **get_table_info** - Provides detailed table metadata
4. **get_sample_data** - Returns sample data from tables

**Protocol Compliance:**
- JSON-RPC 2.0 specification
- MCP 2024-11-05 version
- HTTP transport layer
- Server-Sent Events ready

**Security Features:**
- API key authentication (Bearer token)
- Read-only access enforcement
- Query limits and timeouts
- SQL injection prevention
- Input validation

**Endpoints:**
- `GET /health` - Health check
- `GET /` - Server capabilities
- `POST /mcp` - MCP JSON-RPC endpoint
- `GET /docs` - OpenAPI documentation

**Startup:**
```bash
cd mcp_server
python start_server.py
# Server available at http://localhost:8000
```

---

### 4. **VPN Proxy** (Secure Database Access)

**Location:** `vpn_config/`

**Core Files:**
- `proxy.py` - Flask HTTPS proxy server
- `connections.yaml` - Database connection configuration
- `setup_proxy_windows.ps1` - Windows setup script

**Architecture:**
```
Mac Agent → HTTPS/TLS → Windows Proxy → VPN → SQL Server
```

**Features:**
- **HTTPS/TLS Encryption** - End-to-end encrypted communication
- **API Key Authentication** - Secure access control
- **Multi-Database Support** - MSSQL, PostgreSQL
- **YAML Configuration** - Flexible connection management
- **Environment Variables** - Secure credential handling
- **Parameterized Queries** - SQL injection prevention
- **Query Limits** - Server-side row limits (max 10,000)
- **Timeouts** - Configurable query timeouts (max 300s)
- **Read-Only Enforcement** - Only SELECT queries allowed

**Endpoints:**
- `GET /health` - Proxy status and available connections
- `GET /diag` - Diagnostic information (authenticated)
- `POST /query` - Execute SELECT queries (authenticated)

**Configuration Example:**
```yaml
connections:
  corp_sql_erp:
    type: mssql
    driver: "ODBC Driver 18 for SQL Server"
    host: "192.168.200.16"
    port: 1433
    database: "master"
    user: "SimonM"
    password: "${SQLSERVER_PASSWORD}"
    encrypt: true
    trust_server_certificate: true
```

**Startup (Windows):**
```powershell
cd vpn_config
python proxy.py
# Proxy available at https://0.0.0.0:5000
```

---

### 5. **Database Client** (Unified Interface)

**Location:** `langgraph_integration/hybrid_db_client.py`

**Modes:**
- **Direct Mode** (`DB_MODE=direct`) - Local PostgreSQL via asyncpg
- **Proxy Mode** (`DB_MODE=proxy`) - Remote SQL Server via HTTPS proxy

**Key Features:**
- Unified API across database types
- Automatic SQL dialect translation
- Connection pooling
- Error handling and retry logic
- Schema caching
- Query validation

**SQL Translation:**
- PostgreSQL → SQL Server syntax conversion
- `LIMIT` → `TOP` clause conversion
- Schema qualification handling
- Data type mapping

**Usage:**
```python
from langgraph_integration.hybrid_db_client import DatabaseClient

# Initialize client
client = DatabaseClient(mode="proxy")  # or "direct"

# Get schema
schema = await client.get_schema()

# Execute query
results = await client.execute_query("SELECT * FROM customers LIMIT 10")
```

---

### 6. **Synthetic Data Service** (Test Data Generation)

**Location:** `synthetic_data_service/`

**Purpose:** Generates realistic synthetic ERP data for development and testing.

**Database Schema:**
- **customers** - Business clients with contact information
- **products** - Items with categorization and pricing
- **suppliers** - Vendors providing products
- **warehouse** - Inventory stock across locations
- **sales** - Transaction records
- **employees** - Staff members with departments

**Features:**
- Realistic data using Faker library
- Referential integrity
- Configurable data volumes
- PostgreSQL support
- Relationship preservation

**Usage:**
```bash
cd synthetic_data_service
python main.py --customers 1000 --products 500 --sales 5000
```

---

## 🛠️ Technology Stack

### Backend
- **Python 3.8+** - Core programming language
- **FastAPI** - Modern web framework for APIs
- **LangGraph** - Workflow orchestration and state management
- **LangChain** - LLM integration framework
- **OpenAI GPT-4** - Natural language processing
- **AsyncPG** - PostgreSQL async driver
- **PyODBC** - SQL Server ODBC driver
- **Flask** - Proxy server framework

### Frontend
- **HTML5/CSS3/JavaScript** - Modern web UI
- **Streamlit** - Python-based UI framework (legacy)
- **Fetch API** - HTTP client for REST calls

### Databases
- **PostgreSQL 12+** - Development database
- **SQL Server** - Production ERP database
- **MongoDB** - Document store (optional)
- **Neo4j** - Graph database (optional)

### Protocols & Standards
- **MCP (Model Context Protocol)** - AI agent communication
- **JSON-RPC 2.0** - Remote procedure calls
- **REST API** - HTTP-based services
- **HTTPS/TLS 1.3** - Secure communication

### Development Tools
- **Docker** - Containerization
- **Git** - Version control
- **pytest** - Testing framework
- **Pydantic** - Data validation
- **python-dotenv** - Environment management

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+** installed
2. **PostgreSQL 12+** running locally
3. **OpenAI API Key** (for GPT-4 access)
4. **Git** for cloning the repository

### Installation

```bash
# Clone the repository
cd "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code"

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.template .env
# Edit .env with your OpenAI API key and database credentials
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
DB_MODE=direct  # or "proxy" for production
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
DB_USER=your_username
DB_PASSWORD=your_password

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
API_KEY=supersecretapikey

# Proxy Configuration (if using proxy mode)
PROXY_BASE_URL=https://10.255.152.48:5000
PROXY_API_KEY=your_proxy_api_key
PROXY_CERT_PATH=/path/to/proxy.crt
```

### Generate Synthetic Data

```bash
cd synthetic_data_service
python main.py --customers 1000 --products 500 --sales 5000
```

### Start Services

#### Option 1: All-in-One Startup (Recommended)

```bash
cd chatbot_ui
python start_web_ui.py
```

This starts:
- LangGraph Service (Port 5001)
- Web UI (Port 3000)

#### Option 2: Manual Startup

```bash
# Terminal 1: Start MCP Server (optional)
cd mcp_server
python start_server.py

# Terminal 2: Start LangGraph Service
cd chatbot_ui
python langgraph_service.py

# Terminal 3: Start Web UI
cd chatbot_ui
python web_app.py
```

### Access the Application

- **Modern Web UI:** http://localhost:3000
- **Streamlit UI:** http://localhost:8501 (if using legacy UI)
- **LangGraph API:** http://localhost:5001/docs
- **MCP Server:** http://localhost:8000/docs

### Test the System

Try these sample queries in the chat interface:

```
"How many customers do we have?"
"Show me the top 5 products by sales"
"What tables are available in the database?"
"List all customers from New York"
"What were our total sales last month?"
```

---

## 🔄 Deployment Modes

### Development Mode (Direct)

**Configuration:**
```env
DB_MODE=direct
DB_HOST=localhost
DB_PORT=5432
DB_NAME=synthetic_erp_data
```

**Architecture:**
```
Web UI → LangGraph → Database Client → PostgreSQL (Local)
```

**Use Cases:**
- Local development
- Testing and debugging
- Schema exploration
- Feature development

**Advantages:**
- Fast response times
- No network dependencies
- Full control over data
- Easy debugging

---

### Production Mode (Proxy)

**Configuration:**
```env
DB_MODE=proxy
PROXY_BASE_URL=https://10.255.152.48:5000
PROXY_API_KEY=your_secure_api_key
PROXY_CERT_PATH=/path/to/proxy.crt
```

**Architecture:**
```
Web UI → LangGraph → Database Client → HTTPS/TLS → Windows Proxy → VPN → SQL Server
```

**Use Cases:**
- Production database access
- Secure VPN-protected environments
- Multi-database deployments
- Enterprise integration

**Advantages:**
- Secure credential management
- VPN-protected access
- Read-only enforcement
- Audit logging

**Setup:**
1. Configure Windows proxy server (see `vpn_config/README.md`)
2. Set up VPN connection on Windows machine
3. Configure `connections.yaml` with database details
4. Update Mac environment variables
5. Test connection with `test_proxy_simple.py`

---

### Hybrid Mode

**Configuration:**
```env
DB_MODE=hybrid
# Both direct and proxy configurations
```

**Use Cases:**
- Development with production schema
- Testing proxy integration
- Fallback scenarios

---

## 🔒 Security Architecture

### Multi-Layer Security Model

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Application Security                               │
│ - Environment variables (no hardcoded secrets)              │
│ - API key authentication                                    │
│ - Input validation and sanitization                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Network Security                                   │
│ - HTTPS/TLS 1.3 encryption                                  │
│ - Certificate validation                                    │
│ - Firewall rules                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Proxy Security                                     │
│ - API key validation                                        │
│ - Rate limiting                                             │
│ - SQL query validation (read-only enforcement)              │
│ - Query timeouts and row limits                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Database Security                                  │
│ - VPN encrypted tunnel                                      │
│ - Database authentication                                   │
│ - Read-only database user                                   │
│ - Query audit logging                                       │
└─────────────────────────────────────────────────────────────┘
```

### Security Features

#### 1. **Credential Management**
- Environment variables only (no hardcoded secrets)
- Separate credentials for dev/prod
- Password redaction in logs
- Secure credential storage

#### 2. **Authentication & Authorization**
- API key authentication for all services
- Bearer token support
- Role-based access control (future)
- Session management

#### 3. **Query Safety**
- Read-only enforcement (only SELECT queries)
- SQL injection prevention (parameterized queries)
- Query validation and sanitization
- Row limits (max 10,000 rows)
- Timeout protection (max 300 seconds)

#### 4. **Network Security**
- HTTPS/TLS 1.3 encryption
- Certificate-based authentication
- VPN tunnel for production access
- Firewall rules and network segmentation

#### 5. **Audit & Monitoring**
- Query logging
- Error tracking
- Performance metrics
- Security event logging

---

## 📚 API Documentation

### LangGraph Service API

**Base URL:** `http://localhost:5001`

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "mcp_server": "available"
}
```

#### Process Query
```http
POST /process_query
Content-Type: application/json

{
  "user_input": "How many customers do we have?",
  "api_key": "supersecretapikey"
}
```

**Response:**
```json
{
  "final_response": "You have 1,247 customers in the database.",
  "status": "success"
}
```

#### Process Conversation
```http
POST /process_conversation
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Show me sales data"},
    {"role": "assistant", "content": "What time period?"},
    {"role": "user", "content": "Last month"}
  ],
  "api_key": "supersecretapikey"
}
```

**Response:**
```json
{
  "final_response": "Here are the sales for last month...",
  "operation": "QUERY",
  "clarify": false,
  "messages": [...],
  "status": "success"
}
```

---

### MCP Server API

**Base URL:** `http://localhost:8000`

#### Call Tool
```http
POST /mcp
Content-Type: application/json
Authorization: Bearer supersecretapikey

{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT COUNT(*) FROM customers"
    }
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Query executed successfully. Results: [{'count': 1247}]"
      }
    ]
  },
  "id": 1
}
```

---

### Proxy Server API

**Base URL:** `https://10.255.152.48:5000`

#### Execute Query
```http
POST /query
Content-Type: application/json
X-API-Key: your_proxy_api_key

{
  "conn": "corp_sql_erp",
  "sql": "SELECT name FROM sys.databases",
  "limit": 10,
  "timeout_s": 30
}
```

**Response:**
```json
{
  "ok": true,
  "connection": "corp_sql_erp",
  "columns": ["name"],
  "rows": [["master"], ["tempdb"], ["model"], ["msdb"]],
  "rowcount": 4,
  "elapsed_ms": 12
}
```

---

## 💻 Development Guide

### Project Structure

```
code/
├── adrs/                          # Architecture Decision Records
│   ├── 0007-mcp-database-server-implementation.md
│   ├── 0010-dynamic-erp-assistant-complete-system-architecture.md
│   └── 0011-erp-proxy-integration-architecture.md
├── chatbot_ui/                    # Frontend interfaces
│   ├── index.html                 # Modern web UI
│   ├── styles.css                 # UI styling
│   ├── script.js                  # Frontend logic
│   ├── web_app.py                 # FastAPI web server
│   ├── app.py                     # Streamlit UI (legacy)
│   ├── langgraph_service.py       # LangGraph API wrapper
│   └── start_web_ui.py            # Startup script
├── langgraph_integration/         # Workflow engine
│   ├── graph_definition.py        # LangGraph workflow
│   ├── mcp_client.py              # MCP protocol client
│   ├── prompts.py                 # LLM prompts
│   ├── hybrid_db_client.py        # Unified database client
│   ├── proxy_db_client.py         # Proxy mode handler
│   └── direct_db_client.py        # Direct mode handler
├── mcp_server/                    # MCP protocol server
│   ├── server.py                  # FastAPI application
│   ├── db.py                      # Database connection pool
│   ├── tools.py                   # MCP tool implementations
│   ├── models.py                  # Pydantic models
│   └── database_adapter.py        # Database abstraction
├── vpn_config/                    # Proxy server
│   ├── proxy.py                   # Flask HTTPS proxy
│   ├── connections.yaml           # Database configurations
│   └── setup_proxy_windows.ps1    # Windows setup script
├── synthetic_data_service/        # Test data generator
│   ├── main.py                    # Data generation script
│   └── models.py                  # Data models
├── tests/                         # Test suite
│   ├── integration/               # Integration tests
│   └── unit/                      # Unit tests
├── scripts/                       # Utility scripts
├── exports/                       # Documentation exports
├── requirements.txt               # Python dependencies
├── .env.template                  # Environment template
└── README.md                      # This file
```

### Adding New Features

#### 1. Add a New MCP Tool

```python
# mcp_server/tools.py

async def new_tool(db_manager, arguments: dict):
    """
    New tool description.
    
    Args:
        db_manager: Database manager instance
        arguments: Tool arguments
    
    Returns:
        Tool result
    """
    # Implementation
    pass

# Register in TOOLS dictionary
TOOLS = {
    "new_tool": {
        "name": "new_tool",
        "description": "Tool description",
        "inputSchema": {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            },
            "required": ["param"]
        }
    }
}
```

#### 2. Add a New Workflow Node

```python
# langgraph_integration/graph_definition.py

def new_node(state: Dict) -> Dict:
    """
    New workflow node.
    
    Args:
        state: Current workflow state
    
    Returns:
        Updated state
    """
    # Implementation
    return state

# Add to workflow
workflow.add_node("new_node", new_node)
workflow.add_edge("previous_node", "new_node")
```

#### 3. Add a New Database Backend

```python
# langgraph_integration/new_db_client.py

class NewDatabaseClient:
    """Client for new database type."""
    
    async def get_schema(self) -> str:
        """Get database schema."""
        pass
    
    async def execute_query(self, sql: str) -> List[Dict]:
        """Execute query."""
        pass
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_mcp_servers.py

# Run with coverage
pytest --cov=langgraph_integration tests/

# Run integration tests
pytest tests/integration/
```

### Code Style

- **PEP 8** compliance
- **Type hints** for all functions
- **Docstrings** for all public methods
- **Error handling** with try/except blocks
- **Logging** for debugging and monitoring

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Cannot connect to MCP server"

**Symptoms:** LangGraph service cannot reach MCP server

**Solutions:**
```bash
# Check if MCP server is running
curl http://localhost:8000/health

# Start MCP server
cd mcp_server
python start_server.py

# Check firewall rules
# Ensure port 8000 is not blocked
```

#### 2. "OpenAI API key not set"

**Symptoms:** Error about missing OpenAI API key

**Solutions:**
```bash
# Set in .env file
echo "OPENAI_API_KEY=your_key_here" >> .env

# Or export environment variable
export OPENAI_API_KEY=your_key_here

# Verify
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

#### 3. "Database connection failed"

**Symptoms:** Cannot connect to PostgreSQL

**Solutions:**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection
psql -h localhost -U your_username -d synthetic_erp_data

# Check credentials in .env
cat .env | grep DB_
```

#### 4. "Proxy connection timeout"

**Symptoms:** Timeout when connecting to Windows proxy

**Solutions:**
```bash
# Test proxy connectivity
curl -k https://10.255.152.48:5000/health

# Check VPN connection on Windows machine
# Verify firewall allows port 5000

# Test with verbose output
curl -v -k -H "X-API-Key: your_key" https://10.255.152.48:5000/health
```

#### 5. "SQL syntax error"

**Symptoms:** Query fails with syntax error

**Solutions:**
- Check SQL dialect (PostgreSQL vs SQL Server)
- Verify table and column names
- Use schema qualification (e.g., `dbo.customers`)
- Check for reserved keywords

#### 6. "Import errors"

**Symptoms:** Python import errors

**Solutions:**
```bash
# Install dependencies
pip install -r requirements.txt

# Check Python version
python --version  # Should be 3.8+

# Verify installation
python -c "import langgraph; print(langgraph.__version__)"
```

### Service Health Checks

| Service | URL | Expected Response |
|---------|-----|-------------------|
| LangGraph Service | http://localhost:5001/health | `{"status": "healthy"}` |
| MCP Server | http://localhost:8000/health | `{"status": "healthy"}` |
| Web UI | http://localhost:3000 | Web interface loads |
| Proxy Server | https://10.255.152.48:5000/health | `{"status": "ok"}` |

### Debug Mode

Enable debug logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run with verbose output
python langgraph_service.py --verbose

# Check logs
tail -f logs/langgraph.log
```

---

## 📖 Architecture Decision Records

Comprehensive documentation of architectural decisions:

- **[ADR-0007](../adrs/0007-mcp-database-server-implementation.md)** - MCP Database Server Implementation
- **[ADR-0010](../adrs/0010-dynamic-erp-assistant-complete-system-architecture.md)** - Dynamic ERP Assistant Complete System Architecture
- **[ADR-0011](../adrs/0011-erp-proxy-integration-architecture.md)** - ERP Proxy Integration Architecture

Additional ADRs:
- ADR-0001: Synthetic Data Service Architecture
- ADR-0002: Synthetic Data Results and Database Access
- ADR-0003: PostgreSQL Migration and Enhanced Data Generation
- ADR-0004: Crawling Agent Architecture
- ADR-0005: Model Context Protocol
- ADR-0006: Agent Architecture and Data Integration
- ADR-0008: ERP Chatbot UI Complete System Architecture
- ADR-0009: Context-Aware ERP Assistant Query Processing Flow

---

## 🤝 Contributing

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test**
   ```bash
   pytest tests/
   ```

3. **Commit with descriptive messages**
   ```bash
   git commit -m "Add: New feature description"
   ```

4. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

```
Type: Brief description

Detailed explanation of changes.

- Bullet point 1
- Bullet point 2

Closes #issue_number
```

**Types:** Add, Fix, Update, Refactor, Docs, Test, Style

---

## 📄 License

This project is part of a Master's Thesis and is intended for educational and research purposes.

---

## 📞 Support

For issues, questions, or contributions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review [Architecture Decision Records](#architecture-decision-records)
3. Check existing issues in the repository
4. Create a new issue with detailed information

---

## 🎓 Academic Context

This system is part of a Master's Thesis on **"Multi-Agent Systems for Data Fusion Across Heterogeneous Data Sources"**.

**Key Research Areas:**
- Natural language interfaces for databases
- Multi-agent system architectures
- Secure proxy-based database access
- LLM-powered query generation
- Model Context Protocol (MCP) integration

---

## 🔄 Version History

- **v1.0.0** - Initial release with core functionality
- **v1.1.0** - Added MCP server integration
- **v1.2.0** - Implemented proxy architecture for VPN access
- **v1.3.0** - Added modern web UI
- **v1.4.0** - Enhanced LangGraph workflow with clarification handling

---

## 🚀 Future Enhancements

### Planned Features

1. **Multi-Database Support**
   - MongoDB integration for document store
   - Neo4j integration for graph database
   - Unified query interface across all databases

2. **Advanced Query Features**
   - Query history and favorites
   - Query templates and macros
   - Batch query execution
   - Scheduled queries

3. **Enhanced Security**
   - OAuth2/JWT authentication
   - Role-based access control (RBAC)
   - Query approval workflows
   - Audit trail visualization

4. **Performance Optimization**
   - Query result caching (Redis)
   - Connection pooling improvements
   - Streaming responses for large datasets
   - Query optimization suggestions

5. **User Experience**
   - Voice input support
   - Query suggestions and autocomplete
   - Data visualization (charts, graphs)
   - Export to CSV/Excel/PDF

6. **Monitoring & Observability**
   - Prometheus metrics integration
   - Grafana dashboards
   - Distributed tracing (OpenTelemetry)
   - Real-time performance monitoring

---

**Built with ❤️ for the Master's Thesis Project**

*Last Updated: 2024-12-19*