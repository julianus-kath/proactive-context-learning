"""
Knowledge Graph Connector for executing SPARQL queries against a knowledge graph endpoint.
"""
import time
import os
import yaml
from typing import Dict, List, Any, Optional, Union
import requests
import pandas as pd
import json

from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest
from crawling_agent.utils.logger import get_logger


class KnowledgeGraphConnector:
    """
    Connector for crawling data from a knowledge graph using SPARQL queries.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Knowledge Graph connector.
        
        Args:
            config_path: Path to the configuration file (optional)
        """
        self.logger = get_logger(__name__)
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config = self._load_config(config_path)
        self.endpoint = self.config['data_sources']['knowledge_graph']['endpoint']
        self.timeout = self.config['data_sources']['knowledge_graph'].get('timeout_seconds', 30)
        
        # Set up authentication if needed
        auth_config = self.config['data_sources']['knowledge_graph'].get('auth', {})
        self.auth_method = auth_config.get('method', 'none')
        self.auth_params = auth_config
        
        self.logger.info(f"Initialized Knowledge Graph connector with endpoint: {self.endpoint}")
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from the YAML file with environment variable substitution.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dictionary containing the configuration
        """
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
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers based on the configured auth method.
        
        Returns:
            Dictionary of HTTP headers for authentication
        """
        headers = {}
        
        if self.auth_method == 'none':
            return headers
        elif self.auth_method == 'basic':
            # Basic auth is handled by the requests library, not in headers
            pass
        elif self.auth_method == 'token':
            token = self.auth_params.get('token')
            if token:
                headers['Authorization'] = f"Bearer {token}"
        elif self.auth_method == 'api_key':
            key = self.auth_params.get('api_key')
            key_name = self.auth_params.get('api_key_name', 'api_key')
            if key:
                headers[key_name] = key
                
        return headers
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a SPARQL query against the knowledge graph endpoint.
        
        Args:
            query: The DataSourceQuery object containing the SPARQL query
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.SPARQL:
            raise ValueError(f"Invalid query type for Knowledge Graph connector: {query.query_type}")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing SPARQL query against endpoint: {self.endpoint}")
            self.logger.debug(f"SPARQL query: {query.query}")
            
            # Prepare request
            headers = {
                'Accept': 'application/sparql-results+json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            headers.update(self._get_auth_headers())
            
            # Prepare authentication for requests
            auth = None
            if self.auth_method == 'basic':
                username = self.auth_params.get('username')
                password = self.auth_params.get('password')
                if username and password:
                    auth = (username, password)
            
            # Execute the query
            response = requests.post(
                self.endpoint,
                data={'query': query.query},
                headers=headers,
                auth=auth,
                timeout=self.timeout
            )
            
            # Check for errors
            response.raise_for_status()
            
            # Parse the response
            result_json = response.json()
            
            # Convert to a more usable format (list of dictionaries)
            bindings = result_json.get('results', {}).get('bindings', [])
            results = []
            
            for binding in bindings:
                row = {}
                for var, value in binding.items():
                    row[var] = value.get('value')
                results.append(row)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the result
            result = {
                "data": results,
                "metadata": {
                    "row_count": len(results),
                    "variables": result_json.get('head', {}).get('vars', []),
                    "execution_time_ms": execution_time
                }
            }
            
            self.logger.info(f"SPARQL query executed successfully. Retrieved {len(results)} results in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SPARQL query: {str(e)}")
            raise