"""
Script to run all MCP servers.
"""
import argparse
import multiprocessing
import os
import sys
import time
from typing import List, Dict, Any

from crawling_agent.servers.erp_server import ERPServer
from crawling_agent.servers.document_storage_server import DocumentStorageServer
from crawling_agent.servers.knowledge_graph_server import KnowledgeGraphServer
from crawling_agent.utils.logger import get_logger


def run_erp_server(host: str, port: int, config_path: str, mock_mode: bool):
    """Run the ERP server."""
    server = ERPServer(
        host=host,
        port=port,
        config_path=config_path,
        mock_mode=mock_mode
    )
    server.run()


def run_document_storage_server(host: str, port: int, config_path: str, mock_mode: bool):
    """Run the Document Storage server."""
    server = DocumentStorageServer(
        host=host,
        port=port,
        config_path=config_path,
        mock_mode=mock_mode
    )
    server.run()


def run_knowledge_graph_server(host: str, port: int, config_path: str, mock_mode: bool):
    """Run the Knowledge Graph server."""
    server = KnowledgeGraphServer(
        host=host,
        port=port,
        config_path=config_path,
        mock_mode=mock_mode
    )
    server.run()


def main():
    """Run all MCP servers."""
    parser = argparse.ArgumentParser(description="Run all MCP servers")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind the servers to")
    parser.add_argument("--erp-port", type=int, default=8001, help="Port for the ERP server")
    parser.add_argument("--doc-port", type=int, default=8002, help="Port for the Document Storage server")
    parser.add_argument("--kg-port", type=int, default=8003, help="Port for the Knowledge Graph server")
    parser.add_argument("--config", type=str, help="Path to the configuration file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    
    args = parser.parse_args()
    
    logger = get_logger("run_servers")
    logger.info("Starting all MCP servers")
    
    # Get the configuration path
    if args.config:
        config_path = args.config
    else:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "config.yaml"
        )
    
    # Create processes for each server
    processes = []
    
    # ERP Server
    erp_process = multiprocessing.Process(
        target=run_erp_server,
        args=(args.host, args.erp_port, config_path, args.mock)
    )
    processes.append(("ERP", erp_process))
    
    # Document Storage Server
    doc_process = multiprocessing.Process(
        target=run_document_storage_server,
        args=(args.host, args.doc_port, config_path, args.mock)
    )
    processes.append(("Document Storage", doc_process))
    
    # Knowledge Graph Server
    kg_process = multiprocessing.Process(
        target=run_knowledge_graph_server,
        args=(args.host, args.kg_port, config_path, args.mock)
    )
    processes.append(("Knowledge Graph", kg_process))
    
    # Start all processes
    for name, process in processes:
        logger.info(f"Starting {name} server")
        process.start()
    
    # Wait for all processes to finish
    try:
        while True:
            time.sleep(1)
            # Check if any process has terminated
            for name, process in processes:
                if not process.is_alive():
                    logger.error(f"{name} server has terminated unexpectedly")
                    # Terminate all other processes
                    for _, p in processes:
                        if p.is_alive():
                            p.terminate()
                    sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down servers")
        # Terminate all processes
        for name, process in processes:
            logger.info(f"Terminating {name} server")
            process.terminate()
    
    # Wait for all processes to terminate
    for name, process in processes:
        process.join()
    
    logger.info("All servers have been shut down")


if __name__ == "__main__":
    main()