# Simple SQL Agent - ERP Natural Language Query System

A text-to-SQL system that enables natural language queries against an ERP database using a single ReAct agent.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Question                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Web UI (Port 3000)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Simple SQL Agent (Port 5001)                   │
│                                                              │
│  Single ReAct Agent (GPT-4o) with 4 tools:                  │
│  • list_tables - Discover available tables                   │
│  • get_schema - Get column details and relationships         │
│  • validate_sql - Check MSSQL syntax                         │
│  • execute_query - Run SELECT queries                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 MCP Server (Port 8000)                       │
│                 (Runs on Windows)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MSSQL Database                            │
│                    (On-Premise ERP)                          │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

1. **MCP Server running on Windows** (connects to MSSQL database)
2. **Python 3.10+** on Mac
3. **OpenAI API key**

### Configuration

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here
MCP_SERVER_URL=http://YOUR_WINDOWS_IP:8000
MCP_API_KEY=supersecretapikey

# Optional
API_KEY=supersecretapikey  # For API authentication
```

### Running the System

```bash
# Start all services (Web UI + SQL Agent)
./start_scripts/start_all_services_mac.sh
```

This will:
1. Install dependencies
2. Check MCP server connectivity
3. Start Simple SQL Agent on port 5001
4. Start Web UI on port 3000

### Access

- **Web UI**: http://localhost:3000
- **SQL Agent API**: http://localhost:5001
- **Health Check**: http://localhost:5001/health

### Stop

Press `Ctrl+C` in the terminal running the script.

## Project Structure

```
.
├── simple_sql_agent/          # Main SQL agent package
│   ├── agent.py               # ReAct agent using LangGraph
│   ├── service.py             # FastAPI service (port 5001)
│   ├── tools/                 # 4 database tools
│   ├── prompts/               # System prompt with domain knowledge
│   └── db/                    # MCP client for database access
├── chatbot_ui/                # Web interface
│   ├── web_app.py             # FastAPI server (port 3000)
│   └── index.html, script.js  # Frontend assets
├── mcp_server/                # MCP database server (runs on Windows)
├── data/
│   └── concepts.json          # Domain knowledge (KPIs, joins)
├── adrs/                      # Architecture Decision Records
├── start_scripts/             # Startup scripts
└── eval/                      # Evaluation framework
```

## API Endpoints

### SQL Agent (Port 5001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with MCP status |
| `/query` | POST | Process a single question |
| `/process_conversation` | POST | Process conversation (frontend compatible) |

### Query Request

```json
POST /query
{
  "question": "Who are our top 5 customers by revenue?"
}
```

### Query Response

```json
{
  "answer": "Based on the data...",
  "sql_query": "SELECT TOP 5...",
  "success": true,
  "latency_ms": 2500
}
```

## Running Benchmarks

```bash
cd simple_sql_agent
python run_benchmark.py --max 12
```

## Documentation

- [ADR 0030: Simple SQL Agent Architecture](adrs/0030-simple-sql-agent-architecture.md)

## License

MIT
