"""
Tests for Reflexion-style planning/validation loop (Approach 1).

Covers:
- Blueprint JSON planning uses only snippet identifiers
- Error normalization mapping
- Single repair attempt via switching time column or casting numeric expr
- Preflight validation path (simulated)
"""

import asyncio
import pytest
from typing import List, Dict, Any

from mcp_server.answer_first_orchestrator import AnswerFirstOrchestrator


class DummyDBAdapter:
    """Dummy adapter that simulates fetch/preflight outcomes based on SQL content."""
    def __init__(self, fail_on: str | None = None, then_ok: bool = True):
        self.fail_on = fail_on
        self.then_ok = then_ok
        self.called_sql: List[str] = []
        # minimal catalog-like shape for describe_table enrichment path
        self.catalog = None

    async def fetch(self, query: str, params=None, limit: int = 100):
        self.called_sql.append(query)
        ql = query.lower()
        if self.fail_on and self.fail_on in ql:
            # Simulate engine error strings
            if "col_missing" in ql:
                raise Exception("invalid column name 'col_missing'")
            if "type_mismatch" in ql:
                raise Exception("cannot cast type varchar to numeric")
        # Return deterministic rows
        return [{"value": 1}]


@pytest.mark.asyncio
async def test_normalize_exec_error_mapping():
    orch = AnswerFirstOrchestrator(db_adapter=None)
    norm = orch._normalize_exec_error(None, "Invalid column name 'foo'")
    assert norm["code"] == "UNKNOWN_COLUMN"
    assert any("column" in h.lower() for h in norm["hints"])  # targeted hint


@pytest.mark.asyncio
async def test_plan_blueprint_uses_snippet_only():
    orch = AnswerFirstOrchestrator(db_adapter=None, dialect="mssql")
    snippet = [
        {
            "schema": "dbo",
            "name": "InvoiceLine",
            "full_name": "dbo.InvoiceLine",
            "columns": [
                {"name": "product_id", "type": "int", "role_hints": ["fk_to:dbo.Product"]},
                {"name": "quantity", "type": "int", "role_hints": ["quantity"]},
                {"name": "unit_price", "type": "numeric", "role_hints": ["amount"]},
                {"name": "invoice_date", "type": "date", "role_hints": ["date"]},
            ],
            "foreign_keys": [
                {"column": "product_id", "referenced_schema": "dbo", "referenced_table": "Product", "referenced_column": "id", "referenced_full_name": "dbo.Product"}
            ],
            "time_col_candidates": ["invoice_date"],
            "measure_suggestions": [
                {"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}
            ],
        },
        {
            "schema": "dbo",
            "name": "Product",
            "full_name": "dbo.Product",
            "columns": [
                {"name": "id", "type": "int", "role_hints": ["id"]},
                {"name": "name", "type": "varchar"},
            ],
            "foreign_keys": []
        }
    ]
    class PI:
        def __init__(self):
            self.intent = type("I", (), {"value": "REPORT"})
            self.entities = ["product", "sale"]
            self.operations = ["top", "sum"]
    bp = orch._plan_blueprint_json(
        user_query="Top products by sales last quarter",
        parsed_intent=PI(),
        selected_tables=[],
        schema_snippet=snippet,
        dialect="mssql",
    )
    assert bp is not None
    assert bp["fact_table"] == "dbo.InvoiceLine"
    assert "dbo.Product" in bp["dimensions"]
    # ensure only known identifiers used in joins
    for j in bp["joins"]:
        assert j["left"].startswith("dbo.") and j["right"].startswith("dbo.")


@pytest.mark.asyncio
async def test_generate_sql_from_blueprint():
    orch = AnswerFirstOrchestrator(db_adapter=None, dialect="mssql")
    snippet = [{
        "full_name": "dbo.InvoiceLine",
        "time_col_candidates": ["invoice_date"],
        "measure_suggestions": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
    }]
    bp = {
        "fact_table": "dbo.InvoiceLine",
        "dimensions": [],
        "joins": [],
        "measures": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
        "filters": [],
        "order_by": [{"expr": "revenue", "dir": "DESC"}],
        "limit": 5,
        "dialect": "mssql",
    }
    sql = orch._generate_sql_from_blueprint(bp, snippet)
    assert sql.strip().lower().startswith("select top 5 sum(")
    assert "from dbo.invoiceline" in sql.lower()


@pytest.mark.asyncio
async def test_repair_sql_unknown_column_switch_time_candidate():
    orch = AnswerFirstOrchestrator(db_adapter=None, dialect="mssql")
    snippet = [{
        "full_name": "dbo.InvoiceLine",
        "time_col_candidates": ["invoice_date", "created_at"],
        "measure_suggestions": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
    }]
    bp = {
        "fact_table": "dbo.InvoiceLine",
        "dimensions": [],
        "joins": [],
        "measures": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
        "filters": [{"expr": "dbo.InvoiceLine.col_missing >= GETDATE()"}],
        "order_by": [],
        "limit": 5,
        "dialect": "mssql",
    }
    norm = {"code": "UNKNOWN_COLUMN", "message": "Invalid column name", "hints": []}
    sql2 = orch._repair_sql_with_error("SELECT 1", norm, snippet, bp)
    # Expect rebuilt SQL with a valid time candidate in WHERE
    assert "created_at" in sql2 or "invoice_date" in sql2


@pytest.mark.asyncio
async def test_reflexion_loop_attempt_and_success():
    # Build orchestrator with dummy adapter that fails first preflight then succeeds
    dummy = DummyDBAdapter()
    orch = AnswerFirstOrchestrator(db_adapter=dummy, dialect="mssql")

    # Monkeypatch internal helpers to avoid LLM and use deterministic snippet and bp
    orch._get_schema_snippet = lambda names: asyncio.Future()
    fut = orch._get_schema_snippet(names=None)
    fut.set_result([
        {
            "schema": "dbo",
            "name": "InvoiceLine",
            "full_name": "dbo.InvoiceLine",
            "time_col_candidates": ["invoice_date"],
            "measure_suggestions": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
            "foreign_keys": []
        }
    ])
    orch._plan_blueprint_json = lambda **kwargs: {
        "fact_table": "dbo.InvoiceLine",
        "dimensions": [],
        "joins": [],
        "measures": [{"name": "revenue", "expr": "unit_price*quantity", "agg": "SUM"}],
        "filters": [{"expr": "dbo.InvoiceLine.col_missing >= GETDATE()"}],
        "order_by": [{"expr": "revenue", "dir": "DESC"}],
        "limit": 5,
        "dialect": "mssql",
    }
    # First execute_bounded_query call should fail due to col_missing; second after repair should pass
    from mcp_server import bounded_query as bq
    async def fake_exec(query: str, db_adapter, dialect: str, max_rows: int, requested_limit: int, enable_redaction: bool):
        if "col_missing" in query.lower():
            return bq.QueryResponse(ok=False, error_code="EXECUTION_FAILED", error_message="Invalid column name col_missing")
        else:
            return bq.QueryResponse(ok=True, rows=[{"value": 1}], columns=["value"], row_count=1)
    bq.execute_bounded_query = fake_exec

    # Provide a simple intent parser stub via attributes
    class PI:
        def __init__(self):
            self.intent = type("I", (), {"value": "REPORT"})
            self.entities = ["product", "sale"]
            self.operations = ["top", "sum"]
    orch.parse_intent = None  # not used directly

    result = await orch.execute_answer_first("Top products by sales last quarter")
    assert result.success is True
    assert result.debug_info.get("attempts") in (1, 2)
    assert result.debug_info.get("needed_clarification") is False