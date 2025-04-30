# ADR 0005: Adoption of Model-Context Protocol (MCP)

## Status

Accepted

## Date

30.4.2025

## Context

The crawling agent system needs to interact with multiple heterogeneous data sources (ERP systems, document storage, knowledge graphs) in a consistent and maintainable way. We need a standardized approach to:

1. Process natural language queries from users
2. Translate these queries into structured data source-specific queries
3. Execute these queries against different data sources
4. Collect and combine results into coherent responses
5. Maintain traceability throughout the process

The system requires a clear separation of concerns between components while ensuring smooth data flow between them. Additionally, we need to support future extensions to new data sources and query types.

## Decision

We will adopt the Model-Context Protocol (MCP) as the core architectural pattern for our crawling agent system. The MCP divides the processing flow into three distinct phases:

1. **Planning Phase**: Translating natural language queries into structured plans and actions
2. **Acting Phase**: Executing the planned actions against data sources
3. **Observing Phase**: Collecting and processing the results of actions

The central component of this architecture will be the `CrawlingContext` object, which will:
- Maintain state throughout the entire process
- Store the original query, plan, actions, observations, and final result
- Provide methods for updating its state and tracking progress
- Serve as the primary means of communication between components

## Consequences

### Positive
- **Clear Separation of Concerns**: Each component has a well-defined responsibility
- **Improved Traceability**: The entire process flow is captured in the context object
- **Enhanced Debugging**: The state at each step can be inspected and logged
- **Simplified Testing**: Components can be tested in isolation with mock contexts
- **Extensibility**: New data sources and query types can be added without changing the core protocol
- **Consistency**: All components interact with data in a standardized way
- **Stateful Processing**: The context maintains state throughout the process, enabling complex multi-step operations

### Negative
- **Increased Complexity**: Introduces additional abstractions and indirection
- **Learning Curve**: Developers need to understand the MCP pattern
- **Potential Performance Overhead**: Maintaining and passing context objects may introduce some overhead
- **State Management Challenges**: Proper state management becomes critical

## Implementation Details

### MCP Architecture Diagram

```
+------------------------------------------------------------------------------------------------------+
|                                     Model-Context Protocol (MCP)                                      |
+------------------------------------------------------------------------------------------------------+
                                                |
                                                v
+------------------------------------------------------------------------------------------------------+
|                                        CrawlingContext                                                |
|                                                                                                      |
|  +----------------+  +----------------+  +----------------+  +----------------+  +----------------+  |
|  | context_id     |  | original_query |  | thought        |  | plan           |  | action_requests|  |
|  +----------------+  +----------------+  +----------------+  +----------------+  +----------------+  |
|                                                                                                      |
|  +----------------+  +----------------+  +----------------+  +----------------+                      |
|  | observations   |  | final_result   |  | task_instruction| | status         |                      |
|  +----------------+  +----------------+  +----------------+  +----------------+                      |
+------------------------------------------------------------------------------------------------------+
                |                  |                   |                  |
                v                  v                   v                  v
+---------------+--+  +-----------+-------+  +--------+---------+  +-----+------------+
|   Planning Phase  |  |   Acting Phase   |  | Observing Phase  |  |  Controller      |
+------------------+  +------------------+  +------------------+  +------------------+
| - Query Analysis |  | - Execute Actions|  | - Process Results|  | - Orchestration  |
| - Tool Selection |  | - Data Retrieval |  | - Combine Data   |  | - State Management|
| - Query Generation|  | - Error Handling|  | - Format Response|  | - Error Recovery |
+--------+---------+  +--------+---------+  +--------+---------+  +------------------+
         |                     |                     |                      |
         v                     v                     v                      v
+------------------+  +------------------+  +------------------+  +------------------+
|  Data Sources    |  |    Connectors    |  |  Response Format |  |  API Endpoints   |
+------------------+  +------------------+  +------------------+  +------------------+
| - ERP System     |  | - ERPConnector   |  | - JSON           |  | - Query          |
| - Document Store |  | - DocumentStorage|  | - Text           |  | - Health         |
| - Knowledge Graph|  | - KnowledgeGraph |  | - Structured     |  | - Info           |
+------------------+  +------------------+  +------------------+  +------------------+
```

The MCP will be implemented with the following key components:

1. **CrawlingContext**: The central state container with the following structure:
   - `context_id`: Unique identifier for the context
   - `original_query`: The user's natural language query
   - `thought`: The reasoning process
   - `plan`: The structured plan for addressing the query
   - `action_requests`: List of actions to be performed
   - `observations`: Results collected from actions
   - `final_result`: The processed final response
   - `task_instruction`: Structured representation of the task
   - `status`: Current state of processing (initialized, planning, acting, observing, completed, failed)

2. **ActionRequest**: Represents a specific action to be performed:
   - `action_id`: Unique identifier for the action
   - `action_type`: Type of action (query_erp, query_kg, query_document_storage)
   - `parameters`: Action-specific parameters
   - `source`: Component that requested the action
   - `status`: Current state of the action (pending, in_progress, completed, failed)

3. **TaskInstruction**: Structured representation of what needs to be done:
   - `task_id`: Unique identifier for the task
   - `original_query`: The user's query
   - `description`: Description of the task
   - `data_sources`: List of data sources to query
   - `queries`: List of structured queries for each data source

4. **Connectors**: Components that execute queries against specific data sources:
   - `ERPConnector`: Executes SQL queries against ERP systems
   - `DocumentStorageConnector`: Executes MongoDB queries against document storage
   - `KnowledgeGraphConnector`: Executes SPARQL queries against knowledge graphs

5. **Controller**: Orchestrates the entire process:
   - Manages the flow between planning, acting, and observing phases
   - Delegates actions to appropriate connectors
   - Updates the context with results

### MCP Sequence Diagram

```
+--------+      +------------+      +------------+      +------------+      +------------+
| Client |      | API        |      | Controller |      | Connectors |      | Data       |
|        |      | Endpoint   |      |            |      |            |      | Sources    |
+---+----+      +-----+------+      +-----+------+      +-----+------+      +-----+------+
    |                 |                   |                   |                   |
    | Natural Language|                   |                   |                   |
    | Query           |                   |                   |                   |
    +---------------->|                   |                   |                   |
    |                 | Create Context    |                   |                   |
    |                 +------------------>|                   |                   |
    |                 |                   |                   |                   |
    |                 |                   | Planning Phase    |                   |
    |                 |                   |-------------------|                   |
    |                 |                   | 1. Analyze Query  |                   |
    |                 |                   | 2. Select Tools   |                   |
    |                 |                   | 3. Generate Query |                   |
    |                 |                   |                   |                   |
    |                 |                   | Create Action     |                   |
    |                 |                   | Requests          |                   |
    |                 |                   |------------------>|                   |
    |                 |                   |                   |                   |
    |                 |                   |                   | Acting Phase      |
    |                 |                   |                   |-------------------|
    |                 |                   |                   | Execute Queries   |
    |                 |                   |                   |------------------>|
    |                 |                   |                   |                   |
    |                 |                   |                   |                   | Process
    |                 |                   |                   |                   | Queries
    |                 |                   |                   |                   |---------|
    |                 |                   |                   |                   |         |
    |                 |                   |                   |                   |<--------|
    |                 |                   |                   |                   |
    |                 |                   |                   | Return Results    |
    |                 |                   |                   |<------------------|
    |                 |                   |                   |                   |
    |                 |                   |                   | Update Context    |
    |                 |                   |<------------------|                   |
    |                 |                   |                   |                   |
    |                 |                   | Observing Phase   |                   |
    |                 |                   |-------------------|                   |
    |                 |                   | 1. Process Results|                   |
    |                 |                   | 2. Combine Data   |                   |
    |                 |                   | 3. Format Response|                   |
    |                 |                   |                   |                   |
    |                 | Return Response   |                   |                   |
    |                 |<------------------|                   |                   |
    |                 |                   |                   |                   |
    | Formatted       |                   |                   |                   |
    | Response        |                   |                   |                   |
    |<----------------|                   |                   |                   |
    |                 |                   |                   |                   |
```

### MCP Data Flow Diagram

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
| Natural Language |     | Structured Query |     |  Query Results   |
|      Query       +---->+   Generation     +---->+   Processing     |
|                  |     |                  |     |                  |
+------------------+     +------------------+     +------------------+
                               |                         |
                               v                         v
                         +-----+-----+           +-------+-------+
                         |           |           |               |
                         | ERP Query |           | ERP Results   |
                         |           |           |               |
                         +-----------+           +---------------+
                               |                         ^
                               v                         |
                         +-----+-----+           +-------+-------+
                         |           |           |               |
                         | Document  |           | Document      |
                         | Query     |           | Results       |
                         |           |           |               |
                         +-----------+           +---------------+
                               |                         ^
                               v                         |
                         +-----+-----+           +-------+-------+
                         |           |           |               |
                         | Knowledge |           | Knowledge     |
                         | Graph     |           | Graph Results |
                         | Query     |           |               |
                         +-----------+           +---------------+
                               |                         ^
                               |                         |
                               v                         |
                         +-----+---------------------+   |
                         |                           |   |
                         | Data Source Connectors    +---+
                         |                           |
                         +---------------------------+
```

## Alternatives Considered

1. **Simple Query-Response Model**: A simpler approach where each component directly calls the next in a pipeline. Rejected due to lack of state tracking and difficulty in debugging complex flows.

2. **Event-Driven Architecture**: Using events to communicate between components. Rejected due to increased complexity and potential for race conditions.

3. **Microservices with API Gateways**: Implementing each component as a separate microservice. Rejected as overly complex for our current needs, though the MCP pattern could be extended to this architecture in the future if needed.

## References

- Model-Context Protocol design patterns
- Similar implementations in large language model systems
- State management patterns in distributed systems

## Notes

The MCP implementation will be validated through comprehensive testing, including unit tests for individual components and integration tests for the entire flow. We will monitor the performance and maintainability of this approach and make adjustments as needed.