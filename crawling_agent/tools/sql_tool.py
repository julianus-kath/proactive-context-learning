"""
SQL Tool implementation for the crawling agent.
"""
import os
import json
import logging
import aiohttp
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)


class SQLTool:
    """
    Tool for executing SQL queries against the ERP database.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the SQL tool.
        
        Args:
            config: Optional configuration dictionary with the following keys:
                - host: Host where the ERP API is running
                - port: Port of the ERP API
        """
        self.config = config or {}
        
        # Get configuration from environment variables or use defaults
        self.host = self.config.get("host") or os.environ.get("SQL_HOST", "localhost")
        self.port = self.config.get("port") or os.environ.get("SQL_PORT", "8001")
        
        # Build the base URL
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Initialize session to None, will be created when needed
        self._session = None
        
        logger.info(f"Initialized SQL tool with API at {self.base_url}")
    
    async def _ensure_session(self):
        """Ensure we have an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata about the database (tables and columns).
        
        Returns:
            Dictionary containing database metadata
        """
        await self._ensure_session()
        
        try:
            async with self._session.get(f"{self.base_url}/metadata") as response:
                response.raise_for_status()
                metadata = await response.json()
                logger.info(f"Retrieved metadata for {len(metadata.get('tables', []))} tables")
                return metadata
        except Exception as e:
            logger.error(f"Error getting metadata: {str(e)}")
            raise
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an SQL query.
        
        Args:
            parameters: Dictionary with the following keys:
                - query: SQL query to execute
                - parameters: Query parameters (optional)
            
        Returns:
            The query results
        """
        query = parameters.get("query")
        if not query:
            error_msg = "Query is required"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        query_params = parameters.get("parameters", {})
        
        await self._ensure_session()
        
        try:
            logger.info(f"Executing SQL query: {query}")
            if query_params:
                logger.info(f"With parameters: {json.dumps(query_params, indent=2)}")
            
            async with self._session.post(
                f"{self.base_url}/query",
                json={"sql": query, "parameters": query_params}
            ) as response:
                response.raise_for_status()
                result = await response.json()
                
                # Log the result summary
                row_count = len(result.get("data", []))
                logger.info(f"Query executed successfully. Retrieved {row_count} rows.")
                
                if row_count > 0:
                    # Log a sample of the data (first row)
                    logger.info("Sample data (first row):")
                    logger.info(json.dumps(result["data"][0], indent=2))
                
                return {
                    "source_tool": "sql",
                    "query_text": query,
                    "raw_result": result.get("data", []),
                    "metadata": result.get("metadata", {})
                }
                
        except Exception as e:
            logger.error(f"Error executing SQL query: {str(e)}")
            raise
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "sql"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Execute SQL queries against the ERP database. "
            "This tool can be used to retrieve information about products, "
            "customers, orders, employees, and other business data stored in "
            "the ERP database."
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
                    "description": "SQL query to execute"
                },
                "parameters": {
                    "type": "object",
                    "description": "Query parameters"
                }
            },
            "required": ["query"]
        }