"""
Runtime configuration helpers for the LangGraph orchestrator.

Centralizes access to key environment-driven knobs so that:
- The orchestrator can enforce LLM budgets consistently.
- Future utilities (e.g., identifier canonicalization) can share
  the same database dialect and schema defaults.
"""

from __future__ import annotations

import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

DatabaseDialect = Literal["postgres", "mssql"]


def _coerce_int(env_value: str | None, default: int, name: str) -> int:
    """Parse an integer environment value with safe fallback."""
    if env_value is None or str(env_value).strip() == "":
        return default
    try:
        value = int(str(env_value).strip())
        if value <= 0:
            raise ValueError("must be positive")
        return value
    except Exception:
        logger.warning("Invalid %s value '%s'; using default %s", name, env_value, default)
        return default


def get_max_llm_calls(default: int = 20) -> int:
    """
    Resolve the global LLM call budget.

    Controlled by MAX_LLM_CALLS; falls back to the existing
    hard-coded default of 20 when unset or invalid.
    """
    return _coerce_int(os.getenv("MAX_LLM_CALLS"), default, "MAX_LLM_CALLS")


def get_llm_budget_safety_margin(default: int = 2) -> int:
    """
    Resolve the LLM budget safety margin.

    Controlled by LLM_BUDGET_SAFETY_MARGIN; this does not change
    behaviour yet, but is exposed for future budget-aware routing.
    """
    return _coerce_int(os.getenv("LLM_BUDGET_SAFETY_MARGIN"), default, "LLM_BUDGET_SAFETY_MARGIN")


def get_db_dialect(default: DatabaseDialect = "postgres") -> DatabaseDialect:
    """
    Resolve the active database dialect in a canonical form.

    Mirrors the DB_DIALECT semantics used elsewhere:
    - "postgres" / "postgresql" -> "postgres"
    - "mssql" / "sqlserver" -> "mssql"
    - Unknown/empty -> default (postgres by default)
    """
    raw = os.getenv("DB_DIALECT")
    if raw is None or str(raw).strip() == "":
        return default

    value = str(raw).strip().lower()
    if value in {"postgres", "postgresql"}:
        return "postgres"
    if value in {"mssql", "sqlserver"}:
        return "mssql"

    logger.warning("Unknown DB_DIALECT '%s'; using default '%s'", raw, default)
    return default


def get_db_default_schema(
    dialect: DatabaseDialect | None = None,
    default: str | None = None,
) -> str:
    """
    Resolve the default logical schema name used by the orchestrator.

    Controlled primarily by DB_DEFAULT_SCHEMA. When unset, choose a
    sensible default based on the active dialect:
    - postgres -> public (optionally POSTGRES_SCHEMA if present)
    - mssql    -> dbo
    """
    env_schema = os.getenv("DB_DEFAULT_SCHEMA")
    if env_schema and str(env_schema).strip():
        return str(env_schema).strip()

    # Fallback to dialect-specific defaults
    if dialect is None:
        dialect = get_db_dialect()

    if dialect == "postgres":
        # Reuse POSTGRES_SCHEMA when available to stay aligned with MCP config.
        return os.getenv("POSTGRES_SCHEMA", "public")
    if dialect == "mssql":
        return "dbo"

    return default or "public"


def get_max_graph_cycles(default: int = 10) -> int:
    """
    Resolve the maximum number of allowed validation-driven graph cycles.

    Controlled by MAX_GRAPH_CYCLES; currently used only for reporting
    and future safety guards, with a default aligned to existing docs.
    """
    return _coerce_int(os.getenv("MAX_GRAPH_CYCLES"), default, "MAX_GRAPH_CYCLES")


def get_max_validation_attempts(default: int = 2) -> int:
    """
    Resolve the maximum number of allowed validation attempts.

    Controlled by MAX_VALIDATION_ATTEMPTS; used by the orchestrator's
    repair loop control to prevent infinite validate/replan cycles.
    """
    return _coerce_int(os.getenv("MAX_VALIDATION_ATTEMPTS"), default, "MAX_VALIDATION_ATTEMPTS")


def get_max_exec_recovery_attempts(default: int = 2) -> int:
    """
    Resolve the maximum number of allowed exec_recovery attempts.

    Controlled by MAX_EXEC_RECOVERY_ATTEMPTS; separate from the older
    max_exec_attempts counter to differentiate planning vs. repair.
    """
    return _coerce_int(os.getenv("MAX_EXEC_RECOVERY_ATTEMPTS"), default, "MAX_EXEC_RECOVERY_ATTEMPTS")


def get_max_no_progress_repeats(default: int = 2) -> int:
    """
    Resolve the maximum number of allowed repeated repair signatures.

    Controlled by MAX_NO_PROGRESS_REPEATS; when the same (SQL,error)
    pair is seen this many times, the orchestrator will stop repair
    loops and return a structured diagnostic instead of thrashing.
    """
    return _coerce_int(os.getenv("MAX_NO_PROGRESS_REPEATS"), default, "MAX_NO_PROGRESS_REPEATS")


def get_default_answer_mode(default: str = "llm_first") -> str:
    """
    Resolve the default answer formatting mode.

    Controlled by ANSWER_MODE; supported values:
    - \"llm_first\" (default): prefer LLM formatting when budget allows
    - \"deterministic\" / \"data_first\": prefer deterministic summaries from data
    - \"data_only\": always use deterministic data formatting when possible
    """
    raw = os.getenv("ANSWER_MODE")
    if raw is None or str(raw).strip() == "":
        return default

    value = str(raw).strip().lower()

    # Canonicalize common variants into a small set of modes
    if value in {"llm_first", "llm", "model"}:
        return "llm_first"
    if value in {"deterministic", "data_first"}:
        return "deterministic_from_data"
    if value == "data_only":
        return "data_only"

    logger.warning("Unknown ANSWER_MODE '%s'; using default '%s'", raw, default)
    return default
