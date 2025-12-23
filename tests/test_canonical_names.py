import os
import sys

# Ensure langgraph_integration package is importable when running tests directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph_integration.utils.canonical_names import (
    canonical_table_name,
    canonicalize_table_list,
)


def test_canonical_table_name_bracketed_to_postgres_public():
    # Explicit dialect/schema should drive canonicalisation, independent of env.
    result = canonical_table_name("[dbo].[Order Details]", dialect="postgres", schema="public")
    # Syntactic, identifier-safe normalisation: schema + lowercased, whitespace→underscore.
    assert result == "public.order_details"


def test_canonical_table_name_dbo_prefix_to_postgres():
    # Schema prefix differences are normalised to the configured logical schema.
    result = canonical_table_name("dbo.Products", dialect="postgres", schema="public")
    assert result == "public.products"


def test_canonical_table_name_simple_table_uses_default_schema():
    result = canonical_table_name("Products", dialect="postgres", schema="public")
    assert result == "public.products"


def test_canonical_table_name_mssql_bracketed_keeps_dbo_schema():
    result = canonical_table_name("[dbo].[Order Details]", dialect="mssql", schema="dbo")
    assert result == "dbo.order_details"


def test_canonicalize_table_list_deduplicates_equivalent_syntactic_forms():
    # Different notations for the same logical table should collapse when
    # normalised with the same dialect + default schema.
    tables = ["[dbo].[Orders]", "dbo.Orders", "public.orders"]
    canonical = canonicalize_table_list(tables, dialect="postgres", schema="public")
    assert canonical == ["public.orders"]
