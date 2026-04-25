# ADR-0011: ERP Proxy Integration Architecture

**Status**: Accepted  
**Date**: 2025-10-06
**Author**: System Architecture Team  
**Reviewers**: Technical Lead  

## Context

The Dynamic ERP Assistant system has been enhanced to support secure access to production ERP databases through a Windows-hosted proxy server. This architecture enables the Mac-based agent to securely query SQL Server databases over VPN without storing production credentials locally.

## Decision

We have implemented a proxy-based architecture that maintains security boundaries while enabling seamless database access through adapter layers.

### System Overview with Proxy Integration

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
            DB_CLIENT[Database Client<br/>Proxy Mode]
            MCP_ADAPTER[MCP Server Adapter<br/>Compatibility Layer]
            MCP[MCP Server<br/>Port 8000]
        end
        
        subgraph "Local Development"
            PG[(PostgreSQL<br/>synthetic_erp_data<br/>Port 5432)]
        end
    end
    
    subgraph "Network Boundary"
        HTTPS[HTTPS/TLS<br/>Encrypted Communication]
    end
    
    subgraph "Windows Proxy Environment"
        subgraph "Proxy Server"
            PROXY[SQL Proxy Server<br/>Python Flask<br/>Port 5000]
            AUTH[API Key Authentication]
            RATE[Rate Limiting]
        end
        
        subgraph "VPN Connection"
            VPN[Corporate VPN<br/>Secure Tunnel]
        end
        
        subgraph "Production ERP Databases"
            SQL1[(SQL Server 1<br/>ERP Database)]
            SQL2[(SQL Server 2<br/>Analytics DB)]
            SQL3[(SQL Server 3<br/>Archive DB)]
        end
    end
    
    UI --> LG
    CLI --> WF
    LG --> WF
    WF --> AI
    WF --> ADAPTER
    WF --> MCP
    ADAPTER --> DB_CLIENT
    MCP --> MCP_ADAPTER
    MCP_ADAPTER --> DB_CLIENT
    
    DB_CLIENT -->|DB_MODE=direct| PG
    DB_CLIENT -->|DB_MODE=proxy| HTTPS
    
    HTTPS --> AUTH
    AUTH --> RATE
    RATE --> PROXY
    PROXY --> VPN
    VPN --> SQL1
    VPN --> SQL2
    VPN --> SQL3
    
    style UI fill:#e1f5fe
    style LG fill:#f3e5f5
    style WF fill:#fff3e0
    style ADAPTER fill:#e8f5e8
    style DB_CLIENT fill:#e8f5e8
    style PROXY fill:#fff8e1
    style SQL1 fill:#fce4ec
    style SQL2 fill:#fce4ec
    style SQL3 fill:#fce4ec
    style HTTPS fill:#ffebee
```

## Proxy Communication Architecture

### 1. Network Communication Flow

```mermaid
sequenceDiagram
    participant Agent as Mac Agent
    participant Client as Database Client
    participant HTTPS as HTTPS Layer
    participant Proxy as Windows Proxy
    participant VPN as Corporate VPN
    participant SQL as SQL Server

    Agent->>Client: execute_query(sql)
    Note over Agent,Client: DB_MODE=proxy
    
    Client->>Client: Validate SQL query
    Client->>Client: Apply row limits & timeouts
    
    Client->>HTTPS: POST /query
    Note over Client,HTTPS: API Key + TLS encryption
    
    HTTPS->>Proxy: Encrypted request
    Proxy->>Proxy: Authenticate API key
    Proxy->>Proxy: Validate query safety
    Proxy->>Proxy: Apply rate limiting
    
    Proxy->>VPN: Database connection
    VPN->>SQL: Execute SQL query
    SQL-->>VPN: Query results
    VPN-->>Proxy: Encrypted results
    
    Proxy->>Proxy: Format JSON response
    Proxy-->>HTTPS: JSON response
    HTTPS-->>Client: Decrypted results
    Client-->>Agent: Formatted data
```

### 2. Adapter Layer Architecture

```mermaid
graph TB
    subgraph "LangGraph Integration"
        LG_WORKFLOW[DatabaseWorkflow]
        LG_CLIENT[Proxy DB Client]
    end
    
    subgraph "MCP Server Integration"
        MCP_SERVER[MCP Server]
        MCP_ADAPTER[Database Adapter]
    end
    
    subgraph "Core Database Layer"
        DB_CLIENT[Database Client<br/>Unified Interface]
        PROXY_MODE[Proxy Mode Handler]
        DIRECT_MODE[Direct Mode Handler]
    end
    
    subgraph "Database Backends"
        PROXY_API[Windows Proxy<br/>SQL Server Access]
        LOCAL_PG[Local PostgreSQL<br/>Development Data]
    end
    
    LG_WORKFLOW --> LG_CLIENT
    LG_CLIENT --> DB_CLIENT
    
    MCP_SERVER --> MCP_ADAPTER
    MCP_ADAPTER --> DB_CLIENT
    
    DB_CLIENT --> PROXY_MODE
    DB_CLIENT --> DIRECT_MODE
    
    PROXY_MODE -->|HTTPS/TLS| PROXY_API
    DIRECT_MODE -->|asyncpg| LOCAL_PG
    
    style LG_CLIENT fill:#e3f2fd
    style MCP_ADAPTER fill:#e8f5e8
    style DB_CLIENT fill:#fff3e0
    style PROXY_API fill:#fff8e1
    style LOCAL_PG fill:#f3e5f5
```

### 3. Database Client Abstraction

```mermaid
classDiagram
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
        -_format_results(results: Any) List[Dict]
    }
    
    class ProxyConfig {
        +base_url: str
        +api_key: str
        +timeout: int
        +verify_ssl: bool
        +cert_path: Optional[str]
    }
    
    class PostgreSQLConfig {
        +host: str
        +port: int
        +database: str
        +user: str
        +password: str
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
        -_handle_schema_qualification(sql: str) str
    }
    
    DatabaseClient --> ProxyConfig : uses
    DatabaseClient --> PostgreSQLConfig : uses
    DatabaseAdapter --> DatabaseClient : wraps
    ProxyDBClient --> DatabaseClient : wraps
```

## Security Architecture

### 4. Multi-Layer Security Model

```mermaid
graph TB
    subgraph "Mac Agent Security"
        ENV[Environment Variables<br/>No hardcoded secrets]
        API_KEY[API Key Authentication]
        TLS_CLIENT[TLS Client Certificates]
    end
    
    subgraph "Network Security"
        HTTPS[HTTPS/TLS 1.3<br/>End-to-end encryption]
        CERT[Certificate Validation]
        FIREWALL[Network Firewall Rules]
    end
    
    subgraph "Proxy Security"
        AUTH[API Key Validation]
        RATE_LIMIT[Rate Limiting<br/>Request throttling]
        SQL_VALIDATION[SQL Query Validation<br/>Read-only enforcement]
        TIMEOUT[Query Timeouts<br/>Resource protection]
    end
    
    subgraph "Database Security"
        VPN_TUNNEL[VPN Encrypted Tunnel]
        DB_AUTH[Database Authentication]
        READ_ONLY[Read-only Database User]
        AUDIT[Query Audit Logging]
    end
    
    ENV --> API_KEY
    API_KEY --> TLS_CLIENT
    TLS_CLIENT --> HTTPS
    HTTPS --> CERT
    CERT --> FIREWALL
    FIREWALL --> AUTH
    AUTH --> RATE_LIMIT
    RATE_LIMIT --> SQL_VALIDATION
    SQL_VALIDATION --> TIMEOUT
    TIMEOUT --> VPN_TUNNEL
    VPN_TUNNEL --> DB_AUTH
    DB_AUTH --> READ_ONLY
    READ_ONLY --> AUDIT
    
    style ENV fill:#e8f5e8
    style HTTPS fill:#ffebee
    style AUTH fill:#fff3e0
    style VPN_TUNNEL fill:#e3f2fd
```

### 5. Configuration Management

```mermaid
graph LR
    subgraph "Mac Agent Configuration"
        ENV_FILE[.env File<br/>Local settings]
        CONFIG[config.yaml<br/>Application config]
    end
    
    subgraph "Environment Variables"
        DB_MODE[DB_MODE=proxy/direct]
        PROXY_URL[PROXY_BASE_URL]
        API_KEY_VAR[PROXY_API_KEY]
        CERT_PATH[PROXY_CERT_PATH]
    end
    
    subgraph "Proxy Configuration"
        PROXY_ENV[proxy.env<br/>Windows environment]
        DB_CONFIGS[database_configs.yaml<br/>Connection strings]
        CERTS[SSL Certificates<br/>TLS configuration]
    end
    
    ENV_FILE --> DB_MODE
    CONFIG --> PROXY_URL
    ENV_FILE --> API_KEY_VAR
    CONFIG --> CERT_PATH
    
    DB_MODE --> PROXY_ENV
    PROXY_URL --> DB_CONFIGS
    API_KEY_VAR --> CERTS
    
    style ENV_FILE fill:#e8f5e8
    style PROXY_ENV fill:#fff8e1
    style CERTS fill:#ffebee
```

## Implementation Details

### 6. Query Processing with Proxy Integration

```mermaid
sequenceDiagram
    participant User as User
    participant UI as Streamlit UI
    participant Workflow as DatabaseWorkflow
    participant Adapter as Database Adapter
    participant Client as Database Client
    participant Proxy as Windows Proxy
    participant SQL as SQL Server

    User->>UI: "Show me recent sales"
    UI->>Workflow: process_query()
    
    Workflow->>Adapter: get_schema()
    Adapter->>Client: get_schema()
    
    alt DB_MODE=proxy
        Client->>Proxy: GET /schema
        Proxy->>SQL: Query information_schema
        SQL-->>Proxy: Schema metadata
        Proxy-->>Client: JSON schema
        Client->>Client: Convert SQL Server to PostgreSQL format
    else DB_MODE=direct
        Client->>Client: Query local PostgreSQL
    end
    
    Client-->>Adapter: Formatted schema
    Adapter-->>Workflow: Schema string
    
    Workflow->>Workflow: Generate SQL with AI
    Workflow->>Adapter: execute_query(sql)
    Adapter->>Adapter: Convert PostgreSQL to SQL Server syntax
    Adapter->>Client: execute_query(converted_sql)
    
    alt DB_MODE=proxy
        Client->>Proxy: POST /query
        Proxy->>SQL: Execute query
        SQL-->>Proxy: Results
        Proxy-->>Client: JSON results
    else DB_MODE=direct
        Client->>Client: Execute on PostgreSQL
    end
    
    Client-->>Adapter: Query results
    Adapter-->>Workflow: Formatted results
    Workflow-->>UI: Final response
    UI-->>User: Display answer
```

### 7. Error Handling and Fallback

```mermaid
graph TD
    A[Query Request] --> B{DB_MODE Check}
    
    B -->|proxy| C[Proxy Connection Test]
    B -->|direct| D[Direct PostgreSQL]
    
    C --> E{Proxy Available?}
    E -->|Yes| F[Execute via Proxy]
    E -->|No| G[Log Error]
    
    F --> H{Query Success?}
    H -->|Yes| I[Return Results]
    H -->|No| J[Handle SQL Server Error]
    
    J --> K{Syntax Error?}
    K -->|Yes| L[Auto-fix Query]
    K -->|No| M[Return Error]
    
    L --> N[Retry Query]
    N --> H
    
    G --> O[Fallback to Direct Mode?]
    O -->|Yes| D
    O -->|No| P[Return Connection Error]
    
    D --> Q[Execute on PostgreSQL]
    Q --> I
    
    style C fill:#fff3e0
    style F fill:#e8f5e8
    style G fill:#ffebee
    style L fill:#e3f2fd
```

## Deployment Architecture

### 8. Multi-Environment Deployment

```mermaid
graph TB
    subgraph "Development Environment"
        DEV_AGENT[Mac Agent<br/>DB_MODE=direct]
        DEV_PG[(Local PostgreSQL<br/>Synthetic Data)]
    end
    
    subgraph "Testing Environment"
        TEST_AGENT[Mac Agent<br/>DB_MODE=proxy]
        TEST_PROXY[Windows Proxy<br/>Test Environment]
        TEST_SQL[(Test SQL Server<br/>Sanitized Data)]
    end
    
    subgraph "Production Environment"
        PROD_AGENT[Mac Agent<br/>DB_MODE=proxy]
        PROD_PROXY[Windows Proxy<br/>Production VPN]
        PROD_SQL[(Production SQL Server<br/>Live ERP Data)]
    end
    
    DEV_AGENT --> DEV_PG
    TEST_AGENT --> TEST_PROXY
    TEST_PROXY --> TEST_SQL
    PROD_AGENT --> PROD_PROXY
    PROD_PROXY --> PROD_SQL
    
    style DEV_AGENT fill:#e8f5e8
    style TEST_AGENT fill:#fff3e0
    style PROD_AGENT fill:#ffebee
```

## Key Design Decisions

### 9. Architecture Decisions

#### 9.1 Proxy-Only Database Access
**Decision**: Use Windows proxy for all production database access  
**Rationale**: 
- Maintains security boundaries between development and production
- Eliminates need for VPN client on Mac development machine
- Centralizes database access control and monitoring
- Enables secure credential management on Windows environment

#### 9.2 Adapter Pattern for Integration
**Decision**: Implement adapter layers for existing components  
**Rationale**:
- Maintains backward compatibility with existing codebase
- Enables gradual migration from direct to proxy access
- Provides clean abstraction between database modes
- Supports both PostgreSQL and SQL Server syntax differences

#### 9.3 Environment-Based Mode Switching
**Decision**: Use DB_MODE environment variable for mode selection  
**Rationale**:
- Enables easy switching between development and production
- Supports testing with both local and remote databases
- Provides clear configuration management
- Allows for fallback scenarios during development

#### 9.4 SQL Syntax Translation
**Decision**: Implement automatic SQL syntax conversion  
**Rationale**:
- Handles differences between PostgreSQL and SQL Server
- Enables seamless operation across database types
- Reduces complexity in AI prompt engineering
- Provides consistent interface for application logic

## Performance Considerations

### 10. System Performance with Proxy

| Component | Direct Mode | Proxy Mode | Impact |
|-----------|-------------|------------|---------|
| Schema Discovery | < 100ms | 200-500ms | Network latency |
| Query Execution | < 50ms | 100-300ms | HTTPS overhead |
| Connection Setup | < 10ms | 50-100ms | TLS handshake |
| Error Recovery | Immediate | 200-400ms | Network retry |
| Throughput | 1000+ qps | 100-200 qps | Rate limiting |

### 11. Monitoring and Observability

```mermaid
graph TB
    subgraph "Mac Agent Monitoring"
        AGENT_LOGS[Application Logs]
        AGENT_METRICS[Performance Metrics]
        AGENT_HEALTH[Health Checks]
    end
    
    subgraph "Network Monitoring"
        TLS_METRICS[TLS Connection Metrics]
        LATENCY[Network Latency]
        ERRORS[Connection Errors]
    end
    
    subgraph "Proxy Monitoring"
        PROXY_LOGS[Request/Response Logs]
        RATE_METRICS[Rate Limiting Metrics]
        AUTH_LOGS[Authentication Logs]
    end
    
    subgraph "Database Monitoring"
        QUERY_LOGS[SQL Query Logs]
        PERF_METRICS[Database Performance]
        AUDIT_TRAIL[Security Audit Trail]
    end
    
    AGENT_LOGS --> TLS_METRICS
    AGENT_METRICS --> LATENCY
    AGENT_HEALTH --> ERRORS
    
    TLS_METRICS --> PROXY_LOGS
    LATENCY --> RATE_METRICS
    ERRORS --> AUTH_LOGS
    
    PROXY_LOGS --> QUERY_LOGS
    RATE_METRICS --> PERF_METRICS
    AUTH_LOGS --> AUDIT_TRAIL
    
    style AGENT_LOGS fill:#e8f5e8
    style PROXY_LOGS fill:#fff3e0
    style QUERY_LOGS fill:#e3f2fd
```

## Consequences

### Positive
- **Security**: Production credentials never leave Windows environment
- **Flexibility**: Easy switching between development and production modes
- **Compatibility**: Maintains existing codebase with minimal changes
- **Monitoring**: Centralized logging and audit trail for database access
- **Scalability**: Proxy can serve multiple agent instances

### Negative
- **Latency**: Additional network hop increases response times
- **Complexity**: Additional layer increases system complexity
- **Dependency**: Agent depends on proxy availability for production access
- **Maintenance**: Requires maintaining both direct and proxy code paths

### Risks
- **Single Point of Failure**: Proxy server becomes critical dependency
- **Network Issues**: VPN or network problems affect system availability
- **Certificate Management**: TLS certificate renewal and management overhead

## Future Considerations

1. **Load Balancing**: Multiple proxy instances for high availability
2. **Caching**: Implement schema and query result caching
3. **Connection Pooling**: Optimize database connections on proxy side
4. **Monitoring Integration**: Enhanced observability and alerting
5. **Multi-Region**: Support for multiple geographic deployments

---

**Related ADRs**: ADR-0010 (System Architecture), ADR-0006 (Data Integration)  
**Implementation Status**: Complete  
**Next Review**: 2025-01-19