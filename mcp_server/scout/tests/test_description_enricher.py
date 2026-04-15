"""
Unit tests for mcp_server.scout.description_enricher.

Covers:
- Null generator stamps every table with ""
- Enabled generator populates each table
- overwrite_existing respects / bypasses existing values
- Generator exceptions are swallowed and yield ""
- Non-dict entries are skipped
"""

from __future__ import annotations

from typing import Any, Dict, List

from mcp_server.scout.description_enricher import enrich_tables_with_descriptions
from mcp_server.scout.description_generator import NullDescriptionGenerator


class _RecordingGenerator:
    enabled = True

    def __init__(self, produces: str = "desc"):
        self.produces = produces
        self.seen: List[str] = []

    def generate(self, table_info: Dict[str, Any]) -> str:
        self.seen.append(str(table_info.get("full_name")))
        return f"{self.produces}:{table_info.get('full_name')}"


def _tables():
    return [
        {"full_name": "dbo.A", "name": "A"},
        {"full_name": "dbo.B", "name": "B", "description": "preexisting"},
    ]


def test_null_generator_stamps_empty_strings():
    tables = _tables()
    written = enrich_tables_with_descriptions(tables, NullDescriptionGenerator())
    # Preserves existing because overwrite_existing=False
    assert tables[0]["description"] == ""
    assert tables[1]["description"] == "preexisting"
    assert written == 1


def test_null_generator_with_overwrite_clears_all():
    tables = _tables()
    enrich_tables_with_descriptions(
        tables, NullDescriptionGenerator(), overwrite_existing=True
    )
    assert tables[0]["description"] == ""
    assert tables[1]["description"] == ""


def test_enabled_generator_populates_missing_only_by_default():
    tables = _tables()
    gen = _RecordingGenerator()
    enrich_tables_with_descriptions(tables, gen)
    assert tables[0]["description"] == "desc:dbo.A"
    assert tables[1]["description"] == "preexisting"
    assert gen.seen == ["dbo.A"]  # B was skipped


def test_enabled_generator_with_overwrite_regenerates_all():
    tables = _tables()
    gen = _RecordingGenerator()
    enrich_tables_with_descriptions(tables, gen, overwrite_existing=True)
    assert tables[0]["description"] == "desc:dbo.A"
    assert tables[1]["description"] == "desc:dbo.B"
    assert gen.seen == ["dbo.A", "dbo.B"]


def test_generator_exceptions_fall_back_to_empty_string():
    class _BoomGen:
        enabled = True

        def generate(self, table_info):
            raise RuntimeError("api down")

    tables = [{"full_name": "dbo.A", "name": "A"}]
    enrich_tables_with_descriptions(tables, _BoomGen())
    assert tables[0]["description"] == ""


def test_non_dict_entries_are_skipped():
    tables = [{"full_name": "dbo.A", "name": "A"}, "not a dict", None]
    gen = _RecordingGenerator()
    enrich_tables_with_descriptions(tables, gen)
    assert tables[0]["description"] == "desc:dbo.A"
    assert tables[1] == "not a dict"  # unchanged
    assert tables[2] is None


def test_empty_catalog_is_noop():
    assert enrich_tables_with_descriptions([], NullDescriptionGenerator()) == 0
    assert enrich_tables_with_descriptions([], _RecordingGenerator()) == 0
