import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from langgraph_integration.agents.join_sql.agent import MSSQLTemplateBuilder, TemplateBuildError


def build_join_plan(**overrides):
    base = {
        "fact_table": "dbo.FactSales",
        "metric_candidates": {"SalesAmount": 0.95},
        "dimensions": {},
        "date_columns": ["OrderDate"],
    }
    base.update(overrides)
    return base


def test_topk_sum_by_customer_template():
    join_plan = build_join_plan(
        dimensions={
            "customer": {
                "table": "dbo.Customers",
                "join_condition": "dbo.FactSales.CustomerID = dbo.Customers.ID",
                "label_columns": ["CustomerName"],
                "id_columns": ["ID"],
            }
        }
    )
    intent = {"required_action": "topk_sum_by_customer", "top_k": 7}
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=100)
    result = builder.build()

    sql = result["sql"].upper()
    assert "SELECT TOP 7" in sql
    assert "SUM(" in sql and "GROUP BY" in sql
    assert "ORDER BY" in sql
    assert "CUSTOMER_NAME" in sql


def test_sum_with_period_template():
    join_plan = build_join_plan()
    intent = {
        "required_action": "sum_with_period",
        "time_window": {"start": "2024-01-01", "end": "2024-02-01"},
    }
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=100)
    result = builder.build()

    sql = result["sql"].upper()
    assert "SUM(" in sql
    assert "WHERE" in sql
    assert "DATEFROMPARTS(2024, 1, 1)" in sql
    assert "DATEADD(DAY, 1, DATEFROMPARTS(2024, 2, 1))" in sql


def test_low_stock_template_requires_threshold():
    join_plan = build_join_plan(metric_candidates={"QuantityOnHand": 0.8})
    intent = {"required_action": "low_stock", "filters": [{"field": "QuantityOnHand", "operator": "<=", "value": 15}]}
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=50)
    result = builder.build()

    sql = result["sql"].upper()
    assert "TOP 50" in sql
    assert "WHERE" in sql and "<= 15" in sql
    assert "ORDER BY" in sql


def test_low_stock_without_threshold_raises():
    join_plan = build_join_plan(metric_candidates={"QuantityOnHand": 0.8})
    intent = {"required_action": "low_stock", "filters": []}
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=50)
    with pytest.raises(TemplateBuildError):
        builder.build()


def test_topk_sum_by_product_template():
    join_plan = build_join_plan(
        dimensions={
            "product": {
                "table": "dbo.Products",
                "join_condition": "dbo.FactSales.ProductID = dbo.Products.ID",
                "label_columns": ["ProductName"],
                "id_columns": ["ID"],
            }
        }
    )
    intent = {"required_action": "topk_sum_by_product", "top_k": 5}
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=25)
    result = builder.build()

    sql = result["sql"].upper()
    assert "SELECT TOP 5" in sql
    assert "PRODUCT_NAME" in sql
    assert "SUM(" in sql
    assert "ORDER BY" in sql


def test_sum_by_product_template():
    join_plan = build_join_plan(
        dimensions={
            "product": {
                "table": "dbo.Products",
                "join_condition": "dbo.FactSales.ProductID = dbo.Products.ID",
                "label_columns": ["ProductName"],
                "id_columns": ["ID"],
            }
        }
    )
    intent = {"required_action": "sum_by_product"}
    builder = MSSQLTemplateBuilder(join_plan, intent, row_limit=50)
    result = builder.build()

    sql = result["sql"].upper()
    assert "SELECT TOP 50" in sql
    assert "PRODUCT_NAME" in sql
    assert "SUM(" in sql
