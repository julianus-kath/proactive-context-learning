"""
Simple test script for the connectors.
"""

import os
import sys
from pathlib import Path

# Add the current directory to the path
sys.path.append(str(Path(__file__).resolve().parent))

from agent_crawler.connectors.sql_connector import SQLConnector
from agent_crawler.connectors.docs_connector import DocumentConnector
from agent_crawler.connectors.graph_connector import GraphConnector

# Paths
SQLITE_DB_PATH = str(Path(__file__).resolve().parent / "synthetic_data.db")
DOCUMENT_STORE_PATH = str(Path(__file__).resolve().parent / "extended_data" / "documents")
GRAPH_DB_PATH = str(Path(__file__).resolve().parent / "extended_data" / "graphs")

def main():
    """Run simple tests for the connectors."""
    print("=" * 80)
    print("SIMPLE CONNECTOR TESTS")
    print("=" * 80)
    
    # Test SQL connector
    print("\n" + "=" * 40)
    print("TESTING SQL CONNECTOR")
    print("=" * 40)
    print(f"SQLite DB Path: {SQLITE_DB_PATH}")
    print(f"Exists: {os.path.exists(SQLITE_DB_PATH)}")
    
    try:
        sql_connector = SQLConnector(f"sqlite:///{SQLITE_DB_PATH}")
        print("SQL Connector initialized successfully!")
        
        tables = sql_connector.get_tables()
        print(f"Tables: {tables}")
        
        if tables:
            first_table = tables[0]
            schema = sql_connector.get_table_schema(first_table)
            print(f"Schema for {first_table}:")
            for column in schema:
                print(f"  {column['name']} ({column['type']})")
        
        sql_connector.close()
    except Exception as e:
        print(f"Error testing SQL connector: {e}")
    
    # Test Document connector
    print("\n" + "=" * 40)
    print("TESTING DOCUMENT CONNECTOR")
    print("=" * 40)
    print(f"Document Store Path: {DOCUMENT_STORE_PATH}")
    print(f"Exists: {os.path.exists(DOCUMENT_STORE_PATH)}")
    print(f"Contents: {os.listdir(DOCUMENT_STORE_PATH)}")
    
    try:
        doc_connector = DocumentConnector(DOCUMENT_STORE_PATH)
        print("Document Connector initialized successfully!")
        
        collections = doc_connector.get_collections()
        print(f"Collections: {collections}")
        
        if collections:
            first_collection = collections[0]
            try:
                schema = doc_connector.get_collection_schema(first_collection)
                print(f"Schema for {first_collection}:")
                for field, field_type in schema.items():
                    print(f"  {field}: {field_type}")
            except Exception as e:
                print(f"Error getting schema for {first_collection}: {e}")
    except Exception as e:
        print(f"Error testing Document connector: {e}")
    
    # Test Graph connector
    print("\n" + "=" * 40)
    print("TESTING GRAPH CONNECTOR")
    print("=" * 40)
    print(f"Graph DB Path: {GRAPH_DB_PATH}")
    print(f"Exists: {os.path.exists(GRAPH_DB_PATH)}")
    print(f"Contents: {os.listdir(GRAPH_DB_PATH)}")
    
    try:
        graph_connector = GraphConnector(GRAPH_DB_PATH)
        print("Graph Connector initialized successfully!")
        
        networks = graph_connector.get_networks()
        print(f"Networks: {networks}")
        
        if networks:
            first_network = networks[0]
            try:
                schema = graph_connector.get_network_schema(first_network)
                print(f"Schema for {first_network}:")
                print(f"  Node Labels: {schema.get('node_labels', [])}")
                print(f"  Edge Types: {schema.get('edge_types', [])}")
                print(f"  Node Count: {schema.get('node_count', 0)}")
                print(f"  Edge Count: {schema.get('edge_count', 0)}")
            except Exception as e:
                print(f"Error getting schema for {first_network}: {e}")
    except Exception as e:
        print(f"Error testing Graph connector: {e}")
    
    print("\n" + "=" * 80)
    print("TESTS COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    main()