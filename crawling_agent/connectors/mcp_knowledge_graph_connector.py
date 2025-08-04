"""
Knowledge Graph Connector for executing SPARQL queries against the Knowledge Graph MCP server.
"""
import time
import uuid
import requests
import json
from typing import Dict, List, Any, Optional, Union

from crawling_agent.connectors.base_connector import BaseMCPConnector
from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest


class KnowledgeGraphConnector(BaseMCPConnector):
    """
    Connector for crawling data from a knowledge graph using SPARQL queries via MCP.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8003,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the Knowledge Graph connector.
        
        Args:
            host: Host where the Knowledge Graph MCP server is running
            port: Port where the Knowledge Graph MCP server is running
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="knowledge_graph",
            host=host,
            port=port,
            config_path=config_path,
            mock_mode=mock_mode
        )
    
    def get_namespaces(self) -> Dict[str, str]:
        """
        Get list of namespaces in the knowledge graph.
        
        Returns:
            Dictionary mapping namespace prefixes to URIs
        """
        try:
            response = requests.get(f"{self.base_url}/namespaces")
            response.raise_for_status()
            return response.json().get("namespaces", {})
        except Exception as e:
            self.logger.error(f"Error getting namespaces: {str(e)}")
            if self.mock_mode:
                return {
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                    "owl": "http://www.w3.org/2002/07/owl#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#",
                    "product": "http://example.org/product#",
                    "employee": "http://example.org/employee#",
                    "company": "http://example.org/company#"
                }
            else:
                raise
    
    def get_classes(self) -> List[Dict[str, Any]]:
        """
        Get list of classes in the knowledge graph.
        
        Returns:
            List of dictionaries containing class information
        """
        try:
            response = requests.get(f"{self.base_url}/classes")
            response.raise_for_status()
            return response.json().get("classes", [])
        except Exception as e:
            self.logger.error(f"Error getting classes: {str(e)}")
            if self.mock_mode:
                return [
                    {"class": "http://example.org/product#Product", "count": 5},
                    {"class": "http://example.org/employee#Employee", "count": 5},
                    {"class": "http://example.org/company#Department", "count": 3}
                ]
            else:
                raise
    
    def get_properties(self, class_uri: str) -> Dict[str, Any]:
        """
        Get properties for a specific class.
        
        Args:
            class_uri: URI of the class
            
        Returns:
            Dictionary containing the class properties
        """
        try:
            response = requests.get(f"{self.base_url}/properties/{class_uri}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error getting properties for class {class_uri}: {str(e)}")
            if self.mock_mode:
                return {"class": class_uri, "properties": []}
            else:
                raise
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a SPARQL query against the knowledge graph via MCP.
        
        Args:
            query: The DataSourceQuery object containing the SPARQL query and parameters
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.SPARQL:
            raise ValueError(f"Invalid query type for Knowledge Graph connector: {query.query_type}")
        
        start_time = time.time()
        
        try:
            query_text = query.query if hasattr(query, 'query') else query
            query_params = query.parameters if hasattr(query, 'parameters') else {}
            self.logger.info(f"Executing SPARQL query via MCP: {query_text}")
            self.logger.debug(f"Query parameters: {query_params}")
            
            # Prepare the request
            request_data = {
                "query": query_text,
                "query_type": "SPARQL",
                "parameters": query_params,
                "request_id": str(query.query_id) if hasattr(query, 'query_id') and query.query_id else str(uuid.uuid4())
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
            
            self.logger.info(f"Query executed successfully via MCP. Retrieved {len(result.get('data', []))} results in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing SPARQL query via MCP: {str(e)}")
            raise