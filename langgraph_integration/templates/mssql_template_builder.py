"""
Deterministic MSSQL templates for common analytic query patterns.

The planner supplies a join_plan (built from discovery role hints) and the
intent metadata.  This builder turns that structured plan into a fully formed
MSSQL statement without relying on free-form LLM prompting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import textwrap
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
    join_condition: Optional[str]
    label_columns: List[str]
    id_columns: List[str]
    self_join: bool = False


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
        elif action == "sum_by_product":
            sql = self._build_sum_by_product()
            template = "sum_by_product"
        elif action == "topk_sum_by_product":
            sql = self._build_topk_sum_by_product()
            template = "topk_sum_by_product"
        elif action == "low_stock":
            sql = self._build_low_stock()
            template = "low_stock"
        elif action == "growth_analysis":
            sql = self._build_growth_analysis()
            template = "growth_analysis"
        elif action == "comparative_analysis":
            sql = self._build_comparative_analysis()
            template = "comparative_analysis"
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

        metric_expr = self._table_column(fact, metric_col)
        label_col = self._dimension_label(customer_dim)

        if customer_dim.self_join or customer_dim.table == fact:
            label_expr = self._table_column(fact, label_col)
            join_clause = ""
        else:
            label_expr = self._table_column(customer_dim.table, label_col)
            join_condition = self._normalize_join_condition(customer_dim.join_condition or "")
            join_clause = f"JOIN {self._qualify_table(customer_dim.table)} ON {join_condition}\n"

        sql = (
            f"SELECT TOP {self.row_limit} {label_expr} AS customer_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
        )
        if join_clause:
            sql += join_clause
        sql += (
            f"GROUP BY {label_expr}\n"
            f"ORDER BY total_metric DESC"
        )
        return sql

    def _build_topk_sum_by_customer(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        customer_dim = self._dimension("customer", required=True)

        metric_expr = self._table_column(fact, metric_col)
        top_k = self._top_k(default=5)
        label_col = self._dimension_label(customer_dim)

        if customer_dim.self_join or customer_dim.table == fact:
            label_expr = self._table_column(fact, label_col)
            join_clause = ""
        else:
            label_expr = self._table_column(customer_dim.table, label_col)
            join_condition = self._normalize_join_condition(customer_dim.join_condition or "")
            join_clause = f"JOIN {self._qualify_table(customer_dim.table)} ON {join_condition}\n"

        sql = (
            f"SELECT TOP {top_k} {label_expr} AS customer_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
        )
        if join_clause:
            sql += join_clause
        sql += (
            f"GROUP BY {label_expr}\n"
            f"ORDER BY total_metric DESC"
        )
        return sql

    def _build_sum_by_product(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        product_dim = self._dimension("product", required=True)

        label_col = self._dimension_label(product_dim)
        metric_expr = self._table_column(fact, metric_col)
        if product_dim.self_join or product_dim.table == fact:
            label_expr = self._table_column(fact, label_col)
            join_clause = ""
        else:
            label_expr = self._table_column(product_dim.table, label_col)
            join_condition = self._normalize_join_condition(product_dim.join_condition or "")
            join_clause = f"JOIN {self._qualify_table(product_dim.table)} ON {join_condition}\n"

        sql = (
            f"SELECT TOP {self.row_limit} {label_expr} AS product_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
        )
        if join_clause:
            sql += join_clause
        sql += (
            f"GROUP BY {label_expr}\n"
            f"ORDER BY total_metric DESC"
        )
        return sql

    def _build_topk_sum_by_product(self) -> str:
        fact = self._fact_table()
        metric_col = self._metric_column(required=True)
        product_dim = self._dimension("product", required=True)
        label_col = self._dimension_label(product_dim)

        metric_expr = self._table_column(fact, metric_col)
        top_k = self._top_k(default=5)
        if product_dim.self_join or product_dim.table == fact:
            label_expr = self._table_column(fact, label_col)
            join_clause = ""
        else:
            label_expr = self._table_column(product_dim.table, label_col)
            join_condition = self._normalize_join_condition(product_dim.join_condition or "")
            join_clause = f"JOIN {self._qualify_table(product_dim.table)} ON {join_condition}\n"

        sql = (
            f"SELECT TOP {top_k} {label_expr} AS product_name, "
            f"SUM({metric_expr}) AS total_metric\n"
            f"FROM {self._qualify_table(fact)}\n"
        )
        if join_clause:
            sql += join_clause
        sql += (
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
            if product_dim.self_join or product_dim.table == fact:
                label_expr = self._table_column(fact, label_col)
                select_fields.insert(0, f"{label_expr} AS product_name")
            else:
                label_expr = self._table_column(product_dim.table, label_col)
                join_condition = self._normalize_join_condition(product_dim.join_condition or "")
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

    def _build_growth_analysis(self) -> str:
        fact = self._fact_table()
        date_col = self._date_column(required=True)
        date_expr = self._table_column(fact, date_col)

        metric_col = self._metric_column(required=False)
        if metric_col:
            metric_expr = self._table_column(fact, metric_col)
            agg_expr = f"SUM({metric_expr})"
            alias = "total_metric"
        else:
            agg_expr = "COUNT(*)"
            alias = "total_count"

        years = self._growth_years()
        qualified_table = self._qualify_table(fact)

        sql = textwrap.dedent(
            f"""
            WITH yearly AS (
                SELECT
                    YEAR({date_expr}) AS year_value,
                    {agg_expr} AS {alias}
                FROM {qualified_table}
                WHERE {date_expr} >= DATEADD(YEAR, -{years}, GETDATE())
                GROUP BY YEAR({date_expr})
            )
            SELECT
                year_value AS year,
                {alias},
                LAG({alias}) OVER (ORDER BY year_value) AS previous_{alias},
                CASE
                    WHEN LAG({alias}) OVER (ORDER BY year_value) > 0 THEN
                        ROUND(
                            ({alias} - LAG({alias}) OVER (ORDER BY year_value)) * 100.0 /
                            NULLIF(LAG({alias}) OVER (ORDER BY year_value), 0),
                            2
                        )
                    ELSE NULL
                END AS growth_percent
            FROM yearly
            ORDER BY year_value
            """
        ).strip()

        return sql

    def _build_comparative_analysis(self) -> str:
        fact = self._fact_table()
        date_col = self._date_column(required=True)
        date_expr = self._table_column(fact, date_col)

        metric_col = self._metric_column(required=False)
        if metric_col:
            metric_expr = self._table_column(fact, metric_col)
            agg_expr = f"SUM({metric_expr})"
            alias = "total_metric"
        else:
            agg_expr = "COUNT(*)"
            alias = "total_count"

        quarters = self._comparative_quarters()
        qualified_table = self._qualify_table(fact)

        sql = textwrap.dedent(
            f"""
            WITH quarterly AS (
                SELECT
                    YEAR({date_expr}) AS year_value,
                    DATEPART(QUARTER, {date_expr}) AS quarter_value,
                    CONCAT(YEAR({date_expr}), '-Q', DATEPART(QUARTER, {date_expr})) AS period_label,
                    {agg_expr} AS {alias}
                FROM {qualified_table}
                WHERE {date_expr} >= DATEADD(QUARTER, -{quarters}, GETDATE())
                GROUP BY YEAR({date_expr}), DATEPART(QUARTER, {date_expr})
            )
            SELECT
                year_value,
                quarter_value,
                period_label,
                {alias},
                LAG({alias}) OVER (ORDER BY year_value, quarter_value) AS previous_{alias},
                CASE
                    WHEN LAG({alias}) OVER (ORDER BY year_value, quarter_value) > 0 THEN
                        ROUND(
                            ({alias} - LAG({alias}) OVER (ORDER BY year_value, quarter_value)) * 100.0 /
                            NULLIF(LAG({alias}) OVER (ORDER BY year_value, quarter_value), 0),
                            2
                        )
                    ELSE NULL
                END AS delta_percent
            FROM quarterly
            ORDER BY year_value, quarter_value
            """
        ).strip()

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
            def preference_rank(column: str) -> int:
                name = column.lower()
                rank = 1
                if any(token in name for token in ("umsatz", "revenue", "gesamt", "total", "summe", "sales")):
                    rank = 5
                elif any(token in name for token in ("brutto", "netto", "wert", "amount", "value")):
                    rank = 4
                elif "preis" in name:
                    rank = 3
                elif "betrag" in name:
                    rank = 2
                if any(token in name for token in ("rabatt", "discount")):
                    rank -= 2
                return rank

            sorted_candidates = sorted(
                metric_candidates.items(),
                key=lambda item: (item[1], preference_rank(item[0])),
                reverse=True,
            )
            non_numeric_hints = (
                "nummer",
                "id",
                "code",
                "nr",
                "no",
                "kennung",
                "artnr",
                "gruppe",
                "group",
                "status",
            )

            for column, _ in sorted_candidates:
                name = column.lower()
                if any(hint in name for hint in non_numeric_hints):
                    continue
                return self._strip_table_prefix(column)

            return self._strip_table_prefix(sorted_candidates[0][0])
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
        self_join = bool(raw.get("self_join"))
        if not join_condition and not self_join:
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
            self_join=self_join,
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

    def _growth_years(self) -> int:
        window = self.intent.get("time_window") or self.join_plan.get("time_window") or {}
        if isinstance(window, dict):
            years = window.get("years")
            if isinstance(years, int) and years > 0:
                return years
            period = str(window.get("period") or "").lower()
            match = re.search(r"last[_\s]*(\d+)\s*year", period)
            if match:
                try:
                    return max(1, int(match.group(1)))
                except Exception:
                    pass
        fallback = self.intent.get("growth_years")
        if isinstance(fallback, int) and fallback > 0:
            return fallback
        return 3

    def _comparative_quarters(self) -> int:
        window = self.intent.get("time_window") or self.join_plan.get("time_window") or {}
        if isinstance(window, dict):
            quarters = window.get("quarters")
            if isinstance(quarters, int) and quarters > 0:
                return quarters
            period = str(window.get("period") or "").lower()
            match = re.search(r"last[_\s]*(\d+)\s*quarter", period)
            if match:
                try:
                    return max(2, int(match.group(1)))
                except Exception:
                    pass
        return 4

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


