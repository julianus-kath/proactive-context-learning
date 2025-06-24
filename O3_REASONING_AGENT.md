# O3 Reasoning Model and Agent-Based Workflow

This document explains how to use the o3 reasoning model and agent-based workflow in the crawling agent system.

## Overview

The crawling agent system now supports the OpenAI o3 reasoning model and the agent-based workflow using the OpenAI Agents SDK. This enables more sophisticated reasoning and better handling of complex queries that require integrating data from multiple sources.

## The Workflow

The agent-based workflow follows these steps:

1. **Intent Identification**: The AI model identifies the intent in the user's natural language query.
2. **Data Source Selection**: The agent determines which data sources are necessary to fulfill the query.
3. **Query Formulation**: The agent creates appropriate queries for each relevant data source.
4. **Data Integration**: The agent combines and synthesizes information from multiple sources.
5. **Response Generation**: The agent provides a clear, comprehensive answer to the user's query.

## Using the O3 Reasoning Model

The o3 reasoning model is now the default model used by the OpenAI LLM client. You can specify a different model using the `--llm-model` command-line argument when running the agent.

```bash
# Run the agent with the o3 reasoning model (default)
python -m crawling_agent.run_agent

# Run the agent with a different model
python -m crawling_agent.run_agent --llm-model gpt-4
```

## Using the Agent-Based Workflow

The agent-based workflow is enabled by default when the OpenAI Agents SDK is available. You can disable it using the `--no-agents-sdk` command-line argument.

```bash
# Run the agent with the agent-based workflow (default)
python -m crawling_agent.run_agent

# Run the agent without the agent-based workflow
python -m crawling_agent.run_agent --no-agents-sdk
```

## Installation

To use the o3 reasoning model and agent-based workflow, you need to install the OpenAI Agents SDK:

```bash
pip install openai-agents
```

This package is now included in the `requirements.txt` file, so it will be installed automatically when you install the dependencies.

## Testing

You can test the o3 reasoning model and agent-based workflow using the `test_o3_agent.py` script:

```bash
# Test both simple queries and tool calls
python test_o3_agent.py

# Test only simple queries
python test_o3_agent.py --test-type simple

# Test only tool calls
python test_o3_agent.py --test-type tools

# Test with a different model
python test_o3_agent.py --model gpt-4

# Test without the agent-based workflow
python test_o3_agent.py --no-agents-sdk
```

## Example Queries

Here are some example queries that demonstrate the capabilities of the o3 reasoning model and agent-based workflow:

1. "What were the top-selling products in Q1 2023, and how do they compare to Q1 2022?"
2. "Find all customers who purchased Product X and also viewed Product Y in the last 30 days."
3. "Which suppliers have the highest on-time delivery rate for our most popular products?"
4. "Identify potential cross-selling opportunities based on customer purchase history and product relationships."
5. "What is the average customer satisfaction score for orders that were delivered late, and what are the main reasons for dissatisfaction?"

## Troubleshooting

If you encounter issues with the o3 reasoning model or agent-based workflow, try the following:

1. Make sure you have the latest version of the OpenAI Agents SDK installed.
2. Check that your OpenAI API key has access to the o3 reasoning model.
3. Try running the agent with the `--debug` flag to see more detailed logs.
4. If the agent-based workflow is not working, try running without it using the `--no-agents-sdk` flag.

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [OpenAI API Documentation](https://platform.openai.com/docs/guides/agents)
- [Model-Context Protocol (MCP) Implementation](./crawling_agent/MCP_IMPLEMENTATION.md)