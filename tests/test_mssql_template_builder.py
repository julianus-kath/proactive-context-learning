import pytest

from langgraph_integration.templates import MSSQLTemplateBuilder, TemplateBuildError


def build_join_plan(**overrides):
    plan = {
        "strategy": "template",
        "fact_table": "dbo.Sales",
        "primary_table": "dbo.Sales",
        "metric_candidates": {"Amount": 1.0},
        "date_columns": ["OrderDate"],
        "entity_keys": {"customer": ["CustomerID"]},
        "filters": [],
        "time_window": None,
        "joins": [],
        "dimensions": {},
        "fk_hints": [],
        "required_action": None,
        "fact_estimated_rows": 1000,
    }
    plan.update(overrides)
    return plan


def test_sum_with_period_template():
    join_plan = build_join_plan(
        time_window={"start": "2024-01-01", "end": "2024-01-31"},
    )
    intent = {"required_action": "sum_with_period"}

    builder = MSSQLTemplateBuilder(join_plan=join_plan, intent=intent, row_limit=100)
    result = builder.build()

    expected_sql = (
        "SELECT SUM([dbo].[Sales].[Amount]) AS total_metric\n"
        "FROM [dbo].[Sales]\n"
        "WHERE [dbo].[Sales].[OrderDate] >= DATEFROMPARTS(2024, 1, 1) "
        "AND [dbo].[Sales].[OrderDate] < DATEADD(DAY, 1, DATEFROMPARTS(2024, 1, 31))"
    )

    assert result["sql"] == expected_sql
    assert result["metadata"]["template"] == "sum_with_period"


def test_topk_sum_by_customer_template():
    join_plan = build_join_plan(
        dimensions={
            "customer": {
                "table": "dbo.Customers",
                "join_condition": "dbo.Sales.CustomerID = dbo.Customers.CustomerID",
                "label_columns": ["CustomerName"],
                "id_columns": ["CustomerID"],
            }
        },
    )
    intent = {"required_action": "topk_sum_by_customer", "top_k": 5}

    builder = MSSQLTemplateBuilder(join_plan=join_plan, intent=intent, row_limit=100)
    result = builder.build()

    expected_sql = (
        "SELECT TOP 5 [dbo].[Customers].[CustomerName] AS customer_name, "
        "SUM([dbo].[Sales].[Amount]) AS total_metric\n"
        "FROM [dbo].[Sales]\n"
        "JOIN [dbo].[Customers] ON [dbo].[Sales].[CustomerID] = [dbo].[Customers].[CustomerID]\n"
        "GROUP BY [dbo].[Customers].[CustomerName]\n"
        "ORDER BY total_metric DESC"
    )

    assert result["sql"] == expected_sql


def test_low_stock_template_without_dimension():
    join_plan = build_join_plan(
        fact_table="dbo.Inventory",
        primary_table="dbo.Inventory",
        metric_candidates={"QuantityOnHand": 1.0},
    )
    intent = {"required_action": "low_stock"}

    builder = MSSQLTemplateBuilder(join_plan=join_plan, intent=intent, row_limit=50)
    result = builder.build()

    expected_sql = (
        "SELECT TOP 50 [dbo].[Inventory].[QuantityOnHand]\n"
        "FROM [dbo].[Inventory]\n"
        "WHERE [dbo].[Inventory].[QuantityOnHand] <= 10\n"
        "ORDER BY [dbo].[Inventory].[QuantityOnHand] ASC"
    )

    assert result["sql"] == expected_sql


def test_template_build_error_when_metric_missing():
    join_plan = build_join_plan(metric_candidates={})
    intent = {"required_action": "sum_with_period"}

    builder = MSSQLTemplateBuilder(join_plan=join_plan, intent=intent)

    with pytest.raises(TemplateBuildError):
        builder.build()

