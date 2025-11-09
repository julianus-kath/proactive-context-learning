"""
Deterministic MSSQL templates for common analytic query patterns.

The planner supplies a join_plan (built from discovery role hints) and the
intent metadata.  This builder turns that structured plan into a fully formed
MSSQL statement without relying on free-form LLM prompting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class TemplateBuildError(Exception):
    """Raised when a deterministic template cannot be produced."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def as_error_info(self) -> Dict[str, Any]:
        error = {
            "type": "TEMPLATE_BUILD_ERROR",
            "message": self.message,
        }
        if self.details:
            error["details"] = self.details
        return error


@dataclass
class DimensionInfo:
    table: str
    join_condition: str
    label_columns: List[str]
    id_columns: List[str]


class MSSQLTemplateBuilder:
    """Generate deterministic MSSQL queries from join plans."""

    def __init__(self, join_plan: Dict[str, Any], intent: Dict[str, Any], row_limit: int = 100):
        self.join_plan = join_plan or {}
        self.intent = intent or {}
        self.row_limit = max(1, int(row_limit or 100))
        self.required_action = (self.intent.get("required_action") or "").lower()

    # Public API -----------------------------------------------------------------

    def build(self) -> Dict[str, Any]:
        """Return {"sql": ..., "metadata": {...}} for the required action."""
        action = self.required_action

        if action == "sum_with_period":
            sql = self._build_sum_with_period()
            template = "sum_with_period"
        elif action == "sum_by_customer":
            sql = self._build_sum_by_customer()
            template = "sum_by_customer"
        elif action == "topk_sum_by_customer":
            sql = self._build_topk_sum_by_customer()
            template = "topk_sum_by_customer"
        elif action == "low_stock":
            sql = self._build_low_stock()
            template = "low_stock"
        else:
            raise TemplateBuildError(
                f"Unsupported required_action '{action}' for template builder.",
                {"required_action": action},
            )

        return {
            "sql": sql,
            "metadata": {"template": template},
        }

    # Template helpers -----------------------------------------------------------

    def _build_sum_with_period(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        date_col = self._date_column(required=True)
        time_window = self._time_window(required=True)

        start_expr, end_expr = self._time_window_bounds(time_window)
        metric_expr = self._table_column(fact, metric_col)
        date_expr = self._table_column(fact, date_col)

        sql = (
            f"SELECT SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
            f"WHERE {date_expr} >= {start_expr} AND {date_expr} < {end_expr}"
        )
        return sql

    def _build_sum_by_customer(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        customer_dim = self._dimension("customer", required=True)

        label_col = self._dimension_label(customer_dim)
        join_condition = self._normalize_join_condition(customer_dim.join_condition)

        metric_expr = self._table_column(fact, metric_col)
        label_expr = self._table_column(customer_dim.table, label_col)

        sql = (
            f"SELECT TOP {self.row_limit} {label_expr} AS customer_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
            f"JOIN {self._qualify_table(customer_dim.table)} ON {join_condition}\n"
            f"GROUP BY {label_expr}\n"
            f"ORDER BY total_metric DESC"
        )
        return sql

    def _build_topk_sum_by_customer(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        customer_dim = self._dimension("customer", required=True)
        label_col = self._dimension_label(customer_dim)
        join_condition = self._normalize_join_condition(customer_dim.join_condition)

        metric_expr = self._table_column(fact, metric_col)
        label_expr = self._table_column(customer_dim.table, label_col)
        top_k = self._top_k(default=5)

        sql = (
            f"SELECT TOP {top_k} {label_expr} AS customer_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
            f"JOIN {self._qualify_table(customer_dim.table)} ON {join_condition}\n"
            f"GROUP BY {label_expr}\n"
            f"ORDER BY total_metric DESC"
        )
        return sql

    def _build_low_stock(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        product_dim = self._dimension("product", required=False)

        metric_expr = self._table_column(fact, metric_col)
        threshold = self._stock_threshold(default=10)

        select_fields = [metric_expr]
        joins = ""

        if product_dim:
            label_col = self._dimension_label(product_dim)
            label_expr = self._table_column(product_dim.table, label_col)
            join_condition = self._normalize_join_condition(product_dim.join_condition)
            select_fields.insert(0, f"{label_expr} AS product_name")
            joins = (
                f"\nJOIN {self._qualify_table(product_dim.table)} "
                f"ON {join_condition}"
            )

        select_list = ", ".join(select_fields)

        sql = (
            f"SELECT TOP {self.row_limit} {select_list}\n"
            f"FROM {self._qualify_table(fact)}{joins}\n"
            f"WHERE {metric_expr} <= {threshold}\n"
            f"ORDER BY {metric_expr} ASC"
        )
        return sql

    # Data extraction helpers ----------------------------------------------------

    def _fact_table(self) -> str:
        fact = (
            self.join_plan.get("fact_table")
            or self.join_plan.get("primary_table")
            or self.join_plan.get("table")
        )
        if not fact:
            raise TemplateBuildError("Join plan is missing a fact table.")
        return fact

    def _metric_column(self, required: bool = False) -> str:
        metric_candidates = self.join_plan.get("metric_candidates") or {}
        if metric_candidates:
            best = sorted(
                metric_candidates.items(), key=lambda item: item[1], reverse=True
            )[0][0]
            return self._strip_table_prefix(best)
        if required:
            raise TemplateBuildError(
                "No metric candidates available for template.",
                {"metric_candidates": metric_candidates},
            )
        return ""

    def _date_column(self, required: bool = False) -> str:
        date_columns = self.join_plan.get("date_columns") or []
        if date_columns:
            return self._strip_table_prefix(date_columns[0])
        if required:
            raise TemplateBuildError("No date column identified for this template.")
        return ""

    def _dimension(self, role: str, required: bool) -> Optional[DimensionInfo]:
        raw = (self.join_plan.get("dimensions") or {}).get(role)
        if not raw:
            if required:
                raise TemplateBuildError(
                    f"Dimension '{role}' not available in join plan."
                )
            return None
        join_condition = raw.get("join_condition")
        if not join_condition:
            if required:
                raise TemplateBuildError(
                    f"Dimension '{role}' is missing a join condition."
                )
            return None
        return DimensionInfo(
            table=raw.get("table"),
            join_condition=join_condition,
            label_columns=raw.get("label_columns") or [],
            id_columns=raw.get("id_columns") or [],
        )

    def _dimension_label(self, dimension: DimensionInfo) -> str:
        if dimension.label_columns:
            return self._strip_table_prefix(dimension.label_columns[0])
        if dimension.id_columns:
            return self._strip_table_prefix(dimension.id_columns[0])
        raise TemplateBuildError(
            "Dimension is missing both label_columns and id_columns.",
            {"dimension": dimension.table},
        )

    def _time_window(self, required: bool) -> Dict[str, Any]:
        window = self.join_plan.get("time_window") or self.intent.get("time_window") or {}
        if window or not required:
            return window
        raise TemplateBuildError("Time window is required for this template.")

    def _time_window_bounds(self, window: Dict[str, Any]) -> Tuple[str, str]:
        """
        Return MSSQL expressions for inclusive start and exclusive end bounds.
        Prefers explicit start/end dates when provided, otherwise falls back to
        period-based heuristics (last month/quarter).
        """
        start = window.get("start")
        end = window.get("end")
        if start and end:
            start_expr = self._date_literal(start)
            exclusive_end = self._exclusive_end_literal(end)
            return start_expr, exclusive_end

        period = (window.get("period") or "").lower()
        if period == "last_month":
            return (
                "DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) - 1, 0)",
                "DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)",
            )
        if period == "last_quarter":
            return (
                "DATEADD(QUARTER, DATEDIFF(QUARTER, 0, GETDATE()) - 1, 0)",
                "DATEADD(QUARTER, DATEDIFF(QUARTER, 0, GETDATE()), 0)",
            )

        raise TemplateBuildError(
            "Unsupported or missing time window bounds.",
            {"time_window": window},
        )

    def _top_k(self, default: int) -> int:
        k = self.intent.get("top_k")
        if isinstance(k, int) and k > 0:
            return min(k, self.row_limit)
        # Attempt to parse from user text hints (stored in join_plan metadata?)
        return min(default, self.row_limit)

    def _stock_threshold(self, default: int) -> str:
        filters = self.intent.get("filters") or []
        for flt in filters:
            if not isinstance(flt, dict):
                continue
            operator = str(flt.get("operator") or "").strip()
            value = flt.get("value")
            if operator in {"<", "<=", "≤"}:
                try:
                    return str(int(float(value)))
                except Exception:
                    continue
        raise TemplateBuildError(
            "Low stock queries require a numeric threshold filter (<=).",
            {"filters": filters},
        )

    # Formatting helpers ---------------------------------------------------------

    def _qualify_table(self, table: str) -> str:
        schema, name = self._split_table_name(table)
        return f"[{schema}].[{name}]"

    def _table_column(self, table: str, column: str) -> str:
        column_name = self._strip_table_prefix(column)
        return f"{self._qualify_table(table)}.{self._qualify_column(column_name)}"

    def _strip_table_prefix(self, column: str) -> str:
        column = column or ""
        if "." in column:
            return column.split(".")[-1]
        return column

    def _qualify_column(self, column: str) -> str:
        name = self._strip_brackets(column)
        if not name:
            raise TemplateBuildError("Column name cannot be empty.")
        return f"[{name}]"

    def _normalize_join_condition(self, condition: str) -> str:
        """
        Replace any table/column tokens with fully qualified bracketed versions.
        """
        import re

        token = re.compile(r"([A-Za-z0-9_\[\]\.]+)\.([A-Za-z0-9_\[\]]+)")

        def repl(match: re.Match[str]) -> str:
            table_ref = match.group(1)
            column_ref = match.group(2)
            stripped_table = self._strip_brackets(table_ref)
            if "." in stripped_table:
                return self._table_column(table_ref, column_ref)
            alias = stripped_table
            return f"{alias}.{self._qualify_column(column_ref)}"

        normalized = token.sub(repl, condition)
        return normalized

    def _split_table_name(self, table: str) -> Tuple[str, str]:
        if not table:
            raise TemplateBuildError("Table name is required for template generation.")
        raw = self._strip_brackets(table)
        if "." in raw:
            schema, name = raw.split(".", 1)
        else:
            schema, name = "dbo", raw
        schema = schema.strip() or "dbo"
        name = name.strip()
        if not name:
            raise TemplateBuildError("Table name is invalid.", {"table": table})
        return schema, name

    def _strip_brackets(self, value: str) -> str:
        return value.replace("[", "").replace("]", "").strip()

    def _date_literal(self, iso_date: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_date)
        except ValueError as exc:
            raise TemplateBuildError(
                "Invalid ISO date for time window.",
                {"value": iso_date},
            ) from exc
        return f"DATEFROMPARTS({dt.year}, {dt.month}, {dt.day})"

    def _exclusive_end_literal(self, iso_date: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_date)
        except ValueError as exc:
            raise TemplateBuildError(
                "Invalid ISO end date for time window.",
                {"value": iso_date},
            ) from exc
        return f"DATEADD(DAY, 1, DATEFROMPARTS({dt.year}, {dt.month}, {dt.day}))"


