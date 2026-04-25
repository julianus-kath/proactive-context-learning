"""Unit tests for the evaluation metric functions used in the H2a pipeline.

These functions live in eval/run_h2a_full_pipeline.py and produce the numbers
reported in the thesis. If these are wrong, the thesis numbers are wrong.
"""
from eval.run_h2a_full_pipeline import compute_recall, normalize_table


class TestNormalizeTable:
    def test_lowercases(self):
        assert normalize_table("Customers") == "customers"

    def test_strips_schema_prefix_dbo(self):
        assert normalize_table("dbo.Customers") == "customers"

    def test_strips_schema_prefix_public(self):
        assert normalize_table("public.orders") == "orders"

    def test_strips_whitespace(self):
        assert normalize_table("  Orders  ") == "orders"

    def test_keeps_only_last_segment_for_nested_dots(self):
        assert normalize_table("db.schema.Table") == "table"

    def test_plain_name_unchanged_modulo_case(self):
        assert normalize_table("orders") == "orders"


class TestComputeRecall:
    def test_empty_required_returns_one(self):
        """Vacuous full recall when no tables are required."""
        assert compute_recall(retrieved=set(), required=set()) == 1.0
        assert compute_recall(retrieved={"anything"}, required=set()) == 1.0

    def test_no_overlap_returns_zero(self):
        assert compute_recall(
            retrieved={"orders", "products"},
            required={"customers", "employees"},
        ) == 0.0

    def test_full_overlap_returns_one(self):
        assert compute_recall(
            retrieved={"customers", "orders"},
            required={"customers", "orders"},
        ) == 1.0

    def test_partial_overlap_half(self):
        assert compute_recall(
            retrieved={"customers", "products"},
            required={"customers", "orders"},
        ) == 0.5

    def test_partial_overlap_one_third(self):
        assert abs(compute_recall(
            retrieved={"customers"},
            required={"customers", "orders", "order_details"},
        ) - (1 / 3)) < 1e-9

    def test_case_insensitive(self):
        """Recall is computed after case-normalization."""
        assert compute_recall(
            retrieved={"CUSTOMERS", "Orders"},
            required={"customers", "orders"},
        ) == 1.0

    def test_schema_prefix_ignored(self):
        """dbo.Customers must match customers — H2a recall depends on this."""
        assert compute_recall(
            retrieved={"dbo.Customers", "public.Orders"},
            required={"customers", "orders"},
        ) == 1.0

    def test_extra_retrieved_tables_do_not_hurt_recall(self):
        """Recall measures coverage only — extras are not penalized.

        This is exactly why precision/F1 need to be reported alongside for
        any claim about retrieval quality.
        """
        assert compute_recall(
            retrieved={"customers", "orders", "products", "employees"},
            required={"customers", "orders"},
        ) == 1.0
