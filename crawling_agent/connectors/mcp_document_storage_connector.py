"""
MCP Document Storage Connector implementation.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from crawling_agent.base_connector import BaseMCPConnector


class MCPDocumentStorageConnector(BaseMCPConnector):
    """
    MCP connector for the Document Storage Server.
    
    This connector provides methods to interact with the Document Storage Server via MCP.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8002/sse",
        server_name: str = "DocumentStorageServer",
    ):
        """
        Initialize the MCP Document Storage Connector.

        Args:
            server_url: The URL of the Document Storage Server (default: "http://localhost:8002/sse")
            server_name: The name of the server (default: "DocumentStorageServer")
        """
        super().__init__(server_url=server_url, server_name=server_name)
    
    async def find_documents(
        self,
        collection: str,
        query: Dict[str, Any],
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find documents in a collection that match a query.
        
        Args:
            collection: The name of the collection to query
            query: A MongoDB-style query dictionary
            limit: Maximum number of documents to return (optional)
            
        Returns:
            The matching documents as a list of dictionaries
        """
        args = {
            "collection": collection,
            "query": query
        }
        
        if limit is not None:
            args["limit"] = limit
        
        result = await self.call_tool("find_documents", args)
        return json.loads(result)
    
    async def list_collections(self) -> List[str]:
        """
        List all collections in the document storage.
        
        Returns:
            A list of collection names
        """
        result = await self.call_tool("list_collections", {})
        return json.loads(result)["collections"]
    
    async def get_collection_info(self, collection: str) -> Dict[str, Any]:
        """
        Get information about a specific collection.
        
        Args:
            collection: The name of the collection
            
        Returns:
            Information about the collection as a dictionary
        """
        result = await self.call_tool("get_collection_info", {"collection": collection})
        return json.loads(result)


async def main():
    """Example usage of the MCP Document Storage Connector."""
    async with MCPDocumentStorageConnector() as connector:
        # List all collections
        collections = await connector.list_collections()
        print("Collections:", collections)
        
        if collections:
            # Get info about the first collection
            collection_info = await connector.get_collection_info(collections[0])
            print(f"Info for {collections[0]}:", collection_info)
            
            # Find documents in the first collection
            documents = await connector.find_documents(collections[0], {}, limit=5)
            print(f"Documents in {collections[0]} (limited to 5):", documents)


if __name__ == "__main__":
    asyncio.run(main())