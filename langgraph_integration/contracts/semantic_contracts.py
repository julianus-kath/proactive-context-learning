"""
Semantic contract schemas shared between eval harness and LangGraph agents.

These models define the shape of per-query semantic contracts used in
benchmark mode. Contracts are loaded by the eval harness and passed
through to the orchestrator via metadata["query_contract"].
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TimeWindow(BaseModel):
    """Optional normalized time window constraints for a query contract."""

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = Field(
        default=None,
        description="Logical window type (e.g., 'calendar_year', 'rolling_30d').",
    )
    year: Optional[int] = Field(
        default=None,
        description="Calendar year when type == 'calendar_year'.",
    )
    column: Optional[str] = Field(
        default=None,
        description="Fully-qualified timestamp column used for the window.",
    )


class QueryContract(BaseModel):
    """
    Canonical semantic contract for a benchmark query.

    This model is the single source of truth for contract shape across:
    - eval/run_benchmark.py (contract loading & wiring),
    - result validator / semantic checks in the LangGraph pipeline.
    """

    model_config = ConfigDict(extra="allow")

    query_id: str = Field(
        description="Identifier for the benchmark query (matches dataset 'id')."
    )
    entity: str = Field(
        description="Human-level entity name (e.g., 'customer', 'order')."
    )
    entity_table: str = Field(
        description="Canonical base table name for the entity (e.g., 'customers')."
    )
    metric_key: str = Field(
        description="Stable metric identifier (e.g., 'total_revenue', 'orders_placed')."
    )
    metric_expression_sql: str = Field(
        description=(
            "Canonical SQL expression for the metric (no GROUP BY/ORDER BY), "
            "using base table/column names."
        )
    )
    required_tables: List[str] = Field(
        description=(
            "Base table names that must appear in the final plan/executed tables."
        )
    )
    allowed_join_paths: List[List[str]] = Field(
        description=(
            "List of allowed FK paths, each a sequence of base table names from "
            "entity ↔ fact (e.g., ['customers', 'orders', 'order_details'])."
        )
    )
    analytic_template: Optional[str] = Field(
        default=None,
        description="Analytic template key (e.g., 'TOP_K_BY_METRIC', 'COUNT_ENTITY').",
    )
    metric_phrase: Optional[str] = Field(
        default=None,
        description="Natural language metric phrase from the question.",
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Expected K for top-k style queries.",
    )
    time_window: Optional[TimeWindow] = Field(
        default=None,
        description="Optional normalized time window for the query.",
    )


class MetricDefinition(BaseModel):
    """
    Canonical metric definition used by metric catalogs.

    Metric catalogs map metric keys to deterministic SQL expressions and
    representative phrases. This is wired into benchmark-mode metric
    resolution in later phases.
    """

    model_config = ConfigDict(extra="allow")

    key: str = Field(
        description="Metric key (e.g., 'total_revenue', 'orders_placed').",
    )
    phrase: str = Field(
        description="Representative natural language phrase for the metric.",
    )
    expression_sql: str = Field(
        description="Canonical SQL expression for this metric.",
    )


MetricCatalog = Dict[str, MetricDefinition]
"""Mapping from metric_key to MetricDefinition for a given dataset."""

