# ADR-0010: Dynamic ERP Assistant Complete System Architecture

**Status**: Accepted
**Date**: 2025-09-02
**Author**: Julianus Kath
**Reviewers**: Technical Lead

## Context

The Dynamic ERP Assistant is a sophisticated natural language interface for ERP database systems that automatically discovers database schemas, converts natural language queries to SQL, and provides intelligent responses. This ADR documents the complete system architecture, component interactions, and design decisions.

## Decision

We have implemented a multi-layered architecture with the following key components:

### System Overview

```mermaid
graph TB
    subgraph "Mac Development Environment"
        subgraph "User Interface Layer"
            UI[Streamlit Web UI<br/>Port 3000]
            CLI[CLI Interface<br/>Optional]
        end
        
        subgraph "API Gateway Layer"
            LG[LangGraph Service<br/>FastAPI - Port 5001]
        end
        
        subgraph "Core Processing Layer"
            WF[DatabaseWorkflow<br/>LangGraph Orchestrator]
            AI[OpenAI GPT-4<br/>Language Model]
        end
        
        subgraph "Data Access Layer"
            ADAPTER[Database Adapter<br/>Proxy Integration]
            DB_CLIENT[Database Client<br/>Unified Interface]
            MCP[MCP Server<br/>Port 8000 - Optional]
        end
        
        subgraph "Local Development"
            PG[(PostgreSQL<br/>synthetic_erp_data<br/>Port 5432)]
        end
    end
    
    subgraph "Network Boundary"
        HTTPS[HTTPS/TLS<br/>Encrypted Communication]
    end
    
    subgraph "Windows Proxy Environment"
        PROXY[SQL Proxy Server<br/>Python Flask<br/>Port 5000]
        
        subgraph "Production ERP Databases"
            SQL1[(SQL Server<br/>ERP Database)]
            SQL2[(SQL Server<br/>Analytics DB)]
        end
    end
    
    UI --> LG
    CLI --> WF
    LG --> WF
    WF --> AI
    WF --> ADAPTER
    WF --> MCP
    ADAPTER --> DB_CLIENT
    MCP --> ADAPTER
    
    DB_CLIENT -->|DB_MODE=direct| PG
    DB_CLIENT -->|DB_MODE=proxy| HTTPS
    
    HTTPS --> PROXY
    PROXY --> SQL1
    PROXY --> SQL2
    
    style UI fill:#e1f5fe
    style LG fill:#f3e5f5
    style WF fill:#fff3e0
    style ADAPTER fill:#e8f5e8
    style DB_CLIENT fill:#e8f5e8
    style PROXY fill:#fff8e1
    style SQL1 fill:#fce4ec
    style SQL2 fill:#fce4ec
    style HTTPS fill:#ffebee
```

## System Architecture

### 1. Component Architecture

```mermaid
graph LR
    subgraph "Frontend Components"
        A[Streamlit App<br/>app.py]
        B[UI Components<br/>Chat Interface]
        C[State Management<br/>Session State]
    end
    
    subgraph "API Layer"
        D[FastAPI Service<br/>langgraph_service.py]
        E[CORS Middleware]
        F[Authentication]
    end
    
    subgraph "Core Workflow Engine"
        G[DatabaseWorkflow<br/>graph_definition.py]
        H[Schema Discovery<br/>Dynamic Schema Retrieval]
        I[Query Processing<br/>NL to SQL Conversion]
        J[Response Formatting<br/>User-Friendly Output]
    end
    
    subgraph "AI Integration"
        K[OpenAI Client<br/>GPT-4 Integration]
        L[Prompt Engineering<br/>Context Management]
        M[Response Processing<br/>Result Interpretation]
    end
    
    subgraph "Database Layer"
        N[Database Client<br/>Unified Interface]
        O[Database Adapter<br/>Compatibility Layer]
        P[Proxy Handler<br/>HTTPS Communication]
        Q[Direct Handler<br/>asyncpg Connection]
    end
    
    A --> D
    B --> A
    C --> A
    D --> G
    E --> D
    F --> D
    G --> H
    G --> I
    G --> J
    I --> K
    J --> K
    K --> L
    K --> M
    G --> O
    O --> N
    N --> P
    N --> Q
```

### 2. Class Diagram

```mermaid
classDiagram
    class StreamlitApp {
        +main()
        +render_chat_interface()
        +handle_user_input()
        +display_response()
        +manage_session_state()
    }
    
    class LangGraphService {
        -app: FastAPI
        -workflow: DatabaseWorkflow
        +startup_event()
        +health_check()
        +process_query(request: QueryRequest)
        +process_conversation(request: ConversationRequest)
    }
    
    class DatabaseWorkflow {
        -client: DatabaseClient
        -llm: ChatOpenAI
        -graph: StateGraph
        +__init__(model_name: str, temperature: float)
        +_build_workflow() StateGraph
        +process_query(user_input: str) str
        +process_conversation(messages: List) Dict
        -_get_schema() str
        -_analyze_intent(state: Dict) Dict
        -_execute_query(state: Dict) Dict
        -_format_response(state: Dict) Dict
        -_handle_clarification(state: Dict) Dict
    }
    
    class DatabaseClient {
        -mode: str
        -proxy_config: ProxyConfig
        -pg_config: PostgreSQLConfig
        +__init__(mode: str)
        +get_schema() str
        +execute_query(sql: str) List[Dict]
        +test_connection() bool
        -_execute_proxy_query(sql: str) List[Dict]
        -_execute_direct_query(sql: str) List[Dict]
    }
    
    class DatabaseAdapter {
        -client: DatabaseClient
        +get_available_tools() List[Tool]
        +call_tool(name: str, args: Dict) ToolResult
        -_handle_sql_differences(sql: str) str
        -_format_schema_info(schema: str) str
    }
    
    class ProxyDBClient {
        -client: DatabaseClient
        +get_schema() str
        +execute_query(sql: str) List[Dict]
        +fix_query_syntax(sql: str) str
        -_convert_limit_to_top(sql: str) str
    }
    
    class QueryRequest {
        +user_input: str
        +api_key: str
    }
    
    class QueryResponse {
        +final_response: str
        +status: str
    }
    
    class ConversationRequest {
        +messages: List[Dict]
        +api_key: str
    }
    
    class ConversationResponse {
        +final_response: str
        +operation: str
        +clarify: bool
        +messages: List[Dict]
        +status: str
    }
    
    StreamlitApp --> LangGraphService : HTTP Requests
    LangGraphService --> DatabaseWorkflow : Direct Calls
    DatabaseWorkflow --> DatabaseAdapter : MCP Integration
    DatabaseWorkflow --> ProxyDBClient : LangGraph Integration
    DatabaseAdapter --> DatabaseClient : Database Operations
    ProxyDBClient --> DatabaseClient : Database Operations
    DatabaseWorkflow --> ChatOpenAI : AI Processing
    LangGraphService ..> QueryRequest : Uses
    LangGraphService ..> QueryResponse : Returns
    LangGraphService ..> ConversationRequest : Uses
    LangGraphService ..> ConversationResponse : Returns
```

### 3. Sequence Diagrams

#### 3.1 Complete Query Processing Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Streamlit UI
    participant API as LangGraph Service
    participant WF as DatabaseWorkflow
    participant AI as OpenAI GPT-4
    participant DB as Database Client
    participant PROXY as Windows Proxy
    participant SQL as SQL Server
    participant PG as PostgreSQL DB
    
    U->>UI: Enter natural language query
    UI->>UI: Validate input
    UI->>API: POST /process_query
    Note over UI,API: Request: user_input + api_key
    
    API->>API: Validate API key
    API->>WF: process_query(user_input)
    
    WF->>DB: get_schema()
    
    alt DB_MODE=proxy
        DB->>PROXY: GET /schema (HTTPS)
        PROXY->>SQL: Query information_schema
        SQL-->>PROXY: Schema metadata
        PROXY-->>DB: JSON schema response
        DB->>DB: Convert SQL Server to PostgreSQL format
    else DB_MODE=direct
        DB->>PG: SELECT table_name, column_name...
        PG-->>DB: Schema metadata
    end
    
    DB-->>WF: Formatted schema string
    
    WF->>AI: Analyze intent + schema context
    Note over WF,AI: System prompt + user query + schema
    AI-->>WF: Intent: QUERY, SQL: SELECT COUNT(*)...
    
    WF->>DB: execute_query(sql)
    
    alt DB_MODE=proxy
        DB->>DB: Convert PostgreSQL to SQL Server syntax
        DB->>PROXY: POST /query (HTTPS)
        PROXY->>SQL: Execute SQL query
        SQL-->>PROXY: Query results
        PROXY-->>DB: JSON results
    else DB_MODE=direct
        DB->>PG: Execute SQL query
        PG-->>DB: Query results
    end
    
    DB-->>WF: Formatted results
    
    WF->>AI: Format response for user
    Note over WF,AI: Results + formatting instructions
    AI-->>WF: User-friendly response
    
    WF-->>API: final_response
    API-->>UI: QueryResponse JSON
    UI->>UI: Display response
    UI-->>U: Show formatted answer
```

#### 3.2 Schema Discovery Process

```mermaid
sequenceDiagram
    participant WF as DatabaseWorkflow
    participant DB as Database Client
    participant PG as PostgreSQL DB
    
    WF->>DB: get_schema()
    DB->>PG: Query information_schema.tables
    PG-->>DB: Table names
    
    loop For each table
        DB->>PG: Query information_schema.columns
        PG-->>DB: Column details (name, type, nullable)
        DB->>PG: Query table constraints
        PG-->>DB: Primary keys, foreign keys
    end
    
    DB->>DB: Format schema as structured text
    Note over DB: Creates human-readable schema description
    DB-->>WF: Complete schema string
```

#### 3.3 Error Handling and Clarification Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Streamlit UI
    participant WF as DatabaseWorkflow
    participant AI as OpenAI GPT-4
    participant DB as Database Client
    
    U->>UI: "Show me sales data"
    UI->>WF: process_query()
    
    WF->>DB: get_schema()
    DB-->>WF: Schema with sales table
    
    WF->>AI: Analyze ambiguous query
    AI-->>WF: Intent: CLARIFY
    Note over AI,WF: Query too vague, needs clarification
    
    WF->>AI: Generate clarification question
    AI-->>WF: Clarification question
    
    WF-->>UI: Clarification response
    UI-->>U: Display clarification question
    
    U->>UI: "Recent sales from last month"
    UI->>WF: process_query() with context
    
    WF->>AI: Analyze with clarification
    AI-->>WF: Intent: QUERY, SQL with date filter
    
    WF->>DB: execute_query()
    DB-->>WF: Results
    WF-->>UI: Final response
```

## Technical Implementation Details

### 4. Data Flow Architecture

```mermaid
graph TD
    A[User Input] --> B{Input Validation}
    B -->|Valid| C[API Authentication]
    B -->|Invalid| Z[Error Response]
    
    C -->|Authenticated| D[Schema Discovery]
    C -->|Unauthorized| Z
    
    D --> E[Intent Analysis]
    E --> F{Intent Type}
    
    F -->|QUERY| G[SQL Generation]
    F -->|CLARIFY| H[Clarification Generation]
    F -->|ERROR| I[Error Handling]
    
    G --> J[Query Validation]
    J -->|Valid SQL| K[Database Execution]
    J -->|Invalid SQL| L[SQL Correction]
    
    K --> M[Result Processing]
    L --> G
    
    H --> N[Clarification Response]
    I --> O[Error Response]
    M --> P[Response Formatting]
    
    P --> Q[Final Response]
    N --> Q
    O --> Q
    
    Q --> R[User Interface Update]
    
    style A fill:#e3f2fd
    style Q fill:#e8f5e8
    style Z fill:#ffebee
    style O fill:#ffebee
```

### 5. Database Schema Structure

```mermaid
erDiagram
    CUSTOMERS {
        int customer_id PK
        string name
        string email
        string phone
        string address
        timestamp created_at
        timestamp updated_at
    }
    
    PRODUCTS {
        int product_id PK
        string name
        text description
        string category
        decimal price
        int stock_quantity
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }
    
    EMPLOYEES {
        int employee_id PK
        string first_name
        string last_name
        string email
        string department
        string position
        decimal salary
        date hire_date
        timestamp created_at
        timestamp updated_at
    }
    
    SUPPLIERS {
        int supplier_id PK
        string name
        string contact_person
        string email
        string phone
        string address
        timestamp created_at
        timestamp updated_at
    }
    
    SALES {
        int sale_id PK
        int customer_id FK
        int employee_id FK
        timestamp sale_date
        decimal total_amount
        string status
        timestamp created_at
        timestamp updated_at
    }
    
    WAREHOUSE {
        int warehouse_id PK
        int product_id FK
        int supplier_id FK
        int quantity
        decimal unit_cost
        timestamp last_updated
        string location
        timestamp created_at
        timestamp updated_at
    }
    
    CUSTOMERS ||--o{ SALES : "places"
    EMPLOYEES ||--o{ SALES : "processes"
    PRODUCTS ||--o{ WAREHOUSE : "stored_in"
    SUPPLIERS ||--o{ WAREHOUSE : "supplies"
```

## Key Design Decisions

### 6. Architecture Decisions

#### 6.1 Hybrid Database Access Architecture
**Decision**: Support both direct database connection and proxy-based access  
**Rationale**: 
- Direct mode (asyncpg) for local development with synthetic data
- Proxy mode (HTTPS) for secure production ERP database access
- Environment-based switching via DB_MODE configuration
- Maintains security boundaries between development and production environments
- Enables adapter pattern for seamless integration

#### 6.2 LangGraph for Workflow Orchestration
**Decision**: Use LangGraph StateGraph for query processing workflow  
**Rationale**:
- Provides clear state management for complex query processing
- Enables easy addition of new processing steps
- Supports conditional routing (query vs clarification)
- Maintains conversation context effectively

#### 6.3 Dynamic Schema Discovery
**Decision**: Implement runtime schema discovery instead of static configuration  
**Rationale**:
- Adapts to any PostgreSQL database automatically
- Reduces configuration overhead
- Enables the system to work with evolving database schemas
- Provides accurate, up-to-date schema information to the AI

#### 6.4 OpenAI GPT-4 Integration
**Decision**: Use OpenAI GPT-4 for natural language processing  
**Rationale**:
- Superior natural language understanding capabilities
- Excellent SQL generation accuracy
- Strong reasoning abilities for clarification scenarios
- Reliable API with good performance

### 7. Component Responsibilities

```mermaid
graph TB
    subgraph "Presentation Layer"
        UI[Streamlit UI<br/>- User interaction<br/>- Input validation<br/>- Response display<br/>- Session management]
    end
    
    subgraph "API Layer"
        API[FastAPI Service<br/>- Request routing<br/>- Authentication<br/>- Error handling<br/>- Response formatting]
    end
    
    subgraph "Business Logic Layer"
        WF[DatabaseWorkflow<br/>- Query orchestration<br/>- Intent analysis<br/>- Context management<br/>- Response generation]
        
        SCHEMA[Schema Discovery<br/>- Database introspection<br/>- Metadata extraction<br/>- Schema formatting]
        
        QUERY[Query Processing<br/>- SQL generation<br/>- Query validation<br/>- Result processing]
        
        CLARIFY[Clarification Logic<br/>- Ambiguity detection<br/>- Question generation<br/>- Context preservation]
    end
    
    subgraph "Data Access Layer"
        DB[Database Client<br/>- Connection management<br/>- Query execution<br/>- Result formatting<br/>- Error handling]
    end
    
    subgraph "External Services"
        AI[OpenAI API<br/>- Language understanding<br/>- SQL generation<br/>- Response formatting]
        
        PG[PostgreSQL<br/>- Data storage<br/>- Query execution<br/>- Schema metadata]
    end
    
    UI --> API
    API --> WF
    WF --> SCHEMA
    WF --> QUERY
    WF --> CLARIFY
    WF --> AI
    SCHEMA --> DB
    QUERY --> DB
    DB --> PG
```

## Performance Considerations

### 8. System Performance Metrics

| Component | Response Time | Throughput | Resource Usage |
|-----------|---------------|------------|----------------|
| Streamlit UI | < 100ms | N/A | Low CPU, Moderate Memory |
| FastAPI Service | < 50ms | 100+ req/sec | Low CPU, Low Memory |
| DatabaseWorkflow | 2-5 seconds | 10-20 queries/min | Moderate CPU, Low Memory |
| OpenAI API | 1-3 seconds | Rate limited | Network dependent |
| Database Client | < 100ms | 1000+ queries/sec | Low CPU, Connection pool |
| PostgreSQL | < 50ms | 1000+ queries/sec | Variable based on query |

### 9. Scalability Architecture

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/HAProxy]
    end
    
    subgraph "Application Tier"
        UI1[Streamlit Instance 1]
        UI2[Streamlit Instance 2]
        API1[FastAPI Instance 1]
        API2[FastAPI Instance 2]
    end
    
    subgraph "Processing Tier"
        WF1[Workflow Engine 1]
        WF2[Workflow Engine 2]
        CACHE[Redis Cache<br/>Schema & Results]
    end
    
    subgraph "Data Tier"
        PG_MASTER[(PostgreSQL Master)]
        PG_REPLICA[(PostgreSQL Replica)]
    end
    
    subgraph "External Services"
        OPENAI[OpenAI API<br/>Rate Limited]
    end
    
    LB --> UI1
    LB --> UI2
    UI1 --> API1
    UI2 --> API2
    API1 --> WF1
    API2 --> WF2
    WF1 --> CACHE
    WF2 --> CACHE
    WF1 --> OPENAI
    WF2 --> OPENAI
    WF1 --> PG_MASTER
    WF2 --> PG_REPLICA
    PG_MASTER --> PG_REPLICA
```

## Security Architecture

### 10. Security Layers

```mermaid
graph TB
    subgraph "Network Security"
        FW[Firewall Rules]
        TLS[TLS/HTTPS Encryption]
    end
    
    subgraph "Application Security"
        AUTH[API Key Authentication]
        CORS[CORS Configuration]
        VALID[Input Validation]
    end
    
    subgraph "Database Security"
        CONN[Secure Connections]
        POOL[Connection Pooling]
        PARAM[Parameterized Queries]
    end
    
    subgraph "AI Security"
        PROMPT[Prompt Injection Protection]
        RATE[Rate Limiting]
        FILTER[Content Filtering]
    end
    
    FW --> AUTH
    TLS --> AUTH
    AUTH --> VALID
    CORS --> VALID
    VALID --> CONN
    CONN --> PARAM
    POOL --> PARAM
    PARAM --> PROMPT
    PROMPT --> RATE
    RATE --> FILTER
```

## Deployment Architecture

### 11. Container Deployment

```mermaid
graph TB
    subgraph "Docker Containers"
        subgraph "Web Tier"
            C1[streamlit-ui:latest<br/>Port 8501]
            C2[langgraph-api:latest<br/>Port 5001]
        end
        
        subgraph "Data Tier"
            C3[postgresql:14<br/>Port 5432]
            C4[redis:alpine<br/>Port 6379]
        end
    end
    
    subgraph "Docker Network"
        NET[erp-assistant-network]
    end
    
    subgraph "Volumes"
        V1[postgres-data]
        V2[redis-data]
        V3[app-logs]
    end
    
    C1 -.-> NET
    C2 -.-> NET
    C3 -.-> NET
    C4 -.-> NET
    
    C3 --> V1
    C4 --> V2
    C1 --> V3
    C2 --> V3
```

## Monitoring and Observability

### 12. Monitoring Stack

```mermaid
graph TB
    subgraph "Application Metrics"
        APP[Application Logs]
        PERF[Performance Metrics]
        ERROR[Error Tracking]
    end
    
    subgraph "Infrastructure Metrics"
        SYS[System Resources]
        NET[Network Metrics]
        DB[Database Metrics]
    end
    
    subgraph "Monitoring Tools"
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[AlertManager]
    end
    
    subgraph "Log Aggregation"
        ELK[ELK Stack]
        LOKI[Loki]
    end
    
    APP --> PROM
    PERF --> PROM
    ERROR --> PROM
    SYS --> PROM
    NET --> PROM
    DB --> PROM
    
    PROM --> GRAF
    PROM --> ALERT
    
    APP --> ELK
    ERROR --> ELK
    APP --> LOKI
```

## Future Enhancements

### 13. Roadmap Architecture

```mermaid
gantt
    title System Evolution Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1 (Current)
    Basic NL to SQL           :done, phase1, 2024-01-01, 2024-12-31
    Single database support   :done, phase1a, 2024-01-01, 2024-06-30
    Direct PostgreSQL connection :done, phase1b, 2024-07-01, 2024-09-30
    OpenAI GPT-4 integration  :done, phase1c, 2024-10-01, 2024-12-31
    
    section Phase 2 (Q1 2025)
    Multi-database support    :phase2, 2025-01-01, 2025-03-31
    MySQL, SQLite support     :phase2a, 2025-01-01, 2025-02-28
    Database abstraction layer :phase2b, 2025-02-01, 2025-03-31
    Connection management     :phase2c, 2025-03-01, 2025-03-31
    
    section Phase 3 (Q2 2025)
    Advanced Features         :phase3, 2025-04-01, 2025-06-30
    Query optimization        :phase3a, 2025-04-01, 2025-05-15
    Result caching           :phase3b, 2025-05-01, 2025-06-15
    User preferences         :phase3c, 2025-06-01, 2025-06-30
    
    section Phase 4 (Q3 2025)
    Enterprise Features       :phase4, 2025-07-01, 2025-09-30
    Multi-tenant support     :phase4a, 2025-07-01, 2025-08-15
    Advanced security        :phase4b, 2025-08-01, 2025-09-15
    Audit logging           :phase4c, 2025-09-01, 2025-09-30
    
    section Phase 5 (Q4 2025)
    AI Enhancements          :phase5, 2025-10-01, 2025-12-31
    Custom model fine-tuning :phase5a, 2025-10-01, 2025-11-15
    Advanced reasoning       :phase5b, 2025-11-01, 2025-12-15
    Predictive analytics     :phase5c, 2025-12-01, 2025-12-31
```

## Consequences

### Positive Outcomes
- **Modularity**: Clear separation of concerns enables independent development and testing
- **Scalability**: Architecture supports horizontal scaling of individual components
- **Maintainability**: Well-defined interfaces and responsibilities simplify maintenance
- **Flexibility**: Dynamic schema discovery adapts to different database structures
- **Performance**: Direct database connection eliminates unnecessary HTTP overhead
- **User Experience**: Natural language interface makes database querying accessible

### Trade-offs
- **Complexity**: Multi-component architecture requires careful orchestration
- **Dependencies**: Reliance on external OpenAI API introduces potential points of failure
- **Cost**: OpenAI API usage incurs ongoing operational costs
- **Latency**: AI processing introduces 2-5 second response times
- **Resource Usage**: Multiple services require adequate system resources

### Risk Mitigation
- **Service Monitoring**: Comprehensive health checks and monitoring
- **Error Handling**: Graceful degradation and user-friendly error messages
- **Caching**: Schema and result caching to reduce API calls
- **Fallback Mechanisms**: Alternative processing paths for service failures
- **Documentation**: Comprehensive documentation for maintenance and troubleshooting

## Conclusion

The Dynamic ERP Assistant architecture provides a robust, scalable, and maintainable solution for natural language database querying. The design emphasizes modularity, performance, and user experience while maintaining flexibility for future enhancements. The direct database connection approach, combined with LangGraph workflow orchestration and OpenAI integration, creates an effective system for democratizing database access through natural language interfaces.

---

**Document Version**: 1.0  
**Last Updated**: 2024-12-19  
**Next Review**: 2025-01-19
