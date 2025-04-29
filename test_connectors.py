"""
Test script for the connectors.
"""

import os
import sys
import json
from pathlib import Path

# Add the current directory to the path
sys.path.append(str(Path(__file__).resolve().parent))

print("Starting test_connectors.py...")

from agent_crawler.connectors.sql_connector import SQLConnector
from agent_crawler.connectors.docs_connector import DocumentConnector
from agent_crawler.connectors.graph_connector import GraphConnector

print("Imported connectors successfully!")

def main():
    """Test the connectors."""
    # Paths
    base_dir = Path(__file__).resolve().parent
    sqlite_db_path = base_dir / "synthetic_data.db"
    document_store_path = base_dir / "extended_data" / "documents"
    graph_db_path = base_dir / "extended_data" / "graphs"
    
    # Print paths
    print("Paths:")
    print(f"  Base directory: {base_dir}")
    print(f"  SQLite database: {sqlite_db_path} (exists: {sqlite_db_path.exists()})")
    print(f"  Document store: {document_store_path} (exists: {document_store_path.exists()})")
    print(f"  Graph database: {graph_db_path} (exists: {graph_db_path.exists()})")
    
    # Create test data if it doesn't exist
    if not document_store_path.exists():
        document_store_path.mkdir(parents=True, exist_ok=True)
    
    if not (document_store_path / "test_collection.json").exists():
        with open(document_store_path / "test_collection.json", "w") as f:
            json.dump([{"id": 1, "name": "Test Document", "value": 42}], f)
    
    if not graph_db_path.exists():
        graph_db_path.mkdir(parents=True, exist_ok=True)
    
    if not (graph_db_path / "test_network.json").exists():
        with open(graph_db_path / "test_network.json", "w") as f:
            json.dump({
                "nodes": [
                    {"id": "1", "labels": ["Person"], "properties": {"name": "John Doe", "age": 30}},
                    {"id": "2", "labels": ["Person"], "properties": {"name": "Jane Smith", "age": 28}}
                ],
                "edges": [
                    {"source": "1", "target": "2", "type": "KNOWS", "properties": {"since": 2020}}
                ]
            }, f)
    
    if not sqlite_db_path.exists():
        import sqlite3
        conn = sqlite3.connect(sqlite_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value REAL)")
        cursor.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("Test Item", 42.0))
        conn.commit()
        conn.close()
    
    # Test SQL connector
    print("\nTesting SQL connector...")
    try:
        sql_connector = SQLConnector(f"sqlite:///{sqlite_db_path}")
        print("  SQL connector initialized successfully")
        
        tables = sql_connector.get_tables()
        print(f"  Tables: {tables}")
        
        if tables:
            first_table = tables[0]
            schema = sql_connector.get_table_schema(first_table)
            print(f"  Schema for {first_table}:")
            for column in schema:
                print(f"    {column['name']} ({column['type']})")
            
            # Test query
            results = sql_connector.query(f"SELECT * FROM {first_table}")
            print(f"  Query results: {results}")
        
        sql_connector.close()
        print("  SQL connector test completed successfully")
    except Exception as e:
        print(f"  Error testing SQL connector: {e}")
    
    # Test Document connector
    print("\nTesting Document connector...")
    try:
        doc_connector = DocumentConnector(str(document_store_path))
        print("  Document connector initialized successfully")
        
        collections = doc_connector.get_collections()
        print(f"  Collections: {collections}")
        
        if collections:
            first_collection = collections[0]
            schema = doc_connector.get_collection_schema(first_collection)
            print(f"  Schema for {first_collection}: {schema}")
            
            # Test query
            results = doc_connector.query_collection(first_collection)
            print(f"  Query results: {results}")
        
        print("  Document connector test completed successfully")
    except Exception as e:
        print(f"  Error testing Document connector: {e}")
    
    # Test Graph connector
    print("\nTesting Graph connector...")
    try:
        graph_connector = GraphConnector(str(graph_db_path))
        print("  Graph connector initialized successfully")
        
        networks = graph_connector.get_networks()
        print(f"  Networks: {networks}")
        
        if networks:
            first_network = networks[0]
            schema = graph_connector.get_network_schema(first_network)
            print(f"  Schema for {first_network}: {schema}")
            
            # Test query
            nodes = graph_connector.get_nodes(first_network)
            print(f"  Nodes: {nodes}")
            
            edges = graph_connector.get_edges(first_network)
            print(f"  Edges: {edges}")
        
        print("  Graph connector test completed successfully")
    except Exception as e:
        print(f"  Error testing Graph connector: {e}")
    
    print("\nAll connector tests completed")

if __name__ == "__main__":
    main()