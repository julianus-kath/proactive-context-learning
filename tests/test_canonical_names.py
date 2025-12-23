import os
import sys

# Ensure langgraph_integration package is importable when running tests directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph_integration.utils.canonical_names import (
    canonical_table_name,
    canonicalize_table_list,
)


def test_canonical_table_name_bracketed_to_postgres_public():
    # Explicit schema in the raw name is preserved in Postgres mode so that
    # multi-schema usage is not collapsed.
    result = canonical_table_name("[dbo].[Order Details]", dialect="postgres", schema="public")
    assert result == "dbo.order_details"


def test_canonical_table_name_dbo_prefix_to_postgres():
    # Explicit schema prefix is preserved; we do not remap dbo→public at the
    # canonicalisation layer, only normalise casing and identifier form.
    result = canonical_table_name("dbo.Products", dialect="postgres", schema="public")
    assert result == "dbo.products"


def test_canonical_table_name_simple_table_uses_default_schema():
    result = canonical_table_name("Products", dialect="postgres", schema="public")
    assert result == "public.products"


def test_canonical_table_name_mssql_bracketed_keeps_dbo_schema():
    result = canonical_table_name("[dbo].[Order Details]", dialect="mssql", schema="dbo")
    assert result == "dbo.order_details"


def test_canonicalize_table_list_deduplicates_equivalent_syntactic_forms():
    # Different notations for the same logical table within a schema should
    # collapse; cross-schema tables remain distinct canonical entries.
    tables = ["[dbo].[Orders]", "dbo.Orders", "public.orders"]
    canonical = canonicalize_table_list(tables, dialect="postgres", schema="public")
    assert canonical == ["dbo.orders", "public.orders"]
