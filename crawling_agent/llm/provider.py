"""
Abstract LLM provider interface and implementations.
"""
import os
import json
import abc
import logging
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


class LLMProvider(abc.ABC):
    """
    Abstract base class for LLM providers.
    
    This interface defines the common methods that all LLM providers must implement,
    allowing the agent to use different LLM backends interchangeably.
    """
    
    @abc.abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the LLM provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        pass
    
    @abc.abstractmethod
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a completion for the given prompt.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The generated text
        """
        pass
    
    @abc.abstractmethod
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a completion with structured JSON output.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            The generated output as a Python dictionary
        """
        pass
    
    @abc.abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        pass
    
    @abc.abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        pass
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for this provider.
        
        Returns:
            Default configuration dictionary
        """
        return {}


class OpenAIProvider(LLMProvider):
    """
    OpenAI API implementation of the LLM provider interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the OpenAI provider.
        
        Args:
            config: Configuration dictionary with the following keys:
                - api_key: OpenAI API key (required)
                - model: Model to use (default: "gpt-4")
                - organization: OpenAI organization ID (optional)
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "The OpenAI package is required to use the OpenAI provider. "
                "Please install it with `pip install openai`."
            )
        
        # Get API key from config or environment variable
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Provide it in the config or "
                "set the OPENAI_API_KEY environment variable."
            )
        
        # Get organization ID from config or environment variable
        self.organization = config.get("organization") or os.environ.get("OPENAI_ORGANIZATION")
        
        # Get model from config, environment variable, or use default
        self.model = config.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4")
        
        # Initialize the client
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            organization=self.organization
        )
        
        logger.info(f"Initialized OpenAI provider with model: {self.model}")
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a completion using the OpenAI API.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The generated text
        """
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # Add user prompt
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating completion with OpenAI: {str(e)}")
            raise
    
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a completion with structured JSON output using the OpenAI API.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            The generated output as a Python dictionary
        """
        if not system_message:
            system_message = "You are a helpful assistant that always responds in JSON format."
        else:
            system_message += "\n\nYou must respond in JSON format."
        
        # Add schema information to the prompt
        schema_prompt = f"\n\nYour response must conform to the following JSON schema:\n{json.dumps(output_schema, indent=2)}"
        full_prompt = prompt + schema_prompt
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from OpenAI response: {str(e)}")
            logger.error(f"Raw response: {content}")
            raise
            
        except Exception as e:
            logger.error(f"Error generating JSON completion with OpenAI: {str(e)}")
            raise
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        return "openai"
    
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        return self.model
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the OpenAI provider.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "model": "gpt-4",
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
            "organization": os.environ.get("OPENAI_ORGANIZATION", "")
        }


class MockProvider(LLMProvider):
    """
    Mock LLM provider for testing purposes.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the mock provider.
        
        Args:
            config: Configuration dictionary with the following keys:
                - responses: Dictionary mapping prompts to responses (optional)
                - default_response: Default response for prompts not in responses (optional)
        """
        self.responses = config.get("responses", {})
        self.default_response = config.get("default_response", "This is a mock response.")
        self.model = config.get("model", "mock-model")
        logger.info("Initialized Mock LLM provider")
    
    async def generate(self, 
                      prompt: str, 
                      system_message: Optional[str] = None,
                      temperature: float = 0.7, 
                      max_tokens: Optional[int] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """
        Generate a mock completion.
        
        Args:
            prompt: The prompt to generate a completion for
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            stop_sequences: Optional list of sequences where the model should stop generating
            
        Returns:
            The mock response
        """
        # Log the prompt for debugging
        logger.info(f"Mock provider received prompt: {prompt[:100]}...")
        
        # Check if we have a predefined response for this prompt
        for pattern, response in self.responses.items():
            if pattern in prompt:
                logger.info(f"Using predefined response for pattern: {pattern}")
                return response
        
        # Generate a more helpful default response based on the prompt
        if "analyze" in prompt.lower() or "analysis" in prompt.lower():
            return "I've analyzed the query and identified that it's asking about business data that would be stored in our ERP system. The main entities involved are likely products, customers, or orders."
        elif "select tool" in prompt.lower() or "tool selection" in prompt.lower():
            return "Based on the query, I recommend using the ERP query tool since it contains the structured business data we need to answer this question."
        elif "generate" in prompt.lower() and "query" in prompt.lower():
            if "customer" in prompt.lower():
                return "SELECT COUNT(*) as count FROM customers;"
            elif "product" in prompt.lower() and "expensive" in prompt.lower():
                return "SELECT * FROM products WHERE price > 1000 ORDER BY price DESC LIMIT 10;"
            elif "employee" in prompt.lower() and "sales" in prompt.lower():
                return "SELECT * FROM employees WHERE department = 'Sales';"
            elif "order" in prompt.lower() and "complete" in prompt.lower():
                return "SELECT * FROM orders WHERE status = 'Completed';"
            else:
                return "SELECT * FROM products LIMIT 10;"
        elif "process" in prompt.lower() and "result" in prompt.lower():
            return "I've processed the results and formatted them in a way that directly answers the original query."
        
        return self.default_response
    
    async def generate_with_json_output(self, 
                                       prompt: str, 
                                       output_schema: Dict[str, Any],
                                       system_message: Optional[str] = None,
                                       temperature: float = 0.2) -> Dict[str, Any]:
        """
        Generate a mock JSON completion.
        
        Args:
            prompt: The prompt to generate a completion for
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            A mock JSON response
        """
        # Log the prompt for debugging
        logger.info(f"Mock provider received JSON prompt: {prompt[:100]}...")
        
        # Generate more realistic responses based on the prompt content
        prompt_lower = prompt.lower()
        
        # Query Analysis Task
        if "query analysis task" in prompt_lower:
            # Extract the query from the prompt
            query = None
            if '"{query}"' in prompt:
                parts = prompt.split('"{query}"')
                if len(parts) > 1:
                    query_parts = parts[1].split('"')
                    if len(query_parts) > 1:
                        query = query_parts[0].strip()
            
            if not query:
                query = "unknown query"
                
            logger.info(f"Analyzing query: {query}")
            
            # Generate a dynamic analysis based on the query
            result = {
                "intent": "retrieve_information",
                "entities": [],
                "filters": [],
                "data_sources": [],
                "thought_process": f"I need to analyze what the user is asking for in '{query}' and determine which data sources would have this information."
            }
            
            # Identify entities and data sources based on the query
            query_lower = query.lower()
            
            # Check for common entities
            if "customer" in query_lower or "client" in query_lower:
                result["entities"].append({"type": "entity", "value": "customer"})
                result["data_sources"].append("erp")
            
            if "product" in query_lower or "item" in query_lower:
                result["entities"].append({"type": "entity", "value": "product"})
                result["data_sources"].append("erp")
                
            if "order" in query_lower or "purchase" in query_lower:
                result["entities"].append({"type": "entity", "value": "order"})
                result["data_sources"].append("erp")
                
            if "employee" in query_lower or "staff" in query_lower:
                result["entities"].append({"type": "entity", "value": "employee"})
                result["data_sources"].append("erp")
                
            if "document" in query_lower or "file" in query_lower or "report" in query_lower:
                result["entities"].append({"type": "entity", "value": "document"})
                result["data_sources"].append("document_storage")
                
            if "concept" in query_lower or "relationship" in query_lower or "connection" in query_lower:
                result["entities"].append({"type": "entity", "value": "concept"})
                result["data_sources"].append("knowledge_graph")
                
            # Check for common filters
            if "expensive" in query_lower or "high price" in query_lower:
                result["filters"].append({
                    "field": "price", 
                    "operator": "greater_than", 
                    "value": "1000"
                })
                
            if "cheap" in query_lower or "low price" in query_lower:
                result["filters"].append({
                    "field": "price", 
                    "operator": "less_than", 
                    "value": "100"
                })
                
            if "completed" in query_lower or "finished" in query_lower:
                result["filters"].append({
                    "field": "status", 
                    "operator": "equals", 
                    "value": "Completed"
                })
                
            if "sales" in query_lower:
                result["filters"].append({
                    "field": "department", 
                    "operator": "equals", 
                    "value": "Sales"
                })
                
            # If no specific data sources were identified, default to ERP
            if not result["data_sources"]:
                result["data_sources"].append("erp")
                
            # Update the thought process
            entities_str = ", ".join([e["value"] for e in result["entities"]])
            sources_str = ", ".join(result["data_sources"])
            result["thought_process"] = f"The query '{query}' appears to be asking about {entities_str or 'general business data'}. This information would likely be found in the {sources_str} data source(s). I've identified relevant entities and filters to help construct an appropriate structured query."
            
            return result
            
        # Tool Selection Task
        elif "tool selection task" in prompt_lower:
            # Determine which tools to use based on the data sources mentioned
            data_sources = []
            if "erp" in prompt_lower:
                data_sources.append("erp")
            if "document" in prompt_lower:
                data_sources.append("document_storage")
            if "knowledge" in prompt_lower:
                data_sources.append("knowledge_graph")
                
            # Default to ERP if no data sources were identified
            if not data_sources:
                data_sources.append("erp")
                
            # Create the tool selection response
            selected_tools = []
            
            if "erp" in data_sources:
                selected_tools.append({
                    "name": "erp_query",
                    "reason": "The query is asking about business data that would be stored in the ERP system."
                })
                
            if "document_storage" in data_sources:
                selected_tools.append({
                    "name": "document_storage_query",
                    "reason": "The query is asking about documents or unstructured data that would be stored in the document storage system."
                })
                
            if "knowledge_graph" in data_sources:
                selected_tools.append({
                    "name": "knowledge_graph_query",
                    "reason": "The query is asking about relationships or concepts that would be represented in the knowledge graph."
                })
                
            return {
                "selected_tools": selected_tools,
                "thought_process": "Based on the query analysis, I need to select the appropriate tools to retrieve the requested information. I've chosen tools that can access the data sources containing the relevant information."
            }
            
        # Query Generation Task
        elif "structured query generation task" in prompt_lower:
            # Extract the tool name from the prompt
            tool_name = None
            if "erp_query" in prompt_lower:
                tool_name = "erp_query"
            elif "document_storage_query" in prompt_lower:
                tool_name = "document_storage_query"
            elif "knowledge_graph_query" in prompt_lower:
                tool_name = "knowledge_graph_query"
            else:
                tool_name = "unknown_tool"
                
            # Generate a query based on the tool and the content of the prompt
            parameters = {}
            thought_process = "I need to generate a structured query that will retrieve the information requested in the natural language query."
            
            if tool_name == "erp_query":
                # Generate an SQL query based on the prompt content
                sql_query = "SELECT * FROM "
                
                if "customer" in prompt_lower:
                    sql_query += "customers"
                    if "count" in prompt_lower:
                        sql_query = "SELECT COUNT(*) as count FROM customers"
                elif "product" in prompt_lower:
                    sql_query += "products"
                    if "expensive" in prompt_lower:
                        sql_query += " WHERE price > 1000 ORDER BY price DESC LIMIT 10"
                elif "employee" in prompt_lower:
                    sql_query += "employees"
                    if "sales" in prompt_lower:
                        sql_query += " WHERE department = 'Sales'"
                elif "order" in prompt_lower:
                    sql_query += "orders"
                    if "completed" in prompt_lower:
                        sql_query += " WHERE status = 'Completed'"
                else:
                    sql_query += "products LIMIT 10"
                    
                parameters = {
                    "query": sql_query,
                    "parameters": {}
                }
                
                thought_process = f"I've generated an SQL query ({sql_query}) that should retrieve the data needed to answer the original question. This query targets the appropriate tables in the ERP database and includes any necessary filters or sorting."
                
            elif tool_name == "document_storage_query":
                # Generate a MongoDB query based on the prompt content
                mongo_query = {}
                collection = "documents"
                
                if "report" in prompt_lower:
                    mongo_query = {"type": "report"}
                    collection = "reports"
                elif "invoice" in prompt_lower:
                    mongo_query = {"type": "invoice"}
                    collection = "invoices"
                elif "contract" in prompt_lower:
                    mongo_query = {"type": "contract"}
                    collection = "contracts"
                    
                parameters = {
                    "query": json.dumps(mongo_query),
                    "collection": collection
                }
                
                thought_process = f"I've generated a MongoDB query that should retrieve the documents needed to answer the original question. This query targets the {collection} collection and includes appropriate filters."
                
            elif tool_name == "knowledge_graph_query":
                # Generate a SPARQL query based on the prompt content
                sparql_query = "SELECT ?subject ?predicate ?object WHERE { ?subject ?predicate ?object . "
                
                if "product" in prompt_lower and "category" in prompt_lower:
                    sparql_query += "?subject rdf:type :Product . ?subject :hasCategory ?object . "
                elif "customer" in prompt_lower and "order" in prompt_lower:
                    sparql_query += "?subject rdf:type :Customer . ?subject :hasPlaced ?object . ?object rdf:type :Order . "
                
                sparql_query += "} LIMIT 10"
                
                parameters = {
                    "query": sparql_query
                }
                
                thought_process = f"I've generated a SPARQL query that should retrieve the relationships needed to answer the original question. This query explores the relevant connections in the knowledge graph."
                
            return {
                "parameters": parameters,
                "thought_process": thought_process
            }
            
        # Result Processing Task
        elif "result processing task" in prompt_lower:
            # Process the results based on the query
            return {
                "processed_results": [
                    {"summary": "Based on the query results, I've found the information you requested."}
                ],
                "thought_process": "I've processed the raw data returned from the data sources and formatted it in a way that directly answers the original query. I've combined results from multiple sources where necessary and highlighted the most relevant information."
            }
            
        # Default response
        else:
            # For testing, return a simple JSON that matches the schema
            if "properties" in output_schema:
                result = {}
                for prop, details in output_schema["properties"].items():
                    if details.get("type") == "string":
                        result[prop] = f"Dynamic {prop} based on the query"
                    elif details.get("type") == "number" or details.get("type") == "integer":
                        result[prop] = 42
                    elif details.get("type") == "boolean":
                        result[prop] = True
                    elif details.get("type") == "array":
                        result[prop] = []
                    elif details.get("type") == "object":
                        result[prop] = {}
                    else:
                        result[prop] = None
                return result
            
            return {"result": "This is a dynamic JSON response based on your query."}
    
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.
        
        Returns:
            The provider name
        """
        return "mock"
    
    def get_model_name(self) -> str:
        """
        Get the name of the model being used.
        
        Returns:
            The model name
        """
        return self.model
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """
        Get the default configuration for the mock provider.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "model": "mock-model",
            "responses": {},
            "default_response": "This is a mock response."
        }


class LLMProviderFactory:
    """
    Factory for creating LLM providers.
    """
    
    _providers = {
        "openai": OpenAIProvider,
        "mock": MockProvider
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new LLM provider.
        
        Args:
            name: Provider name
            provider_class: Provider class
        """
        cls._providers[name] = provider_class
    
    @classmethod
    def create(cls, provider_name: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            provider_name: Name of the provider to create
            config: Provider-specific configuration
            
        Returns:
            An instance of the specified LLM provider
            
        Raises:
            ValueError: If the provider is not registered
        """
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
        
        provider_class = cls._providers[provider_name]
        
        # Use default config if none provided
        if config is None:
            config = provider_class.get_default_config()
        
        return provider_class(config)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get a list of available provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())