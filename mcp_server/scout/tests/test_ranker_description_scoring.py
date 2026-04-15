"""
Verify the opt-in description-scoring path in TableRanker.

The kill-switch is `SCOUT_DESCRIPTIONS_RANKING` (default false). When enabled,
the ranker uses token-coverage substring matching of query entities against
the table description (SDG v2 catalog field). Behaviour requirements:

  - Default (kill-switch off): no contribution to score, no inclusion of
    structurally-irrelevant tables. Covered by passthrough test.
  - Kill-switch on:
      * Token coverage = (entities found as substring in lowered description) /
        (count of entities with len >= 3).
      * Tables qualify for inclusion on description alone only when coverage
        is >= 0.5 (otherwise descriptions act as a re-rank tiebreaker within
        the existing structurally-qualified candidate set).
      * A glowing-but-unrelated table must not outrank a table with a strong
        name/column match.
"""

from __future__ import annotations

from typing import Any, Dict

from mcp_server.tools.table_ranker import TableRanker


def _table(
    name: str,
    description: str = "",
    columns: list | None = None,
    estimated_rows: int = 10,
) -> Dict[str, Any]:
    return {
        "schema": "dbo",
        "name": name,
        "full_name": f"dbo.{name}",
        "type": "TABLE",
        "estimated_rows": estimated_rows,
        "column_count": len(columns or []),
        "fk_count": 0,
        "columns": columns or [],
        "description": description,
    }


# ---------------------------------------------------------------------------
# _score_description_match unit behavior
# ---------------------------------------------------------------------------

def test_description_score_returns_zero_when_no_description():
    ranker = TableRanker(use_description_scoring=True)
    assert ranker._score_description_match(_table("X"), ["customer"]) == 0.0


def test_description_score_returns_zero_when_no_entities():
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table("X", description="customer order revenue")
    assert ranker._score_description_match(tbl, []) == 0.0


def test_description_score_filters_short_entities():
    """Entities with <3 chars must be ignored to avoid spurious matches."""
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table("X", description="zz aa bb")
    # 'aa' and 'bb' are <3 chars so should be filtered → no valid entities → 0
    assert ranker._score_description_match(tbl, ["aa", "bb"]) == 0.0


def test_description_score_full_coverage():
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table("X", description="Tracks customer orders and revenue trends.")
    # all three entities present → 3/3 = 1.0
    score = ranker._score_description_match(tbl, ["customer", "order", "revenue"])
    assert score == 1.0


def test_description_score_partial_coverage():
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table("X", description="Tracks customer addresses only.")
    # only 'customer' matches; 'order' and 'revenue' do not → 1/3 ≈ 0.333
    score = ranker._score_description_match(
        tbl, ["customer", "order", "revenue"]
    )
    assert abs(score - 1.0 / 3.0) < 1e-9


def test_description_score_handles_german_compound_words():
    """A German entity like 'kunden' must match inside compounds like
    'Kundenkundendemo'. Substring (not strict token) matching is what makes
    crosslingual rescue work."""
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table(
        "customer_customer_demo",
        description="Kundenkundendemo (Customer Customer Demo) — Die Tabelle...",
    )
    score = ranker._score_description_match(tbl, ["kunden"])
    assert score == 1.0


def test_description_score_is_case_insensitive():
    ranker = TableRanker(use_description_scoring=True)
    tbl = _table("X", description="CUSTOMER ORDERS REVENUE")
    score = ranker._score_description_match(tbl, ["customer", "order"])
    assert score == 1.0


# ---------------------------------------------------------------------------
# rank_tables integration: kill-switch behavior
# ---------------------------------------------------------------------------

def test_kill_switch_off_means_no_description_contribution():
    """A table whose description matches the query but whose name does not
    must be filtered out when scoring is off."""
    only_desc = _table(
        "Z9", description="customer order revenue trends summary"
    )
    ranked = TableRanker(use_description_scoring=False).rank_tables(
        tables=[only_desc],
        entities=["customer", "order", "revenue"],
        intent_operations=[],
    )
    assert ranked == []


def test_kill_switch_on_rescues_table_with_strong_description_coverage():
    """With scoring on and ≥0.5 entity coverage in description, a table whose
    name does not match the query should still appear in the ranked set."""
    only_desc = _table(
        "Z9", description="Tracks customer orders and revenue trends."
    )
    ranked = TableRanker(use_description_scoring=True).rank_tables(
        tables=[only_desc],
        entities=["customer", "order", "revenue"],
        intent_operations=[],
    )
    assert len(ranked) == 1
    assert ranked[0].full_name == "dbo.Z9"
    assert any("Description match" in r for r in ranked[0].reasons)


def test_kill_switch_on_does_not_outrank_strong_name_match():
    """A glowing description on an unrelated table must not beat an exact name
    match on the right table — descriptions are a tiebreaker, not a primary
    signal."""
    glowing_unrelated = _table(
        "WeatherLog",
        description="customer customer customer customer customer",
    )
    on_point = _table(
        "Customers",
        columns=[{"name": "CustomerID", "type": "nchar"}],
        estimated_rows=91,
    )
    ranked = TableRanker(use_description_scoring=True).rank_tables(
        tables=[glowing_unrelated, on_point],
        entities=["customer"],
        intent_operations=[],
    )
    # Customers (entity_match * 1.0) >> WeatherLog (description_match * 0.4)
    assert ranked[0].full_name == "dbo.Customers"


def test_below_half_coverage_does_not_qualify_alone():
    """Description match below 0.5 coverage must NOT qualify a table for
    inclusion when no structural signal is present. It only acts as a
    tiebreaker within the already-qualified candidate set."""
    weak_desc = _table(
        "Z9", description="something about customers only"
    )
    # Entities: customer, order, revenue, employee → only 'customer' in desc
    # coverage = 1/4 = 0.25 < 0.5 → must not qualify on description alone
    ranked = TableRanker(use_description_scoring=True).rank_tables(
        tables=[weak_desc],
        entities=["customer", "order", "revenue", "employee"],
        intent_operations=[],
    )
    assert ranked == []


def test_description_acts_as_tiebreaker_among_qualified_tables():
    """Two tables both qualify structurally via a weak fuzzy signal. The one
    whose description also matches the query should rank higher. Structural
    scores must be kept weak enough here that neither saturates to 1.0, so
    the description contribution can differentiate."""
    # Both tables have a weak column partial-match on 'client' → 'client_ref'
    # (reverse substring, 0.5), no name match, no column exact match.
    plain = _table(
        "Ledger",
        columns=[{"name": "client_ref", "type": "int"}],
        description="",
    )
    annotated = _table(
        "Register",
        columns=[{"name": "client_ref", "type": "int"}],
        description="Tracks client transactions and reconciliation entries.",
    )
    ranked = TableRanker(use_description_scoring=True).rank_tables(
        tables=[plain, annotated],
        entities=["client", "transaction"],
        intent_operations=[],
    )
    assert len(ranked) == 2
    assert ranked[0].full_name == "dbo.Register"
    assert ranked[0].score > ranked[1].score


# ---------------------------------------------------------------------------
# env var wiring
# ---------------------------------------------------------------------------

def test_env_var_off_by_default(monkeypatch):
    monkeypatch.delenv("SCOUT_DESCRIPTIONS_RANKING", raising=False)
    assert TableRanker().use_description_scoring is False


def test_env_var_truthy_values_enable_scoring(monkeypatch):
    for v in ("true", "True", "1", "yes", "on", "TRUE"):
        monkeypatch.setenv("SCOUT_DESCRIPTIONS_RANKING", v)
        assert TableRanker().use_description_scoring is True, f"failed for {v!r}"


def test_env_var_falsy_values_keep_scoring_off(monkeypatch):
    for v in ("false", "0", "no", "off", ""):
        monkeypatch.setenv("SCOUT_DESCRIPTIONS_RANKING", v)
        assert TableRanker().use_description_scoring is False, f"failed for {v!r}"


def test_explicit_constructor_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("SCOUT_DESCRIPTIONS_RANKING", "true")
    assert TableRanker(use_description_scoring=False).use_description_scoring is False
    monkeypatch.setenv("SCOUT_DESCRIPTIONS_RANKING", "false")
    assert TableRanker(use_description_scoring=True).use_description_scoring is True
