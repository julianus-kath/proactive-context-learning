"""
Semantic contracts for benchmark queries.

These contracts define expected entity, metric, tables, and join paths
for benchmark queries, enabling semantic correctness validation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TimeWindow(BaseModel):
    """Time window specification for time-based queries."""
    type: str = Field(..., description="Type of time window (calendar_year, month_over_month, year_over_year)")
    year: Optional[int] = Field(None, description="Specific year for calendar_year type")
    column: str = Field(..., description="Column to use for time filtering")


class QueryContract(BaseModel):
    """
    Semantic contract for a benchmark query.

    Defines the expected entity, metric, required tables, and allowed join paths
    for validating that the agent's response is semantically correct.
    """
    query_id: str = Field(..., description="Unique identifier for the query")
    entity: str = Field(..., description="Primary business entity (e.g., 'customer', 'product')")
    entity_table: str = Field(..., description="Main table for the entity")
    metric_key: str = Field(..., description="Metric identifier (e.g., 'total_revenue')")
    metric_expression_sql: str = Field(..., description="SQL expression for the metric")
    required_tables: List[str] = Field(default_factory=list, description="Tables that must be used")
    allowed_join_paths: List[List[str]] = Field(default_factory=list, description="Valid join paths between tables")
    analytic_template: str = Field(..., description="Template type (TOP_K_BY_METRIC, COUNT_ENTITY, AGG_OVER_PERIOD)")
    metric_phrase: str = Field(..., description="Natural language description of the metric")
    top_k: Optional[int] = Field(None, description="For TOP_K_BY_METRIC: how many results")
    time_window: Optional[TimeWindow] = Field(None, description="Time window specification")

    class Config:
        extra = "allow"  # Allow additional fields for forward compatibility
