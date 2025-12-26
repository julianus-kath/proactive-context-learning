import logging
import os
import sys
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path so chatbot_ui can be imported
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import chatbot_ui.langgraph_service as svc


logger = logging.getLogger(__name__)


class StubOrchestrator:
    """
    Lightweight orchestrator stub used to test /agent/* HTTP endpoints
    without invoking real LLMs, databases, or MCP.
    """

    # The service now routes directly to internal node handlers, so we
    # provide lightweight async methods that match those expectations.
    async def _discovery_node(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.update(
            {
                "relevant_tables": [{"name": "dbo.Customers"}],
                "schema_snippet": "CREATE TABLE dbo.Customers (...);",
                "column_index": {"dbo.Customers": ["CustomerId", "Name"]},
            }
        )
        return state

    async def _join_sql_node(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.update(
            {
                "sql_query": "SELECT TOP 1 * FROM dbo.Customers",
                "join_plan": {"primary_table": "dbo.Customers", "joins": []},
            }
        )
        return state

    async def _validate_sql_node(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.setdefault(
            "validation_result",
            {
                "is_valid": False,
                "error_type": "no_sql",
                "error_message": "sql_query is required for validation",
            },
        )
        return state

    async def _exec_recovery_node(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.setdefault(
            "exec_result",
            {
                "ok": True,
                "data": [{"id": 1}],
                "row_count": 1,
                "truncated": False,
            },
        )
        return state

    async def _result_validator_async(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.setdefault(
            "validation_result",
            {
                "is_valid": True,
                "error_type": None,
            },
        )
        return state

    async def _parse_intent_node(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = dict(state or {})
        state.setdefault(
            "intent",
            {
                "operation": "query",
                "primary_entities": ["customers"],
                "metrics": ["count"],
                "filters": [],
                "time_window": "last_month",
                "keywords_for_discovery": ["customers", "orders"],
                "confidence": 0.9,
                "needs_clarification": False,
            },
        )
        return state


def make_test_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """
    Build a TestClient with a stubbed orchestrator to avoid heavy
    initialization and external dependencies.
    """

    # Avoid real orchestrator creation in startup_event
    monkeypatch.setattr(svc, "create_query_orchestrator", lambda: StubOrchestrator())
    monkeypatch.setattr(svc, "get_debug_logger", lambda: None)

    client = TestClient(svc.app)
    # Ensure the global orchestrator used by handlers is our stub
    svc.orchestrator = StubOrchestrator()
    return client


class TestAgentEndpoints:
    def test_agent_docs_endpoint_serves_html(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.get("/agent/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        body = response.text
        assert "/agent/discovery" in body
        assert "/agent/join_sql" in body

    def test_intent_parser_endpoint_returns_intent(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/intent_parser",
            json={
                "state": {"user_input": "How many customers placed orders last month?"},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] in ("intent_parser", "parse_intent")
        intent = payload["output_state"].get("intent") or {}
        assert intent.get("operation") == "query"
        assert "customers" in (intent.get("keywords_for_discovery") or [])

    def test_discovery_endpoint_returns_relevant_tables(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/discovery",
            json={
                "state": {"user_input": "show me customers"},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] == "discovery"
        assert payload["ok"] is True
        assert "output_state" in payload
        assert "relevant_tables" in payload["output_state"]

    def test_join_sql_endpoint_returns_sql_and_join_plan(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/join_sql",
            json={
                "state": {"intent": {"operation": "query"}, "relevant_tables": []},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] == "join_sql"
        assert payload["ok"] is True
        assert "sql_query" in payload["output_state"]
        assert "join_plan" in payload["output_state"]

    def test_validate_sql_endpoint_surfaces_localized_error(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        # Purposely omit sql_query to trigger the stubbed validation error
        response = client.post(
            "/agent/validate_sql",
            json={
                "state": {},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] == "validate_sql"
        assert "output_state" in payload
        validation = payload["output_state"].get("validation_result") or {}
        assert validation.get("is_valid") is False
        assert validation.get("error_type") == "no_sql"

    def test_exec_recovery_endpoint_returns_exec_result(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/exec_recovery",
            json={
                "state": {"sql_query": "SELECT 1"},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] == "exec_recovery"
        assert payload["ok"] is True
        assert payload["row_count"] == 1
        assert "exec_result" in payload["output_state"]

    def test_result_validator_endpoint_returns_validation_result(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/result_validator",
            json={
                "state": {"exec_result": {"ok": True}},
                "api_key": "supersecretapikey",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["agent"] == "result_validator"
        validation = payload["output_state"].get("validation_result") or {}
        assert "is_valid" in validation

    def test_agent_endpoint_rejects_invalid_api_key(self, monkeypatch: pytest.MonkeyPatch):
        client = make_test_client(monkeypatch)

        response = client.post(
            "/agent/discovery",
            json={
                "state": {"user_input": "invalid key test"},
                "api_key": "not_the_right_key",
            },
        )

        assert response.status_code == 401
