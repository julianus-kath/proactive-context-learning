"""
Template-based intent inference for ERP analytics.

Maps user queries to analytic templates and required actions:
- analytic_template: Query archetype (e.g., "SUM_WITH_PERIOD", "TOP_K_BY_METRIC")
- required_action: Concrete action (e.g., "sum_with_period", "topk_sum_by_customer")
- template_params: Structured parameters for SQL generation

This enables specialized SQL generation for common query archetypes.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


def infer_template_and_action(
    user_input: str,
    primary_entities: List[str],
    metrics: List[str],
    filters: List[Dict[str, Any]],
    time_window: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Heuristic classifier that maps raw intent info to:
      - analytic_template  (for join_sql)
      - required_action    (for SQL builder)
      - template_params    (extra hints)
    
    Returns:
        (analytic_template, required_action, template_params)
    """
    text = (user_input or "").lower()
    metrics_lc = [m.lower() for m in (metrics or [])]
    entities_lc = [e.lower() for e in (primary_entities or [])]

    template_params: Dict[str, Any] = {}

    # Common convenience flags
    asks_top = "top" in text or "höchsten" in text or "meisten" in text or "beste" in text
    asks_count = (
        any(m in ["count", "anzahl"] for m in metrics_lc)
        or text.strip().startswith(("how many", "wieviele", "wie viele"))
    )
    asks_total = (
        "total" in text or "gesamt" in text or "summe" in text or 
        "umsatz" in text or "revenue" in text or "sum" in text
    )
    has_time_window = bool(time_window)
    
    # Extract a bit of structure for params
    if primary_entities:
        template_params["entity"] = primary_entities[0]
    if metrics:
        template_params["metric"] = metrics[0]
    if time_window:
        template_params["period"] = time_window.get("period")
        template_params["start"] = time_window.get("start")
        template_params["end"] = time_window.get("end")

    # -------------------------
    # 1) Profit margin & ranked metrics
    # -------------------------
    if "profit margin" in text or "marge" in text or "deckungsbeitrag" in text or "gewinnmarge" in text:
        template_params["metric"] = "profit_margin"
        if asks_top:
            return "RANKED_METRICS", "ranked_metrics", template_params
        return "DERIVED_METRIC", "derived_metric", template_params

    # -------------------------
    # 2) Top-K by metric (products, customers, regions ...)
    # -------------------------
    if asks_top:
        # Try to distinguish customer vs product
        is_customer = any(e in ["customer", "customers", "kunde", "kunden", "client", "clients"] for e in entities_lc)
        is_product = any(e in ["product", "products", "artikel", "produkte"] for e in entities_lc)

        if is_customer and asks_total:
            # e.g. "Top 10 customers by revenue"
            return "TOP_K_BY_METRIC", "topk_sum_by_customer", template_params
        if is_product and asks_total:
            return "TOP_K_BY_METRIC", "topk_sum_by_product", template_params

        # Generic Top-K metric ranking
        return "TOP_K_BY_METRIC", "topk_by_metric", template_params

    # -------------------------
    # 3) Pure COUNT questions (how many X ...)
    # -------------------------
    # Important: only treat as COUNT_ENTITY if it's a genuine count question,
    # NOT "total sales" (which is SUM).
    if asks_count and not asks_total:
        return "COUNT_ENTITY", "count_entity", template_params

    # -------------------------
    # 4) Sum / total with a period filter (your failing example)
    # -------------------------
    if asks_total and has_time_window:
        # e.g. "total sales last month", "Gesamtumsatz 2024"
        # Often we just need one aggregated row.
        return "SUM_WITH_PERIOD", "sum_with_period", template_params

    # -------------------------
    # 5) Period comparison (this year vs last year, etc.)
    # -------------------------
    comp_tokens = ["vs", "versus", "compared to", "im vergleich zu", "gegenüber", "vs.", "comparison"]
    if any(tok in text for tok in comp_tokens) or "difference between" in text:
        # e.g. "Compare revenue this year vs last year"
        return "PERIOD_COMPARISON", "comparative_analysis", template_params

    # -------------------------
    # 6) Growth / trend / development over time
    # -------------------------
    if any(w in text for w in ["trend", "entwicklung", "over time", "über die zeit", "over the last", "over the past", "growth", "wachsen", "zunehmen", "abnehmen", "developed", "develop", "change", "progression"]):
        if "growth" in text or "wachstum" in text:
            return "GROWTH_ANALYSIS", "growth_analysis", template_params
        else:
            return "TREND_SERIES", "trend_series", template_params

    # -------------------------
    # 7) Sales by customer / product without top-k
    # -------------------------
    if asks_total and not has_time_window:
        # e.g. "Total sales by customer", "Total sales per product"
        is_customer = any(e in ["customer", "customers", "kunde", "kunden"] for e in entities_lc)
        is_product = any(e in ["product", "products", "artikel", "produkte"] for e in entities_lc)
        if is_customer:
            return "SUM_BY_CUSTOMER", "sum_by_customer", template_params
        if is_product:
            return "SUM_BY_PRODUCT", "sum_by_product", template_params

    # -------------------------
    # 8) Inventory / low stock style
    # -------------------------
    if "low stock" in text or "wenig bestand" in text or "knapp" in text or "low inventory" in text:
        return "LOW_STOCK", "low_stock", template_params

    # -------------------------
    # Default: no template
    # -------------------------
    return None, None, template_params
