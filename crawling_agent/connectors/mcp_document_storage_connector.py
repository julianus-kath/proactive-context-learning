"""
Document Storage Connector for executing MongoDB queries against the Document Storage MCP server.
"""
import time
import requests
import json
from typing import Dict, List, Any, Optional, Union

from crawling_agent.connectors.base_connector import BaseMCPConnector
from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest


class DocumentStorageConnector(BaseMCPConnector):
    """
    Connector for crawling data from a document storage system using MongoDB queries via MCP.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8002,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the Document Storage connector.
        
        Args:
            host: Host where the Document Storage MCP server is running
            port: Port where the Document Storage MCP server is running
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="document_storage",
            host=host,
            port=port,
            config_path=config_path,
            mock_mode=mock_mode
        )
    
    def get_collections(self) -> List[str]:
        """
        Get list of collections in the document database.
        
        Returns:
            List of collection names
        """
        try:
            response = requests.get(f"{self.base_url}/collections")
            response.raise_for_status()
            return response.json().get("collections", [])
        except Exception as e:
            self.logger.error(f"Error getting collections: {str(e)}")
            if self.mock_mode:
                return ["products", "orders", "customers"]
            else:
                raise
    
    def get_collection_schema(self, collection_name: str) -> Dict[str, Any]:
        """
        Get schema for a specific collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary containing the collection schema
        """
        try:
            response = requests.get(f"{self.base_url}/schema/{collection_name}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting schema for collection {collection_name}: {str(e)}")
            if self.mock_mode:
                return {"collection": collection_name, "schema": {}}
            else:
                raise
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a MongoDB query against the document database via MCP.
        
        Args:
            query: The DataSourceQuery object containing the MongoDB query and parameters
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.MONGODB:
            raise ValueError(f"Invalid query type for Document Storage connector: {query.query_type}")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing MongoDB query via MCP: {query.query}")
            self.logger.debug(f"Query parameters: {query.parameters}")
            
            # Prepare the request
            request_data = {
                "query": query.query,
                "query_type": "MONGODB",
                "parameters": query.parameters,
                "request_id": str(query.query_id) if hasattr(query, 'query_id') else None
            }
            
            # Execute the query
            response = requests.post(
                f"{self.base_url}/query",
                json=request_data
            )
            response.raise_for_status()
            result = response.json()
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Add our own execution time to the metadata
            if "metadata" in result:
                result["metadata"]["total_execution_time_ms"] = execution_time
            
            self.logger.info(f"Query executed successfully via MCP. Retrieved {len(result.get('data', []))} documents in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing MongoDB query via MCP: {str(e)}")
            raise