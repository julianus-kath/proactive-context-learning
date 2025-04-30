"""
Base MCP Client Connector.
Provides common functionality for all MCP client connectors.
"""
import os
import yaml
import json
import uuid
import requests
from typing import Dict, Any, Optional, List, Union

from crawling_agent.models.task_instruction import DataSourceQuery
from crawling_agent.utils.logger import get_logger


class BaseMCPConnector:
    """
    Base class for all MCP client connectors.
    Provides common functionality for connecting to MCP servers.
    """
    
    def __init__(
        self,
        server_type: str,
        host: str = "localhost",
        port: int = 8000,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the base MCP client connector.
        
        Args:
            server_type: Type of the server to connect to
            host: Host where the server is running
            port: Port where the server is running
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        self.logger = get_logger(f"mcp_connector.{server_type.lower()}")
        self.server_type = server_type
        self.host = host
        self.port = port
        self.mock_mode = mock_mode
        
        # Build the base URL
        self.base_url = f"http://{host}:{port}"
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config = self._load_config(config_path)
        
        # Get server configuration
        if not mock_mode:
            server_config = self.config.get('data_sources', {}).get(server_type.lower(), {})
            if 'host' in server_config:
                self.host = server_config['host']
            if 'port' in server_config:
                self.port = server_config['port']
            
            # Update base URL with configured host and port
            self.base_url = f"http://{self.host}:{self.port}"
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from the YAML file with environment variable substitution.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dictionary containing the configuration
        """
        try:
            with open(config_path, 'r') as f:
                # Load the YAML content
                config_str = f.read()
                
                # Replace environment variables
                for env_var in os.environ:
                    placeholder = f"${{{env_var}}}"
                    if placeholder in config_str:
                        config_str = config_str.replace(placeholder, os.environ[env_var])
                
                # Handle default values in format ${VAR:default}
                import re
                pattern = r'\${([^{}]+):([^{}]*)}'
                
                def replace_with_default(match):
                    env_var, default = match.groups()
                    return os.environ.get(env_var, default)
                
                config_str = re.sub(pattern, replace_with_default, config_str)
                
                # Parse the modified YAML
                config = yaml.safe_load(config_str)
                
                return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return {}
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the server.
        
        Returns:
            Dictionary containing server information
        """
        try:
            response = requests.get(f"{self.base_url}/info")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting server info: {str(e)}")
            if self.mock_mode:
                return {
                    "server_type": self.server_type,
                    "version": "1.0.0",
                    "capabilities": ["query"],
                    "query_types": [],
                    "status": "online"
                }
            else:
                raise
    
    def check_health(self) -> bool:
        """
        Check if the server is healthy.
        
        Returns:
            True if the server is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json().get("status") == "healthy"
        except Exception as e:
            self.logger.error(f"Error checking server health: {str(e)}")
            return False
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a query against the server.
        
        Args:
            query: The query to execute
            
        Returns:
            Dictionary containing the query results
        """
        raise NotImplementedError("Subclasses must implement execute_query")