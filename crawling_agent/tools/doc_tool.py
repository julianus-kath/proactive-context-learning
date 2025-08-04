"""
Document Tool implementation for the crawling agent.
"""
import os
import json
import logging
import aiohttp
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


class DocTool:
    """
    Tool for querying the document storage system.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the document tool.
        
        Args:
            config: Optional configuration dictionary with the following keys:
                - host: Host where the Document Store API is running
                - port: Port of the Document Store API
        """
        self.config = config or {}
        
        # Get configuration from environment variables or use defaults
        self.host = self.config.get("host") or os.environ.get("DOC_HOST", "localhost")
        self.port = self.config.get("port") or os.environ.get("DOC_PORT", "8002")
        
        # Build the base URL
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Initialize session to None, will be created when needed
        self._session = None
        
        logger.info(f"Initialized document tool with API at {self.base_url}")
    
    async def _ensure_session(self):
        """Ensure we have an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the document store (collections and sample documents).
        
        Returns:
            Dictionary containing document store metadata
        """
        await self._ensure_session()
        
        try:
            async with self._session.get(f"{self.base_url}/metadata") as response:
                response.raise_for_status()
                metadata = await response.json()
                logger.info(f"Retrieved metadata for {len(metadata.get('collections', []))} collections")
                return metadata
        except Exception as e:
            logger.error(f"Error getting metadata: {str(e)}")
            raise
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a document query.
        
        Args:
            parameters: Dictionary with the following keys:
                - query: Query to execute
                - collection: Collection to query
                - limit: Maximum number of documents to return (optional)
                - skip: Number of documents to skip (optional)
            
        Returns:
            The query results
        """
        query = parameters.get("query")
        collection = parameters.get("collection")
        
        if not query:
            error_msg = "Query is required"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not collection:
            error_msg = "Collection is required"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Get optional parameters
        limit = parameters.get("limit", 10)
        skip = parameters.get("skip", 0)
        
        await self._ensure_session()
        
        try:
            logger.info(f"Executing document query: {query} on collection: {collection}")
            
            async with self._session.post(
                f"{self.base_url}/query",
                json={
                    "query": query,
                    "collection": collection,
                    "limit": limit,
                    "skip": skip
                }
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Log the result summary
                document_count = len(result.get("data", []))
                logger.info(f"Query executed successfully. Retrieved {document_count} documents.")
                
                if document_count > 0:
                    # Log a sample of the data (first document)
                    logger.info("Sample data (first document):")
                    logger.info(json.dumps(result["data"][0], indent=2))
                
                return {
                    "source_tool": "doc",
                    "query_text": query,
                    "raw_result": result.get("data", []),
                    "metadata": {
                        "collection": collection,
                        "count": document_count,
                        "limit": limit,
                        "skip": skip
                    }
                }
                
        except Exception as e:
            logger.error(f"Error executing document query: {str(e)}")
            raise
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "doc"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Execute queries against the document storage system. "
            "This tool can be used to retrieve unstructured or semi-structured "
            "documents, such as product descriptions, customer reviews, "
            "support tickets, and other document-based data."
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool's parameters.
        
        Returns:
            JSON schema for the parameters
        """
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query to execute"
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of documents to return",
                    "default": 10
                },
                "skip": {
                    "type": "integer",
                    "description": "Number of documents to skip",
                    "default": 0
                }
            },
            "required": ["query", "collection"]
        }