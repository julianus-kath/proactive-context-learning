"""
Script to run all MCP servers.
"""
import argparse
import multiprocessing
import os
import sys
import time

from crawling_agent.servers.erp_server import ERPServer
from crawling_agent.servers.document_storage_server import DocumentStorageServer
from crawling_agent.servers.knowledge_graph_server import KnowledgeGraphServer


def run_erp_server():
    """Run the ERP Server."""
    db_path = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/synthetic_data.db"
    server = ERPServer(db_path=db_path, port=8001)
    server.run(transport="sse")


def run_document_storage_server():
    """Run the Document Storage Server."""
    json_path = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/mongodb_data.json"
    server = DocumentStorageServer(json_path=json_path, port=8002)
    server.run(transport="sse")


def run_knowledge_graph_server():
    """Run the Knowledge Graph Server."""
    server = KnowledgeGraphServer(port=8003)
    server.run(transport="sse")


def main():
    """Run all MCP servers."""
    parser = argparse.ArgumentParser(description="Run MCP servers")
    parser.add_argument(
        "--servers",
        type=str,
        nargs="+",
        choices=["erp", "document", "knowledge", "all"],
        default=["all"],
        help="Servers to run (default: all)",
    )
    
    args = parser.parse_args()
    
    servers_to_run = []
    if "all" in args.servers or "erp" in args.servers:
        servers_to_run.append(("ERP Server", run_erp_server))
    
    if "all" in args.servers or "document" in args.servers:
        servers_to_run.append(("Document Storage Server", run_document_storage_server))
    
    if "all" in args.servers or "knowledge" in args.servers:
        servers_to_run.append(("Knowledge Graph Server", run_knowledge_graph_server))
    
    processes = []
    
    try:
        for name, func in servers_to_run:
            print(f"Starting {name}...")
            process = multiprocessing.Process(target=func)
            process.start()
            processes.append((name, process))
            time.sleep(1)  # Give each server a moment to start
        
        print("All servers started. Press Ctrl+C to stop.")
        
        # Wait for all processes to complete (which they won't unless terminated)
        for _, process in processes:
            process.join()
    
    except KeyboardInterrupt:
        print("\nStopping servers...")
        
        # Terminate all processes
        for name, process in processes:
            print(f"Stopping {name}...")
            process.terminate()
        
        # Wait for all processes to terminate
        for _, process in processes:
            process.join()
        
        print("All servers stopped.")


if __name__ == "__main__":
    main()