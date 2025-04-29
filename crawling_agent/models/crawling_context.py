"""
CrawlingContext dataclass for MCP-compliant context passing between components.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
import uuid
import json
from datetime import datetime

from crawling_agent.models.task_instruction import TaskInstruction


@dataclass
class ActionRequest:
    """
    Represents a specific action to be performed by a connector.
    """
    action_id: str
    action_type: str  # "query_erp", "query_kg", "query_document_storage"
    parameters: Dict[str, Any]
    source: str  # Which component requested this action
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, in_progress, completed, failed
    
    @classmethod
    def create_query_action(cls, source: str, data_source: str, query: str, 
                           query_params: Dict[str, Any] = None) -> "ActionRequest":
        """
        Factory method to create a query action request.
        
        Args:
            source: The component requesting the action
            data_source: The data source to query (erp, knowledge_graph, document_storage)
            query: The query string
            query_params: Parameters for the query
            
        Returns:
            An ActionRequest object
        """
        action_type = f"query_{data_source}"
        return cls(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            parameters={
                "query": query,
                "parameters": query_params or {}
            },
            source=source
        )


@dataclass
class CrawlingContext:
    """
    MCP-compliant context object for passing between components.
    """
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_query: str = ""
    thought: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    action_requests: List[ActionRequest] = field(default_factory=list)
    observations: Dict[str, Any] = field(default_factory=dict)
    final_result: Optional[Dict[str, Any]] = None
    task_instruction: Optional[TaskInstruction] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "initialized"  # initialized, planning, acting, observing, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def update_status(self, new_status: str) -> None:
        """
        Update the status of the context and the updated_at timestamp.
        
        Args:
            new_status: The new status
        """
        self.status = new_status
        self.updated_at = datetime.now().isoformat()
    
    def add_action_request(self, action_request: ActionRequest) -> None:
        """
        Add an action request to the context.
        
        Args:
            action_request: The action request to add
        """
        self.action_requests.append(action_request)
        self.updated_at = datetime.now().isoformat()
    
    def add_observation(self, action_id: str, data: Any) -> None:
        """
        Add an observation to the context.
        
        Args:
            action_id: The ID of the action that produced this observation
            data: The observation data
        """
        if "actions" not in self.observations:
            self.observations["actions"] = {}
        
        self.observations["actions"][action_id] = {
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.updated_at = datetime.now().isoformat()
    
    def get_pending_actions(self) -> List[ActionRequest]:
        """
        Get all pending action requests.
        
        Returns:
            List of pending ActionRequest objects
        """
        return [action for action in self.action_requests if action.status == "pending"]
    
    def get_action_by_id(self, action_id: str) -> Optional[ActionRequest]:
        """
        Get an action request by its ID.
        
        Args:
            action_id: The ID of the action request
            
        Returns:
            The ActionRequest object or None if not found
        """
        for action in self.action_requests:
            if action.action_id == action_id:
                return action
        return None
    
    def update_action_status(self, action_id: str, status: str) -> None:
        """
        Update the status of an action request.
        
        Args:
            action_id: The ID of the action request
            status: The new status
        """
        action = self.get_action_by_id(action_id)
        if action:
            action.status = status
            self.updated_at = datetime.now().isoformat()
    
    def set_final_result(self, result: Dict[str, Any]) -> None:
        """
        Set the final result of the crawling process.
        
        Args:
            result: The final result
        """
        self.final_result = result
        self.update_status("completed")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the context to a dictionary.
        
        Returns:
            Dictionary representation of the context
        """
        # Convert task_instruction to dict if it exists
        task_dict = None
        if self.task_instruction:
            # Convert Enum values to strings for JSON serialization
            task_dict = {
                "task_id": self.task_instruction.task_id,
                "original_query": self.task_instruction.original_query,
                "description": self.task_instruction.description,
                "data_sources": [ds.value for ds in self.task_instruction.data_sources],
                "queries": [
                    {
                        "source_type": q.source_type.value,
                        "query_type": q.query_type.value,
                        "query": q.query,
                        "parameters": q.parameters
                    }
                    for q in self.task_instruction.queries
                ],
                "priority": self.task_instruction.priority,
                "max_results": self.task_instruction.max_results,
                "timeout_seconds": self.task_instruction.timeout_seconds,
                "metadata": self.task_instruction.metadata
            }
        
        return {
            "context_id": self.context_id,
            "original_query": self.original_query,
            "thought": self.thought,
            "plan": self.plan,
            "action_requests": [
                {
                    "action_id": a.action_id,
                    "action_type": a.action_type,
                    "parameters": a.parameters,
                    "source": a.source,
                    "timestamp": a.timestamp,
                    "status": a.status
                }
                for a in self.action_requests
            ],
            "observations": self.observations,
            "final_result": self.final_result,
            "task_instruction": task_dict,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert the context to a JSON string.
        
        Args:
            indent: Number of spaces for indentation
            
        Returns:
            JSON string representation of the context
        """
        return json.dumps(self.to_dict(), indent=indent)