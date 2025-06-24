"""
Multi-Source Reasoning Agent implementation.

This module provides an implementation of an agent that can reason across multiple data sources.
"""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from crawling_agent.agent.base_agent import BaseAgent
from crawling_agent.connectors.mcp_erp_connector import MCPERPConnector
from crawling_agent.connectors.mcp_document_storage_connector import MCPDocumentStorageConnector
from crawling_agent.connectors.mcp_knowledge_graph_connector import MCPKnowledgeGraphConnector
from crawling_agent.llm.base_llm_client import BaseLLMClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MultiSourceAgent")


class MultiSourceAgent(BaseAgent):
    """
    Agent that can reason across multiple data sources.
    
    This agent integrates data from ERP, document storage, and knowledge graph sources.
    """
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        erp_connector: MCPERPConnector,
        document_connector: MCPDocumentStorageConnector,
        knowledge_connector: MCPKnowledgeGraphConnector,
        system_prompt: Optional[str] = None,
        max_reasoning_steps: int = 5,
        debug: bool = False,
    ):
        """
        Initialize the multi-source agent.
        
        Args:
            llm_client: The LLM client to use
            erp_connector: The ERP connector
            document_connector: The document storage connector
            knowledge_connector: The knowledge graph connector
            system_prompt: Optional system prompt (if None, a default will be used)
            max_reasoning_steps: Maximum number of reasoning steps (default: 5)
            debug: Whether to enable debug mode (default: False)
        """
        # Use default system prompt if none provided
        if system_prompt is None:
            system_prompt = self._get_default_system_prompt()
        
        super().__init__(
            llm_client=llm_client,
            system_prompt=system_prompt,
            debug=debug,
        )
        
        self.erp_connector = erp_connector
        self.document_connector = document_connector
        self.knowledge_connector = knowledge_connector
        self.max_reasoning_steps = max_reasoning_steps
        
        # Register the available tools
        self.tools = self._register_tools()
        
        logger.info("Initialized multi-source agent")
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")
    
    def _get_default_system_prompt(self) -> str:
        """
        Get the default system prompt.
        
        Returns:
            The default system prompt
        """
        return """
        You are an advanced reasoning agent that can analyze complex queries, identify required data sources, and integrate information to provide comprehensive answers.
        
        You have access to the following data sources:
        
        1. ERP Database: Contains structured business data like customers, orders, products, etc.
        2. Document Storage: Contains unstructured documents like reports, emails, etc.
        3. Knowledge Graph: Contains relationships between entities like people, organizations, etc.
        
        Your workflow for processing queries:
        
        1. INTENT IDENTIFICATION: Carefully analyze the user's natural language query to understand their intent and information needs.
        
        2. DATA SOURCE SELECTION: Determine which data sources are necessary to fulfill the query. Consider:
           - Which sources contain the primary data needed
           - Which sources contain supplementary information
           - How the data from different sources will need to be combined
        
        3. QUERY FORMULATION: For each relevant data source, create appropriate queries:
           - For ERP: Construct precise SQL queries to extract relevant structured data
           - For Document Storage: Create NoSQL queries to retrieve relevant documents
           - For Knowledge Graph: Develop graph queries to explore entity relationships
        
        4. DATA INTEGRATION: Combine and synthesize information from multiple sources:
           - Merge related data from different sources
           - Resolve any inconsistencies or conflicts
           - Transform raw data into meaningful insights
        
        5. RESPONSE GENERATION: Provide a clear, comprehensive answer that:
           - Directly addresses the user's query
           - Presents information in a structured, easy-to-understand format
           - Includes relevant context and supporting details
           - Cites the specific data sources used
        
        Always explain your reasoning process and the steps you took to arrive at your answer.
        If you don't have enough information to answer a query completely, explain what additional information would be needed and why.
        """
    
    def _register_tools(self) -> List[Dict[str, Any]]:
        """
        Register the available tools.
        
        Returns:
            A list of tool definitions
        """
        return [
            # ERP tools
            {
                "type": "function",
                "function": {
                    "name": "execute_sql_query",
                    "description": "Execute a SQL query against the ERP database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The SQL query to execute"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_table_schema",
                    "description": "Get the schema for a specific table in the ERP database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "The name of the table"
                            }
                        },
                        "required": ["table_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tables",
                    "description": "List all tables in the ERP database",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            
            # Document Storage tools
            {
                "type": "function",
                "function": {
                    "name": "find_documents",
                    "description": "Find documents in the document storage",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "collection": {
                                "type": "string",
                                "description": "The collection to search in"
                            },
                            "query": {
                                "type": "string",
                                "description": "The query to execute (JSON string)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "The maximum number of documents to return"
                            }
                        },
                        "required": ["collection", "query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_collections",
                    "description": "List all collections in the document storage",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_collection_info",
                    "description": "Get information about a specific collection in the document storage",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "collection": {
                                "type": "string",
                                "description": "The name of the collection"
                            }
                        },
                        "required": ["collection"]
                    }
                }
            },
            
            # Knowledge Graph tools
            {
                "type": "function",
                "function": {
                    "name": "query_nodes",
                    "description": "Query nodes in the knowledge graph",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "node_type": {
                                "type": "string",
                                "description": "The type of nodes to query"
                            },
                            "properties": {
                                "type": "string",
                                "description": "The properties to filter on (JSON string)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "The maximum number of nodes to return"
                            }
                        },
                        "required": ["node_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_relationships",
                    "description": "Query relationships in the knowledge graph",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_node_type": {
                                "type": "string",
                                "description": "The type of the start node"
                            },
                            "relationship_type": {
                                "type": "string",
                                "description": "The type of relationship"
                            },
                            "end_node_type": {
                                "type": "string",
                                "description": "The type of the end node"
                            },
                            "properties": {
                                "type": "string",
                                "description": "The properties to filter on (JSON string)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "The maximum number of relationships to return"
                            }
                        },
                        "required": ["start_node_type", "relationship_type", "end_node_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_node_types",
                    "description": "Get all node types in the knowledge graph",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_relationship_types",
                    "description": "Get all relationship types in the knowledge graph",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
    
    async def process_query(self, query: str) -> str:
        """
        Process a user query and return a response.
        
        Args:
            query: The user query
            
        Returns:
            The agent's response
        """
        logger.info(f"Processing query: {query}")
        
        # Add the user query to the conversation history
        self.add_message_to_history("user", query)
        
        # Start the reasoning loop
        response = await self._reasoning_loop()
        
        # Add the final response to the conversation history
        self.add_message_to_history("assistant", response)
        
        return response
    
    async def _reasoning_loop(self) -> str:
        """
        Execute the reasoning loop.
        
        This method implements a loop that:
        1. Generates tool calls using the LLM
        2. Executes the tool calls
        3. Adds the results to the conversation history
        4. Repeats until the LLM generates a final response or the maximum number of steps is reached
        
        Returns:
            The final response from the LLM
        """
        logger.info("Starting reasoning loop")
        
        for step in range(self.max_reasoning_steps):
            logger.info(f"Reasoning step {step + 1}/{self.max_reasoning_steps}")
            
            # Generate tool calls or a final response
            response = await self.llm_client.generate_tool_calls(
                messages=self.conversation_history,
                tools=self.tools,
            )
            
            # Check if the response contains tool calls
            if "tool_calls" in response:
                logger.info(f"Generated {len(response['tool_calls'])} tool calls")
                
                # Add the assistant's message with tool calls to the conversation history
                # Ensure content is a string, defaulting to empty string if None
                content = response.get("content", "") or ""
                
                # Create a message with tool calls
                assistant_message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": response["tool_calls"]
                }
                
                # Add the message directly to the conversation history
                self.conversation_history.append(assistant_message)
                
                if self.debug:
                    logger.debug(f"Added message to history - Role: assistant")
                    logger.debug(f"Content: {content}")
                    logger.debug(f"Tool calls: {len(response['tool_calls'])}")
                
                # Execute each tool call
                for tool_call in response["tool_calls"]:
                    if tool_call["type"] != "function":
                        logger.warning(f"Unsupported tool call type: {tool_call['type']}")
                        continue
                    
                    function_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"Executing tool call: {function_name}")
                    if self.debug:
                        logger.debug(f"Tool call arguments: {arguments}")
                    
                    # Execute the tool call
                    result = await self._execute_tool_call(function_name, arguments)
                    
                    # Add the tool result to the conversation history
                    self.add_tool_result_to_history(function_name, result)
            else:
                # No tool calls, just a final response
                logger.info("Generated final response")
                return response.get("content", "")
        
        # If we've reached the maximum number of steps, generate a final response
        logger.info("Reached maximum number of reasoning steps, generating final response")
        
        response = await self.llm_client.generate_response(
            messages=self.conversation_history,
        )
        
        return response.get("content", "")
    
    async def _execute_tool_call(self, function_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool call.
        
        Args:
            function_name: The name of the function to call
            arguments: The arguments to pass to the function
            
        Returns:
            The result of the tool call as a string
            
        Raises:
            ValueError: If the function name is not recognized
        """
        try:
            # ERP tools
            if function_name == "execute_sql_query":
                query = arguments["query"]
                try:
                    # Connect to the ERP server
                    await self.erp_connector.connect()
                    # Execute the query
                    result = await self.erp_connector.execute_sql_query(query)
                    # Disconnect from the ERP server
                    await self.erp_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error executing SQL query: {str(e)}")
                    return json.dumps({"error": f"Error executing SQL query: {str(e)}"})
            
            elif function_name == "get_table_schema":
                table_name = arguments["table_name"]
                try:
                    # Connect to the ERP server
                    await self.erp_connector.connect()
                    # Get the table schema
                    result = await self.erp_connector.get_table_schema(table_name)
                    # Disconnect from the ERP server
                    await self.erp_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error getting table schema: {str(e)}")
                    return json.dumps({"error": f"Error getting table schema: {str(e)}"})
            
            elif function_name == "list_tables":
                try:
                    # Connect to the ERP server
                    await self.erp_connector.connect()
                    # List the tables
                    result = await self.erp_connector.list_tables()
                    # Disconnect from the ERP server
                    await self.erp_connector.disconnect()
                    return json.dumps({"tables": result})
                except Exception as e:
                    import traceback
                    logger.error(f"Error listing tables: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return json.dumps({"error": f"Error listing tables: {str(e)}"})
            
            # Document Storage tools
            elif function_name == "find_documents":
                collection = arguments["collection"]
                query = arguments["query"]
                limit = arguments.get("limit", 10)
                try:
                    # Connect to the Document Storage server
                    await self.document_connector.connect()
                    # Find documents
                    result = await self.document_connector.find_documents(collection, query, limit)
                    # Disconnect from the Document Storage server
                    await self.document_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error finding documents: {str(e)}")
                    return json.dumps({"error": f"Error finding documents: {str(e)}"})
            
            elif function_name == "list_collections":
                try:
                    # Connect to the Document Storage server
                    await self.document_connector.connect()
                    # List collections
                    result = await self.document_connector.list_collections()
                    # Disconnect from the Document Storage server
                    await self.document_connector.disconnect()
                    return json.dumps({"collections": result})
                except Exception as e:
                    logger.error(f"Error listing collections: {str(e)}")
                    return json.dumps({"error": f"Error listing collections: {str(e)}"})
            
            elif function_name == "get_collection_info":
                collection = arguments["collection"]
                try:
                    # Connect to the Document Storage server
                    await self.document_connector.connect()
                    # Get collection info
                    result = await self.document_connector.get_collection_info(collection)
                    # Disconnect from the Document Storage server
                    await self.document_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error getting collection info: {str(e)}")
                    return json.dumps({"error": f"Error getting collection info: {str(e)}"})
            
            # Knowledge Graph tools
            elif function_name == "query_nodes":
                node_type = arguments["node_type"]
                properties = arguments.get("properties", "{}")
                limit = arguments.get("limit", 10)
                try:
                    # Connect to the Knowledge Graph server
                    await self.knowledge_connector.connect()
                    # Query nodes
                    result = await self.knowledge_connector.query_nodes(node_type, properties, limit)
                    # Disconnect from the Knowledge Graph server
                    await self.knowledge_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error querying nodes: {str(e)}")
                    return json.dumps({"error": f"Error querying nodes: {str(e)}"})
            
            elif function_name == "query_relationships":
                start_node_type = arguments["start_node_type"]
                relationship_type = arguments["relationship_type"]
                end_node_type = arguments["end_node_type"]
                properties = arguments.get("properties", "{}")
                limit = arguments.get("limit", 10)
                try:
                    # Connect to the Knowledge Graph server
                    await self.knowledge_connector.connect()
                    # Query relationships
                    result = await self.knowledge_connector.query_relationships(
                        start_node_type, relationship_type, end_node_type, properties, limit
                    )
                    # Disconnect from the Knowledge Graph server
                    await self.knowledge_connector.disconnect()
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f"Error querying relationships: {str(e)}")
                    return json.dumps({"error": f"Error querying relationships: {str(e)}"})
            
            elif function_name == "get_node_types":
                try:
                    # Connect to the Knowledge Graph server
                    await self.knowledge_connector.connect()
                    # Get node types
                    result = await self.knowledge_connector.get_node_types()
                    # Disconnect from the Knowledge Graph server
                    await self.knowledge_connector.disconnect()
                    return json.dumps({"node_types": result})
                except Exception as e:
                    logger.error(f"Error getting node types: {str(e)}")
                    return json.dumps({"error": f"Error getting node types: {str(e)}"})
            
            elif function_name == "get_relationship_types":
                try:
                    # Connect to the Knowledge Graph server
                    await self.knowledge_connector.connect()
                    # Get relationship types
                    result = await self.knowledge_connector.get_relationship_types()
                    # Disconnect from the Knowledge Graph server
                    await self.knowledge_connector.disconnect()
                    return json.dumps({"relationship_types": result})
                except Exception as e:
                    logger.error(f"Error getting relationship types: {str(e)}")
                    return json.dumps({"error": f"Error getting relationship types: {str(e)}"})
            
            else:
                error_msg = f"Unknown function: {function_name}"
                logger.error(error_msg)
                return json.dumps({"error": error_msg})
        
        except Exception as e:
            error_msg = f"Error executing {function_name}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})