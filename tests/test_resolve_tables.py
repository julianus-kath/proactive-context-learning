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
    # Bracketed MSSQL-style name that should resolve via loose key
    r = resolver.resolve("[dbo].[Order Details]")
    assert r.match_type in {"loose", "default_schema", "ci", "exact"}
    assert r.physical_full_name == "public.order_details"


def test_resolve_table_only_default_schema():
    resolver = TableResolver(_fake_catalog(), dialect="postgres", default_schema="public")
    r = resolver.resolve("Order Details")
    assert r.match_type in {"default_schema", "loose", "ci", "exact"}
    assert r.physical_full_name == "public.order_details"

