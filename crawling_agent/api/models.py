"""
Models for the crawling agent API.
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import uuid


class NaturalLanguageQuery(BaseModel):
    """Model for natural language query requests."""
    query: str = Field(..., description="The natural language query")
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique query ID")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for the query")


class QueryResult(BaseModel):
    """Model for query results."""
    query_id: str = Field(..., description="The query ID this result is for")
    thought_process: str = Field(..., description="The thought process used to translate the query")
    structured_queries: List[Dict[str, Any]] = Field(..., description="The structured queries generated")
    results: List[Dict[str, Any]] = Field(..., description="The combined results from all data sources")
    execution_time_ms: float = Field(..., description="Total execution time in milliseconds")
    status: str = Field(default="success", description="Status of the query execution")
    error: Optional[str] = Field(default=None, description="Error message if the query failed")
    answer: Optional[str] = Field(default=None, description="Natural language answer to the query")


class HealthStatus(BaseModel):
    """Model for health status."""
    status: str = Field(..., description="Health status")
    components: Dict[str, str] = Field(..., description="Status of individual components")
    version: str = Field(..., description="API version")