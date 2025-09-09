"""
Test script for the Crawling Agent v2.
"""
import os
import json
import asyncio
import logging
from typing import Dict, List, Any

from crawling_agent.llm.provider import LLMProviderFactory
from crawling_agent.tools.base import ToolRegistry
from crawling_agent.tools.sql_tool import SQLTool
from crawling_agent.agent.mcp_agent import MCPCrawlingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_crawling_agent():
    """Test the Crawling Agent v2."""
    # Initialize the LLM provider
    llm_provider_name = os.environ.get("LLM_PROVIDER", "openai")
    llm_config = {}
    
    if llm_provider_name == "openai":
        llm_config["api_key"] = os.environ.get("OPENAI_API_KEY")
        llm_config["model"] = os.environ.get("OPENAI_MODEL", "gpt-4")
    
    llm_provider = LLMProviderFactory.create(llm_provider_name, llm_config)
    logger.info(f"Initialized LLM provider: {llm_provider_name}")
    
    # Initialize the tool registry
    tool_registry = ToolRegistry()
    
    # Register tools
    sql_config = {
        "host": os.environ.get("SQL_HOST", "localhost"),
        "port": os.environ.get("SQL_PORT", "8001")
    }
    tool_registry.register_tool(SQLTool(sql_config))
    
    # Initialize the agent
    agent = MCPCrawlingAgent(llm_provider, tool_registry)
    
    # Test queries
    test_queries = [
        "How many customers do we have?",
        "Find all expensive products with price greater than $1000",
        "Show me all employees in the sales department",
        "List all completed orders",
        "What is the total revenue from orders this month?"
    ]
    
    # Run the test queries
    for query in test_queries:
        logger.info(f"Testing query: {query}")
        
        try:
            result = await agent.run(query)
            
            logger.info(f"Query: {query}")
            logger.info(f"SQL Query: {result.query_text}")
            logger.info(f"Explanation: {result.nl_explanation}")
            logger.info(f"Result count: {len(result.raw_result)}")
            
            if result.raw_result:
                logger.info(f"Sample result: {json.dumps(result.raw_result[0], indent=2)}")
            
            logger.info("-" * 80)
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_crawling_agent())