"""
Script to run both the MCP servers and the multi-source agent.
"""
import argparse
import asyncio
import logging
import multiprocessing
import os
import signal
import sys
import time
from typing import List, Tuple

from crawling_agent.agent.multi_source_agent import MultiSourceAgent
from crawling_agent.config import (
    OPENAI_API_KEY,
    DEFAULT_LLM_TYPE,
    DEFAULT_LLM_MODEL,
    ERP_SERVER_URL,
    DOCUMENT_STORAGE_SERVER_URL,
    KNOWLEDGE_GRAPH_SERVER_URL,
    MAX_REASONING_STEPS,
    DEBUG_MODE,
    DB_PATH,
    JSON_PATH,
)
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector
from crawling_agent.llm.llm_client_factory import LLMClientFactory
from crawling_agent.run_servers import run_erp_server, run_document_storage_server, run_knowledge_graph_server


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_all")


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
    """Run both the MCP servers and the multi-source agent."""
    parser = argparse.ArgumentParser(description="Run both the MCP servers and the multi-source agent")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--llm-type",
        type=str,
        default=DEFAULT_LLM_TYPE,
        choices=LLMClientFactory.get_available_client_types(),
        help=f"The type of LLM to use (default: {DEFAULT_LLM_TYPE})",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help=f"The LLM model to use (default: {DEFAULT_LLM_MODEL})",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=OPENAI_API_KEY,
        help="The API key for the LLM service",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=MAX_REASONING_STEPS,
        help=f"Maximum number of reasoning steps (default: {MAX_REASONING_STEPS})",
    )
    parser.add_argument(
        "--servers",
        type=str,
        nargs="+",
        choices=["erp", "document", "knowledge", "all"],
        default=["all"],
        help="Servers to run (default: all)",
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Start the servers
    processes = []
    
    try:
        # Determine which servers to run
        servers_to_run = []
        if "all" in args.servers or "erp" in args.servers:
            servers_to_run.append(("ERP Server", run_erp_server))
        
        if "all" in args.servers or "document" in args.servers:
            servers_to_run.append(("Document Storage Server", run_document_storage_server))
        
        if "all" in args.servers or "knowledge" in args.servers:
            servers_to_run.append(("Knowledge Graph Server", run_knowledge_graph_server))
        
        # Start the servers
        for name, func in servers_to_run:
            logger.info(f"Starting {name}...")
            process = multiprocessing.Process(target=func)
            process.start()
            processes.append((name, process))
            time.sleep(1)  # Give each server a moment to start
        
        logger.info("All servers started")
        
        # Wait a moment for the servers to initialize
        time.sleep(2)
        
        # Create the LLM client
        llm_client = LLMClientFactory.create_client(
            client_type=args.llm_type,
            api_key=args.api_key,
            model=args.llm_model,
        )
        
        # Create the connectors
        erp_connector = MCPERPConnector(server_url=ERP_SERVER_URL)
        document_connector = MCPDocumentStorageConnector(server_url=DOCUMENT_STORAGE_SERVER_URL)
        knowledge_connector = MCPKnowledgeGraphConnector(server_url=KNOWLEDGE_GRAPH_SERVER_URL)
        
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
    
    finally:
        # Stop the servers
        logger.info("Stopping servers...")
        
        # Terminate all processes
        for name, process in processes:
            logger.info(f"Stopping {name}...")
            process.terminate()
        
        # Wait for all processes to terminate
        for _, process in processes:
            process.join()
        
        logger.info("All servers stopped")


if __name__ == "__main__":
    main()