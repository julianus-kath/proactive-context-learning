"""
TaskInstruction dataclass for structured representation of crawling tasks.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union


class DataSourceType(Enum):
    """Enum for different data source types."""
    ERP = "erp"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DOCUMENT_STORAGE = "document_storage"


class QueryType(Enum):
    """Enum for different query types."""
    SQL = "sql"
    SPARQL = "sparql"
    MONGODB = "mongodb"


@dataclass
class DataSourceQuery:
    """Represents a query for a specific data source."""
    source_type: DataSourceType
    query_type: QueryType
    query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskInstruction:
    """
    Structured representation of a crawling task derived from natural language.
    """
    task_id: str
    original_query: str
    description: str
    data_sources: List[DataSourceType]
    queries: List[DataSourceQuery]
    priority: int = 1
    max_results: Optional[int] = None
    timeout_seconds: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_queries_for_source(self, source_type: DataSourceType) -> List[DataSourceQuery]:
        """
        Get all queries for a specific data source type.
        
        Args:
            source_type: The data source type to filter by
            
        Returns:
            List of DataSourceQuery objects for the specified source type
        """
        return [q for q in self.queries if q.source_type == source_type]