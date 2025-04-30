"""
MCP Server for Knowledge Graph data source.
Exposes SPARQL query capabilities through the MCP protocol.
"""
import time
import json
import pandas as pd
import requests
from typing import Dict, Any, List, Optional
import os

from crawling_agent.servers.base_server import BaseMCPServer, QueryRequest, QueryResponse


class KnowledgeGraphServer(BaseMCPServer):
    """
    MCP Server for Knowledge Graph data source.
    Provides SPARQL query capabilities.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8003,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the Knowledge Graph MCP server.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="KNOWLEDGE_GRAPH",
            version="1.0.0",
            host=host,
            port=port,
            config_path=config_path
        )
        
        self.mock_mode = mock_mode
        self.endpoint_url = None
        
        # Register additional routes
        self._register_additional_routes()
    
    def _register_additional_routes(self):
        """Register additional API routes specific to Knowledge Graph server."""
        
        @self.app.get("/namespaces", tags=["Knowledge Graph"])
        async def get_namespaces():
            """Get list of namespaces in the knowledge graph."""
            try:
                if self.mock_mode:
                    namespaces = {
                        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                        "owl": "http://www.w3.org/2002/07/owl#",
                        "xsd": "http://www.w3.org/2001/XMLSchema#",
                        "product": "http://example.org/product#",
                        "employee": "http://example.org/employee#",
                        "company": "http://example.org/company#"
                    }
                else:
                    self._connect()
                    # Query for namespaces
                    query = """
                    SELECT DISTINCT ?prefix ?namespace
                    WHERE {
                        ?s ?p ?o .
                        BIND(STRBEFORE(STR(?p), "#") AS ?namespace)
                        BIND(REPLACE(STRBEFORE(STR(?p), "#"), "http://example.org/", "") AS ?prefix)
                        FILTER(STRSTARTS(STR(?p), "http://example.org/"))
                    }
                    """
                    response = self._execute_sparql_query(query)
                    namespaces = {}
                    for row in response.get("results", {}).get("bindings", []):
                        prefix = row.get("prefix", {}).get("value", "")
                        namespace = row.get("namespace", {}).get("value", "")
                        if prefix and namespace:
                            namespaces[prefix] = namespace
                
                return {"namespaces": namespaces}
            except Exception as e:
                self.logger.error(f"Error getting namespaces: {str(e)}")
                return {"error": str(e)}
        
        @self.app.get("/classes", tags=["Knowledge Graph"])
        async def get_classes():
            """Get list of classes in the knowledge graph."""
            try:
                if self.mock_mode:
                    classes = [
                        {"class": "http://example.org/product#Product", "count": 5},
                        {"class": "http://example.org/employee#Employee", "count": 5},
                        {"class": "http://example.org/company#Department", "count": 3}
                    ]
                else:
                    self._connect()
                    # Query for classes
                    query = """
                    SELECT ?class (COUNT(?instance) AS ?count)
                    WHERE {
                        ?instance a ?class .
                    }
                    GROUP BY ?class
                    ORDER BY DESC(?count)
                    """
                    response = self._execute_sparql_query(query)
                    classes = []
                    for row in response.get("results", {}).get("bindings", []):
                        class_uri = row.get("class", {}).get("value", "")
                        count = row.get("count", {}).get("value", "0")
                        if class_uri:
                            classes.append({"class": class_uri, "count": int(count)})
                
                return {"classes": classes}
            except Exception as e:
                self.logger.error(f"Error getting classes: {str(e)}")
                return {"error": str(e)}
        
        @self.app.get("/properties/{class_uri}", tags=["Knowledge Graph"])
        async def get_properties(class_uri: str):
            """Get properties for a specific class."""
            try:
                if self.mock_mode:
                    if "Product" in class_uri:
                        properties = [
                            {"property": "http://example.org/product#name", "type": "http://www.w3.org/2001/XMLSchema#string"},
                            {"property": "http://example.org/product#price", "type": "http://www.w3.org/2001/XMLSchema#decimal"},
                            {"property": "http://example.org/product#category", "type": "http://www.w3.org/2001/XMLSchema#string"}
                        ]
                    elif "Employee" in class_uri:
                        properties = [
                            {"property": "http://example.org/employee#name", "type": "http://www.w3.org/2001/XMLSchema#string"},
                            {"property": "http://example.org/employee#position", "type": "http://www.w3.org/2001/XMLSchema#string"},
                            {"property": "http://example.org/employee#department", "type": "http://example.org/company#Department"}
                        ]
                    else:
                        properties = []
                else:
                    self._connect()
                    # Query for properties
                    query = f"""
                    SELECT DISTINCT ?property ?type
                    WHERE {{
                        ?instance a <{class_uri}> .
                        ?instance ?property ?value .
                        OPTIONAL {{ ?value a ?type }}
                        FILTER(?property != rdf:type)
                    }}
                    """
                    response = self._execute_sparql_query(query)
                    properties = []
                    for row in response.get("results", {}).get("bindings", []):
                        property_uri = row.get("property", {}).get("value", "")
                        type_uri = row.get("type", {}).get("value", "")
                        if property_uri:
                            properties.append({"property": property_uri, "type": type_uri})
                
                return {"class": class_uri, "properties": properties}
            except Exception as e:
                self.logger.error(f"Error getting properties for class {class_uri}: {str(e)}")
                return {"error": str(e)}
    
    def get_capabilities(self) -> List[str]:
        """
        Get server capabilities.
        
        Returns:
            List of capability strings
        """
        return ["query", "namespaces", "classes", "properties"]
    
    def get_query_types(self) -> List[str]:
        """
        Get supported query types.
        
        Returns:
            List of supported query type strings
        """
        return ["SPARQL"]
    
    def _connect(self):
        """Set up the connection to the knowledge graph endpoint."""
        if self.endpoint_url is not None:
            return
        
        try:
            if self.mock_mode:
                self.endpoint_url = "mock://endpoint"
                self.logger.info("Running in mock mode, no actual connection established")
            else:
                # Get endpoint URL from config
                endpoint = self.config['data_sources']['knowledge_graph']['endpoint']
                self.endpoint_url = endpoint
                self.logger.info(f"Initialized Knowledge Graph connector with endpoint: {endpoint}")
                
                # Test the connection
                test_query = "ASK { ?s ?p ?o }"
                response = requests.post(
                    self.endpoint_url,
                    data={"query": test_query},
                    headers={"Accept": "application/sparql-results+json"}
                )
                response.raise_for_status()
                self.logger.info("Successfully connected to Knowledge Graph endpoint")
        except Exception as e:
            self.logger.error(f"Error connecting to Knowledge Graph endpoint: {str(e)}")
            raise
    
    def _execute_sparql_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query against the real endpoint.
        
        Args:
            query: The SPARQL query string
            
        Returns:
            Query results as a dictionary
        """
        response = requests.post(
            self.endpoint_url,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"}
        )
        response.raise_for_status()
        return response.json()
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a SPARQL query against the knowledge graph.
        
        Args:
            request: The query request
            
        Returns:
            Query response with results
        """
        if request.query_type != "SPARQL":
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=f"Invalid query type for Knowledge Graph server: {request.query_type}"
            )
        
        self._connect()
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing SPARQL query: {request.query}")
            
            if self.mock_mode:
                # In mock mode, return mock data based on the query
                result = self._execute_mock_query(request.query)
            else:
                # Execute the query against the real endpoint
                response = requests.post(
                    self.endpoint_url,
                    data={"query": request.query},
                    headers={"Accept": "application/sparql-results+json"}
                )
                response.raise_for_status()
                
                # Parse the response
                sparql_results = response.json()
                
                # Convert SPARQL results to a list of dictionaries
                result = []
                for binding in sparql_results.get("results", {}).get("bindings", []):
                    row = {}
                    for var, value in binding.items():
                        row[var] = value.get("value")
                    result.append(row)
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the response
            response = QueryResponse(
                request_id=request.request_id,
                data=result,
                metadata={
                    "row_count": len(result),
                    "execution_time_ms": execution_time
                },
                status="success"
            )
            
            self.logger.info(f"Query executed successfully. Retrieved {len(result)} results in {execution_time:.2f}ms")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing SPARQL query: {str(e)}")
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=str(e)
            )
    
    def _execute_mock_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a mock SPARQL query and return mock data.
        
        Args:
            query: The SPARQL query string
            
        Returns:
            List of mock results
        """
        query_lower = query.lower()
        
        # Mock data for product queries
        if "product" in query_lower and "price" in query_lower and "filter" in query_lower and ">" in query_lower:
            return [
                {"product": "prod1", "name": "Expensive Product 1", "price": "150.0"},
                {"product": "prod2", "name": "Expensive Product 2", "price": "200.0"},
                {"product": "prod5", "name": "Premium Service", "price": "300.0"}
            ]
        # Mock data for employee queries
        elif "employee" in query_lower and "sales" in query_lower:
            return [
                {"employee": "emp1", "name": "John Doe", "position": "Manager", "department": "Sales"},
                {"employee": "emp2", "name": "Jane Smith", "position": "Associate", "department": "Sales"}
            ]
        # Mock data for department queries
        elif "department" in query_lower:
            return [
                {"department": "dept1", "name": "Sales", "employee_count": "2"},
                {"department": "dept2", "name": "Engineering", "employee_count": "2"},
                {"department": "dept3", "name": "Marketing", "employee_count": "1"}
            ]
        # Default mock data
        else:
            return [
                {"s": "subject1", "p": "predicate1", "o": "object1"},
                {"s": "subject2", "p": "predicate2", "o": "object2"},
                {"s": "subject3", "p": "predicate3", "o": "object3"}
            ]


def main():
    """Run the Knowledge Graph MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Knowledge Graph MCP Server")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8003, help="Port to bind the server to")
    parser.add_argument("--config", type=str, help="Path to the configuration file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    
    args = parser.parse_args()
    
    server = KnowledgeGraphServer(
        host=args.host,
        port=args.port,
        config_path=args.config,
        mock_mode=args.mock
    )
    
    server.run()


if __name__ == "__main__":
    main()