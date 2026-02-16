# ADR-0004: Crawling Agent Architecture

**Status**: Accepted
**Date**: 2025-04-29
**Author**: Julianus Kath

## Context

As part of a larger data fusion project, we need to develop a Crawling Agent that can retrieve data from multiple heterogeneous data sources based on natural language queries. The agent must be modular, extensible, and capable of interfacing with an ERP system (SQL), a Knowledge Graph (SPARQL), and a Document Storage system (MongoDB).

Key requirements:
- Translate natural language queries into structured task instructions using an LLM
- Crawl multiple data sources based on these instructions
- Return raw data without performing fusion or analytics
- Maintain a clean, modular architecture for future extensions
- Support easy integration with a future Fusing Agent

## Decision

We've implemented a modular Crawling Agent with the following architecture:

### 1. Component-Based Architecture

We've adopted a component-based architecture with clear separation of concerns:

- **Translator**: Converts natural language to structured task instructions
- **Controller**: Coordinates execution across data sources
- **Connectors**: Interface with specific data sources
- **Models**: Define data structures
- **Utils**: Provide common functionality

### 2. Data Flow

The data flow follows a clear pipeline:
1. Natural language query input
2. Translation to structured TaskInstruction
3. Dispatching to appropriate data source connectors
4. Parallel or sequential execution of queries
5. Collection and return of raw results

### 3. Configuration Management

We've implemented a flexible configuration system:
- YAML-based configuration file
- Environment variable substitution
- Default values for optional settings
- Runtime configuration options

### 4. Error Handling and Logging

We've implemented comprehensive error handling and logging:
- Structured logging with different levels
- Task-specific logging
- Performance metrics collection
- Error aggregation and reporting

### 5. Testing Strategy

We've designed for testability:
- Mock LLM implementation for testing without a real model
- Mock mode for connectors to test without real databases
- Clear interfaces for component mocking

## Consequences

### Positive

1. **Modularity**: Each component can be developed, tested, and replaced independently.
2. **Extensibility**: New data sources can be added by implementing new connectors.
3. **Separation of Concerns**: Clear boundaries between components make the system easier to understand and maintain.
4. **Configurability**: The system can be configured for different environments without code changes.
5. **Testability**: Mock implementations facilitate testing without external dependencies.
6. **Performance Options**: Support for both parallel and sequential execution provides flexibility.
7. **Type Safety**: Comprehensive type annotations improve code quality and IDE support.

### Negative

1. **Complexity**: The modular architecture introduces some overhead in terms of code complexity.
2. **Dependency Management**: Multiple components require careful management of dependencies.
3. **Configuration Overhead**: The flexible configuration system requires more initial setup.
4. **Mock Limitations**: Mock implementations may not fully represent real-world behavior.

## Technical Details

### Key Classes and Their Responsibilities

1. **TaskInstruction (Model)**
   - Structured representation of a crawling task
   - Contains queries for multiple data sources
   - Includes metadata for execution control

2. **QueryTranslator**
   - Translates natural language to TaskInstruction objects
   - Interfaces with LLM (or MockLLM for testing)
   - Handles translation errors

3. **CrawlingAgentController**
   - Coordinates execution across data sources
   - Manages connector lifecycle
   - Handles parallel/sequential execution
   - Aggregates results and errors

4. **Connectors (ERPConnector, KnowledgeGraphConnector, DocumentStorageConnector)**
   - Interface with specific data sources
   - Execute queries and process results
   - Handle connection management
   - Implement error handling

5. **Logger Utilities**
   - Provide structured logging
   - Support different log levels
   - Enable file and console logging
   - Track task execution

### Design Patterns Used

1. **Factory Pattern**: For creating connectors based on configuration
2. **Strategy Pattern**: For different query execution strategies
3. **Facade Pattern**: Controller provides a simplified interface to the complex subsystems
4. **Adapter Pattern**: Connectors adapt different data sources to a common interface
5. **Builder Pattern**: For constructing complex TaskInstruction objects
6. **Singleton Pattern**: For logger instances

## Alternatives Considered

### 1. Monolithic Architecture

**Decision**: Rejected in favor of a modular approach.

**Rationale**: A monolithic architecture would be simpler initially but would make future extensions and maintenance more difficult. The modular approach allows for independent development and testing of components.

### 2. Microservices Architecture

**Decision**: Rejected in favor of a component-based architecture within a single application.

**Rationale**: While microservices would provide even greater separation, they would introduce unnecessary complexity for this use case. The component-based approach provides sufficient modularity without the overhead of service communication.

### 3. Hard-Coded Query Translation Rules

**Decision**: Rejected in favor of LLM-based translation.

**Rationale**: Hard-coded rules would be brittle and difficult to maintain. The LLM approach provides flexibility and can handle a wider range of natural language inputs.

### 4. Direct Database Access

**Decision**: Rejected in favor of connector abstractions.

**Rationale**: Direct database access would create tight coupling with specific database implementations. The connector abstractions provide flexibility to change underlying data sources without affecting the rest of the system.

## Future Considerations

1. **Real LLM Integration**: Replace the mock LLM with a real implementation
2. **Additional Data Sources**: Add connectors for other data sources as needed
3. **Performance Optimization**: Optimize query execution and result processing
4. **Security Enhancements**: Add authentication and authorization mechanisms
5. **Monitoring and Metrics**: Add more detailed performance monitoring
6. **GUI Development**: Create a graphical interface for the Crawling Agent
7. **Integration with Fusing Agent**: Develop the interface for passing results to the Fusing Agent

## Conclusion

The modular architecture of the Crawling Agent provides a solid foundation for retrieving data from multiple heterogeneous sources based on natural language queries. The clear separation of concerns, flexible configuration, and comprehensive error handling make the system maintainable and extensible. The mock implementations facilitate testing and development without external dependencies, while the well-defined interfaces ensure smooth integration with the future Fusing Agent.
