"""
Test script for MCP servers and connectors.
"""
import argparse
import json
import time
import uuid
from typing import Dict, Any, List

from crawling_agent.connectors.mcp_erp_connector import ERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import DocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import KnowledgeGraphConnector
from crawling_agent.models.task_instruction import DataSourceQuery, QueryType


def test_erp_connector(host: str, port: int, mock_mode: bool):
    """Test the ERP connector."""
    print("\n=== Testing ERP Connector ===")
    
    # Initialize the connector
    connector = ERPConnector(host=host, port=port, mock_mode=mock_mode)
    
    # Check server info
    print("\nServer Info:")
    info = connector.get_server_info()
    print(json.dumps(info, indent=2))
    
    # Check health
    print("\nServer Health:")
    health = connector.check_health()
    print(f"Healthy: {health}")
    
    # Get tables
    print("\nTables:")
    tables = connector.get_tables()
    print(json.dumps(tables, indent=2))
    
    # Get schema for a table
    if tables:
        table = tables[0]
        print(f"\nSchema for table '{table}':")
        schema = connector.get_table_schema(table)
        print(json.dumps(schema, indent=2))
    
    # Execute a query
    print("\nExecuting query:")
    query = DataSourceQuery(
        source_type="erp",
        query_type=QueryType.SQL,
        query="SELECT * FROM products WHERE price > 100",
        parameters={}
    )
    result = connector.execute_query(query)
    print(json.dumps(result, indent=2))


def test_document_storage_connector(host: str, port: int, mock_mode: bool):
    """Test the Document Storage connector."""
    print("\n=== Testing Document Storage Connector ===")
    
    # Initialize the connector
    connector = DocumentStorageConnector(host=host, port=port, mock_mode=mock_mode)
    
    # Check server info
    print("\nServer Info:")
    info = connector.get_server_info()
    print(json.dumps(info, indent=2))
    
    # Check health
    print("\nServer Health:")
    health = connector.check_health()
    print(f"Healthy: {health}")
    
    # Get collections
    print("\nCollections:")
    collections = connector.get_collections()
    print(json.dumps(collections, indent=2))
    
    # Get schema for a collection
    if collections:
        collection = collections[0]
        print(f"\nSchema for collection '{collection}':")
        schema = connector.get_collection_schema(collection)
        print(json.dumps(schema, indent=2))
    
    # Execute a query
    print("\nExecuting query:")
    query = DataSourceQuery(
        source_type="document_storage",
        query_type=QueryType.MONGODB,
        query='{"price": {"$gt": 100}}',
        parameters={"collection": "products"}
    )
    result = connector.execute_query(query)
    print(json.dumps(result, indent=2))


def test_knowledge_graph_connector(host: str, port: int, mock_mode: bool):
    """Test the Knowledge Graph connector."""
    print("\n=== Testing Knowledge Graph Connector ===")
    
    # Initialize the connector
    connector = KnowledgeGraphConnector(host=host, port=port, mock_mode=mock_mode)
    
    # Check server info
    print("\nServer Info:")
    info = connector.get_server_info()
    print(json.dumps(info, indent=2))
    
    # Check health
    print("\nServer Health:")
    health = connector.check_health()
    print(f"Healthy: {health}")
    
    # Get namespaces
    print("\nNamespaces:")
    namespaces = connector.get_namespaces()
    print(json.dumps(namespaces, indent=2))
    
    # Get classes
    print("\nClasses:")
    classes = connector.get_classes()
    print(json.dumps(classes, indent=2))
    
    # Get properties for a class
    if classes:
        class_uri = classes[0]["class"]
        print(f"\nProperties for class '{class_uri}':")
        properties = connector.get_properties(class_uri)
        print(json.dumps(properties, indent=2))
    
    # Execute a query
    print("\nExecuting query:")
    query = DataSourceQuery(
        source_type="knowledge_graph",
        query_type=QueryType.SPARQL,
        query="""
        PREFIX product: <http://example.org/product#>
        SELECT ?product ?name ?price
        WHERE {
            ?product product:price ?price .
            ?product product:name ?name .
            FILTER (?price > 100)
        }
        """,
        parameters={}
    )
    result = connector.execute_query(query)
    print(json.dumps(result, indent=2))


def main():
    """Run the MCP test script."""
    parser = argparse.ArgumentParser(description="Test MCP servers and connectors")
    parser.add_argument("--host", type=str, default="localhost", help="Host where the servers are running")
    parser.add_argument("--erp-port", type=int, default=8001, help="Port for the ERP server")
    parser.add_argument("--doc-port", type=int, default=8002, help="Port for the Document Storage server")
    parser.add_argument("--kg-port", type=int, default=8003, help="Port for the Knowledge Graph server")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument("--test", type=str, choices=["erp", "doc", "kg", "all"], default="all", help="Which connector to test")
    
    args = parser.parse_args()
    
    try:
        if args.test == "erp" or args.test == "all":
            test_erp_connector(args.host, args.erp_port, args.mock)
        
        if args.test == "doc" or args.test == "all":
            test_document_storage_connector(args.host, args.doc_port, args.mock)
        
        if args.test == "kg" or args.test == "all":
            test_knowledge_graph_connector(args.host, args.kg_port, args.mock)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()