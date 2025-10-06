# Dynamic ERP Assistant - Architecture Overview

**Last Updated**: January 2025 (Post-Phase 7)  
**Version**: 2.0 (MCP-Only Architecture)  
**Status**: Production Ready

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Design Principles](#design-principles)
7. [Security & Privacy](#security--privacy)
8. [Performance & Scalability](#performance--scalability)
9. [Deployment](#deployment)
10. [Future Roadmap](#future-roadmap)

---

## 🎯 Executive Summary

The **Dynamic ERP Assistant** is an AI-powered chatbot that provides natural language access to ERP databases. It uses **LangGraph** for agent orchestration, **MCP (Model Context Protocol)** for database access, and **GPT-4** for natural language understanding.

### Key Features

✅ **Natural Language Queries**: Ask questions in plain English  
✅ **Multi-Database Support**: SQL Server, PostgreSQL  
✅ **Schema Discovery**: Automatic table and column detection  
✅ **Safe Query Execution**: Read-only, bounded, validated queries  
✅ **Context-Aware**: Maintains conversation history  
✅ **Clarification Handling**: Asks for missing information  
✅ **Streaming Responses**: Real-time answer generation  

### Architecture Highlights

- **MCP-Only Database Access**: Single interface, no drift risk
- **Design Guardrails**: Pagination, rate limiting, bounded queries
- **LangGraph Agent**: Stateful, multi-step reasoning
- **Streamlit UI**: Simple, intuitive chat interface
- **FastAPI Backend**: High-performance async API

---

## 🏗️ System Architecture

### High-Level Architecture (Post-Phase 7)

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│                     (Streamlit Chat UI)                      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│                    (Agent Orchestration)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     LangGraph Agent                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Query   │→ │  Schema  │→ │   SQL    │→ │ Response │   │
│  │ Planning │  │Discovery │  │Generation│  │Formatting│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP JSON-RPC
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                       MCP Server                             │
│                     (port 8000)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ search_tables│  │describe_table│  │ execute_query│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │ SQL
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  SQL Server  │  │  PostgreSQL  │  │   (Future)   │     │
│  │   (ERP DB)   │  │ (Synthetic)  │  │   MongoDB    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User Query
    │
    ▼
┌─────────────┐
│ Streamlit   │ "Show me top 5 customers by revenue"
│    UI       │
└──────┬──────┘
       │ POST /chat
       ▼
┌─────────────┐
│  FastAPI    │ Route to LangGraph agent
│  Backend    │
└──────┬──────┘
       │ invoke()
       ▼
┌─────────────┐
│ LangGraph   │ 1. Parse query
│   Agent     │ 2. Search for "customer" tables
│             │ 3. Describe relevant tables
│             │ 4. Generate SQL
│             │ 5. Execute query
│             │ 6. Format response
└──────┬──────┘
       │ MCP JSON-RPC
       ▼
┌─────────────┐
│ MCP Server  │ search_tables("customer")
│             │ describe_table("dbo.customers")
│             │ execute_query("SELECT TOP 5 ...")
└──────┬──────┘
       │ SQL
       ▼
┌─────────────┐
│  Database   │ Execute query, return results
└─────────────┘
```

---

## 🔧 Component Details

### 1. User Interface (Streamlit)

**Location**: `chatbot_ui/`

**Purpose**: Provides a simple, intuitive chat interface for users.

**Features**:
- Chat history display
- Message input
- Streaming responses
- Error handling
- Session management

**Technology**: Streamlit, Python

**Key Files**:
- `chatbot_ui/app.py` - Main UI application
- `chatbot_ui/components/` - Reusable UI components

### 2. FastAPI Backend

**Location**: `app/`

**Purpose**: Handles HTTP requests, routes to LangGraph agent, manages sessions.

**Features**:
- RESTful API endpoints
- WebSocket support for streaming
- Session management
- Error handling
- Logging

**Technology**: FastAPI, Python, Uvicorn

**Key Files**:
- `app/main.py` - FastAPI application
- `app/routers/` - API route handlers
- `app/models/` - Pydantic models

**Endpoints**:
- `POST /chat` - Send user message, get agent response
- `GET /health` - Health check
- `GET /sessions` - List active sessions
- `DELETE /sessions/{id}` - Clear session

### 3. LangGraph Agent

**Location**: `langgraph_integration/`

**Purpose**: Orchestrates multi-step reasoning, query planning, SQL generation.

**Features**:
- Stateful conversation management
- Multi-step reasoning
- Schema discovery
- SQL generation
- Query validation
- Response formatting
- Clarification handling

**Technology**: LangGraph, LangChain, OpenAI GPT-4

**Key Files**:
- `langgraph_integration/agent.py` - Agent definition
- `langgraph_integration/nodes/` - Agent nodes (query planning, SQL generation, etc.)
- `langgraph_integration/proxy_db_client.py` - Database client wrapper

**Agent Workflow**:
```
Start
  │
  ▼
Parse Query ──> Ambiguous? ──Yes──> Ask Clarification ──> Wait for User
  │                                                            │
  No                                                           │
  │                                                            │
  ▼                                                            │
Search Tables ◄──────────────────────────────────────────────┘
  │
  ▼
Describe Tables
  │
  ▼
Generate SQL
  │
  ▼
Validate SQL ──> Invalid? ──Yes──> Retry (max 3)
  │                                      │
  No                                     │
  │                                      │
  ▼                                      │
Execute Query ◄────────────────────────┘
  │
  ▼
Format Response
  │
  ▼
End
```

### 4. MCP Server

**Location**: `mcp_server/`

**Purpose**: Provides MCP JSON-RPC interface for database access.

**Features**:
- MCP JSON-RPC 2.0 protocol
- Schema discovery tools
- Safe query execution
- Catalog caching
- Response caching
- Rate limiting
- Structured logging

**Technology**: Python, FastAPI, MCP SDK

**Key Files**:
- `mcp_server/server.py` - MCP server implementation
- `mcp_server/tools/` - MCP tool implementations
- `mcp_server/cache/` - Caching layer

**MCP Tools**:
1. **search_tables** - Search for tables by pattern
2. **describe_table** - Get table schema (columns, types, keys)
3. **list_relations** - Get foreign key relationships
4. **execute_query** - Execute safe SELECT queries

**Configuration**:
```bash
MCP_SERVER_URL=http://localhost:8000/mcp
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_BACKOFF_FACTOR=2.0
```

### 5. MCP Database Client

**Location**: `app/db/mcp_client.py`

**Purpose**: Python client for MCP server, used by LangGraph agent.

**Features**:
- MCP JSON-RPC protocol support
- Exponential backoff with Retry-After
- Discovery tools wrapper
- Design guardrails enforcement
- Structured logging
- Configuration management

**Technology**: Python, Requests

**Usage**:
```python
from app.db.mcp_client import MCPDatabaseClient

client = MCPDatabaseClient()

# Search for tables
tables = client.search_tables("customer", limit=20)

# Describe table
info = client.describe_table("dbo.customers")

# Execute query
columns, rows = client.query("SELECT * FROM customers LIMIT 10")

# Health check
is_healthy = client.health_check()
```

### 6. Database Layer

**Databases**:
1. **SQL Server** (Production ERP)
   - Host: 192.168.200.16:1433
   - Access: Via VPN (Windows proxy)
   - Schema: dbo (default)

2. **PostgreSQL** (Synthetic Data)
   - Host: localhost:5432
   - Access: Direct connection
   - Schema: public

**Access Pattern**:
- All access goes through MCP server
- Read-only queries (SELECT only)
- Row limits enforced (max 1000)
- Timeouts enforced (30 seconds)
- Parameterized queries (SQL injection prevention)

---

## 🔄 Data Flow

### Query Processing Flow

```
1. User Input
   │
   ▼
2. FastAPI receives request
   │
   ▼
3. LangGraph agent invoked
   │
   ├─> 4. Parse query intent
   │
   ├─> 5. Search for relevant tables (MCP: search_tables)
   │
   ├─> 6. Describe table schemas (MCP: describe_table)
   │
   ├─> 7. Generate SQL query (GPT-4)
   │
   ├─> 8. Validate SQL (safety checks)
   │
   ├─> 9. Execute query (MCP: execute_query)
   │
   ├─> 10. Format results (GPT-4)
   │
   ▼
11. Return response to user
```

### Schema Discovery Flow

```
1. Agent needs schema info
   │
   ▼
2. Check session cache
   │
   ├─> Cache hit? ──Yes──> Return cached schema
   │                            │
   No                           │
   │                            │
   ▼                            │
3. Call MCP search_tables ◄────┘
   │
   ▼
4. Call MCP describe_table for each table
   │
   ▼
5. Build schema index
   │
   ▼
6. Cache in session
   │
   ▼
7. Return schema
```

### Caching Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    Caching Layers                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Session Cache (LangGraph)                           │
│     - Lifetime: Session duration                        │
│     - Scope: Per conversation                           │
│     - Contents: Schema index, query history             │
│                                                          │
│  2. Response Cache (MCP Server)                         │
│     - Lifetime: 5 minutes                               │
│     - Scope: Global                                     │
│     - Contents: Query results                           │
│                                                          │
│  3. Catalog Cache (MCP Server)                          │
│     - Lifetime: 1 hour                                  │
│     - Scope: Global                                     │
│     - Contents: Table schemas, metadata                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### Backend
- **Python 3.11+** - Core language
- **FastAPI** - Web framework
- **LangGraph** - Agent orchestration
- **LangChain** - LLM integration
- **OpenAI GPT-4** - Natural language understanding
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### Database Access
- **MCP (Model Context Protocol)** - Database interface
- **pyodbc** - SQL Server driver
- **psycopg2** - PostgreSQL driver
- **SQLAlchemy** - ORM (optional)

### Frontend
- **Streamlit** - UI framework
- **Python** - UI logic

### Infrastructure
- **Docker** - Containerization (planned)
- **Nginx** - Reverse proxy (planned)
- **Redis** - Session storage (planned)

### Development Tools
- **pytest** - Testing framework
- **black** - Code formatting
- **mypy** - Type checking
- **flake8** - Linting

---

## 🎓 Design Principles

### 1. Single Interface Principle ✅
**Principle**: One interface for database access eliminates drift risk.

**Implementation**:
- MCP is the only database access path
- Legacy Flask `/query` endpoint deprecated (410 Gone)
- All code uses `MCPDatabaseClient`

**Benefits**:
- No synchronization issues
- Easier to maintain
- Simpler testing

### 2. Design Guardrails ✅
**Principle**: Enforce best practices in code, not just documentation.

**Implementation**:
- **Pagination Required**: `search_tables()` requires limit parameter
- **Bounded Queries**: Max 1000 rows per query
- **Small Prompts**: Encourage ≤3 tables per context
- **Caching**: Catalog + response + session caching
- **Backpressure**: Rate limiting + Retry-After + exponential backoff

**Benefits**:
- Prevents performance issues
- Ensures scalability
- Automatic best practices

### 3. Read-Only, Safe Queries ✅
**Principle**: Only SELECT statements allowed, no writes.

**Implementation**:
- SQL validation before execution
- Parameterized queries (SQL injection prevention)
- Row limits enforced
- Timeouts enforced (30 seconds)

**Benefits**:
- Data safety
- No accidental modifications
- Predictable performance

### 4. Proxy-Only Separation ✅
**Principle**: Proxy is a pass-through, no business logic.

**Implementation**:
- MCP server only handles database access
- All business logic in LangGraph agent
- No credentials in agent code

**Benefits**:
- Clear separation of concerns
- Security (credentials isolated)
- Easier to test

### 5. JSON as Single Data Format ✅
**Principle**: All APIs return structured JSON.

**Implementation**:
- MCP JSON-RPC protocol
- FastAPI JSON responses
- Pydantic models for validation

**Benefits**:
- Type safety
- Easy to parse
- Language-agnostic

---

## 🔒 Security & Privacy

### Authentication & Authorization
- **API Key Authentication**: All MCP requests require API key
- **Environment Variables**: Credentials stored in `.env` files
- **No Hard-Coded Secrets**: All secrets from environment

### Data Protection
- **Read-Only Access**: Only SELECT queries allowed
- **PII Redaction**: Sensitive data redacted in logs
- **SQL Injection Prevention**: Parameterized queries
- **Row Limits**: Max 1000 rows per query

### Network Security
- **HTTPS/TLS**: All external communication encrypted (planned)
- **VPN Access**: Production database behind VPN
- **Local Network**: MCP server on localhost only

### Logging & Monitoring
- **Structured Logging**: All operations logged with context
- **PII Redaction**: Sensitive data removed from logs
- **Audit Trail**: All queries logged for compliance

---

## ⚡ Performance & Scalability

### Performance Optimizations

1. **Catalog Caching** (1 hour TTL)
   - Schema metadata cached
   - Reduces database load
   - Faster schema discovery

2. **Response Caching** (5 minutes TTL)
   - Query results cached
   - Reduces redundant queries
   - Faster responses

3. **Session Caching** (session lifetime)
   - Schema index cached per conversation
   - Reduces MCP calls
   - Faster multi-turn conversations

4. **Pagination** (required)
   - Never enumerate full schema
   - Bounded result sets
   - Predictable memory usage

5. **Rate Limiting** (automatic)
   - Respects Retry-After headers
   - Exponential backoff on errors
   - Prevents overload

### Scalability Considerations

**Current Capacity**:
- Single MCP server instance
- Handles ~100 concurrent users
- ~1000 queries/hour

**Future Scaling**:
- Horizontal scaling (multiple MCP servers)
- Load balancing (Nginx)
- Distributed caching (Redis)
- Database read replicas

---

## 🚀 Deployment

### Development Environment

```bash
# 1. Clone repository
git clone <repo-url>
cd code

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
.venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Start MCP server
python mcp_server/server.py

# 6. Start FastAPI backend
uvicorn app.main:app --reload

# 7. Start Streamlit UI
streamlit run chatbot_ui/app.py
```

### Production Deployment (Planned)

```bash
# 1. Build Docker images
docker-compose build

# 2. Start services
docker-compose up -d

# 3. Verify health
curl http://localhost:8000/health
curl http://localhost:8001/mcp/health

# 4. Monitor logs
docker-compose logs -f
```

### Environment Variables

```bash
# Database
SQLSERVER_HOST=192.168.200.16
SQLSERVER_PORT=1433
SQLSERVER_DB=master
SQLSERVER_USER=<username>
SQLSERVER_PASSWORD=<password>

# MCP Server
MCP_SERVER_URL=http://localhost:8000/mcp
MCP_TIMEOUT_SECONDS=30
MCP_MAX_RETRIES=3
MCP_BACKOFF_FACTOR=2.0

# OpenAI
OPENAI_API_KEY=<your-key>

# Logging
LOG_LEVEL=INFO
```

---

## 🗺️ Future Roadmap

### Phase 8: Multi-Source Data Integration (Q1 2025)

**Goals**:
- Integrate MongoDB document store
- Add Neo4j graph database
- Create unified data access layer

**Architecture**:
```
┌─────────────┐
│  LangGraph  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  Unified Data Access    │
│  Abstraction Layer      │
└────┬──────┬──────┬──────┘
     │      │      │
     ▼      ▼      ▼
  ┌───┐  ┌───┐  ┌───┐
  │MCP│  │Mongo│ │Neo4j│
  └───┘  └───┘  └───┘
```

### Phase 9: Advanced Features (Q2 2025)

**Goals**:
- Query optimization suggestions
- Automatic index recommendations
- Performance analytics
- Multi-language support

### Phase 10: Production Hardening (Q3 2025)

**Goals**:
- Horizontal scaling
- Load balancing
- Distributed caching
- High availability
- Disaster recovery

---

## 📚 Documentation Index

### Core Documentation
1. **Architecture Overview**: `docs/ARCHITECTURE_OVERVIEW.md` (this file)
2. **Phase 7 Complete**: `docs/PHASE_7_COMPLETE.md`
3. **Migration Guide**: `docs/MIGRATION_GUIDE_PHASE_7.md`
4. **MCP Client README**: `app/db/README.md`
5. **MCP Server README**: `mcp_server/README.md`

### ADRs (Architecture Decision Records)
1. **ADR-0005**: Model Context Protocol
2. **ADR-0006**: Agent Architecture and Data Integration
3. **ADR-0007**: MCP Database Server Implementation
4. **ADR-0010**: Dynamic ERP Assistant Complete System Architecture
5. **ADR-0011**: Proxy for VPN Tunneling (deprecated)

### Phase Documentation
1. **Phase 6 Complete**: `docs/PHASE_6_COMPLETE.md`
2. **Phase 7 Plan**: `docs/PHASE_7_PLAN.md`
3. **Phase 7 Summary**: `docs/PHASE_7_SUMMARY.md`
4. **Phase 7 Checklist**: `docs/PHASE_7_CHECKLIST.md`

---

## 🎉 Conclusion

The Dynamic ERP Assistant provides a robust, scalable, and secure platform for natural language database access. With Phase 7 complete, the system now uses a clean MCP-only architecture that eliminates technical debt and provides a solid foundation for future enhancements.

**Key Strengths**:
- ✅ Single interface (MCP-only) eliminates complexity
- ✅ Design guardrails enforced in code
- ✅ Comprehensive caching strategy
- ✅ Safe, read-only database access
- ✅ Well-tested and documented

**Ready for**:
- ✅ Production deployment
- ✅ Multi-source data integration (Phase 8)
- ✅ Advanced features (Phase 9+)

---

**Document Version**: 2.0  
**Last Updated**: January 2025 (Post-Phase 7)  
**Maintained By**: Dynamic ERP Assistant Team  
**Status**: Production Ready ✅