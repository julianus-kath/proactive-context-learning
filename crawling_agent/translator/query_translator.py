"""
QueryTranslator module for translating natural language queries into MCP-compliant CrawlingContext objects.
"""
import json
import logging
from typing import Dict, Any, Optional, Union

from crawling_agent.translator.mock_llm import MockLLM
from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery, QueryType
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
from crawling_agent.utils.logger import get_logger


class QueryTranslator:
    """
    Translates natural language queries into MCP-compliant CrawlingContext objects
    using an LLM (or mock LLM for testing).
    """
    
    def __init__(self, use_mock: bool = True, llm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the QueryTranslator.
        
        Args:
            use_mock: Whether to use the mock LLM (True) or a real LLM (False)
            llm_config: Configuration for the real LLM if use_mock is False
        """
        self.logger = get_logger(__name__)
        self.use_mock = use_mock
        self.llm_config = llm_config or {}
        
        if use_mock:
            self.logger.info("Using mock LLM for translation")
            self.llm = MockLLM()
        else:
            # In a real implementation, this would initialize the actual LLM
            # For now, we'll still use the mock as a placeholder
            self.logger.info("Using real LLM for translation (not implemented yet)")
            self.llm = MockLLM()  # Replace with actual LLM implementation
    
    def translate(self, query: str) -> CrawlingContext:
        """
        Translate a natural language query into an MCP-compliant CrawlingContext.
        
        Args:
            query: The natural language query to translate
            
        Returns:
            A CrawlingContext object with initial thought, plan, and action requests
        """
        self.logger.info(f"[MCP:PLANNING] Translating query: {query}")
        
        try:
            # Create a new CrawlingContext
            context = CrawlingContext(original_query=query)
            context.update_status("planning")
            
            # Use the LLM (or mock) to translate the query to a TaskInstruction
            task_instruction = self.llm.translate_query(query)
            
            # Store the TaskInstruction in the context
            context.task_instruction = task_instruction
            
            # Generate thought based on the task instruction
            thought = f"I need to retrieve data about '{task_instruction.description}' from " \
                     f"{', '.join([ds.value for ds in task_instruction.data_sources])}."
            context.thought = thought
            
            # Generate plan based on the task instruction
            plan = {
                "objective": task_instruction.description,
                "data_sources": [ds.value for ds in task_instruction.data_sources],
                "steps": []
            }
            
            # Add steps to the plan for each data source
            for i, data_source in enumerate(task_instruction.data_sources):
                step = {
                    "step_number": i + 1,
                    "action": f"Query {data_source.value}",
                    "description": f"Retrieve data from {data_source.value} based on the query"
                }
                plan["steps"].append(step)
            
            context.plan = plan
            
            # Generate action requests based on the task instruction
            for query_obj in task_instruction.queries:
                source_type = query_obj.source_type.value
                query_str = query_obj.query
                query_params = query_obj.parameters
                
                action_request = ActionRequest.create_query_action(
                    source="query_translator",
                    data_source=source_type,
                    query=query_str,
                    query_params=query_params
                )
                
                context.add_action_request(action_request)
            
            self.logger.info(f"[MCP:PLANNING] Translation successful: {thought}")
            self.logger.debug(f"[MCP:PLANNING] Generated context: {context.to_json()}")
            
            return context
            
        except Exception as e:
            self.logger.error(f"[MCP:PLANNING] Error translating query: {str(e)}")
            # Create an error context
            error_context = CrawlingContext(original_query=query)
            error_context.update_status("failed")
            error_context.thought = f"Failed to translate query: {str(e)}"
            error_context.metadata["error"] = str(e)
            raise