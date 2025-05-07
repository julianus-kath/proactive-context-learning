"""
Tool interface and implementations for the agent.
"""
import abc
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Union

from crawling_agent.models.task_instruction import DataSourceQuery, QueryType
from crawling_agent.connectors.mcp_erp_connector import ERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import DocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import KnowledgeGraphConnector

# Configure logging
logger = logging.getLogger(__name__)


class Tool(abc.ABC):
    """
    Abstract base class for agent tools.
    
    Tools are the primary way for the agent to interact with external systems
    and perform actions.
    """
    
    @abc.abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the tool with configuration.
        
        Args:
            config: Tool-specific configuration
        """
        self.config = config or {}
    
    @abc.abstractmethod
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the tool with the given parameters.
        
        Args:
            parameters: Tool-specific parameters
            
        Returns:
            The result of running the tool
        """
        pass
    
    @abc.abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        pass
    
    @abc.abstractmethod
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        pass
    
    @abc.abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool's parameters.
        
        Returns:
            JSON schema for the parameters
        """
        pass
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for this tool.
        
        Returns:
            Default configuration dictionary
        """
        return {}


class ERPQueryTool(Tool):
    """
    Tool for querying the ERP system.
    """
    
    def __init__(self, erp_connector: Optional[ERPConnector] = None, config: Optional[Dict] = None):
        """
        Initialize the ERP query tool.
        
        Args:
            erp_connector: Optional ERPConnector instance
            config: Optional configuration dictionary with the following keys:
            - host: Host where the MCP server is running
            - port: Port of the MCP server
            - config_path: Path to the configuration file
        """
        config = config or self.get_default_config()
        super().__init__(config)
        
        if erp_connector is not None:
            self.erp_connector = erp_connector
        else:
            self.erp_connector = ERPConnector(
                host=config.get("host", "localhost"),
                port=config.get("port", 8001),
                config_path=config.get("config_path")
            )
        
        logger.info("Initialized ERP query tool")
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run an SQL query against the ERP system.
        
        Args:
            parameters: Dictionary with the following keys:
                - query: SQL query to execute
                - parameters: Query parameters (optional)
            
        Returns:
            The query results
        """
        query = parameters.get("query")
        if not query:
            raise ValueError("Query is required")
        
        query_params = parameters.get("parameters", {})
        
        # Create a DataSourceQuery
        data_source_query = DataSourceQuery(
            source_type="erp",
            query_type=QueryType.SQL,
            query=query,
            parameters=query_params
        )
        
        # Execute the query
        result = await self.erp_connector.execute_query(data_source_query)
        
        return {
            "source_type": "erp",
            "query_type": "SQL",
            "data": result.get("data", []),
            "metadata": result.get("metadata", {})
        }
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "erp_query"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Execute SQL queries against the ERP system. "
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
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the ERP query tool.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "host": "localhost",
            "port": 8001
        }


class DocumentStorageQueryTool(Tool):
    """
    Tool for querying the document storage system.
    """
    
    def __init__(self, doc_connector: Optional[DocumentStorageConnector] = None, config: Optional[Dict] = None):
        """
        Initialize the document storage query tool.
        
        Args:
            doc_connector: Optional DocumentStorageConnector instance
            config: Optional configuration dictionary with the following keys:
            - host: Host where the MCP server is running
            - port: Port of the MCP server
            - config_path: Path to the configuration file
        """
        config = config or self.get_default_config()
        super().__init__(config)
        
        if doc_connector is not None:
            self.doc_connector = doc_connector
        else:
            self.doc_connector = DocumentStorageConnector(
                host=config.get("host", "localhost"),
                port=config.get("port", 8002),
                config_path=config.get("config_path")
            )
        
        logger.info("Initialized document storage query tool")
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a MongoDB query against the document storage system.
        
        Args:
            parameters: Dictionary with the following keys:
                - query: MongoDB query to execute (as a JSON string or dict)
                - collection: Collection to query
                - parameters: Additional query parameters (optional)
            
        Returns:
            The query results
        """
        query = parameters.get("query")
        if not query:
            raise ValueError("Query is required")
        
        collection = parameters.get("collection")
        if not collection:
            raise ValueError("Collection is required")
        
        query_params = parameters.get("parameters", {})
        
        # If query is a string, parse it as JSON
        if isinstance(query, str):
            try:
                query = json.loads(query)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON query")
        
        # Add collection to query parameters
        query_params["collection"] = collection
        
        # Create a DataSourceQuery
        data_source_query = DataSourceQuery(
            source_type="document_storage",
            query_type=QueryType.MONGODB,
            query=json.dumps(query),  # Convert back to string for the connector
            parameters=query_params
        )
        
        # Execute the query
        result = self.doc_connector.execute_query(data_source_query)
        
        return {
            "source_type": "document_storage",
            "query_type": "MONGODB",
            "collection": collection,
            "data": result.get("data", []),
            "metadata": result.get("metadata", {})
        }
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "document_storage_query"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Execute MongoDB queries against the document storage system. "
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
                    "oneOf": [
                        {"type": "string", "description": "MongoDB query as a JSON string"},
                        {"type": "object", "description": "MongoDB query as an object"}
                    ],
                    "description": "MongoDB query to execute"
                },
                "collection": {
                    "type": "string",
                    "description": "Collection to query"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional query parameters"
                }
            },
            "required": ["query", "collection"]
        }
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the document storage query tool.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "host": "localhost",
            "port": 8002
        }


class KnowledgeGraphQueryTool(Tool):
    """
    Tool for querying the knowledge graph system.
    """
    
    def __init__(self, kg_connector: Optional[KnowledgeGraphConnector] = None, config: Optional[Dict] = None):
        """
        Initialize the knowledge graph query tool.
        
        Args:
            kg_connector: Optional KnowledgeGraphConnector instance
            config: Optional configuration dictionary with the following keys:
            - host: Host where the MCP server is running
            - port: Port of the MCP server
            - config_path: Path to the configuration file
        """
        config = config or self.get_default_config()
        super().__init__(config)
        
        if kg_connector is not None:
            self.kg_connector = kg_connector
        else:
            self.kg_connector = KnowledgeGraphConnector(
                host=config.get("host", "localhost"),
                port=config.get("port", 8003),
                config_path=config.get("config_path")
            )
        
        logger.info("Initialized knowledge graph query tool")
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a SPARQL query against the knowledge graph system.
        
        Args:
            parameters: Dictionary with the following keys:
                - query: SPARQL query to execute
                - parameters: Additional query parameters (optional)
            
        Returns:
            The query results
        """
        query = parameters.get("query")
        if not query:
            raise ValueError("Query is required")
        
        query_params = parameters.get("parameters", {})
        
        # Create a DataSourceQuery
        data_source_query = DataSourceQuery(
            source_type="knowledge_graph",
            query_type=QueryType.SPARQL,
            query=query,
            parameters=query_params
        )
        
        # Execute the query
        result = self.kg_connector.execute_query(data_source_query)
        
        return {
            "source_type": "knowledge_graph",
            "query_type": "SPARQL",
            "data": result.get("data", []),
            "metadata": result.get("metadata", {})
        }
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "knowledge_graph_query"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Execute SPARQL queries against the knowledge graph system. "
            "This tool can be used to retrieve semantic information and "
            "relationships between entities, such as product categories, "
            "customer segments, organizational hierarchies, and other "
            "graph-based data."
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
                    "description": "SPARQL query to execute"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional query parameters"
                }
            },
            "required": ["query"]
        }
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the knowledge graph query tool.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "host": "localhost",
            "port": 8003
        }


class SchemaInformationTool(Tool):
    """
    Tool for retrieving schema information about data sources.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the schema information tool.
        
        Args:
            config: Optional configuration dictionary with connection settings
        """
        config = config or self.get_default_config()
        super().__init__(config)
        
        # Initialize connectors with configuration
        self.erp_connector = ERPConnector(
            host=config.get("host", "localhost"),
            port=config.get("port", 8001),
            config_path=config.get("config_path")
        )
        self.document_storage_connector = DocumentStorageConnector(
            host=config.get("host", "localhost"),
            port=config.get("port", 8002),
            config_path=config.get("config_path")
        )
        self.knowledge_graph_connector = KnowledgeGraphConnector(
            host=config.get("host", "localhost"),
            port=config.get("port", 8003),
            config_path=config.get("config_path")
        )
        
        logger.info("Initialized schema information tool")
    
    async def run(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve schema information about data sources.
        
        Args:
            parameters: Dictionary with the following keys:
                - source_type: Type of data source (erp, document_storage, knowledge_graph, or all)
            
        Returns:
            Schema information for the requested data sources
        """
        source_type = parameters.get("source_type", "all").lower()
        
        result = {
            "schemas": {}
        }
        
        # Get schema information for the requested data sources
        if source_type in ["erp", "all"]:
            result["schemas"]["erp"] = self._get_erp_schema()
        
        if source_type in ["document_storage", "all"]:
            result["schemas"]["document_storage"] = self._get_document_storage_schema()
        
        if source_type in ["knowledge_graph", "all"]:
            result["schemas"]["knowledge_graph"] = self._get_knowledge_graph_schema()
        
        return result
    
    def _get_erp_schema(self) -> Dict[str, Any]:
        """
        Get schema information for the ERP system.
        
        Returns:
            Schema information for the ERP system
        """
        # In a real implementation, this would query the ERP system for its schema
        # For now, we'll return a mock schema
        return {
            "tables": [
                {
                    "name": "products",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT", "nullable": False},
                        {"name": "description", "type": "TEXT", "nullable": True},
                        {"name": "price", "type": "REAL", "nullable": False},
                        {"name": "category", "type": "TEXT", "nullable": True},
                        {"name": "stock", "type": "INTEGER", "nullable": False},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": False}
                    ]
                },
                {
                    "name": "customers",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT", "nullable": False},
                        {"name": "email", "type": "TEXT", "nullable": False},
                        {"name": "address", "type": "TEXT", "nullable": True},
                        {"name": "phone", "type": "TEXT", "nullable": True},
                        {"name": "created_at", "type": "TIMESTAMP", "nullable": False}
                    ]
                },
                {
                    "name": "orders",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "customer_id", "type": "INTEGER", "nullable": False, "foreign_key": "customers.id"},
                        {"name": "order_date", "type": "TIMESTAMP", "nullable": False},
                        {"name": "status", "type": "TEXT", "nullable": False},
                        {"name": "total", "type": "REAL", "nullable": False}
                    ]
                },
                {
                    "name": "order_items",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "order_id", "type": "INTEGER", "nullable": False, "foreign_key": "orders.id"},
                        {"name": "product_id", "type": "INTEGER", "nullable": False, "foreign_key": "products.id"},
                        {"name": "quantity", "type": "INTEGER", "nullable": False},
                        {"name": "price", "type": "REAL", "nullable": False}
                    ]
                },
                {
                    "name": "employees",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "TEXT", "nullable": False},
                        {"name": "email", "type": "TEXT", "nullable": False},
                        {"name": "department", "type": "TEXT", "nullable": False},
                        {"name": "position", "type": "TEXT", "nullable": False},
                        {"name": "hire_date", "type": "TIMESTAMP", "nullable": False}
                    ]
                }
            ],
            "query_type": "SQL"
        }
    
    def _get_document_storage_schema(self) -> Dict[str, Any]:
        """
        Get schema information for the document storage system.
        
        Returns:
            Schema information for the document storage system
        """
        # In a real implementation, this would query the document storage system for its schema
        # For now, we'll return a mock schema
        return {
            "collections": [
                {
                    "name": "products",
                    "fields": [
                        {"name": "_id", "type": "ObjectId"},
                        {"name": "name", "type": "string"},
                        {"name": "description", "type": "string"},
                        {"name": "price", "type": "number"},
                        {"name": "category", "type": "string"},
                        {"name": "tags", "type": "array", "items": {"type": "string"}},
                        {"name": "specifications", "type": "object"},
                        {"name": "created_at", "type": "date"}
                    ]
                },
                {
                    "name": "orders",
                    "fields": [
                        {"name": "_id", "type": "ObjectId"},
                        {"name": "customer_id", "type": "string"},
                        {"name": "order_date", "type": "date"},
                        {"name": "status", "type": "string"},
                        {"name": "items", "type": "array", "items": {
                            "type": "object",
                            "fields": [
                                {"name": "product_id", "type": "string"},
                                {"name": "quantity", "type": "number"},
                                {"name": "price", "type": "number"}
                            ]
                        }},
                        {"name": "shipping_address", "type": "object"},
                        {"name": "total", "type": "number"}
                    ]
                },
                {
                    "name": "customer_reviews",
                    "fields": [
                        {"name": "_id", "type": "ObjectId"},
                        {"name": "product_id", "type": "string"},
                        {"name": "customer_id", "type": "string"},
                        {"name": "rating", "type": "number"},
                        {"name": "review_text", "type": "string"},
                        {"name": "created_at", "type": "date"}
                    ]
                }
            ],
            "query_type": "MONGODB"
        }
    
    def _get_knowledge_graph_schema(self) -> Dict[str, Any]:
        """
        Get schema information for the knowledge graph system.
        
        Returns:
            Schema information for the knowledge graph system
        """
        # In a real implementation, this would query the knowledge graph system for its schema
        # For now, we'll return a mock schema
        return {
            "prefixes": {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "product": "http://example.org/product#",
                "customer": "http://example.org/customer#",
                "order": "http://example.org/order#",
                "employee": "http://example.org/employee#"
            },
            "classes": [
                {
                    "name": "product:Product",
                    "properties": [
                        {"name": "product:name", "type": "xsd:string"},
                        {"name": "product:price", "type": "xsd:decimal"},
                        {"name": "product:category", "type": "xsd:string"},
                        {"name": "product:inStock", "type": "xsd:boolean"}
                    ]
                },
                {
                    "name": "customer:Customer",
                    "properties": [
                        {"name": "customer:name", "type": "xsd:string"},
                        {"name": "customer:email", "type": "xsd:string"},
                        {"name": "customer:hasOrder", "type": "order:Order"}
                    ]
                },
                {
                    "name": "order:Order",
                    "properties": [
                        {"name": "order:orderDate", "type": "xsd:dateTime"},
                        {"name": "order:status", "type": "xsd:string"},
                        {"name": "order:total", "type": "xsd:decimal"},
                        {"name": "order:hasItem", "type": "order:OrderItem"}
                    ]
                },
                {
                    "name": "order:OrderItem",
                    "properties": [
                        {"name": "order:product", "type": "product:Product"},
                        {"name": "order:quantity", "type": "xsd:integer"},
                        {"name": "order:price", "type": "xsd:decimal"}
                    ]
                },
                {
                    "name": "employee:Employee",
                    "properties": [
                        {"name": "employee:name", "type": "xsd:string"},
                        {"name": "employee:email", "type": "xsd:string"},
                        {"name": "employee:department", "type": "xsd:string"},
                        {"name": "employee:position", "type": "xsd:string"},
                        {"name": "employee:hireDate", "type": "xsd:dateTime"}
                    ]
                }
            ],
            "query_type": "SPARQL"
        }
    
    def get_name(self) -> str:
        """
        Get the name of the tool.
        
        Returns:
            The tool name
        """
        return "schema_information"
    
    def get_description(self) -> str:
        """
        Get a description of the tool.
        
        Returns:
            The tool description
        """
        return (
            "Retrieve schema information about data sources. "
            "This tool can be used to get information about the structure of "
            "the data sources, such as tables, columns, collections, fields, "
            "classes, and properties."
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
                "source_type": {
                    "type": "string",
                    "enum": ["erp", "document_storage", "knowledge_graph", "all"],
                    "description": "Type of data source to get schema information for"
                }
            }
        }
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the schema information tool.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "host": "localhost",
            "port": 8003
        }


class ToolRegistry:
    """
    Registry for agent tools.
    """
    
    def __init__(self):
        """
        Initialize the tool registry.
        """
        self._tools: Dict[str, Tool] = {}
    
    def register_tool(self, tool: Tool):
        """
        Register a tool.
        
        Args:
            tool: Tool to register
        """
        self._tools[tool.get_name()] = tool
        logger.info(f"Registered tool: {tool.get_name()}")
    
    def get_tool(self, name: str) -> Tool:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            The tool
            
        Raises:
            ValueError: If the tool is not registered
        """
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        
        return self._tools[name]
    
    def get_all_tools(self) -> List[Tool]:
        """
        Get all registered tools.
        
        Returns:
            List of tools
        """
        return list(self._tools.values())
    
    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """
        Get descriptions of all registered tools.
        
        Returns:
            List of tool descriptions
        """
        return [
            {
                "name": tool.get_name(),
                "description": tool.get_description(),
                "parameters": tool.get_parameter_schema()
            }
            for tool in self._tools.values()
        ]


def initialize_tools(
    host: str = "localhost",
    erp_port: int = 8001,
    config_path: Optional[str] = None
) -> List[Tool]:
    """
    Initialize the tools for the agent.
    
    Args:
        host: Host where the MCP servers are running
        erp_port: Port of the ERP MCP server
        config_path: Path to the configuration file
        
    Returns:
        List of initialized tools
    """
    # Initialize connectors
    erp_connector = ERPConnector(
        host=host,
        port=erp_port,
        config_path=config_path
    )
    
    # Initialize tools
    tools = [
        ERPQueryTool(erp_connector)
    ]
    
    return tools