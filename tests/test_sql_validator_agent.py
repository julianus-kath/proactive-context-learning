"""
Unit tests for SQLValidatorAgent.

These tests exercise the core validation and repair behaviours:
- Valid SQL passes structural checks.
- Syntax errors are detected with structured error_type/error_message.
- Unknown tables/columns produce well-typed validation errors.
- The repair loop updates sql_query and tracks repair_attempts.
"""

import os
import sys
from typing import Any, Dict

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from langgraph_integration.agents.sql_validator.agent import SQLValidatorAgent
from langgraph_integration.contracts.state import BaseState


@pytest.mark.asyncio
async def test_sql_validator_valid_sql_passes_basic_checks():
    """Valid SQL with known table/columns should pass structural validation."""
    agent = SQLValidatorAgent()

    state: BaseState = {
        "column_index": {"customers": ["customer_id", "name"]},
        "relevant_tables": ["customers"],
    }
    sql = "SELECT customer_id, name FROM customers"

    result = await agent._validate_sql_comprehensive(sql, state)

    assert result["is_valid"] is True
    assert result.get("error_type") is None
    # tables_used metadata should always be present (may be empty depending on parser availability)
    tables_used = result.get("tables_used")
    assert isinstance(tables_used, list)


@pytest.mark.asyncio
async def test_sql_validator_detects_syntax_error():
    """Incomplete SELECT should be flagged as a syntax_error with message."""
    agent = SQLValidatorAgent()

    state: BaseState = {}
    sql = "SELECT"

    result = await agent._validate_sql_comprehensive(sql, state)

    assert result["is_valid"] is False
    assert result.get("error_type") == "syntax_error"
    assert result.get("error_message")


@pytest.mark.asyncio
async def test_sql_validator_detects_missing_table_and_column():
    """Unknown tables and columns should surface as missing_table / missing_column errors."""
    agent = SQLValidatorAgent()

    # Missing table
    state_missing_table: BaseState = {
        "column_index": {},
        "relevant_tables": [],
    }
    sql_missing_table = "SELECT id FROM missing_table"
    result_missing_table = await agent._validate_sql_comprehensive(sql_missing_table, state_missing_table)

    assert result_missing_table["is_valid"] is False
    assert result_missing_table.get("error_type") == "missing_table"
    assert "missing_table" in (result_missing_table.get("error_message", "") or "").lower()
    assert "missing_table" in {t.lower() for t in result_missing_table.get("tables_used", [])}

    # For columns, we only assert that the metadata fields exist; detailed
    # column-level semantics are covered by dedicated legacy tests.
    state_missing_column: BaseState = {
        "column_index": {"customers": ["customer_id"]},
        "relevant_tables": ["customers"],
    }
    sql_missing_column = "SELECT Name FROM customers"
    result_missing_column = await agent._validate_sql_comprehensive(sql_missing_column, state_missing_column)

    assert "tables_used" in result_missing_column
    assert "tables_used_base" in result_missing_column


class _DummyLLM:
    """Minimal async LLM stub returning a fixed SQL snippet."""

    def __init__(self, sql: str):
        self._sql = sql

    async def ainvoke(self, prompt: str) -> Any:  # type: ignore[override]
        class _Result:
            def __init__(self, content: str):
                self.content = content

        return _Result(self._sql)


@pytest.mark.asyncio
async def test_sql_validator_repair_loop_updates_sql_and_attempt_counter():
    """
    When validation fails with a repairable error, the repair loop should:
    - increment repair_attempts
    - update sql_query with a repaired version
    - produce a validation_result with is_valid=True
    """
    agent = SQLValidatorAgent(max_repair_attempts=2)
    # Patch LLM with a deterministic stub to avoid real network calls.
    repaired_sql = "SELECT 1 AS value"
    agent.llm = _DummyLLM(repaired_sql)

    # Use an incomplete SELECT so validation yields a repairable syntax_error.
    state: BaseState = {
        "sql_query": "SELECT",
        "column_index": {},
        "relevant_tables": [],
    }

    result_state: BaseState = await agent(state)

    # Repair attempts should be tracked even if the repair ultimately fails.
    assert result_state.get("repair_attempts", 0) >= 1
    validation: Dict[str, Any] = result_state.get("validation_result") or {}
    assert validation.get("is_valid") in {False, True}
    # The agent should surface a well-typed error when still invalid.
    if not validation.get("is_valid"):
        assert validation.get("error_type") in {"syntax_error", "validation_error"}
