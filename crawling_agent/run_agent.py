"""
Script to run the multi-source agent.
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

from crawling_agent.agent.multi_source_agent import MultiSourceAgent
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector
from crawling_agent.llm.llm_client_factory import LLMClientFactory


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_agent")


async def run_interactive_session(
    agent: MultiSourceAgent,
    exit_commands: list = ["exit", "quit", "bye"],
):
    """
    Run an interactive session with the agent.
    
    Args:
        agent: The agent to use
        exit_commands: List of commands that will exit the session (default: ["exit", "quit", "bye"])
    """
    print("\nWelcome to the Multi-Source Agent!")
    print("You can ask questions that require integrating data from multiple sources.")
    print(f"Type one of {exit_commands} to exit.\n")
    
    while True:
        try:
            # Get user input
            query = input("\nYou: ")
            
            # Check if the user wants to exit
            if query.lower() in exit_commands:
                print("\nGoodbye!")
                break
            
            # Process the query
            print("\nAgent is thinking...")
            response = await agent.process_query(query)
            
            # Print the response
            print(f"\nAgent: {response}")
        
        except KeyboardInterrupt:
            print("\n\nSession interrupted. Exiting...")
            break
        
        except Exception as e:
            print(f"\nError: {str(e)}")
            logger.exception("Error in interactive session")


def main():
    """Run the multi-source agent."""
    parser = argparse.ArgumentParser(description="Run the multi-source agent")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--llm-type",
        type=str,
        default="openai",
        choices=LLMClientFactory.get_available_client_types(),
        help="The type of LLM to use",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        help="The LLM model to use (default depends on LLM type)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="The API key for the LLM service",
    )
    parser.add_argument(
        "--erp-url",
        type=str,
        default="http://localhost:8001/sse",
        help="The URL of the ERP server",
    )
    parser.add_argument(
        "--document-url",
        type=str,
        default="http://localhost:8002/sse",
        help="The URL of the document storage server",
    )
    parser.add_argument(
        "--knowledge-url",
        type=str,
        default="http://localhost:8003/sse",
        help="The URL of the knowledge graph server",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=5,
        help="Maximum number of reasoning steps",
    )
    parser.add_argument(
        "--use-agents-sdk",
        action="store_true",
        help="Use the OpenAI Agents SDK for enhanced reasoning capabilities",
    )
    parser.add_argument(
        "--no-agents-sdk",
        action="store_false",
        dest="use_agents_sdk",
        help="Don't use the OpenAI Agents SDK",
    )
    parser.set_defaults(use_agents_sdk=True)
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    try:
        # Create the LLM client
        llm_client = LLMClientFactory.create_client(
            client_type=args.llm_type,
            api_key=args.api_key,
            model=args.llm_model,
            use_agents_sdk=args.use_agents_sdk,
        )
        
        # Create the connectors
        erp_connector = MCPERPConnector(server_url=args.erp_url)
        document_connector = MCPDocumentStorageConnector(server_url=args.document_url)
        knowledge_connector = MCPKnowledgeGraphConnector(server_url=args.knowledge_url)
        
        # Create the agent
        agent = MultiSourceAgent(
            llm_client=llm_client,
            erp_connector=erp_connector,
            document_connector=document_connector,
            knowledge_connector=knowledge_connector,
            max_reasoning_steps=args.max_steps,
            debug=args.debug,
        )
        
        # Run the interactive session
        asyncio.run(run_interactive_session(agent))
    
    except Exception as e:
        logger.exception("Error running agent")
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()