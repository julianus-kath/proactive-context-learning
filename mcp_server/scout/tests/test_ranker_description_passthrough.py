"""
Verify the description field flows:

    catalog.table["description"]
        → RankedTable.description
        → RankedTable.to_dict()["description"]
        → search_tables response entry "description"

By default (SCOUT_DESCRIPTIONS_RANKING unset / false) the ranker must NOT use
description for scoring; it is a passthrough only. The opt-in scoring path
(SCOUT_DESCRIPTIONS_RANKING=true) is covered by
test_ranker_description_scoring.py.
"""

from __future__ import annotations

from typing import Any, Dict, List

from mcp_server.tools import _rank_entities_with_table_ranker
from mcp_server.tools.table_ranker import RankedTable, TableRanker


def _fake_customer_table(description: str = "") -> Dict[str, Any]:
    return {
        "schema": "dbo",
        "name": "Customers",
        "full_name": "dbo.Customers",
        "type": "TABLE",
        "estimated_rows": 91,
        "column_count": 11,
        "fk_count": 0,
        "columns": [
            {"name": "CustomerID", "type": "nchar"},
            {"name": "CompanyName", "type": "nvarchar"},
        ],
        "description": description,
    }


# ---------------------------------------------------------------------------
# RankedTable dataclass
# ---------------------------------------------------------------------------

def test_ranked_table_defaults_description_to_empty_string():
    rt = RankedTable(
        schema="dbo", name="X", full_name="dbo.X", score=0.5, reasons=[]
    )
    assert rt.description == ""
    assert rt.to_dict()["description"] == ""


def test_ranked_table_to_dict_roundtrips_description():
    rt = RankedTable(
        schema="dbo",
        name="X",
        full_name="dbo.X",
        score=0.5,
        reasons=[],
        description="Kundentabelle (Customer table).",
    )
    assert rt.to_dict()["description"] == "Kundentabelle (Customer table)."


# ---------------------------------------------------------------------------
# TableRanker passthrough
# ---------------------------------------------------------------------------

def test_ranker_passes_description_through_to_ranked_table():
    tables = [_fake_customer_table(description="Business description from SDG.")]
    ranker = TableRanker()
    ranked = ranker.rank_tables(
        tables=tables, entities=["customer"], intent_operations=["count"]
    )
    assert len(ranked) == 1
    assert ranked[0].description == "Business description from SDG."


def test_ranker_emits_empty_description_when_catalog_has_none():
    table = _fake_customer_table()
    table.pop("description", None)  # field missing entirely
    ranker = TableRanker()
    ranked = ranker.rank_tables(
        tables=[table], entities=["customer"], intent_operations=["count"]
    )
    assert ranked[0].description == ""


def test_ranker_does_not_use_description_for_scoring_when_kill_switch_off():
    """
    With description scoring disabled (default), a table whose only signal is
    a glowing description must not appear in the ranked output at all — the
    structural floor (entity/column/fuzzy match) is the sole gate.
    """
    unrelated_but_glowing = {
        "schema": "dbo",
        "name": "WeatherLog",
        "full_name": "dbo.WeatherLog",
        "columns": [],
        "description": "customer customer customer customer customer",
        "estimated_rows": 10,
    }
    on_point = _fake_customer_table()

    # Pin the kill-switch off explicitly so the test does not depend on env.
    ranked = TableRanker(use_description_scoring=False).rank_tables(
        tables=[unrelated_but_glowing, on_point],
        entities=["customer"],
        intent_operations=[],
    )
    # The name-matching Customers table must rank first.
    assert ranked[0].full_name == "dbo.Customers"
    # And WeatherLog must be filtered out entirely (no structural match).
    assert all(rt.full_name != "dbo.WeatherLog" for rt in ranked)


# ---------------------------------------------------------------------------
# MCP response wiring (_rank_entities_with_table_ranker)
# ---------------------------------------------------------------------------

def test_search_tables_response_includes_description_field():
    tables = [_fake_customer_table(description="SDG text here.")]
    resp = _rank_entities_with_table_ranker(
        tables=tables,
        query="customer",
        page=1,
        page_size=10,
        intent_data=None,
        source="test",
        cached=False,
    )
    results = resp["data"]["results"]
    assert len(results) == 1
    assert results[0]["description"] == "SDG text here."


def test_search_tables_response_description_is_empty_string_when_disabled():
    tables = [_fake_customer_table(description="")]
    resp = _rank_entities_with_table_ranker(
        tables=tables,
        query="customer",
        page=1,
        page_size=10,
        intent_data=None,
        source="test",
        cached=False,
    )
    results = resp["data"]["results"]
    assert results[0]["description"] == ""
