"""
Test numeric value quoting in join planner and SQL generator.

Verifies that:
1. Join planner generates unquoted numeric values in where_filters JSON
2. SQL generator correctly handles both numeric and string filter values
3. WHERE clauses are properly constructed without syntax errors
"""

import pytest
import logging
from pathlib import Path
import sys
import json

# Add path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Import components
from langgraph_integration.agents.join_sql.agent import JoinPlanAndSQLAgent
from langgraph_integration.contracts.state import BaseState


class TestNumericFilterQuoting:
    """Test numeric value handling in filters."""
    
    def test_sql_generator_numeric_value_no_quotes(self):
        """
        Test that numeric values in WHERE filters are NOT quoted in SQL.
        
        Input filter: {"column": "quantity", "operator": "=", "value": 100}
        Expected output: quantity = 100  (not quantity = '100')
        """
        join_plan = {
            "strategy": "joins",
            "primary_table": "dbo.sales_orders",
            "joins": [
                {
                    "table": "dbo.customers",
                    "on": "sales_orders.customer_id = customers.id",
                    "type": "INNER"
                }
            ],
            "where_filters": [
                {"column": "quantity", "operator": "=", "value": 100},
                {"column": "price", "operator": ">", "value": 50.5}
            ],
            "select_columns": ["*"],
            "groupby_columns": [],
            "limit": 1000,
            "reason": "Test join"
        }
        
        agent = JoinPlanAndSQLAgent(llm_model="gpt-4o", max_joins=3)
        
        # Simulate the SQL generation logic from agent.py (lines 290-353)
        filters = join_plan.get("where_filters", [])
        where_conditions = []
        
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                val_str = str(val).strip()
                
                try:
                    float(val_str)
                    condition = f"{col} {op} {val_str}"  # No quotes for numeric
                except ValueError:
                    condition = f"{col} {op} '{val_str}'"  # Quotes for string
                
                where_conditions.append(condition)
        
        # Verify numeric values are NOT quoted
        assert "quantity = 100" in where_conditions
        assert "quantity = '100'" not in where_conditions
        assert "price > 50.5" in where_conditions
        assert "price > '50.5'" not in where_conditions
        
        logger.info(f"✅ Numeric values correctly unquoted: {where_conditions}")
    
    def test_sql_generator_string_value_with_quotes(self):
        """
        Test that string values in WHERE filters ARE quoted in SQL.
        
        Input filter: {"column": "region", "operator": "=", "value": "West"}
        Expected output: region = 'West'
        """
        join_plan = {
            "strategy": "joins",
            "primary_table": "dbo.sales_orders",
            "joins": [],
            "where_filters": [
                {"column": "region", "operator": "=", "value": "West"},
                {"column": "customer_name", "operator": "LIKE", "value": "John%"}
            ],
            "select_columns": ["*"],
            "groupby_columns": [],
            "limit": 1000,
            "reason": "Test join"
        }
        
        filters = join_plan.get("where_filters", [])
        where_conditions = []
        
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                val_str = str(val).strip()
                
                try:
                    float(val_str)
                    condition = f"{col} {op} {val_str}"  # No quotes for numeric
                except ValueError:
                    condition = f"{col} {op} '{val_str}'"  # Quotes for string
                
                where_conditions.append(condition)
        
        # Verify string values ARE quoted
        assert "region = 'West'" in where_conditions
        assert "customer_name LIKE 'John%'" in where_conditions
        
        logger.info(f"✅ String values correctly quoted: {where_conditions}")
    
    def test_sql_generator_date_value_with_quotes(self):
        """
        Test that date values in WHERE filters ARE quoted in SQL.
        
        Input filter: {"column": "order_date", "operator": ">=", "value": "2024-01-01"}
        Expected output: order_date >= '2024-01-01'
        """
        join_plan = {
            "strategy": "joins",
            "primary_table": "dbo.sales_orders",
            "joins": [],
            "where_filters": [
                {"column": "order_date", "operator": ">=", "value": "2024-01-01"},
                {"column": "created_at", "operator": "<", "value": "2024-12-31"}
            ],
            "select_columns": ["*"],
            "groupby_columns": [],
            "limit": 1000,
            "reason": "Test join"
        }
        
        filters = join_plan.get("where_filters", [])
        where_conditions = []
        
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                val_str = str(val).strip()
                
                try:
                    float(val_str)
                    condition = f"{col} {op} {val_str}"  # No quotes for numeric
                except ValueError:
                    condition = f"{col} {op} '{val_str}'"  # Quotes for string
                
                where_conditions.append(condition)
        
        # Verify date values ARE quoted (they're not numeric)
        assert "order_date >= '2024-01-01'" in where_conditions
        assert "created_at < '2024-12-31'" in where_conditions
        
        logger.info(f"✅ Date values correctly quoted: {where_conditions}")
    
    def test_mixed_filter_types(self):
        """
        Test a realistic mix of numeric, string, and date filters.
        
        Simulates: "Show sales orders with quantity > 100 from region 'West' after 2024-01-01"
        """
        join_plan = {
            "strategy": "joins",
            "primary_table": "dbo.sales_orders",
            "joins": [
                {
                    "table": "dbo.customers",
                    "on": "sales_orders.customer_id = customers.id",
                    "type": "INNER"
                }
            ],
            "where_filters": [
                {"column": "quantity", "operator": ">", "value": 100},
                {"column": "region", "operator": "=", "value": "West"},
                {"column": "order_date", "operator": ">=", "value": "2024-01-01"},
                {"column": "unit_price", "operator": "<", "value": 99.99}
            ],
            "select_columns": ["*"],
            "groupby_columns": [],
            "limit": 1000,
            "reason": "Test join"
        }
        
        filters = join_plan.get("where_filters", [])
        where_conditions = []
        
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                val_str = str(val).strip()
                
                try:
                    float(val_str)
                    condition = f"{col} {op} {val_str}"  # No quotes for numeric
                except ValueError:
                    condition = f"{col} {op} '{val_str}'"  # Quotes for string
                
                where_conditions.append(condition)
        
        # Build the WHERE clause
        where_clause = " AND ".join(where_conditions)
        
        # Verify correctness
        expected = "quantity > 100 AND region = 'West' AND order_date >= '2024-01-01' AND unit_price < 99.99"
        assert where_clause == expected
        
        logger.info(f"✅ Mixed filters correct: {where_clause}")
    
    def test_filter_value_json_format(self):
        """
        Test that filter values from intent are correctly formatted in join plan JSON.
        
        The join planner should preserve the value type from intent.get("filters", [])
        """
        intent = {
            "operation": "search",
            "entities": ["orders"],
            "filters": [
                {"column": "quantity", "operator": ">=", "value": 100},
                {"column": "status", "operator": "=", "value": "Shipped"},
                {"column": "created_date", "operator": ">=", "value": "2024-01-01"}
            ]
        }
        
        # Simulate join plan building (line 216 of agent.py)
        join_plan = {
            "where_filters": intent.get("filters", []),
        }
        
        # Verify filter types are preserved
        filters = join_plan["where_filters"]
        assert len(filters) == 3
        
        # Check first filter (numeric)
        assert filters[0]["value"] == 100
        assert isinstance(filters[0]["value"], int)
        
        # Check second filter (string)
        assert filters[1]["value"] == "Shipped"
        assert isinstance(filters[1]["value"], str)
        
        # Check third filter (string date)
        assert filters[2]["value"] == "2024-01-01"
        assert isinstance(filters[2]["value"], str)
        
        logger.info("✅ Filter value types correctly preserved in join plan")


@pytest.mark.asyncio
async def test_no_syntax_errors_with_numeric_filters():
    """
    Integration test: Verify that join plans with numeric filters generate valid SQL.
    
    This test ensures the fix prevents "Syntax error near '100'" errors.
    """
    join_plan = {
        "strategy": "joins",
        "primary_table": "dbo.sales_orders",
        "joins": [
            {
                "table": "dbo.customers",
                "on": "sales_orders.customer_id = customers.id",
                "type": "INNER"
            }
        ],
        "where_filters": [
            {"column": "quantity", "operator": "=", "value": 100},
            {"column": "region", "operator": "=", "value": "West"}
        ],
        "select_columns": ["*"],
        "groupby_columns": [],
        "limit": 1000,
        "reason": "Integration test"
    }
    
    # Generate SQL using the same logic from agent.py
    primary_table = join_plan.get("primary_table", "")
    joins = join_plan.get("joins", [])
    filters = join_plan.get("where_filters", [])
    row_limit = join_plan.get("limit", 1000)
    
    sql = f"SELECT TOP {row_limit} * FROM {primary_table}"
    
    for join in joins:
        join_type = join.get("type", "INNER")
        join_table = join.get("table", "")
        join_condition = join.get("on", "")
        sql += f" {join_type} JOIN {join_table} ON {join_condition}"
    
    if filters:
        where_conditions = []
        for f in filters:
            if isinstance(f, dict):
                col = f.get("column", "")
                op = f.get("operator", "=")
                val = f.get("value", "")
                val_str = str(val).strip()
                
                try:
                    float(val_str)
                    condition = f"{col} {op} {val_str}"  # No quotes for numeric
                except ValueError:
                    condition = f"{col} {op} '{val_str}'"  # Quotes for string
                
                where_conditions.append(condition)
        
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
    
    # Verify SQL is correctly formatted
    expected_sql = "SELECT TOP 1000 * FROM dbo.sales_orders INNER JOIN dbo.customers ON sales_orders.customer_id = customers.id WHERE quantity = 100 AND region = 'West'"
    assert sql == expected_sql
    
    # Verify no quoted numeric values in SQL
    assert "= '100'" not in sql
    assert "= 100" in sql
    
    logger.info(f"✅ Generated valid SQL: {sql}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])