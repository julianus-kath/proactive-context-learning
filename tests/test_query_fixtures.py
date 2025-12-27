from __future__ import annotations

from typing import Dict, Any

from tests.query_fixtures import load_cockpit_queries


def test_cockpit_query_fixture_shapes() -> None:
    """Reference cockpit queries should load and have expected shape."""
    entries = load_cockpit_queries(limit=3)
    assert entries, "Expected at least one cockpit query entry"

    for entry in entries:
        assert isinstance(entry, dict)
        assert isinstance(entry.get("id"), str)
        assert isinstance(entry.get("question"), str)
        expected_tables = entry.get("expected_tables")
        assert isinstance(expected_tables, list)
        assert all(isinstance(t, str) for t in expected_tables)

