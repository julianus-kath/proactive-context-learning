"""Unit tests for TableNameNormalizer (mcp_server/scout/runner.py).

TableNameNormalizer is the bedrock of Scout's fuzzy ranking on German ERP
schemas — it splits camelCase table names into searchable tokens and
performs fuzzy matching that avoids false suffix collisions
(e.g. 'Bestellungen' ≠ 'Einstellungen').

Cases here mirror the docstring in runner.py.
"""
from mcp_server.scout.runner import TableNameNormalizer


class TestNormalize:
    def test_lowercases(self):
        assert TableNameNormalizer.normalize("Customers") == "customers"

    def test_strips_dbo_prefix(self):
        assert TableNameNormalizer.normalize("dbo.Customers") == "customers"

    def test_leaves_non_dbo_prefix_intact(self):
        # normalize() is schema-specific; it strips 'dbo.' only.
        assert (
            TableNameNormalizer.normalize("public.customers") == "public.customers"
        )


class TestExtractComponents:
    """Component extraction drives lexical matching on German ERP prefixes
    (KHK, BS, VK, etc.). Cases below are from the docstring at
    runner.py:65."""

    def test_khk_stat_vk_kunden(self):
        assert TableNameNormalizer.extract_components("KHKStatVKKunden") == [
            "khk", "stat", "vk", "kunden",
        ]

    def test_bs_einstellungen(self):
        assert TableNameNormalizer.extract_components("BSEinstellungen") == [
            "bs", "einstellungen",
        ]

    def test_ma_artikel(self):
        assert TableNameNormalizer.extract_components("MAArtikel") == [
            "ma", "artikel",
        ]

    def test_xml_parser(self):
        assert TableNameNormalizer.extract_components("XMLParser") == [
            "xml", "parser",
        ]

    def test_short_components_filtered(self):
        # Components of len < 2 are dropped.
        components = TableNameNormalizer.extract_components("AArtikel")
        assert "a" not in components

    def test_plain_lowercase_name_has_single_component(self):
        assert TableNameNormalizer.extract_components("customers") == ["customers"]


class TestSafeFuzzyMatch:
    """safe_fuzzy_match prevents false suffix matches between words that
    share a common suffix (the motivating case: 'Bestellungen' vs
    'Einstellungen'). See runner.py:83."""

    def test_exact_substring_returns_high(self):
        # 'stell' is a substring of 'einstellungen' → 0.9 branch
        assert (
            TableNameNormalizer.safe_fuzzy_match("stell", "einstellungen") == 0.9
        )

    def test_substring_self_returns_high(self):
        assert (
            TableNameNormalizer.safe_fuzzy_match("customers", "customers") == 0.9
        )

    def test_prefix_overlap_allows_fuzzy_match(self):
        score = TableNameNormalizer.safe_fuzzy_match("cust", "customers")
        assert 0.0 < score <= 1.0

    def test_false_suffix_collision_is_penalized(self):
        """The motivating bug: these should NOT return a naive 0.83+ ratio."""
        score = TableNameNormalizer.safe_fuzzy_match(
            "bestellungen", "einstellungen"
        )
        assert score < 0.5

    def test_unrelated_strings_return_low(self):
        score = TableNameNormalizer.safe_fuzzy_match("orders", "suppliers")
        assert score < 0.5
