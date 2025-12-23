import os
import sys

# Ensure langgraph_integration package is importable when running tests directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph_integration.utils.resolve_tables import TableResolver


def _fake_catalog():
    return {
        "tables": {
            "public.orders": {
                "schema": "public",
                "table_name": "orders",
                "type": "BASE TABLE",
            },
            "public.order_details": {
                "schema": "public",
                "table_name": "order_details",
                "type": "BASE TABLE",
            },
            "analytics.orders": {
                "schema": "analytics",
                "table_name": "orders",
                "type": "BASE TABLE",
            },
        },
        "views": {
            "public.orders_view": {
                "schema": "public",
                "table_name": "orders_view",
                "type": "VIEW",
            }
        },
    }


def test_resolve_exact_canonical_match():
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="public")
    r = resolver.resolve("public.order_details")
    assert r.match_type == "exact"
    assert r.physical_full_name == "public.order_details"
    assert r.physical_schema == "public"
    assert r.physical_name == "order_details"


def test_resolve_loose_full_match():
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="public")
    # Bracketed MSSQL-style name with dbo schema does not map directly to the
    # Postgres catalog when schema is preserved; resolver should not fabricate
    # a mapping here.
    r = resolver.resolve("[dbo].[Order Details]")
    assert r.match_type == "not_found"


def test_resolve_table_only_default_schema():
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="public")
    r = resolver.resolve("Order Details")
    assert r.match_type in {"default_schema", "loose", "ci", "exact"}
    assert r.physical_full_name == "public.order_details"


def test_resolve_prefers_default_schema_on_collision():
    # 'orders' exists in both public and analytics schemas; default_schema=public
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="public")
    r = resolver.resolve("orders")
    assert r.match_type in {"default_schema", "loose", "ci", "exact"}
    assert r.physical_full_name == "public.orders"


def test_resolve_ambiguous_when_no_default_schema_match():
    # Use a resolver with default_schema that does not match either candidate;
    # collisions on 'orders' should become ambiguous.
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="reporting")
    r = resolver.resolve("orders")
    assert r.match_type == "ambiguous"
    assert "public.orders" in r.candidates
    assert "analytics.orders" in r.candidates
