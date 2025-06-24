"""
Knowledge Graph Server implementation using MCP.
"""
import json
import os
from typing import Any, Dict, List, Optional, Union

from crawling_agent.base_server import BaseMCPServer
from crawling_agent.custom_resource import CustomResource
from fastmcp.resources import Resource


class KnowledgeGraphServer(BaseMCPServer):
    """
    Knowledge Graph Server that exposes graph query tools over MCP.
    
    This server provides tools to query a knowledge graph.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8003,
    ):
        """
        Initialize the Knowledge Graph Server.

        Args:
            host: Host to bind to (default: "0.0.0.0")
            port: Port to listen on (default: 8003)
        """
        super().__init__(
            name="KnowledgeGraphServer",
            host=host,
            port=port,
            description="Knowledge Graph Server providing graph query capabilities over MCP",
        )
        
        # Mock graph data for demonstration
        self.graph_data = self._initialize_mock_graph()
        
        # Register resources
        self._register_resources()
        
        # Register tools
        self._register_tools()
    
    def _initialize_mock_graph(self) -> Dict[str, Any]:
        """
        Initialize mock graph data for demonstration.
        
        Returns:
            A dictionary containing mock graph data
        """
        return {
            "nodes": [
                {"id": "product1", "type": "Product", "properties": {"name": "Product A", "price": 100}},
                {"id": "product2", "type": "Product", "properties": {"name": "Product B", "price": 200}},
                {"id": "customer1", "type": "Customer", "properties": {"name": "Customer X", "email": "x@example.com"}},
                {"id": "customer2", "type": "Customer", "properties": {"name": "Customer Y", "email": "y@example.com"}},
                {"id": "supplier1", "type": "Supplier", "properties": {"name": "Supplier P", "country": "USA"}},
                {"id": "supplier2", "type": "Supplier", "properties": {"name": "Supplier Q", "country": "Canada"}}
            ],
            "relationships": [
                {"source": "customer1", "target": "product1", "type": "PURCHASED", "properties": {"date": "2023-01-15"}},
                {"source": "customer1", "target": "product2", "type": "VIEWED", "properties": {"date": "2023-01-10"}},
                {"source": "customer2", "target": "product2", "type": "PURCHASED", "properties": {"date": "2023-02-20"}},
                {"source": "supplier1", "target": "product1", "type": "SUPPLIES", "properties": {"since": "2022-05-01"}},
                {"source": "supplier2", "target": "product2", "type": "SUPPLIES", "properties": {"since": "2022-06-15"}}
            ]
        }
    
    def _register_resources(self):
        """Register resources with the MCP server."""
        # Load the schema from the JSON file
        schema_path = os.path.join(
            os.path.dirname(__file__), 
            "resources", 
            "knowledge_graph_schema.json"
        )
        
        with open(schema_path, "r") as f:
            schema = json.load(f)
        
        # Create the resource
        graph_resource = CustomResource(
            name="knowledge_graph",
            description="Knowledge graph schema and metadata",
            schema=schema,
        )
        
        # Register the resource with the MCP server
        self.mcp.add_resource(graph_resource)
        
        # Populate the resource with graph metadata
        self._populate_resource(graph_resource)
    
    def _populate_resource(self, resource: Resource):
        """
        Populate the resource with graph metadata.
        
        Args:
            resource: The resource to populate
        """
        # Extract node types and their properties
        node_types = {}
        for node in self.graph_data["nodes"]:
            node_type = node["type"]
            if node_type not in node_types:
                node_types[node_type] = {"properties": {}}
            
            for prop_name, prop_value in node["properties"].items():
                if prop_name not in node_types[node_type]["properties"]:
                    node_types[node_type]["properties"][prop_name] = type(prop_value).__name__
        
        # Extract relationship types and their properties
        rel_types = {}
        for rel in self.graph_data["relationships"]:
            rel_type = rel["type"]
            if rel_type not in rel_types:
                rel_types[rel_type] = {
                    "source": None,
                    "target": None,
                    "properties": {}
                }
            
            # Find source and target node types
            source_id = rel["source"]
            target_id = rel["target"]
            source_type = next((node["type"] for node in self.graph_data["nodes"] if node["id"] == source_id), None)
            target_type = next((node["type"] for node in self.graph_data["nodes"] if node["id"] == target_id), None)
            
            rel_types[rel_type]["source"] = source_type
            rel_types[rel_type]["target"] = target_type
            
            for prop_name, prop_value in rel.get("properties", {}).items():
                if prop_name not in rel_types[rel_type]["properties"]:
                    rel_types[rel_type]["properties"][prop_name] = type(prop_value).__name__
        
        # Prepare the nodes data
        nodes_data = []
        for node_type, info in node_types.items():
            properties = []
            for prop_name, prop_type in info["properties"].items():
                properties.append({
                    "name": prop_name,
                    "type": prop_type,
                    "description": f"Property {prop_name} of type {prop_type} for node type {node_type}"
                })
            
            nodes_data.append({
                "type": node_type,
                "properties": properties
            })
        
        # Prepare the relationships data
        relationships_data = []
        for rel_type, info in rel_types.items():
            properties = []
            for prop_name, prop_type in info["properties"].items():
                properties.append({
                    "name": prop_name,
                    "type": prop_type,
                    "description": f"Property {prop_name} of type {prop_type} for relationship type {rel_type}"
                })
            
            relationships_data.append({
                "type": rel_type,
                "source": info["source"],
                "target": info["target"],
                "properties": properties
            })
        
        # Update the resource with the graph metadata
        resource.update({
            "nodes": nodes_data,
            "relationships": relationships_data
        })
    
    def _register_tools(self):
        """Register tools with the MCP server."""
        
        @self.mcp.tool()
        def query_nodes(node_type: Optional[str] = None, properties: Optional[Dict[str, Any]] = None) -> str:
            """
            Query nodes in the knowledge graph.
            
            Args:
                node_type: Filter by node type (optional)
                properties: Filter by node properties (optional)
                
            Returns:
                The matching nodes as a JSON string
            """
            try:
                # Get all nodes
                nodes = self.graph_data["nodes"]
                
                # Filter by node type if specified
                if node_type:
                    nodes = [node for node in nodes if node["type"] == node_type]
                
                # Filter by properties if specified
                if properties:
                    filtered_nodes = []
                    for node in nodes:
                        match = True
                        for key, value in properties.items():
                            if key not in node["properties"] or node["properties"][key] != value:
                                match = False
                                break
                        
                        if match:
                            filtered_nodes.append(node)
                    
                    nodes = filtered_nodes
                
                return json.dumps(nodes)
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def query_relationships(
            relationship_type: Optional[str] = None,
            source_id: Optional[str] = None,
            target_id: Optional[str] = None,
            properties: Optional[Dict[str, Any]] = None
        ) -> str:
            """
            Query relationships in the knowledge graph.
            
            Args:
                relationship_type: Filter by relationship type (optional)
                source_id: Filter by source node ID (optional)
                target_id: Filter by target node ID (optional)
                properties: Filter by relationship properties (optional)
                
            Returns:
                The matching relationships as a JSON string
            """
            try:
                # Get all relationships
                relationships = self.graph_data["relationships"]
                
                # Filter by relationship type if specified
                if relationship_type:
                    relationships = [rel for rel in relationships if rel["type"] == relationship_type]
                
                # Filter by source node ID if specified
                if source_id:
                    relationships = [rel for rel in relationships if rel["source"] == source_id]
                
                # Filter by target node ID if specified
                if target_id:
                    relationships = [rel for rel in relationships if rel["target"] == target_id]
                
                # Filter by properties if specified
                if properties:
                    filtered_rels = []
                    for rel in relationships:
                        match = True
                        for key, value in properties.items():
                            if "properties" not in rel or key not in rel["properties"] or rel["properties"][key] != value:
                                match = False
                                break
                        
                        if match:
                            filtered_rels.append(rel)
                    
                    relationships = filtered_rels
                
                return json.dumps(relationships)
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def get_node_types() -> str:
            """
            Get all node types in the knowledge graph.
            
            Returns:
                A JSON string containing the list of node types
            """
            try:
                # Extract unique node types
                node_types = set(node["type"] for node in self.graph_data["nodes"])
                
                return json.dumps({"node_types": list(node_types)})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def get_relationship_types() -> str:
            """
            Get all relationship types in the knowledge graph.
            
            Returns:
                A JSON string containing the list of relationship types
            """
            try:
                # Extract unique relationship types
                rel_types = set(rel["type"] for rel in self.graph_data["relationships"])
                
                return json.dumps({"relationship_types": list(rel_types)})
            except Exception as e:
                return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Create and run the server
    server = KnowledgeGraphServer()
    server.run(transport="sse")