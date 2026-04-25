"""Unit tests for extract_tables_from_sql (eval/run_h2a_full_pipeline.py).

This function parses FROM/JOIN clauses in agent-generated SQL and is the
source of the 'retrieved' set in compute_recall. Its limits bound the
evaluation.
"""
import pytest
from eval.run_h2a_full_pipeline import extract_tables_from_sql


class TestExtractTablesFromSQL:
    def test_empty_string_returns_empty_set(self):
        assert extract_tables_from_sql("") == set()

    def test_none_safe(self):
        assert extract_tables_from_sql(None) == set()

    def test_simple_select_from(self):
        assert extract_tables_from_sql("SELECT * FROM customers") == {"customers"}

    def test_lowercase_from_keyword(self):
        assert extract_tables_from_sql("select id from orders") == {"orders"}

    def test_multiple_joins(self):
        sql = """
            SELECT c.name, o.id
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            JOIN order_details od ON o.id = od.order_id
        """
        assert extract_tables_from_sql(sql) == {
            "customers", "orders", "order_details",
        }

    def test_left_join(self):
        sql = "SELECT * FROM a LEFT JOIN b ON a.id = b.id"
        assert extract_tables_from_sql(sql) == {"a", "b"}

    def test_schema_qualified_public(self):
        assert extract_tables_from_sql("SELECT * FROM public.customers") == {
            "customers"
        }

    def test_schema_qualified_dbo(self):
        assert extract_tables_from_sql("SELECT * FROM dbo.Customers") == {
            "customers"
        }

    def test_quoted_identifier(self):
        assert extract_tables_from_sql('SELECT * FROM "customers"') == {"customers"}

    def test_table_names_normalised_to_lowercase(self):
        assert extract_tables_from_sql("FROM Orders") == {"orders"}

    def test_union_captures_both_tables(self):
        sql = "SELECT id FROM customers UNION SELECT id FROM employees"
        assert extract_tables_from_sql(sql) == {"customers", "employees"}

    def test_subquery_in_from(self):
        """Flat regex — inner tables are captured."""
        sql = "SELECT * FROM (SELECT id FROM orders) t"
        assert extract_tables_from_sql(sql) == {"orders"}

    def test_cte_body_and_reference_both_captured(self):
        sql = "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent"
        assert extract_tables_from_sql(sql) == {"orders", "recent"}

    def test_aliases_do_not_leak_into_table_names(self):
        """FROM orders o → 'orders', not 'orders_o'."""
        assert extract_tables_from_sql("SELECT * FROM orders o") == {"orders"}

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Known limitation: the regex at eval/run_h2a_full_pipeline.py:32 "
            "only explicitly strips 'public.' and 'dbo.' prefixes. Tables "
            "qualified with any other schema (e.g. 'sales.orders') are "
            "captured as the schema name. Either extend the regex to match "
            "`\\w+\\.(\\w+)` or document this as a "
            "Northwind-and-Cockpit-only assumption."
        ),
    )
    def test_custom_schema_prefix_not_currently_handled(self):
        assert extract_tables_from_sql("SELECT * FROM sales.orders") == {"orders"}
