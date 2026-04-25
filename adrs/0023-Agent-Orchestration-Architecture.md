# ADR-0023: Agent Orchestration Architecture for Proactive Context Learning
**Status**: Accepted
**Date**: 2025-11-03
**Author**: Julianus Kath


## Status
Accepted — **Superseded by [ADR-0030](0030-simple-sql-agent-architecture.md)** (the five-agent orchestration described here was retired for a single ReAct agent with four tools; see [`README.md`](README.md)).

## Context

The Proactive Context Learning system is a multi-agent AI assistant designed to answer business intelligence queries against complex ERP databases. The system was originally built with a sophisticated multi-agent architecture using LangGraph orchestration, but was failing to provide meaningful responses to user queries.

### Original System Architecture

The system consisted of five specialized agents orchestrated through LangGraph:

1. **IntentParserAgent**: Semantic analysis of natural language queries to extract structured intent (operation, entities, metrics, filters, keywords_for_discovery, confidence)

2. **DiscoveryAgent**: Table/view discovery using Scout mode catalog with semantic search and ranking

3. **JoinPlanAndSQLAgent**: Complex SQL generation with join planning, FK relationship analysis, and MSSQL query validation

4. **ExecAndRecoveryAgent**: Safe query execution with row limits, timeouts, and error recovery via LLM repair

5. **AnswerAgent**: Natural language response formatting with contextual explanations

### Key Components

- **Scout Mode**: Windows-based MCP server that catalogs the entire database schema on startup
- **LangGraph Orchestration**: Conditional routing based on query intent and operation type
- **MCP Protocol**: JSON-RPC communication between LangGraph (macOS) and MCP server (Windows)
- **German ERP Database**: Complex schema with German table names and business logic

## Problem Statement

The original system suffered from critical failures:

1. **Stuck in Discovery Phase**: Agent only called `search_tables` on MCP server, never progressed to SQL generation or execution
2. **Generic Error Responses**: All queries returned "It looks like there's missing information in your query"
3. **Poor Table Discovery**: Only found `KHKArtikelKunden` (customer table) for all query types
4. **Failed SQL Generation**: Complex subgraph approach was throwing exceptions and not producing valid SQL
5. **No Contextual Responses**: Answer agent provided meaningless generic errors instead of explaining what data was found

## Decision

### Core Decision: Simplify and Stabilize Agent Orchestration

**Chosen Approach**: Implement a simplified but robust agent orchestration that:

1. **Maintains Multi-Agent Architecture**: Keep the five-agent structure but simplify interactions
2. **Direct SQL Generation**: Replace complex subgraph SQL generation with direct, intent-aware SQL generation
3. **Intelligent Table Selection**: Use query intent to select most appropriate tables from discovery results
4. **Contextual Error Handling**: Provide meaningful responses explaining what data was found vs. requested
5. **Scout Mode Integration**: Leverage the Scout catalog for comprehensive table discovery

### Alternative Approaches Considered

#### Option 1: Full Subgraph Preservation (Rejected)
- **Pros**: Maintains original sophisticated architecture
- **Cons**: Complex subgraph was throwing unhandled exceptions, making the entire system unusable
- **Rationale**: System was completely broken; couldn't justify preserving non-functional complexity

#### Option 2: Single-Agent Approach (Rejected)
- **Pros**: Simpler, more reliable
- **Cons**: Loses the benefits of specialized agents and Scout mode integration
- **Rationale**: The multi-agent approach with Scout mode was a core architectural decision

#### Option 3: External SQL Generation Service (Rejected)
- **Pros**: Offloads complexity
- **Cons**: Increases system dependencies and latency
- **Rationale**: Would undermine the LangGraph orchestration design

## Solution Architecture

### Current Agent Flow

```
User Query
    ↓
IntentParserAgent (LLM-based semantic parsing)
    ↓
DiscoveryAgent (Scout catalog + intelligent fallback)
    ↓
Table Selection (Intent-aware best table choice)
    ↓
Direct SQL Generation (Intent → SQL mapping)
    ↓
ExecAndRecoveryAgent (Safe execution with recovery)
    ↓
AnswerAgent (Contextual response formatting)
    ↓
Final Response
```

### Key Architectural Components

#### 1. IntentParserAgent
- **Input**: Natural language query
- **Output**: Structured ParsedIntent with confidence scoring
- **Implementation**: GPT-4o with custom prompts for ERP/business terminology
- **Unchanged**: Core functionality working well

#### 2. DiscoveryAgent (Enhanced)
- **Input**: keywords_for_discovery from intent
- **Output**: Ranked list of relevant tables
- **New Features**:
  - Intelligent fallback discovery for business-relevant tables
  - German ERP terminology support ("beleg", "artikel", "kunde")
  - Table scoring based on data volume, relationships, and query relevance
- **Scout Integration**: Uses MCP server's search_tables tool with Scout catalog

#### 3. Table Selection Logic (New)
- **Location**: orchestrator.py `_select_best_table_for_query()`
- **Logic**: Scores tables based on:
  - Semantic match with query entities
  - Business type appropriateness (sales → transaction tables, customers → customer tables)
  - Data availability and table connectivity
- **Fallback**: Uses best available table if no perfect match

#### 4. Direct SQL Generation (Simplified)
- **Location**: orchestrator.py JOIN_SQL node
- **Logic**:
  ```python
  # Table-type-aware SQL generation
  if "kunde" in table_name:  # Customer table
      sql = f"SELECT COUNT(*) FROM {table}"
  elif "artikel" in table_name:  # Product table
      sql = f"SELECT COUNT(*) FROM {table}"
  ```
- **Rationale**: Original complex subgraph was failing; direct approach is more reliable

#### 5. ExecAndRecoveryAgent
- **Input**: Generated SQL query
- **Output**: Query results or error information
- **Capabilities**: Row limiting, timeout handling, error recovery
- **Unchanged**: Core functionality working well

#### 6. AnswerAgent (Enhanced)
- **New Features**: Contextual response generation
- **Logic**:
  ```python
  # Instead of generic errors:
  if query_about_sales and found_customer_table:
      return f"I found customer data in {table_name}, which contains {count} customer records. This table appears to contain customer relationships rather than direct sales transactions."
  ```

### Database Integration

#### Scout Mode Catalog
- **Purpose**: Comprehensive database schema cataloging on MCP server startup
- **Benefits**: Enables semantic table discovery without repeated database queries
- **Integration**: DiscoveryAgent uses MCP search_tables tool backed by Scout catalog

#### MCP Protocol
- **Transport**: JSON-RPC over HTTP
- **Cross-Platform**: LangGraph (macOS) ↔ MCP Server (Windows)
- **Tools**: search_tables, describe_table, query_bounded, query, get_column_index

## Consequences

### Positive

1. **Functional System**: Agent now provides meaningful responses instead of generic errors
2. **Contextual Responses**: Users understand what data exists and why certain queries can't be answered
3. **Scout Mode Utilization**: Leverages the comprehensive database catalog effectively
4. **German ERP Support**: Handles German table names and business terminology
5. **Reliable Operation**: System works consistently across different query types

### Negative

1. **Reduced Complexity**: Lost sophisticated join planning and complex SQL generation capabilities
2. **Limited Analytics**: Current system focuses on counts rather than complex aggregations
3. **Hardcoded Logic**: Table selection and SQL generation use pattern matching rather than full schema analysis
4. **Time Filtering**: Not implemented due to unknown date column names in ERP schema

### Risks

1. **Scalability**: Direct SQL generation may not scale to more complex analytical queries
2. **Schema Changes**: Hardcoded patterns may break if database schema changes
3. **Feature Regression**: Some advanced capabilities from original design may be lost

## Implementation Details

### Code Changes Made

1. **Enhanced Discovery Agent** (`langgraph_integration/agents/discovery/agent.py`):
   - Added `_fallback_business_table_discovery()` method
   - Improved table scoring with German ERP terminology
   - Better integration with Scout catalog results

2. **Simplified Orchestrator** (`langgraph_integration/orchestrator.py`):
   - Replaced complex JOIN_SQL subgraph with direct SQL generation
   - Added `_select_best_table_for_query()` method
   - Enhanced Answer node with contextual response logic

3. **Contextual Answer Logic**:
   - Table-aware response generation
   - Explanation of data found vs. requested
   - Database structure insights for users

### Configuration

- **ENABLE_SCOUT_MODE**: Must be true for proper catalog initialization
- **MCP_IP_ADDRESS**: Correctly configured for cross-platform communication
- **ROW_LIMIT**: 10 for exploratory queries, configurable

## Future Considerations

### Potential Enhancements

1. **Schema Analysis**: Implement column type detection for better SQL generation
2. **Date Column Discovery**: Automatic identification of temporal columns for time-based queries
3. **Complex Joins**: Re-implement join planning for multi-table analytics
4. **Query Expansion**: Support for more complex business intelligence queries

### Migration Path

If more sophisticated SQL generation is needed:
1. Debug and fix the original JOIN_SQL subgraph
2. Implement gradual migration from direct SQL to complex generation
3. Add feature flags to enable/disable advanced capabilities

## Conclusion

The simplified agent orchestration architecture successfully restored system functionality while maintaining the core multi-agent design and Scout mode integration. The system now provides meaningful, contextual responses that help users understand their data landscape, even when specific queries cannot be answered due to database structure limitations.

This architecture represents a pragmatic balance between sophistication and reliability, ensuring the Proactive Context Learning system delivers value to users while preserving the foundation for future enhancements.

## Related ADRs

- ADR-0006: Agent Architecture and Data Integration
- ADR-0021: Intent Parser Agent Design
- ADR-0022: MCP Response Format Parsing
