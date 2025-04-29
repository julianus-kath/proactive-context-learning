"""
Crawling Controller for coordinating the execution of crawling tasks across multiple data sources.
"""
import time
import os
import concurrent.futures
from typing import Dict, List, Any, Optional, Union

from crawling_agent.models.task_instruction import TaskInstruction, DataSourceType, DataSourceQuery
from crawling_agent.models.crawling_context import CrawlingContext, ActionRequest
from crawling_agent.connectors.erp_connector import ERPConnector
from crawling_agent.connectors.knowledge_graph_connector import KnowledgeGraphConnector
from crawling_agent.connectors.document_storage_connector import DocumentStorageConnector
from crawling_agent.utils.logger import get_logger, TaskLogger


class CrawlingAgentController:
    """
    Controller for coordinating the execution of crawling tasks across multiple data sources
    following the MCP (Model Context Protocol) architecture.
    """
    
    def __init__(self, config_path: Optional[str] = None, mock_mode: bool = False):
        """
        Initialize the Crawling Agent Controller.
        
        Args:
            config_path: Path to the configuration file (optional)
            mock_mode: Whether to run connectors in mock mode
        """
        self.logger = get_logger(__name__)
        self.mock_mode = mock_mode
        
        # Set default config path if not provided
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "config.yaml"
            )
        
        self.config_path = config_path
        
        # Initialize connectors (lazy loading)
        self._erp_connector = None
        self._kg_connector = None
        self._doc_connector = None
        
        self.logger.info("Crawling Agent Controller initialized")
    
    @property
    def erp_connector(self) -> ERPConnector:
        """
        Get the ERP connector (lazy initialization).
        
        Returns:
            ERPConnector instance
        """
        if self._erp_connector is None:
            self._erp_connector = ERPConnector(self.config_path)
        return self._erp_connector
    
    @property
    def kg_connector(self) -> KnowledgeGraphConnector:
        """
        Get the Knowledge Graph connector (lazy initialization).
        
        Returns:
            KnowledgeGraphConnector instance
        """
        if self._kg_connector is None:
            self._kg_connector = KnowledgeGraphConnector(self.config_path)
        return self._kg_connector
    
    @property
    def doc_connector(self) -> DocumentStorageConnector:
        """
        Get the Document Storage connector (lazy initialization).
        
        Returns:
            DocumentStorageConnector instance
        """
        if self._doc_connector is None:
            self._doc_connector = DocumentStorageConnector(self.config_path, mock_mode=self.mock_mode)
        return self._doc_connector
    
    def execute(self, context: CrawlingContext) -> CrawlingContext:
        """
        Execute actions in the CrawlingContext and update it with observations.
        
        Args:
            context: The CrawlingContext object containing action requests
            
        Returns:
            Updated CrawlingContext with observations
        """
        self.logger.info(f"[MCP:ACTING] Executing actions for context {context.context_id}")
        
        # Update context status
        context.update_status("acting")
        
        # Get pending actions
        pending_actions = context.get_pending_actions()
        
        if not pending_actions:
            self.logger.info(f"[MCP:ACTING] No pending actions to execute")
            context.update_status("completed")
            return context
        
        # Check if we should execute in parallel
        parallel_execution = os.environ.get("CRAWLING_PARALLEL", "true").lower() == "true"
        
        try:
            if parallel_execution:
                # Execute actions in parallel
                self._execute_parallel_actions(context)
            else:
                # Execute actions sequentially
                self._execute_sequential_actions(context)
            
            # Update context status
            if context.get_pending_actions():
                context.update_status("partially_completed")
            else:
                context.update_status("completed")
            
            # Prepare the final result
            final_result = {
                "context_id": context.context_id,
                "original_query": context.original_query,
                "observations": context.observations,
                "metadata": {
                    "execution_time": context.updated_at,
                    "data_sources": list(set([action.action_type.split('_')[1] for action in context.action_requests])),
                    "action_count": len(context.action_requests),
                    "completed_action_count": len([a for a in context.action_requests if a.status == "completed"]),
                    "failed_action_count": len([a for a in context.action_requests if a.status == "failed"])
                }
            }
            
            context.set_final_result(final_result)
            
            self.logger.info(f"[MCP:OBSERVING] Context execution completed: {context.status}")
            
            return context
            
        except Exception as e:
            self.logger.error(f"[MCP:ACTING] Error executing context {context.context_id}: {str(e)}")
            context.update_status("failed")
            context.metadata["error"] = str(e)
            raise
            
    def execute_task(self, task: TaskInstruction) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        Converts TaskInstruction to CrawlingContext, executes it, and returns the results.
        
        Args:
            task: The TaskInstruction object describing what to crawl
            
        Returns:
            Dictionary containing the crawled data and execution metadata
        """
        self.logger.warning("Using legacy execute_task method. Consider using execute with CrawlingContext instead.")
        
        # Create a CrawlingContext from the TaskInstruction
        context = CrawlingContext(
            original_query=task.original_query,
            task_instruction=task
        )
        
        # Generate action requests based on the task instruction
        for query_obj in task.queries:
            source_type = query_obj.source_type.value
            query_str = query_obj.query
            query_params = query_obj.parameters
            
            action_request = ActionRequest.create_query_action(
                source="execute_task",
                data_source=source_type,
                query=query_str,
                query_params=query_params
            )
            
            context.add_action_request(action_request)
        
        # Execute the context
        result_context = self.execute(context)
        
        # Convert the result to the legacy format
        if result_context.final_result:
            return result_context.final_result
        else:
            return {
                "task_id": task.task_id,
                "original_query": task.original_query,
                "results": result_context.observations.get("actions", {}),
                "metadata": {
                    "status": result_context.status,
                    "error": result_context.metadata.get("error", None)
                }
            }
    
    def _execute_sequential_actions(self, context: CrawlingContext) -> None:
        """
        Execute actions sequentially and update the context with observations.
        
        Args:
            context: The CrawlingContext object
        """
        pending_actions = context.get_pending_actions()
        
        for action in pending_actions:
            self._execute_action(context, action)
    
    def _execute_parallel_actions(self, context: CrawlingContext) -> None:
        """
        Execute actions in parallel using ThreadPoolExecutor and update the context with observations.
        
        Args:
            context: The CrawlingContext object
        """
        pending_actions = context.get_pending_actions()
        futures = []
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all actions
            for action in pending_actions:
                future = executor.submit(self._execute_action, context, action)
                futures.append((action.action_id, future))
            
            # Wait for all futures to complete
            for action_id, future in futures:
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"[MCP:ACTING] Error executing action {action_id}: {str(e)}")
                    context.update_action_status(action_id, "failed")
                    if "errors" not in context.observations:
                        context.observations["errors"] = []
                    context.observations["errors"].append({
                        "action_id": action_id,
                        "error": str(e)
                    })
    
    def _execute_action(self, context: CrawlingContext, action: ActionRequest) -> None:
        """
        Execute a single action and update the context with observations.
        
        Args:
            context: The CrawlingContext object
            action: The ActionRequest to execute
        """
        action_type = action.action_type
        action_id = action.action_id
        
        self.logger.info(f"[MCP:ACTING] Executing action {action_id} of type {action_type}")
        
        # Update action status
        context.update_action_status(action_id, "in_progress")
        
        try:
            # Execute the action based on its type
            if action_type.startswith("query_erp"):
                result = self._execute_erp_action(action)
            elif action_type.startswith("query_knowledge_graph"):
                result = self._execute_kg_action(action)
            elif action_type.startswith("query_document_storage"):
                result = self._execute_doc_action(action)
            else:
                raise ValueError(f"Unknown action type: {action_type}")
            
            # Add observation to context
            context.add_observation(action_id, result)
            
            # Update action status
            context.update_action_status(action_id, "completed")
            
            self.logger.info(f"[MCP:OBSERVING] Action {action_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"[MCP:ACTING] Error executing action {action_id}: {str(e)}")
            context.update_action_status(action_id, "failed")
            if "errors" not in context.observations:
                context.observations["errors"] = []
            context.observations["errors"].append({
                "action_id": action_id,
                "error": str(e)
            })
    
    def _execute_erp_action(self, action: ActionRequest) -> Dict[str, Any]:
        """
        Execute an ERP action.
        
        Args:
            action: The ActionRequest for the ERP action
            
        Returns:
            Dictionary containing the action results
        """
        self.logger.info(f"[MCP:ACTING] Executing ERP action: {action.action_id}")
        
        # Extract query and parameters from the action
        query_str = action.parameters.get("query", "")
        query_params = action.parameters.get("parameters", {})
        
        # Create a DataSourceQuery object
        query = DataSourceQuery(
            source_type=DataSourceType.ERP,
            query_type=QueryType.SQL,
            query=query_str,
            parameters=query_params
        )
        
        # Execute the query
        start_time = time.time()
        with self.erp_connector as connector:
            result = connector.execute_query(query)
        duration_ms = (time.time() - start_time) * 1000
        
        # Add execution metadata
        result["metadata"]["action_id"] = action.action_id
        result["metadata"]["execution_time_ms"] = duration_ms
        
        self.logger.info(f"[MCP:OBSERVING] ERP action {action.action_id} executed in {duration_ms:.2f}ms")
        
        return result
    
    def _execute_kg_action(self, action: ActionRequest) -> Dict[str, Any]:
        """
        Execute a Knowledge Graph action.
        
        Args:
            action: The ActionRequest for the Knowledge Graph action
            
        Returns:
            Dictionary containing the action results
        """
        self.logger.info(f"[MCP:ACTING] Executing Knowledge Graph action: {action.action_id}")
        
        # Extract query and parameters from the action
        query_str = action.parameters.get("query", "")
        query_params = action.parameters.get("parameters", {})
        
        # Create a DataSourceQuery object
        query = DataSourceQuery(
            source_type=DataSourceType.KNOWLEDGE_GRAPH,
            query_type=QueryType.SPARQL,
            query=query_str,
            parameters=query_params
        )
        
        # Execute the query
        start_time = time.time()
        connector = self.kg_connector
        result = connector.execute_query(query)
        duration_ms = (time.time() - start_time) * 1000
        
        # Add execution metadata
        result["metadata"]["action_id"] = action.action_id
        result["metadata"]["execution_time_ms"] = duration_ms
        
        self.logger.info(f"[MCP:OBSERVING] Knowledge Graph action {action.action_id} executed in {duration_ms:.2f}ms")
        
        return result
    
    def _execute_doc_action(self, action: ActionRequest) -> Dict[str, Any]:
        """
        Execute a Document Storage action.
        
        Args:
            action: The ActionRequest for the Document Storage action
            
        Returns:
            Dictionary containing the action results
        """
        self.logger.info(f"[MCP:ACTING] Executing Document Storage action: {action.action_id}")
        
        # Extract query and parameters from the action
        query_str = action.parameters.get("query", "")
        query_params = action.parameters.get("parameters", {})
        
        # Create a DataSourceQuery object
        query = DataSourceQuery(
            source_type=DataSourceType.DOCUMENT_STORAGE,
            query_type=QueryType.MONGODB,
            query=query_str,
            parameters=query_params
        )
        
        # Execute the query
        start_time = time.time()
        with self.doc_connector as connector:
            result = connector.execute_query(query)
        duration_ms = (time.time() - start_time) * 1000
        
        # Add execution metadata
        result["metadata"]["action_id"] = action.action_id
        result["metadata"]["execution_time_ms"] = duration_ms
        
        self.logger.info(f"[MCP:OBSERVING] Document Storage action {action.action_id} executed in {duration_ms:.2f}ms")
        
        return result
        
    # Legacy methods for backward compatibility
    
    def _execute_sequential(self, task: TaskInstruction, task_logger: TaskLogger) -> tuple:
        """
        Legacy method: Execute queries sequentially.
        
        Args:
            task: The TaskInstruction object
            task_logger: The TaskLogger for logging execution
            
        Returns:
            Tuple of (results dictionary, errors list)
        """
        self.logger.warning("Using legacy _execute_sequential method")
        
        # Create a context and convert to the new MCP approach
        context = CrawlingContext(
            original_query=task.original_query,
            task_instruction=task
        )
        
        # Generate action requests based on the task instruction
        for query_obj in task.queries:
            source_type = query_obj.source_type.value
            query_str = query_obj.query
            query_params = query_obj.parameters
            
            action_request = ActionRequest.create_query_action(
                source="_execute_sequential",
                data_source=source_type,
                query=query_str,
                query_params=query_params
            )
            
            context.add_action_request(action_request)
        
        # Execute the actions sequentially
        self._execute_sequential_actions(context)
        
        # Convert the results back to the legacy format
        results = {}
        errors = []
        
        if "errors" in context.observations:
            errors = context.observations["errors"]
        
        if "actions" in context.observations:
            for action_id, observation in context.observations["actions"].items():
                action = context.get_action_by_id(action_id)
                if action:
                    data_source = action.action_type.split('_')[1]
                    if data_source not in results:
                        results[data_source] = []
                    results[data_source].append(observation["data"])
        
        return results, errors
    
    def _execute_parallel(self, task: TaskInstruction, task_logger: TaskLogger) -> tuple:
        """
        Legacy method: Execute queries in parallel using ThreadPoolExecutor.
        
        Args:
            task: The TaskInstruction object
            task_logger: The TaskLogger for logging execution
            
        Returns:
            Tuple of (results dictionary, errors list)
        """
        self.logger.warning("Using legacy _execute_parallel method")
        
        # Create a context and convert to the new MCP approach
        context = CrawlingContext(
            original_query=task.original_query,
            task_instruction=task
        )
        
        # Generate action requests based on the task instruction
        for query_obj in task.queries:
            source_type = query_obj.source_type.value
            query_str = query_obj.query
            query_params = query_obj.parameters
            
            action_request = ActionRequest.create_query_action(
                source="_execute_parallel",
                data_source=source_type,
                query=query_str,
                query_params=query_params
            )
            
            context.add_action_request(action_request)
        
        # Execute the actions in parallel
        self._execute_parallel_actions(context)
        
        # Convert the results back to the legacy format
        results = {}
        errors = []
        
        if "errors" in context.observations:
            errors = context.observations["errors"]
        
        if "actions" in context.observations:
            for action_id, observation in context.observations["actions"].items():
                action = context.get_action_by_id(action_id)
                if action:
                    data_source = action.action_type.split('_')[1]
                    if data_source not in results:
                        results[data_source] = []
                    results[data_source].append(observation["data"])
        
        return results, errors