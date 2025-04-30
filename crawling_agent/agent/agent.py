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
    RESULT_PROCESSING_PROMPT,
    ANSWER_GENERATION_PROMPT
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
        self.progress_callback = None
        
        logger.info(f"Initialized agent with LLM provider: {llm_provider.get_provider_name()}")
    
    def set_progress_callback(self, callback: callable):
        """
        Set a callback function to receive progress updates during query processing.
        
        Args:
            callback: A callable that accepts a dictionary with progress information
        """
        self.progress_callback = callback
    
    def _emit_progress(self, step: str, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Emit a progress update.
        
        Args:
            step: The current processing step
            message: A human-readable message describing the progress
            details: Optional additional details about the progress
        """
        if self.progress_callback:
            progress_info = {
                "timestamp": time.time(),
                "step": step,
                "message": message,
                "details": details or {}
            }
            self.progress_callback(progress_info)
            
        # Also log the progress
        logger.info(f"Progress [{step}]: {message}")
    
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
            # Initialize the complete thought process
            complete_thought_process = []
            
            # Emit initial progress update
            self._emit_progress("start", "Starting query processing", {"query": query})
            
            # Step 1: Analyze the query
            analysis = await self._analyze_query(query)
            
            # Log detailed analysis information
            intent = analysis.get('intent', 'unknown')
            entities = [e.get('value', 'unknown') for e in analysis.get('entities', [])]
            data_sources = analysis.get('data_sources', [])
            
            logger.info(f"Query analysis - Intent: {intent}, Entities: {entities}, Data sources: {data_sources}")
            
            # Add analysis thought process to complete thought process
            complete_thought_process.append(analysis['thought_process'])
            
            # Step 2: Select tools
            selected_tools = await self._select_tools(query, analysis)
            logger.info(f"Selected tools: {[tool['name'] for tool in selected_tools]}")
            
            # Step 3: Generate structured queries
            structured_queries = await self._generate_structured_queries(query, analysis, selected_tools)
            logger.info(f"Generated {len(structured_queries)} structured queries")
            
            # Step 4: Execute queries
            results = await self._execute_queries(structured_queries)
            
            # Log which queries were executed vs. skipped
            executed_queries = [r for r in results if r.get('status') != 'skipped']
            skipped_queries = [r for r in results if r.get('status') == 'skipped']
            
            logger.info(f"Executed {len(executed_queries)} queries, skipped {len(skipped_queries)} queries")
            
            # Log the names of executed and skipped tools
            executed_tools = [r.get('tool_name', 'unknown') for r in executed_queries]
            skipped_tools = [r.get('tool_name', 'unknown') for r in skipped_queries]
            
            if executed_tools:
                logger.info(f"Executed tools: {executed_tools}")
            if skipped_tools:
                logger.info(f"Skipped tools: {skipped_tools}")
            
            # Step 5: Process results
            processed_results = await self._process_results(query, analysis, results)
            logger.info("Processed results")
            
            # Add results processing thought process to complete thought process
            if isinstance(processed_results, dict) and "thought_process" in processed_results:
                complete_thought_process.append(processed_results["thought_process"])
            
            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # in milliseconds
            
            # Combine all thought processes into a single string
            combined_thought_process = "\n\n".join(complete_thought_process)
            
            # Prepare the response
            response = {
                "query": query,
                "analysis": analysis,
                "structured_queries": structured_queries,
                "results": processed_results,
                "execution_time_ms": execution_time,
                "status": "success",
                "complete_thought_process": combined_thought_process
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
                "error": str(e),
                "complete_thought_process": f"Error occurred during processing: {str(e)}"
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
        # Emit progress update
        self._emit_progress("analyze_query", "Analyzing query to understand intent and entities")
        
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
        
        # Log the thought process
        logger.info(f"Query analysis thought process: {analysis['thought_process']}")
        
        # Emit progress update with analysis results
        intent = analysis.get('intent', 'unknown')
        entities = [e.get('value', 'unknown') for e in analysis.get('entities', [])]
        data_sources = analysis.get('data_sources', [])
        
        self._emit_progress(
            "analyze_query_complete", 
            f"Query analysis complete: Intent is '{intent}', found {len(entities)} entities",
            {
                "intent": intent,
                "entities": entities,
                "data_sources": data_sources,
                "thought_process": analysis['thought_process']
            }
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
        # Emit progress update
        self._emit_progress("select_tools", "Selecting appropriate tools based on query analysis")
        
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
        
        # Log the thought process
        logger.info(f"Tool selection thought process: {tool_selection['thought_process']}")
        
        # Emit progress update with tool selection results
        selected_tool_names = [tool['name'] for tool in tool_selection["selected_tools"]]
        
        self._emit_progress(
            "select_tools_complete", 
            f"Selected {len(selected_tool_names)} tools: {', '.join(selected_tool_names)}",
            {
                "selected_tools": selected_tool_names,
                "thought_process": tool_selection['thought_process']
            }
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
        # Emit progress update
        self._emit_progress(
            "generate_queries", 
            f"Generating structured queries for {len(selected_tools)} selected tools"
        )
        
        structured_queries = []
        
        # Get schema information
        schema_tool = self.tool_registry.get_tool("schema_information")
        schema_info = await schema_tool.run({"source_type": "all"})
        
        # For each selected tool, generate a structured query
        for i, tool_info in enumerate(selected_tools):
            tool_name = tool_info["name"]
            tool = self.tool_registry.get_tool(tool_name)
            
            # Emit progress update for this specific tool
            self._emit_progress(
                "generate_query", 
                f"Generating query for tool {i+1}/{len(selected_tools)}: {tool_name}"
            )
            
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
            
            # Log the thought process
            logger.info(f"Structured query generation thought process for {tool_name}: {structured_query['thought_process']}")
            
            # Add the tool name to the structured query
            structured_query["tool_name"] = tool_name
            
            # Emit progress update for this specific tool completion
            self._emit_progress(
                "generate_query_complete", 
                f"Generated query for {tool_name}",
                {
                    "tool_name": tool_name,
                    "thought_process": structured_query['thought_process']
                }
            )
            
            structured_queries.append(structured_query)
        
        # Emit progress update for all queries
        self._emit_progress(
            "generate_queries_complete", 
            f"Generated {len(structured_queries)} structured queries"
        )
        
        return structured_queries
    
    async def _execute_queries(self, structured_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute structured queries.
        
        Args:
            structured_queries: Structured queries
            
        Returns:
            Query results
        """
        # Emit progress update
        self._emit_progress(
            "execute_queries", 
            f"Determining which of the {len(structured_queries)} queries are necessary to execute"
        )
        
        results = []
        
        # Determine which queries are necessary to execute
        necessary_queries = self._determine_necessary_queries(structured_queries)
        logger.info(f"Determined {len(necessary_queries)} necessary queries out of {len(structured_queries)} total")
        
        # Emit progress update for necessary queries
        necessary_tool_names = [q["tool_name"] for q in necessary_queries]
        skipped_tool_names = [q["tool_name"] for q in structured_queries if q not in necessary_queries]
        
        self._emit_progress(
            "execute_queries_plan", 
            f"Will execute {len(necessary_queries)} queries and skip {len(structured_queries) - len(necessary_queries)}",
            {
                "necessary_tools": necessary_tool_names,
                "skipped_tools": skipped_tool_names
            }
        )
        
        # Execute only necessary queries
        for i, query in enumerate(necessary_queries):
            tool_name = query["tool_name"]
            parameters = query["parameters"]
            
            # Emit progress update for this specific query
            self._emit_progress(
                "execute_query", 
                f"Executing query {i+1}/{len(necessary_queries)}: {tool_name}"
            )
            
            try:
                # Get the tool
                tool = self.tool_registry.get_tool(tool_name)
                
                # Execute the query
                result = await tool.run(parameters)
                
                # Add the tool name and parameters to the result
                result["tool_name"] = tool_name
                result["parameters"] = parameters
                result["thought_process"] = query["thought_process"]
                
                # Emit progress update for this specific query completion
                result_count = len(result.get("data", [])) if isinstance(result.get("data"), list) else "N/A"
                self._emit_progress(
                    "execute_query_complete", 
                    f"Executed {tool_name} query, got {result_count} results",
                    {
                        "tool_name": tool_name,
                        "result_count": result_count,
                        "status": "success"
                    }
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error executing query with tool {tool_name}: {str(e)}")
                
                # Emit progress update for this specific query error
                self._emit_progress(
                    "execute_query_error", 
                    f"Error executing {tool_name} query: {str(e)}",
                    {
                        "tool_name": tool_name,
                        "error": str(e)
                    }
                )
                
                # Add the error to the results
                results.append({
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "thought_process": query.get("thought_process", ""),
                    "error": str(e),
                    "status": "error"
                })
        
        # Add skipped queries to results with a "skipped" status
        for query in structured_queries:
            if query not in necessary_queries:
                results.append({
                    "tool_name": query["tool_name"],
                    "parameters": query["parameters"],
                    "thought_process": query.get("thought_process", ""),
                    "status": "skipped",
                    "reason": "This query was determined to be unnecessary for answering the user's question"
                })
        
        # Emit progress update for all queries
        self._emit_progress(
            "execute_queries_complete", 
            f"Executed {len(necessary_queries)} queries, skipped {len(structured_queries) - len(necessary_queries)}"
        )
        
        return results
        
    def _determine_necessary_queries(self, structured_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Determine which queries are necessary to execute based on intent mapping.
        
        This method analyzes the structured queries and determines which ones are
        actually necessary to answer the user's question by mapping the user's intent
        to the appropriate data sources and tools.
        
        Args:
            structured_queries: List of structured queries
            
        Returns:
            List of necessary queries
        """
        # Always execute schema information queries
        necessary_queries = [q for q in structured_queries if q["tool_name"] == "schema_information"]
        
        # Get non-schema queries
        non_schema_queries = [q for q in structured_queries if q["tool_name"] != "schema_information"]
        
        # If there are no non-schema queries, return just the schema queries
        if not non_schema_queries:
            return necessary_queries
            
        # If there's only one non-schema query, it's likely necessary
        if len(non_schema_queries) == 1:
            necessary_queries.extend(non_schema_queries)
            return necessary_queries
            
        # For multiple queries, we need to analyze the intent and map it to tools
        
        # Use LLM to classify intents and extract entities
        intent_keywords, data_entities = self._classify_intents_and_entities(non_schema_queries)
                
        # Now map intents and entities to the appropriate data sources
        tool_mapping = {
            # ERP is good for structured data, counts, and aggregations
            "erp_query": {
                "intents": {"count", "search", "aggregate"},
            #Use LLM to classify intents and extract entities
            "entities": {"customer", "product", "order", "employee"}
            },
            # Document storage is good for unstructured data and text search
            "document_storage_query": {
                "intents": {"search"},
                "entities": {"document", "review", "description","details"}
            },
            # Knowledge graph is good for relationships and connections
            "knowledge_graph_query": {
                "intents": {"relationship", "connection", "hierarchy"},
                "entities": {"customer", "product", "order", "employee"}
            }
        }
        
        # Determine which tools are necessary based on intent and entity mapping
        for query in non_schema_queries:
            tool_name = query["tool_name"]
            thought_process = query.get("thought_process", "").lower()
            
            # If the thought process explicitly states this query is necessary, include it
            if "necessary" in thought_process or "required" in thought_process or "needed" in thought_process:
                necessary_queries.append(query)
                continue
                
            # Check if this tool is appropriate for the detected intents and entities
            if tool_name in tool_mapping:
                tool_info = tool_mapping[tool_name]
                
                # Check if any of the intents match this tool
                intent_match = any(intent in intent_keywords for intent in tool_info["intents"])
                
                # Check if any of the entities match this tool
                entity_match = any(entity in data_entities for entity in tool_info["entities"])
                
                # If both intent and entity match, this tool is necessary
                if intent_match and entity_match:
                    necessary_queries.append(query)
                    continue
            
            # Special case handling for specific query types
            if "count" in intent_keywords and "customer" in data_entities and "erp_query" in tool_name:
                # For customer count queries, we only need the ERP query
                necessary_queries.append(query)
            elif "product" in data_entities and "price" in thought_process and "erp_query" in tool_name:
                # For product price queries, we need the ERP query
                necessary_queries.append(query)
            elif "document" in data_entities and "document_storage_query" in tool_name:
                # For document queries, we need the document storage query
                necessary_queries.append(query)
            elif "relationship" in intent_keywords and "knowledge_graph_query" in tool_name:
                # For relationship queries, we need the knowledge graph query
                necessary_queries.append(query)
        
        # If we couldn't determine any necessary queries, include the first non-schema query as a fallback
        if len(necessary_queries) == len([q for q in necessary_queries if q["tool_name"] == "schema_information"]):
            logger.warning("Could not determine necessary queries, using first non-schema query as fallback")
            necessary_queries.append(non_schema_queries[0])
        
        return necessary_queries
    
    async def _classify_intents_and_entities(self, queries: List[Dict[str, Any]]) -> Tuple[set, set]:
        """
        Use LLM to classify intents and extract entities from query thought processes.
        
        Args:
            queries: List of query dictionaries containing thought processes
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # If there are no queries, return empty sets
        if not queries:
            return set(), set()
            
        # Combine all thought processes
        combined_thought_process = "\n\n".join([q.get("thought_process", "") for q in queries])
        
        # Define the intent and entity classification prompt
        classification_prompt = f"""
        # Intent and Entity Classification Task
        
        Analyze the following thought processes from query generation:
        
        ```
        {combined_thought_process}
        ```
        
        Your task is to:
        1. Identify all intents present in these thought processes
        2. Extract all data entities mentioned
        
        For intents, use ONLY these categories:
        - count: Queries asking for a count or number of items
        - search: Queries looking for specific items or filtering data
        - aggregate: Queries asking for sums, averages, or other aggregations
        - compare: Queries asking to compare different items or groups
        - relationship: Queries about connections between different entities
        
        For entities, identify ONLY these main data objects:
        - customer: Any reference to customers or clients
        - product: Any reference to products or items
        - order: Any reference to orders, purchases, or transactions
        - employee: Any reference to staff, employees, or personnel
        - document: Any reference to documents, reviews, or unstructured text
        
        Analyze the thought processes carefully to determine which intents and entities are present.
        """
        
        # Define the output schema
        output_schema = {
            "type": "object",
            "properties": {
                "intents": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["count", "search", "aggregate", "compare", "relationship"]
                    },
                    "description": "Intents identified in the thought processes"
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["customer", "product", "order", "employee", "document"]
                    },
                    "description": "Data entities identified in the thought processes"
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation of why these intents and entities were identified"
                }
            },
            "required": ["intents", "entities", "explanation"]
        }
        
        # Define fallback strategies in order of preference
        fallback_strategies = [
            self._classify_with_primary_llm,
            self._classify_with_simplified_prompt,
            self._classify_with_direct_extraction,
            self._classify_with_tool_names,
            self._classify_with_default_values
        ]
        
        # Try each strategy in order until one succeeds
        for i, strategy in enumerate(fallback_strategies):
            try:
                if i > 0:
                    logger.warning(f"Trying fallback strategy {i}: {strategy.__name__}")
                
                intent_keywords, data_entities = await strategy(queries, classification_prompt, output_schema)

                    
            except Exception as e:
                logger.error(f"Error in fallback strategy {i} ({strategy.__name__}): {str(e)}")
        
        # If all strategies fail, return empty sets
        logger.error("All classification strategies failed, returning empty sets")
        return set(), set()
        
    async def _classify_with_primary_llm(self, queries: List[Dict[str, Any]], prompt: str, schema: Dict[str, Any]) -> Tuple[set, set]:
        """
        Primary classification strategy using the main LLM with full prompt and schema.
        
        Args:
            queries: List of query dictionaries
            prompt: Classification prompt
            schema: Output schema
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # Generate the classification
        classification = await self.llm_provider.generate_with_json_output(
            prompt=prompt,
            output_schema=schema,
            system_message=SYSTEM_PROMPT,
            temperature=0.2
        )
        
        # Log the classification
        logger.info(f"Intent classification: {classification['intents']}")
        logger.info(f"Entity classification: {classification['entities']}")
        logger.info(f"Classification explanation: {classification['explanation']}")
        
        # Convert to sets
        intent_keywords = set(classification["intents"])
        data_entities = set(classification["entities"])
        
        return intent_keywords, data_entities
        
    async def _classify_with_simplified_prompt(self, queries: List[Dict[str, Any]], prompt: str, schema: Dict[str, Any]) -> Tuple[set, set]:
        """
        Fallback strategy using a simplified prompt with the same LLM.
        
        Args:
            queries: List of query dictionaries
            prompt: Original classification prompt (not used)
            schema: Output schema
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # Combine all thought processes
        combined_thought_process = "\n\n".join([q.get("thought_process", "") for q in queries])
        
        # Create a simplified prompt
        simplified_prompt = f"""
        Analyze this text and identify:
        1. Which of these intents are present: count, search, aggregate, compare, relationship
        2. Which of these entities are mentioned: customer, product, order, employee, document
        
        Text to analyze:
        ```
        {combined_thought_process}
        ```
        
        Be very literal in your analysis. If you see words like "count", "find", "average", "compare", 
        or "relationship" directly mentioned, include those intents. Similarly, if you see direct mentions 
        of "customer", "product", "order", "employee", or "document", include those entities.
        """
        
        # Generate the classification with the simplified prompt
        classification = await self.llm_provider.generate_with_json_output(
            prompt=simplified_prompt,
            output_schema=schema,
            system_message=SYSTEM_PROMPT,
            temperature=0.3  # Slightly higher temperature for more variety
        )
        
        # Log the classification
        logger.info(f"Simplified prompt intent classification: {classification['intents']}")
        logger.info(f"Simplified prompt entity classification: {classification['entities']}")
        
        # Convert to sets
        intent_keywords = set(classification["intents"])
        data_entities = set(classification["entities"])
        
        return intent_keywords, data_entities
        
    async def _classify_with_direct_extraction(self, queries: List[Dict[str, Any]], prompt: str, schema: Dict[str, Any]) -> Tuple[set, set]:
        """
        Fallback strategy using direct keyword extraction from thought processes.
        
        Args:
            queries: List of query dictionaries
            prompt: Original classification prompt (not used)
            schema: Output schema (not used)
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # Initialize sets
        intent_keywords = set()
        data_entities = set()
        
        # Define keyword mappings
        intent_mapping = {
            "count": ["count", "how many", "number of", "total number"],
            "search": ["find", "search", "retrieve", "look for", "get", "fetch"],
            "aggregate": ["average", "sum", "total", "mean", "aggregate", "calculate"],
            "compare": ["compare", "difference", "versus", "vs", "against", "relative"],
            "relationship": ["relationship", "connection", "link", "related", "association", "between"]
        }
        
        entity_mapping = {
            "customer": ["customer", "client", "buyer", "purchaser", "consumer"],
            "product": ["product", "item", "good", "merchandise", "offering"],
            "order": ["order", "purchase", "transaction", "sale", "invoice"],
            "employee": ["employee", "staff", "personnel", "worker", "team member"],
            "document": ["document", "review", "text", "article", "paper", "report"]
        }
        
        # Combine all thought processes
        combined_thought_process = "\n\n".join([q.get("thought_process", "") for q in queries]).lower()
        
        # Extract intents using keyword mapping
        for intent, keywords in intent_mapping.items():
            if any(keyword in combined_thought_process for keyword in keywords):
                intent_keywords.add(intent)
                
        # Extract entities using keyword mapping
        for entity, keywords in entity_mapping.items():
            if any(keyword in combined_thought_process for keyword in keywords):
                data_entities.add(entity)
                
        # Log the extraction results
        logger.info(f"Direct extraction intent classification: {intent_keywords}")
        logger.info(f"Direct extraction entity classification: {data_entities}")
        
        return intent_keywords, data_entities
        
    async def _classify_with_tool_names(self, queries: List[Dict[str, Any]], prompt: str, schema: Dict[str, Any]) -> Tuple[set, set]:
        """
        Fallback strategy inferring intents and entities from tool names.
        
        Args:
            queries: List of query dictionaries
            prompt: Original classification prompt (not used)
            schema: Output schema (not used)
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # Initialize sets
        intent_keywords = set()
        data_entities = set()
        
        # Tool name to intent/entity mapping
        tool_mappings = {
            "erp_query": {
                "intents": {"search", "count", "aggregate"},
                "entities": {"customer", "product", "order", "employee"}
            },
            "document_storage_query": {
                "intents": {"search"},
                "entities": {"document"}
            },
            "knowledge_graph_query": {
                "intents": {"relationship", "search"},
                "entities": {"customer", "product", "order", "employee"}
            }
        }
        
        # Extract tool names from queries
        tool_names = [q.get("tool_name", "") for q in queries]
        
        # Map tool names to intents and entities
        for tool_name in tool_names:
            for mapped_tool, mappings in tool_mappings.items():
                if mapped_tool in tool_name:
                    intent_keywords.update(mappings["intents"])
                    data_entities.update(mappings["entities"])
        
        # Log the tool-based classification
        logger.info(f"Tool-based intent classification: {intent_keywords}")
        logger.info(f"Tool-based entity classification: {data_entities}")
        
        return intent_keywords, data_entities
        
    async def _classify_with_default_values(self, queries: List[Dict[str, Any]], prompt: str, schema: Dict[str, Any]) -> Tuple[set, set]:
        """
        Final fallback strategy using default values based on query analysis.
        
        Args:
            queries: List of query dictionaries
            prompt: Original classification prompt (not used)
            schema: Output schema (not used)
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # Default to search intent if we can't determine anything else
        intent_keywords = {"search"}
        
        # Try to extract entities from query parameters
        data_entities = set()
        
        for query in queries:
            # Check parameters for entity hints
            parameters = query.get("parameters", {})
            
            # Look for common parameter names that might indicate entities
            param_keys = " ".join(parameters.keys()).lower()
            param_values = " ".join(str(v) for v in parameters.values() if isinstance(v, (str, int, float))).lower()
            
            combined_params = param_keys + " " + param_values
            
            if "customer" in combined_params:
                data_entities.add("customer")
            if "product" in combined_params:
                data_entities.add("product")
            if "order" in combined_params:
                data_entities.add("order")
            if "employee" in combined_params:
                data_entities.add("employee")
            if "document" in combined_params or "text" in combined_params:
                data_entities.add("document")
                
        # If we still couldn't determine any entities, add a default one based on tool names
        if not data_entities:
            tool_names = [q.get("tool_name", "") for q in queries]
            
            if any("erp" in tool for tool in tool_names):
                data_entities.add("customer")  # Default to customer for ERP
            elif any("document" in tool for tool in tool_names):
                data_entities.add("document")  # Default to document for document storage
            elif any("knowledge" in tool for tool in tool_names):
                data_entities.add("customer")  # Default to customer for knowledge graph
            else:
                data_entities.add("customer")  # Ultimate fallback
        
        # Log the default classification
        logger.info(f"Default intent classification: {intent_keywords}")
        logger.info(f"Default entity classification: {data_entities}")
        
        return intent_keywords, data_entities
    
    async def _classify_intents_and_entities(self, queries: List[Dict[str, Any]]) -> Tuple[set, set]:
        """
        Use LLM to classify intents and extract entities from query thought processes.
        
        Args:
            queries: List of query dictionaries containing thought processes
            
        Returns:
            Tuple of (intent_keywords, data_entities) sets
        """
        # If there are no queries, return empty sets
        if not queries:
            return set(), set()
            
        # Combine all thought processes
        combined_thought_process = "\n\n".join([q.get("thought_process", "") for q in queries])
        
        # Define the intent and entity classification prompt
        classification_prompt = f"""
        # Intent and Entity Classification Task
        
        Analyze the following thought processes from query generation:
        
        ```
        {combined_thought_process}
        ```
        
        Your task is to:
        1. Identify all intents present in these thought processes
        2. Extract all data entities mentioned
        
        For intents, use ONLY these categories:
        - count: Queries asking for a count or number of items
        - search: Queries looking for specific items or filtering data
        - aggregate: Queries asking for sums, averages, or other aggregations
        - compare: Queries asking to compare different items or groups
        - relationship: Queries about connections between different entities
        
        For entities, identify ONLY these main data objects:
        - customer: Any reference to customers or clients
        - product: Any reference to products or items
        - order: Any reference to orders, purchases, or transactions
        - employee: Any reference to staff, employees, or personnel
        - document: Any reference to documents, reviews, or unstructured text
        
        Analyze the thought processes carefully to determine which intents and entities are present.
        """
        
        # Define the output schema
        output_schema = {
            "type": "object",
            "properties": {
                "intents": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["count", "search", "aggregate", "compare", "relationship"]
                    },
                    "description": "Intents identified in the thought processes"
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["customer", "product", "order", "employee", "document"]
                    },
                    "description": "Data entities identified in the thought processes"
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation of why these intents and entities were identified"
                }
            },
            "required": ["intents", "entities", "explanation"]
        }
        
        # Generate the classification
        try:
            classification = await self.llm_provider.generate_with_json_output(
                prompt=classification_prompt,
                output_schema=output_schema,
                system_message=SYSTEM_PROMPT,
                temperature=0.2
            )
            
            # Log the classification
            logger.info(f"Intent classification: {classification['intents']}")
            logger.info(f"Entity classification: {classification['entities']}")
            logger.info(f"Classification explanation: {classification['explanation']}")
            
            # Convert to sets
            intent_keywords = set(classification["intents"])
            data_entities = set(classification["entities"])
            
            return intent_keywords, data_entities
            
        except Exception as e:
            # If LLM classification fails, fall back to a simple keyword-based approach
            logger.error(f"Error in intent classification: {str(e)}")
            logger.warning("Falling back to simple keyword-based classification")
            
            # Initialize sets
            intent_keywords = set()
            data_entities = set()
            
            # Simple keyword-based classification as fallback
            for query in queries:
                thought_process = query.get("thought_process", "").lower()
                
                # Extract intent keywords
                if "count" in thought_process:
                    intent_keywords.add("count")
                if "find" in thought_process or "search" in thought_process or "retrieve" in thought_process:
                    intent_keywords.add("search")
                if "average" in thought_process or "sum" in thought_process or "total" in thought_process:
                    intent_keywords.add("aggregate")
                if "compare" in thought_process or "difference" in thought_process:
                    intent_keywords.add("compare")
                if "relationship" in thought_process or "connection" in thought_process:
                    intent_keywords.add("relationship")
                    
                # Extract data entities
                if "customer" in thought_process:
                    data_entities.add("customer")
                if "product" in thought_process:
                    data_entities.add("product")
                if "order" in thought_process:
                    data_entities.add("order")
                if "employee" in thought_process:
                    data_entities.add("employee")
                if "document" in thought_process or "review" in thought_process:
                    data_entities.add("document")
            
            return intent_keywords, data_entities
    
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
        # If there are no results, return an empty result
        if not results:
            logger.warning("No results to process")
            return {
                "combined_results": [],
                "summary": "No results found for your query.",
                "thought_process": "The query did not return any results from the data sources."
            }
        
        # Log the results for debugging
        logger.info(f"Processing {len(results)} results")
        for i, result in enumerate(results):
            logger.info(f"Result {i+1} from tool {result.get('tool_name', 'unknown')}: {len(result.get('data', []))} items")
        
        # Extract data from all results
        all_data = []
        for result in results:
            # Check if the result contains data
            if "data" in result and isinstance(result["data"], list):
                # Add source information to each data item
                source_type = result.get("source_type", "unknown")
                tool_name = result.get("tool_name", "unknown")
                
                # Add metadata to each item
                for item in result["data"]:
                    if isinstance(item, dict):
                        item_with_source = item.copy()
                        item_with_source["_source"] = {
                            "type": source_type,
                            "tool": tool_name
                        }
                        all_data.append(item_with_source)
                    else:
                        # Handle non-dict items
                        all_data.append({
                            "value": item,
                            "_source": {
                                "type": source_type,
                                "tool": tool_name
                            }
                        })
        
        # If we have data after extraction, use it directly
        if all_data:
            logger.info(f"Using {len(all_data)} extracted items directly")
            
            # Generate a natural language answer using the LLM
            try:
                # Use the LLM to generate a natural language answer
                answer_prompt = ANSWER_GENERATION_PROMPT.format(
                    query=query,
                    results=json.dumps(all_data, indent=2)
                )
                
                # Log the prompt for debugging
                logger.debug(f"Answer generation prompt: {answer_prompt}")
                
                answer_response = await self.llm_provider.generate(
                    prompt=answer_prompt,
                    system_message="You are a helpful assistant that provides direct, natural language answers to user queries based on the data provided.",
                    temperature=0.3
                )
                
                # Log the data structure for debugging
                logger.debug(f"Data structure for answer generation: {json.dumps(all_data, indent=2)}")
                
                # Log the data structure for debugging
                logger.debug(f"Data structure for answer generation: {json.dumps(all_data, indent=2)}")
                
                # Extract the answer from the response
                natural_language_answer = answer_response.strip()
                
                # Log the generated answer
                logger.debug(f"Raw generated answer: '{natural_language_answer}'")
                
                # Log the generated answer
                logger.debug(f"Raw generated answer: '{natural_language_answer}'")
                
                # If the answer is empty or too short, use a fallback
                if not natural_language_answer or len(natural_language_answer) < 10:
                    logger.warning("Generated answer was too short, using fallback")
                    natural_language_answer = self._generate_fallback_answer(query, all_data)
                    
                logger.info(f"Generated natural language answer: {natural_language_answer}")
                
                return {
                    "combined_results": all_data,
                    "summary": natural_language_answer,  # Use the natural language answer as the summary
                    "answer": natural_language_answer,   # Also include it as a dedicated answer field
                    "thought_process": "I've extracted the data from the query results and generated a natural language answer."
                }
                
            except Exception as e:
                logger.error(f"Error generating natural language answer: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Return the error directly without using fallback
                error_message = f"Error generating natural_language answer: {str(e)}"
                
                return {
                    "combined_results": all_data,
                    "summary": error_message,
                    "answer": error_message,
                    "error": str(e),
                    "thought_process": f"Error occurred during answer generation: {str(e)}"
                }
        
        # Prepare the prompt for LLM processing
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
                "answer": {
                    "type": "string",
                    "description": "Natural language answer to the query"
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
        
        # Log the thought process
        logger.info(f"Results processing thought process: {processed_results['thought_process']}")
        
        # If the processed results don't have an answer field, add one
        if "answer" not in processed_results and "summary" in processed_results:
            processed_results["answer"] = processed_results["summary"]
            
        return processed_results
        
    def _generate_fallback_answer(self, query: str, data: List[Dict[str, Any]]) -> str:
        """
        Generate a fallback natural language answer when the LLM-based generation fails.
        
        Args:
            query: The original query
            data: The result data
            
        Returns:
            A natural language answer
        """
        # Default fallback
        answer = f"I found {len(data)} results for your query."
        
        try:
            # If there's no data, return a clear message
            if not data:
                return "I couldn't find any results matching your query."
            
            # If there's only one row with one field, it's likely a count or aggregation
            if len(data) == 1 and len(data[0]) == 1:
                # Get the single field name and value
                field_name = list(data[0].keys())[0]
                field_value = data[0][field_name]
                
                # Format based on the field name
                if "count" in field_name.lower():
                    entity_type = self._extract_entity_type_from_query(query)
                    return f"You have {field_value} {entity_type} in your system."
                elif "sum" in field_name.lower() or "total" in field_name.lower():
                    entity_type = self._extract_entity_type_from_query(query)
                    return f"The total {entity_type} is {field_value}."
                elif "avg" in field_name.lower() or "average" in field_name.lower():
                    entity_type = self._extract_entity_type_from_query(query)
                    return f"The average {entity_type} is {field_value}."
                elif "max" in field_name.lower():
                    entity_type = self._extract_entity_type_from_query(query)
                    return f"The maximum {entity_type} is {field_value}."
                elif "min" in field_name.lower():
                    entity_type = self._extract_entity_type_from_query(query)
                    return f"The minimum {entity_type} is {field_value}."
                else:
                    # Generic single value response
                    return f"The {field_name} is {field_value}."
            
            # For multiple rows, try to provide a meaningful summary
            if len(data) > 0:
                # Check if we have common fields that might help identify the entity type
                sample_item = data[0]
                
                # Look for name/title fields to provide more context
                if "name" in sample_item:
                    entity_type = self._extract_entity_type_from_query(query)
                    first_item_name = sample_item["name"]
                    return f"I found {len(data)} {entity_type}. The first one is '{first_item_name}'."
                elif "title" in sample_item:
                    entity_type = self._extract_entity_type_from_query(query)
                    first_item_title = sample_item["title"]
                    return f"I found {len(data)} {entity_type}. The first one is '{first_item_title}'."
                
                # If we have price information, we might be dealing with products
                if "price" in sample_item:
                    # Sort by price to find the most expensive
                    sorted_items = sorted(data, key=lambda p: p.get("price", 0), reverse=True)
                    most_expensive = sorted_items[0]
                    name_field = "name" if "name" in most_expensive else "title" if "title" in most_expensive else "id"
                    return f"I found {len(data)} items. The most expensive is '{most_expensive.get(name_field, 'Unknown')}' at ${most_expensive.get('price', 0):.2f}."
                
                # If we have department information, we might be dealing with employees
                if "department" in sample_item:
                    # Group by department
                    departments = {}
                    for item in data:
                        dept = item.get("department", "Unknown")
                        if dept not in departments:
                            departments[dept] = 0
                        departments[dept] += 1
                    
                    dept_summary = ", ".join([f"{count} in {dept}" for dept, count in departments.items()])
                    return f"I found {len(data)} employees: {dept_summary}."
                
                # If we have status information, we might be dealing with orders
                if "status" in sample_item:
                    # Group by status
                    statuses = {}
                    for item in data:
                        status = item.get("status", "Unknown")
                        if status not in statuses:
                            statuses[status] = 0
                        statuses[status] += 1
                    
                    status_summary = ", ".join([f"{count} {status}" for status, count in statuses.items()])
                    return f"I found {len(data)} items: {status_summary}."
            
            # If we couldn't generate a more specific answer, return the default
            return answer
            
        except Exception as e:
            logger.error(f"Error in fallback answer generation: {str(e)}")
            # If anything goes wrong, return the default answer
            return answer
            
    def _extract_entity_type_from_query(self, query: str) -> str:
        """
        Extract the entity type from the query.
        
        Args:
            query: The query string
            
        Returns:
            The entity type (e.g., "customers", "products", etc.)
        """
        query_lower = query.lower()
        
        # Check for common entity types
        if "customer" in query_lower:
            return "customers"
        elif "product" in query_lower:
            return "products"
        elif "employee" in query_lower:
            return "employees"
        elif "order" in query_lower:
            return "orders"
        elif "sale" in query_lower:
            return "sales"
        elif "supplier" in query_lower:
            return "suppliers"
        elif "inventory" in query_lower:
            return "inventory items"
        
        # Default to generic "items"
        return "items"