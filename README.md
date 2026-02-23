<!-- Logo placeholder -->
<p align="center">
  <!-- TODO: Add your logo here -->
  <!-- <img src="docs/images/logo.png" alt="ERP Assistant Logo" width="200"/> -->
  <h1 align="center">ERP Natural Language Query Assistant</h1>
</p>

<p align="center">
  <strong>Transform natural language into SQL queries for your ERP database</strong>
</p>

<!-- Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/LangGraph-0.2+-green.svg" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100+-teal.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"/>
  <img src="https://img.shields.io/badge/MSSQL-2019+-red.svg" alt="MSSQL"/>
  <!-- TODO: Add more badges as needed -->
  <!-- <img src="https://img.shields.io/github/stars/youruser/yourrepo?style=social" alt="GitHub Stars"/> -->
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#api-reference">API</a> •
  <a href="#documentation">Docs</a>
</p>

---

<!-- Interface Screenshot -->
<p align="center">
  <img src="docs/interface-screenshot.png" alt="ERP Assistant Interface" width="800"/>
</p>

---

## Features

- **Natural Language Queries** - Ask questions in plain English or German
- **Intelligent Table Discovery** - Automatically finds relevant tables using semantic search
- **SQL Generation & Validation** - Generates and validates MSSQL syntax
- **Interactive Clarifications** - Asks follow-up questions when queries are ambiguous
- **Real-time Streaming** - See results as they're generated
- **Secure Architecture** - API keys managed server-side, no client exposure

---

## Architecture

### System Overview

```mermaid
flowchart TB
    subgraph Client["🖥️ Client Layer"]
        UI[Web UI<br/>Port 3000]
    end

    subgraph Agent["🤖 Agent Layer"]
        SA[SQL Agent<br/>Port 5001]
        LG[LangGraph<br/>ReAct Agent]
    end

    subgraph MCP["🔌 MCP Layer"]
        MS[MCP Server<br/>Port 8000]
        SC[Scout Cache<br/>Table Metadata]
    end

    subgraph Data["💾 Data Layer"]
        DB[(MSSQL<br/>ERP Database)]
    end

    UI -->|HTTP/JSON| SA
    SA --> LG
    LG -->|Tool Calls| MS
    MS --> SC
    MS -->|SQL Queries| DB

    style Client fill:#e1f5fe
    style Agent fill:#fff3e0
    style MCP fill:#f3e5f5
    style Data fill:#e8f5e9
```

### Query Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Web UI
    participant A as SQL Agent
    participant M as MCP Server
    participant DB as Database

    U->>UI: "Show top 10 customers by revenue"
    UI->>A: POST /process_conversation

    A->>A: Parse Intent
    A->>M: list_tables(query)
    M->>M: Semantic Search
    M-->>A: Relevant Tables

    A->>M: get_schema(tables)
    M-->>A: Column Details

    A->>A: Generate SQL
    A->>M: validate_sql(query)
    M-->>A: Valid ✓

    A->>M: execute_query(sql)
    M->>DB: SELECT TOP 10...
    DB-->>M: Results
    M-->>A: Data

    A->>A: Format Answer
    A-->>UI: Response + SQL
    UI-->>U: Display Results
```

### Component Architecture

```mermaid
flowchart LR
    subgraph Tools["🔧 Agent Tools"]
        T1[list_tables]
        T2[get_schema]
        T3[validate_sql]
        T4[execute_query]
    end

    subgraph Scout["🔍 Scout Mode"]
        S1[Semantic Search]
        S2[CamelCase Parser]
        S3[Fuzzy Matching]
        S4[Token Decomposition]
    end

    subgraph Cache["📦 Catalog Cache"]
        C1[Table Metadata]
        C2[Column Types]
        C3[Row Counts]
    end

    T1 --> S1
    S1 --> S2
    S1 --> S3
    S1 --> S4
    S1 --> C1
    T2 --> C2
    T2 --> C3

    style Tools fill:#fff3e0
    style Scout fill:#e8f5e9
    style Cache fill:#f3e5f5
```

---

## Quick Start

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Agent runtime |
| Node.js | 18+ | Optional, for development |
| MSSQL | 2019+ | ERP database |
| OpenAI API | - | GPT-4o access |

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/erp-assistant.git
cd erp-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here
MCP_SERVER_URL=http://YOUR_WINDOWS_IP:8000
MCP_API_KEY=your-mcp-api-key

# Optional
API_KEY=your-api-key  # For API authentication
```

### Running the System

```bash
# Start all services (Web UI + SQL Agent)
./start_scripts/start_all_services_mac.sh
```

This will:
1. Install dependencies
2. Check MCP server connectivity
3. Start SQL Agent on port 5001
4. Start Web UI on port 3000

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:3000 | Chat interface |
| SQL Agent API | http://localhost:5001 | Agent endpoints |
| Health Check | http://localhost:5001/health | Service status |

### Deployment (Railway, Northwind Demo)

For production-style deployment with Northwind/Postgres on Railway, use the runbook:

- [deploy/railway/README.md](deploy/railway/README.md)

Railway Dockerfiles:

- `deploy/railway/Dockerfile.web-ui`
- `deploy/railway/Dockerfile.sql-agent`
- `deploy/railway/Dockerfile.mcp-server`

---

## API Reference

### Query Endpoint

```http
POST /query
Content-Type: application/json

{
  "question": "Who are our top 5 customers by revenue?"
}
```

**Response:**
```json
{
  "answer": "Based on the sales data, your top 5 customers are...",
  "sql_query": "SELECT TOP 5 c.Name, SUM(s.Amount) as Revenue...",
  "success": true,
  "latency_ms": 2500
}
```

### Conversation Endpoint

```http
POST /process_conversation
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Show me sales by region"}
  ]
}
```

### Health Endpoint

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "mcp_connected": true,
  "catalog_tables": 943,
  "version": "1.0.0"
}
```

---

## Project Structure

```
.
├── simple_sql_agent/          # Main SQL agent package
│   ├── agent.py               # ReAct agent using LangGraph
│   ├── service.py             # FastAPI service (port 5001)
│   ├── tools/                 # Database tools
│   └── prompts/               # System prompts
├── chatbot_ui/                # Web interface
│   ├── web_app.py             # FastAPI server (port 3000)
│   ├── index.html             # Chat interface
│   ├── styles.css             # Styling
│   └── script.js              # Frontend logic
├── mcp_server/                # MCP database server
│   ├── scout/                 # Semantic search
│   │   └── runner.py          # Table ranking algorithm
│   └── catalog/               # Metadata caching
├── data/
│   └── concepts.json          # Domain knowledge
├── adrs/                      # Architecture Decision Records
├── start_scripts/             # Startup scripts
└── eval/                      # Evaluation framework
```

---

## Documentation

### Architecture Decision Records

| ADR | Title | Status |
|-----|-------|--------|
| [0030](adrs/0030-simple-sql-agent-architecture.md) | Simple SQL Agent Architecture | Accepted |
| [0031](adrs/0031-erp-chatbot-frontend-architecture-decision.md) | Frontend Architecture Decision | Accepted |
| [0032](adrs/0032-generic-table-search-ranking-fixes.md) | Generic Table Search Ranking | Accepted |

### Key Concepts

- **Scout Mode** - Pre-computed table metadata for fast semantic search
- **ReAct Agent** - Reasoning + Acting pattern for query decomposition
- **MCP Protocol** - Model Context Protocol for database access

---

## Running Benchmarks

```bash
cd simple_sql_agent
python run_benchmark.py --max 12
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## Authors

<!-- TODO: Fill in author information -->
<table>
  <tr>
    <td align="center">
      <!-- <img src="https://github.com/yourusername.png" width="100px;" alt=""/> -->
      <br />
      <sub><b>Your Name</b></sub>
      <br />
      <!-- <a href="https://github.com/yourusername">GitHub</a> • -->
      <!-- <a href="https://linkedin.com/in/yourprofile">LinkedIn</a> -->
    </td>
  </tr>
</table>

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with <a href="https://www.langchain.com/langgraph">LangGraph</a> and <a href="https://openai.com">OpenAI</a>
</p>
