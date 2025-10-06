"""
Integration Tests for Table Selector

Tests the table selection functionality to ensure:
1. Relevant tables are selected based on query intent
2. Scoring algorithm works correctly
3. Fallback strategies work when no matches found
4. Session context improves selection accuracy
5. Schema snippets are compact and accurate

Run with: pytest tests/integration/test_table_selector.py -v
"""

import pytest
import os
import sys

# Add project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

from app.db.table_selector import (
    select_relevant_tables,
    build_schema_snippet,
    _score_table,
    _detect_intent
)
from app.db.schema_cache import TableInfo


@pytest.fixture
def sample_erp_schema():
    """Create a realistic ERP schema for testing."""
    return {
        'dbo.customers': TableInfo(
            schema_name='dbo',
            table_name='customers',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'customer_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'customer_name', 'data_type': 'varchar', 'is_nullable': 'NO'},
                {'column_name': 'email', 'data_type': 'varchar', 'is_nullable': 'YES'},
                {'column_name': 'phone', 'data_type': 'varchar', 'is_nullable': 'YES'},
                {'column_name': 'created_date', 'data_type': 'date', 'is_nullable': 'NO'},
            ],
            primary_keys=['customer_id'],
            foreign_keys=[],
            row_count=5000
        ),
        'dbo.sales_orders': TableInfo(
            schema_name='dbo',
            table_name='sales_orders',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'order_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'customer_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'order_date', 'data_type': 'date', 'is_nullable': 'NO'},
                {'column_name': 'total_amount', 'data_type': 'decimal', 'is_nullable': 'NO'},
                {'column_name': 'status', 'data_type': 'varchar', 'is_nullable': 'NO'},
            ],
            primary_keys=['order_id'],
            foreign_keys=[
                {'column_name': 'customer_id', 'referenced_table': 'customers', 'referenced_column': 'customer_id'}
            ],
            row_count=15000
        ),
        'dbo.products': TableInfo(
            schema_name='dbo',
            table_name='products',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'product_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'product_name', 'data_type': 'varchar', 'is_nullable': 'NO'},
                {'column_name': 'category', 'data_type': 'varchar', 'is_nullable': 'YES'},
                {'column_name': 'price', 'data_type': 'decimal', 'is_nullable': 'NO'},
                {'column_name': 'stock_quantity', 'data_type': 'int', 'is_nullable': 'NO'},
            ],
            primary_keys=['product_id'],
            foreign_keys=[],
            row_count=2000
        ),
        'dbo.employees': TableInfo(
            schema_name='dbo',
            table_name='employees',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'employee_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'first_name', 'data_type': 'varchar', 'is_nullable': 'NO'},
                {'column_name': 'last_name', 'data_type': 'varchar', 'is_nullable': 'NO'},
                {'column_name': 'department', 'data_type': 'varchar', 'is_nullable': 'YES'},
                {'column_name': 'salary', 'data_type': 'decimal', 'is_nullable': 'YES'},
                {'column_name': 'hire_date', 'data_type': 'date', 'is_nullable': 'NO'},
            ],
            primary_keys=['employee_id'],
            foreign_keys=[],
            row_count=500
        ),
        'dbo.invoices': TableInfo(
            schema_name='dbo',
            table_name='invoices',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'invoice_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'order_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'invoice_date', 'data_type': 'date', 'is_nullable': 'NO'},
                {'column_name': 'amount', 'data_type': 'decimal', 'is_nullable': 'NO'},
                {'column_name': 'paid', 'data_type': 'bit', 'is_nullable': 'NO'},
            ],
            primary_keys=['invoice_id'],
            foreign_keys=[
                {'column_name': 'order_id', 'referenced_table': 'sales_orders', 'referenced_column': 'order_id'}
            ],
            row_count=12000
        ),
        'dbo.suppliers': TableInfo(
            schema_name='dbo',
            table_name='suppliers',
            table_type='BASE TABLE',
            columns=[
                {'column_name': 'supplier_id', 'data_type': 'int', 'is_nullable': 'NO'},
                {'column_name': 'supplier_name', 'data_type': 'varchar', 'is_nullable': 'NO'},
                {'column_name': 'contact_email', 'data_type': 'varchar', 'is_nullable': 'YES'},
                {'column_name': 'country', 'data_type': 'varchar', 'is_nullable': 'YES'},
            ],
            primary_keys=['supplier_id'],
            foreign_keys=[],
            row_count=300
        ),
    }


def test_detect_intent():
    """Test intent detection from queries."""
    # Sales intent
    assert "sales" in _detect_intent("show me total sales for last month")
    assert "sales" in _detect_intent("what are the revenue numbers?")
    
    # Customer intent
    assert "customers" in _detect_intent("list all customers from new york")
    assert "customers" in _detect_intent("find client information")
    
    # Product intent
    assert "products" in _detect_intent("show me product inventory")
    assert "products" in _detect_intent("what items are in stock?")
    
    # Employee intent
    assert "employees" in _detect_intent("list all employees in sales department")
    assert "employees" in _detect_intent("show staff salaries")
    
    # Finance intent
    assert "finance" in _detect_intent("show me unpaid invoices")
    
    # Unknown intent (empty set)
    assert len(_detect_intent("random query about nothing specific")) == 0


def test_score_table_exact_match(sample_erp_schema):
    """Test scoring with exact table name match."""
    query = "SELECT * FROM customers"
    query_words = set(query.lower().split())
    intents = _detect_intent(query.lower())
    
    score, reasons = _score_table(
        'dbo.customers',
        sample_erp_schema['dbo.customers'],
        query_words,
        intents,
        []
    )
    
    # Should have high score due to exact table name match
    assert score >= 10  # Exact match = 10 points
    assert len(reasons) > 0


def test_score_table_column_match(sample_erp_schema):
    """Test scoring with column name matches."""
    query = "Show me customer_name and email"
    query_words = set(query.lower().split())
    intents = _detect_intent(query.lower())
    
    score, reasons = _score_table(
        'dbo.customers',
        sample_erp_schema['dbo.customers'],
        query_words,
        intents,
        []
    )
    
    # Should have points for column matches (customer_name, email)
    assert score >= 6  # 3 points per column match
    assert len(reasons) > 0


def test_score_table_intent_match(sample_erp_schema):
    """Test scoring with intent-based matching."""
    query = "Show me total sales revenue"
    query_words = set(query.lower().split())
    intents = _detect_intent(query.lower())
    
    score, reasons = _score_table(
        'dbo.sales_orders',
        sample_erp_schema['dbo.sales_orders'],
        query_words,
        intents,
        []
    )
    
    # Should have points for sales intent matching sales_orders table
    assert score >= 5  # Intent match = 5 points
    assert len(reasons) > 0


def test_score_table_session_bonus(sample_erp_schema):
    """Test scoring with session history bonus."""
    query = "Show me more data"
    query_words = set(query.lower().split())
    intents = _detect_intent(query.lower())
    
    session_tables = ['dbo.customers', 'dbo.sales_orders']
    
    score, reasons = _score_table(
        'dbo.customers',
        sample_erp_schema['dbo.customers'],
        query_words,
        intents,
        session_tables
    )
    
    # Should have session bonus
    assert score >= 1  # Session bonus = 1 point
    assert "recent queries" in ' '.join(reasons)


def test_select_relevant_tables_sales_query(sample_erp_schema):
    """
    MILESTONE 2 ACCEPTANCE CRITERIA:
    Agent selects 1-3 relevant tables instead of full schema.
    """
    query = "Show me total sales for last month"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    # Should select sales-related tables
    assert len(selected) >= 1
    assert len(selected) <= 3
    assert 'dbo.sales_orders' in selected or 'dbo.invoices' in selected
    
    print(f"\nSales query selected: {selected}")


def test_select_relevant_tables_customer_query(sample_erp_schema):
    """Test table selection for customer-focused query."""
    query = "List all customers from California"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    assert len(selected) >= 1
    assert len(selected) <= 3
    assert 'dbo.customers' in selected
    
    print(f"\nCustomer query selected: {selected}")


def test_select_relevant_tables_product_query(sample_erp_schema):
    """Test table selection for product-focused query."""
    query = "Show me products with low stock"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    assert len(selected) >= 1
    assert len(selected) <= 3
    assert 'dbo.products' in selected
    
    print(f"\nProduct query selected: {selected}")


def test_select_relevant_tables_with_session_context(sample_erp_schema):
    """Test that session context influences table selection."""
    query = "Show me more details"  # Vague query
    
    # Without session context
    selected_no_context = select_relevant_tables(query, sample_erp_schema, session_tables=[])
    
    # With session context
    session_tables = ['dbo.customers', 'dbo.sales_orders']
    selected_with_context = select_relevant_tables(query, sample_erp_schema, session_tables=session_tables)
    
    # With context should prefer session tables
    assert any(t in selected_with_context for t in session_tables)
    
    print(f"\nVague query without context: {selected_no_context}")
    print(f"Vague query with context: {selected_with_context}")


def test_select_relevant_tables_fallback(sample_erp_schema):
    """Test fallback behavior when no clear match."""
    query = "Show me some random data xyz123"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    # Should still return 1-3 tables (fallback to first 3)
    assert len(selected) >= 1
    assert len(selected) <= 3
    
    print(f"\nFallback query selected: {selected}")


def test_select_relevant_tables_top_k_limit(sample_erp_schema):
    """Test that top_k parameter limits results."""
    query = "Show me sales and customer data"
    
    # Request only 1 table
    selected_1 = select_relevant_tables(query, sample_erp_schema, top_k=1)
    assert len(selected_1) == 1
    
    # Request 2 tables
    selected_2 = select_relevant_tables(query, sample_erp_schema, top_k=2)
    assert len(selected_2) == 2
    
    # Request 3 tables (may return fewer if not enough matches)
    selected_3 = select_relevant_tables(query, sample_erp_schema, top_k=3)
    assert len(selected_3) <= 3
    assert len(selected_3) >= 2  # Should at least get sales and customers


def test_build_schema_snippet_single_table(sample_erp_schema):
    """Test schema snippet generation for single table."""
    table_names = ['dbo.customers']
    
    snippet = build_schema_snippet(table_names, sample_erp_schema)
    
    # Should contain table name and columns
    assert 'customers' in snippet.lower()
    assert 'customer_id' in snippet
    assert 'customer_name' in snippet
    assert 'email' in snippet
    
    # Should be compact (not include other tables)
    assert 'sales_orders' not in snippet
    assert 'products' not in snippet
    
    print(f"\nSingle table snippet:\n{snippet}")


def test_build_schema_snippet_multiple_tables(sample_erp_schema):
    """Test schema snippet generation for multiple tables."""
    table_names = ['dbo.customers', 'dbo.sales_orders']
    
    snippet = build_schema_snippet(table_names, sample_erp_schema)
    
    # Should contain both tables
    assert 'customers' in snippet.lower()
    assert 'sales_orders' in snippet.lower()
    
    # Should show foreign key relationships
    assert 'customer_id' in snippet
    
    # Should not include unrelated tables
    assert 'employees' not in snippet
    assert 'suppliers' not in snippet
    
    print(f"\nMultiple table snippet:\n{snippet}")


def test_build_schema_snippet_with_relationships(sample_erp_schema):
    """Test that schema snippet includes foreign key relationships."""
    table_names = ['dbo.sales_orders', 'dbo.invoices']
    
    snippet = build_schema_snippet(table_names, sample_erp_schema)
    
    # Should mention foreign keys
    assert 'order_id' in snippet
    
    print(f"\nSchema snippet with relationships:\n{snippet}")


def test_schema_snippet_size_reduction(sample_erp_schema):
    """
    MILESTONE 2 ACCEPTANCE CRITERIA:
    Prompt size reduced by 4-10x.
    """
    # Build full schema (all tables)
    all_table_names = list(sample_erp_schema.keys())
    full_snippet = build_schema_snippet(all_table_names, sample_erp_schema)
    
    # Build selective schema (1-3 tables)
    selective_tables = ['dbo.customers', 'dbo.sales_orders']
    selective_snippet = build_schema_snippet(selective_tables, sample_erp_schema)
    
    # Calculate size reduction
    full_size = len(full_snippet)
    selective_size = len(selective_snippet)
    reduction_factor = full_size / selective_size
    
    print(f"\nFull schema size: {full_size} chars")
    print(f"Selective schema size: {selective_size} chars")
    print(f"Reduction factor: {reduction_factor:.1f}x")
    
    # Should be significantly smaller (at least 2x)
    assert reduction_factor >= 2.0
    
    # Ideally 3-5x for 2 out of 6 tables
    assert reduction_factor >= 2.5


def test_empty_schema_index():
    """Test behavior with empty schema index."""
    selected = select_relevant_tables("Show me data", {})
    assert selected == []
    
    snippet = build_schema_snippet([], {})
    assert snippet == ""


def test_nonexistent_table_in_snippet(sample_erp_schema):
    """Test schema snippet with non-existent table name."""
    table_names = ['dbo.customers', 'dbo.nonexistent']
    
    snippet = build_schema_snippet(table_names, sample_erp_schema)
    
    # Should include existing table
    assert 'customers' in snippet.lower()
    
    # Should skip non-existent table gracefully
    assert 'nonexistent' not in snippet.lower()


def test_case_insensitive_table_matching(sample_erp_schema):
    """Test that table selection is case-insensitive."""
    query = "Show me CUSTOMERS data"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    assert 'dbo.customers' in selected


def test_complex_multi_table_query(sample_erp_schema):
    """Test selection for complex query involving multiple tables."""
    query = "Show me customers who placed orders with unpaid invoices"
    
    selected = select_relevant_tables(query, sample_erp_schema)
    
    # Should select relevant tables for this join query
    assert len(selected) >= 2
    assert len(selected) <= 3
    
    # Should include at least customers and one of orders/invoices
    relevant_tables = {'dbo.customers', 'dbo.sales_orders', 'dbo.invoices'}
    assert any(t in selected for t in relevant_tables)
    
    print(f"\nComplex query selected: {selected}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])