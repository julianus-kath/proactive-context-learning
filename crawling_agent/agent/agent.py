"""
Agent implementation for the crawling agent.
"""
import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union

from crawling_agent.llm.provider import LLMProvider, LLMProviderFactory
from crawling_agent.agent.tool import Tool, ToolRegistry
from crawling_agent.agent.prompt import (
    SYSTEM_PROMPT,
    QUERY_ANALYSIS_PROMPT,
    TOOL_SELECTION_PROMPT,
    QUERY_GENERATION_PROMPT,
    RESULT_PROCESSING_PROMPT
)

# Configure logging
logger = logging.getLogger(__name__)


class Agent:
    """
    Agent implementation for the crawling agent.
    
    The agent uses an LLM to:
    1. Analyze natural language queries
    2. Select appropriate tools
    3. Generate structured queries
    4. Process and combine results
    """
    
    def __init__(self, llm_provider: LLMProvider, tool_registry: ToolRegistry):
        """
        Initialize the agent.
        
        Args:
            llm_provider: LLM provider to use
            tool_registry: Tool registry containing available tools
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        
        logger.info(f"Initialized agent with LLM provider: {llm_provider.get_provider_name()}")
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query.
        
        Args:
            query: Natural language query
            
        Returns:
            Query results and processing information
        """
        start_time = time.time()
        
        try:
            # Step 1: Analyze the query
            analysis = await self._analyze_query(query)
            logger.info(f"Query analysis: {analysis['intent']}")
            
            # Step 2: Select tools
            selected_tools = await self._select_tools(query, analysis)
            logger.info(f"Selected tools: {[tool['name'] for tool in selected_tools]}")
            
            # Step 3: Generate structured queries
            structured_queries = await self._generate_structured_queries(query, analysis, selected_tools)
            logger.info(f"Generated {len(structured_queries)} structured queries")
            
            # Step 4: Execute queries
            results = await self._execute_queries(structured_queries)
            logger.info(f"Executed {len(results)} queries")
            
            # Step 5: Process results
            processed_results = await self._process_results(query, analysis, results)
            logger.info("Processed results")
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the response
            response = {
                "query": query,
                "analysis": analysis,
                "structured_queries": structured_queries,
                "results": processed_results,
                "execution_time_ms": execution_time,
                "status": "success"
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Prepare the error response
            response = {
                "query": query,
                "execution_time_ms": execution_time,
                "status": "error",
                "error": str(e)
            }
            
            return response
    
    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a natural language query.
        
        Args:
            query: Natural language query
            
        Returns:
            Query analysis
        """
        # Prepare the prompt
        prompt = QUERY_ANALYSIS_PROMPT.format(query=query)
        
        # Define the output schema
        output_schema = {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "The main intent of the query"
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "Type of entity"
                            },
                            "value": {
                                "type": "string",
                                "description": "Value of entity"
                            }
                        }
                    },
                    "description": "Entities mentioned in the query"
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "description": "Field to filter on"
                            },
                            "operator": {
                                "type": "string",
                                "description": "Filter operator"
                            },
                            "value": {
                                "type": "string",
                                "description": "Filter value"
                            }
                        }
                    },
                    "description": "Filters mentioned in the query"
                },
                "data_sources": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["erp", "document_storage", "knowledge_graph"]
                    },
                    "description": "Data sources that might contain relevant information"
                },
                "thought_process": {
                    "type": "string",
                    "description": "Thought process used to analyze the query"
                }
            },
            "required": ["intent", "entities", "filters", "data_sources", "thought_process"]
        }
        
        # Generate the analysis
        analysis = await self.llm_provider.generate_with_json_output(
            prompt=prompt,
            output_schema=output_schema,
            system_message=SYSTEM_PROMPT,
            temperature=0.2
        )
        
        return analysis
    
    async def _select_tools(self, query: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Select tools to use for the query.
        
        Args:
            query: Natural language query
            analysis: Query analysis
            
        Returns:
            Selected tools
        """
        # Get tool descriptions
        tool_descriptions = self.tool_registry.get_tool_descriptions()
        
        # Prepare the prompt
        prompt = TOOL_SELECTION_PROMPT.format(
            query=query,
            analysis=json.dumps(analysis, indent=2),
            tools=json.dumps(tool_descriptions, indent=2)
        )
        
        # Define the output schema
        output_schema = {
            "type": "object",
            "properties": {
                "selected_tools": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the selected tool"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for selecting this tool"
                            }
                        }
                    },
                    "description": "Tools selected for the query"
                },
                "thought_process": {
                    "type": "string",
                    "description": "Thought process used to select tools"
                }
            },
            "required": ["selected_tools", "thought_process"]
        }
        
        # Generate the tool selection
        tool_selection = await self.llm_provider.generate_with_json_output(
            prompt=prompt,
            output_schema=output_schema,
            system_message=SYSTEM_PROMPT,
            temperature=0.2
        )
        
        return tool_selection["selected_tools"]
    
    async def _generate_structured_queries(self, 
                                          query: str, 
                                          analysis: Dict[str, Any], 
                                          selected_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate structured queries for the selected tools.
        
        Args:
            query: Natural language query
            analysis: Query analysis
            selected_tools: Selected tools
            
        Returns:
            Structured queries
        """
        structured_queries = []
        
        # Get schema information
        schema_tool = self.tool_registry.get_tool("schema_information")
        schema_info = await schema_tool.run({"source_type": "all"})
        
        # For each selected tool, generate a structured query
        for tool_info in selected_tools:
            tool_name = tool_info["name"]
            tool = self.tool_registry.get_tool(tool_name)
            
            # Get the schema for the data source
            source_type = None
            if "erp" in tool_name:
                source_type = "erp"
            elif "document_storage" in tool_name:
                source_type = "document_storage"
            elif "knowledge_graph" in tool_name:
                source_type = "knowledge_graph"
            
            source_schema = schema_info["schemas"].get(source_type, {}) if source_type else {}
            
            # Prepare the prompt
            prompt = QUERY_GENERATION_PROMPT.format(
                query=query,
                analysis=json.dumps(analysis, indent=2),
                tool=json.dumps(tool_info, indent=2),
                tool_parameters=json.dumps(tool.get_parameter_schema(), indent=2),
                schema=json.dumps(source_schema, indent=2)
            )
            
            # Define the output schema
            output_schema = {
                "type": "object",
                "properties": {
                    "parameters": {
                        "type": "object",
                        "description": "Parameters for the tool"
                    },
                    "thought_process": {
                        "type": "string",
                        "description": "Thought process used to generate the query"
                    }
                },
                "required": ["parameters", "thought_process"]
            }
            
            # Generate the structured query
            structured_query = await self.llm_provider.generate_with_json_output(
                prompt=prompt,
                output_schema=output_schema,
                system_message=SYSTEM_PROMPT,
                temperature=0.2
            )
            
            # Add the tool name to the structured query
            structured_query["tool_name"] = tool_name
            
            structured_queries.append(structured_query)
        
        return structured_queries
    
    async def _execute_queries(self, structured_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute structured queries.
        
        Args:
            structured_queries: Structured queries
            
        Returns:
            Query results
        """
        results = []
        
        # Execute each query
        for query in structured_queries:
            tool_name = query["tool_name"]
            parameters = query["parameters"]
            
            try:
                # Get the tool
                tool = self.tool_registry.get_tool(tool_name)
                
                # Execute the query
                result = await tool.run(parameters)
                
                # Add the tool name and parameters to the result
                result["tool_name"] = tool_name
                result["parameters"] = parameters
                result["thought_process"] = query["thought_process"]
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error executing query with tool {tool_name}: {str(e)}")
                
                # Add the error to the results
                results.append({
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "thought_process": query.get("thought_process", ""),
                    "error": str(e),
                    "status": "error"
                })
        
        return results
    
    async def _process_results(self, 
                              query: str, 
                              analysis: Dict[str, Any], 
                              results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process and combine query results.
        
        Args:
            query: Natural language query
            analysis: Query analysis
            results: Query results
            
        Returns:
            Processed results
        """
        # Prepare the prompt
        prompt = RESULT_PROCESSING_PROMPT.format(
            query=query,
            analysis=json.dumps(analysis, indent=2),
            results=json.dumps(results, indent=2)
        )
        
        # Define the output schema
        output_schema = {
            "type": "object",
            "properties": {
                "combined_results": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    },
                    "description": "Combined results from all data sources"
                },
                "summary": {
                    "type": "string",
                    "description": "Summary of the results"
                },
                "thought_process": {
                    "type": "string",
                    "description": "Thought process used to process the results"
                }
            },
            "required": ["combined_results", "summary", "thought_process"]
        }
        
        # Generate the processed results
        processed_results = await self.llm_provider.generate_with_json_output(
            prompt=prompt,
            output_schema=output_schema,
            system_message=SYSTEM_PROMPT,
            temperature=0.2
        )
        
        return processed_results