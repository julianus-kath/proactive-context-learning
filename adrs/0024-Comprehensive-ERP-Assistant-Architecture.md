# ADR-0024: Comprehensive ERP Assistant Architecture
**Status**: Accepted
**Date**: 2025-11-06
**Author**: Julianus Kath


## Status
Accepted

## Context

The ERP Assistant has evolved into a sophisticated multi-agent system capable of handling complex business intelligence queries against ERP databases. This ADR documents the final comprehensive architecture after implementing all phases of the system.

### Evolution from Previous Architecture

The system progressed through 7 major phases:

1. **Phase 1**: MCP Server Truthful Discovery (accurate row counts, view dependencies)
2. **Phase 2**: Intent-Driven SQL Generation (router-based SQL generation, column probing)
3. **Phase 3**: SQL Validation & Repair (AST parsing, auto-repair, dialect validation)
4. **Phase 4**: Strategic Query Patterns (growth analysis, productivity, comparative)
5. **Phase 5**: Discovery Enhancement (multi-keyword search, dimension detection)
6. **Phase 6**: Clarification Loop (ambiguity detection, smart fallbacks)
7. **Phase 7**: Comprehensive Test Suite (automated validation)

## Decision

### Final Architecture: 7-Agent Orchestration System

The comprehensive ERP assistant uses 7 specialized agents orchestrated through LangGraph:

#### Core Agents

1. **IntentParserAgent**: Advanced semantic parsing with clarification detection
2. **DiscoveryAgent**: Strategic multi-keyword table discovery with business domain awareness
3. **JoinPlanAndSQLAgent**: Intent-driven SQL generation with 6 specialized generators
4. **SQLValidatorAgent**: Pre-execution validation and auto-repair
5. **ExecAndRecoveryAgent**: Safe execution with error recovery
6. **AnswerAgent**: Contextual response formatting with source attribution
7. **InterpretationAgent**: Follow-up query handling without re-execution

## Architecture Diagrams

### System Overview

```mermaid
graph TB
    subgraph "User Interface"
        UI[User Query Input]
    end

    subgraph "LangGraph Orchestration Layer"
        ORCH[QueryOrchestrator]

        subgraph "Agent Pipeline"
            IP[IntentParserAgent<br/>Semantic Analysis +<br/>Action Classification]

            DA[DiscoveryAgent<br/>Strategic Table Discovery<br/>+ Business Domain Awareness]

            JS[JoinPlanAndSQLAgent<br/>Intent-Driven SQL Generation<br/>6 Specialized Generators]

            SV[SQLValidatorAgent<br/>AST Validation +<br/>Auto-Repair Loop]

            ER[ExecAndRecoveryAgent<br/>Safe Execution +<br/>Error Recovery]

            AA[AnswerAgent<br/>Contextual Response<br/>Formatting]
        end

        subgraph "Specialized Paths"
            IA[InterpretationAgent<br/>Follow-up Query<br/>Processing]
        end
    end

    subgraph "MCP Server Layer (Windows)"
        MCP[MCP Server]

        subgraph "Database Components"
            SM[Scout Mode<br/>Semantic Catalog<br/>Builder]

            DT[Discovery Tools<br/>Table/View Search<br/>Column Indexing]

            QT[Query Tools<br/>Bounded Execution<br/>Row Limiting]
        end
    end

    subgraph "Database Layer"
        DB[(MSSQL ERP Database<br/>Complex Schema<br/>German Table Names)]
    end

    UI --> ORCH
    ORCH --> IP
    IP --> DA
    DA --> JS
    JS --> SV
    SV --> ER
    ER --> AA

    ORCH -.-> IA

    AA --> UI
    IA --> UI

    ORCH <--> MCP
    MCP --> SM
    MCP --> DT
    MCP --> QT

    DT --> DB
    QT --> DB
    SM --> DB

    style ORCH fill:#e1f5fe
    style IP fill:#f3e5f5
    style DA fill:#e8f5e8
    style JS fill:#fff3e0
    style SV fill:#fce4ec
    style ER fill:#f3e5f5
    style AA fill:#e8f5e8
    style IA fill:#e0f2f1
```

### Detailed Agent Interactions

```mermaid
graph TD
    A[User Query] --> B[IntentParserAgent]

    B --> C{Query Type}
    C -->|Data Query| D[DiscoveryAgent]
    C -->|Follow-up| E[InterpretationAgent]
    C -->|Health Check| F[Health Response]
    C -->|Schema Query| G[Schema Discovery]

    D --> H[Table Candidates<br/>+ Column Metadata]

    H --> I[JoinPlanAndSQLAgent]

    I --> J{Intent Action}
    J -->|count| K[Count SQL Generator]
    J -->|topk_sum_by_customer| L[Revenue Aggregation<br/>with JOIN]
    J -->|trend_series| M[Time Series SQL<br/>with GROUP BY]
    J -->|growth_analysis| N[Growth Analysis<br/>with LAG]
    J -->|comparative_analysis| O[Comparative SQL<br/>with Window Functions]
    J -->|month_count| P[Month-filtered Count]

    K --> Q[Generated SQL]
    L --> Q
    M --> Q
    N --> Q
    O --> Q
    P --> Q

    Q --> R[SQLValidatorAgent]

    R --> S{Validation Result}
    S -->|Valid| T[ExecAndRecoveryAgent]
    S -->|Invalid| U[Auto-Repair Loop<br/>Up to 2 attempts]

    U --> S

    T --> V[Safe Query Execution<br/>Row Limits + Timeouts]

    V --> W{Execution Result}
    W -->|Success| X[AnswerAgent]
    W -->|Failure| Y[Recovery Strategies<br/>LLM Repair + Fallbacks]

    Y --> V

    X --> Z[Contextual Response<br/>with Sources + Preview]

    E --> AA[Interpret Previous Results<br/>No DB Re-query]

    F --> Z
    G --> Z
    AA --> Z

    Z --> AB[Final Response to User]

    style B fill:#e3f2fd
    style D fill:#f3e5f5
    style I fill:#fff3e0
    style R fill:#fce4ec
    style T fill:#e8f5e8
    style X fill:#e0f2f1
    style E fill:#fff9c4
```

### Process Flow Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant IP as IntentParserAgent
    participant DA as DiscoveryAgent
    participant JS as JoinPlanAndSQLAgent
    participant SV as SQLValidatorAgent
    participant ER as ExecAndRecoveryAgent
    participant AA as AnswerAgent
    participant MCP as MCP Server
    participant DB as MSSQL Database

    U->>IP: "How many customers do we have?"
    IP->>IP: Parse intent + classify action
    IP-->>U: Intent: {action: "count", entities: ["customers"]}

    IP->>DA: Route to discovery
    DA->>MCP: Strategic table search for "customers"
    MCP->>DB: Query catalog for customer tables
    DB-->>MCP: Table candidates + metadata
    MCP-->>DA: Ranked table list

    DA->>JS: Pass intent + table candidates
    JS->>JS: Route to count SQL generator
    JS->>JS: Generate: SELECT COUNT(*) FROM KHKAdressen

    JS->>SV: Validate generated SQL
    SV->>SV: AST parsing + MSSQL dialect check
    SV-->>JS: Validation result

    JS->>ER: Execute validated SQL
    ER->>MCP: Bounded query execution
    MCP->>DB: Execute SELECT COUNT(*) FROM KHKAdressen
    DB-->>MCP: Result: 419 customers
    MCP-->>ER: Safe execution result

    ER->>AA: Format response with context
    AA->>AA: Generate natural language response
    AA-->>U: "You have 419 customers in your system. Source: KHKAdressen table"
```

### Strategic Query Processing Flow

```mermaid
flowchart TD
    A[Complex Query] --> B{Intent Classification}
    B --> C[Simple Count<br/>→ Direct SQL]
    B --> D[Revenue Aggregation<br/>→ JOIN Planning]
    B --> E[Time Series<br/>→ Trend Analysis]
    B --> F[Growth Analysis<br/>→ Year-over-Year]
    B --> G[Productivity<br/>→ Department Metrics]
    B --> H[Comparative<br/>→ Quarter Comparison]

    C --> I[Standard Discovery]
    D --> J[Strategic Discovery<br/>Multi-Keyword Search]
    E --> J
    F --> J
    G --> J
    H --> J

    J --> K[Business Domain<br/>Awareness]
    K --> L[Sales Tables for Revenue]
    K --> M[Customer Tables for Growth]
    K --> N[Employee Tables for Productivity]

    I --> O[Table Selection]
    L --> O
    M --> O
    N --> O

    O --> P[Intent-Driven<br/>SQL Generation]
    P --> Q[Column Probing<br/>Required]
    Q --> R[Specialized SQL<br/>Templates]
    R --> S[Validation & Repair]
    S --> T[Safe Execution]
    T --> U[Contextual<br/>Response]

    style B fill:#e3f2fd
    style J fill:#fff3e0
    style K fill:#f3e5f5
    style P fill:#fce4ec
    style R fill:#e8f5e8
    style U fill:#e0f2f1
```

## Technical Implementation Details

### Agent Responsibilities

#### IntentParserAgent
- **Input**: Raw user query string
- **Processing**: LLM-based semantic analysis, entity extraction, action classification
- **Output**: Structured intent with `required_action`, entities, metrics, confidence
- **Special Features**: Clarification detection, multi-keyword generation, ambiguity resolution

#### DiscoveryAgent
- **Input**: Intent with keywords_for_discovery, required_action
- **Processing**: Strategic search based on query type, business domain awareness
- **Output**: Ranked table/view candidates with column metadata
- **Special Features**: Multi-keyword search, junk table filtering, dimension detection

#### JoinPlanAndSQLAgent
- **Input**: Intent, table candidates, column metadata
- **Processing**: Route to specialized SQL generators based on required_action
- **Output**: Validated MSSQL query + join plan
- **Special Features**: 6 specialized generators, column probing, FK-based joins

#### SQLValidatorAgent
- **Input**: Generated SQL query
- **Processing**: AST parsing, MSSQL dialect validation, table/column existence checks
- **Output**: Validation result with repair suggestions
- **Special Features**: Auto-repair loop (2 attempts), comprehensive error reporting

#### ExecAndRecoveryAgent
- **Input**: Validated SQL query
- **Processing**: Safe execution with row limits, timeouts, error recovery
- **Output**: Query results or recovery attempts
- **Special Features**: LLM-based repair, fallback strategies, performance monitoring

#### AnswerAgent
- **Input**: Execution results, source metadata
- **Processing**: Contextual response formatting with explanations
- **Output**: Natural language response with source attribution
- **Special Features**: Source table inclusion, row previews, error explanations

#### InterpretationAgent
- **Input**: Follow-up query + previous execution results
- **Processing**: Interpret stored results without re-querying database
- **Output**: Contextual answers from cached data
- **Special Features**: Session persistence, follow-up handling

### Key Innovations

1. **Intent-Driven Architecture**: Each agent specializes in one phase with clear contracts
2. **Strategic Discovery**: Multi-keyword search with business domain awareness
3. **Specialized SQL Generators**: 6 different generators for different query patterns
4. **Validation & Repair Loop**: Pre-execution validation with automatic fixing
5. **Contextual Responses**: Always include sources and explanations
6. **Clarification System**: Detect and handle ambiguous queries intelligently

## Consequences

### Positive Outcomes

- **Comprehensive Query Support**: Handles 15+ query patterns from simple counts to complex BI
- **Robust Error Handling**: Multiple recovery strategies and meaningful error messages
- **Scalable Architecture**: Each agent can be improved independently
- **Business Intelligence Ready**: Supports strategic analysis queries
- **Production Ready**: Comprehensive validation, monitoring, and error recovery

### Implementation Status

- ✅ **Phase 1**: MCP Server Truthful Discovery
- ✅ **Phase 2**: Intent-Driven SQL Generation
- ✅ **Phase 3**: SQL Validation & Repair
- ✅ **Phase 4**: Strategic Query Patterns
- ✅ **Phase 5**: Discovery Enhancement
- ✅ **Phase 6**: Clarification Loop
- ✅ **Phase 7**: Comprehensive Test Suite

### Testing Results

The system successfully handles:
- Basic counts: "How many customers do we have?"
- Revenue analysis: "Top 5 customers by revenue"
- Time-based queries: "Projects in October", "Growth over 3 years"
- Strategic analysis: Customer growth, department productivity, comparative analysis
- Follow-up queries: Interpretation without re-execution
- Ambiguous queries: Clarification requests

### Future Extensions

The architecture supports easy addition of:
- New query patterns (additional SQL generators)
- Enhanced business domain knowledge
- Advanced analytics (predictions, correlations)
- Multi-database support
- Custom clarification strategies

This comprehensive architecture provides a robust foundation for enterprise-grade ERP query assistance with room for continuous improvement and expansion.
