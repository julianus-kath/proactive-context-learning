"""
MCP Server for Document Storage data source.
Exposes MongoDB query capabilities through the MCP protocol.
"""
import time
import json
from typing import Dict, Any, List, Optional
import os

from crawling_agent.servers.base_server import BaseMCPServer, QueryRequest, QueryResponse

# Import pymongo conditionally to allow for mock testing without the actual dependency
try:
    import pymongo
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


class DocumentStorageServer(BaseMCPServer):
    """
    MCP Server for Document Storage data source.
    Provides MongoDB query capabilities.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8002,
        config_path: Optional[str] = None,
        mock_mode: bool = False
    ):
        """
        Initialize the Document Storage MCP server.
        
        Args:
            host: Host to bind the server to
            port: Port to bind the server to
            config_path: Path to the configuration file
            mock_mode: Whether to run in mock mode
        """
        super().__init__(
            server_type="DOCUMENT_STORAGE",
            version="1.0.0",
            host=host,
            port=port,
            config_path=config_path
        )
        
        self.mock_mode = mock_mode
        self.client = None
        self.db = None
        
        # Register additional routes
        self._register_additional_routes()
    
    def _register_additional_routes(self):
        """Register additional API routes specific to Document Storage server."""
        
        @self.app.get("/collections", tags=["Document Storage"])
        async def get_collections():
            """Get list of collections in the document database."""
            try:
                self._connect()
                if self.mock_mode:
                    collections = ["products", "orders", "customers"]
                else:
                    collections = self.db.list_collection_names()
                return {"collections": collections}
            except Exception as e:
                self.logger.error(f"Error getting collections: {str(e)}")
                return {"error": str(e)}
        
        @self.app.get("/schema/{collection_name}", tags=["Document Storage"])
        async def get_collection_schema(collection_name: str):
            """Get schema for a specific collection."""
            try:
                self._connect()
                if self.mock_mode:
                    if collection_name == "products":
                        schema = {
                            "type": "object",
                            "properties": {
                                "_id": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "price": {"type": "number"},
                                "category": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                                "specifications": {"type": "object"}
                            }
                        }
                    elif collection_name == "orders":
                        schema = {
                            "type": "object",
                            "properties": {
                                "_id": {"type": "string"},
                                "customer_id": {"type": "string"},
                                "order_date": {"type": "string", "format": "date-time"},
                                "items": {"type": "array", "items": {"type": "object"}},
                                "total_amount": {"type": "number"},
                                "status": {"type": "string"}
                            }
                        }
                    elif collection_name == "customers":
                        schema = {
                            "type": "object",
                            "properties": {
                                "_id": {"type": "string"},
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "address": {"type": "object"},
                                "orders": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    else:
                        schema = {}
                else:
                    # Infer schema from a sample document
                    sample = self.db[collection_name].find_one()
                    if sample:
                        schema = self._infer_schema(sample)
                    else:
                        schema = {}
                
                return {"collection": collection_name, "schema": schema}
            except Exception as e:
                self.logger.error(f"Error getting schema for collection {collection_name}: {str(e)}")
                return {"error": str(e)}
    
    def _infer_schema(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infer schema from a document.
        
        Args:
            document: The document to infer schema from
            
        Returns:
            Schema as a dictionary
        """
        schema = {"type": "object", "properties": {}}
        
        for key, value in document.items():
            if isinstance(value, dict):
                schema["properties"][key] = self._infer_schema(value)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    schema["properties"][key] = {
                        "type": "array",
                        "items": self._infer_schema(value[0])
                    }
                else:
                    schema["properties"][key] = {
                        "type": "array",
                        "items": {"type": self._get_type(value[0]) if value else "any"}
                    }
            else:
                schema["properties"][key] = {"type": self._get_type(value)}
        
        return schema
    
    def _get_type(self, value: Any) -> str:
        """
        Get the type of a value.
        
        Args:
            value: The value to get the type of
            
        Returns:
            Type as a string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "any"
    
    def get_capabilities(self) -> List[str]:
        """
        Get server capabilities.
        
        Returns:
            List of capability strings
        """
        return ["query", "schema", "collections"]
    
    def get_query_types(self) -> List[str]:
        """
        Get supported query types.
        
        Returns:
            List of supported query type strings
        """
        return ["MONGODB"]
    
    def _connect(self):
        """Establish a connection to the document database."""
        if self.client is not None:
            return
        
        if self.mock_mode:
            self.logger.info("Running in mock mode, no actual connection established")
            self.client = "mock_client"
            self.db = "mock_db"
            return
        
        if not PYMONGO_AVAILABLE:
            self.logger.error("pymongo is not installed. Cannot connect to MongoDB.")
            raise ImportError("pymongo is required to connect to MongoDB")
        
        try:
            # Get connection details from config
            mongo_uri = self.config['data_sources']['document_storage']['uri']
            db_name = self.config['data_sources']['document_storage']['database']
            
            self.logger.info(f"Connecting to MongoDB at {mongo_uri}")
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            self.logger.info(f"Connected to MongoDB database: {db_name}")
            
        except Exception as e:
            self.logger.error(f"Error connecting to MongoDB: {str(e)}")
            raise
    
    async def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute a MongoDB query against the document database.
        
        Args:
            request: The query request
            
        Returns:
            Query response with results
        """
        if request.query_type != "MONGODB":
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=f"Invalid query type for Document Storage server: {request.query_type}"
            )
        
        self._connect()
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing MongoDB query: {request.query}")
            
            if self.mock_mode:
                # In mock mode, return mock data based on the query
                result = self._execute_mock_query(request.query, request.parameters)
            else:
                # Parse the query string as JSON
                query_dict = json.loads(request.query)
                
                # Get the collection name from parameters
                collection_name = request.parameters.get("collection", "products")
                
                # Execute the query
                collection = self.db[collection_name]
                cursor = collection.find(query_dict)
                
                # Convert cursor to list of dictionaries
                result = list(cursor)
                
                # Convert ObjectId to string for JSON serialization
                for doc in result:
                    if "_id" in doc and hasattr(doc["_id"], "__str__"):
                        doc["_id"] = str(doc["_id"])
            
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
            
            self.logger.info(f"Query executed successfully. Retrieved {len(result)} documents in {execution_time:.2f}ms")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error executing MongoDB query: {str(e)}")
            return QueryResponse(
                request_id=request.request_id,
                status="error",
                error=str(e)
            )
    
    def _execute_mock_query(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a mock query and return mock data.
        
        Args:
            query: The query string
            parameters: Query parameters
            
        Returns:
            List of mock documents
        """
        # Parse the query string as JSON
        try:
            query_dict = json.loads(query)
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON query: {query}")
            return []
        
        # Get the collection name from parameters
        collection_name = parameters.get("collection", "products")
        
        # Mock data for different collections
        if collection_name == "products":
            # Check if the query is for expensive products
            if "price" in query_dict and "$gt" in query_dict["price"] and query_dict["price"]["$gt"] >= 100:
                return [
                    {"_id": "prod1", "name": "Expensive Product 1", "description": "A very expensive product", "price": 150.0, "category": "Electronics", "tags": ["premium", "electronics"]},
                    {"_id": "prod2", "name": "Expensive Product 2", "description": "Another expensive product", "price": 200.0, "category": "Electronics", "tags": ["premium", "electronics"]},
                    {"_id": "prod5", "name": "Premium Service", "description": "A premium service offering", "price": 300.0, "category": "Services", "tags": ["premium", "service"]}
                ]
            # Check if the query is for products in a specific category
            elif "category" in query_dict and query_dict["category"] == "Electronics":
                return [
                    {"_id": "prod1", "name": "Expensive Product 1", "description": "A very expensive product", "price": 150.0, "category": "Electronics", "tags": ["premium", "electronics"]},
                    {"_id": "prod2", "name": "Expensive Product 2", "description": "Another expensive product", "price": 200.0, "category": "Electronics", "tags": ["premium", "electronics"]}
                ]
            # Default products
            else:
                return [
                    {"_id": "prod1", "name": "Expensive Product 1", "description": "A very expensive product", "price": 150.0, "category": "Electronics", "tags": ["premium", "electronics"]},
                    {"_id": "prod2", "name": "Expensive Product 2", "description": "Another expensive product", "price": 200.0, "category": "Electronics", "tags": ["premium", "electronics"]},
                    {"_id": "prod3", "name": "Budget Product 1", "description": "An affordable product", "price": 50.0, "category": "Home", "tags": ["budget", "home"]},
                    {"_id": "prod4", "name": "Budget Product 2", "description": "Another affordable product", "price": 75.0, "category": "Home", "tags": ["budget", "home"]},
                    {"_id": "prod5", "name": "Premium Service", "description": "A premium service offering", "price": 300.0, "category": "Services", "tags": ["premium", "service"]}
                ]
        elif collection_name == "orders":
            # Check if the query is for completed orders
            if "status" in query_dict and query_dict["status"] == "Completed":
                return [
                    {"_id": "ord1", "customer_id": "cust1", "order_date": "2023-01-10T00:00:00Z", "items": [{"product_id": "prod1", "quantity": 2, "price": 150.0}, {"product_id": "prod3", "quantity": 1, "price": 50.0}], "total_amount": 350.0, "status": "Completed"},
                    {"_id": "ord2", "customer_id": "cust2", "order_date": "2023-01-15T00:00:00Z", "items": [{"product_id": "prod2", "quantity": 1, "price": 200.0}], "total_amount": 200.0, "status": "Completed"},
                    {"_id": "ord4", "customer_id": "cust1", "order_date": "2023-02-20T00:00:00Z", "items": [{"product_id": "prod3", "quantity": 1, "price": 50.0}, {"product_id": "prod4", "quantity": 1, "price": 25.0}], "total_amount": 75.0, "status": "Completed"}
                ]
            # Default orders
            else:
                return [
                    {"_id": "ord1", "customer_id": "cust1", "order_date": "2023-01-10T00:00:00Z", "items": [{"product_id": "prod1", "quantity": 2, "price": 150.0}, {"product_id": "prod3", "quantity": 1, "price": 50.0}], "total_amount": 350.0, "status": "Completed"},
                    {"_id": "ord2", "customer_id": "cust2", "order_date": "2023-01-15T00:00:00Z", "items": [{"product_id": "prod2", "quantity": 1, "price": 200.0}], "total_amount": 200.0, "status": "Completed"},
                    {"_id": "ord3", "customer_id": "cust3", "order_date": "2023-02-05T00:00:00Z", "items": [{"product_id": "prod1", "quantity": 1, "price": 150.0}], "total_amount": 150.0, "status": "Processing"},
                    {"_id": "ord4", "customer_id": "cust1", "order_date": "2023-02-20T00:00:00Z", "items": [{"product_id": "prod3", "quantity": 1, "price": 50.0}, {"product_id": "prod4", "quantity": 1, "price": 25.0}], "total_amount": 75.0, "status": "Completed"},
                    {"_id": "ord5", "customer_id": "cust4", "order_date": "2023-03-01T00:00:00Z", "items": [{"product_id": "prod2", "quantity": 1, "price": 200.0}, {"product_id": "prod5", "quantity": 1, "price": 300.0}], "total_amount": 500.0, "status": "Processing"}
                ]
        elif collection_name == "customers":
            # Check if the query is for a specific customer
            if "_id" in query_dict:
                customer_id = query_dict["_id"]
                if customer_id == "cust1":
                    return [{"_id": "cust1", "name": "John Smith", "email": "john.smith@example.com", "address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "12345"}, "orders": ["ord1", "ord4"]}]
                elif customer_id == "cust2":
                    return [{"_id": "cust2", "name": "Jane Doe", "email": "jane.doe@example.com", "address": {"street": "456 Oak Ave", "city": "Somewhere", "state": "NY", "zip": "67890"}, "orders": ["ord2"]}]
                else:
                    return []
            # Default customers
            else:
                return [
                    {"_id": "cust1", "name": "John Smith", "email": "john.smith@example.com", "address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "12345"}, "orders": ["ord1", "ord4"]},
                    {"_id": "cust2", "name": "Jane Doe", "email": "jane.doe@example.com", "address": {"street": "456 Oak Ave", "city": "Somewhere", "state": "NY", "zip": "67890"}, "orders": ["ord2"]},
                    {"_id": "cust3", "name": "Bob Johnson", "email": "bob.johnson@example.com", "address": {"street": "789 Pine Rd", "city": "Nowhere", "state": "TX", "zip": "54321"}, "orders": ["ord3"]},
                    {"_id": "cust4", "name": "Alice Brown", "email": "alice.brown@example.com", "address": {"street": "321 Elm St", "city": "Everywhere", "state": "FL", "zip": "09876"}, "orders": ["ord5"]}
                ]
        else:
            return []


def main():
    """Run the Document Storage MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Document Storage MCP Server")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind the server to")
    parser.add_argument("--config", type=str, help="Path to the configuration file")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    
    args = parser.parse_args()
    
    server = DocumentStorageServer(
        host=args.host,
        port=args.port,
        config_path=args.config,
        mock_mode=args.mock
    )
    
    server.run()


if __name__ == "__main__":
    main()