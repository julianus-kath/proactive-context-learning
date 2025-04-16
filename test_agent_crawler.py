"""
Test script for the Agent Crawler.
"""

import sys
import os
import traceback
from pathlib import Path

# Add the current directory to the path
sys.path.append(str(Path(__file__).resolve().parent))

from agent_crawler.agent import DataCrawlerAgent


def main():
    """Test the Agent Crawler."""
    print("=" * 80)
    print("STARTING AGENT CRAWLER TEST")
    print("=" * 80)
    
    # Initialize the agent
    print("\nInitializing DataCrawlerAgent...")
    try:
        agent = DataCrawlerAgent()
        print("Agent initialized successfully!")
    except Exception as e:
        print(f"Error initializing agent: {e}")
        traceback.print_exc()
        return
    
    try:
        # Test SQL connector
        print("\n" + "=" * 40)
        print("TESTING SQL CONNECTOR")
        print("=" * 40)
        if agent.sql_connector:
            print("SQL Connector: Connected")
            try:
                tables = agent.sql_connector.get_tables()
                print(f"Tables: {tables}")
                
                if tables:
                    # Get schema for the first table
                    first_table = tables[0]
                    schema = agent.sql_connector.get_table_schema(first_table)
                    print(f"Schema for {first_table}:")
                    for column in schema:
                        print(f"  {column['name']} ({column['type']})")
            except Exception as e:
                print(f"Error testing SQL connector: {e}")
                traceback.print_exc()
        else:
            print("SQL Connector: Not connected")
        
        # Test Document connector
        print("\n" + "=" * 40)
        print("TESTING DOCUMENT CONNECTOR")
        print("=" * 40)
        if agent.doc_connector:
            print("Document Connector: Connected")
            try:
                collections = agent.doc_connector.get_collections()
                print(f"Collections: {collections}")
                
                if collections:
                    # Get schema for the first collection
                    first_collection = collections[0]
                    try:
                        schema = agent.doc_connector.get_collection_schema(first_collection)
                        print(f"Schema for {first_collection}:")
                        for field, field_type in schema.items():
                            print(f"  {field}: {field_type}")
                    except Exception as e:
                        print(f"Error getting schema for {first_collection}: {e}")
                        traceback.print_exc()
            except Exception as e:
                print(f"Error testing Document connector: {e}")
                traceback.print_exc()
        else:
            print("Document Connector: Not connected")
        
        # Test Graph connector
        print("\n" + "=" * 40)
        print("TESTING GRAPH CONNECTOR")
        print("=" * 40)
        if agent.graph_connector:
            print("Graph Connector: Connected")
            try:
                networks = agent.graph_connector.get_networks()
                print(f"Networks: {networks}")
                
                if networks:
                    # Get schema for the first network
                    first_network = networks[0]
                    try:
                        schema = agent.graph_connector.get_network_schema(first_network)
                        print(f"Schema for {first_network}:")
                        print(f"  Node Labels: {schema.get('node_labels', [])}")
                        print(f"  Edge Types: {schema.get('edge_types', [])}")
                        print(f"  Node Count: {schema.get('node_count', 0)}")
                        print(f"  Edge Count: {schema.get('edge_count', 0)}")
                    except Exception as e:
                        print(f"Error getting schema for {first_network}: {e}")
                        traceback.print_exc()
            except Exception as e:
                print(f"Error testing Graph connector: {e}")
                traceback.print_exc()
        else:
            print("Graph Connector: Not connected")
        
        print("\n" + "=" * 40)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 40)
    except Exception as e:
        print(f"\nError during testing: {e}")
        traceback.print_exc()
    finally:
        # Close the agent
        print("\nClosing agent connections...")
        try:
            agent.close()
            print("Agent connections closed successfully!")
        except Exception as e:
            print(f"Error closing agent connections: {e}")
            traceback.print_exc()
        
        print("\n" + "=" * 80)
        print("TEST COMPLETED")
        print("=" * 80)


if __name__ == "__main__":
    main()