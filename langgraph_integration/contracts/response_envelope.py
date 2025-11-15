"""
Response envelopes shared across agents.

Provides strict-but-forgiving Pydantic models so every component
handles `{ok, data, error_info}` consistently. Additional execution
metadata (row_count, warnings, etc.) is preserved via extra fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ErrorInfo(BaseModel):
    """Normalized error envelope with optional debug metadata."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: str = Field(default="UNKNOWN_ERROR", description="Machine-readable error code.")
    message: str = Field(default="Unknown error", description="User-facing error message.")
    suggestion: Optional[str] = Field(
        default=None,
        description="Optional remediation guidance for the user.",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Opaque context for downstream debugging/logging.",
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured data for UI surfaces (e.g. failing tables).",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, value: Any) -> Dict[str, Any]:
        if value is None:
            return {"type": "UNKNOWN_ERROR", "message": "Unknown error"}
        if isinstance(value, ErrorInfo):
            return value.model_dump()
        if isinstance(value, Exception):
            return {"type": value.__class__.__name__.upper(), "message": str(value)}
        if isinstance(value, str):
            return {"type": "UNKNOWN_ERROR", "message": value}
        if isinstance(value, dict):
            data = dict(value)
            # Promote common legacy keys
            if "message" not in data and "error" in data:
                data["message"] = str(data.get("error"))
            data.setdefault("type", "UNKNOWN_ERROR")
            data["message"] = str(data.get("message") or "Unknown error")
            return data
        return {"type": "UNKNOWN_ERROR", "message": str(value)}


class ResponseEnvelope(BaseModel):
    """
    Standardized execution/result envelope.

    Ensures every downstream consumer can rely on `ok`, `data`, and
    `error_info` being present with predictable types while retaining
    additional metadata like row counts, latency, and warnings.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ok: bool = Field(default=False, description="True when the operation succeeded.")
    data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tabular rows or structured payload for successful operations.",
    )
    row_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of rows returned (defaults to len(data)).",
    )
    execution_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Execution duration in milliseconds.",
    )
    truncated: bool = Field(
        default=False,
        description="True when results were truncated to fit row caps.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal issues encountered during processing.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Legacy error string (discouraged; use error_info).",
    )
    error_info: Optional[ErrorInfo] = Field(
        default=None,
        description="Structured error information when `ok` is False.",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, value: Any) -> Dict[str, Any]:
        if isinstance(value, ResponseEnvelope):
            return value.model_dump()
        if isinstance(value, dict):
            data = dict(value)
            rows = data.get("data")
            if rows in (None, False):
                rows = data.get("rows")
            if isinstance(rows, list):
                data["data"] = rows
            elif rows is None:
                data["data"] = []
            else:
                try:
                    data["data"] = list(rows)
                except Exception:
                    data["data"] = []
            warnings = data.get("warnings")
            if warnings is not None and not isinstance(warnings, list):
                data["warnings"] = [str(warnings)]
            exec_time = data.get("execution_time_ms")
            if isinstance(exec_time, (int, float)):
                data["execution_time_ms"] = int(exec_time)
            return data
        if value is None:
            return {}
        return {
            "ok": False,
            "data": [],
            "error": f"Invalid response payload type: {type(value).__name__}",
        }

    @model_validator(mode="after")
    def _post_process(self) -> "ResponseEnvelope":
        # Coerce warnings to list of strings
        if not isinstance(self.warnings, list):
            self.warnings = [str(self.warnings)]
        else:
            self.warnings = [str(w) for w in self.warnings]

        # Derive row_count if missing
        if self.row_count is None:
            self.row_count = len(self.data or [])

        # When operation succeeded, drop stale error metadata
        if self.ok:
            self.error = None
            if self.error_info is not None:
                self.error_info = None
        else:
            # Backfill error_info from legacy error strings if needed
            if self.error_info is None and self.error:
                self.error_info = ErrorInfo(
                    type="QUERY_ERROR",
                    message=str(self.error),
                )

        return self

