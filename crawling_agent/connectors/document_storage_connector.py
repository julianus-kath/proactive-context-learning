"""
Document Storage Connector for executing MongoDB queries against a document database.
"""
import time
import os
import yaml
import json
from typing import Dict, List, Any, Optional, Union

from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import ActionRequest
from crawling_agent.utils.logger import get_logger

# Import pymongo conditionally to allow for mock testing without the actual dependency
try:
    import pymongo
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


class DocumentStorageConnector:
    """
    Connector for crawling data from a document storage system (MongoDB).
    """
    
    def __init__(self, config_path: Optional[str] = None, mock_mode: bool = False):
        """
        Initialize the Document Storage connector.
        
        Args:
            config_path: Path to the configuration file (optional)
            mock_mode: Whether to run in mock mode without actual MongoDB connection
        """
        self.logger = get_logger(__name__)
        self.mock_mode = mock_mode
        
        if not PYMONGO_AVAILABLE and not mock_mode:
            self.logger.warning("pymongo not available. Install it with 'pip install pymongo'")
            self.logger.warning("Falling back to mock mode")
            self.mock_mode = True
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config = self._load_config(config_path)
        self.client = None
        self.db = None
        
        if not self.mock_mode:
            self.uri = self.config['data_sources']['document_storage']['uri']
            self.db_name = self.config['data_sources']['document_storage']['database']
            self.timeout = self.config['data_sources']['document_storage'].get('timeout_seconds', 30)
            
            self.logger.info(f"Initialized Document Storage connector with URI: {self.uri}")
        else:
            self.logger.info("Initialized Document Storage connector in mock mode")
        
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
    
    def connect(self) -> None:
        """
        Establish a connection to the MongoDB database.
        """
        if self.mock_mode or self.client is not None:
            return
        
        try:
            self.logger.info(f"Connecting to MongoDB at {self.uri}")
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=self.timeout * 1000)
            
            # Test the connection
            self.client.server_info()
            
            self.db = self.client[self.db_name]
            self.logger.info(f"Connected to MongoDB database: {self.db_name}")
            
        except Exception as e:
            self.logger.error(f"Error connecting to MongoDB: {str(e)}")
            if self.client:
                self.client.close()
                self.client = None
            raise
    
    def disconnect(self) -> None:
        """
        Close the connection to the MongoDB database.
        """
        if self.mock_mode or self.client is None:
            return
            
        self.client.close()
        self.client = None
        self.db = None
        self.logger.info("Disconnected from MongoDB")
    
    def execute_query(self, query: DataSourceQuery) -> Dict[str, Any]:
        """
        Execute a MongoDB query against the document storage.
        
        Args:
            query: The DataSourceQuery object containing the MongoDB query
            
        Returns:
            Dictionary containing the query results and metadata
        """
        if query.query_type != QueryType.MONGODB:
            raise ValueError(f"Invalid query type for Document Storage connector: {query.query_type}")
        
        start_time = time.time()
        
        try:
            # Parse the query string as JSON
            if isinstance(query.query, str):
                query_dict = json.loads(query.query)
            else:
                query_dict = query.query
                
            self.logger.info("Executing MongoDB query")
            self.logger.debug(f"MongoDB query: {query_dict}")
            
            if self.mock_mode:
                # In mock mode, return sample data
                self.logger.info("Running in mock mode, returning sample data")
                results = self._get_mock_data(query_dict)
            else:
                # Connect to MongoDB
                self.connect()
                
                # Determine the collection to query
                collection_name = query.parameters.get('collection', 'documents')
                collection = self.db[collection_name]
                
                # Execute the query
                cursor = collection.find(query_dict)
                
                # Apply limit if specified
                if 'limit' in query.parameters:
                    cursor = cursor.limit(query.parameters['limit'])
                
                # Convert cursor to list
                results = list(cursor)
                
                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if '_id' in doc and hasattr(doc['_id'], '__str__'):
                        doc['_id'] = str(doc['_id'])
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the result
            result = {
                "data": results,
                "metadata": {
                    "document_count": len(results),
                    "execution_time_ms": execution_time
                }
            }
            
            self.logger.info(f"MongoDB query executed successfully. Retrieved {len(results)} documents in {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing MongoDB query: {str(e)}")
            raise
        finally:
            # Keep the connection open for potential future queries
            pass
    
    def _get_mock_data(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate mock data for testing without a real MongoDB connection.
        
        Args:
            query: The MongoDB query dictionary
            
        Returns:
            List of dictionaries representing MongoDB documents
        """
        # Simple mock implementation that returns data based on query patterns
        # In a real implementation, this would be more sophisticated
        
        # Sample documents
        documents = [
            {
                "_id": "doc1",
                "title": "Product Specification",
                "product_type": "Electronics",
                "price": 150,
                "tags": ["specification", "technical", "product"],
                "created_at": "2023-01-15T10:30:00Z"
            },
            {
                "_id": "doc2",
                "title": "User Manual",
                "product_type": "Software",
                "price": 50,
                "tags": ["manual", "user guide", "instructions"],
                "created_at": "2023-02-20T14:45:00Z"
            },
            {
                "_id": "doc3",
                "title": "Sales Report",
                "department": "Sales",
                "quarter": "Q1",
                "year": 2023,
                "tags": ["report", "sales", "quarterly"],
                "created_at": "2023-04-05T09:15:00Z"
            }
        ]
        
        # Filter documents based on the query
        filtered_docs = []
        for doc in documents:
            match = True
            
            # Simple filtering logic (very basic, just for demonstration)
            for key, value in query.items():
                if key not in doc:
                    match = False
                    break
                    
                if isinstance(value, dict):
                    # Handle operators like $gt, $lt, etc.
                    for op, op_value in value.items():
                        if op == "$gt" and not (doc[key] > op_value):
                            match = False
                            break
                        elif op == "$lt" and not (doc[key] < op_value):
                            match = False
                            break
                        elif op == "$exists" and (key in doc) != op_value:
                            match = False
                            break
                else:
                    # Direct value comparison
                    if doc[key] != value:
                        match = False
                        break
            
            if match:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def __enter__(self):
        """
        Context manager entry point.
        """
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        """
        self.disconnect()