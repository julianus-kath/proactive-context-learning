"""
Custom resource implementation for MCP servers.
"""
from typing import Any, Dict, Optional

from fastmcp.resources import Resource


class CustomResource(Resource):
    """
    Custom resource implementation that extends the abstract Resource class.
    
    This class implements the required read method and provides a simple
    way to store and retrieve resource data.
    """

    def __init__(
        self,
        name: str,
        description: str,
        schema: Dict[str, Any],
        uri: str = "https://example.com/resource",
    ):
        """
        Initialize the custom resource.
        
        Args:
            name: The name of the resource
            description: A description of the resource
            schema: The JSON schema for the resource
            uri: The URI of the resource (default: "https://example.com/resource")
        """
        super().__init__(name=name, description=description, schema=schema, uri=uri)
        self._data = {}
    
    def read(self) -> Dict[str, Any]:
        """
        Read the resource data.
        
        Returns:
            The resource data
        """
        return self._data
    
    def update(self, data: Dict[str, Any]):
        """
        Update the resource data.
        
        Args:
            data: The new resource data
        """
        self._data = data