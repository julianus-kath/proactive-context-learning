#!/usr/bin/env python3
"""
Test script for the o3 reasoning model and agent-based workflow.

This script tests the OpenAI LLM client with the o3 reasoning model and the agent-based workflow.
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import Dict, List, Any

from crawling_agent.llm.llm_client_factory import LLMClientFactory


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_o3_agent")


async def test_simple_query(api_key: str, model: str = "gpt-4o-2024-05-13", use_agents_sdk: bool = True):
    """
    Test a simple query with the o3 reasoning model.
    
    Args:
        api_key: The OpenAI API key
        model: The model to use (default: "gpt-4o-2024-05-13")
        use_agents_sdk: Whether to use the OpenAI Agents SDK (default: True)
    """
    # Create the LLM client
    llm_client = LLMClientFactory.create_client(
        client_type="openai",
        api_key=api_key,
        model=model,
        use_agents_sdk=use_agents_sdk,
    )
    
    # Define a simple system prompt
    system_prompt = """
    You are an advanced reasoning agent that can analyze complex queries about data.
    When given a query, explain how you would approach answering it by:
    1. Identifying the intent
    2. Determining which data sources would be needed
    3. Describing what queries you would make
    4. Explaining how you would integrate the results
    """
    
    # Define a simple query
    query = "What were the top-selling products in Q1 2023, and how do they compare to Q1 2022?"
    
    # Create the messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    
    # Generate a response
    logger.info(f"Generating response for query: {query}")
    response = await llm_client.generate_response(messages)
    
    # Print the response
    print("\nSystem Prompt:")
    print(system_prompt)
    print("\nQuery:")
    print(query)
    print("\nResponse:")
    print(response.get("content", "No content"))


async def test_tool_calls(api_key: str, model: str = "gpt-4o-2024-05-13", use_agents_sdk: bool = True):
    """
    Test tool calls with the o3 reasoning model.
    
    Args:
        api_key: The OpenAI API key
        model: The model to use (default: "gpt-4o-2024-05-13")
        use_agents_sdk: Whether to use the OpenAI Agents SDK (default: True)
    """
    # Create the LLM client
    llm_client = LLMClientFactory.create_client(
        client_type="openai",
        api_key=api_key,
        model=model,
        use_agents_sdk=use_agents_sdk,
    )
    
    # Define a simple system prompt
    system_prompt = """
    You are an advanced reasoning agent that can analyze complex queries about data.
    You have access to tools that allow you to query different data sources.
    Use these tools to gather the information needed to answer the user's query.
    """
    
    # Define the tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_sql_database",
                "description": "Execute a SQL query on the ERP database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to execute"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_document_storage",
                "description": "Query the document storage for relevant documents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "description": "The collection to query"
                        },
                        "filter": {
                            "type": "object",
                            "description": "The filter to apply to the query"
                        }
                    },
                    "required": ["collection", "filter"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_knowledge_graph",
                "description": "Query the knowledge graph for entity relationships",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The graph query to execute"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
    # Define a simple query
    query = "What were the top-selling products in Q1 2023, and how do they compare to Q1 2022?"
    
    # Create the messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    
    # Generate tool calls
    logger.info(f"Generating tool calls for query: {query}")
    response = await llm_client.generate_tool_calls(messages, tools)
    
    # Print the response
    print("\nSystem Prompt:")
    print(system_prompt)
    print("\nQuery:")
    print(query)
    print("\nResponse:")
    print(response.get("content", "No content"))
    
    # Print the tool calls
    if "tool_calls" in response:
        print("\nTool Calls:")
        for tool_call in response["tool_calls"]:
            print(f"Tool: {tool_call['function']['name']}")
            print(f"Arguments: {tool_call['function']['arguments']}")
            print()


def main():
    """Run the test script."""
    parser = argparse.ArgumentParser(description="Test the o3 reasoning model and agent-based workflow")
    parser.add_argument(
        "--api-key",
        type=str,
        help="The OpenAI API key",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-05-13",
        help="The model to use (default: gpt-4o-2024-05-13)",
    )
    parser.add_argument(
        "--use-agents-sdk",
        action="store_true",
        help="Use the OpenAI Agents SDK",
    )
    parser.add_argument(
        "--no-agents-sdk",
        action="store_false",
        dest="use_agents_sdk",
        help="Don't use the OpenAI Agents SDK",
    )
    parser.add_argument(
        "--test-type",
        type=str,
        choices=["simple", "tools", "both"],
        default="both",
        help="The type of test to run (default: both)",
    )
    parser.set_defaults(use_agents_sdk=True)
    
    args = parser.parse_args()
    
    # Get the API key
    api_key = args.api_key
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key is None:
            # Prompt the user for the API key
            api_key = input("Enter your OpenAI API key: ")
            if not api_key:
                print("Error: OpenAI API key not provided")
                sys.exit(1)
            # Set the API key in the environment for future use
            os.environ["OPENAI_API_KEY"] = api_key
    
    # Run the tests
    if args.test_type == "simple" or args.test_type == "both":
        asyncio.run(test_simple_query(api_key, args.model, args.use_agents_sdk))
    
    if args.test_type == "tools" or args.test_type == "both":
        asyncio.run(test_tool_calls(api_key, args.model, args.use_agents_sdk))


if __name__ == "__main__":
    main()