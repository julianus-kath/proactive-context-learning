"""
Example client that demonstrates how to use all three MCP connectors.
"""
import asyncio
import json
from typing import Any, Dict, List

from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector


async def demo_erp_connector():
    """Demonstrate the ERP connector."""
    print("\n=== ERP Connector Demo ===\n")
    
    async with MCPERPConnector() as connector:
        # List all tables
        tables = await connector.list_tables()
        print("Tables:", tables)
        
        if tables:
            # Get the schema for the first table
            schema = await connector.get_table_schema(tables[0])
            print(f"Schema for {tables[0]}:", json.dumps(schema, indent=2))
            
            # Execute a simple query
            query = f"SELECT * FROM {tables[0]} LIMIT 3"
            results = await connector.execute_sql_query(query)
            print(f"Query results for '{query}':", json.dumps(results, indent=2))


async def demo_document_storage_connector():
    """Demonstrate the Document Storage connector."""
    print("\n=== Document Storage Connector Demo ===\n")
    
    async with MCPDocumentStorageConnector() as connector:
        # List all collections
        collections = await connector.list_collections()
        print("Collections:", collections)
        
        if collections:
            # Get info about the first collection
            collection_info = await connector.get_collection_info(collections[0])
            print(f"Info for {collections[0]}:", json.dumps(collection_info, indent=2))
            
            # Find documents in the first collection
            documents = await connector.find_documents(collections[0], {}, limit=3)
            print(f"Documents in {collections[0]} (limited to 3):", json.dumps(documents, indent=2))


async def demo_knowledge_graph_connector():
    """Demonstrate the Knowledge Graph connector."""
    print("\n=== Knowledge Graph Connector Demo ===\n")
    
    async with MCPKnowledgeGraphConnector() as connector:
        # Get all node types
        node_types = await connector.get_node_types()
        print("Node types:", node_types)
        
        # Get all relationship types
        rel_types = await connector.get_relationship_types()
        print("Relationship types:", rel_types)
        
        # Query all nodes of a specific type (if available)
        if node_types:
            nodes = await connector.query_nodes(node_type=node_types[0])
            print(f"Nodes of type {node_types[0]}:", json.dumps(nodes, indent=2))
        
        # Query all relationships of a specific type (if available)
        if rel_types:
            relationships = await connector.query_relationships(relationship_type=rel_types[0])
            print(f"Relationships of type {rel_types[0]}:", json.dumps(relationships, indent=2))


async def main():
    """Run all connector demos."""
    try:
        await demo_erp_connector()
    except Exception as e:
        print(f"Error in ERP connector demo: {e}")
    
    try:
        await demo_document_storage_connector()
    except Exception as e:
        print(f"Error in Document Storage connector demo: {e}")
    
    try:
        await demo_knowledge_graph_connector()
    except Exception as e:
        print(f"Error in Knowledge Graph connector demo: {e}")


if __name__ == "__main__":
    asyncio.run(main())