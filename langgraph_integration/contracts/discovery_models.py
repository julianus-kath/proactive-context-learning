"""
Pydantic models for discovery agent outputs.

Provides strict validation so downstream agents receive predictable structures.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiscoveryCandidate(BaseModel):
    """Normalized discovery candidate returned by Scout search."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    full_name: str = Field(..., description="Schema-qualified table/view name")
    schema: Optional[str] = Field(default=None, description="Schema component")
    name: Optional[str] = Field(default=None, description="Bare table/view name")
    type: str = Field(default="table", description="Entity type (table/view)")
    is_view: bool = Field(default=False, description="True when candidate is a view")
    relevance_score: float = Field(default=0.0, ge=0.0, description="Semantic rank score")
    role_coverage: float = Field(default=0.0, ge=0.0, description="Business coverage score for views")
    has_rows: bool = Field(default=True, description="True if table/view is known to contain rows")
    estimated_rows: Optional[int] = Field(default=None, ge=0, description="Approximate row count")
    column_count: Optional[int] = Field(default=None, ge=0, description="Number of columns")
    fk_count: Optional[int] = Field(default=None, ge=0, description="Number of foreign keys")
    columns: List[Dict[str, Any]] = Field(default_factory=list, description="Column metadata")
    description: Optional[str] = Field(default=None, description="Human friendly description if available")

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(values or {})

        schema = data.get("schema") or data.get("table_schema")
        name = data.get("name") or data.get("table_name")
        full_name = data.get("full_name") or data.get("table_name") or data.get("name")

        if schema and name:
            full_name = f"{schema}.{name}"
        elif full_name and "." in full_name and not schema:
            parts = full_name.split(".", 1)
            schema, name = parts[0], parts[1]
        elif name and not full_name:
            full_name = name

        if not full_name:
            raise ValueError("Discovery candidate requires a full_name or table name.")

        data["schema"] = schema
        data["name"] = name or full_name.split(".")[-1]
        data["full_name"] = full_name

        entity_type = str(data.get("type") or "").lower()
        data["is_view"] = bool(data.get("is_view") or entity_type == "view")
        data["type"] = "view" if data["is_view"] else "table"

        # Normalise numeric fields that might arrive as strings
        for key in ("relevance_score", "role_coverage", "estimated_rows", "column_count", "fk_count"):
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = float(data[key]) if key in ("relevance_score", "role_coverage") else int(data[key])
                except Exception:
                    data[key] = None

        if data.get("estimated_rows") is not None:
            data["has_rows"] = data["estimated_rows"] > 0

        return data


class DiscoveryOutput(BaseModel):
    """Validated payload that DiscoveryAgent writes into shared state."""

    model_config = ConfigDict(extra="allow")

    relevant_tables: List[str]
    schema_snippet: Optional[str] = None
    candidate_views: List[DiscoveryCandidate] = Field(default_factory=list)
    relevant_table_details: List[DiscoveryCandidate] = Field(default_factory=list)
    column_index: Dict[str, List[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def deduplicate_tables(self) -> "DiscoveryOutput":
        seen = set()
        unique_tables: List[str] = []
        for table in self.relevant_tables:
            if table not in seen:
                seen.add(table)
                unique_tables.append(table)
        self.relevant_tables = unique_tables
        return self

