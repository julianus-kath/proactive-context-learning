# Crawling Agent with LLM Integration

This directory contains the implementation of the LLM-powered agent for the crawling agent system.

## Overview

The agent uses an LLM to:
1. Analyze natural language queries
2. Select appropriate tools
3. Generate structured queries
4. Process and combine results

## Components

### Agent

The `Agent` class is the core component that orchestrates the query processing workflow. It uses the LLM provider to:
- Analyze the query to understand its intent and extract entities
- Select the appropriate tools to use
- Generate structured queries for each tool
- Process and combine the results

### Tools

Tools are the primary way for the agent to interact with external systems and perform actions. The following tools are available:

- **ERPQueryTool**: Executes SQL queries against the ERP system
- **DocumentStorageQueryTool**: Executes MongoDB queries against the document storage system
- **KnowledgeGraphQueryTool**: Executes SPARQL queries against the knowledge graph system
- **SchemaInformationTool**: Retrieves schema information about data sources

### Tool Registry

The `ToolRegistry` class manages the available tools and provides methods to register, retrieve, and list tools.

## LLM Integration

The agent uses a modular LLM provider interface that allows different LLM backends to be used interchangeably. The following providers are available:

- **OpenAIProvider**: Uses the OpenAI API (GPT-4, GPT-3.5, etc.)
- **MockProvider**: A mock provider for testing purposes

## Configuration

The agent can be configured using environment variables:

- `LLM_PROVIDER`: The LLM provider to use (openai, mock)
- `OPENAI_API_KEY`: OpenAI API key (required for OpenAI provider)
- `OPENAI_ORGANIZATION`: OpenAI organization ID (optional for OpenAI provider)

## Usage

To use the agent, create an instance with an LLM provider and tool registry, then call the `process_query` method:

```python
from crawling_agent.llm.provider import LLMProviderFactory
from crawling_agent.agent.agent import Agent
from crawling_agent.agent.tool import (
    ERPQueryTool,
    DocumentStorageQueryTool,
    KnowledgeGraphQueryTool,
    SchemaInformationTool,
    ToolRegistry
)

# Create the LLM provider
llm_provider = LLMProviderFactory.create("openai")

# Create the tool registry
tool_registry = ToolRegistry()

# Register tools
tool_registry.register_tool(ERPQueryTool({"mock_mode": True}))
tool_registry.register_tool(DocumentStorageQueryTool({"mock_mode": True}))
tool_registry.register_tool(KnowledgeGraphQueryTool({"mock_mode": True}))
tool_registry.register_tool(SchemaInformationTool({"mock_mode": True}))

# Create the agent
agent = Agent(llm_provider, tool_registry)

# Process a query
result = await agent.process_query("How many customers do we have?")
```

## API Integration

The agent is integrated with the Crawling Agent API, which provides a REST API for executing natural language queries. See the `crawling_agent/api/agent_api.py` file for details.