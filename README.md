# ERP Natural Language Assistant

<p align="center">
  <strong>Natural language to SQL interface for MSSQL databases.</strong>
</p>

<p align="center">
  <img src="docs/interface-screenshot.png" alt="ERP Assistant Interface" width="700"/>
</p>

---

## Problem Statement

Enterprise databases contain valuable business insights, but accessing them requires:
- Technical SQL knowledge
- Understanding of complex database schemas
- IT department involvement for ad-hoc queries

**Result:** Business users face delays for simple data retrieval tasks.

---

## Solution

An AI-powered assistant that translates natural language questions into SQL queries and retrieves data from MSSQL databases.

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'background': 'transparent'}}}%%
flowchart LR
    A["💬 Natural Language Input"] --> B["🤖 Intent Recognition"]
    B --> C["🔍 Table Discovery"]
    C --> D["📊 Query Execution"]

    style A fill:#e3f2fd,stroke:#1976d2,color:#1565c0
    style B fill:#fff3e0,stroke:#f57c00,color:#e65100
    style C fill:#f3e5f5,stroke:#7b1fa2,color:#6a1b9a
    style D fill:#e8f5e9,stroke:#388e3c,color:#2e7d32
```

---

## How It Works

### 1. Natural Language Input

The system accepts queries in plain language (German and English):

> *"Show me the top 10 customers by revenue this year"*
>
> *"Which products had the highest sales growth last quarter?"*
>
> *"What's the average order value by region?"*

### 2. Intelligent Table Discovery

The system automatically:
- Identifies relevant tables from the database schema
- Resolves relationships between entities
- Generates appropriate SQL queries

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'background': 'transparent'}}}%%
flowchart TB
    Q["User Query"] --> AI["LLM Agent"]

    subgraph Understanding["Intent Parsing"]
        AI --> T1["Entity: Customers"]
        AI --> T2["Metric: Revenue"]
        AI --> T3["Filter: Time Period"]
    end

    subgraph Finding["Schema Search"]
        T1 --> DB[("MSSQL Database<br/>940+ Tables")]
        T2 --> DB
        T3 --> DB
    end

    DB --> R["Query Results"]

    style Q fill:#e3f2fd,stroke:#1976d2,color:#1565c0
    style AI fill:#fff3e0,stroke:#f57c00,color:#e65100
    style Understanding fill:#fafafa,stroke:#bdbdbd
    style Finding fill:#fafafa,stroke:#bdbdbd
    style DB fill:#f3e5f5,stroke:#7b1fa2,color:#6a1b9a
    style R fill:#e8f5e9,stroke:#388e3c,color:#2e7d32
```

### 3. Result Presentation

Responses include:
- Formatted answers to the query
- Data tables where applicable
- Support for follow-up questions in conversational context

---

## Architecture

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'background': 'transparent'}}}%%
flowchart TB
    subgraph Client["Client Layer"]
        UI["Web Interface<br/>Port 3000"]
    end

    subgraph Agent["Agent Layer"]
        SA["SQL Agent<br/>Port 5001"]
        LLM["LLM<br/>(GPT-4)"]
    end

    subgraph MCP["Data Access Layer"]
        MS["MCP Server<br/>Port 8000"]
        SC["Scout Index"]
    end

    subgraph Data["Storage Layer"]
        DB[("MSSQL / PostgreSQL")]
    end

    UI <--> SA
    SA <--> LLM
    SA <--> MS
    MS <--> SC
    MS <--> DB

    style Client fill:#e3f2fd,stroke:#1976d2
    style Agent fill:#fff3e0,stroke:#f57c00
    style MCP fill:#f3e5f5,stroke:#7b1fa2
    style Data fill:#e8f5e9,stroke:#388e3c
```

### Components

| Component | Purpose |
|-----------|---------|
| **Web Interface** | Chat-based UI for query input and result display |
| **SQL Agent** | LangGraph-based ReAct agent for query decomposition |
| **MCP Server** | Database abstraction layer with tool endpoints |
| **Scout Index** | Pre-computed table metadata for semantic search |

---

## Features

| Feature | Description |
|---------|-------------|
| **Natural Language Processing** | Supports German and English queries |
| **Semantic Table Discovery** | Finds relevant tables among 900+ candidates |
| **Real-time Streaming** | Server-Sent Events for progressive response display |
| **Conversational Context** | Maintains session state for follow-up queries |
| **Read-only Access** | No data modification capabilities |

---

## Use Cases

**Sales Analytics**
- Revenue by customer, product, or region
- Sales trends and growth analysis
- Performance comparisons

**Inventory Management**
- Stock levels and availability
- Product performance metrics

**Operations**
- Order fulfillment statistics
- Supplier analysis
- Cost breakdowns

---

## Getting Started

### Prerequisites

- Python 3.10+
- MSSQL or PostgreSQL database (read-only access)
- OpenAI API key ([platform.openai.com](https://platform.openai.com/api-keys))

### Installation

```bash
# Clone repository
git clone https://github.com/julianus-kath/erp-assistant.git
cd erp-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Required environment variables:
```
OPENAI_API_KEY=sk-...
MCP_SERVER_URL=http://database-server:8000
```

### Running

```bash
./start_scripts/start_all_services.sh
```

### Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Web Interface | http://localhost:3000 | Chat UI |
| Agent API | http://localhost:5001 | Query endpoints |
| Health Check | http://localhost:5001/health | Service status |

---

## Project Structure

```
├── simple_sql_agent/       # LangGraph agent implementation
│   ├── agent.py            # ReAct agent logic
│   ├── service.py          # FastAPI service
│   └── prompts/            # System prompts
├── chatbot_ui/             # Web interface
├── mcp_server/             # Database access layer
│   ├── scout/              # Semantic search
│   └── catalog/            # Schema caching
├── eval/                   # Evaluation framework
└── adrs/                   # Architecture Decision Records
```

---

## About

Master's thesis project exploring LLM-based natural language to SQL translation.

**Author:** Julianus Kath

**Stack:** Python, LangGraph, FastAPI, GPT-4, MSSQL

---

<p align="center">
  <em>Natural language to SQL for MSSQL databases.</em>
</p>
