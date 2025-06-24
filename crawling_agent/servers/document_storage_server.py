"""
Document Storage Server implementation using MCP.
"""
import json
import os
from typing import Any, Dict, List, Optional, Union

from crawling_agent.base_server import BaseMCPServer
from crawling_agent.custom_resource import CustomResource
from fastmcp.resources import Resource


class DocumentStorageServer(BaseMCPServer):
    """
    Document Storage Server that exposes MongoDB-style query tools over MCP.
    
    This server loads documents from a JSON file and provides tools to query them.
    """

    def __init__(
        self,
        json_path: str,
        host: str = "0.0.0.0",
        port: int = 8002,
    ):
        """
        Initialize the Document Storage Server.

        Args:
            json_path: Path to the JSON file containing the documents
            host: Host to bind to (default: "0.0.0.0")
            port: Port to listen on (default: 8002)
        """
        super().__init__(
            name="DocumentStorageServer",
            host=host,
            port=port,
            description="Document Storage Server providing MongoDB-style query capabilities over MCP",
        )
        
        self.json_path = json_path
        self.documents = self._load_documents()
        
        # Register resources
        self._register_resources()
        
        # Register tools
        self._register_tools()
    
    def _load_documents(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load documents from the JSON file.
        
        Returns:
            A dictionary mapping collection names to lists of documents
        """
        with open(self.json_path, "r") as f:
            return json.load(f)
    
    def _register_resources(self):
        """Register resources with the MCP server."""
        # Load the schema from the JSON file
        schema_path = os.path.join(
            os.path.dirname(__file__), 
            "resources", 
            "document_storage_schema.json"
        )
        
        with open(schema_path, "r") as f:
            schema = json.load(f)
        
        # Create the resource
        doc_resource = CustomResource(
            name="document_storage",
            description="Document storage collections and metadata",
            schema=schema,
        )
        
        # Register the resource with the MCP server
        self.mcp.add_resource(doc_resource)
        
        # Populate the resource with actual collection metadata
        self._populate_resource(doc_resource)
    
    def _populate_resource(self, resource: Resource):
        """
        Populate the resource with actual collection metadata.
        
        Args:
            resource: The resource to populate
        """
        # Prepare the collections data
        collections_data = []
        
        for collection_name, documents in self.documents.items():
            if not documents:
                continue
                
            # Get a sample document to extract fields
            sample_doc = documents[0]
            
            # Extract fields from the sample document
            fields = []
            for field_name, field_value in sample_doc.items():
                field_type = type(field_value).__name__
                fields.append({
                    "name": field_name,
                    "type": field_type,
                    "description": f"Field {field_name} of type {field_type} in collection {collection_name}"
                })
            
            collections_data.append({
                "name": collection_name,
                "description": f"Collection of {collection_name} documents",
                "fields": fields
            })
        
        # Update the resource with the collections data
        resource.update({"collections": collections_data})
    
    def _register_tools(self):
        """Register tools with the MCP server."""
        
        @self.mcp.tool()
        def find_documents(collection: str, query: Dict[str, Any], limit: Optional[int] = None) -> str:
            """
            Find documents in a collection that match a query.
            
            Args:
                collection: The name of the collection to query
                query: A MongoDB-style query dictionary
                limit: Maximum number of documents to return (optional)
                
            Returns:
                The matching documents as a JSON string
            """
            try:
                if collection not in self.documents:
                    return json.dumps({"error": f"Collection '{collection}' not found"})
                
                # Get the documents in the collection
                docs = self.documents[collection]
                
                # Filter the documents based on the query
                results = []
                for doc in docs:
                    match = True
                    for key, value in query.items():
                        if key not in doc or doc[key] != value:
                            match = False
                            break
                    
                    if match:
                        results.append(doc)
                
                # Apply the limit if specified
                if limit is not None:
                    results = results[:limit]
                
                return json.dumps(results)
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def list_collections() -> str:
            """
            List all collections in the document storage.
            
            Returns:
                A JSON string containing the list of collections
            """
            try:
                collections = list(self.documents.keys())
                return json.dumps({"collections": collections})
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @self.mcp.tool()
        def get_collection_info(collection: str) -> str:
            """
            Get information about a specific collection.
            
            Args:
                collection: The name of the collection
                
            Returns:
                Information about the collection as a JSON string
            """
            try:
                if collection not in self.documents:
                    return json.dumps({"error": f"Collection '{collection}' not found"})
                
                # Get the documents in the collection
                docs = self.documents[collection]
                
                # Get a sample document to extract fields
                sample_doc = docs[0] if docs else {}
                
                # Extract fields from the sample document
                fields = []
                for field_name, field_value in sample_doc.items():
                    field_type = type(field_value).__name__
                    fields.append({
                        "name": field_name,
                        "type": field_type
                    })
                
                return json.dumps({
                    "collection": collection,
                    "document_count": len(docs),
                    "fields": fields
                })
            except Exception as e:
                return json.dumps({"error": str(e)})


if __name__ == "__main__":
    # Path to the JSON file containing the documents
    json_path = "/Users/juli/Desktop/Studies/Master/Year 2/Semester 2/Master Thesis/code/mongodb_data.json"
    
    # Create and run the server
    server = DocumentStorageServer(json_path=json_path)
    server.run(transport="sse")