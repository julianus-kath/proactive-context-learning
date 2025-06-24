"""
MCP Knowledge Graph Connector implementation.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from crawling_agent.base_connector import BaseMCPConnector


class MCPKnowledgeGraphConnector(BaseMCPConnector):
    """
    MCP connector for the Knowledge Graph Server.
    
    This connector provides methods to interact with the Knowledge Graph Server via MCP.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8003/sse",
        server_name: str = "KnowledgeGraphServer",
    ):
        """
        Initialize the MCP Knowledge Graph Connector.

        Args:
            server_url: The URL of the Knowledge Graph Server (default: "http://localhost:8003/sse")
            server_name: The name of the server (default: "KnowledgeGraphServer")
        """
        super().__init__(server_url=server_url, server_name=server_name)
    
    async def query_nodes(
        self,
        node_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query nodes in the knowledge graph.
        
        Args:
            node_type: Filter by node type (optional)
            properties: Filter by node properties (optional)
            
        Returns:
            The matching nodes as a list of dictionaries
        """
        args = {}
        
        if node_type is not None:
            args["node_type"] = node_type
        
        if properties is not None:
            args["properties"] = properties
        
        result = await self.call_tool("query_nodes", args)
        return json.loads(result)
    
    async def query_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query relationships in the knowledge graph.
        
        Args:
            relationship_type: Filter by relationship type (optional)
            source_id: Filter by source node ID (optional)
            target_id: Filter by target node ID (optional)
            properties: Filter by relationship properties (optional)
            
        Returns:
            The matching relationships as a list of dictionaries
        """
        args = {}
        
        if relationship_type is not None:
            args["relationship_type"] = relationship_type
        
        if source_id is not None:
            args["source_id"] = source_id
        
        if target_id is not None:
            args["target_id"] = target_id
        
        if properties is not None:
            args["properties"] = properties
        
        result = await self.call_tool("query_relationships", args)
        return json.loads(result)
    
    async def get_node_types(self) -> List[str]:
        """
        Get all node types in the knowledge graph.
        
        Returns:
            A list of node types
        """
        result = await self.call_tool("get_node_types", {})
        return json.loads(result)["node_types"]
    
    async def get_relationship_types(self) -> List[str]:
        """
        Get all relationship types in the knowledge graph.
        
        Returns:
            A list of relationship types
        """
        result = await self.call_tool("get_relationship_types", {})
        return json.loads(result)["relationship_types"]


async def main():
    """Example usage of the MCP Knowledge Graph Connector."""
    async with MCPKnowledgeGraphConnector() as connector:
        # Get all node types
        node_types = await connector.get_node_types()
        print("Node types:", node_types)
        
        # Get all relationship types
        rel_types = await connector.get_relationship_types()
        print("Relationship types:", rel_types)
        
        # Query all nodes
        nodes = await connector.query_nodes()
        print("All nodes:", nodes)
        
        # Query all relationships
        relationships = await connector.query_relationships()
        print("All relationships:", relationships)


if __name__ == "__main__":
    asyncio.run(main())